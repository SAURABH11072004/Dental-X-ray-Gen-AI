#!/usr/bin/env python
"""Full gate V6 for a registered CV5 import manifest, run LOCALLY (protocol section 3.1 item 4; DRAFT Amendment 02).

    .venv\\Scripts\\python.exe scripts\\dataset\\run_cv5_import_v6.py --manifest <m.json> --manifest-sha256 <hex> --out <v6.json>

Protected images: every project manifest radiograph (combined train + validation = CV pool, calibration, test) and every
annotation-pool radiograph not locked 'unassigned' (twins, eval_locked). Their files are read here only to compute the perceptual
hash and thumbnail correlation of the leakage rule, as scripts/check_leakage.py does; no label or prediction is involved. This is
why the full check runs locally: the CV5 notebook never reads a calibration or test image, and only verifies this record (by its
registered SHA-256) plus its own identity and CV-pool near-duplicate checks. The record is written once and only if V6 passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (HERE, ROOT / "kaggle"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import cv5_imports as CIM  # noqa: E402
from dsutil import read_csv  # noqa: E402


def protected_images(splits_dir, pool_csv, data_root) -> tuple[list, dict]:
    imgs, desc = {}, {}
    for s in ("train", "validation", "calibration", "test"):
        rows = read_csv(Path(splits_dir) / f"combined_{s}.csv")
        desc[f"combined_{s}"] = len({r["image_sha256"] for r in rows})
        for r in rows:
            imgs.setdefault(r["image_sha256"], {"id": r["sample_id"], "group": r["radiograph_group"], "sha256": r["image_sha256"],
                                                "path": Path(data_root) / r["image_path"]})
    pool = [r for r in read_csv(pool_csv) if r["split_lock"] != CIM.IMPORTABLE_SPLIT_LOCK]
    desc["annotation_pool_not_unassigned"] = len(pool)
    for r in pool:
        imgs.setdefault(r["image_sha256"], {"id": r["pool_id"], "group": r["radiograph_group"], "sha256": r["image_sha256"],
                                            "path": Path(data_root) / r["image_path"]})
    missing = [i["path"].as_posix() for i in imgs.values() if not i["path"].is_file()]
    if missing:
        raise CIM.ImportRefused(f"{len(missing)} protected image file(s) not found locally (V6 must see every one): {missing[:5]}")
    return list(imgs.values()), desc


def run(manifest_path, manifest_sha256, splits_dir, pool_csv, data_root, import_root) -> dict:
    m = CIM.load_import_manifest(manifest_path, manifest_sha256)
    CIM.verify_image_files(m, import_root)
    prot, desc = protected_images(splits_dir, pool_csv, data_root)
    desc["protected_images"] = len(prot)
    res = CIM.gate_v6_for_manifest(m, prot, import_root)
    return CIM.make_v6_record(m, res, desc)


def write_once(rec: dict, out) -> str:
    out = Path(out)
    if out.exists():
        raise CIM.ImportRefused(f"{out} exists: a V6 record is written once")
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, default=str)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--manifest-sha256", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-root", default=str(ROOT / "data"))
    ap.add_argument("--import-root", default=str(ROOT / "data"))
    a = ap.parse_args()
    rec = run(a.manifest, a.manifest_sha256, ROOT / "data" / "splits", ROOT / "data" / "annotation" / "annotation_pool.csv",
              a.data_root, a.import_root)
    print(f"wrote {a.out}: V6 passed for {rec['imported_images']} images vs {rec['protected']['protected_images']} protected; "
          f"sha256 {write_once(rec, a.out)}")


if __name__ == "__main__":
    main()
