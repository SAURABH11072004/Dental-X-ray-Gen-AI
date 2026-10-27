#!/usr/bin/env python
"""Class-imbalance audit of the CURRENT finding-classifier data (DENTEX quadrant-enumeration-disease + persisted splits).

    .venv\\Scripts\\python.exe scripts\\dataset\\audit_class_imbalance.py

Reads (never writes) data/processed/manifest.csv, data/splits/dentex_splits.json, the DENTEX disease COCO file, the dHash cache
and the classifier crop caches (runtime/ml_cache/crops_<split>_224.npz, label arrays only). Writes:
  reports/class_imbalance_before.csv, reports/dataset_inventory.json, reports/class_distribution_before.png

"Findings" = annotations with a target diagnosis and a usable box. "Crops" = findings whose padded crop passes the production
crop rule (``crop_region``: padded box at least 4 px each way); computed from geometry, cross-checked against the cached crops.
Unannotated teeth are not counted as anything; there is no "healthy" class.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import parse_dentex_coco  # noqa: E402
from dsutil import CLASSES, crop_box_xyxy, near_duplicate_pairs, read_csv, sha256_file, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DISEASE_DIR = "training_data/quadrant-enumeration-disease"
SPLITS = ["train", "val", "calibration", "test"]


def crop_ok(rec):
    if not rec["bbox_xywh"]:
        return False
    x1, y1, x2, y2 = crop_box_xyxy(rec["bbox_xywh"], rec["image_width"], rec["image_height"])
    return (x2 - x1) >= 4 and (y2 - y1) >= 4


def class_table(records, split_of):
    """rows split x class with findings, crops, radiographs; plus totals."""
    rows = []
    for sp in SPLITS + ["all"]:
        recs = [r for r in records if r["target_class"] and (sp == "all" or split_of(r) == sp)]
        n_img = len({r["image_path"] for r in recs})
        tot = sum(1 for r in recs if crop_ok(r))
        for c in CLASSES:
            rc = [r for r in recs if r["target_class"] == c]
            nc = sum(1 for r in rc if crop_ok(r))
            rows.append({"split": sp, "class": c, "findings": len(rc), "crops_after_crop_rule": nc,
                         "radiographs_with_class": len({r["image_path"] for r in rc}),
                         "share_of_split_crops": round(nc / tot, 4) if tot else 0.0,
                         "radiographs_in_split_with_any_finding": n_img})
    return rows


def plot(rows, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sp = [s for s in SPLITS if any(r["split"] == s for r in rows)] + [s for s in sorted({r["split"] for r in rows}) if s not in SPLITS + ["all"]]
    cols = ["#4C72B0", "#C44E52", "#55A868", "#8172B2"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    x = np.arange(len(sp))
    w = 0.2
    for k, c in enumerate(CLASSES):
        v = [next((r["crops_after_crop_rule"] for r in rows if r["split"] == s and r["class"] == c), 0) for s in sp]
        b = axes[0].bar(x + (k - 1.5) * w, v, w, label=c, color=cols[k])
        axes[0].bar_label(b, fontsize=7)
    axes[0].set_xticks(x, sp)
    axes[0].set_ylabel("finding crops")
    axes[0].set_title("Crops per class and split")
    axes[0].legend(fontsize=8)
    allr = [r for r in rows if r["split"] == "all"] or [r for r in rows if r["split"] == "train"]
    v = [r["crops_after_crop_rule"] for r in allr]
    b = axes[1].barh(CLASSES[::-1], v[::-1], color=cols[::-1])
    axes[1].bar_label(b, labels=[f"{n} ({n / max(1, sum(v)):.1%})" for n in v[::-1]], fontsize=8)
    axes[1].set_title(f"{allr[0]['split']}: class share (imbalance ratio {max(v) / max(1, min(v)):.1f}:1)")
    axes[1].set_xlim(0, max(v) * 1.3)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    out = ROOT / "reports"
    man = read_csv(DATA / "processed/manifest.csv")
    splits = json.loads((DATA / "splits/dentex_splits.json").read_text(encoding="utf-8"))
    assign = splits["assignments"]
    ann_file = DATA / DISEASE_DIR / "train_quadrant_enumeration_disease.json"
    images, recs = parse_dentex_coco(ann_file, f"{DISEASE_DIR}/xrays", "dentex_train_disease")
    dis = {r["file_path"]: r for r in man if r["dataset_source"] == DISEASE_DIR}
    split_of = lambda rec: dis.get(rec["image_path"], {}).get("split") or assign.get(dis.get(rec["image_path"], {}).get("image_id"))  # noqa: E731
    rows = class_table(recs, split_of)
    write_csv(out / "class_imbalance_before.csv", rows)
    plot(rows, out / "class_distribution_before.png", "BEFORE integration: DENTEX disease subset, persisted project splits (seed 42)")

    # cross-check against the cached crops the experiments actually trained on
    cache_check = {}
    for sp in ("train", "val"):
        f = ROOT / f"runtime/ml_cache/crops_{sp}_224.npz"
        if f.is_file():
            with np.load(f) as z:
                y = z["y"]
            cached = dict(zip(CLASSES, np.bincount(y, minlength=4).tolist()))
            computed = {r["class"]: r["crops_after_crop_rule"] for r in rows if r["split"] == sp}
            cache_check[sp] = {"cached": cached, "computed": computed, "identical": cached == computed}

    # images / duplicates / near duplicates
    dis_rows = list(dis.values())
    by_hash = defaultdict(list)
    for r in man:
        by_hash[r["content_hash"]].append(r)
    exact_within = [r["image_id"] for r in dis_rows if r["duplicate_of"]]
    exact_other = sorted({(r["image_id"], o["image_id"], o["dataset_source"]) for r in dis_rows for o in by_hash[r["content_hash"]]
                          if o["image_id"] != r["image_id"] and o["dataset_source"] != DISEASE_DIR})
    dh = json.loads((DATA / "processed/dhash_cache.json").read_text(encoding="utf-8"))
    items = [(r["image_id"], r["content_hash"], dh[r["file_path"]], DATA / r["file_path"]) for r in dis_rows if r["file_path"] in dh]
    near, n_cand, max_corr = near_duplicate_pairs(items)
    sp_by_id = {r["image_id"]: r["split"] for r in dis_rows}
    near_cross = [p for p in near if sp_by_id.get(p[0]) != sp_by_id.get(p[1])]

    per_image = Counter()
    for r in recs:
        if r["target_class"]:
            per_image[r["image_path"]] += 1
    cls_img = {c: Counter() for c in CLASSES}
    for r in recs:
        if r["target_class"]:
            cls_img[r["target_class"]][r["image_path"]] += 1
    concentration = {}
    for c in CLASSES:
        cnt = sorted(cls_img[c].values(), reverse=True)
        tot = sum(cnt)
        top10 = sum(cnt[:max(1, len(cnt) // 10)])
        concentration[c] = {"findings": tot, "radiographs": len(cnt), "max_per_radiograph": cnt[0] if cnt else 0,
                            "share_in_top_10pct_radiographs": round(top10 / tot, 3) if tot else None}

    inv = {
        "generated": datetime.now(timezone.utc).isoformat(), "script": "scripts/dataset/audit_class_imbalance.py",
        "inputs": {"annotation_file": str(ann_file.relative_to(ROOT)), "annotation_sha256": sha256_file(ann_file),
                   "manifest_sha256": sha256_file(DATA / "processed/manifest.csv"),
                   "split_file_sha256": sha256_file(DATA / "splits/dentex_splits.json"), "split_seed": splits.get("seed"),
                   "split_fractions": splits.get("fractions"), "split_fingerprint": splits.get("fingerprint")},
        "classifier_data": {
            "source": "DENTEX quadrant-enumeration-disease (training archive)", "image_type": "panoramic",
            "images_in_annotation_file": len(images),
            "images_with_target_findings": len(per_image),
            "images_without_any_annotation": sum(1 for v in images.values() if v["n_annotations"] == 0),
            "images_per_split": dict(Counter(r["split"] for r in dis_rows)),
            "images_with_findings_per_split": dict(Counter(split_of({"image_path": p}) for p in per_image)),
            "findings_total": sum(1 for r in recs if r["target_class"]),
            "annotations_dropped": [{"annotation_id": r["annotation_id"], "reason": r["mapping_note"]} for r in recs if not r["target_class"]],
            "findings_failing_crop_rule": sum(1 for r in recs if r["target_class"] and not crop_ok(r)),
            "findings_per_radiograph": {"mean": round(float(np.mean(list(per_image.values()))), 2), "max": max(per_image.values())},
            "class_concentration": concentration,
            "crop_cache_cross_check": cache_check,
        },
        "duplicates": {
            "exact_within_disease_subset": {"count": len(exact_within), "image_ids": exact_within,
                                            "note": "manifest duplicate_of: later copies of a byte-identical image"},
            "exact_with_other_dentex_subsets": {"count": len(exact_other), "examples": exact_other[:10],
                                                "note": "same radiograph also in quadrant / enumeration / unlabelled subsets; the "
                                                        "split file assigns such twins by content hash, so they share one split"},
            "near_duplicates": {"method": "dHash Hamming <= 4 + 256x128 thumbnail correlation >= 0.97 (scripts/check_leakage.py rule)",
                                "hash_candidates": n_cand, "confirmed": len(near), "confirmed_across_splits": len(near_cross),
                                "max_candidate_correlation": max_corr, "pairs": near},
        },
        "patients": {"patient_ids_available": False,
                     "note": "DENTEX file names carry no patient id; manifest patient_id is a content-hash surrogate (one radiograph = one "
                             "group). Patient-level separation across splits therefore CANNOT be claimed, and it cannot be checked "
                             "whether a minority class comes from few patients; per-radiograph concentration is reported instead."},
        "class_counts_before_and_after_crop_rule": {sp: {r["class"]: [r["findings"], r["crops_after_crop_rule"]] for r in rows if r["split"] == sp}
                                                     for sp in SPLITS + ["all"]},
        "unlabelled_images_policy": "1571 unlabelled DENTEX radiographs and 27 disease-subset images without annotations are not used as "
                                    "negatives; teeth without a finding annotation are never labelled healthy.",
    }
    (out / "dataset_inventory.json").write_text(json.dumps(inv, indent=1, default=str), encoding="utf-8")
    print(json.dumps(inv["class_counts_before_and_after_crop_rule"], indent=0))
    print("crop cache cross-check:", {k: v["identical"] for k, v in cache_check.items()})
    print("near duplicates:", inv["duplicates"]["near_duplicates"]["confirmed"], "cross-split", len(near_cross))


if __name__ == "__main__":
    main()
