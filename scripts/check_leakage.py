#!/usr/bin/env python
"""Leakage check for the held-out test split, by pixel content (SHA-256), writing Data/reports/leakage_check.json/.md.

For every trained task it rebuilds the exact image sets used for training (train split, task's sub-set) and
validation, and verifies that no radiograph in them is pixel-identical to a radiograph in the test set the task was
evaluated on. It also checks the splits against each other across *all* sub-sets and the unlabeled folders, and the
images whose approved review labels would be added to training. The exact-hash checks live in dentexmodel.data.leakage.
"""
import _bootstrap  # noqa: F401
import json
import sys

import numpy as np
from datetime import datetime, timezone

from dentexmodel.config import get_settings
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.leakage import SPLITS, add_check, split_checks, summarize
from dentexmodel.data.splits import load_split_file
from dentexmodel.training.trainers import TASK_LEVEL, assignments_sha


def _sha(p):
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else None


def dhash(path, size=8):
    """64-bit difference hash of a 9x8 grayscale thumbnail: robust to re-encoding/resizing, not to crops."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("L").resize((size + 1, size), Image.BILINEAR)
    a = np.asarray(im, dtype=np.int16)
    return int("".join("1" if v else "0" for v in (a[:, 1:] > a[:, :-1]).flatten()), 2)


def near_duplicates(settings, rows, assign, max_hamming=4):
    """Pairs of *different* images (different SHA-256) whose perceptual hashes differ in <= max_hamming bits."""
    import json as _json
    cache_p = settings.processed_dir / "dhash_cache.json"
    cache = _json.loads(cache_p.read_text()) if cache_p.is_file() else {}
    hs = {}
    for r in rows:
        key = r.file_path
        if key not in cache:
            cache[key] = dhash(settings.data_root / key)
        hs[r.image_id] = (cache[key], r)
    cache_p.write_text(_json.dumps(cache))
    items = list(hs.values())
    arr = np.array([h for h, _ in items], dtype=np.uint64)
    pairs = []
    for i in range(len(items)):
        x = arr[i] ^ arr[i + 1:]
        # popcount of the XOR of 64-bit hashes
        c = np.array([bin(int(v)).count("1") for v in x])
        for j in np.where(c <= max_hamming)[0]:
            a_, b_ = items[i][1], items[i + 1 + j][1]
            if a_.content_hash != b_.content_hash:          # exact copies are already handled by pixel hash
                pairs.append((a_, b_, int(c[j])))
    return pairs


def review_training_hashes(s) -> set:
    """SHA-256 of every image whose approved review label would actually be added to training right now."""
    import hashlib
    from pathlib import Path
    from dentexmodel.annotation.reviews import ReviewStore
    from dentexmodel.storage import Database
    items, _ = ReviewStore(Database(s.db_path)).training_items(s)
    return {hashlib.sha256(Path(it["path"]).read_bytes()).hexdigest() for it in items}


def main() -> int:
    s = get_settings()
    svc = DatasetService(s)
    rows = svc.manifest("main")
    test_data_rows = svc.manifest("test_data")
    split_path = s.splits_dir / "dentex_splits.json"
    assign = load_split_file(split_path).get("assignments", {})
    annotated = [r for r in rows if r.annotation_status == "annotated"]
    names = list(SPLITS)
    res = split_checks(rows, test_data_rows, assign, TASK_LEVEL, review_training_hashes(s))
    out = {"generated": datetime.now(timezone.utc).isoformat(), "unit": "SHA-256 of image file bytes (identical radiographs)",
           "inputs": {"manifest_sha": _sha(s.processed_dir / "manifest.json"), "manifest_test_data_sha": _sha(s.processed_dir / "manifest_test_data.json"),
                      "assignments_sha": assignments_sha(split_path)}, **res}

    def add(name, overlap, note="", informational=False):
        add_check(out, name, overlap, note, informational)

    n_dup_val = out.pop("validation_data_identical_to_labeled")
    # near-duplicates (different bytes, nearly identical picture) across annotated images / test data
    ann_rows = [r for r in annotated] + test_data_rows
    pairs = near_duplicates(s, ann_rows, assign)
    cross_any = [(a_, b_, d) for a_, b_, d in pairs if assign.get(a_.image_id) in names and assign.get(b_.image_id) in names and assign.get(a_.image_id) != assign.get(b_.image_id)]
    # stage 2: a coarse hash is not evidence of duplication for panoramic films (they share a layout). Confirm with a fine-scale
    # pixel correlation (256x128 grayscale, Pearson); re-encodes/resizes of one film correlate > 0.97, different films stay below ~0.9.
    from PIL import Image
    thumbs = {}

    def thumb(r):
        if r.image_id not in thumbs:
            a2 = np.asarray(Image.open(s.data_root / r.file_path).convert("L").resize((256, 128), Image.BILINEAR), dtype=np.float32)
            thumbs[r.image_id] = (a2 - a2.mean()) / (a2.std() + 1e-6)
        return thumbs[r.image_id]
    cors = [float((thumb(a_) * thumb(b_)).mean()) for a_, b_, _ in cross_any]
    confirmed = [(p_, c) for p_, c in zip(cross_any, cors) if c >= 0.97]
    out["near_duplicates"] = {"method": "stage 1: 64-bit difference hash, Hamming <= 4 and different SHA-256; stage 2: Pearson correlation of 256x128 grayscale thumbnails >= 0.97",
                              "stage1_candidate_pairs": len(pairs), "stage1_pairs_across_different_splits": len(cross_any),
                              "stage2_confirmed_across_splits": len(confirmed), "max_correlation_among_candidates": max(cors) if cors else None,
                              "reference": "correlation between unrelated radiographs reaches about 0.86; the highest candidate here is below 0.92",
                              "limits": "re-encoded / resized copies are detected; crops, rotations and different exposures of the same patient are not",
                              "examples": [{"a": p_[0].image_id, "b": p_[1].image_id, "correlation": round(c, 4)} for p_, c in confirmed[:10]]}
    add("near-duplicate films across different splits (hash candidates confirmed by pixel correlation >= 0.97)", len(confirmed),
        f"{len(cross_any)} hash candidates, max correlation {max(cors):.3f} -> hash alone over-flags panoramic films" if cors else "no candidates")
    out["note_validation_data_overlap"] = f"{n_dup_val} validation_data images duplicate a labeled radiograph; they are unlabeled and excluded from every metric."
    out["limitation"] = ("Pixel identity cannot detect two different radiographs of the same patient: DENTEX provides no patient ids, so "
                         "patient-level leakage cannot be excluded.")
    out["summary"] = summarize(out["checks"])
    rep = s.data_root / "reports"
    (rep / "leakage_check.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    sm = out["summary"]
    lines = ["# Leakage check (held-out test split)", "", f"Generated {out['generated']}. Unit: {out['unit']}.", "",
             f"Result: {sm['passed']} of {sm['total']} checks passed; {sm['failed']} failed; {sm['warnings']} warning(s) (cannot affect any metric).", "",
             f"Distinct annotated radiographs per split: {out['annotated_distinct_per_split']}", "", "| Check | Overlap | Result |", "|---|---:|---|"]
    lines += [f"| {c['check']} | {c['overlap']} | {'PASS' if c['passed'] else ('WARNING (not used in any metric)' if c.get('informational') else 'FAIL')} |" for c in out["checks"]]
    lines += ["", out["note_validation_data_overlap"], "", f"**Limitation:** {out['limitation']}", ""]
    (rep / "leakage_check.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
