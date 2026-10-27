"""Temperature scaling with a leakage guard, for the DRAFT calibration experiment
(reports/cv5_calibration_experiment_registration_DRAFT.md). Not used by any run until that registration is approved.

* ``fit_temperature`` minimises the mean negative log-likelihood over log T by golden-section search (deterministic, no tuning
  knobs beyond the registered bounds).
* ``fit_per_fold`` fits one temperature per fold and REFUSES any partition other than the registered fitting partition, so
  held-out, calibration-split or test predictions cannot be used for fitting by mistake.
* Temperature scaling divides logits by one positive scalar, so the arg-max (and hence every discrimination metric based on the
  predicted class, e.g. macro-F1) is unchanged; only probability-based metrics can change.
"""
from __future__ import annotations

import numpy as np

T_BOUNDS = (0.05, 20.0)
FIT_PARTITION = "inner_validation"


def softmax(logits, t: float = 1.0) -> np.ndarray:
    z = np.asarray(logits, dtype=np.float64) / float(t)
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(logits, labels, t: float = 1.0) -> float:
    p = softmax(logits, t)
    y = np.asarray(labels, dtype=int)
    return float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-300, None)).mean())


def fit_temperature(logits, labels, bounds=T_BOUNDS, tol: float = 1e-6) -> float:
    """Golden-section search of NLL over log T within ``bounds``."""
    y = np.asarray(labels, dtype=int)
    if len(y) == 0 or np.asarray(logits).shape[0] != len(y):
        raise ValueError("logits must be (N, C) with N == len(labels) > 0")
    a, b = np.log(bounds[0]), np.log(bounds[1])
    g = (np.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = nll(logits, y, np.exp(c)), nll(logits, y, np.exp(d))
    while b - a > tol:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = nll(logits, y, np.exp(c))
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = nll(logits, y, np.exp(d))
    return float(np.exp((a + b) / 2))


def fit_per_fold(parts: dict) -> dict:
    """parts: {fold: {"partition": str, "logits": (N, C), "labels": (N,)}} -> {fold: T}. Only FIT_PARTITION is accepted."""
    out = {}
    for fold, p in parts.items():
        if p.get("partition") != FIT_PARTITION:
            raise PermissionError(f"fold {fold}: temperature may only be fitted on '{FIT_PARTITION}', got {p.get('partition')!r}")
        out[fold] = fit_temperature(p["logits"], p["labels"])
    return out
