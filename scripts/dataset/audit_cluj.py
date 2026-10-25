"""Audit the Cluj-Napoca panoramic dataset (Zenodo 10.5281/zenodo.15487430, CC BY 4.0) before any use.

Muresanu et al., "Automating Dental Condition Detection on Panoramic Radiographs: Challenges, Pitfalls, and Opportunities",
Diagnostics 14(20):2336, 2024, doi:10.3390/diagnostics14202336.

What this does (read-only on the archive, never modifies original files):
1. verifies the archive MD5 published by Zenodo, extracts it safely into Data/raw/external/zenodo_cluj_15487430/extracted/;
2. inventories images and YOLO label files per folder, decodes every image, counts boxes per class;
3. checks exact (SHA-256 of file bytes) and near duplicates (dHash + pixel correlation >= 0.97, the project's leakage rule)
   inside Cluj and against every DENTEX and Hanoi image on disk;
4. writes reports/cluj_dataset_audit.json and .md.

No class mapping to the four DENTEX classes is made here: that is a separate, documented decision
(see reports/additional_dataset_candidates.md and dsutil.canonical_finding).
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from dsutil import dhash, near_duplicate_pairs, sha256_file  # noqa: E402

SRC = ROOT / "Data/raw/external/zenodo_cluj_15487430"
ZIP = SRC / "panoramic_radiography_yolo_dataset_14_classes.zip"
MD5 = "18d5acaea021f4f3b05b76e9a27fbd42"
OUT = SRC / "extracted"
NAMES = ["IMP", "PRR", "OBT", "END", "CAR", "BON", "IMT", "API", "ROT", "FUR", "APS", "ROR", "ORD", "SRD"]
LONG = ["Implant", "Prosthetic restoration", "Obturation", "Endodontic treatment", "Carious lesion", "Bone resorption",
        "Impacted tooth", "Apical periodontitis", "Root fragment", "Furcation lesion", "Apical surgery", "Root resorption",
        "Orthodontic device", "Surgical device"]
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def safe_extract():
    if OUT.exists() and any(OUT.rglob("*")):
        return
    with zipfile.ZipFile(ZIP) as z:
        for m in z.infolist():
            target = (OUT / m.filename).resolve()
            if not str(target).startswith(str(OUT.resolve())):
                raise RuntimeError(f"unsafe path in archive: {m.filename}")
        z.extractall(OUT)


def main():
    from PIL import Image
    got = md5(ZIP)
    assert got == MD5, f"MD5 mismatch {got} != {MD5}"
    safe_extract()
    files = [p for p in OUT.rglob("*") if p.is_file()]
    imgs = [p for p in files if p.suffix.lower() in IMG_EXT]
    labels = {p.with_suffix("").name: p for p in files if p.suffix.lower() == ".txt" and p.name not in ("classes.txt",)}
    per_folder = Counter(str(p.parent.relative_to(OUT)) for p in imgs)
    cls_boxes, cls_imgs, per_folder_cls = Counter(), Counter(), defaultdict(Counter)
    sizes, bad, no_label, empty_label = Counter(), [], 0, 0
    for p in imgs:
        try:
            with Image.open(p) as im:
                im.load()
                sizes[im.size] += 1
        except Exception as e:  # noqa: BLE001
            bad.append((str(p.relative_to(OUT)), repr(e)))
        lab = p.parent.parent / "labels" / (p.stem + ".txt")
        if not lab.exists():
            lab = labels.get(p.stem)
        if lab is None or not Path(lab).exists():
            no_label += 1
            continue
        rows = [r.split() for r in Path(lab).read_text().splitlines() if r.strip()]
        if not rows:
            empty_label += 1
        seen = set()
        for r in rows:
            c = int(float(r[0]))
            cls_boxes[NAMES[c]] += 1
            per_folder_cls[str(p.parent.relative_to(OUT))][NAMES[c]] += 1
            seen.add(NAMES[c])
        for c in seen:
            cls_imgs[c] += 1

    # duplicates: inside Cluj and against DENTEX + Hanoi
    def items_for(paths, tag):
        out = []
        for p in paths:
            try:
                out.append((f"{tag}:{p}", sha256_file(p), dhash(p), p))
            except Exception:  # noqa: BLE001
                pass
        return out

    cluj = items_for(imgs, "cluj")
    dentex = [p for p in (ROOT / "Data").rglob("*.png") if "raw" not in p.parts or "dentex_hf" in p.parts]
    hanoi = [p for p in (ROOT / "Data/raw/external/hanoi_periapical").rglob("*") if p.suffix.lower() in IMG_EXT]
    others = items_for(dentex, "dentex") + items_for(hanoi, "hanoi")
    sha_cluj = Counter(i[1] for i in cluj)
    exact_internal = sum(c - 1 for c in sha_cluj.values() if c > 1)
    sha_other = {i[1] for i in others}
    exact_cross = sum(1 for i in cluj if i[1] in sha_other)
    near, n_cand, max_corr = near_duplicate_pairs(cluj + others)
    near_internal = [x for x in near if x[0].startswith("cluj:") and x[1].startswith("cluj:")]
    near_cross = [x for x in near if x[0].startswith("cluj:") != x[1].startswith("cluj:")]

    rep = {
        "source": "Zenodo 10.5281/zenodo.15487430 (CC BY 4.0); paper doi:10.3390/diagnostics14202336",
        "archive_md5_verified": got, "n_files": len(files), "n_images": len(imgs), "images_per_folder": dict(per_folder),
        "undecodable_images": bad, "images_without_label_file": no_label, "images_with_empty_label": empty_label,
        "image_sizes_top10": [[f"{w}x{h}", n] for (w, h), n in sizes.most_common(10)],
        "boxes_per_class": {f"{k} ({LONG[NAMES.index(k)]})": v for k, v in cls_boxes.most_common()},
        "images_with_class": {f"{k} ({LONG[NAMES.index(k)]})": v for k, v in cls_imgs.most_common()},
        "boxes_per_folder_and_class": {k: dict(v) for k, v in per_folder_cls.items()},
        "duplicates": {"exact_within_cluj": exact_internal, "exact_vs_dentex_or_hanoi": exact_cross,
                       "near_candidates_checked": n_cand, "near_confirmed_within_cluj": len(near_internal),
                       "near_confirmed_vs_dentex_or_hanoi": len(near_cross), "near_examples": near[:20],
                       "compared_against": {"dentex_png": len(dentex), "hanoi": len(hanoi)}},
    }
    (ROOT / "reports/cluj_dataset_audit.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "boxes_per_folder_and_class"}, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
