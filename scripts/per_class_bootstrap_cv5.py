#!/usr/bin/env python
"""Per-class radiograph-bootstrap intervals for CV5-BASE run 1, from the ARCHIVED out-of-fold predictions.

    .venv\\Scripts\\python.exe scripts\\per_class_bootstrap_cv5.py

Post-hoc DESCRIPTIVE analysis of the BASE reference only (no candidate, no test split, not an acceptance criterion).
* Input: kaggle/artifacts_cv5_run1/oof_predictions.csv and cv5_results.json, both checked against the run's SHA256SUMS.txt.
* Method: the exact resampling of kaggle/cv5_lib.cluster_bootstrap (radiograph groups, numpy default_rng(0), 2,000 draws, seed-mean
  statistic, 2.5 / 97.5 percentiles), applied to per-class precision, recall and F1 on the same draws.
* Validation gate: the recomputed macro-F1 point estimates and 95 % intervals must equal the archived ones (bootstrap/{gt,det_matched})
  to 1e-9, or the script stops and writes nothing.
Outputs reports/cv5_per_class_bootstrap.json and .md (never overwritten).
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "kaggle" / "artifacts_cv5_run1"
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
SEEDS = [42, 43, 44, 45, 46]
N_BOOT, BOOT_SEED = 2000, 0


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(rel: str) -> str:
    sums = {}
    for line in (ART / "SHA256SUMS.txt").read_text().splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*").replace("\\", "/")] = h
    h = sha(ART / rel)
    if sums.get(rel) != h:
        raise SystemExit(f"{rel} does not match SHA256SUMS.txt")
    return h


def per_class(y, pred, n=len(CLASSES)):
    cm = np.bincount(y * n + pred, minlength=n * n).reshape(n, n)
    tp, pp, sup = np.diag(cm), cm.sum(0), cm.sum(1)
    prec = np.divide(tp, pp, out=np.zeros(n), where=pp > 0)
    rec = np.divide(tp, sup, out=np.zeros(n), where=sup > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(n), where=(prec + rec) > 0)
    return prec, rec, f1


def load():
    rows = list(csv.DictReader(open(ART / "oof_predictions.csv", encoding="utf-8")))
    y = np.array([CLASSES.index(r["true_class"]) for r in rows])
    groups = np.array([r["radiograph_group"] for r in rows])
    matched = np.array([r["detector_matched"] == "True" for r in rows])
    preds = {}
    for st, col in (("gt", "gt"), ("det_matched", "det")):
        preds[st] = []
        for s in SEEDS:
            p = np.array([[float(r[f"s{s}_{col}_{c}"]) if r[f"s{s}_{col}_{c}"] not in ("", "nan") else np.nan for c in CLASSES]
                          for r in rows])
            preds[st].append(np.nan_to_num(p, nan=0).argmax(1))
    return y, groups, matched, preds


def run(y, groups, valid, preds):
    """Same draws as cv5_lib.cluster_bootstrap; returns stats of shape (n_boot, 4 metrics(macro, prec, rec, f1) ...)."""
    uniq = np.unique(groups)
    members = {g: np.flatnonzero(groups == g) for g in uniq}
    rng = np.random.default_rng(BOOT_SEED)
    macro, prec, rec, f1 = np.empty(N_BOOT), np.empty((N_BOOT, 4)), np.empty((N_BOOT, 4)), np.empty((N_BOOT, 4))
    for b in range(N_BOOT):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        i = np.concatenate([members[g] for g in pick])
        i = i[valid[i]]
        res = [per_class(y[i], p[i]) for p in preds]
        prec[b], rec[b], f1[b] = (np.mean([r[k] for r in res], 0) for k in range(3))
        macro[b] = np.mean([r[2].mean() for r in res])
    pt = [per_class(y[valid], p[valid]) for p in preds]
    point = {"macro_f1": float(np.mean([r[2].mean() for r in pt]))}
    for k, name in enumerate(("precision", "recall", "f1")):
        point[name] = np.mean([r[k] for r in pt], 0)
    ci = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    out = {"n_radiographs": int(len(uniq)), "n_findings": int(valid.sum()),
           "macro_f1": {"point": point["macro_f1"], "ci95": ci(macro)}, "per_class": {}}
    for j, c in enumerate(CLASSES):
        out["per_class"][c] = {name: {"point": float(point[name][j]), "ci95": ci(arr[:, j])}
                               for name, arr in (("precision", prec), ("recall", rec), ("f1", f1))}
    return out


def main():
    out_j, out_m = ROOT / "reports" / "cv5_per_class_bootstrap.json", ROOT / "reports" / "cv5_per_class_bootstrap.md"
    if out_j.exists() or out_m.exists():
        raise SystemExit("cv5_per_class_bootstrap.* exists: write a new version instead of overwriting")
    h_oof, h_res = check("oof_predictions.csv"), check("cv5_results.json")
    archived = json.loads((ART / "cv5_results.json").read_text(encoding="utf-8"))
    y, groups, matched, preds = load()
    result = {}
    for st, valid in (("gt", np.ones(len(y), bool)), ("det_matched", matched)):
        r = run(y, groups, valid, preds[st])
        a = archived["bootstrap"][st]
        if abs(r["macro_f1"]["point"] - a["point"]) > 1e-9 or any(abs(u - v) > 1e-9 for u, v in zip(r["macro_f1"]["ci95"], a["ci95"])):
            raise SystemExit(f"{st}: recomputed macro-F1 {r['macro_f1']} does not reproduce the archived {a} - nothing written")
        for c in CLASSES:
            for m in ("precision", "recall", "f1"):
                arch = archived["summary"][st]["per_class"][c][m]["mean"]
                if abs(r["per_class"][c][m]["point"] - arch) > 1e-9:
                    raise SystemExit(f"{st} {c} {m}: point {r['per_class'][c][m]['point']} != archived {arch} - nothing written")
        r["reproduces_archived_macro_f1_bootstrap"] = True
        result[st] = r
    t = {"format": "dentamind-cv5-per-class-bootstrap-v1", "status": "post-hoc descriptive analysis of the BASE reference; not an "
         "acceptance criterion; no candidate and no test data involved", "script_sha256": sha(Path(__file__)),
         "inputs": {"kaggle/artifacts_cv5_run1/oof_predictions.csv": h_oof, "kaggle/artifacts_cv5_run1/cv5_results.json": h_res},
         "method": {"unit": "radiograph group", "n_boot": N_BOOT, "rng": f"numpy default_rng({BOOT_SEED})", "statistic": "mean over "
                    "seeds 42-46", "interval": "percentile 2.5 / 97.5", "same_draws_as": "kaggle/cv5_lib.cluster_bootstrap"},
         "results": result}
    with open(out_j, "x", encoding="utf-8") as fh:
        json.dump(t, fh, indent=1)
    lines = ["# CV5-BASE run 1: per-class radiograph-bootstrap 95 % intervals (post-hoc, descriptive)", "",
             f"Script `scripts/per_class_bootstrap_cv5.py` (sha256 `{t['script_sha256']}`). Inputs checked against SHA256SUMS.txt: "
             f"`oof_predictions.csv` `{h_oof}`, `cv5_results.json` `{h_res}`. The recomputation reproduces the archived macro-F1 point "
             "estimates and intervals exactly, and the archived per-class seed means.", "",
             "| Setting | Class | Precision (95 % CI) | Recall (95 % CI) | F1 (95 % CI) |", "|---|---|---|---|---|"]
    for st, r in result.items():
        for c in CLASSES:
            v = r["per_class"][c]
            cell = lambda m: f"{v[m]['point']:.3f} ({v[m]['ci95'][0]:.3f}–{v[m]['ci95'][1]:.3f})"
            lines.append(f"| {st} | {c} | {cell('precision')} | {cell('recall')} | {cell('f1')} |")
    with open(out_m, "x", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines[4:]))


if __name__ == "__main__":
    main()
