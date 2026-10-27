"""pytest/unittest bootstrap: make ``src`` and the project root importable without installing anything.

Some tests check real artifacts that are deliberately not in Git (dataset manifests, restricted run outputs, clinical
review files, the deployed model). ``REQUIRES`` names, per test, the exact files it reads; the test is skipped with
that reason only when one of them is absent. Everything else always runs.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# ------------------------------------------------------------------------------------------- external artifacts
_HOW = {
    "data/splits/": "built from the DENTEX download by scripts/dataset/build_combined_manifest.py; not in Git",
    "kaggle/artifacts_cv5_run1/": "archived CV5-BASE run outputs (restricted; kept outside Git)",
    "reports/clinical_review/": "blinded clinical re-reading files (restricted; kept outside Git)",
    "Data/checkpoints/": "deployed classifier sidecar, kept with the model weights outside Git",
}
_MANIFESTS = [f"data/splits/combined_{s}.csv" for s in ("train", "validation", "calibration", "test")]
_CV5 = "kaggle/artifacts_cv5_run1/"
_OOF = [_CV5 + "oof_predictions.csv", _CV5 + "cv5_results.json"]
_CR = "reports/clinical_review/caries_rereading_"

REQUIRES = {
    **{f"tests/test_cv5.py::{t}": _MANIFESTS for t in (
        "test_approved_fold_file_is_reproduced_by_the_generator", "test_reviewed_draft_is_still_reproduced_without_the_flag",
        "test_fold_assignment_does_not_depend_on_row_order", "test_fold_gate_passes_on_the_real_manifests",
        "test_fold_gate_catches_a_test_radiograph", "test_fold_gate_catches_one_image_in_two_folds",
        "test_every_radiograph_keeps_all_its_findings_in_one_fold", "test_plans_are_disjoint_and_cover_every_primary_finding_once",
        "test_inner_validation_is_about_one_eighth_and_deterministic", "test_official_val_findings_are_never_trained_on",
        "test_plan_gate_catches_leakage", "test_class_mapping_matches_the_deployed_order")},
    **{f"tests/test_cv5_imports.py::{t}": _MANIFESTS for t in (
        "test_independence_rejects_shared_groups_and_images", "test_imports_enter_only_the_fitting_part_of_every_fold",
        "test_import_rows_are_valid_crop_rows", "test_imports_never_touch_protected_artifacts_or_the_default_notebook")},
    **{f"tests/test_cv5_accept.py::{t}": _OOF for t in (
        "test_point_estimates_reproduce_the_archived_cv5_results", "test_base_vs_itself_has_zero_delta_and_fails_pa",
        "test_bootstrap_resample_matches_explicit_multiset", "test_bootstrap_is_deterministic_and_records_draws",
        "test_clearly_better_candidate_is_accepted", "test_hard_harm_fails_a_clear_protected_decrease_within_margin",
        "test_ensemble_mode_skips_pc_only")},
    "tests/test_cv5_accept.py::test_gate_r": _OOF + [_CV5 + "runs"],
    "tests/test_cv5_accept.py::test_heldout_report_from_stored_predictions": _MANIFESTS[:2] + [
        _CV5 + "runs/CV5_BASE_f0_s42__heldout_pred.npz", _CV5 + "runs/CV5_BASE_f0_s42__cv_run.json"],
    "tests/test_improvement_round2.py::test_worksheet_v2_reveals_nothing_that_identifies_the_public_label": [
        _CR + "worksheet_v2_BLINDED.csv", _CR + "key_v2_COORDINATOR_ONLY.csv"],
    "tests/test_improvement_round2.py::test_v1_worksheet_and_key_unchanged": [
        _CR + "worksheet_v1_BLINDED.csv", _CR + "key_v1_COORDINATOR_ONLY.csv"],
    "tests/test_improvement_round2.py::test_v3_1_discloses_test_split_use_and_passes_all_audits": [
        _CV5 + "SHA256SUMS.txt", _CV5 + "cv5_results.json"],
    "tests/test_inference_consistency.py::test_deployed_sidecar_states_the_cv5_training_preprocessing": [
        "Data/checkpoints/dentex_findings_classification_v1.json"],
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        missing = [p for p in REQUIRES.get(item.nodeid, ()) if not (ROOT / p).exists()]
        if missing:
            why = next(v for k, v in _HOW.items() if missing[0].startswith(k))
            item.add_marker(pytest.mark.skip(reason=f"needs {missing[0]} ({why})"))
