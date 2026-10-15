#!/usr/bin/env python
"""Crop-robustness comparison on the VALIDATION split: deployed classifier, C0r (5 seeds) and B_cropjitter (5 seeds), each scored
on ground-truth-box crops and on production-detector-box crops. Evaluation only. Calibration and test are never read.

Same definitions as scripts/evaluate_end_to_end.py: production loading (load_gray -> 3 channels), production detector
(score >= configs threshold), production crop_region (pad 0.10, 224 px), ImageNet normalisation, argmax; findings matched to
detector boxes one-to-one by IoU >= 0.5, class-agnostic. Acceptance criteria are fixed in ACCEPT below (set before results).
Writes Data/reports/crop_robustness_experiment.json (never overwrites).
"""
import _bootstrap  # noqa: F401
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

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

SEEDS = (42, 43, 44, 45, 46)
IOU = 0.5
EVID = Path("docs/audit_evidence/ml_improvement/crop_robustness")
ACCEPT = {"macro_f1_gain_min": 0.027, "macro_f1_seeds_better_min": 4, "class_f1_drop_max": 0.05, "gt_macro_f1_drop_max": 0.02}
CL = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]


def match(gt, pred, thr):
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


def metrics(y, p):
    rep = classification_report(y, p, 4, CL)
    rep["balanced_accuracy"] = float(np.mean([rep["per_class"][c]["recall"] for c in CL if rep["per_class"][c]["support"]]))
    rep["n"] = len(y)
    return rep


def main() -> int:
    s = get_settings()
    out = s.data_root / "reports" / "crop_robustness_experiment.json"
    if out.exists():
        print("refusing to overwrite", out)
        return 2
    torch, tv = TM.require_torch()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cls_info, det_info = active_model(s, "classification"), active_model(s, "detection")
    pad, size = float(cls_info.metadata.get("crop_pad", 0.1)), int(cls_info.metadata.get("image_size", 224))
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == T.TASK_LEVEL["classification"] and assign.get(r.image_id) == "val"]
    t0 = time.time()
    # ---------------- crops (production path), detector run once
    gt_crops, det_crops, y, matched_idx, missed, det_cache = [], [], [], [], 0, {}
    for row, anns, cats in T._annotations_for(s, svc, rows):
        rgb01 = np.repeat(load_gray(s.data_root / row.file_path)[..., None], 3, axis=2)
        u8 = (np.clip(rgb01, 0, 1) * 255).astype(np.uint8)
        finds = []
        for a in anns:
            lab = annotation_finding(a, cats) if "category_id_3" in a else None
            if lab is None or not a.get("bbox") or lab not in CL:
                continue
            x, yy, w, h = a["bbox"]
            b = [float(x), float(yy), float(x + w), float(yy + h)]
            c = T.crop_region(u8, b, size, pad)
            if c is not None:
                finds.append((lab, b, c))
        if not finds:
            continue
        dets = TM.detect_teeth(rgb01, row.image_id, s).detections
        dboxes = [d.box for d in dets]
        det_cache[row.image_id] = [[round(v, 2) for v in d.box] + [round(d.score, 4)] for d in dets]
        m = match([f[1] for f in finds], dboxes, IOU)
        for i, (lab, b, c) in enumerate(finds):
            y.append(CL.index(lab))
            gt_crops.append(c)
            hit = m.get(i)
            dc = T.crop_region(u8, dboxes[hit[0]], size, pad) if hit else None
            if dc is None:
                missed += 1
                det_crops.append(None)
            else:
                det_crops.append(dc)
                matched_idx.append(len(y) - 1)
    y = np.asarray(y)
    mi = np.asarray(matched_idx)
    Xg = np.stack(gt_crops)
    Xd = np.stack([det_crops[i] for i in mi])
    prep = time.time() - t0
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "val_detector_boxes.json").write_text(json.dumps(det_cache), encoding="utf-8")

    def predict(path):
        model = tv.models.resnet50(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, 4)
        model.load_state_dict(torch.load(path, map_location=dev, weights_only=True), strict=True)
        model.to(dev).eval()
        res = []
        for X in (Xg, Xd):
            p = []
            with torch.no_grad():
                for i in range(0, len(X), 64):
                    p.append(torch.softmax(model(T._norm(torch.from_numpy(X[i:i + 64]), dev, torch)).float(), 1).cpu().numpy())
            res.append(np.concatenate(p))
        del model
        torch.cuda.empty_cache()
        return res

    def score(pg, pd):
        ag, ad = pg.argmax(1), pd.argmax(1)
        e2e = np.full(len(y), -1)
        e2e[mi] = ad
        per_e2e = {c: {"recall_end_to_end": float(((e2e == k) & (y == k)).sum() / max(1, (y == k).sum())),
                       "missed": int(((e2e == -1) & (y == k)).sum())} for k, c in enumerate(CL)}
        return {"gt_all": metrics(y, ag), "gt_matched": metrics(y[mi], ag[mi]), "det_matched": metrics(y[mi], ad),
                "end_to_end": {"accuracy": float((e2e == y).mean()), "per_class": per_e2e},
                "prediction_changed_gt_vs_det": int((ag[mi] != ad).sum()), "n_matched": int(len(mi))}

    models = {"deployed": [("deployed", Path(cls_info.path))]}
    for exp in ("C0r", "B_cropjitter"):
        models[exp] = [(sd, Path("runtime/candidates") / f"{exp}_s{sd}.pth") for sd in SEEDS]
    res = {"generated": datetime.now(timezone.utc).isoformat(), "split": "val", "iou_match": IOU, "acceptance_criteria": ACCEPT,
           "data": {"n_findings": int(len(y)), "n_matched": int(len(mi)), "n_unmatched_findings": int(missed),
                    "supports": {c: int((y == k).sum()) for k, c in enumerate(CL)},
                    "manifest_sha256": file_sha256(s.processed_dir / "manifest.json"), "split_assignments_sha": assignments_sha(s.splits_dir / "dentex_splits.json")},
           "detector": {"version": det_info.version, "sha256": file_sha256(det_info.path), "score_threshold": float((s.models_cfg.get("inference", {}) or {}).get("score_threshold", 0.3))},
           "deployed_classifier": {"version": cls_info.version, "sha256": file_sha256(cls_info.path)}, "models": {}}
    for exp, lst in models.items():
        res["models"][exp] = {}
        for sd, p in lst:
            if not p.is_file():
                res["models"][exp][str(sd)] = {"missing": str(p)}
                continue
            pg, pd = predict(p)
            res["models"][exp][str(sd)] = {"checkpoint": str(p), "sha256": file_sha256(p), **score(pg, pd)}
            np.savez(EVID / f"val_probs_{exp}_{sd}.npz", gt=pg, det=pd, y=y, matched=mi)

    # ---------------- aggregates + acceptance (B vs C0r, paired by seed)
    def get(exp, sd, path):
        v = res["models"][exp][str(sd)]
        for k in path:
            v = v[k]
        return v
    keys = {"det_macro_f1": ("det_matched", "macro_f1"), "gt_macro_f1": ("gt_all", "macro_f1"), "det_accuracy": ("det_matched", "accuracy"),
            "det_balanced_accuracy": ("det_matched", "balanced_accuracy"), "det_macro_precision": ("det_matched", "macro_precision"),
            "det_macro_recall": ("det_matched", "macro_recall"), "gt_accuracy": ("gt_all", "accuracy"), "e2e_accuracy": ("end_to_end", "accuracy"),
            **{f"det_{c}_{m}": ("det_matched", "per_class", c, m) for c in CL for m in ("precision", "recall", "f1")},
            **{f"gt_{c}_{m}": ("gt_all", "per_class", c, m) for c in CL for m in ("precision", "recall", "f1")},
            **{f"e2e_{c}_recall": ("end_to_end", "per_class", c, "recall_end_to_end") for c in CL}}
    agg = {}
    for exp in ("C0r", "B_cropjitter"):
        ok = [sd for sd in SEEDS if "missing" not in res["models"][exp][str(sd)]]
        agg[exp] = {"seeds": ok, **{k: [float(np.mean([get(exp, sd, p) for sd in ok])), float(np.std([get(exp, sd, p) for sd in ok], ddof=1)) if len(ok) > 1 else None]
                                    for k, p in keys.items()}} if ok else {"seeds": []}
    agg["deployed"] = {k: get("deployed", "deployed", p) for k, p in keys.items()}
    res["aggregate_mean_sd"] = agg
    common = [sd for sd in SEEDS if "missing" not in res["models"]["C0r"][str(sd)] and "missing" not in res["models"]["B_cropjitter"][str(sd)]]
    d = lambda k: [get("B_cropjitter", sd, keys[k]) - get("C0r", sd, keys[k]) for sd in common]  # noqa: E731
    paired = {k: {"mean": float(np.mean(d(k))), "min": float(min(d(k))), "max": float(max(d(k))), "n_better": int(sum(x > 0 for x in d(k))), "n": len(common)}
              for k in keys} if common else {}
    res["paired_B_minus_C0r"] = paired
    if len(common) == 5:
        c1 = paired["det_macro_f1"]["n_better"] >= ACCEPT["macro_f1_seeds_better_min"] and paired["det_macro_f1"]["mean"] > ACCEPT["macro_f1_gain_min"]
        c2 = paired["det_Deep Caries_recall"]["mean"] >= 0 and paired["det_Periapical Lesion_recall"]["mean"] >= 0
        worst = min(paired[f"det_{c}_f1"]["mean"] for c in CL)
        c3 = worst >= -ACCEPT["class_f1_drop_max"]
        c4 = paired["gt_macro_f1"]["mean"] >= -ACCEPT["gt_macro_f1_drop_max"]
        res["acceptance"] = {"1_detector_macro_f1_gain": {"pass": bool(c1), "mean_gain": paired["det_macro_f1"]["mean"], "seeds_better": paired["det_macro_f1"]["n_better"]},
                             "2_minority_recall_not_lower": {"pass": bool(c2), "deep_caries": paired["det_Deep Caries_recall"]["mean"],
                                                             "periapical_lesion": paired["det_Periapical Lesion_recall"]["mean"]},
                             "3_no_class_f1_drop_over_0.05": {"pass": bool(c3), "worst_class_mean_change": worst},
                             "4_gt_macro_f1_drop_at_most_0.02": {"pass": bool(c4), "mean_change": paired["gt_macro_f1"]["mean"]},
                             "all_pass": bool(c1 and c2 and c3 and c4)}
    else:
        res["acceptance"] = {"all_pass": False, "reason": f"only {len(common)} paired seeds available"}
    res["duration_s"] = {"crop_and_detector_prep": round(prep, 1), "total": round(time.time() - t0, 1)}
    out.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"acceptance": res["acceptance"], "data": res["data"]}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
