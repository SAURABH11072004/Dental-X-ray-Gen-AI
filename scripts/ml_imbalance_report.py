#!/usr/bin/env python
"""Class-imbalance comparison report (validation split only) + post-hoc class-specific decision thresholds.

Reads docs/audit_evidence/ml_improvement/cls/<exp>_s<seed>.json (+ _valprob.npz) written by scripts/ml_cls_train.py and writes
docs/audit_evidence/ml_improvement/imbalance/{report.md, results.json, configs.json, frozen_thresholds.json}.
Never reads calibration or test data.

Decision rules (fixed before the new runs finished; see report):
* a method "improves" macro-F1 only if its paired difference vs the same-code baseline C0r is > 0 in at least 4 of 5 seeds AND
  the mean paired difference exceeds the baseline's seed SD;
* it is "acceptable" only if no class loses more than 0.05 mean F1 and Deep Caries / Periapical Lesion precision does not drop
  by more than 0.10 on average;
* thresholds are fitted on validation and judged by 2-fold cross-fitting grouped by radiograph (repeated 20x); the in-sample
  number is reported but is optimistic by construction and is never called an improvement of the learned model.
"""
import _bootstrap  # noqa: F401
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ml_common import CLASSES, report

D = Path("docs/audit_evidence/ml_improvement")
OUT = D / "imbalance"
BASE = "C0r"
METHODS = [  # (label, experiment id, what changes vs C0; everything else identical)
    ("C0 baseline (original runs)", "C0", "inverse-frequency class weights (cap 5), baseline aug"),
    ("C0r baseline re-run (same code as new runs)", "C0r", "identical to C0; re-run to check reproducibility and save probabilities"),
    ("A weighted sampler", "I_sampler", "sampler p ~ n_c^-0.5, plain cross-entropy (no class weights)"),
    ("B oversampling", "C3b_oversample_baselineaug", "duplicate minority crops to min(3n, sqrt(n_max n)); class weights kept; longer epochs"),
    ("C focal loss", "I_focal", "focal loss gamma 2, no class weights"),
    ("D sqrt class weights", "I_weights_sqrt", "class weights = sqrt(inverse frequency)"),
    ("E minority-only geometric aug", "I_minority_geom", "baseline aug + rotation 5 deg / shift 3% / scale 0.95-1.05 for Deep Caries & Periapical Lesion only"),
    ("ref: no rebalancing", "C_unweighted", "plain cross-entropy, no weights (reference)"),
]
K = ("accuracy", "macro_precision", "macro_recall", "macro_f1", "balanced_accuracy")


def load():
    runs = defaultdict(dict)
    for f in sorted((D / "cls").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        runs[r["exp"]][r["seed"]] = r
    return runs


def flat(r):
    b = r["best_val"]
    m = {"accuracy": b["accuracy"], "macro_f1": b["macro_f1"], "balanced_accuracy": b["balanced_accuracy"],
         "macro_precision": float(np.mean([b["per_class"][c]["precision"] for c in CLASSES])),
         "macro_recall": float(np.mean([b["per_class"][c]["recall"] for c in CLASSES]))}
    for c in CLASSES:
        for k in ("precision", "recall", "f1", "support"):
            m[f"{c}|{k}"] = b["per_class"][c][k]
    m["best_epoch"], m["duration_s"] = r["best_epoch"], r["duration_s"]
    return m


def ms(v):
    v = np.asarray(v, float)
    return float(v.mean()), (float(v.std(ddof=1)) if len(v) > 1 else None)


# ------------------------------------------------------------------------------------------------ thresholds
def predict_w(prob, w):
    return (prob * w).argmax(1)


def macro_f1(y, p):
    return report(y, p)["macro_f1"]


def fit_weights(prob, y, grid=np.exp(np.linspace(np.log(0.25), np.log(4.0), 25)), rounds=3):
    """Class-specific multiplicative weights on the probabilities (Caries fixed at 1), coordinate ascent on macro-F1."""
    w = np.ones(prob.shape[1])
    for _ in range(rounds):
        for c in range(1, prob.shape[1]):
            best, bw = -1, w[c]
            for g in grid:
                w2 = w.copy()
                w2[c] = g
                f = macro_f1(y, predict_w(prob, w2))
                if f > best + 1e-12 or (abs(f - best) <= 1e-12 and abs(np.log(g)) < abs(np.log(bw))):   # tie -> closest to 1
                    best, bw = f, g
            w[c] = bw
    return w


def crossfit(prob, y, groups, reps=20, seed=0):
    """2-fold cross-fitting grouped by radiograph: fit weights on one half, score the other. Returns per-rep macro-F1 and per-class recall/precision."""
    rng = np.random.default_rng(seed)
    ug = np.unique(groups)
    out = []
    for _ in range(reps):
        perm = rng.permutation(ug)
        half = set(perm[: len(ug) // 2])
        a = np.array([g in half for g in groups])
        pred = np.empty(len(y), int)
        for fit_m, ev_m in ((a, ~a), (~a, a)):
            w = fit_weights(prob[fit_m], y[fit_m])
            pred[ev_m] = predict_w(prob[ev_m], w)
        out.append(report(y, pred))
    return out


def threshold_analysis(exp):
    rows = []
    for f in sorted((D / "cls").glob(f"{exp}_s*_valprob.npz")):
        z = np.load(f)
        prob, y, gid = z["prob"], z["y"], z["image_id"]
        seed = int(f.stem.split("_s")[-1].split("_")[0])
        base = report(y, prob.argmax(1))
        w = fit_weights(prob, y)
        ins = report(y, predict_w(prob, w))
        cf = crossfit(prob, y, gid)
        cfm = lambda k: float(np.mean([r[k] for r in cf]))  # noqa: E731
        cfc = lambda c, k: float(np.mean([r["per_class"][c][k] for r in cf]))  # noqa: E731
        curve = []                                   # precision/recall trade-off for the two minority classes, other weights at 1
        for c in (1, 3):
            for g in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0):
                ww = np.ones(4)
                ww[c] = g
                rr = report(y, predict_w(prob, ww))
                curve.append({"class": CLASSES[c], "weight": g, "precision": rr["per_class"][CLASSES[c]]["precision"],
                              "recall": rr["per_class"][CLASSES[c]]["recall"], "macro_f1": rr["macro_f1"]})
        rows.append({"seed": seed, "weights_fit_on_full_val": w.round(4).tolist(), "argmax": _brief(base), "in_sample_tuned": _brief(ins),
                     "crossfit_mean": {"macro_f1": cfm("macro_f1"), "balanced_accuracy": cfm("balanced_accuracy"),
                                       **{f"{c}|{k}": cfc(c, k) for c in CLASSES for k in ("precision", "recall", "f1")}},
                     "crossfit_reps": len(cf), "tradeoff": curve})
    return rows


def _brief(r):
    return {"macro_f1": r["macro_f1"], "balanced_accuracy": r["balanced_accuracy"], "accuracy": r["accuracy"],
            **{f"{c}|{k}": r["per_class"][c][k] for c in CLASSES for k in ("precision", "recall", "f1")}}


# ------------------------------------------------------------------------------------------------ main
def main():
    runs = load()
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"generated": datetime.now(timezone.utc).isoformat(), "split": "validation (331 crops; supports 205/45/72/9)",
           "protocol": "ResNet-50 ImageNet, 15 epochs, batch 32, AdamW lr 3e-4 wd 1e-4, cosine; best epoch by validation macro-F1; seeds 42-46; "
                       "only the listed factor differs from C0. Validation is used for epoch selection AND reporting (same optimistic bias for every method).",
           "sd": "sample SD (ddof=1) across seeds; the earlier cls_summary.md used population SD (ddof=0)",
           "methods": {}, "not_run": [], "reproducibility": None}
    base = runs.get(BASE, {})
    base_sd = ms([flat(r)["macro_f1"] for r in base.values()])[1] if len(base) > 1 else None
    for label, exp, change in METHODS:
        rr = runs.get(exp, {})
        if not rr:
            res["not_run"].append({"method": label, "exp": exp})
            continue
        per = {s: flat(r) for s, r in sorted(rr.items())}
        keys = list(next(iter(per.values())))
        agg = {k: ms([m[k] for m in per.values()]) for k in keys}
        paired = {}
        if base and exp != BASE:
            common = sorted(set(per) & set(base))
            for k in ("macro_f1", "balanced_accuracy", "accuracy") + tuple(f"{c}|{x}" for c in CLASSES for x in ("precision", "recall", "f1")):
                d = [per[s][k] - flat(base[s])[k] for s in common]
                paired[k] = {"mean": float(np.mean(d)), "min": float(min(d)), "max": float(max(d)), "n_positive": int(sum(x > 0 for x in d)), "n": len(d)}
        verdict = None
        if paired:
            pf = paired["macro_f1"]
            improves = pf["n_positive"] >= 4 and pf["n"] >= 5 and base_sd is not None and pf["mean"] > base_sd
            worst_class = min(paired[f"{c}|f1"]["mean"] for c in CLASSES)
            prec_drop = min(paired["Deep Caries|precision"]["mean"], paired["Periapical Lesion|precision"]["mean"])
            acceptable = worst_class >= -0.05 and prec_drop >= -0.10
            verdict = {"improves_macro_f1": bool(improves), "acceptable_side_effects": bool(acceptable),
                       "worst_class_mean_f1_change": worst_class, "minority_precision_change_min": prec_drop,
                       "supported": bool(improves and acceptable)}
        cfg = next(iter(rr.values()))["config"]
        res["methods"][exp] = {"label": label, "change_vs_C0": change, "seeds": sorted(per), "per_seed": per, "aggregate": agg,
                               "paired_vs_C0r": paired, "verdict": verdict, "config": cfg,
                               "inputs": next(iter(rr.values())).get("inputs"),
                               "duration_s_total": float(sum(m["duration_s"] for m in per.values()))}
    # reproducibility: C0 (original) vs C0r (re-run) per seed
    if "C0" in runs and base:
        res["reproducibility"] = [{"seed": s, "C0_macro_f1": runs["C0"][s]["best_val"]["macro_f1"], "C0r_macro_f1": base[s]["best_val"]["macro_f1"],
                                   "C0_best_epoch": runs["C0"][s]["best_epoch"], "C0r_best_epoch": base[s]["best_epoch"],
                                   "identical_confusion": runs["C0"][s]["best_val"]["confusion"] == base[s]["best_val"]["confusion"]}
                                  for s in sorted(set(runs["C0"]) & set(base))]
    # thresholds: baseline + every supported method (decided by the rule above, not by eye)
    supported = [e for e, m in res["methods"].items() if (m.get("verdict") or {}).get("supported")]
    res["supported_methods"] = supported
    res["thresholds"] = {e: threshold_analysis(e) for e in [BASE] + supported if any((D / "cls").glob(f"{e}_s*_valprob.npz"))}
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (OUT / "configs.json").write_text(json.dumps({e: {"config": m["config"], "inputs": m["inputs"], "change_vs_C0": m["change_vs_C0"]}
                                                  for e, m in res["methods"].items()}, indent=1), encoding="utf-8")
    print(json.dumps({"supported": supported, "not_run": res["not_run"]}, indent=1))


if __name__ == "__main__":
    main()
