#!/usr/bin/env python
"""reports/expanded_class_distribution.csv: verified findings per class and source (unique radiographs, never duplicate files),
plus the unlabelled pool and the proposed targets.

    .venv\\Scripts\\python.exe scripts\\dataset\\expansion_report.py

Verified = combined manifests (DENTEX + official validation) + clinician-accepted labels in data/annotation/verified_findings.csv.
Pool rows are counts of radiographs awaiting review; they are NOT findings and carry no class until a clinician confirms one.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsutil import CLASSES, read_csv, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
# Proposed minimum before the cross-validation / context-resolution experiments (see reports/data_expansion_audit.md).
TARGET_TRAIN = {"Periapical Lesion": {"findings": 300, "radiographs": 200}, "Deep Caries": {"findings": 750, "radiographs": 400},
                "Caries": {"findings": None, "radiographs": None}, "Impacted": {"findings": None, "radiographs": None}}


def main():
    rows = []
    for split in ("train", "validation", "calibration", "test"):
        man = read_csv(DATA / f"splits/combined_{split}.csv")
        by = defaultdict(lambda: defaultdict(list))
        for r in man:
            by[r["source_dataset"]][r["target_class"]].append(r["radiograph_group"])
        for src, d in sorted(by.items()):
            for c in CLASSES:
                rows.append({"status": "verified", "split": split, "source": src, "class": c, "findings": len(d[c]),
                             "unique_radiographs_with_class": len(set(d[c])), "note": "original expert labels (DENTEX)"})
    vf = DATA / "annotation/verified_findings.csv"
    ver = read_csv(vf) if vf.is_file() else []
    vb = defaultdict(lambda: defaultdict(list))
    for r in ver:
        vb[(r["split_lock"], r["source_dataset"])][r["label"]].append(r["image_sha256"])
    for (lock, src), d in sorted(vb.items()):
        for c in CLASSES:
            rows.append({"status": "verified (clinician, new)", "split": f"pool:{lock}", "source": src, "class": c, "findings": len(d[c]),
                         "unique_radiographs_with_class": len(set(d[c])), "note": "accepted in data/annotation/clinical_reviews.jsonl"})
    if not ver:
        rows.append({"status": "verified (clinician, new)", "split": "-", "source": "-", "class": "all", "findings": 0,
                     "unique_radiographs_with_class": 0, "note": "no clinician review imported yet"})
    pool = read_csv(DATA / "annotation/annotation_pool.csv")
    for (src, lock), n in sorted(Counter((p["source_dataset"], p["split_lock"]) for p in pool).items()):
        rows.append({"status": "pending review (unlabelled)", "split": f"pool:{lock}", "source": src, "class": "-", "findings": "",
                     "unique_radiographs_with_class": n, "note": "radiographs awaiting clinician review; no labels"})
    # current totals vs targets (training split, verified only)
    tr = read_csv(DATA / "splits/combined_train.csv")
    for c in CLASSES:
        f = [r for r in tr if r["target_class"] == c] + [r for r in ver if r["label"] == c and r["split_lock"] in ("train", "unassigned")]
        n_rad = len({r.get("radiograph_group") or r.get("image_sha256") for r in f})
        t = TARGET_TRAIN[c]
        rows.append({"status": "TARGET (proposed)", "split": "train", "source": "all verified", "class": c, "findings": len(f),
                     "unique_radiographs_with_class": n_rad,
                     "note": (f"target >= {t['findings']} findings from >= {t['radiographs']} radiographs; "
                              f"gap {max(0, t['findings'] - len(f))} findings / {max(0, t['radiographs'] - n_rad)} radiographs")
                     if t["findings"] else "no expansion target; keep all verified labels, do not duplicate"})
    write_csv(ROOT / "reports/expanded_class_distribution.csv", rows,
              ["status", "split", "source", "class", "findings", "unique_radiographs_with_class", "note"])
    print(f"wrote reports/expanded_class_distribution.csv ({len(rows)} rows); clinician-verified new findings: {len(ver)}")


if __name__ == "__main__":
    main()
