#!/usr/bin/env python
"""Verify a downloaded Kaggle artifact archive and stage its checkpoints for OFFLINE review (never activates anything).

    .venv\\Scripts\\python.exe kaggle\\stage_kaggle_candidates.py PATH\\dentamind_balanced_training_artifacts.zip [--no-inference]

1. Every archive member is checked against SHA256SUMS.txt (and each checkpoint against the sha256 in its sidecar).
2. Files are extracted to checkpoints/kaggle_candidates/<archive-sha8>/ (top-level checkpoints/, outside data/checkpoints, so the
   model registry never scans or activates them).
3. Each sidecar is validated with the production rules (dentexmodel.inference.registry.validate_sidecar) and the weights are loaded
   with the production construction (torchvision resnet50 + 4-class fc, strict=True, torch_models._load_state).
4. Local inference test: the staged model predicts the cached validation crops (runtime/ml_cache/crops_val_224.npz) and the
   macro-F1 is compared with the value the sidecar reports from Kaggle (GPU-to-GPU differences of a few 1e-3 are expected).
Writes reports/checkpoint_manifest.json. data/checkpoints, configs/models.yaml and the abstention threshold are not touched.
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
for p in (ROOT / "src", ROOT / "kaggle", ROOT / "scripts/dataset"):
    sys.path.insert(0, str(p))
STAGE = ROOT / "checkpoints/kaggle_candidates"
PROTECTED = [ROOT / "data/checkpoints", ROOT / "configs/models.yaml", ROOT / "data/reports/uncertainty_thresholds.json"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def snapshot():
    out = {}
    for p in PROTECTED:
        files = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file()) if p.is_dir() else []
        for f in files:
            out[str(f.relative_to(ROOT))] = sha256(f)
    return out


def verify_and_extract(zpath: Path, stage_root: Path = STAGE):
    with zipfile.ZipFile(zpath) as z:
        if z.testzip():
            raise SystemExit("archive CRC error")
        names = z.namelist()
        for n in names:
            if n.startswith("/") or ".." in Path(n).parts:
                raise SystemExit(f"unsafe member {n}")
        sums = {}
        for line in z.read("SHA256SUMS.txt").decode().splitlines():
            if line.strip():
                h, f = line.split(None, 1)
                sums[f.strip()] = h
        bad = [n for n in names if n != "SHA256SUMS.txt" and hashlib.sha256(z.read(n)).hexdigest() != sums.get(n)]
        missing = [f for f in sums if f not in names]
        if bad or missing:
            raise SystemExit(f"hash verification failed: modified {bad[:5]} missing {missing[:5]}")
        dest = stage_root / sha256(zpath)[:8]
        dest.mkdir(parents=True, exist_ok=True)
        z.extractall(dest)
    return dest, len(sums)


def check_checkpoint(pth: Path, run_inference: bool):
    import numpy as np
    from dentexmodel.inference.registry import validate_sidecar
    meta = json.loads(pth.with_suffix(".json").read_text(encoding="utf-8"))
    rec = {"file": str(pth), "sha256": sha256(pth), "version": meta.get("version"), "promoted": meta.get("promoted")}
    rec["sidecar_problems"] = validate_sidecar(meta)
    rec["sha256_matches_sidecar"] = rec["sha256"] == meta.get("checkpoint_sha256_full", "") or rec["sha256"].startswith(str(meta.get("checkpoint_sha256")))
    import torch
    import torchvision as tv
    from dentexmodel.inference.torch_models import _load_state
    model = getattr(tv.models, meta["architecture"])(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, int(meta["num_classes"]))
    model.load_state_dict(_load_state(torch, str(pth), torch.device("cpu")), strict=True)
    rec["loads_with_production_construction"] = True
    rec["class_names"] = meta.get("class_names")
    rec["class_names_match_production"] = meta.get("class_names") == ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
    cache = ROOT / "runtime/ml_cache/crops_val_224.npz"
    if run_inference and cache.is_file():
        import dentamind_kaggle as DK
        with np.load(cache) as z:
            X, y = z["X"], z["y"]
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(dev)
        prob = DK.predict(torch, model, X, dev, bs=32)
        rep = DK.report(y, prob.argmax(1), prob)
        reported = (meta.get("metrics") or {}).get("classification", {}).get("macro_f1")
        rec["local_val_macro_f1"] = round(rep["macro_f1"], 4)
        rec["kaggle_reported_val_macro_f1"] = round(reported, 4) if reported is not None else None
        rec["abs_difference"] = round(abs(rep["macro_f1"] - reported), 4) if reported is not None else None
        rec["local_inference_ok"] = rec["abs_difference"] is not None and rec["abs_difference"] <= 0.01
    del model
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive")
    ap.add_argument("--no-inference", action="store_true")
    ap.add_argument("--stage-dir", default=str(STAGE), help="testing only: stage somewhere else")
    ap.add_argument("--manifest-out", default=str(ROOT / "reports/checkpoint_manifest.json"))
    a = ap.parse_args()
    before = snapshot()
    dest, n = verify_and_extract(Path(a.archive), Path(a.stage_dir))
    recs = [check_checkpoint(p, not a.no_inference) for p in sorted((dest / "checkpoints").glob("*.pth"))]
    after = snapshot()
    out = {"generated": datetime.now(timezone.utc).isoformat(), "archive": str(Path(a.archive).resolve()), "archive_sha256": sha256(a.archive),
           "members_verified": n, "staged_to": str(dest), "checkpoints": recs,
           "production_unchanged": before == after, "protected_files_checked": len(before),
           "note": "Staged for offline review only. Promotion requires explicit approval and the project's promotion workflow."}
    Path(a.manifest_out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    if not out["production_unchanged"]:
        sys.exit("ERROR: a protected production file changed during staging")


if __name__ == "__main__":
    main()
