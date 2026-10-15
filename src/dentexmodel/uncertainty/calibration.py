"""Calibration and selective-prediction metrics."""
from __future__ import annotations

import numpy as np


def _prep(probs, labels):
    p = np.asarray(probs, dtype=np.float64)
    y = np.asarray(labels, dtype=int)
    if p.ndim != 2 or len(p) != len(y):
        raise ValueError("probs must be (N, C) and labels (N,)")
    if len(y) == 0:
        raise ValueError("no samples")
    if y.min() < 0 or y.max() >= p.shape[1]:
        raise ValueError("label index out of range for the number of classes")
    return p, y


def reliability_bins(probs, labels, n_bins: int = 10) -> list:
    """Top-label reliability diagram data: per bin confidence, accuracy, count."""
    p, y = _prep(probs, labels)
    conf, pred = p.max(axis=1), p.argmax(axis=1)
    correct = (pred == y).astype(float)
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (conf > lo) & (conf <= hi) if i > 0 else (conf >= lo) & (conf <= hi)
        n = int(m.sum())
        out.append({"bin": i, "lower": float(lo), "upper": float(hi), "count": n,
                    "confidence": float(conf[m].mean()) if n else None, "accuracy": float(correct[m].mean()) if n else None})
    return out


def expected_calibration_error(probs, labels, n_bins: int = 10) -> float:
    p, y = _prep(probs, labels)
    bins = reliability_bins(p, y, n_bins)
    n = len(y)
    return float(sum(b["count"] / n * abs(b["accuracy"] - b["confidence"]) for b in bins if b["count"]))


def brier_score(probs, labels) -> float:
    """Multiclass Brier score (mean squared error to one-hot targets, summed over classes)."""
    p, y = _prep(probs, labels)
    onehot = np.eye(p.shape[1])[y]
    return float(((p - onehot) ** 2).sum(axis=1).mean())


def risk_coverage(confidence, correct) -> dict:
    """Risk-coverage curve: sort by confidence desc; risk = error rate among the retained top-k."""
    c = np.asarray(confidence, dtype=np.float64)
    ok = np.asarray(correct, dtype=bool)
    if len(c) != len(ok) or len(c) == 0:
        raise ValueError("confidence and correct must be equal-length, non-empty")
    order = np.argsort(-c, kind="stable")
    errs = (~ok[order]).astype(float)
    k = np.arange(1, len(c) + 1)
    risk = np.cumsum(errs) / k
    coverage = k / len(c)
    return {"coverage": coverage.tolist(), "risk": risk.tolist(), "aurc": float(risk.mean())}
