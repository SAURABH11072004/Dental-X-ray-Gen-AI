"""Render every page of a PDF to PNG and build contact sheets (N pages per sheet) for visual inspection.
python render_pdf.py <pdf> <out_dir> [per_sheet=6] [dpi=70]"""
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
per = int(sys.argv[3]) if len(sys.argv) > 3 else 6
dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 70
out.mkdir(parents=True, exist_ok=True)
for f in out.glob("*.png"):
    f.unlink()
doc = pymupdf.open(pdf)
pages = []
for i, p in enumerate(doc):
    pix = p.get_pixmap(dpi=dpi)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    ImageDraw.Draw(im).rectangle([0, 0, im.width - 1, im.height - 1], outline=(255, 0, 0))
    ImageDraw.Draw(im).text((6, 4), f"pdf p{i + 1}", fill=(255, 0, 0))
    pages.append(im)
cols = 3 if per >= 6 else 2
for s in range(0, len(pages), per):
    chunk = pages[s:s + per]
    w, h = chunk[0].size
    rows = (len(chunk) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    for k, im in enumerate(chunk):
        sheet.paste(im, ((k % cols) * w, (k // cols) * h))
    sheet.save(out / f"sheet_{s // per + 1:02d}.png")
print(len(pages), "pages ->", out)
