"""Abstention rules for the finding classifier, used by the OFFLINE abstention experiment
(scripts/abstention_threshold_experiment.py).

The production rule lives in backend/services/pipeline.py and is NOT changed by this module:
    normalised entropy H(p) = -sum_k p_k ln p_k / ln K   (K = 4)
    abstain  <=>  H(p) >= normalised_entropy_ge          (Data/reports/uncertainty_thresholds.json, 0.39660 today)
``Rule("entropy", t)`` reproduces it exactly; tests/test_abstention_rules.py checks that against PipelineService.run.

Other rule families evaluated offline (never deployed without approval):
    "max_prob": abstain <=> max_k p_k  <  t
    "margin":   abstain <=> p_(1) - p_(2) < t      (top-two margin)
Every rule returns either the argmax class (accepted) or None (abstained). There is no "healthy" outcome: an abstention
means "no reliable class candidate", never "no finding".
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dentexmodel.uncertainty.measures import entropy

FAMILIES = ("entropy", "max_prob", "margin")


@dataclass(frozen=True)
class Rule:
    family: str
    threshold: float

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"unknown rule family '{self.family}'; use one of {FAMILIES}")

    @property
    def name(self) -> str:
        op = {"entropy": "H >=", "max_prob": "max p <", "margin": "p1-p2 <"}[self.family]
        return f"abstain if {op} {self.threshold:.4f}"


def _probs(p) -> np.ndarray:
    a = np.asarray(p, dtype=np.float64)
    if a.ndim != 1 or a.size < 2 or not np.all(np.isfinite(a)) or np.any(a < -1e-9) or abs(a.sum() - 1.0) > 1e-4:
        raise ValueError(f"invalid probability vector: {p!r}")
    return a


def abstains(p, rule: Rule) -> bool:
    """True if ``rule`` withholds a class for probability vector ``p``. Raises ValueError for an invalid vector."""
    a = _probs(p)
    if rule.family == "entropy":
        return bool(float(entropy(a)) >= rule.threshold)          # same function and operator as the pipeline
    if rule.family == "max_prob":
        return bool(a.max() < rule.threshold)
    top2 = np.sort(a)[-2:]
    return bool(top2[1] - top2[0] < rule.threshold)


def decide(p, rule: Rule):
    """Class index if accepted, None if abstained. ``p is None`` (no classifier output, e.g. crop too small) -> 'missing'."""
    if p is None:
        return "missing"
    return None if abstains(p, rule) else int(np.argmax(_probs(p)))


def selective_metrics(y_true: list, probs: list, rule: Rule, names: list) -> dict:
    """Metrics of a selective classifier on crops that HAVE a ground-truth finding label.

    * coverage = accepted / (accepted + abstained); missing predictions are counted separately and never as correct.
    * risk = error rate among accepted crops.
    * per class: precision on accepted predictions; 'accepted_recall' = correct / accepted crops of that class;
      'recall_all' = correct / ALL crops of that class (an abstention counts as a miss, so this is the end-to-end view).
    * fp_c = accepted crops predicted c whose label is not c; fn_c = crops of class c not correctly accepted
      (wrong class, abstained or missing).
    """
    K = len(names)
    decisions = [decide(p, rule) for p in probs]
    cm = np.zeros((K, K + 2), int)                       # columns: predicted classes, ABSTAINED, MISSING
    for y, d in zip(y_true, decisions):
        col = K + 1 if d == "missing" else (K if d is None else d)
        cm[y, col] += 1
    n = len(y_true)
    acc_n = int(cm[:, :K].sum())
    abst = int(cm[:, K].sum())
    miss = int(cm[:, K + 1].sum())
    correct = int(np.trace(cm[:, :K]))
    per, f1s, f1_all, precs, recs = {}, [], [], [], []
    for k, c in enumerate(names):
        support = int(cm[k].sum())
        pred_k = int(cm[:, k].sum())
        tp = int(cm[k, k])
        prec = tp / pred_k if pred_k else None
        rec_acc = tp / int(cm[k, :K].sum()) if cm[k, :K].sum() else None
        rec_all = tp / support if support else None
        f1 = (2 * prec * rec_acc / (prec + rec_acc)) if prec and rec_acc else (0.0 if prec is not None and rec_acc is not None else None)
        f1a = (2 * prec * rec_all / (prec + rec_all)) if prec and rec_all else (0.0 if prec is not None and rec_all is not None else None)
        per[c] = {"support": support, "accepted": int(cm[k, :K].sum()), "abstained": int(cm[k, K]), "missing": int(cm[k, K + 1]),
                  "predicted": pred_k, "tp": tp, "fp": pred_k - tp, "fn": support - tp, "precision": prec,
                  "recall_accepted": rec_acc, "f1_accepted": f1, "recall_all": rec_all, "f1_all": f1a}
        if support:
            f1s.append(f1 if f1 is not None else 0.0)
            f1_all.append(f1a if f1a is not None else 0.0)
            precs.append(prec if prec is not None else 0.0)
            recs.append(rec_all)
    return {"rule": {"family": rule.family, "threshold": rule.threshold, "name": rule.name}, "n": n,
            "accepted": acc_n, "abstained": abst, "missing": miss,
            "coverage": acc_n / (acc_n + abst) if acc_n + abst else None,
            "abstention_rate": abst / (acc_n + abst) if acc_n + abst else None,
            "risk": (acc_n - correct) / acc_n if acc_n else None, "accuracy_accepted": correct / acc_n if acc_n else None,
            "macro_precision": float(np.mean(precs)) if precs else None, "macro_recall_all": float(np.mean(recs)) if recs else None,
            "macro_f1_accepted": float(np.mean(f1s)) if f1s else None, "macro_f1_all": float(np.mean(f1_all)) if f1_all else None,
            "per_class": per, "confusion": cm.tolist(), "confusion_columns": list(names) + ["ABSTAINED", "MISSING"]}


def acceptance_rate(probs: list, rule: Rule, names: list) -> dict:
    """For crops WITHOUT a finding label: how often the rule names a class, and which. These are NOT counted as false
    positives (DENTEX does not label healthy teeth; an unlabelled tooth is not known to be healthy)."""
    d = [decide(p, rule) for p in probs]
    named = [x for x in d if x not in (None, "missing")]
    return {"n": len(d), "named": len(named), "abstained": sum(1 for x in d if x is None), "missing": sum(1 for x in d if x == "missing"),
            "named_rate": len(named) / max(1, sum(1 for x in d if x != "missing")),
            "named_by_class": {names[k]: sum(1 for x in named if x == k) for k in range(len(names))}}
