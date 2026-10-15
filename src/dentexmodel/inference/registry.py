"""Model/checkpoint registry built from files actually present in ``MODEL_CHECKPOINT_DIR``.

A checkpoint is *dental-specific* only if it has a metadata sidecar (``<name>.json``) saying so. Anything else is
listed as an unverified-provenance file and is NOT used for inference. No entries are ever invented.

Sidecar example (``detector_v1.pth`` -> ``detector_v1.json``)::

    {"task": "detection", "architecture": "fasterrcnn_resnet50_fpn", "version": "det-v1", "dental_specific": true,
     "class_names": ["tooth"], "dataset_version": "dentex-2024-01", "num_classes": 2}
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

from dentexmodel.config import Settings
from dentexmodel.errors import ModelUnavailableError

CKPT_EXT = {".pt", ".pth", ".ckpt"}
TASKS = ("detection", "segmentation", "classification", "numbering")


@dataclass
class ModelInfo:
    model_id: str            # POSIX path relative to the checkpoint dir
    path: str
    task: str
    architecture: str | None
    version: str
    dental_specific: bool
    provenance: str          # "dental-trained (sidecar)" | "unverified (no metadata sidecar)"
    dataset_version: str | None
    size_mb: float
    created: str
    metadata: dict = field(default_factory=dict)
    eval_status: str = "not evaluated"
    promoted: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("path", None)  # do not leak absolute paths to the UI
        return d


KNOWN_ARCHITECTURES = {"detection": {"fasterrcnn_resnet50_fpn"}, "segmentation": {"maskrcnn_resnet50_fpn"},
                       "classification": {"resnet18", "resnet50"}, "numbering": {"fasterrcnn_resnet50_fpn"}}


def validate_sidecar(meta: dict) -> list:
    """Problems that make a checkpoint unsafe to load (empty list = compatible). Only checks what the sidecar states."""
    task, problems = meta.get("task"), []
    if task not in TASKS:
        return [f"unknown or missing task {task!r}"]
    arch = meta.get("architecture")
    if arch is not None and arch not in KNOWN_ARCHITECTURES[task]:
        problems.append(f"architecture {arch!r} is not supported for {task}")
    names, n = meta.get("class_names"), meta.get("num_classes")
    if names is not None and n is not None:
        expected = len(names) + (1 if task in ("detection", "segmentation", "numbering") else 0)
        if int(n) != expected:
            problems.append(f"num_classes={n} does not match {len(names)} class names (expected {expected})")
    if task == "numbering":
        if meta.get("label_mode") != "fdi" or not meta.get("fdi_codes"):
            problems.append("a numbering checkpoint must be trained with label_mode='fdi' and list its fdi_codes")
        ev = meta.get("evaluated_on")
        if not ev:
            problems.append("not registered yet: a numbering checkpoint is registered only after a successful evaluation "
                            "(scripts/evaluate_model.py writes 'evaluated_on' into the sidecar)")
        elif ev.get("passed") is not True:
            problems.append("evaluation did not pass the registration gate: " + str(ev.get("gate")))
    if task in ("detection", "segmentation", "numbering") and meta.get("label_mode") == "fdi" and meta.get("fdi_codes") is not None             and names is not None and len(meta["fdi_codes"]) != len(names):
        problems.append("fdi_codes and class_names differ in length")
    return problems


_SHA_CACHE: dict = {}


def _sha256_prefix(path: Path, n: int = 16) -> str:
    """sha256 prefix of a checkpoint file, cached per (path, size, mtime) so repeated scans stay cheap."""
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _SHA_CACHE:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        _SHA_CACHE[key] = h.hexdigest()
    return _SHA_CACHE[key][:n]


def scan_checkpoints(settings: Settings) -> list:
    root = settings.checkpoint_dir
    out: list = []
    if not root.is_dir():
        return out
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            p = Path(dirpath) / fn
            if p.suffix.lower() not in CKPT_EXT:
                continue
            meta = {}
            side = p.with_suffix(".json")
            if side.is_file():
                try:
                    meta = json.loads(side.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    meta = {}
            dental = bool(meta.get("dental_specific")) and meta.get("task") in TASKS
            rejected = validate_sidecar(meta) if dental else []
            recorded = str(meta.get("checkpoint_sha256") or "")
            if dental and recorded and not rejected:        # integrity: the file must be the one the sidecar describes
                try:
                    if not _sha256_prefix(p, len(recorded)) == recorded:
                        rejected.append("checkpoint file does not match the sha256 recorded in its sidecar (modified or corrupted)")
                except OSError as exc:
                    rejected.append(f"checkpoint file cannot be read: {exc}")
            if dental and not rejected and meta.get("training_manifest"):   # a declared manifest must exist and be unmodified
                from dentexmodel.training.provenance import level as _prov_level
                if not _prov_level(p, meta)["verified"]:
                    rejected.append("training manifest listed in the sidecar is missing or does not match its sha256")
            if rejected:
                dental = False
                meta = {**meta, "rejected_reasons": rejected}
            st = p.stat()
            out.append(ModelInfo(
                model_id=p.relative_to(root).as_posix(), path=str(p), task=meta.get("task", "unknown") if dental or meta.get("task") in TASKS else "unknown",
                architecture=meta.get("architecture"), version=str(meta.get("version", p.stem)), dental_specific=dental,
                provenance=("dental-trained (sidecar)" if dental else
                            ("rejected: " + "; ".join(rejected) if rejected else "unverified (no valid metadata sidecar)")),
                dataset_version=meta.get("dataset_version"), size_mb=round(st.st_size / 2**20, 2),
                created=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(), metadata=meta))
    return sorted(out, key=lambda m: m.model_id)


def _override_file(settings: Settings) -> Path:
    return settings.checkpoint_dir / "active_models.json"


def read_overrides(settings: Settings) -> dict:
    """Active-model selections made from the UI (precedence: env var > this file > configs/models.yaml)."""
    p = _override_file(settings)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def set_active(settings: Settings, task: str, model_id: str) -> None:
    if task not in TASKS:
        raise ModelUnavailableError(f"Unknown task '{task}'.", code="unknown_task")
    m = next((x for x in scan_checkpoints(settings) if x.model_id == model_id), None)
    if m is None:
        raise ModelUnavailableError(f"Checkpoint '{model_id}' does not exist.", code="checkpoint_missing")
    if not m.dental_specific or m.task != task:
        raise ModelUnavailableError(f"'{model_id}' is not a dental-specific {task} checkpoint (missing/invalid metadata sidecar).",
                                    code="unverified_checkpoint", hint="Only checkpoints with a valid .json sidecar can be activated.")
    data = read_overrides(settings)
    data[task] = model_id
    settings.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    _override_file(settings).write_text(json.dumps(data, indent=1), encoding="utf-8")


def active_model(settings: Settings, task: str) -> ModelInfo:
    """Resolve the active dental checkpoint for ``task`` or raise an actionable :class:`ModelUnavailableError`."""
    if task not in TASKS:
        raise ModelUnavailableError(f"Unknown task '{task}'.", code="unknown_task")
    configured = (os.environ.get(f"ACTIVE_{task.upper()}_CHECKPOINT") or read_overrides(settings).get(task)
                  or ((settings.models_cfg or {}).get("active") or {}).get(task))
    models = scan_checkpoints(settings)
    where = f"{settings.checkpoint_dir.name}/"
    setup_hint = (f"Place a trained {task} checkpoint and its .json metadata sidecar in {where}, then set active.{task} in "
                  f"configs/models.yaml - or train one from the Model Training page once the main dataset is available.")
    if not configured:
        cands = [m for m in models if m.task == task and m.dental_specific]
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1:
            raise ModelUnavailableError(f"{len(cands)} dental {task} checkpoints found but none is selected.",
                                        hint=f"Set active.{task} in configs/models.yaml.", code="model_not_selected")
        raise ModelUnavailableError(f"No dental {task} model is available.", hint=setup_hint, code="no_checkpoint")
    for m in models:
        if m.model_id == str(configured).replace("\\", "/"):
            if not m.dental_specific or m.task != task:
                raise ModelUnavailableError(f"Checkpoint '{m.model_id}' lacks dental-specific {task} metadata; refusing to use it as a dental model.",
                                            hint="Create the .json sidecar only if the weights were trained on dental data.", code="unverified_checkpoint")
            return m
    raise ModelUnavailableError(f"Configured {task} checkpoint '{configured}' was not found in {where}.", hint=setup_hint, code="checkpoint_missing")
