"""Source-specific annotation parsers -> one record per (image, annotation), in the source's own terms plus a mapped class.

A record keeps the original label and IDs unchanged; ``target_class`` is None (with ``mapping_note``) whenever the label is not
the same diagnosis as one of the four target classes. Parsers never open images and never invent labels for unannotated teeth.
"""
from __future__ import annotations

import json
from pathlib import Path

from dsutil import canonical_finding


def _fdi(q_name, t_name):
    try:
        q, t = int(q_name), int(t_name)
    except (TypeError, ValueError):
        return None
    return q * 10 + t if 1 <= q <= 4 and 1 <= t <= 8 else None


def parse_dentex_coco(json_path, image_dir_rel: str, source_id: str):
    """DENTEX COCO with categories_1 (quadrant), categories_2 (tooth), categories_3 (diagnosis).

    Returns (images, records). images: {file_name: {"width", "height", "coco_id", "n_annotations"}}.
    ``image_dir_rel`` is the image folder relative to DATA_ROOT (e.g. 'training_data/quadrant-enumeration-disease/xrays')."""
    raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
    cats = {k: {c["id"]: c["name"] for c in v} for k, v in raw.items() if k.startswith("categories")}
    if "categories_3" not in cats:
        raise ValueError(f"{json_path}: no categories_3 (diagnosis) table - not a disease-level file")
    imgs = {im["id"]: im for im in raw["images"]}
    images = {im["file_name"]: {"width": im.get("width"), "height": im.get("height"), "coco_id": im["id"], "n_annotations": 0}
              for im in raw["images"]}
    records = []
    for a in raw["annotations"]:
        im = imgs.get(a.get("image_id"))
        if im is None:
            continue
        images[im["file_name"]]["n_annotations"] += 1
        label = cats["categories_3"].get(a.get("category_id_3"))
        target = canonical_finding(label, "dentex_en")
        bbox = a.get("bbox")
        ok_box = isinstance(bbox, list) and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0
        records.append({
            "source_dataset": source_id, "original_image_id": im["id"], "original_file_name": im["file_name"],
            "image_path": f"{image_dir_rel}/{im['file_name']}", "annotation_id": a.get("id"),
            "fdi_tooth": _fdi(cats.get("categories_1", {}).get(a.get("category_id_1")), cats.get("categories_2", {}).get(a.get("category_id_2"))),
            "original_label": label, "target_class": target if ok_box else None,
            "annotation_type": "bbox (COCO xywh; polygon also present)" if a.get("segmentation") else "bbox (COCO xywh)",
            "bbox_xywh": [float(v) for v in bbox] if ok_box else None,
            "image_width": im.get("width"), "image_height": im.get("height"),
            "mapping_note": ("exact DENTEX category name" if target else f"label {label!r} is not a target class") if ok_box
            else "missing or degenerate bbox - dropped",
        })
    return images, records


def parse_labelme_tr(label_dir, image_dir_rel: str, source_id: str):
    """DENTEX test_data.zip labels (Labelme; '<code>-<turkish name>-<FDI>'). Inventory only: every record has target_class None,
    because this taxonomy is not verified to be equivalent to the four DENTEX diagnoses (see dsutil.canonical_finding)."""
    images, records = {}, []
    for f in sorted(Path(label_dir).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        name = d.get("imagePath") or f.stem + ".png"
        images[name] = {"width": d.get("imageWidth"), "height": d.get("imageHeight"), "coco_id": None, "n_annotations": len(d["shapes"])}
        for k, s in enumerate(d["shapes"]):
            lab, _, tooth = s["label"].rpartition("-")
            xs, ys = [p[0] for p in s["points"]], [p[1] for p in s["points"]]
            records.append({
                "source_dataset": source_id, "original_image_id": Path(name).stem, "original_file_name": name,
                "image_path": f"{image_dir_rel}/{name}", "annotation_id": f"{f.stem}#{k}",
                "fdi_tooth": int(tooth) if tooth.isdigit() else None, "original_label": lab,
                "target_class": canonical_finding(lab, "dentex_tr_labelme"), "annotation_type": "polygon (Labelme)",
                "bbox_xywh": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)],
                "image_width": d.get("imageWidth"), "image_height": d.get("imageHeight"),
                "mapping_note": "Turkish treatment-oriented taxonomy; not mapped (no verified equivalence)",
            })
    return images, records
