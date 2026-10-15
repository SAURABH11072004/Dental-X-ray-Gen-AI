#!/usr/bin/env python
"""Evaluate a trained checkpoint on the validation split (default) or - once, deliberately - the locked test split.

    python scripts/evaluate_model.py --checkpoint dentex_findings_classification_v1.pth
    python scripts/evaluate_model.py --checkpoint <new>.pth --split test --final-test --authorized-by "<name>" --reason "<why>"

Metrics are computed from the model's real outputs against the DENTEX ground truth and written to
Data/reports/eval_<version>_<split>.json and .md. The test split needs --final-test plus a recorded authorization and passes
the gate in dentexmodel.evaluation.test_ledger (validation report first, one use per checkpoint, one new candidate per task);
every test run is appended to Data/reports/test_set_ledger.json. See docs/RESEARCH_INTEGRITY.md.
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

from dentexmodel.config import get_settings
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.splits import load_split_file
from dentexmodel.errors import DentaMindError
from dentexmodel.inference.registry import scan_checkpoints
from dentexmodel.training import trainers as T
from dentexmodel.utils.logging_utils import setup_logging


def items_for_split(settings, task: str, split: str, limit: int | None):
    svc = DatasetService(settings)
    level = T.TASK_LEVEL[task]
    assign = load_split_file(settings.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == level and assign.get(r.image_id) == split]
    if limit:
        rows = rows[:limit]
    return T._annotations_for(settings, svc, rows)


def eval_classifier(settings, info, items, device, torch, tv):
    from dentexmodel.evaluation.metrics import classification_report
    names = info.metadata["class_names"]
    idx = {c: i for i, c in enumerate(names)}
    size = int(info.metadata.get("image_size", 224))
    X, y = T._crops(settings, items, size)
    model = getattr(tv.models, info.architecture)(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, len(names))
    model.load_state_dict(torch.load(info.path, map_location=device, weights_only=True), strict=True)
    model.to(device).eval()
    Xt = torch.from_numpy(np.stack(X))
    pred, prob = [], []
    with torch.no_grad():
        for i in range(0, len(Xt), 64):
            p_ = torch.softmax(model(T._norm(Xt[i:i + 64], device, torch)).float(), 1).cpu().numpy()
            prob.append(p_)
            pred += p_.argmax(1).tolist()
    prob = np.concatenate(prob)
    known = [(idx[t], p) for t, p in zip(y, pred) if t in idx]
    rep = classification_report([k[0] for k in known], [k[1] for k in known], len(names), names)
    rep["n_crops"] = len(known)
    # sensitivity / specificity / one-vs-rest ROC-AUC per class (derived from the same predictions and probabilities)
    ytrue = np.array([idx[t] for t in y if t in idx])
    cm = np.array(rep["confusion_matrix"])
    for k, nm in enumerate(names):
        tp, fn = cm[k, k], cm[k].sum() - cm[k, k]
        fp, tn = cm[:, k].sum() - cm[k, k], cm.sum() - cm[k].sum() - cm[:, k].sum() + cm[k, k]
        d = rep["per_class"][nm]
        d["sensitivity"] = float(tp / (tp + fn)) if tp + fn else None
        d["specificity"] = float(tn / (tn + fp)) if tn + fp else None
        pos, neg = prob[ytrue == k, k], prob[ytrue != k, k]
        d["roc_auc_ovr"] = float(((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())) if len(pos) and len(neg) else None
    aucs = [v["roc_auc_ovr"] for v in rep["per_class"].values() if v["roc_auc_ovr"] is not None]
    rep["macro_roc_auc_ovr"] = float(np.mean(aucs)) if aucs else None
    rep["unknown_labels_skipped"] = len(y) - len(known)
    return {"classification": rep}


def eval_detector(settings, info, items, device, torch, tv, task):
    seg = task == "segmentation"
    names = info.metadata["class_names"]
    label_index = None
    if info.metadata.get("label_mode") == "fdi":
        label_index = {int(c): i + 1 for i, c in enumerate(names)}
    ds = T.DetDataset(settings.data_root, items, seg, label_index, train=False)
    model = T.build_detector(torch, tv, info.architecture, len(names) + 1, pretrained=False)
    model.load_state_dict(torch.load(info.path, map_location=device, weights_only=True), strict=True)
    model.to(device)
    ev = T.evaluate_detector(model, ds, device, with_masks=seg)
    # operating point used by the app (score_threshold from configs/models.yaml)
    thr = float((settings.models_cfg.get("inference", {}) or {}).get("score_threshold", 0.3))
    ev["operating_point"] = _operating_point(model, ds, device, torch, thr)
    if task == "numbering":
        ev["numbering"] = _numbering_metrics(model, ds, device, torch, names)
    return {task: ev}


NUMBERING_BAR = 0.80   # registration gate: exact FDI accuracy among correctly localised teeth, on the validation split


def _numbering_metrics(model, ds, device, torch, names, iou=0.5, min_score=0.3):
    """How often is the *tooth number* right? Predictions go through the same resolve_numbering used by the app
    (class-agnostic NMS + one box per number). A prediction is matched to the ground-truth tooth it overlaps (IoU>=0.5)."""
    from collections import defaultdict
    from dentexmodel.utils.geometry import box_iou
    model.eval()
    code = {i + 1: int(n) for i, n in enumerate(names)}
    n_gt = n_matched = n_exact = n_quadrant = n_pred = 0
    per = defaultdict(lambda: [0, 0, 0])       # fdi -> [gt, matched, exact]
    with torch.no_grad():
        for i in range(len(ds)):
            x, tgt, _ = ds[i]
            o = model([x.to(device).float() / 255.0])[0]
            boxes, scores, labels = o["boxes"].cpu().tolist(), o["scores"].cpu().tolist(), o["labels"].cpu().tolist()
            keep = T.resolve_numbering(boxes, scores, labels, nms_iou=iou, min_score=min_score)
            n_pred += len(keep)
            gts = [(b, code[int(l)]) for b, l in zip(tgt["boxes"].tolist(), tgt["labels"].tolist())]
            used = set()
            for gb, gf in gts:
                n_gt += 1
                per[gf][0] += 1
                best, bj = 0.0, None
                for j in keep:
                    if j in used:
                        continue
                    v = box_iou(boxes[j], gb)
                    if v > best:
                        best, bj = v, j
                if bj is not None and best >= iou:
                    used.add(bj)
                    n_matched += 1
                    per[gf][1] += 1
                    pf = code[int(labels[bj])]
                    n_exact += pf == gf
                    per[gf][2] += pf == gf
                    n_quadrant += pf // 10 == gf // 10
    return {"n_ground_truth_teeth": n_gt, "n_predicted_after_resolution": n_pred, "n_matched_iou50": n_matched,
            "coverage": n_matched / n_gt if n_gt else None,
            "exact_accuracy_among_matched": n_exact / n_matched if n_matched else None,
            "quadrant_accuracy_among_matched": n_quadrant / n_matched if n_matched else None,
            "strict_accuracy_all_gt": n_exact / n_gt if n_gt else None,
            "per_tooth": {str(k): {"gt": v[0], "matched": v[1], "exact": v[2], "exact_accuracy": (v[2] / v[1]) if v[1] else None}
                          for k, v in sorted(per.items())},
            "operating_point": {"score_threshold": min_score, "nms_iou": iou, "match_iou": iou}}


def _operating_point(model, ds, device, torch, thr, iou=0.5):
    from dentexmodel.utils.geometry import box_iou
    model.eval()
    tp = fp = fn = 0
    with torch.no_grad():
        for i in range(len(ds)):
            x, tgt, _ = ds[i]
            o = model([x.to(device).float() / 255.0])[0]
            pb = [b for b, s in zip(o["boxes"].cpu().tolist(), o["scores"].cpu().tolist()) if s >= thr]
            gb = tgt["boxes"].tolist()
            used = set()
            for b in pb:
                best, bj = 0.0, -1
                for j, g in enumerate(gb):
                    v = box_iou(b, g)
                    if v > best and j not in used:
                        best, bj = v, j
                if best >= iou:
                    used.add(bj)
                    tp += 1
                else:
                    fp += 1
            fn += len(gb) - len(used)
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    return {"score_threshold": thr, "iou": iou, "tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec}


def to_md(rep: dict) -> str:
    L = [f"# Evaluation: {rep['model_version']} on the **{rep['split']}** split", "",
         f"Generated {rep['generated']}. Images: {rep['n_images']}. Dataset version: `{rep['dataset_version']}`.",
         "", "All numbers below were computed by running this checkpoint over that split. Research use only; not a diagnosis.", ""]
    for task, m in rep["metrics"].items():
        L += [f"## {task}", ""]
        if task == "classification":
            L += [f"- Accuracy: {m['accuracy']:.4f}; macro-F1: {m['macro_f1']:.4f}; macro one-vs-rest ROC-AUC: {m['macro_roc_auc_ovr']:.3f}; crops: {m['n_crops']}", "",
                  "| Class | Precision | Recall (sensitivity) | Specificity | F1 | ROC-AUC (OvR) | Support |", "|---|---:|---:|---:|---:|---:|---:|"]
            for c, v in m["per_class"].items():
                L.append(f"| {c} | {v['precision']:.3f} | {v['sensitivity']:.3f} | {v['specificity']:.3f} | {v['f1']:.3f} | {v['roc_auc_ovr']:.3f} | {v['support']} |")
            L += ["", "Confusion matrix (rows = true, columns = predicted), class order: " + ", ".join(m["per_class"]), "", "```"]
            L += [" ".join(f"{v:5d}" for v in row) for row in m["confusion_matrix"]] + ["```"]
        else:
            L += [f"- Box mAP@[.5:.95]: **{m['map']:.4f}**; AP@0.5: **{m['ap50']:.4f}**; ground-truth boxes: {m['n_ground_truth']}"]
            nb = m.get("numbering")
            if nb:
                L += [f"- **Tooth numbering** (same post-processing as the app): {nb['n_matched_iou50']}/{nb['n_ground_truth_teeth']} ground-truth teeth localised "
                      f"(coverage {nb['coverage']:.3f}); exact FDI number correct among localised: **{nb['exact_accuracy_among_matched']:.3f}**; "
                      f"correct quadrant: {nb['quadrant_accuracy_among_matched']:.3f}; strict accuracy over all teeth: {nb['strict_accuracy_all_gt']:.3f}",
                      "", "| FDI | GT teeth | Localised | Exact | Exact acc. |", "|---:|---:|---:|---:|---:|"]
                L += [f"| {k} | {v['gt']} | {v['matched']} | {v['exact']} | {'-' if v['exact_accuracy'] is None else format(v['exact_accuracy'], '.3f')} |"
                      for k, v in nb["per_tooth"].items()]
            if m.get("mask_ap50") is not None:
                L.append(f"- Mask AP@0.5: {m['mask_ap50']:.4f}; mean mask IoU {m['mean_mask_iou_matched']:.3f} and Dice {m['mean_dice_matched']:.3f} over {m['n_matched_for_iou']} matched teeth")
            op = m["operating_point"]
            L.append(f"- At score >= {op['score_threshold']} (app default), IoU >= {op['iou']}: TP {op['tp']}, FP {op['fp']}, FN {op['fn']}; "
                     f"precision {op['precision']:.3f}, recall {op['recall']:.3f}")
        L.append("")
    return "\n".join(L)


def _file_sha(path) -> str:
    from dentexmodel.evaluation.test_ledger import file_sha256
    return file_sha256(path)


def _register_numbering(info, rep, stem):
    """Write the evaluation outcome into the checkpoint's sidecar. The registry only accepts a numbering checkpoint whose
    sidecar says it passed the validation-split gate."""
    nb = rep["metrics"]["numbering"]["numbering"]
    passed = (nb["exact_accuracy_among_matched"] or 0) >= NUMBERING_BAR
    side = Path(info.path).with_suffix(".json")
    meta = json.loads(side.read_text(encoding="utf-8"))
    meta["evaluated_on"] = {"split": "val", "report": stem, "generated": rep["generated"], "passed": passed,
                            "gate": f"exact FDI accuracy among localised teeth >= {NUMBERING_BAR} on the validation split",
                            "exact_accuracy_among_matched": nb["exact_accuracy_among_matched"], "coverage": nb["coverage"],
                            "map": rep["metrics"]["numbering"]["map"]}
    side.write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    print(("REGISTERED" if passed else "NOT registered (gate failed)") + f": exact accuracy {nb['exact_accuracy_among_matched']:.3f} vs gate {NUMBERING_BAR}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", required=True, help="model id (path relative to Data/checkpoints)")
    ap.add_argument("--split", default="val", choices=["val", "calibration", "test"])
    ap.add_argument("--final-test", action="store_true", help="required to touch the locked test split")
    ap.add_argument("--authorized-by", default="", help="test split only: name of the person authorizing this final evaluation (recorded)")
    ap.add_argument("--reason", default="", help="test split only: why model selection is finished (recorded, >= 20 characters)")
    ap.add_argument("--reproduce", action="store_true", help="test split only: re-run a checkpoint's already-recorded test evaluation into --out-dir")
    ap.add_argument("--max-images", type=int, default=None)
    ap.add_argument("--out-dir", default=None, help="write the report here instead of Data/reports (reproduction runs; the numbering registration write-back is skipped)")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    a = ap.parse_args()
    s = get_settings()
    setup_logging(s.logs_dir, s.log_level)
    if a.split == "test" and not a.final_test:
        print("Refusing: the test split is locked. Re-run with --final-test once model selection is finished.")
        return 2
    torch, tv = T._require_torch()
    info = next((m for m in scan_checkpoints(s) if m.model_id == a.checkpoint.replace("\\", "/")), None)
    pending = bool(info) and info.task == "numbering" and not info.dental_specific and all(
        str(r).startswith(("not registered yet", "evaluation did not pass")) for r in info.metadata.get("rejected_reasons", ["x"]))
    if info is None or not (info.dental_specific or pending):      # a numbering checkpoint awaiting its evaluation may be evaluated
        why = info.provenance if info else "not found"
        print(f"Cannot evaluate '{a.checkpoint}': {why}")
        return 2
    test_ctx, kind = None, ("reproduction" if a.reproduce else "final_metrics")
    if a.split == "test":
        from dentexmodel.evaluation import test_ledger as TL
        if a.max_images:
            print("Refusing: a test-split evaluation is all-or-nothing (--max-images is not allowed).")
            return 2
        try:
            test_ctx = TL.authorize(s, info, kind, a.authorized_by, a.reason, a.out_dir)
        except DentaMindError as exc:
            print("Refusing test-split evaluation:", exc.message, exc.hint or "")
            return 2
    device = torch.device("cuda" if (a.device == "cuda" or (a.device == "auto" and torch.cuda.is_available())) else "cpu")
    try:
        items = items_for_split(s, info.task, a.split, a.max_images)
        if not items:
            print("No annotated images in that split for this task.")
            return 2
        metrics = (eval_classifier(s, info, items, device, torch, tv) if info.task == "classification"
                   else eval_detector(s, info, items, device, torch, tv, info.task))
    except DentaMindError as exc:
        print("Evaluation failed:", exc.message, exc.hint or "")
        return 1
    rep = {"generated": datetime.now(timezone.utc).isoformat(), "model_version": info.version, "model_id": info.model_id,
           "task": info.task, "split": a.split, "n_images": len(items), "dataset_version": T.dataset_version(s),
           "final_test": bool(a.final_test and a.split == "test"), "metrics": metrics, "software": T.software_versions(),
           "checkpoint_sha256": test_ctx["sha"] if test_ctx else _file_sha(info.path)}
    if test_ctx:
        rep["test_set_status"] = TL.test_status_for_report(test_ctx)
        rep["authorized_by"], rep["authorization_reason"], rep["test_kind"] = a.authorized_by.strip(), a.reason.strip(), kind
    out = Path(a.out_dir) if a.out_dir else s.data_root / "reports"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"eval_{info.version}_{a.split}"
    (out / f"{stem}.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (out / f"{stem}.md").write_text(to_md(rep), encoding="utf-8")
    if test_ctx:
        e = TL.record(s, info, kind, test_ctx, a.authorized_by, a.reason, metrics, len(items), str(out / f"{stem}.json"), "scripts/evaluate_model.py")
        print(f"recorded in the test-set ledger as entry {e['seq']} ({kind})")
    if info.task == "numbering" and a.split == "val" and not a.out_dir:
        _register_numbering(info, rep, stem)
    print("wrote", out / f"{stem}.json")
    print(to_md(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
