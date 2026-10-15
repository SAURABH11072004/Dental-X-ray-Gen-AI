"""Shared helpers for the classification experiments: cached tooth crops with provenance, metrics, GPU guards.

Crops are produced with the SAME function the deployed classifier uses (``trainers.crop_region``, 10 % padding, 224 px) from
ground-truth boxes, and cached under runtime/ml_cache/ (git-ignored). Nothing in Data/ is written.
"""
import _bootstrap  # noqa: F401
import json
from pathlib import Path

import numpy as np
from PIL import Image

from dentexmodel.config import get_settings
from dentexmodel.data.coco import annotation_finding
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.splits import load_split_file
from dentexmodel.training import trainers as T

CACHE = Path("runtime/ml_cache")
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]


def load_split_crops(split: str, size: int = 224):
    """-> dict(X uint8 (N,size,size,3), y int (N,), meta list[dict]) for ``split`` in train|val|calibration|test."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"crops_{split}_{size}.npz"
    mf = CACHE / f"crops_{split}_{size}.json"
    if f.is_file() and mf.is_file():
        z = np.load(f)
        return {"X": z["X"], "y": z["y"], "meta": json.loads(mf.read_text(encoding="utf-8"))}
    s = get_settings()
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == T.TASK_LEVEL["classification"] and assign.get(r.image_id) == split]
    X, y, meta = [], [], []
    for row, anns, cats in T._annotations_for(s, svc, rows):
        img = np.asarray(Image.open(s.data_root / row.file_path).convert("RGB"))
        for a in anns:
            lab = annotation_finding(a, cats) if "category_id_3" in a else None
            if lab is None or not a.get("bbox"):
                continue
            x, yy, w, h = a["bbox"]
            c = T.crop_region(img, (x, yy, x + w, yy + h), size)
            if c is None:
                continue
            X.append(c)
            y.append(CLASSES.index(lab))
            meta.append({"image_id": row.image_id, "ann_id": a.get("id"), "label": lab, "content_hash": row.content_hash,
                         "bbox": [float(v) for v in a["bbox"]], "image_wh": [int(img.shape[1]), int(img.shape[0])],
                         "fdi_q": a.get("category_id_1"), "fdi_t": a.get("category_id_2")})
    X = np.stack(X)
    y = np.asarray(y, dtype=np.int64)
    np.savez(f, X=X, y=y)
    mf.write_text(json.dumps(meta), encoding="utf-8")
    return {"X": X, "y": y, "meta": meta}


def report(y_true, y_pred, prob=None):
    """Accuracy, macro/weighted F1, balanced accuracy, per-class P/R/F1/support, confusion matrix, one-vs-rest ROC-AUC / PR-AUC."""
    n = len(CLASSES)
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    cm = np.zeros((n, n), int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    sup = cm.sum(1)
    tp = np.diag(cm)
    prec = np.divide(tp, cm.sum(0), out=np.zeros(n), where=cm.sum(0) > 0)
    rec = np.divide(tp, sup, out=np.zeros(n), where=sup > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(n), where=(prec + rec) > 0)
    out = {"n": int(len(y_true)), "accuracy": float(tp.sum() / max(1, cm.sum())), "macro_f1": float(f1.mean()),
           "weighted_f1": float((f1 * sup).sum() / max(1, sup.sum())), "balanced_accuracy": float(rec.mean()),
           "per_class": {CLASSES[i]: {"precision": float(prec[i]), "recall": float(rec[i]), "f1": float(f1[i]), "support": int(sup[i])} for i in range(n)},
           "confusion": cm.tolist(), "minority_recall_periapical": float(rec[3])}
    if prob is not None:
        prob = np.asarray(prob)
        roc, pr = {}, {}
        for i in range(n):
            pos = (y_true == i)
            if pos.sum() == 0 or pos.sum() == len(pos):
                continue
            roc[CLASSES[i]] = _auc(prob[:, i], pos)
            pr[CLASSES[i]] = _ap(prob[:, i], pos)
        out["roc_auc_ovr"] = roc
        out["pr_auc_ovr"] = pr
        out["macro_roc_auc"] = float(np.mean(list(roc.values()))) if roc else None
        out["macro_pr_auc"] = float(np.mean(list(pr.values()))) if pr else None
        out["nll"] = float(-np.log(np.clip(prob[np.arange(len(y_true)), y_true], 1e-9, 1)).mean())
        out["ece"] = _ece(prob, y_true)
    return out


def _auc(score, pos):
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score))
    s = score[order]
    i = 0
    r = np.arange(1, len(score) + 1, dtype=float)
    while i < len(s):                       # average ranks for ties
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        r[i:j + 1] = r[i:j + 1].mean()
        i = j + 1
    ranks[order] = r
    n1, n0 = pos.sum(), (~pos).sum()
    return float((ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _ap(score, pos):
    order = np.argsort(-score, kind="mergesort")
    p = pos[order]
    tp = np.cumsum(p)
    prec = tp / np.arange(1, len(p) + 1)
    return float((prec * p).sum() / max(1, p.sum()))


def _ece(prob, y, bins=10):
    conf = prob.max(1)
    pred = prob.argmax(1)
    e = 0.0
    for b in range(bins):
        m = (conf > b / bins) & (conf <= (b + 1) / bins)
        if m.any():
            e += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(e)


def free_gpu_mb():
    import torch
    return torch.cuda.mem_get_info()[0] // (1024 * 1024) if torch.cuda.is_available() else 0
