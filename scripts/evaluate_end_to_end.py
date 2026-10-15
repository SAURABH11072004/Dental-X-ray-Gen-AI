#!/usr/bin/env python
"""End-to-end (detector boxes -> classifier) evaluation on the VALIDATION split. Evaluation only: no training, no threshold tuning.

Three settings on the same validation radiographs (the findings sub-set, quadrant_enumeration_disease, split=val):
  A1  existing evaluation pipeline: ground-truth finding boxes, PIL RGB crops (as scripts/evaluate_model.py) -> reproduces the
      recorded validation metrics;
  A2  production image path with ground-truth boxes: load_gray -> 3 channels -> classify_regions (isolates loading differences);
  B   production pipeline: detect_teeth (score >= production threshold) -> classify_regions on detector boxes.
A ground-truth finding is matched to at most one detector box (one-to-one greedy by IoU, no class information used).
Detection is scored against the FULL tooth annotation of the pixel-identical quadrant_enumeration copy of each radiograph
(the findings sub-set annotates only diseased teeth, so it cannot score detection precision).

    python scripts/evaluate_end_to_end.py            # writes Data/reports/end_to_end_validation_evaluation.{json,md} + _predictions.csv
"""
import _bootstrap  # noqa: F401
import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from dentexmodel.config import get_settings
from dentexmodel.data.coco import annotation_finding
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.preprocess import load_gray
from dentexmodel.data.splits import load_split_file
from dentexmodel.evaluation.metrics import classification_report
from dentexmodel.evaluation.test_ledger import file_sha256
from dentexmodel.inference import torch_models as TM
from dentexmodel.inference.registry import active_model
from dentexmodel.training import trainers as T
from dentexmodel.training.trainers import assignments_sha
from dentexmodel.utils.geometry import box_iou

SPLIT = "val"                       # fixed: this script never reads calibration or test
IOU_PRIMARY = 0.5                   # same convention as the app (backend/services/pipeline.py MATCH_IOU)
IOU_EXTRA = (0.3, 0.75)             # sensitivity, fixed before running
STEM = "end_to_end_validation_evaluation"


def xyxy(b):
    x, y, w, h = b
    return [float(x), float(y), float(x + w), float(y + h)]


def match(gt, pred, thr):
    """One-to-one greedy matching by descending IoU; returns {gt_index: (pred_index, iou)}."""
    pairs = sorted(((box_iou(g, p), i, j) for i, g in enumerate(gt) for j, p in enumerate(pred)), reverse=True)
    ug, up, m = set(), set(), {}
    for v, i, j in pairs:
        if v < thr:
            break
        if i in ug or j in up:
            continue
        ug.add(i)
        up.add(j)
        m[i] = (j, v)
    return m


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def cls_metrics(y, p, names):
    rep = classification_report(y, p, len(names), names)
    rep["balanced_accuracy"] = float(np.mean([rep["per_class"][c]["recall"] for c in names if rep["per_class"][c]["support"]]))
    rep["n"] = len(y)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=None, help="default Data/reports; existing files are never overwritten")
    a = ap.parse_args()
    s = get_settings()
    out = Path(a.out_dir) if a.out_dir else s.data_root / "reports"
    targets = [out / f"{STEM}.json", out / f"{STEM}_predictions.csv"]
    if any(t.exists() for t in targets):
        print("Refusing to overwrite:", [str(t) for t in targets if t.exists()])
        return 2
    torch, tv = TM.require_torch()
    det_info, cls_info = active_model(s, "detection"), active_model(s, "classification")
    names = cls_info.metadata["class_names"]
    idx = {c: i for i, c in enumerate(names)}
    size = int(cls_info.metadata.get("image_size", 224))
    thr = float((s.models_cfg.get("inference", {}) or {}).get("score_threshold", 0.3))
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = svc.manifest("main")
    qed = [r for r in rows if r.annotation_status == "annotated" and not r.is_test_data and r.annotation_level == T.TASK_LEVEL["classification"]
           and assign.get(r.image_id) == SPLIT]
    qe_by_hash = {}
    for r in rows:
        if r.annotation_status == "annotated" and r.annotation_level == "quadrant_enumeration" and r.content_hash:
            qe_by_hash.setdefault(r.content_hash, r)
    items = T._annotations_for(s, svc, qed)
    twins = {r.content_hash: r for r in qe_by_hash.values() if r.content_hash in {q.content_hash for q in qed}}
    twin_items = {r.content_hash: (anns, cats) for r, anns, cats in T._annotations_for(s, svc, list(twins.values()))}
    for h, r in twins.items():
        if assign.get(r.image_id) != SPLIT:
            raise SystemExit(f"split leak: tooth-annotation twin {r.image_id} of a validation radiograph is in {assign.get(r.image_id)}")
    # A1 uses the same classifier weights loaded the way the existing evaluation loads them
    model_a1, dev = TM._build("classification", cls_info, s)
    recs, img_recs, unmatched_pred = [], [], Counter()
    det_counts = {t: Counter() for t in (IOU_PRIMARY,) + IOU_EXTRA}
    t0 = time.time()
    for row, anns, cats in items:
        path = s.data_root / row.file_path
        with Image.open(path) as im:
            mode = im.mode
            pil_rgb = np.asarray(im.convert("RGB"))
        rgb01 = np.repeat(load_gray(path)[..., None], 3, axis=2)                 # production loading (backend/services/images.py)
        prod_u8 = (np.clip(rgb01, 0, 1) * 255).astype(np.uint8)                   # what _prep_crops crops from
        maxdiff = int(np.abs(prod_u8.astype(int) - pil_rgb.astype(int)).max())
        finds = []
        for a in anns:                                                            # same filter as trainers._crops
            lab = annotation_finding(a, cats) if "category_id_3" in a else None
            if lab is None or not a.get("bbox") or lab not in idx:
                continue
            b = xyxy(a["bbox"])
            c = T.crop_region(pil_rgb, b, size)
            if c is None:
                continue
            finds.append({"ann_id": a.get("id"), "label": lab, "box": b, "crop_a1": c})
        if not finds:
            continue
        # A1: existing pipeline crops (PIL RGB) + T._norm
        with torch.no_grad():
            pa1 = torch.softmax(model_a1(T._norm(torch.from_numpy(np.stack([f["crop_a1"] for f in finds])), dev, torch)).float(), 1).cpu().numpy()
        # A2: production path, ground-truth boxes
        pa2 = TM.classify_regions(rgb01, [f["box"] for f in finds], s)["probabilities"]
        # B: production detector + classifier
        det = TM.detect_teeth(rgb01, row.image_id, s)
        dboxes = [d.box for d in det.detections]
        dscores = [d.score for d in det.detections]
        pb = TM.classify_regions(rgb01, dboxes, s)["probabilities"] if dboxes else []
        gtb = [f["box"] for f in finds]
        mt = {t: match(gtb, dboxes, t) for t in (IOU_PRIMARY,) + IOU_EXTRA}
        # detection vs the full tooth annotation of the pixel-identical twin
        tw = twins.get(row.content_hash)
        teeth = [xyxy(x["bbox"]) for x in twin_items[row.content_hash][0] if x.get("bbox")] if tw else None
        if teeth is not None:
            for t in det_counts:
                m = match(teeth, dboxes, t)
                det_counts[t].update(tp=len(m), fp=len(dboxes) - len(m), fn=len(teeth) - len(m), images=1)
            tooth_m = match(teeth, dboxes, IOU_PRIMARY)
            tooth_matched_pred = {j for j, _ in tooth_m.values()}
        else:
            tooth_matched_pred = None
        # detector boxes that match no ground-truth finding (teeth without a finding label, or false detections)
        fm = {j for j, _ in mt[IOU_PRIMARY].values()}
        for j in range(len(dboxes)):
            if j in fm or pb[j] is None:
                continue
            kind = "unknown" if tooth_matched_pred is None else ("tooth_without_finding_label" if j in tooth_matched_pred else "no_tooth_match")
            unmatched_pred[(kind, names[int(np.argmax(pb[j]))])] += 1
        for i, f in enumerate(finds):
            best_tooth = max((box_iou(f["box"], tb) for tb in teeth), default=None) if teeth else None
            r = {"image_id": row.image_id, "ann_id": f["ann_id"], "gt_label": f["label"], "gt_box": [round(v, 1) for v in f["box"]],
                 "a1_pred": names[int(pa1[i].argmax())], "a2_pred": names[int(np.argmax(pa2[i]))] if pa2[i] is not None else None,
                 "gt_box_vs_twin_tooth_iou": None if best_tooth is None else round(best_tooth, 4)}
            for t in (IOU_PRIMARY,) + IOU_EXTRA:
                hit = mt[t].get(i)
                r[f"b_pred@{t}"] = names[int(np.argmax(pb[hit[0]]))] if hit and pb[hit[0]] is not None else None
            hit = mt[IOU_PRIMARY].get(i)
            best_any = max((box_iou(f["box"], d) for d in dboxes), default=0.0)
            r.update(matched=bool(hit), match_iou=round(hit[1], 4) if hit else None, best_det_iou=round(best_any, 4),
                     det_box=[round(v, 1) for v in dboxes[hit[0]]] if hit else None, det_score=round(dscores[hit[0]], 4) if hit else None,
                     b_probs=[round(v, 4) for v in pb[hit[0]]] if hit and pb[hit[0]] is not None else None,
                     a2_probs=[round(v, 4) for v in pa2[i]] if pa2[i] is not None else None)
            recs.append(r)
        img_recs.append({"image_id": row.image_id, "mode": mode, "prod_vs_pil_max_abs_diff": maxdiff, "n_findings": len(finds),
                         "n_detections": len(dboxes), "has_tooth_twin": teeth is not None, "n_teeth_gt": len(teeth) if teeth else None})
    dur = time.time() - t0

    # ------------------------------------------------------------------------------------------------ metrics
    Y = [r["gt_label"] for r in recs]
    yi = [idx[v] for v in Y]
    res = {"generated": datetime.now(timezone.utc).isoformat(), "split": SPLIT, "duration_s": round(dur, 1),
           "models": {"detection": {"model_id": det_info.model_id, "version": det_info.version, "sha256": file_sha256(det_info.path),
                                    "sidecar_sha256_prefix": det_info.metadata.get("checkpoint_sha256")},
                      "classification": {"model_id": cls_info.model_id, "version": cls_info.version, "sha256": file_sha256(cls_info.path),
                                         "sidecar_sha256_prefix": cls_info.metadata.get("checkpoint_sha256")}},
           "data": {"manifest_sha256": file_sha256(s.processed_dir / "manifest.json"), "split_assignments_sha": assignments_sha(s.splits_dir / "dentex_splits.json"),
                    "n_radiographs": len(img_recs), "n_findings": len(recs),
                    "n_with_tooth_annotation_twin": sum(1 for x in img_recs if x["has_tooth_twin"]),
                    "image_modes": dict(Counter(x["mode"] for x in img_recs)),
                    "prod_vs_pil_pixel_max_abs_diff": max(x["prod_vs_pil_max_abs_diff"] for x in img_recs)},
           "settings": {"detector_score_threshold": thr, "detector_mixed_precision": bool((s.models_cfg.get("inference", {}) or {}).get("mixed_precision", True)),
                        "crop_pad": cls_info.metadata.get("crop_pad"), "crop_size": size, "classifier_decision": "argmax (frozen rule; abstention display layer not applied)",
                        "iou_primary": IOU_PRIMARY, "iou_extra": list(IOU_EXTRA), "matching": "one-to-one greedy by descending box IoU, class-agnostic"}}
    res["A1_existing_gt_pipeline"] = cls_metrics(yi, [idx[r["a1_pred"]] for r in recs], names)
    ok2 = [r for r in recs if r["a2_pred"] is not None]
    res["A2_production_gt_boxes"] = cls_metrics([idx[r["gt_label"]] for r in ok2], [idx[r["a2_pred"]] for r in ok2], names)
    res["A1_vs_A2_prediction_agreement"] = float(np.mean([r["a1_pred"] == r["a2_pred"] for r in ok2]))
    for t in (IOU_PRIMARY,) + IOU_EXTRA:
        k = f"b_pred@{t}"
        mm = [r for r in recs if r[k] is not None and r["a2_pred"] is not None]
        res[f"matched@{t}"] = {"n_matched": len(mm), "n_missed": len(recs) - len(mm),
                               "missed_by_class": dict(Counter(r["gt_label"] for r in recs if r[k] is None)),
                               "B_detector_boxes": cls_metrics([idx[r["gt_label"]] for r in mm], [idx[r[k]] for r in mm], names),
                               "A2_gt_boxes_same_teeth": cls_metrics([idx[r["gt_label"]] for r in mm], [idx[r["a2_pred"]] for r in mm], names)}
        # end-to-end accounting over ALL ground-truth findings: a missed tooth is a missed finding
        cm = np.zeros((len(names), len(names) + 1), int)
        for r in recs:
            cm[idx[r["gt_label"]], idx[r[k]] if r[k] is not None else len(names)] += 1
        per = {}
        for c, i in idx.items():
            sup = int(cm[i].sum())
            rec_ = cm[i, i] / sup if sup else None
            pred_c = cm[:, i].sum()
            prec = cm[i, i] / pred_c if pred_c else None
            per[c] = {"support": sup, "recall_end_to_end": rec_, "precision_on_matched": prec, "missed": int(cm[i, -1]),
                      "f1": (2 * prec * rec_ / (prec + rec_)) if prec and rec_ else 0.0}
        res[f"end_to_end@{t}"] = {"accuracy": float(np.trace(cm[:, :len(names)]) / cm.sum()), "balanced_accuracy": float(np.mean([v["recall_end_to_end"] for v in per.values()])),
                                  "macro_f1": float(np.mean([v["f1"] for v in per.values()])), "per_class": per,
                                  "confusion_with_missed_column": cm.tolist(), "columns": names + ["MISSED"]}
    res["detection_vs_full_tooth_annotation"] = {str(t): {**prf(c["tp"], c["fp"], c["fn"]), "images": c["images"]} for t, c in det_counts.items()}
    res["detection_vs_full_tooth_annotation"]["n_predictions"] = sum(x["n_detections"] for x in img_recs if x["has_tooth_twin"])
    res["detection_vs_full_tooth_annotation"]["n_gt_teeth"] = sum(x["n_teeth_gt"] for x in img_recs if x["has_tooth_twin"])
    # decomposition per finding at the primary IoU
    dec = Counter()
    for r in recs:
        a2c = r["a2_pred"] == r["gt_label"]
        if r[f"b_pred@{IOU_PRIMARY}"] is None:
            dec["missed (A2 correct)" if a2c else "missed (A2 wrong)"] += 1
        else:
            bc = r[f"b_pred@{IOU_PRIMARY}"] == r["gt_label"]
            dec[{(True, True): "both correct", (True, False): "correct with GT box, wrong with detector box",
                 (False, True): "wrong with GT box, correct with detector box", (False, False): "wrong with both boxes"}[(a2c, bc)]] += 1
    res["decomposition@0.5"] = dict(dec)
    bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    res["flip_rate_by_match_iou"] = []
    for lo, hi in bins:
        sel = [r for r in recs if r["match_iou"] is not None and lo <= r["match_iou"] < hi]
        res["flip_rate_by_match_iou"].append({"iou": f"{lo:.1f}-{min(hi, 1.0):.1f}", "n": len(sel),
                                              "prediction_changed": sum(r[f"b_pred@{IOU_PRIMARY}"] != r["a2_pred"] for r in sel)})
    miss = [r for r in recs if not r["matched"]]
    res["missed_findings_best_iou"] = {"n": len(miss), "best_det_iou_quartiles": np.percentile([r["best_det_iou"] for r in miss], [0, 25, 50, 75, 100]).round(3).tolist() if miss else None,
                                       "gt_box_vs_twin_tooth_iou_quartiles": np.percentile([r["gt_box_vs_twin_tooth_iou"] for r in miss if r["gt_box_vs_twin_tooth_iou"] is not None], [0, 25, 50, 75, 100]).round(3).tolist() if miss else None}
    allt = [r["gt_box_vs_twin_tooth_iou"] for r in recs if r["gt_box_vs_twin_tooth_iou"] is not None]
    res["finding_box_vs_tooth_annotation_iou_quartiles"] = np.percentile(allt, [0, 25, 50, 75, 100]).round(3).tolist() if allt else None
    res["unmatched_detector_boxes@0.5"] = {"by_kind_and_predicted_class": {f"{k}|{c}": n for (k, c), n in sorted(unmatched_pred.items())},
                                           "total": sum(unmatched_pred.values()),
                                           "note": "No ground-truth finding is attached to these boxes. A box matching a fully annotated tooth is a tooth DENTEX did not "
                                                   "label with a finding; that does NOT make it healthy. The classifier has no no-finding class, so the app shows a "
                                                   "closest finding class for every one of them. They are not counted as false positives in any precision above."}
    res["image_records"] = img_recs
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{STEM}.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    with open(out / f"{STEM}_predictions.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()))
        w.writeheader()
        for r in recs:
            w.writerow({k: json.dumps(v) if isinstance(v, list) else v for k, v in r.items()})
    print(json.dumps({k: res[k] for k in ("data", "decomposition@0.5")}, indent=1, default=float))
    print(f"wrote {out / (STEM + '.json')} ({dur:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
