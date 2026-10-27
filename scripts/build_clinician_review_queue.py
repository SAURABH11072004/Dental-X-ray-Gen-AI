#!/usr/bin/env python
"""Blinded clinician re-reading queue for the Caries / Deep Caries findings consistently confused by all 5 BASE seeds.

    .venv\\Scripts\\python.exe scripts\\build_clinician_review_queue.py

Builds files only; shares no image and records no clinical decision. Images may be shown to a reviewer only after the clinical-
governance decision (reports/templates/clinical_governance_decision_template.md) and the data permissions exist.
* Targets: findings with seeds_other_caries_gt == 5 in kaggle/artifacts_cv5_run1/caries_confusion_findings.csv (checked against
  SHA256SUMS.txt); the count must equal the archived total (110).
* Controls: the same number of findings never confused (seeds_other_caries_gt == 0), class by class, drawn with
  numpy default_rng(20261025), so the reviewer cannot infer which items are suspected. The clinical lead may drop them.
* Blinding: the reviewer worksheet holds a random review ID, image path, box and tooth number only - no original label, no model
  output, no target/control flag. The coordinator key (kept away from reviewers) maps IDs back.
* Boxes come from data/splits/combined_train.csv / combined_validation.csv (checked against the CV5 bundle copies).
Writes reports/clinical_review/caries_rereading_*_v1.* and a manifest with SHA-256 (never overwritten).
"""
from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "kaggle" / "artifacts_cv5_run1"
OUT = ROOT / "reports" / "clinical_review"
BUNDLE = ROOT / "kaggle" / "dist" / "dentamind_kaggle_bundle.zip"
MANIFESTS = ["data/splits/combined_train.csv", "data/splits/combined_validation.csv"]
SEED = 20261025
REVIEW_FIELDS = ["reviewer_class (Caries / Deep Caries / Other finding / No finding / Uncertain)", "reviewer_confidence (1-5)",
                 "image_quality_adequate (yes/no)", "comment", "reviewer_id", "review_date"]


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build() -> tuple[list, list, dict]:
    sums = {}
    for line in (ART / "SHA256SUMS.txt").read_text().splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*").replace("\\", "/")] = h
    h_cc = sha(ART / "caries_confusion_findings.csv")
    if sums.get("caries_confusion_findings.csv") != h_cc:
        raise SystemExit("caries_confusion_findings.csv does not match SHA256SUMS.txt")
    res = json.loads((ART / "cv5_results.json").read_text(encoding="utf-8"))
    z = zipfile.ZipFile(BUNDLE)
    man = {}
    for m in MANIFESTS:
        if hashlib.sha256(z.read(m)).hexdigest() != sha(ROOT / m):
            raise SystemExit(f"{m} differs from the CV5 bundle copy")
        for r in csv.DictReader(open(ROOT / m, encoding="utf-8")):
            man[r["sample_id"]] = r
    folds = {r["radiograph_group"]: r["fold"] for r in csv.DictReader(open(ROOT / "data" / "splits" / "cv5_folds_v1.csv", encoding="utf-8"))}
    rows = list(csv.DictReader(open(ART / "caries_confusion_findings.csv", encoding="utf-8")))
    targets = [r for r in rows if r["seeds_other_caries_gt"] == "5"]
    if len(targets) != sum(res["caries_confusion"]["confused_by_all_seeds_gt"].values()):
        raise SystemExit("target count differs from the archived consistent-confusion count")
    rng = np.random.default_rng(SEED)
    controls = []
    for c in ("Caries", "Deep Caries"):
        need = sum(r["label"] == c for r in targets)
        pool = sorted((r for r in rows if r["label"] == c and r["seeds_other_caries_gt"] == "0"), key=lambda r: r["sample_id"])
        controls += [pool[i] for i in sorted(rng.choice(len(pool), size=need, replace=False))]
    items = [(r, "target") for r in targets] + [(r, "control") for r in controls]
    order = rng.permutation(len(items))
    work, key = [], []
    for n, i in enumerate(order, 1):
        r, kind = items[i]
        m = man[r["sample_id"]]
        x, y, w, h = json.loads(m["bbox_xywh"])
        rid = f"CR-{n:03d}"
        work.append({"review_id": rid, "image_path": m["image_path"], "image_sha256": m["image_sha256"],
                     "box_xyxy_px": json.dumps([round(x, 1), round(y, 1), round(x + w, 1), round(y + h, 1)]),
                     "fdi_tooth": m["fdi_tooth"], **{f: "" for f in REVIEW_FIELDS}})
        key.append({"review_id": rid, "sample_id": r["sample_id"], "radiograph_group": r["radiograph_group"],
                    "cv5_fold": folds.get(r["radiograph_group"], ""), "set": kind, "original_label": r["label"],
                    "annotation_provenance": f"{m['source_dataset']} ({m['source_split']}), annotation_id {m['annotation_id']}, "
                                             f"{m['annotation_type']}",
                    "seeds_other_caries_gt": r["seeds_other_caries_gt"], "seeds_other_caries_det": r["seeds_other_caries_det"],
                    "detector_matched": r["detector_matched"]})
    meta = {"targets": len(targets), "controls": len(controls), "seed": SEED, "inputs": {
        "kaggle/artifacts_cv5_run1/caries_confusion_findings.csv": h_cc, **{m: sha(ROOT / m) for m in MANIFESTS},
        "data/splits/cv5_folds_v1.csv": sha(ROOT / "data" / "splits" / "cv5_folds_v1.csv")}}
    return work, key, meta


def write_csv(path: Path, rows: list):
    with open(path, "x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    files = {"worksheet": OUT / "caries_rereading_worksheet_v1_BLINDED.csv", "key": OUT / "caries_rereading_key_v1_COORDINATOR_ONLY.csv",
             "manifest": OUT / "caries_rereading_manifest_v1.json"}
    if any(p.exists() for p in files.values()):
        raise SystemExit("review queue v1 exists: build a new version instead of overwriting")
    work, key, meta = build()
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(files["worksheet"], work)
    write_csv(files["key"], key)
    meta.update({"format": "dentamind-clinician-rereading-queue-v1", "script_sha256": sha(Path(__file__)),
                 "status": "PREPARED ONLY - no image shared, no review performed; blocked until a clinical lead and data permissions exist",
                 "outputs": {k: {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(p)} for k, p in files.items() if k != "manifest"}})
    with open(files["manifest"], "x", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(f"worksheet {len(work)} items ({meta['targets']} targets + {meta['controls']} controls), key, manifest -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
