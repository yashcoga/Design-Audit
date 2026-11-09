"""Print the feedback HTML to a Letter PDF and (optionally) make a small contact sheet of its pages to check.

Usage:  python to_pdf.py feedback.html "Out Name.pdf" [--sheet sheet.png]
"""
import argparse
import pathlib

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html")
    ap.add_argument("pdf")
    ap.add_argument("--sheet")
    a = ap.parse_args()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(pathlib.Path(a.html).resolve().as_uri())
        pg.wait_for_timeout(800)
        pg.pdf(path=a.pdf, format="Letter", print_background=True, prefer_css_page_size=True)
        b.close()
    print("pdf", a.pdf)
    if not a.sheet:
        return
    try:
        import pymupdf
        from PIL import Image
    except ImportError:
        print("pymupdf not installed; open the PDF to check it")
        return
    doc = pymupdf.open(a.pdf)
    ims = []
    for page in doc:
        pix = page.get_pixmap(dpi=40)
        ims.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    w, h = ims[0].size
    cols = 5
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), "white")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    sheet.save(a.sheet)
    print(f"sheet {a.sheet} ({len(ims)} pages)")


if __name__ == "__main__":
    main()
