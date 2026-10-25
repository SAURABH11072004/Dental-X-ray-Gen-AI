#!/usr/bin/env python
"""P4 (approved with review gate, 2026-10-16): DRAFT grouped 5-fold assignment for future experiments. Nothing runs from this file
until the owner has reviewed and approved the exact assignment.

    .venv\\Scripts\\python.exe scripts\\dataset\\make_cv_folds.py

* Units are radiograph groups (all crops of one radiograph are in one fold): data/splits/combined_train.csv + combined_validation.csv.
  The frozen test split and the calibration split are excluded.
* Stratified by (source family, has Periapical Lesion, has Deep Caries); within a stratum, groups are taken in a seeded random order
  and given to the fold with the fewest groups of that stratum (ties: fewest findings, then lowest fold number).
* Writes data/splits/cv5_folds_DRAFT.csv and reports/cv5_fold_draft_summary.md (per-fold radiographs and findings per class / source).
  Adding verified labels changes the input, so the draft must be regenerated and reviewed again.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsutil import CLASSES, read_csv, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
K, SEED = 5, 42


def assign_folds(rows, k=K, seed=SEED, with_impacted=False):
    """rows: manifest rows -> {radiograph_group: fold}. with_impacted=True adds "has Impacted" to the stratum (option B of
    reports/cv5_fold_alternative_comparison.md, approved by the owner on 2026-10-24); False reproduces the reviewed draft."""
    g = defaultdict(list)
    for r in rows:
        g[r["radiograph_group"]].append(r)
    def stratum(rs):
        src = rs[0]["source_dataset"].split(":")[0]
        cls = {r["target_class"] for r in rs}
        key = (src, "Periapical Lesion" in cls, "Deep Caries" in cls)
        return key + ("Impacted" in cls,) if with_impacted else key
    strata = defaultdict(list)
    for gid, rs in g.items():
        strata[stratum(rs)].append(gid)
    fold_of, per_stratum, findings = {}, defaultdict(Counter), Counter()
    rng = random.Random(seed)
    for key in sorted(strata, key=str):
        gids = sorted(strata[key])
        rng.shuffle(gids)
        for gid in gids:
            f = min(range(k), key=lambda i: (per_stratum[key][i], findings[i], i))
            fold_of[gid] = f
            per_stratum[key][f] += 1
            findings[f] += len(g[gid])
    return fold_of


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--approved-v1", action="store_true",
                    help="write the owner-approved assignment (option B, Impacted-stratified) to data/splits/cv5_folds_v1.csv")
    a = ap.parse_args()
    rows = read_csv(DATA / "splits/combined_train.csv") + read_csv(DATA / "splits/combined_validation.csv")
    test_groups = {r["radiograph_group"] for r in read_csv(DATA / "splits/combined_test.csv") + read_csv(DATA / "splits/combined_calibration.csv")}
    assert not ({r["radiograph_group"] for r in rows} & test_groups), "test / calibration radiograph in the CV pool"
    fold_of = assign_folds(rows, with_impacted=a.approved_v1)
    out = []
    for gid in sorted(fold_of):
        rs = [r for r in rows if r["radiograph_group"] == gid]
        c = Counter(r["target_class"] for r in rs)
        out.append({"radiograph_group": gid, "fold": fold_of[gid], "source": rs[0]["source_dataset"],
                    "original_split": rs[0]["split"], "n_findings": len(rs), **{c_.replace(" ", "_"): c[c_] for c_ in CLASSES}})
    p = DATA / ("splits/cv5_folds_v1.csv" if a.approved_v1 else "splits/cv5_folds_DRAFT.csv")
    write_csv(p, out)
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    title = ("# APPROVED grouped 5-fold assignment v1 (P4, option B: Impacted-stratified; owner approval 2026-10-24)" if a.approved_v1
             else "# DRAFT grouped 5-fold assignment (P4): FOR REVIEW, NOT APPROVED, NOT USED")
    lines = [title, "",
             f"File `data/splits/{p.name}`, SHA-256 `{sha}`, seed {SEED}. Units: radiograph groups of combined_train + "
             "combined_validation; test and calibration excluded (checked: no overlap).", "",
             "| Fold | Radiographs | Findings | Caries | Deep Caries | Impacted | Periapical Lesion | PL radiographs | DC radiographs | from old val split |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for f in range(K):
        fr = [o for o in out if o["fold"] == f]
        lines.append(f"| {f} | {len(fr)} | {sum(o['n_findings'] for o in fr)} | " + " | ".join(str(sum(o[c.replace(' ', '_')] for o in fr)) for c in CLASSES)
                     + f" | {sum(1 for o in fr if o['Periapical_Lesion'])} | {sum(1 for o in fr if o['Deep_Caries'])}"
                     + f" | {sum(1 for o in fr if o['original_split'] == 'validation')} |")
    src = Counter((o["fold"], o["source"]) for o in out)
    lines += ["", "Radiographs per fold and source: " + "; ".join(f"fold {f}: " + ", ".join(f"{s} {n}" for (ff, s), n in sorted(src.items()) if ff == f)
                                                        for f in range(K)),
              "", "Review points: (1) every fold has Periapical Lesion radiographs; (2) source mix per fold; (3) the old validation "
              "radiographs are spread over folds (they are trained on in 4 of 5 folds); (4) after clinician-verified labels are added, this "
              "draft is regenerated and needs a new review."]
    (ROOT / ("reports/cv5_folds_v1_summary.md" if a.approved_v1 else "reports/cv5_fold_draft_summary.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
