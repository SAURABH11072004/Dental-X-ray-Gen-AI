"""Tests for kaggle/cv5_lib.py and the approved fold file (protocol reports/cv5_protocol.md)."""
import csv
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset"):
    sys.path.insert(0, str(p))

import cv5_lib as CV  # noqa: E402
import dentamind_kaggle as DK  # noqa: E402
import make_cv_folds as MCF  # noqa: E402
from dsutil import CLASSES, read_csv  # noqa: E402

SPLITS = ROOT / "data" / "splits"
FOLDS = SPLITS / "cv5_folds_v1.csv"


@pytest.fixture(scope="module")
def rows_by_split():
    return {s: read_csv(SPLITS / f"combined_{s}.csv") for s in ("train", "validation", "calibration", "test")}


@pytest.fixture(scope="module")
def pool(rows_by_split):
    return [r for s in CV.POOL_SPLITS for r in rows_by_split[s]]


@pytest.fixture(scope="module")
def fold_of():
    return CV.load_folds(FOLDS)


# ---------------------------------------------------------------------------------------------------- fold file
def test_approved_fold_file_is_reproduced_by_the_generator(pool, fold_of):
    assert MCF.assign_folds(pool, with_impacted=True) == fold_of


def test_reviewed_draft_is_still_reproduced_without_the_flag(pool):
    draft = {r["radiograph_group"]: int(r["fold"]) for r in read_csv(SPLITS / "cv5_folds_DRAFT.csv")}
    assert MCF.assign_folds(pool) == draft


def test_fold_assignment_does_not_depend_on_row_order(pool):
    assert MCF.assign_folds(pool, with_impacted=True) == MCF.assign_folds(list(reversed(pool)), with_impacted=True)


def test_other_fold_files_are_refused(tmp_path):
    p = tmp_path / "folds.csv"
    p.write_text(FOLDS.read_text(encoding="utf-8").replace(",0,", ",1,", 1), encoding="utf-8")
    with pytest.raises(CV.CVError, match="not the approved"):
        CV.load_folds(p)


def test_fold_gate_passes_on_the_real_manifests(fold_of, rows_by_split):
    rep = CV.check_folds(fold_of, rows_by_split)
    assert rep["pool_groups"] == 581 and rep["pool_findings"] == 3010
    assert sorted(rep["radiographs_per_fold"]) == [0, 1, 2, 3, 4]


def test_fold_gate_catches_a_test_radiograph(fold_of, rows_by_split):
    bad = dict(fold_of)
    bad[rows_by_split["test"][0]["radiograph_group"]] = 0
    with pytest.raises(CV.CVError):
        CV.check_folds(bad, rows_by_split)


def test_fold_gate_catches_one_image_in_two_folds(fold_of, rows_by_split):
    rbs = dict(rows_by_split)
    clone = dict(rbs["train"][0])
    other = next(g for g, f in fold_of.items() if f != fold_of[clone["radiograph_group"]])
    clone["radiograph_group"] = other            # same image SHA-256, placed in a radiograph group of another fold
    rbs["train"] = rbs["train"] + [clone]
    with pytest.raises(CV.CVError, match="two folds"):
        CV.check_folds(fold_of, rbs)


def test_every_radiograph_keeps_all_its_findings_in_one_fold(pool, fold_of):
    seen = {}
    for r in pool:
        assert seen.setdefault(r["image_sha256"], fold_of[r["radiograph_group"]]) == fold_of[r["radiograph_group"]]


# ---------------------------------------------------------------------------------------------------- per-fold plan
def test_plans_are_disjoint_and_cover_every_primary_finding_once(pool, fold_of):
    primary = [r["sample_id"] for r in pool if r["source_dataset"] == CV.PRIMARY]
    held = []
    for k in range(CV.K):
        plan = CV.fold_plan(pool, fold_of, k)
        rep = CV.check_plan(plan, fold_of)
        assert rep["inner"]["radiographs"] < rep["fit"]["radiographs"]
        held += [r["sample_id"] for r in plan["heldout"]]
        assert sorted(r["sample_id"] for r in plan["fit"] + plan["inner"] + plan["heldout"]) == sorted(
            r["sample_id"] for r in pool if r["source_dataset"] == CV.PRIMARY)
    assert sorted(held) == sorted(primary)
    assert len(held) == 2851


def test_inner_validation_is_about_one_eighth_and_deterministic(pool, fold_of):
    a, b = CV.fold_plan(pool, fold_of, 2), CV.fold_plan(pool, fold_of, 2)
    assert [r["sample_id"] for r in a["inner"]] == [r["sample_id"] for r in b["inner"]]
    n_in = len({r["radiograph_group"] for r in a["inner"]})
    n_all = n_in + len({r["radiograph_group"] for r in a["fit"]})
    assert 0.10 < n_in / n_all < 0.15


def test_official_val_findings_are_never_trained_on(pool, fold_of):
    for k in range(CV.K):
        plan = CV.fold_plan(pool, fold_of, k)
        assert {r["source_dataset"] for r in plan["fit"] + plan["inner"]} == {CV.PRIMARY}
        assert {r["source_dataset"] for r in plan["heldout_secondary"]} <= {CV.SECONDARY}


def test_plan_gate_catches_leakage(pool, fold_of):
    plan = CV.fold_plan(pool, fold_of, 0)
    leaky = dict(plan, fit=plan["fit"] + plan["heldout"][:1])
    with pytest.raises(CV.CVError):
        CV.check_plan(leaky, fold_of)


# ---------------------------------------------------------------------------------------------------- class mapping / recipe
def test_class_mapping_matches_the_deployed_order(pool):
    assert list(CLASSES) == ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
    assert all(CLASSES[int(r["class_index"])] == r["target_class"] for r in pool)


def test_fold_config_is_the_base_recipe():
    base = dataclasses.asdict(DK.EXPERIMENTS["BASE"])
    cfg = dataclasses.asdict(CV.fold_config(3))
    assert cfg["name"] == "CV5_BASE_f3"
    assert {k: v for k, v in cfg.items() if k not in ("name", "note")} == {k: v for k, v in base.items() if k not in ("name", "note")}


# ---------------------------------------------------------------------------------------------------- evaluation
def test_macro_f1_matches_project_report():
    rng = np.random.default_rng(0)
    for _ in range(20):
        y = rng.integers(0, 4, 80)
        p = np.where(rng.random(80) < 0.7, y, rng.integers(0, 4, 80))
        assert CV.macro_f1(y, p) == pytest.approx(DK.report(y, p)["macro_f1"])


def _oof(n, seeds, fill=1):
    out = {}
    for s in seeds:
        p = np.random.default_rng(s).random((n, 4))
        p /= p.sum(1, keepdims=True)
        out[s] = {"gt": p, "det": p.copy(), "filled": np.full(n, fill)}
    return out


def test_oof_gate_requires_exactly_one_prediction_per_finding():
    CV.check_oof(_oof(10, CV.SEEDS), 10)
    o = _oof(10, CV.SEEDS)
    o[43]["gt"][3] = np.nan
    with pytest.raises(CV.CVError, match="incomplete"):
        CV.check_oof(o, 10)
    o = _oof(10, CV.SEEDS)
    o[44]["filled"][5] = 2
    with pytest.raises(CV.CVError, match="0 or >1"):
        CV.check_oof(o, 10)
    with pytest.raises(CV.CVError, match="no out-of-fold"):
        CV.check_oof(_oof(10, [42]), 10)


def test_pooled_reports_use_matched_findings_for_detector_setting():
    y = np.array([0, 1, 2, 3, 0, 1])
    o = _oof(6, [42])
    matched = np.array([True, True, False, True, True, False])
    o[42]["det"][~matched] = np.nan
    r = CV.pooled_reports(y, o, matched, seeds=[42])[42]
    assert r["gt"]["n"] == 6 and r["det_matched"]["n"] == 4
    assert r["end_to_end"]["unmatched_findings"] == 2


def test_bootstrap_resamples_radiographs_and_is_reproducible():
    rng = np.random.default_rng(1)
    groups = np.repeat(np.arange(30), 4)
    y = rng.integers(0, 4, 120)
    preds = [np.where(rng.random(120) < 0.8, y, 0) for _ in range(3)]
    a = CV.cluster_bootstrap(y, preds, groups, n_boot=300)
    b = CV.cluster_bootstrap(y, preds, groups, n_boot=300)
    assert a == b and a["unit"] == "radiograph" and a["n_radiographs"] == 30
    assert a["ci95"][0] <= a["point"] <= a["ci95"][1]
    valid = np.ones(120, bool)
    valid[:8] = False
    want = np.mean([CV.macro_f1(y[valid], p[valid]) for p in preds])
    assert CV.cluster_bootstrap(y, preds, groups, valid=valid, n_boot=50)["point"] == pytest.approx(want)


# ---------------------------------------------------------------------------------------------------- detector
def _rows_for(boxes, image="img1"):
    return [{"project_image_id": image, "bbox_xywh": json.dumps([b[0], b[1], b[2] - b[0], b[3] - b[1]])} for b in boxes]


def test_detector_comparison_passes_for_identical_and_near_identical_boxes():
    gts = [[0, 0, 100, 100], [200, 0, 300, 100]]
    cached = {"img1": [g + [0.9] for g in gts]}
    assert CV.compare_detector(_rows_for(gts), cached, cached)["pass"]
    near = {"img1": [[g[0] + 0.5, g[1], g[2] + 0.5, g[3]] + [0.9] for g in gts]}
    assert CV.compare_detector(_rows_for(gts), near, cached)["pass"]


def test_detector_comparison_fails_when_a_finding_loses_its_box():
    gts = [[0, 0, 100, 100], [200, 0, 300, 100]]
    cached = {"img1": [g + [0.9] for g in gts]}
    new = {"img1": [gts[0] + [0.9], gts[1] + [0.2]]}          # second box now below the 0.3 score threshold
    r = CV.compare_detector(_rows_for(gts), new, cached)
    assert not r["pass"] and r["images_with_different_match"][0]["only_cached"] == [1]


def test_gray_loader_matches_production(tmp_path):
    from PIL import Image
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from dentexmodel.data.preprocess import load_gray
    except Exception as e:  # pragma: no cover
        pytest.skip(f"production package not importable: {e}")
    rng = np.random.default_rng(0)
    imgs = {"l.png": Image.fromarray(rng.integers(0, 255, (40, 50), dtype=np.uint8), "L"),
            "rgb.png": Image.fromarray(rng.integers(0, 255, (40, 50, 3), dtype=np.uint8), "RGB"),
            "i16.png": Image.fromarray(rng.integers(0, 65535, (40, 50), dtype=np.uint16))}
    for name, im in imgs.items():
        p = tmp_path / name
        im.save(p)
        assert np.array_equal(CV.load_gray01(p), load_gray(p)), name


# ---------------------------------------------------------------------------------------------------- caries analysis
def test_caries_confusion_counts_seeds_without_judging_labels():
    rows = [{"sample_id": f"s{i}", "image_path": "x.png", "radiograph_group": f"g{i}", "fdi_tooth": t, "target_class": c,
             "original_label": c, "class_index": str(CLASSES.index(c)), "bbox_xywh": json.dumps([0, 0, 10 + i, 10])}
            for i, (c, t) in enumerate([("Caries", "16"), ("Deep Caries", "46"), ("Impacted", "38"), ("Caries", "21")])]
    o = {}
    for s in CV.SEEDS:
        p = np.zeros((4, 4))
        p[0, 1] = 1            # Caries predicted as Deep Caries by every seed
        p[1, 1] = 1            # Deep Caries correct
        p[2, 2] = 1
        p[3, 0] = 1
        o[s] = {"gt": p, "det": p.copy()}
    res = CV.caries_confusion(rows, o, np.array([True] * 4))
    recs = {r["sample_id"]: r for r in res["records"]}
    assert set(recs) == {"s0", "s1", "s3"}                      # Impacted excluded
    assert recs["s0"]["seeds_other_caries_gt"] == 5 and recs["s1"]["seeds_other_caries_gt"] == 0
    assert recs["s0"]["tooth_type"] == "molar" and recs["s3"]["tooth_type"] == "incisor"
    assert res["confused_by_all_seeds_gt"] == {"Caries": 1, "Deep Caries": 0}
