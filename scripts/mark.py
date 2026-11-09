"""Draw yellow numbered markers (+ optional yellow boxes) on the full screenshots and crop them into report images.

Usage:  python mark.py marks.json --cap CAPTURE_DIR --out SHOTS_DIR

marks.json:
{
  "desktop": {
    "markers": [ {"n": "1", "x": 330, "y": 300, "box": [250, 175, 1190, 425]}, ... ],
    "crops":   [ {"name": "d-hero", "y0": 0, "y1": 1700}, ... ]
  },
  "mobile": {
    "markers": [ {"n": "M1", "x": 40, "y": 560} ],
    "crops":   [ {"name": "m-hero", "y0": 0, "y1": 3500} ]
  }
}
Coordinates are pixels in desktop-full.png (1x, so = CSS px) and mobile-full.png (2x, so CSS px x 2).
When you read them off a slice image, add the slice offset (desktop sNN: NN*1800, mobile sNN: NN*2400) and undo any
display scaling the image viewer reports. "box" is [left, top, right, bottom]. Look at every output image after.
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

FONTS = ("C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def font(sz):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def draw(im, markers, r):
    d = ImageDraw.Draw(im)
    f = font(int(r * 1.05))
    for m in markers:  # boxes first so the number badges sit on top
        if m.get("box"):
            d.rounded_rectangle(m["box"], radius=8, outline=(255, 212, 0), width=max(3, r // 6))
    for m in markers:
        x, y, t = m["x"], m["y"], str(m["n"])
        w = max(2 * r, int(d.textlength(t, font=f)) + r)
        d.rounded_rectangle((x - w // 2, y - r, x + w // 2, y + r), radius=r, fill=(255, 212, 0),
                            outline=(0, 0, 0), width=3)
        d.text((x, y), t, fill=(0, 0, 0), font=f, anchor="mm")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--cap", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with open(a.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    for dev, r in (("desktop", 20), ("mobile", 30)):
        if dev not in spec:
            continue
        im = Image.open(os.path.join(a.cap, f"{dev}-full.png")).convert("RGB")
        draw(im, spec[dev].get("markers", []), r)
        for c in spec[dev].get("crops", []):
            p = os.path.join(a.out, c["name"] + ".jpg")
            im.crop((0, c["y0"], im.size[0], min(im.size[1], c["y1"]))).save(p, quality=82)
            print("wrote", p)


if __name__ == "__main__":
    main()
