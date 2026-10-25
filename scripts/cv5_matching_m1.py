"""Matching rule M1 (DRAFT registration reports/cv5_matching_rule_registration_DRAFT.md): library only, NOT RUN on CV5 data.

This module deliberately has no entry point. Applying it to the archived CV5 evaluation population is allowed only after the
registration is approved (see the registration's preconditions); its tests use synthetic data only.

M1 = the reference rule (score >= 0.3, greedy one-to-one, IoU >= 0.5; kaggle/dentamind_kaggle.match) UNCHANGED, plus a fallback:
a finding left unmatched by the reference rule is assigned the box with the highest IoU >= 0.5 among ALL boxes of its image (ties:
higher detector score, then lower box index). Under greedy matching every such box is already assigned to another finding, so the
finding inherits that finding's crop - and therefore its stored per-seed prediction - without new inference.
"""
from __future__ import annotations

import numpy as np

IOU_MIN = 0.5


def box_iou(a, b) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return float(inter / union) if union > 0 else 0.0


def greedy_one_to_one(gts, boxes, thr=IOU_MIN) -> dict:
    """Reference rule (identical to kaggle/dentamind_kaggle.match): {finding index: box index}."""
    pairs = sorted(((box_iou(g, p), i, j) for i, g in enumerate(gts) for j, p in enumerate(boxes)), reverse=True)
    ug, up, m = set(), set(), {}
    for v, i, j in pairs:
        if v < thr:
            break
        if i in ug or j in up:
            continue
        ug.add(i)
        up.add(j)
        m[i] = j
    return m


def assign_m1(gts, boxes, scores, thr=IOU_MIN) -> tuple[dict, dict]:
    """-> (reference assignment, fallback assignment {finding: box}) for one image. The reference part is never altered."""
    ref = greedy_one_to_one(gts, boxes, thr)
    fb = {}
    for i, g in enumerate(gts):
        if i in ref:
            continue
        cands = [(box_iou(g, b), scores[j], -j) for j, b in enumerate(boxes) if box_iou(g, b) >= thr]
        if cands:
            fb[i] = -max(cands)[2]
    return ref, fb


def inherited_source(ref: dict, fb: dict) -> dict:
    """For each fallback finding, the finding whose (already classified) crop it inherits. Raises if a fallback box is unassigned
    (that would need new inference, which M1's registration excludes -> NO VERDICT)."""
    owner = {j: i for i, j in ref.items()}
    out = {}
    for i, j in fb.items():
        if j not in owner:
            raise ValueError(f"fallback box {j} of finding {i} has no reference owner: new inference would be needed")
        out[i] = owner[j]
    return out


def end_to_end_scores(y, pred, n_classes=4) -> dict:
    """End-to-end per-class precision / recall / F1 and macro-F1 over ALL findings. pred = -1 for an unmatched finding: a false
    negative of its true class and no false positive of any class."""
    y, pred = np.asarray(y), np.asarray(pred)
    prec, rec, f1 = np.zeros(n_classes), np.zeros(n_classes), np.zeros(n_classes)
    for c in range(n_classes):
        tp = int(((pred == c) & (y == c)).sum())
        fp = int(((pred == c) & (y != c)).sum())
        fn = int(((pred != c) & (y == c)).sum())
        prec[c] = tp / (tp + fp) if tp + fp else 0.0
        rec[c] = tp / (tp + fn) if tp + fn else 0.0
        f1[c] = 2 * prec[c] * rec[c] / (prec[c] + rec[c]) if prec[c] + rec[c] else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "macro_f1": float(f1.mean())}
