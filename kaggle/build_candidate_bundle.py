#!/usr/bin/env python
"""Package the CV5 candidate-path code as a VERSIONED bundle: kaggle/dist/dentamind_cv5_candidate_code_v<N>.zip.

    .venv\\Scripts\\python.exe kaggle\\build_candidate_bundle.py --version 1

The historical data/code bundle kaggle/dist/dentamind_kaggle_bundle.zip (Kaggle dataset v3) is NOT rebuilt or overwritten: the
candidate path does not change any file in it. This bundle records which of its files the candidate path relies on and checks that
the working copies still equal them. An existing versioned bundle is never overwritten; a new version number is required.
Code and the approved fold file only: no radiograph, label manifest beyond the fold assignment, checkpoint or result.
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
DIST = ROOT / "kaggle" / "dist"
BASE_BUNDLE = DIST / "dentamind_kaggle_bundle.zip"
FILES = [
    "kaggle/cv5_accept.py", "kaggle/cv5_interventions.py", "kaggle/cv5_lib.py", "kaggle/make_cv5_notebook.py",
    "kaggle/make_notebook.py", "kaggle/make_cv5_preflight_notebook.py", "kaggle/cv5_preflight_trainer.py",
    "kaggle/dentamind_cv5_preflight.ipynb", "kaggle/build_candidate_bundle.py",
    "scripts/dataset/make_cv_folds.py", "data/splits/cv5_folds_v1.csv",
    "tests/test_cv5_accept.py", "tests/test_cv5_candidate_runs.py", "tests/test_cv5_interventions.py",
]
RELIES_ON = ["kaggle/dentamind_kaggle.py", "scripts/dataset/dsutil.py"]      # from the unchanged base bundle


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build(version: int, dist: Path = DIST, base_bundle: Path = BASE_BUNDLE) -> dict:
    out = dist / f"dentamind_cv5_candidate_code_v{version}.zip"
    if out.exists():
        raise SystemExit(f"{out.name} exists: versioned bundles are never overwritten; use --version {version + 1}")
    missing = [f for f in FILES + RELIES_ON if not (ROOT / f).is_file()]
    if missing:
        raise SystemExit(f"missing files: {missing}")
    with zipfile.ZipFile(base_bundle) as z:
        base_manifest = json.loads(z.read("BUNDLE_MANIFEST.json"))
    relies = {f: {"bundle_sha256": base_manifest["files"].get(f), "working_copy_sha256": sha(ROOT / f)} for f in RELIES_ON}
    drift = [f for f, v in relies.items() if v["bundle_sha256"] != v["working_copy_sha256"]]
    if drift:
        raise SystemExit(f"working copies differ from the base bundle: {drift} - the candidate path must not change them")
    manifest = {"bundle": out.name, "version": version, "built": datetime.now(timezone.utc).isoformat(),
                "purpose": "CV5 candidate-path code (reports/cv5_acceptance_protocol.md rev 3; DRAFT Amendment 01 / 01b)",
                "files": {f: sha(ROOT / f) for f in FILES},
                "base_bundle": {"file": base_bundle.name, "sha256": sha(base_bundle), "built": base_manifest.get("built"),
                                "relied_on_unchanged": relies},
                "not_included": "no radiographs, label manifests, checkpoints, results or ledger data"}
    dist.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(ROOT / f, f)
        z.writestr("CANDIDATE_BUNDLE_MANIFEST.json", json.dumps(manifest, indent=1))
    manifest["bundle_sha256"] = sha(out)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--manifest-out", default=None, help="also write the manifest (with the zip's own SHA-256) to this path")
    a = ap.parse_args()
    m = build(a.version)
    if a.manifest_out:
        Path(a.manifest_out).write_text(json.dumps(m, indent=1), encoding="utf-8")
    print(f"wrote {m['bundle']} ({len(m['files'])} files) sha256 {m['bundle_sha256']}")


if __name__ == "__main__":
    sys.exit(main())
