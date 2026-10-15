"""Tile several PNGs into one contact sheet for visual review: python contact_sheet.py out.png cols width a.png b.png ..."""
import sys
from PIL import Image, ImageDraw

out, cols, width, files = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:]
ims = []
for f in files:
    im = Image.open(f).convert("RGB")
    im = im.resize((width, int(im.height * width / im.width)))
    ImageDraw.Draw(im).rectangle([0, 0, im.width - 1, im.height - 1], outline=(255, 0, 0))
    ims.append(im)
rows = [ims[i:i + cols] for i in range(0, len(ims), cols)]
H = sum(max(i.height for i in r) for r in rows)
sheet = Image.new("RGB", (cols * width, H), "white")
y = 0
for r in rows:
    for c, im in enumerate(r):
        sheet.paste(im, (c * width, y))
    y += max(i.height for i in r)
sheet.save(out)
print(out, sheet.size)
