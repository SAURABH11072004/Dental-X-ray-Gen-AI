#!/usr/bin/env python
"""Aggregate classification (and segmentation) experiment JSONs into a markdown table: mean +- sd over seeds, paired by seed vs C0."""
import _bootstrap  # noqa: F401
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

D = Path("docs/audit_evidence/ml_improvement")


def cls_table():
    runs = defaultdict(dict)
    for f in sorted((D / "cls").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        runs[r["exp"]][r["seed"]] = r
    base = runs.get("C0", {})
    lines = ["| Exp | seeds | val macro-F1 | acc | balanced acc | weighted F1 | Caries F1 | Deep Caries F1 | Impacted F1 | Periapical F1 | PL recall | val NLL | paired dF1 vs C0 (mean, min..max) | best-epoch (median) | s/run |",
             "|---|---:|---|---|---|---|---|---|---|---|---|---|---|---:|---:|"]
    summ = {}
    for exp, rr in sorted(runs.items()):
        def col(fn):
            v = np.array([fn(r) for r in rr.values()], float)
            return f"{v.mean():.3f} +- {v.std():.3f}"
        f1 = {s: r["best_val"]["macro_f1"] for s, r in rr.items()}
        d = [f1[s] - base[s]["best_val"]["macro_f1"] for s in f1 if s in base]
        dtxt = f"{np.mean(d):+.3f} ({min(d):+.3f}..{max(d):+.3f})" if d and exp != "C0" else "-"
        pc = lambda c: (lambda r: r["best_val"]["per_class"][c]["f1"])  # noqa: E731
        lines.append(f"| {exp} | {len(rr)} | {col(lambda r: r['best_val']['macro_f1'])} | {col(lambda r: r['best_val']['accuracy'])} | {col(lambda r: r['best_val']['balanced_accuracy'])} | "
                     f"{col(lambda r: r['best_val']['weighted_f1'])} | {col(pc('Caries'))} | {col(pc('Deep Caries'))} | {col(pc('Impacted'))} | {col(pc('Periapical Lesion'))} | "
                     f"{col(lambda r: r['best_val']['minority_recall_periapical'])} | {col(lambda r: r['best_val']['nll'])} | {dtxt} | "
                     f"{int(np.median([r['best_epoch'] for r in rr.values()]))} | {int(np.mean([r['duration_s'] for r in rr.values()]))} |")
        summ[exp] = {"n": len(rr), "macro_f1_mean": float(np.mean(list(f1.values()))), "macro_f1_sd": float(np.std(list(f1.values())))}
    return "\n".join(lines), summ


if __name__ == "__main__":
    t, s = cls_table()
    print(t)
    (D / "cls_summary.md").write_text(t + "\n", encoding="utf-8")
    (D / "cls_summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
