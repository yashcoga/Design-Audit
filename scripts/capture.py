"""Capture a page for a design review: desktop (1440x900) + mobile (390x844 @2x).

Usage:  python capture.py URL --out DIR
        python capture.py URL1 URL2 ... --out DIR     # whole funnel: 4 pages at a time, each in DIR/<page>/

Writes to DIR:
  desktop-full.png, mobile-full.png        full-page screenshots (desktop 1x, mobile 2x pixels)
  desktop-sNN.jpg, mobile-sNN.jpg          slices small enough to look at (desktop 1800px, mobile 2400px tall)
  desktop-fold.png, mobile-fold.png        first screen only
  text.txt                                 visible page text
  facts.json                               page height, fonts, headings, buttons/links (+ where they go),
                                           form submit button position vs the first screen, sideways scroll,
                                           iframes (GHL forms often live in one), images
  flags (in facts.json and printed)        automatic design checks, same as funnel-audit's scan_page.py:
                                           button/form below the first screen, headline too long, one word alone on
                                           a last line, button text wrapping on mobile, body text under 16px on
                                           mobile, blurry images, more than 3 fonts. Confirm each before reporting.
Ad pixels and form submissions are blocked. Nothing is submitted.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

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

DESIGN_JS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.05; };
  const top = el => Math.round(el.getBoundingClientRect().top + scrollY);
  const txt = el => (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
  const vh = innerHeight, pageH = document.body.scrollHeight;
  const isBtnLink = a => /btn|button|cta/i.test((a.className || '') + '') || getComputedStyle(a).display.includes('block') && parseFloat(getComputedStyle(a).paddingTop) >= 8;
  const ctaEls = [...document.querySelectorAll('button, [role=button], input[type=submit], a[href]')]
    .filter(e => vis(e) && (e.tagName !== 'A' || isBtnLink(e)) && txt(e || '').length + (e.value || '').length > 1);
  const formFrames = [...document.querySelectorAll('iframe')].filter(f => vis(f) && /widget\/(form|survey)|leadconnector|msgsndr|form/i.test(f.src || ''));
  const cands = [...ctaEls.map(e => ({y: top(e), text: (txt(e) || e.value || '').slice(0, 60)})),
                 ...formFrames.map(f => ({y: top(f), text: '(form in a frame)'}))].filter(c => c.y >= 0).sort((a, b) => a.y - b.y);
  const firstAction = cands[0] || null;

  // per-word line positions: is the last line a single word? how many lines?
  const lines = el => { const words = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n; (n = w.nextNode());) { const re = /\S+/g; let m;
      while ((m = re.exec(n.textContent))) { const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
        const rc = r.getClientRects()[0]; if (rc && rc.width > 0) words.push({w: m[0], t: Math.round(rc.top)}); } }
    const tops = []; for (const x of words) if (!tops.some(t => Math.abs(t - x.t) < 4)) tops.push(x.t);
    const last = words.length ? words[words.length - 1] : null;
    const onLast = last ? words.filter(x => Math.abs(x.t - last.t) < 4) : [];
    return {n: tops.length, words: words.length, lastLine: onLast.map(x => x.w).join(' '), lastTop: last ? Math.round(last.t + scrollY) : 0}; };

  const heads = [...document.querySelectorAll('h1,h2,h3')].filter(vis).map(h => {
    const cs = getComputedStyle(h); const L = lines(h);
    return {tag: h.tagName.toLowerCase(), y: top(h), size: cs.fontSize, lines: L.n, text: txt(h).slice(0, 100)}; });
  // main headline = the biggest-font heading on the first screen (GHL often uses h2/p for the headline)
  const firstScreen = [...document.querySelectorAll('h1,h2,h3,p,div')].filter(e => vis(e) && top(e) < vh &&
    [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 8));
  let headline = null;
  for (const e of firstScreen) { const s = parseFloat(getComputedStyle(e).fontSize);
    if (!headline || s > headline.px) headline = {px: s, el: e}; }
  const hl = headline ? {text: txt(headline.el).slice(0, 120), size: Math.round(headline.px) + 'px', y: top(headline.el), lines: lines(headline.el).n} : null;

  // lone word on the last line (headings, paragraphs, list items, buttons)
  const lone = [], wrapBtns = [], small = [], seenLone = new Set();
  const blocks = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,button,a,label,span,div')].filter(e => vis(e) &&
    [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1));
  const legal = /privacy|terms|disclaimer|©|copyright|rights reserved|not (a )?guarantee|results (may|will) vary|facebook|meta platforms/i;
  for (const e of blocks) {
    const t = txt(e); if (t.length < 3) continue;
    const L = lines(e);
    const btn = e.matches('button,[role=button]') || (e.tagName === 'A' && isBtnLink(e));
    const key = L.lastLine + '@' + L.lastTop;
    if (L.n >= 2 && L.words >= 2 && !L.lastLine.includes(' ') && /[A-Za-z0-9]{2,}/.test(L.lastLine) && !seenLone.has(key)) {
      seenLone.add(key); lone.push({text: t.slice(0, 120), last_word: L.lastLine, tag: e.tagName.toLowerCase(), y: top(e)}); }
    if (btn && L.n >= 2 && t.length < 60) wrapBtns.push({text: t, lines: L.n, y: top(e)});
    const fs = parseFloat(getComputedStyle(e).fontSize);
    if (fs < 16 && t.length > 60 && !legal.test(t) && top(e) < pageH - 900 && !e.closest('footer,form,label'))
      small.push({text: t.slice(0, 90), size: fs + 'px', y: top(e)});
  }
  const fonts = {};
  for (const e of blocks) { const f = getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g, '').trim(); fonts[f] = (fonts[f] || 0) + 1; }
  const dedupe = arr => { const s = new Set(); return arr.filter(x => { const k = x.text.slice(0, 50); if (s.has(k)) return false; s.add(k); return true; }); };
  return {first_screen_h: vh, first_action: firstAction, headline: hl, headings: heads.slice(0, 40),
          lone_words: dedupe(lone).slice(0, 25), wrapping_buttons: dedupe(wrapBtns).slice(0, 10),
          small_text: dedupe(small).slice(0, 10), fonts};
}
"""


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


def design_flags(dev, f):
    """Turn the measured design facts into flags (thresholds match funnel-audit's scan_page.py)."""
    dz, out = f.get("design") or {}, []
    vh, fa = dz.get("first_screen_h") or 0, dz.get("first_action")
    if vh and fa:
        limit = vh if dev == "desktop" else int(vh * 1.5)
        if fa["y"] > limit:
            out.append(("High" if dev == "desktop" else "Medium", "cta_below_first_screen",
                        f"first button/form at {fa['y']}px ({fa['text']}), first screen {vh}px"))
    hl = dz.get("headline")
    if hl and hl["lines"] > (3 if dev == "desktop" else 4):
        out.append(("Medium", "headline_too_long", f"{hl['lines']} lines at {hl['size']}: {hl['text'][:60]}"))
    for x in dz.get("lone_words", [])[:12]:
        out.append(("Polish", "lone_word_last_line", f"'{x['last_word']}' alone at y={x['y']}: {x['text'][:60]}"))
    if dev == "mobile":
        for x in dz.get("wrapping_buttons", [])[:5]:
            out.append(("Polish", "button_text_wraps", f"{x['lines']} lines: {x['text'][:50]}"))
        for x in dz.get("small_text", [])[:5]:
            out.append(("Medium", "small_body_text", f"{x['size']} at y={x['y']}: {x['text'][:50]}"))
    for i in f.get("imgs", []):
        if i.get("natural_w") and i["w"] >= 120 and ".svg" not in i["src"].lower() and i["natural_w"] < 0.9 * i["w"]:
            out.append(("Medium", "blurry_image", f"{i['src'][-50:]} file {i['natural_w']}px shown {i['w']}px"))
    fams = [k for k, n in (dz.get("fonts") or {}).items() if n >= 3]
    if len(fams) > 3:
        out.append(("Polish", "many_fonts", ", ".join(fams)))
    return [{"device": dev, "tier": t, "type": k, "detail": d} for t, k, d in out]


def slug(url):
    p = re.sub(r"^https?://", "", url).split("?")[0].strip("/")
    p = p.split("/", 1)[1] if "/" in p else p
    return re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")[:50] or "home"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="+", metavar="URL")
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=4, help="pages captured at the same time (default 4)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if len(a.urls) > 1:
        # one process per page, each in its own folder
        t0, running, queue = time.time(), [], list(a.urls)
        while queue or running:
            while queue and len(running) < a.jobs:
                u = queue.pop(0)
                d = os.path.join(a.out, slug(u))
                os.makedirs(d, exist_ok=True)
                log = open(os.path.join(d, "capture.log"), "w+", encoding="utf-8", errors="replace")
                env = dict(os.environ, PYTHONIOENCODING="utf-8")
                running.append((subprocess.Popen([sys.executable, os.path.abspath(__file__), u, "--out", d],
                                                 stdout=log, stderr=subprocess.STDOUT, env=env), log, d))
            for pr, log, d in running[:]:
                if pr.poll() is not None:
                    log.seek(0)
                    print(f"\n== {d}\n" + log.read(), end="", flush=True)
                    log.close()
                    running.remove((pr, log, d))
            time.sleep(0.3)
        print(f"\nDone: {len(a.urls)} pages in {time.time() - t0:.0f}s")
        return
    a.url = a.urls[0]
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
            pg.evaluate("window.scrollTo(0, 0)")
            try:
                facts[dev]["design"] = pg.evaluate(DESIGN_JS)
            except Exception as e:  # never let the checks break the capture
                facts[dev]["design"] = {"error": str(e)[:200]}
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
    facts["flags"] = design_flags("desktop", facts["desktop"]) + design_flags("mobile", facts["mobile"])
    with open(f"{a.out}/facts.json", "w", encoding="utf-8") as fh:
        json.dump(facts, fh, indent=1, ensure_ascii=False)
    for dev in DEVICES:
        f = facts[dev]
        print(f"{dev}: page {f['height']}px tall, first screen {f['viewport_h']}px, form button at "
              f"{f['form_submit_y']} (None = inside an iframe or no form), sideways scroll: {f['sideways_scroll']}, "
              f"{f['slices']} slices")
    print("title:", facts["desktop"]["title"])
    print(f"{len(facts['flags'])} design flags (confirm each on the screenshot before reporting):")
    for f in facts["flags"]:
        print(f"  FLAG [{f['tier']}] {f['device']} {f['type']}: {f['detail']}")


if __name__ == "__main__":
    main()
