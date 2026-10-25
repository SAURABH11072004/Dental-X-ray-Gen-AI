"""BASE-vs-BASE noise analysis on the completed CV5-BASE out-of-fold predictions (descriptive input for the acceptance proposal).

Reads only ``kaggle/artifacts_cv5_run1/oof_predictions.csv`` (SHA-256 checked against the run's SHA256SUMS.txt) and writes
``reports/cv5_base_noise.json``. Every model compared here is BASE: differences between seeds are what an identical recipe produces
by chance, on identical held-out radiographs. No candidate, no test image, no new training.

    .venv/Scripts/python.exe scripts/cv5_base_noise.py
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "kaggle" / "artifacts_cv5_run1"
OUT = ROOT / "reports" / "cv5_base_noise.json"
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
SEEDS = [42, 43, 44, 45, 46]
N_BOOT, BOOT_SEED = 2000, 0


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_input() -> Path:
    p = ART / "oof_predictions.csv"
    sums = {}
    for line in (ART / "SHA256SUMS.txt").read_text().splitlines():
        h, name = line.split(maxsplit=1)
        sums[name.lstrip("*").replace("\\", "/")] = h
    if sums.get("oof_predictions.csv") != sha256(p):
        raise SystemExit("oof_predictions.csv does not match SHA256SUMS.txt")
    return p


def load(p: Path):
    rows = list(csv.DictReader(p.open(newline="")))
    y = np.array([CLASSES.index(r["true_class"]) for r in rows])
    groups = np.array([r["radiograph_group"] for r in rows])
    folds = np.array([int(r["fold"]) for r in rows])
    matched = np.array([r["detector_matched"] == "True" for r in rows])
    pred = {}
    for s in SEEDS:
        for st in ("gt", "det"):
            cols = [f"s{s}_{st}_{c}" for c in CLASSES]
            prob = np.array([[float(r[c]) if r[c] not in ("", "nan") else np.nan for c in cols] for r in rows])
            pred[(s, st)] = np.nan_to_num(prob, nan=-1).argmax(1)
    return y, groups, folds, matched, pred


def per_class(y, p, n=len(CLASSES)):
    cm = np.bincount(y * n + p, minlength=n * n).reshape(n, n)
    tp, pp, sup = np.diag(cm), cm.sum(0), cm.sum(1)
    prec = np.divide(tp, pp, out=np.zeros(n), where=pp > 0)
    rec = np.divide(tp, sup, out=np.zeros(n), where=sup > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(n), where=(prec + rec) > 0)
    return prec, rec, f1


def metrics(y, p) -> dict:
    prec, rec, f1 = per_class(y, p)
    d = {"macro_f1": float(f1.mean())}
    for k, c in enumerate(CLASSES):
        d[f"{c}|precision"], d[f"{c}|recall"], d[f"{c}|f1"] = float(prec[k]), float(rec[k]), float(f1[k])
    return d


def summary(vals) -> dict:
    a = np.abs(np.asarray(vals, float))
    return {"n": int(len(a)), "mean_abs": float(a.mean()), "max_abs": float(a.max()), "sd_signed": float(np.std(vals, ddof=1))}


def main():
    y, groups, folds, matched, pred = load(check_input())
    pairs = list(itertools.combinations(SEEDS, 2))
    out = {"source": "kaggle/artifacts_cv5_run1/oof_predictions.csv", "source_sha256": sha256(ART / "oof_predictions.csv"),
           "note": "All comparisons are BASE seed vs BASE seed on identical out-of-fold findings. Descriptive only.",
           "seed_pairs": [list(p) for p in pairs], "settings": {}}
    uniq = np.unique(groups)
    members = {g: np.flatnonzero(groups == g) for g in uniq}
    rng = np.random.default_rng(BOOT_SEED)
    picks = [np.concatenate([members[g] for g in rng.choice(uniq, size=len(uniq), replace=True)]) for _ in range(N_BOOT)]

    for st, mask in (("det_matched", matched), ("gt", np.ones(len(y), bool))):
        key = "det" if st == "det_matched" else "gt"
        m = {s: metrics(y[mask], pred[(s, key)][mask]) for s in SEEDS}
        names = list(m[SEEDS[0]])
        # A. pooled out-of-fold, pairwise seed differences
        pooled = {n: summary([m[b][n] - m[a][n] for a, b in pairs]) for n in names}
        # B. fold-level paired differences (5 folds x 10 pairs)
        fold_d = []
        for f in range(5):
            i = mask & (folds == f)
            for a, b in pairs:
                fold_d.append(metrics(y[i], pred[(b, key)][i])["macro_f1"] - metrics(y[i], pred[(a, key)][i])["macro_f1"])
        # C. 2-seed mean vs the other 3 seeds' mean (10 splits): how far two BASE "arms" of unequal size drift apart
        split_d = {n: [] for n in names}
        for two in pairs:
            rest = [s for s in SEEDS if s not in two]
            for n in names:
                split_d[n].append(np.mean([m[s][n] for s in two]) - np.mean([m[s][n] for s in rest]))
        # D. paired radiograph bootstrap of single-seed differences: SD of the paired difference per seed pair
        boot_sd = {n: [] for n in ("macro_f1", "Deep Caries|recall", "Periapical Lesion|recall")}
        for a, b in pairs:
            vals = {n: np.empty(N_BOOT) for n in boot_sd}
            for k, i in enumerate(picks):
                i = i[mask[i]]
                ma, mb = metrics(y[i], pred[(a, key)][i]), metrics(y[i], pred[(b, key)][i])
                for n in boot_sd:
                    vals[n][k] = mb[n] - ma[n]
            for n in boot_sd:
                boot_sd[n].append(float(vals[n].std(ddof=1)))
        out["settings"][st] = {
            "findings": int(mask.sum()),
            "per_seed": {str(s): m[s] for s in SEEDS},
            "A_pooled_pairwise_seed_differences": pooled,
            "B_fold_level_pairwise_macro_f1_differences": summary(fold_d),
            "C_two_vs_three_seed_mean_differences": {n: summary(v) for n, v in split_d.items()},
            "D_paired_radiograph_bootstrap_sd_of_single_seed_difference": {
                n: {"median_over_pairs": float(np.median(v)), "max_over_pairs": float(np.max(v))} for n, v in boot_sd.items()},
        }
    out["class_counts"] = {c: int((y == k).sum()) for k, c in enumerate(CLASSES)}
    out["class_counts_detector_matched"] = {c: int(((y == k) & matched).sum()) for k, c in enumerate(CLASSES)}
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
