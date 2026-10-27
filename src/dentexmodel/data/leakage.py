"""Split-leakage checks by pixel content (SHA-256 of the image file), shared by ``scripts/check_leakage.py`` and the tests.

Every check counts radiographs that appear on both sides of a boundary that must not be crossed. A check with
``informational=True`` is reported (status ``warning``) but cannot invalidate a metric: it concerns images that are never
trained on or scored. It is still never shown as passed while its overlap is non-zero.
"""
from __future__ import annotations

from collections import defaultdict

SPLITS = ("train", "val", "calibration", "test")


def add_check(out: dict, name: str, overlap: int, note: str = "", informational: bool = False) -> None:
    ok = overlap == 0
    out["ok"] &= ok or informational          # informational rows never affect any reported metric
    out["checks"].append({"check": name, "overlap": overlap, "passed": ok, "informational": informational,
                          "status": "pass" if ok else ("warning" if informational else "fail"), "note": note})


def split_checks(rows, test_data_rows, assign: dict, task_level: dict, review_training_hashes: set | None = None) -> dict:
    """Exact-duplicate checks over the persisted split assignments.

    rows: main manifest rows; test_data_rows: unlabeled ``validation_data`` rows; assign: image_id -> split;
    task_level: task -> DENTEX sub-set it trains on; review_training_hashes: SHA-256 of every image whose approved review
    would be added to training (None = not checked).
    """
    annotated = [r for r in rows if r.annotation_status == "annotated"]
    by_split = defaultdict(set)
    for r in annotated:
        by_split[assign.get(r.image_id, "unassigned")].add(r.content_hash)
    out = {"annotated_distinct_per_split": {k: len(v) for k, v in sorted(by_split.items())}, "checks": [], "ok": True}
    add = lambda *a, **k: add_check(out, *a, **k)  # noqa: E731

    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            add(f"{a} vs {b} (all annotated sub-sets)", len(by_split[a] & by_split[b]))
    test_h = by_split["test"]
    for task, level in task_level.items():
        used = {sp: {r.content_hash for r in annotated if r.annotation_level == level and assign.get(r.image_id) == sp} for sp in SPLITS}
        add(f"{task}: training images used vs ALL test radiographs", len(used["train"] & test_h),
            f"train={len(used['train'])} distinct radiographs from '{level}'")
        add(f"{task}: validation images used (epoch selection) vs ALL test radiographs", len(used["val"] & test_h), f"val={len(used['val'])}")
    unl = [r for r in rows if r.annotation_status != "annotated"]
    add("unlabeled pool (after duplicate exclusion) vs test radiographs",
        len({r.content_hash for r in unl if not r.duplicate_of} & test_h),
        "pool images that are copies of labeled radiographs are excluded via duplicate_of")
    vd_test = sorted(r.image_id for r in test_data_rows if r.content_hash in test_h)
    add("validation_data (unlabeled) vs test radiographs", len(vd_test),
        "INFO only: validation_data is unlabeled, never split, never trained on and never scored, so this cannot affect any reported "
        "number; it only means demo predictions on these images are on test radiographs"
        + (f" ({', '.join(vd_test)})" if vd_test else ""), informational=True)
    if review_training_hashes is not None:
        held_out = by_split["val"] | by_split["calibration"] | test_h
        add("approved-review training items (uploads / pool) vs val, calibration and test radiographs",
            len(set(review_training_hashes) & held_out),
            f"{len(review_training_hashes)} image(s) currently feed approved review labels into training")
    out["validation_data_identical_to_test"] = vd_test
    out["validation_data_identical_to_labeled"] = sum(1 for r in test_data_rows if r.content_hash in set().union(*by_split.values()))
    return out


def summarize(checks: list) -> dict:
    """Counts for display. ``unresolved`` lists every check that did not pass, failures and warnings alike."""
    return {"total": len(checks), "passed": sum(1 for c in checks if c["passed"]),
            "failed": sum(1 for c in checks if not c["passed"] and not c.get("informational")),
            "warnings": sum(1 for c in checks if not c["passed"] and c.get("informational")),
            "unresolved": [{"check": c["check"], "overlap": c["overlap"], "status": c.get("status") or ("warning" if c.get("informational") else "fail"),
                            "note": c.get("note", "")} for c in checks if not c["passed"]]}
