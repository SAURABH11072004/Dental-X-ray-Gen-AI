#!/usr/bin/env python
"""Stage 1 of Data/reports/training_recipe_comparison_protocol.md: production recipe P (5 seeds) vs C0r recipe E (5 seeds) vs the
deployed checkpoint, on the VALIDATION split only, with the CACHED production-detector boxes
(docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json). Evaluation only. Calibration and test are never read.

Definitions identical to scripts/ml_crop_robust_eval.py: load_gray -> 3 channels, crop_region (pad 0.10, 224), ImageNet
normalisation, fp32, argmax; findings matched to cached detector boxes one-to-one by IoU >= 0.5, class-agnostic.
Acceptance criteria as pre-registered in the protocol (section 5). Writes Data/reports/training_recipe_comparison_results.json.
"""
import _bootstrap  # noqa: F401
import itertools
import json
import sys
import time
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
IOU, SCORE = 0.5, 0.3
CL = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
DET_CACHE = Path("docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json")
P_DIR = Path("runtime/recipe_experiment/checkpoints")
ACCEPT = {"gain_min": 0.027, "seed_pairs_min": 4, "cross_pairs_min": 20, "class_f1_drop_max": 0.05, "gt_macro_f1_drop_max": 0.02}


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
    return rep


def main() -> int:
    s = get_settings()
    out = s.data_root / "reports" / "training_recipe_comparison_results.json"
    if out.exists():
        print("refusing to overwrite", out)
        return 2
    torch, tv = TM.require_torch()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cls_info = active_model(s, "classification")
    pad, size = float(cls_info.metadata.get("crop_pad", 0.1)), int(cls_info.metadata.get("image_size", 224))
    det_cache = json.loads(DET_CACHE.read_text(encoding="utf-8"))
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == T.TASK_LEVEL["classification"] and assign.get(r.image_id) == "val"]
    t0 = time.time()
    gt_crops, det_crops, y, mi, missed = [], [], [], [], 0
    for row, anns, cats in T._annotations_for(s, svc, rows):
        u8 = (np.clip(np.repeat(load_gray(s.data_root / row.file_path)[..., None], 3, axis=2), 0, 1) * 255).astype(np.uint8)
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
        dboxes = [d[:4] for d in det_cache[row.image_id] if d[4] >= SCORE]
        m = match([f[1] for f in finds], dboxes, IOU)
        for i, (lab, b, c) in enumerate(finds):
            y.append(CL.index(lab))
            gt_crops.append(c)
            hit = m.get(i)
            dc = T.crop_region(u8, dboxes[hit[0]], size, pad) if hit else None
            if dc is None:
                missed += 1
            else:
                det_crops.append(dc)
                mi.append(len(y) - 1)
    y, mi = np.asarray(y), np.asarray(mi)
    Xg, Xd = np.stack(gt_crops), np.stack(det_crops)

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
            res.append(np.concatenate(p).argmax(1))
        del model
        torch.cuda.empty_cache()
        return res

    def score(ag, ad):
        e2e = np.full(len(y), -1)
        e2e[mi] = ad
        return {"gt_all": metrics(y, ag), "det_matched": metrics(y[mi], ad),
                "end_to_end": {"accuracy": float((e2e == y).mean()),
                               "recall": {c: float(((e2e == k) & (y == k)).sum() / (y == k).sum()) for k, c in enumerate(CL)}},
                "prediction_changed_gt_vs_det": int((ag[mi] != ad).sum())}

    paths = {"deployed": {"deployed": Path(cls_info.path)},
             "P_production_recipe": {sd: P_DIR / f"recipeP_s{sd}_classification_v1.pth" for sd in SEEDS},
             "E_C0r_recipe": {sd: Path("runtime/candidates") / f"C0r_s{sd}.pth" for sd in SEEDS}}
    res = {"generated": datetime.now(timezone.utc).isoformat(), "split": "val", "protocol": "Data/reports/training_recipe_comparison_protocol.md",
           "acceptance_criteria": ACCEPT, "detector_boxes": str(DET_CACHE), "detector_boxes_sha256": file_sha256(DET_CACHE),
           "data": {"n_findings": int(len(y)), "n_matched": int(len(mi)), "n_unmatched": int(missed),
                    "supports": {c: int((y == k).sum()) for k, c in enumerate(CL)},
                    "manifest_sha256": file_sha256(s.processed_dir / "manifest.json"), "split_assignments_sha": assignments_sha(s.splits_dir / "dentex_splits.json")},
           "models": {}}
    for grp, d in paths.items():
        res["models"][grp] = {}
        for sd, p in d.items():
            if not p.is_file():
                res["models"][grp][str(sd)] = {"missing": str(p)}
                continue
            ag, ad = predict(p)
            res["models"][grp][str(sd)] = {"checkpoint": str(p), "sha256": file_sha256(p), **score(ag, ad)}

    def val(grp, sd, *path):
        v = res["models"][grp][str(sd)]
        for k in path:
            v = v[k]
        return v
    keys = {"det_macro_f1": ("det_matched", "macro_f1"), "gt_macro_f1": ("gt_all", "macro_f1"), "det_accuracy": ("det_matched", "accuracy"),
            "gt_accuracy": ("gt_all", "accuracy"), "det_balanced_accuracy": ("det_matched", "balanced_accuracy"),
            "det_macro_precision": ("det_matched", "macro_precision"), "det_macro_recall": ("det_matched", "macro_recall"),
            "e2e_accuracy": ("end_to_end", "accuracy"), "changed_gt_vs_det": ("prediction_changed_gt_vs_det",),
            **{f"det_{c}_{m}": ("det_matched", "per_class", c, m) for c in CL for m in ("precision", "recall", "f1")},
            **{f"gt_{c}_{m}": ("gt_all", "per_class", c, m) for c in CL for m in ("precision", "recall", "f1")}}
    ok = {g: [sd for sd in SEEDS if "missing" not in res["models"][g][str(sd)]] for g in ("P_production_recipe", "E_C0r_recipe")}
    res["aggregate_mean_sd"] = {g: {k: [float(np.mean([val(g, sd, *p) for sd in ok[g]])), float(np.std([val(g, sd, *p) for sd in ok[g]], ddof=1)) if len(ok[g]) > 1 else None]
                                    for k, p in keys.items()} for g in ok if ok[g]}
    res["aggregate_mean_sd"]["deployed"] = {k: val("deployed", "deployed", *p) for k, p in keys.items()}
    common = [sd for sd in SEEDS if sd in ok["P_production_recipe"] and sd in ok["E_C0r_recipe"]]
    seedpair = {k: [val("E_C0r_recipe", sd, *p) - val("P_production_recipe", sd, *p) for sd in common] for k, p in keys.items()}
    res["seed_pairs_E_minus_P"] = {k: {"per_seed": dict(zip(map(str, common), v)), "mean": float(np.mean(v)) if v else None,
                                       "n_E_better": int(sum(x > 0 for x in v))} for k, v in seedpair.items()}
    cross = [val("E_C0r_recipe", a, *keys["det_macro_f1"]) - val("P_production_recipe", b, *keys["det_macro_f1"])
             for a, b in itertools.product(ok["E_C0r_recipe"], ok["P_production_recipe"])]
    res["cross_pairs_det_macro_f1"] = {"n": len(cross), "n_E_better": int(sum(x > 0 for x in cross)), "mean": float(np.mean(cross)) if cross else None}
    if len(common) == 5 and len(cross) == 25:
        sp = res["seed_pairs_E_minus_P"]
        c1 = sp["det_macro_f1"]["n_E_better"] >= ACCEPT["seed_pairs_min"] and sp["det_macro_f1"]["mean"] > ACCEPT["gain_min"] \
            and res["cross_pairs_det_macro_f1"]["n_E_better"] >= ACCEPT["cross_pairs_min"]
        c2 = sp["det_Deep Caries_recall"]["mean"] >= 0 and sp["det_Periapical Lesion_recall"]["mean"] >= 0
        worst = min(sp[f"det_{c}_f1"]["mean"] for c in CL)
        c3 = worst >= -ACCEPT["class_f1_drop_max"]
        c4 = sp["gt_macro_f1"]["mean"] >= -ACCEPT["gt_macro_f1_drop_max"]
        res["acceptance"] = {"1_primary": {"pass": bool(c1), "seed_pairs_E_better": sp["det_macro_f1"]["n_E_better"], "mean_gain": sp["det_macro_f1"]["mean"],
                                           "cross_pairs_E_better": res["cross_pairs_det_macro_f1"]["n_E_better"]},
                             "2_minority_recall_not_lower": {"pass": bool(c2), "deep_caries": sp["det_Deep Caries_recall"]["mean"],
                                                             "periapical_lesion": sp["det_Periapical Lesion_recall"]["mean"]},
                             "3_no_class_f1_drop_over_0.05": {"pass": bool(c3), "worst_class_mean_change": worst},
                             "4_gt_macro_f1_drop_at_most_0.02": {"pass": bool(c4), "mean_change": sp["gt_macro_f1"]["mean"]},
                             "all_pass": bool(c1 and c2 and c3 and c4)}
    else:
        res["acceptance"] = {"all_pass": False, "reason": f"{len(common)} complete seed pairs / {len(cross)} cross pairs; criterion 1 requires 5 and 25"}
    res["duration_s"] = round(time.time() - t0, 1)
    out.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"acceptance": res["acceptance"], "data": res["data"]}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
