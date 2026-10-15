"""Predictive-uncertainty measures. All functions are pure NumPy and raise ``ValueError`` on malformed input
rather than silently returning 0."""
from __future__ import annotations

import numpy as np

from dentexmodel.utils.geometry import box_iou, mask_iou

EPS = 1e-12


def _check_probs(p: np.ndarray, atol: float = 1e-3) -> np.ndarray:
    p = np.asarray(p, dtype=np.float64)
    if p.ndim < 1 or p.shape[-1] < 2:
        raise ValueError("probabilities need a class axis with at least 2 classes")
    if not np.all(np.isfinite(p)) or np.any(p < -atol):
        raise ValueError("probabilities must be finite and non-negative")
    s = p.sum(axis=-1)
    if not np.allclose(s, 1.0, atol=atol):
        raise ValueError("probabilities must sum to 1 along the last axis (apply softmax first)")
    return np.clip(p, 0.0, 1.0)


def entropy(p, normalize: bool = True) -> np.ndarray:
    """Shannon entropy H(p) = -sum_c p_c log p_c (natural log). Normalised by log(C) -> range [0, 1]."""
    p = _check_probs(p)
    h = -(p * np.log(p + EPS)).sum(axis=-1)
    h = np.maximum(h, 0.0)
    return h / np.log(p.shape[-1]) if normalize else h


def jensen_shannon_disagreement(member_probs, normalize: bool = True) -> np.ndarray:
    """Generalised Jensen-Shannon divergence across ensemble members.

    ``member_probs`` has shape ``(M, ..., C)``. JSD = H(mean_m p_m) - mean_m H(p_m) (mutual information
    between the label and the member index). It is 0 when all members agree and is bounded by log(min(M, C)).
    Normalising by log(C) keeps it comparable with normalised entropy. Needs M >= 2.
    """
    p = np.asarray(member_probs, dtype=np.float64)
    if p.ndim < 2 or p.shape[0] < 2:
        raise ValueError("ensemble disagreement needs at least 2 members")
    p = _check_probs(p)
    mean = p.mean(axis=0)
    h_mean = entropy(mean, normalize=False)
    h_each = entropy(p, normalize=False).mean(axis=0)
    jsd = np.maximum(h_mean - h_each, 0.0)
    return jsd / np.log(p.shape[-1]) if normalize else jsd


def mask_instability(masks) -> float:
    """Mean pairwise (1 - IoU) among >=2 binary masks of the same instance. 0 = identical masks."""
    ms = [np.asarray(m, dtype=bool) for m in masks]
    if len(ms) < 2:
        raise ValueError("mask instability needs at least 2 mask predictions")
    vals = [1.0 - mask_iou(ms[i], ms[j]) for i in range(len(ms)) for j in range(i + 1, len(ms))]
    return float(np.mean(vals))


def detection_instability(runs, iou_thresh: float = 0.5) -> dict:
    """Instability of detections across >=2 runs (each run: list of (box_xyxy, score)).

    Greedy IoU matching of every run against the first. Returns mean (1 - IoU) of matched boxes, the fraction
    of reference boxes left unmatched in some run, and mean absolute score difference of matches."""
    if len(runs) < 2:
        raise ValueError("detection instability needs at least 2 runs")
    ref = list(runs[0])
    loc, miss, sdiff = [], 0, []
    for other in runs[1:]:
        used = set()
        for rb, rs in ref:
            best, bj = 0.0, -1
            for j, (ob, _os) in enumerate(other):
                if j in used:
                    continue
                iou = box_iou(rb, ob)
                if iou > best:
                    best, bj = iou, j
            if best >= iou_thresh:
                used.add(bj)
                loc.append(1.0 - best)
                sdiff.append(abs(rs - other[bj][1]))
            else:
                miss += 1
    n_ref = max(1, len(ref) * (len(runs) - 1))
    return {"localization_instability": float(np.mean(loc)) if loc else None,
            "unmatched_fraction": miss / n_ref, "score_abs_diff": float(np.mean(sdiff)) if sdiff else None,
            "n_reference_boxes": len(ref)}


def mc_dropout_summary(sample_probs) -> dict:
    """Entropy of the mean prediction (total), mean per-sample entropy (aleatoric part) and their difference
    (epistemic part / BALD) for T stochastic forward passes ``(T, ..., C)``."""
    p = _check_probs(np.asarray(sample_probs, dtype=np.float64))
    if p.shape[0] < 2:
        raise ValueError("need at least 2 stochastic samples")
    total = entropy(p.mean(axis=0), normalize=False)
    aleatoric = entropy(p, normalize=False).mean(axis=0)
    return {"total": total, "aleatoric": aleatoric, "epistemic": np.maximum(total - aleatoric, 0.0)}
