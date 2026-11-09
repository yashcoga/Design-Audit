"""Capture a page for a design review: desktop (1440x900) + mobile (390x844 @2x).

Usage:  python capture.py URL --out DIR

Writes to DIR:
  desktop-full.png, mobile-full.png        full-page screenshots (desktop 1x, mobile 2x pixels)
  desktop-sNN.jpg, mobile-sNN.jpg          slices small enough to look at (desktop 1800px, mobile 2400px tall)
  desktop-fold.png, mobile-fold.png        first screen only
  text.txt                                 visible page text
  facts.json                               page height, fonts, headings, buttons/links (+ where they go),
                                           form submit button position vs the first screen, sideways scroll,
                                           iframes (GHL forms often live in one), images
Ad pixels and form submissions are blocked. Nothing is submitted.
"""
import argparse
import json
import os
import re

from PIL import Image
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
DEVICES = {
    "desktop": dict(viewport={"width": 1440, "height": 900}, user_agent=UA),
    "mobile": dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                   user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
                              "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"),
}
BLOCK = re.compile(r"facebook\.(com|net)/tr|connect\.facebook|googletagmanager|google-analytics|doubleclick|"
                   r"analytics\.tiktok|tiktok\.com/i18n/pixel|clarity\.ms|hotjar")
FORM_POST = re.compile(r"form|submit|survey|order", re.I)

FACTS_JS = r"""() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const pos = e => Math.round(e.getBoundingClientRect().top + scrollY);
  const fonts = {};
  for (const e of document.querySelectorAll('h1,h2,h3,h4,p,li,a,button,span,label')) {
    if (!vis(e) || !e.innerText || !e.innerText.trim()) continue;
    const cs = getComputedStyle(e);
    const k = cs.fontFamily.split(',')[0].replace(/["']/g, '') + ' ' + cs.fontWeight;
    fonts[k] = (fonts[k] || 0) + 1;
  }
  const heads = [...document.querySelectorAll('h1,h2,h3')].filter(vis).map(e => {
    const cs = getComputedStyle(e);
    const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
    return {tag: e.tagName, y: pos(e), size: cs.fontSize, lines: Math.round(e.getBoundingClientRect().height / lh),
            text: e.innerText.trim().slice(0, 90)};
  });
  const clicks = [...document.querySelectorAll('a,button,[role=button],input[type=submit]')].filter(vis).map(e => ({
    text: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 60),
    href: e.getAttribute('href'), y: pos(e),
    w: Math.round(e.getBoundingClientRect().width), h: Math.round(e.getBoundingClientRect().height)}));
  const submit = [...document.querySelectorAll('button,input[type=submit]')].filter(vis).find(e => e.closest('form'));
  const iframes = [...document.querySelectorAll('iframe')].filter(vis).map(f => ({
    src: (f.src || '').slice(0, 120), y: pos(f), h: Math.round(f.getBoundingClientRect().height)}));
  const imgs = [...document.querySelectorAll('img')].filter(vis).map(i => ({
    src: (i.currentSrc || i.src).slice(-80), y: pos(i), w: Math.round(i.getBoundingClientRect().width),
    natural_w: i.naturalWidth, alt: i.alt}));
  return {title: document.title, height: document.documentElement.scrollHeight, viewport_h: innerHeight,
          sideways_scroll: document.documentElement.scrollWidth > innerWidth + 2,
          form_submit_y: submit ? pos(submit) : null, fonts, heads, clicks, iframes, imgs};
}"""

PREP_JS = r"""() => {
  for (const e of document.querySelectorAll('*')) {
    const cs = getComputedStyle(e);
    if (cs.contentVisibility === 'auto') e.style.setProperty('content-visibility', 'visible', 'important');
    if (cs.backgroundAttachment === 'fixed') e.style.setProperty('background-attachment', 'scroll', 'important');
  }
}"""


def route(r):
    req = r.request
    if BLOCK.search(req.url) or (req.method == "POST" and FORM_POST.search(req.url)):
        return r.abort()
    return r.continue_()


def prepare(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3500)
    y, h = 0, page.evaluate("document.body.scrollHeight")
    while y < h + 1000 and y < 40000:  # scroll down in steps so lazy images and animations load
        page.evaluate("y => window.scrollTo(0, y)", y)
        page.wait_for_timeout(90)
        y += 500
        h = page.evaluate("document.body.scrollHeight")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(900)
    page.evaluate(PREP_JS)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    facts = {"url": a.url}
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        for dev, opts in DEVICES.items():
            ctx = b.new_context(**opts)
            ctx.route("**/*", route)
            pg = ctx.new_page()
            prepare(pg, a.url)
            pg.screenshot(path=f"{a.out}/{dev}-fold.png")
            pg.screenshot(path=f"{a.out}/{dev}-full.png", full_page=True)
            facts[dev] = pg.evaluate(FACTS_JS)
            if dev == "desktop":
                with open(f"{a.out}/text.txt", "w", encoding="utf-8") as fh:
                    fh.write(pg.inner_text("body"))
            ctx.close()
        b.close()
    for dev, step in (("desktop", 1800), ("mobile", 2400)):
        im = Image.open(f"{a.out}/{dev}-full.png").convert("RGB")
        W, H = im.size
        n = 0
        for i, y in enumerate(range(0, H, step)):
            im.crop((0, y, W, min(H, y + step))).save(f"{a.out}/{dev}-s{i:02d}.jpg", quality=80)
            n = i + 1
        facts[dev]["screenshot_px"] = [W, H]
        facts[dev]["slices"] = n
    with open(f"{a.out}/facts.json", "w", encoding="utf-8") as fh:
        json.dump(facts, fh, indent=1, ensure_ascii=False)
    for dev in DEVICES:
        f = facts[dev]
        print(f"{dev}: page {f['height']}px tall, first screen {f['viewport_h']}px, form button at "
              f"{f['form_submit_y']} (None = inside an iframe or no form), sideways scroll: {f['sideways_scroll']}, "
              f"{f['slices']} slices")
    print("title:", facts["desktop"]["title"])


if __name__ == "__main__":
    main()
