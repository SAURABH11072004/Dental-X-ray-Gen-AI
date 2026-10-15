#!/usr/bin/env python
"""Task-specific audit of the annotations that the classification and segmentation trainers actually use.

Read-only: nothing in Data/ is modified. Writes docs/audit_evidence/ml_improvement/data_audit.json and a flagged-sample manifest
(flagged_samples.csv) so suspicious samples can be inspected instead of silently deleted.

    .venv\\Scripts\\python.exe scripts\\ml_data_audit.py
"""
import _bootstrap  # noqa: F401
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from dentexmodel.config import get_settings
from dentexmodel.data.coco import annotation_finding
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.splits import load_split_file
from dentexmodel.training import trainers as T

OUT = Path("docs/audit_evidence/ml_improvement")
SPLITS = ("train", "val", "calibration", "test")


def poly_ok(seg, W, H):
    """(valid_polygons, issues) for a COCO polygon list."""
    issues, n_ok = [], 0
    if not isinstance(seg, list) or not seg:
        return 0, ["no_polygon"]
    for p in seg:
        if not isinstance(p, list) or len(p) < 6 or len(p) % 2:
            issues.append("malformed_polygon")
            continue
        a = np.asarray(p, float).reshape(-1, 2)
        if (a[:, 0] < -1).any() or (a[:, 1] < -1).any() or (a[:, 0] > W + 1).any() or (a[:, 1] > H + 1).any():
            issues.append("polygon_out_of_bounds")
        n_ok += 1
    return n_ok, issues


def poly_mask_stats(seg, W, H):
    """Rasterise at 1/4 scale: (area_px_full_res, bbox_xyxy) of the union of polygons, clipped to the image."""
    s = 4
    m = Image.new("L", (max(1, W // s), max(1, H // s)), 0)
    d = ImageDraw.Draw(m)
    for p in seg:
        if isinstance(p, list) and len(p) >= 6 and len(p) % 2 == 0:
            d.polygon([(p[i] / s, p[i + 1] / s) for i in range(0, len(p), 2)], fill=1)
    a = np.asarray(m)
    if not a.any():
        return 0, None
    ys, xs = np.where(a)
    return int(a.sum()) * s * s, (xs.min() * s, ys.min() * s, (xs.max() + 1) * s, (ys.max() + 1) * s)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def main():
    s = get_settings()
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows_all = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data]
    flagged = []
    report = {"tasks": {}}

    # ---- split isolation by pixel content (a radiograph whose pixels appear in two splits is a leak)
    by_hash = defaultdict(set)
    for r in rows_all:
        if r.content_hash:
            by_hash[r.content_hash].add(assign.get(r.image_id, "unassigned"))
    leaks = {h: sorted(v) for h, v in by_hash.items() if len(v - {"unassigned"}) > 1}
    report["split_isolation"] = {"distinct_radiographs": len(by_hash), "hashes_in_more_than_one_split": len(leaks),
                                 "note": "identical pixels in different splits across ALL annotated rows (any source)"}

    for task, level in (("classification", "quadrant_enumeration_disease"), ("segmentation", "quadrant_enumeration")):
        rows = [r for r in rows_all if r.annotation_level == level]
        items = T._annotations_for(s, svc, rows)
        per = {sp: {"images": 0, "unique_radiographs": set(), "annotations": 0, "class_counts": Counter(), "masks": 0} for sp in SPLITS}
        issue_counts = Counter()
        dup_boxes = 0
        conflicts = 0
        crop_fail = Counter()
        areas, ratios = [], []
        n_inst_img = []
        for row, anns, cats in items:
            sp = assign.get(row.image_id, "unassigned")
            if sp not in per:
                continue
            P = per[sp]
            P["images"] += 1
            if row.content_hash:
                P["unique_radiographs"].add(row.content_hash)
            try:
                with Image.open(s.data_root / row.file_path) as im:
                    W, H = im.size
                    mode = im.mode
            except OSError as exc:
                issue_counts["unreadable_image"] += 1
                flagged.append((task, row.image_id, "", "unreadable_image", str(exc)[:80]))
                continue
            if row.width and row.height and (row.width, row.height) != (W, H):
                issue_counts["coco_size_mismatch"] += 1
                flagged.append((task, row.image_id, "", "coco_size_mismatch", f"{row.width}x{row.height} vs {W}x{H}"))
            if mode not in ("RGB", "L"):
                issue_counts[f"mode_{mode}"] += 1
            seen = {}
            n_inst_img.append(len(anns))
            for a in anns:
                P["annotations"] += 1
                bb = a.get("bbox")
                if not bb or len(bb) != 4:
                    issue_counts["missing_bbox"] += 1
                    flagged.append((task, row.image_id, a.get("id"), "missing_bbox", ""))
                    continue
                x, y, w, h = bb
                box = (x, y, x + w, y + h)
                if w <= 0 or h <= 0:
                    issue_counts["degenerate_bbox"] += 1
                    flagged.append((task, row.image_id, a.get("id"), "degenerate_bbox", str(bb)))
                    continue
                if x < -1 or y < -1 or x + w > W + 1 or y + h > H + 1:
                    issue_counts["bbox_out_of_bounds"] += 1
                    flagged.append((task, row.image_id, a.get("id"), "bbox_out_of_bounds", str(bb)))
                if w < 8 or h < 8:
                    issue_counts["tiny_bbox_lt8px"] += 1
                    flagged.append((task, row.image_id, a.get("id"), "tiny_bbox_lt8px", str(bb)))
                ratios.append(w / h)
                key = tuple(round(v) for v in box)
                lab = annotation_finding(a, cats) if "category_id_3" in a else None
                if key in seen:
                    dup_boxes += 1
                    if lab != seen[key]:
                        conflicts += 1
                        flagged.append((task, row.image_id, a.get("id"), "conflicting_label_same_box", f"{seen[key]} vs {lab}"))
                    else:
                        flagged.append((task, row.image_id, a.get("id"), "duplicate_annotation", str(key)))
                seen[key] = lab
                n_ok, iss = poly_ok(a.get("segmentation"), W, H)
                for i in set(iss):
                    issue_counts[i] += 1
                    flagged.append((task, row.image_id, a.get("id"), i, ""))
                if n_ok:
                    P["masks"] += 1
                    if task == "segmentation":
                        area, mb = poly_mask_stats(a["segmentation"], W, H)
                        areas.append(area)
                        if area == 0:
                            issue_counts["empty_mask"] += 1
                            flagged.append((task, row.image_id, a.get("id"), "empty_mask", ""))
                        elif mb is not None and iou(mb, box) < 0.7:
                            issue_counts["mask_bbox_mismatch_iou_lt0.7"] += 1
                            flagged.append((task, row.image_id, a.get("id"), "mask_bbox_mismatch", f"iou={iou(mb, box):.2f}"))
                if task == "classification":
                    if "category_id_3" not in a or lab is None:
                        issue_counts["missing_finding_label"] += 1
                        flagged.append((task, row.image_id, a.get("id"), "missing_finding_label", ""))
                        continue
                    P["class_counts"][lab] += 1
            if task == "classification":      # crop-generation failures, evaluated on the real pixels (once per image)
                img = np.asarray(Image.open(s.data_root / row.file_path).convert("RGB"))
                for a in anns:
                    if "category_id_3" in a and a.get("bbox"):
                        x, y, w, h = a["bbox"]
                        if T.crop_region(img, (x, y, x + w, y + h), 224) is None:
                            crop_fail[sp] += 1
                            flagged.append((task, row.image_id, a.get("id"), "crop_generation_failed", str(a["bbox"])))
        entry = {"level": level, "splits": {}}
        for sp in SPLITS:
            P = per[sp]
            entry["splits"][sp] = {"images": P["images"], "unique_radiographs_by_pixels": len(P["unique_radiographs"]),
                                   "annotations": P["annotations"], "polygon_masks": P["masks"],
                                   "class_counts": dict(P["class_counts"])}
        entry["issue_counts"] = dict(issue_counts)
        entry["duplicate_boxes_same_image"] = dup_boxes
        entry["conflicting_labels_same_box"] = conflicts
        entry["crop_generation_failures"] = dict(crop_fail)
        if ratios:
            entry["bbox_aspect_w_over_h"] = {"p5": round(float(np.percentile(ratios, 5)), 3), "median": round(float(np.median(ratios)), 3),
                                             "p95": round(float(np.percentile(ratios, 95)), 3)}
        if areas:
            a = np.asarray(areas, float)
            entry["mask_area_px"] = {"min": int(a.min()), "p5": int(np.percentile(a, 5)), "median": int(np.median(a)),
                                     "p95": int(np.percentile(a, 95)), "max": int(a.max())}
            entry["sqrt_area_px_percentiles"] = {str(q): round(float(np.sqrt(np.percentile(a, q))), 1) for q in (1, 5, 25, 50, 75, 95, 99)}
        if n_inst_img:
            entry["instances_per_image"] = {"min": int(min(n_inst_img)), "median": float(np.median(n_inst_img)), "max": int(max(n_inst_img))}
        report["tasks"][task] = entry

    # pixel-identical train/non-train crops for classification: do train radiographs' hashes appear in val/test/calibration?
    cls_hash = defaultdict(set)
    for r in rows_all:
        if r.annotation_level == "quadrant_enumeration_disease" and r.content_hash:
            cls_hash[r.content_hash].add(assign.get(r.image_id))
    report["classification_cross_split_pixel_duplicates"] = sum(1 for v in cls_hash.values() if len(v - {None, "unassigned"}) > 1)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data_audit.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    with open(OUT / "flagged_samples.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["task", "image_id", "annotation_id", "issue", "detail"])
        w.writerows(flagged)
    print(json.dumps(report, indent=1))
    print("flagged:", len(flagged))


if __name__ == "__main__":
    sys.exit(main())
