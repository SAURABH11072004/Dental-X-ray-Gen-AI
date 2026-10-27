"""Hanoi periapical dataset (Mendeley kx52tk2ddj v3): verified image <-> annotation mapping, used ONLY as review hints.

Verified 2026-10-16 on the downloaded archives (SHA-256 = Mendeley): every original ``Original JPG Images/NNNN1.jpg`` has
``Image Annots/NNNN1.xml``; for all 3,924 pairs the XML <size> equals the real image size and all 6,741 boxes lie inside the image
(PAI 3: 4,277, PAI 4: 1,755, PAI 5: 709). Two XMLs (16091, 16131) have no image in the archive. The other XMLs belong to the
augmented copies, which are not used.

The boxes outline LESIONS (PAI >= 3 apical periodontitis), not teeth, and equivalence with DENTEX "Periapical Lesion" is not
assumed: a clinician confirms both the finding and the tooth during review.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
ANN_DIR = DATA / "raw/external/hanoi_periapical/annots/Image Annots"


def lesion_boxes(pool_row) -> list:
    """[(xyxy, 'PAI n')] for a pool row of source 'hanoi_periapical'; [] if no annotation file exists."""
    stem = Path(pool_row["image_path"]).stem
    f = ANN_DIR / f"{stem}.xml"
    if not f.is_file():
        return []
    out = []
    for o in ET.parse(f).getroot().findall("object"):
        b = o.find("bndbox")
        out.append(([float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")], f"PAI {o.findtext('name')}"))
    return out
