#!/usr/bin/env python
"""reports/imbalance_experiment_results.csv: one table holding every MEASURED imbalance result plus the planned Kaggle runs.

    .venv\\Scripts\\python.exe scripts\\dataset\\write_results_tables.py [--kaggle checkpoints\\kaggle_candidates\\<sha8>]

Rows with status "measured" come from existing result files (no number is typed in by hand). Kaggle rows stay "pending" until a
verified Kaggle archive has been staged (kaggle/stage_kaggle_candidates.py); then its per-experiment table is merged in.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsutil import read_csv, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "docs/audit_evidence/ml_improvement/imbalance/results.json"
STRATEGY = {"C0": "baseline (original runs)", "C0r": "baseline re-run", "C_unweighted": "reference: no rebalancing",
            "I_weights_sqrt": "A: class weights (sqrt)", "I_sampler": "B: weighted sampler", "I_focal": "C: focal loss",
            "C3b_oversample_baselineaug": "oversampling (duplicate minority crops)", "I_minority_geom": "E-aug: minority-only geometric aug"}
PLANNED = ["BASE", "REF_unweighted", "A1_sqrt_weights", "A2_effnum_weights", "B_sampler", "C_focal", "D_official_val", "E (if justified)"]
C = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]


def local_rows():
    d = json.loads(LOCAL.read_text(encoding="utf-8"))
    out = []
    for exp, m in d["methods"].items():
        a = m["aggregate"]
        g = lambda k: round(a[k][0], 4) if k in a else None  # noqa: E731
        s = lambda k: round(a[k][1], 4) if k in a else None  # noqa: E731
        pv = (m.get("paired_vs_C0r") or {}).get("macro_f1") or {}
        r = {"status": "measured", "result_source": "docs/audit_evidence/ml_improvement/imbalance/results.json (local RTX 3050, 2026-10-15)",
             "experiment": exp, "strategy": STRATEGY.get(exp, m.get("label")), "change_vs_baseline": m.get("change_vs_C0"),
             "train_data": "DENTEX disease subset, project train split", "eval_split": "validation (project)", "eval_setting": "GT boxes",
             "n_seeds": len(m.get("seeds", [])), "accuracy_mean": g("accuracy"), "accuracy_sd": s("accuracy"),
             "macro_precision_mean": g("macro_precision"), "macro_recall_mean": g("macro_recall"),
             "macro_f1_mean": g("macro_f1"), "macro_f1_sd": s("macro_f1"), "balanced_accuracy_mean": g("balanced_accuracy"),
             "paired_macro_f1_gain_vs_C0r": round(pv["mean"], 4) if isinstance(pv, dict) and "mean" in pv else None,
             "verdict": m.get("verdict") if isinstance(m.get("verdict"), str) else json.dumps(m.get("verdict"))}
        for c in C:
            for k in ("precision", "recall", "f1"):
                r[f"{c} {k}"] = g(f"{c}|{k}")
        out.append(r)
    return out


def pending_rows():
    return [{"status": "pending (Kaggle run not executed yet)", "result_source": "kaggle/denta_mind_training.ipynb", "experiment": e,
             "train_data": "combined_train (DENTEX" + (" + official validation)" if e.startswith(("D_", "E")) else ")"),
             "eval_split": "validation (project); test only for BASE + passing candidates",
             "eval_setting": "GT boxes and production-detector boxes", "n_seeds": 5} for e in PLANNED]


def kaggle_rows(folder: Path):
    rows = read_csv(folder / "imbalance_experiment_results.csv")
    for r in rows:
        r["status"] = "measured (Kaggle)"
        r["result_source"] = str(folder.relative_to(ROOT) / "imbalance_experiment_results.csv")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kaggle", help="staged archive folder under checkpoints/kaggle_candidates/")
    a = ap.parse_args()
    rows = local_rows() + (kaggle_rows(ROOT / a.kaggle) if a.kaggle else pending_rows())
    fields = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    write_csv(ROOT / "reports/imbalance_experiment_results.csv", rows, fields)
    print(f"wrote reports/imbalance_experiment_results.csv ({len(rows)} rows)")


if __name__ == "__main__":
    main()
