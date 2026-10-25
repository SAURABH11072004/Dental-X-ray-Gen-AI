"""P1 (approved 2026-10-16): clinician-verified labels -> TRAINING manifest rows. Opt-in only
(``build_combined_manifest.py --include-verified``); validation / calibration / test are never changed.

Every row is re-checked here, independently of the export step:
* the label is one of the four target classes;
* the row is backed by the hash-chained review log: the chain verifies, the row's ``record_hash`` is the LATEST decision for that
  region, its status is ``accepted_label``, label / box / image match the logged record, and the reviewer is still in the registry
  (a hand-edited or stale verified_findings.csv row is refused);
* training eligibility is re-derived from data/annotation/annotation_pool.csv and the frozen evaluation manifests
  (``clinical_review.training_eligibility``: evaluation radiographs, eval_locked twins and Hanoi without full review are excluded);
* the image file on disk still has the SHA-256 recorded in the pool;
* the padded crop passes the production crop rule.
A row that fails any check is skipped with a reason (returned); nothing is guessed or repaired.
"""
from __future__ import annotations

import json
from pathlib import Path

from clinical_review import ANN, _frozen_eval_shas, latest_decisions, load_reviewers, training_eligibility, verify_chain
from dsutil import CLASSES, crop_box_xyxy, read_csv, sha256_file


def verified_training_rows(verified_csv, pool_csv, splits_dir, data_root, log=None, reviewers_csv=None):
    """-> (rows in build_combined_manifest FIELDS format, [(region, reason) skipped])."""
    verified_csv, data_root = Path(verified_csv), Path(data_root)
    if not verified_csv.is_file():
        return [], []
    log = Path(log or ANN / "clinical_reviews.jsonl")
    ok_chain, _n = verify_chain(log)
    if not ok_chain:
        raise SystemExit(f"review log {log} fails its hash-chain check; refusing to use any verified label")
    latest = {(r["pool_id"], r["region_id"]): r for r in latest_decisions(log).values()}
    registered = {r["reviewer_id"] for r in load_reviewers(reviewers_csv).values()}
    pool = {r["pool_id"]: r for r in read_csv(pool_csv)}
    eval_shas = _frozen_eval_shas(splits_dir)
    rows, skipped, sizes, file_ok = [], [], {}, {}
    for v in read_csv(verified_csv):
        key = f"{v.get('pool_id')}:{v.get('region_id')}"
        if v.get("label") not in CLASSES:
            skipped.append((key, f"label {v.get('label')!r} is not a target class"))
            continue
        rec = latest.get((v.get("pool_id"), v.get("region_id")))
        if rec is None or rec.get("record_hash") != v.get("record_hash"):
            skipped.append((key, "not the latest logged decision for this region (missing, superseded or edited)"))
            continue
        if (rec["status"] != "accepted_label" or rec.get("label") != v.get("label")
                or rec.get("image_sha256") != v.get("image_sha256") or json.dumps(rec.get("box_xyxy")) != v.get("box_xyxy")):
            skipped.append((key, "row does not match its accepted record in the review log"))
            continue
        if rec.get("reviewer_id") not in registered:
            skipped.append((key, "reviewer is not (or no longer) in data/annotation/reviewers.csv"))
            continue
        v = {**v, "coverage": rec.get("coverage")}
        why = training_eligibility(v, pool, eval_shas)
        if why:
            skipped.append((key, why))
            continue
        p = pool[v["pool_id"]]
        img = data_root / p["image_path"]
        if p["image_path"] not in file_ok:
            file_ok[p["image_path"]] = img.is_file() and sha256_file(img) == p["image_sha256"]
        if not file_ok[p["image_path"]]:
            skipped.append((key, "image file missing or its SHA-256 changed"))
            continue
        if p["image_path"] not in sizes:
            from PIL import Image
            with Image.open(img) as im:
                sizes[p["image_path"]] = im.size
        W, H = sizes[p["image_path"]]
        x1, y1, x2, y2 = json.loads(v["box_xyxy"])
        bbox = [x1, y1, x2 - x1, y2 - y1]
        cx1, cy1, cx2, cy2 = crop_box_xyxy(bbox, W, H)
        if bbox[2] <= 0 or bbox[3] <= 0 or cx2 - cx1 < 4 or cy2 - cy1 < 4:
            skipped.append((key, "box fails the production crop rule"))
            continue
        rows.append({"sample_id": f"clinician:{v['pool_id']}:{v['region_id']}", "split": "train", "eval_subset": "train",
                     "source_dataset": f"clinician_verified:{p['source_dataset']}", "source_split": "clinician review",
                     "project_image_id": "", "original_image_id": p["image_id"], "original_file_name": Path(p["image_path"]).name,
                     "annotation_id": v["region_id"], "fdi_tooth": v.get("fdi") or "", "target_class": v["label"],
                     "class_index": CLASSES.index(v["label"]), "original_label": v["label"],
                     "annotation_type": "bbox (clinician-verified, Label Studio)", "image_type": "panoramic",
                     "image_path": p["image_path"], "image_sha256": p["image_sha256"], "image_width": W, "image_height": H,
                     "bbox_xywh": [round(b, 2) for b in bbox], "crop_xyxy": [round(c, 2) for c in (cx1, cy1, cx2, cy2)],
                     "radiograph_group": p["radiograph_group"],
                     "conversion": f"clinician decision '{v.get('decision')}' by {v.get('reviewer_id')} at {v.get('reviewed_at')}; "
                                   f"review record {str(v.get('record_hash'))[:16]}"})
    return rows, skipped
