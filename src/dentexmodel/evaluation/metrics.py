"""Evaluation metrics (NumPy only): classification F1/confusion, detection AP/mAP, mask IoU/AP."""
from __future__ import annotations

import numpy as np

from dentexmodel.utils.geometry import box_iou, mask_iou


def confusion_matrix(y_true, y_pred, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for t, p in zip(y_true, y_pred):
        if not (0 <= t < n_classes and 0 <= p < n_classes):
            raise ValueError("class index out of range")
        cm[t, p] += 1
    return cm


def classification_report(y_true, y_pred, n_classes: int, class_names=None) -> dict:
    """Per-class precision/recall/F1 and macro averages. Classes with no support are excluded from the macro
    average (reported in ``classes_without_support``) so absent classes do not silently deflate it."""
    cm = confusion_matrix(y_true, y_pred, n_classes)
    tp = np.diag(cm).astype(float)
    support = cm.sum(axis=1)
    pred_n = cm.sum(axis=0)
    prec = np.divide(tp, pred_n, out=np.zeros(n_classes), where=pred_n > 0)
    rec = np.divide(tp, support, out=np.zeros(n_classes), where=support > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(n_classes), where=(prec + rec) > 0)
    present = support > 0
    names = class_names or [str(i) for i in range(n_classes)]
    return {
        "accuracy": float(tp.sum() / cm.sum()) if cm.sum() else None,
        "macro_f1": float(f1[present].mean()) if present.any() else None,
        "macro_precision": float(prec[present].mean()) if present.any() else None,
        "macro_recall": float(rec[present].mean()) if present.any() else None,
        "per_class": {names[i]: {"precision": float(prec[i]), "recall": float(rec[i]), "f1": float(f1[i]), "support": int(support[i])}
                      for i in range(n_classes)},
        "classes_without_support": [names[i] for i in range(n_classes) if not present[i]],
        "confusion_matrix": cm.tolist(),
    }


def _ap_from_pr(rec: np.ndarray, prec: np.ndarray) -> float:
    """Area under the monotone precision envelope (all-point interpolation)."""
    mrec = np.concatenate(([0.0], rec, [1.0]))
    mpre = np.concatenate(([0.0], prec, [0.0]))
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def average_precision(preds: list, gts: list, iou_thr: float = 0.5, iou_fn=box_iou) -> float | None:
    """AP for one class. ``preds``: list of (image_key, score, geometry); ``gts``: list of (image_key, geometry).
    Returns None when there is no ground truth for the class."""
    if not gts:
        return None
    gt_by_img: dict = {}
    for k, g in gts:
        gt_by_img.setdefault(k, []).append(g)
    used = {k: [False] * len(v) for k, v in gt_by_img.items()}
    order = sorted(range(len(preds)), key=lambda i: -preds[i][1])
    tp = np.zeros(len(order))
    fp = np.zeros(len(order))
    for rank, i in enumerate(order):
        k, _s, g = preds[i]
        cands = gt_by_img.get(k, [])
        best, bj = 0.0, -1
        for j, gg in enumerate(cands):
            iou = iou_fn(g, gg)
            if iou > best:
                best, bj = iou, j
        if best >= iou_thr and not used[k][bj]:
            used[k][bj] = True
            tp[rank] = 1
        else:
            fp[rank] = 1
    if len(order) == 0:
        return 0.0
    ctp, cfp = np.cumsum(tp), np.cumsum(fp)
    return _ap_from_pr(ctp / len(gts), ctp / np.maximum(ctp + cfp, 1e-12))


def detection_map(preds: list, gts: list, iou_thresholds=None, iou_fn=box_iou) -> dict:
    """COCO-style mAP. ``preds``: (image_key, class, score, geometry); ``gts``: (image_key, class, geometry)."""
    thr = list(iou_thresholds) if iou_thresholds is not None else [round(0.5 + 0.05 * i, 2) for i in range(10)]
    classes = sorted({g[1] for g in gts})
    per_class = {}
    for c in classes:
        p = [(k, s, g) for k, cc, s, g in preds if cc == c]
        t = [(k, g) for k, cc, g in gts if cc == c]
        per_class[c] = [average_precision(p, t, th, iou_fn) for th in thr]
    def mean(vals):
        vals = [v for v in vals if v is not None]
        return float(np.mean(vals)) if vals else None
    ap50_idx = thr.index(0.5) if 0.5 in thr else 0
    return {"map": mean([mean(v) for v in per_class.values()]),
            "ap50": mean([v[ap50_idx] for v in per_class.values()]),
            "per_class_ap50": {str(c): v[ap50_idx] for c, v in per_class.items()},
            "iou_thresholds": thr, "n_classes_with_gt": len(classes)}


def mask_ap(preds: list, gts: list, iou_thr: float = 0.5) -> dict:
    """Mask AP using mask IoU for matching (same input format as :func:`detection_map`, geometry = bool arrays)."""
    return detection_map(preds, gts, iou_thresholds=[iou_thr], iou_fn=mask_iou)


def mean_mask_iou(pred_masks: list, gt_masks: list) -> float | None:
    """Mean IoU over paired masks (greedy best-match per ground truth)."""
    if not gt_masks:
        return None
    vals = []
    for g in gt_masks:
        vals.append(max((mask_iou(p, g) for p in pred_masks), default=0.0))
    return float(np.mean(vals))
