"""Seeded, group-aware, persistent train/val/calibration/test splitting.

* Group = patient id when the file name provides one (``patient_id_regex``), otherwise the image itself.
* A persisted split file is **append-only**: previously assigned images never move, so the test split cannot
  be contaminated by later re-splitting.
* ``assert_not_test`` guards training / active-learning code paths.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from dentexmodel.errors import LeakageError, ConfigError

SPLIT_NAMES = ("train", "val", "calibration", "test")


def _h(seed: int, key: str) -> float:
    d = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    return int.from_bytes(d[:8], "big") / 2 ** 64


def validate_fractions(fr: dict) -> dict:
    out = {k: float(fr.get(k, 0.0)) for k in SPLIT_NAMES}
    if any(v < 0 for v in out.values()) or abs(sum(out.values()) - 1.0) > 1e-6:
        raise ConfigError("Split fractions must be non-negative and sum to 1.", hint="Edit splits.fractions in configs/data.yaml.")
    return out


def assign_splits(rows: list, seed: int, fractions: dict, existing: dict | None = None) -> dict:
    """Return ``{image_id: split}``. Existing assignments are preserved; new groups fill remaining quota."""
    fr = validate_fractions(fractions)
    assign = dict(existing or {})
    groups: dict = {}
    for r in rows:
        groups.setdefault(r.patient_id or r.image_id, []).append(r.image_id)
    # keep a group together if any member is already assigned
    pending = []
    for g, members in groups.items():
        known = [assign[m] for m in members if m in assign]
        if known:
            for m in members:
                assign.setdefault(m, known[0])
        else:
            pending.append(g)
    n_total = len(groups)
    counts = {k: sum(1 for m in groups.values() if assign.get(m[0]) == k) for k in SPLIT_NAMES}
    target = {k: int(math.floor(fr[k] * n_total)) for k in SPLIT_NAMES}
    # distribute rounding remainder to train, then val
    rem = n_total - sum(target.values())
    for k in ("train", "val", "calibration", "test"):
        if rem <= 0:
            break
        if fr[k] > 0:
            target[k] += 1
            rem -= 1
    for g in sorted(pending, key=lambda g: _h(seed, g)):
        open_splits = [k for k in SPLIT_NAMES if fr[k] > 0 and counts[k] < target[k]]
        k = open_splits[0] if open_splits else "train"
        # deterministic order: process test first so tiny sets still get a test split
        for cand in ("test", "calibration", "val", "train"):
            if cand in open_splits:
                k = cand
                break
        for m in groups[g]:
            assign[m] = k
        counts[k] += 1
    return assign


def load_split_file(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_split_file(path: Path, assignments: dict, seed: int, fractions: dict, purpose: str, extra: dict | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    counts = {k: sum(1 for v in assignments.values() if v == k) for k in SPLIT_NAMES}
    payload = {"purpose": purpose, "seed": seed, "fractions": fractions, "counts": counts,
               "updated": datetime.now(timezone.utc).isoformat(), "assignments": dict(sorted(assignments.items()))}
    payload.update(extra or {})
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def locked_test_ids(assignments: dict) -> set:
    return {i for i, s in assignments.items() if s == "test"}


def assert_not_test(image_ids, assignments: dict, what: str = "training / active-learning selection") -> None:
    """Raise :class:`LeakageError` if any id belongs to the locked test split."""
    bad = sorted(set(image_ids) & locked_test_ids(assignments))
    if bad:
        raise LeakageError(f"{len(bad)} test-split image(s) were passed to {what}: {bad[:5]}",
                           hint="The test split is reserved for final evaluation only.")
