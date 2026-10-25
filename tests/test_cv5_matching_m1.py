"""Matching rule M1 library (DRAFT registration): synthetic data only - nothing here touches the CV5 evaluation population."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("m1", ROOT / "scripts" / "cv5_matching_m1.py")
M1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M1)


def test_reference_rule_is_identical_to_production():
    sys.path.insert(0, str(ROOT / "kaggle"))
    sys.path.insert(0, str(ROOT / "scripts" / "dataset"))
    import dentamind_kaggle as DK
    rng = np.random.default_rng(0)
    for _ in range(200):
        gts = [[x, y, x + w, y + h] for x, y, w, h in rng.uniform(0, 100, (rng.integers(1, 6), 4))]
        boxes = [[x, y, x + w, y + h] for x, y, w, h in rng.uniform(0, 100, (rng.integers(0, 6), 4))]
        assert M1.greedy_one_to_one(gts, boxes) == {i: j for i, (j, _) in DK.match(gts, boxes).items()}


def test_two_findings_on_one_tooth_share_the_box_and_reference_is_unchanged():
    tooth = [0, 0, 10, 20]
    gts = [[0, 0, 10, 20], [0, 1, 10, 20]]           # e.g. caries and a periapical lesion on the same tooth
    ref, fb = M1.assign_m1(gts, [tooth], [0.99])
    assert ref == {0: 0} and fb == {1: 0}
    assert M1.inherited_source(ref, fb) == {1: 0}


def test_fallback_never_uses_low_overlap_boxes_and_breaks_ties_by_score():
    gts = [[0, 0, 10, 10], [0, 0, 10, 10], [50, 50, 60, 60]]
    boxes = [[0, 0, 10, 10], [0, 0, 10, 10], [50, 50, 80, 80]]   # finding 2 overlaps its box with IoU 1/9 < 0.5
    ref, fb = M1.assign_m1(gts, boxes, [0.5, 0.9, 0.9])
    assert 2 not in ref and 2 not in fb
    gts2 = gts[:2] + [[0, 0, 10, 10]]
    ref2, fb2 = M1.assign_m1(gts2, boxes[:2], [0.5, 0.9])
    (left,) = set(range(3)) - set(ref2)                            # which finding the production rule leaves out on exact ties
    assert fb2 == {left: 1}                                        # equal IoU: the higher-score box wins


def test_unassigned_fallback_box_is_refused():
    with pytest.raises(ValueError, match="new inference"):
        M1.inherited_source({0: 0}, {1: 3})


def test_end_to_end_scores_treat_unmatched_as_missed_and_shared_crop_as_one_class():
    y = np.array([0, 3, 1, 2])
    ref_pred = np.array([0, -1, 1, 2])                # finding 1 (class 3) unmatched under the reference rule
    m1_pred = np.array([0, 0, 1, 2])                  # under M1 it inherits finding 0's crop, predicted class 0
    r, m = M1.end_to_end_scores(y, ref_pred), M1.end_to_end_scores(y, m1_pred)
    assert r["recall"][3] == 0 and m["recall"][3] == 0
    assert m["precision"][0] == 0.5 and r["precision"][0] == 1.0  # the shared crop adds a false positive for class 0
    assert (m["recall"] >= r["recall"]).all()                     # end-to-end recall cannot decrease under M1


def test_module_has_no_entry_point():
    src = (ROOT / "scripts" / "cv5_matching_m1.py").read_text(encoding="utf-8")
    assert "__main__" not in src and "artifacts_cv5_run1" not in src
