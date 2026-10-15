"""Image-level training manifests for checkpoints, and the provenance level shown for every checkpoint.

A training manifest lists every image that actually contributed to training and to epoch selection (image id + SHA-256 of the
file), together with the split/manifest hashes, class mapping, preprocessing, seed and the full training configuration. It is
written next to the checkpoint as ``<checkpoint stem>.training_manifest.json``; the sidecar stores its SHA-256 so a later edit is
detected. Checkpoints trained before this existed are *legacy*: their image-level membership is not recorded and is never
inferred from matching counts.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "dentamind-training-manifest-v1"
LEGACY = "legacy: image-level training membership not recorded"
VERIFIED = "image-level training manifest (verified)"
BROKEN = "training manifest missing or modified"


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def build(settings, cfg, task_level: str, used: dict, class_mapping, preprocessing: dict, approved_reviews: list | None = None) -> dict:
    """``used`` = {"train": [(row, n_items)], "val": [(row, n_items)]} - only images that actually contributed."""
    from dentexmodel.training.trainers import assignments_sha
    state = {}
    sp = settings.results_dir / "dataset_state.json"
    if sp.is_file():
        state = json.loads(sp.read_text(encoding="utf-8"))
    splits = {k: [{"image_id": r.image_id, "content_sha256": r.content_hash, "file_path": r.file_path, "dataset_source": r.dataset_source,
                   "n_items": int(n)} for r, n in v] for k, v in used.items()}
    return {"format": FORMAT, "created": datetime.now(timezone.utc).isoformat(), "task": cfg.task, "annotation_level": task_level,
            "images": splits, "counts": {k: len(v) for k, v in splits.items()},
            "dataset": {"fingerprint": state.get("fingerprint"), "manifest_sha256": _sha(settings.processed_dir / "manifest.json"),
                        "splits_file_sha256": _sha(settings.splits_dir / "dentex_splits.json"),
                        "assignments_sha": assignments_sha(settings.splits_dir / "dentex_splits.json")},
            "class_mapping": class_mapping, "preprocessing": preprocessing, "seed": cfg.seed, "training_config": cfg.to_dict(),
            "approved_reviews": approved_reviews or [],
            "excluded_by_design": "calibration and test splits are never read by training (assert_not_test)"}


def write(path_ckpt: Path, manifest: dict) -> dict:
    """Write the manifest beside the checkpoint; return the sidecar reference."""
    p = path_ckpt.with_name(path_ckpt.stem + ".training_manifest.json")
    p.write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
    return {"file": p.name, "sha256": _sha(p), "format": FORMAT, "counts": manifest["counts"]}


def level(ckpt_path, meta: dict) -> dict:
    """Provenance level of a checkpoint from its sidecar (never from image counts)."""
    ref = meta.get("training_manifest")
    if not ref:
        return {"level": LEGACY, "legacy": True, "verified": False,
                "detail": "Trained before training manifests existed. Recorded image counts match the current split, but which images "
                          "were used cannot be proven image by image."}
    p = Path(ckpt_path).with_name(ref.get("file", ""))
    ok = bool(ref.get("file")) and _sha(p) == ref.get("sha256")
    return {"level": VERIFIED if ok else BROKEN, "legacy": False, "verified": ok, "file": ref.get("file"), "counts": ref.get("counts"),
            "detail": None if ok else "The manifest file is missing or no longer matches the SHA-256 in the sidecar."}
