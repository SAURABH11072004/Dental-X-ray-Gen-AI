#!/usr/bin/env python
"""Package everything the Kaggle notebook needs EXCEPT images into kaggle/dist/dentamind_kaggle_bundle.zip.

    .venv\\Scripts\\python.exe kaggle\\build_kaggle_bundle.py [--with-deployed-checkpoint]

Contents: training library, dataset scripts, combined manifests, persisted DENTEX split file, official-validation labels, cached
production-detector boxes for the validation split, before-audit reports, and (optional, +95 MB) the deployed classifier so the
notebook can evaluate it as a reference. No radiographs: the notebook downloads them from the official source and verifies every
image's SHA-256 against the manifests. Upload the zip as a PRIVATE Kaggle dataset (see kaggle/README.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "kaggle/dentamind_kaggle.py",
    "scripts/dataset/dsutil.py", "scripts/dataset/adapters.py", "scripts/dataset/sources.py", "scripts/dataset/remote_zip_list.py",
    "scripts/dataset/download_external.py",
    "data/splits/combined_train.csv", "data/splits/combined_validation.csv", "data/splits/combined_calibration.csv",
    "data/splits/combined_test.csv", "data/splits/combined_excluded.csv", "data/splits/dentex_splits.json",
    "data/raw/external/dentex_hf/validation_triple.json",
    "docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json",
    "docs/audit_evidence/ml_improvement/imbalance/results.json",
    "reports/class_imbalance_before.csv", "reports/class_imbalance_after.csv", "reports/dataset_inventory.json",
    "reports/combined_split_audit.json", "reports/dataset_source_inventory.csv",
    "reports/class_distribution_before.png", "reports/class_distribution_after.png",
]
DEPLOYED = ["data/checkpoints/dentex_findings_classification_v1.pth", "data/checkpoints/dentex_findings_classification_v1.json"]
# external-data experiment (reports/external_data_protocol.md): Hanoi crops built locally, Cluj crops built on Kaggle with the
# production tooth detector (Cluj is downloaded there from Zenodo; the archive is too slow to fetch locally)
EXTERNAL = ["scripts/dataset/external_crops.py", "reports/external_data_protocol.md",
            "data/external_crops/hanoi/crops.npz", "data/external_crops/hanoi/manifest.csv", "data/external_crops/hanoi/mapping_stats.json",
            "data/checkpoints/dentex_teeth_detection_v1.pth", "data/checkpoints/dentex_teeth_detection_v1.json"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-deployed-checkpoint", action="store_true")
    ap.add_argument("--with-external", action="store_true", help="add the external-data experiment inputs (Hanoi crops, detector)")
    ap.add_argument("--out", default=str(ROOT / "kaggle/dist/dentamind_kaggle_bundle.zip"))
    a = ap.parse_args()
    files = FILES + (DEPLOYED if a.with_deployed_checkpoint else []) + (EXTERNAL if a.with_external else [])
    missing = [f for f in files if not (ROOT / f).is_file()]
    if missing:
        sys.exit(f"missing inputs (run scripts/dataset/audit_class_imbalance.py and build_combined_manifest.py first): {missing}")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"built": datetime.now(timezone.utc).isoformat(), "files": {f: sha(ROOT / f) for f in files}}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(ROOT / f, f)
        z.writestr("BUNDLE_MANIFEST.json", json.dumps(manifest, indent=1))
    print(f"wrote {out} ({out.stat().st_size / 2**20:.1f} MB, {len(files)} files) sha256 {sha(out)}")


if __name__ == "__main__":
    main()
