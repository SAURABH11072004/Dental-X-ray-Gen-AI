"""Shared helpers for the dataset-integration pipeline (scripts/dataset/*) and the Kaggle notebook.

Standard library + numpy + Pillow only (no ``dentexmodel`` import), so the same code runs locally and on Kaggle.

Label policy (enforced by ``canonical_finding``): only names that are *the same DENTEX diagnosis* map to a target class.
Anything else (other taxonomies, generic "lesion"/"infection", healthy-tooth labels, treatment labels) returns ``None`` and is
kept in the provenance record with the reason. Unlabelled teeth are never turned into a class.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]       # index order used by the deployed classifier
CROP_PAD = 0.10                                                            # == dentexmodel.training.trainers.CROP_PAD
CROP_SIZE = 224

# Exact DENTEX English category names (training and official validation JSON: categories_3) -> target class.
_DENTEX_NAMES = {"caries": "Caries", "deep caries": "Deep Caries", "deepcaries": "Deep Caries", "impacted": "Impacted",
                 "periapical lesion": "Periapical Lesion", "periapicallesion": "Periapical Lesion"}


def canonical_finding(name: str | None, taxonomy: str) -> str | None:
    """Target class for a label *of a known taxonomy*, else None. ``taxonomy`` must be one this function knows; an unknown
    taxonomy raises, so a new source cannot silently reuse the DENTEX mapping."""
    if taxonomy == "dentex_en":
        return _DENTEX_NAMES.get(" ".join(str(name or "").lower().replace("_", " ").split()))
    if taxonomy == "dentex_tr_labelme":
        # The Turkish label scheme in DENTEX test_data.zip is NOT mapped: on the one radiograph also present in the English-labelled
        # training set (test_181 == train_332) the two label sets disagree (see reports/additional_dataset_candidates.md).
        return None
    raise ValueError(f"unknown taxonomy {taxonomy!r}: add an explicit, documented mapping first")


def sha256_file(path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def dhash(path, size=8) -> int:
    """64-bit difference hash of a 9x8 grayscale thumbnail (same definition as scripts/check_leakage.py)."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("L").resize((size + 1, size), Image.BILINEAR)
    a = np.asarray(im, dtype=np.int16)
    return int("".join("1" if v else "0" for v in (a[:, 1:] > a[:, :-1]).flatten()), 2)


def thumb(path):
    """Standardised 256x128 grayscale thumbnail for the pixel-correlation confirmation stage."""
    from PIL import Image
    with Image.open(path) as im:
        a = np.asarray(im.convert("L").resize((256, 128), Image.BILINEAR), dtype=np.float32)
    return (a - a.mean()) / (a.std() + 1e-6)


def near_duplicate_pairs(items, max_hamming=4, min_corr=0.97, thumb_fn=thumb):
    """items: list of (key, sha256, dhash, path). Two-stage rule used by the project's leakage check: candidate pairs with
    Hamming distance <= ``max_hamming`` and different SHA-256, confirmed when the thumbnail Pearson correlation >= ``min_corr``.
    Returns (confirmed [(key_a, key_b, hamming, corr)], n_candidates, max_candidate_corr)."""
    if len(items) < 2:
        return [], 0, None
    arr = np.array([it[2] for it in items], dtype=np.uint64)
    cand = []
    for i in range(len(items) - 1):
        x = arr[i] ^ arr[i + 1:]
        c = np.array([bin(int(v)).count("1") for v in x])
        for j in np.where(c <= max_hamming)[0]:
            a, b = items[i], items[i + 1 + j]
            if a[1] != b[1]:
                cand.append((a, b, int(c[j])))
    cache, out, cors = {}, [], []
    for a, b, d in cand:
        for it in (a, b):
            if it[0] not in cache:
                cache[it[0]] = thumb_fn(it[3])
        r = float((cache[a[0]] * cache[b[0]]).mean())
        cors.append(r)
        if r >= min_corr:
            out.append((a[0], b[0], d, round(r, 4)))
    return out, len(cand), (max(cors) if cors else None)


def crop_box_xyxy(bbox_xywh, width, height, pad=CROP_PAD):
    """Padded crop rectangle exactly as ``trainers.crop_region`` computes it (before resizing), clipped to the image."""
    x, y, w, h = (float(v) for v in bbox_xywh)
    x1, y1, x2, y2 = x, y, x + w, y + h
    return [max(0.0, x1 - pad * w), max(0.0, y1 - pad * h), min(float(width), x2 + pad * w), min(float(height), y2 + pad * h)]


def crop_region(img_u8, box_xyxy, size=CROP_SIZE, pad=CROP_PAD):
    """Copy of ``dentexmodel.training.trainers.crop_region`` (kept identical; tests/test_dataset_integration.py checks this)."""
    from PIL import Image
    H, W = img_u8.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in box_xyxy)
    w, h = x2 - x1, y2 - y1
    x1, y1, x2, y2 = max(0, x1 - pad * w), max(0, y1 - pad * h), min(W, x2 + pad * w), min(H, y2 + pad * h)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return np.asarray(Image.fromarray(img_u8[int(y1):int(y2), int(x1):int(x2)]).resize((size, size), Image.BILINEAR))


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0].keys()) if rows else [])
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def file_sha256_short(path, n=16):
    return sha256_file(path)[:n] if Path(path).is_file() else None
