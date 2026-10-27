"""Tests for kaggle/cv5_accept.py (protocol reports/cv5_acceptance_protocol.md, revision 3). Uses the archived CV5-BASE run 1 as a
BASE-vs-BASE fixture only; no candidate exists and nothing here trains or runs inference."""
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset"):
    sys.path.insert(0, str(p))

import cv5_accept as CA  # noqa: E402
import cv5_lib as CV  # noqa: E402
from dsutil import CLASSES  # noqa: E402

ART = ROOT / "kaggle" / "artifacts_cv5_run1"
ALL_OK = {"V1": True, "V2": True, "V3": True, "V5": True, "V6": None}     # V4 is derived from the run classes
RUNS = [f"CAND_f{f}_s{s}" for f in range(5) for s in CV.SEEDS]


def runs(**override):
    """All 25 runs ok, except the overrides {run: class}."""
    return {r: override.get(r, "ok") for r in RUNS}


@pytest.fixture(scope="module")
def base():
    rows = list(csv.DictReader((ART / "oof_predictions.csv").open(newline="", encoding="utf-8")))
    y = np.array([CLASSES.index(r["true_class"]) for r in rows])
    groups = np.array([r["radiograph_group"] for r in rows])
    folds = np.array([int(r["fold"]) for r in rows])
    arm = {}
    for s in CV.SEEDS:
        f = lambda st: np.array([[float(r[f"s{s}_{st}_{c}"]) if r[f"s{s}_{st}_{c}"] not in ("", "nan") else np.nan for c in CLASSES]
                                 for r in rows])
        arm[s] = {"gt": f("gt"), "det": f("det")}
    return y, groups, folds, arm


def test_point_estimates_reproduce_the_archived_cv5_results(base):
    y, groups, folds, arm = base
    res = json.loads((ART / "cv5_results.json").read_text())["pooled_per_seed"]
    L = CA.labels(arm)
    uniq, gidx = np.unique(groups, return_inverse=True)
    for s in CV.SEEDS:
        for st, key in (("det", "det_matched"), ("gt", "gt")):
            mask = L[s]["matched"] if st == "det" else np.ones(len(y), bool)
            cm = CA._group_confusion(y, L[s][st], mask, gidx, len(uniq)).sum(0).reshape(CA.NC, CA.NC + 1)
            assert CA.metrics_from_confusion(cm)["macro_f1"] == pytest.approx(res[str(s)][key]["macro_f1"], abs=1e-12)
        cm = CA._group_confusion(y, L[s]["e2e"], np.ones(len(y), bool), gidx, len(uniq)).sum(0).reshape(CA.NC, CA.NC + 1)
        rec = CA.metrics_from_confusion(cm)["recall"]
        for k, c in enumerate(CLASSES):
            assert rec[k] == pytest.approx(res[str(s)]["end_to_end"]["recall"][c], abs=1e-12)


def test_base_vs_itself_has_zero_delta_and_fails_pa(base):
    y, groups, folds, arm = base
    out = CA.compare(y, groups, folds, arm, arm, n_boot=200)
    c = out["criteria"]
    assert c["P-A"]["delta"] == 0 and not c["P-A"]["pass"]
    assert c["P-B"]["ci"] == [0.0, 0.0] and not c["P-B"]["pass"]
    assert c["P-C"]["wins"] == 0 and c["P-D"]["wins"] == 0
    assert all(c[n]["pass"] for n, *_ in CA.SAFEGUARDS) and all(c[n]["pass"] for n, *_ in CA.HARM)
    assert out["n_findings"] == 2851 and out["n_detector_matched"] == 2745 and out["n_radiographs"] == 541
    assert CA.verdict(out, confirmatory=True, validity=ALL_OK, run_classes=runs())["verdict"] == "FAIL"


def test_bootstrap_resample_matches_explicit_multiset(base):
    y, groups, folds, arm = base
    L = CA.labels(arm)
    uniq, gidx = np.unique(groups, return_inverse=True)
    rng = np.random.default_rng(5)
    draw = rng.choice(len(uniq), size=len(uniq), replace=True)
    w = np.bincount(draw, minlength=len(uniq))[None, :]
    gc = CA._group_confusion(y, L[42]["det"], L[42]["matched"], gidx, len(uniq))
    vec = CA.metrics_from_confusion((w @ gc).reshape(-1, CA.NC, CA.NC + 1))["macro_f1"][0]
    i = np.concatenate([np.flatnonzero(gidx == g) for g in draw])
    i = i[L[42]["matched"][i]]
    assert vec == pytest.approx(CV.macro_f1(y[i], L[42]["det"][i]), abs=1e-12)


def test_bootstrap_is_deterministic_and_records_draws(base):
    y, groups, folds, arm = base
    a = CA.compare(y, groups, folds, arm, arm, n_boot=50)
    b = CA.compare(y, groups, folds, arm, arm, n_boot=50)
    assert a["bootstrap"]["draws_sha256"] == b["bootstrap"]["draws_sha256"] and len(a["delta_b_macro_f1"]) == 50


def test_clearly_better_candidate_is_accepted(base):
    y, groups, folds, arm = base
    eye = np.eye(len(CLASSES))[y]
    cand = {s: {"gt": eye.copy(), "det": np.where(np.isnan(arm[s]["det"]), np.nan, eye)} for s in CV.SEEDS}
    out = CA.compare(y, groups, folds, arm, cand, n_boot=300)
    assert out["all_criteria_pass"], {k: v for k, v in out["criteria"].items() if not v["pass"]}
    assert CA.verdict(out, confirmatory=True, validity=ALL_OK, run_classes=runs())["verdict"] == "ACCEPT"


def test_hard_harm_fails_a_clear_protected_decrease_within_margin(base):
    y, groups, folds, arm = base
    # candidate = reference, except a few correctly predicted Periapical Lesion findings are turned into Caries in every seed
    cand = {s: {k: v.copy() for k, v in arm[s].items()} for s in CV.SEEDS}
    L = CA.labels(arm)
    for s in CV.SEEDS:
        hit = np.flatnonzero((y == CA.PL) & (L[s]["det"] == CA.PL))[:3]
        cand[s]["det"][hit] = np.eye(len(CLASSES))[0]
    out = CA.compare(y, groups, folds, arm, cand, n_boot=300)
    c = out["criteria"]
    assert c["S2"]["pass"]                         # point drop is within the 0.05 margin
    assert not c["H_PL_recall"]["pass"]           # but the decrease is clear, so H fails


def test_ensemble_mode_skips_pc_only(base):
    y, groups, folds, arm = base
    out = CA.compare(y, groups, folds, arm, {"ens": arm[42]}, n_boot=50, ensemble=True)
    assert out["criteria"]["P-C"]["applicable"] is False and "P-D" in out["criteria"]


PASSING = {"criteria": {"P-A": {"pass": True}, "S1": {"pass": True}}}
FAILING = {"criteria": {"P-A": {"pass": False}, "S1": {"pass": True}}}
R0, R1, R2 = RUNS[0], RUNS[7], RUNS[13]


def v(comp=PASSING, validity=ALL_OK, **kw):
    return CA.verdict(comp, confirmatory=True, validity=validity, run_classes=kw.pop("rc", runs()), **kw)


def test_verdict_all_runs_successful():
    assert v()["verdict"] == "ACCEPT"
    assert v(FAILING)["verdict"] == "FAIL" and "P-A" in v(FAILING)["reason"]


def test_verdict_one_divergence_is_fail():
    out = v(rc=runs(**{R0: "divergence"}))
    assert out["verdict"] == "FAIL" and R0 in out["reason"]
    assert v(None, rc=runs(**{R0: "divergence"}))["verdict"] == "FAIL"           # FAIL does not need the comparison


def test_verdict_one_infrastructure_failure_is_no_verdict():
    out = v(rc=runs(**{R1: "infrastructure"}))
    assert out["verdict"] == "NO VERDICT" and R1 in out["reason"]
    assert v(FAILING, rc=runs(**{R1: "infrastructure"}))["verdict"] == "NO VERDICT"   # criteria are not read


def test_verdict_incomplete_and_unreported_runs_are_no_verdict():
    assert v(rc=runs(**{R2: "incomplete"}))["verdict"] == "NO VERDICT"
    partial = {r: "ok" for r in RUNS[:24]}
    out = v(rc=partial)
    assert out["verdict"] == "NO VERDICT" and "unreported runs 1" in out["reason"]
    assert v(None, rc={})["verdict"] == "NO VERDICT"


def test_verdict_mixed_outcomes_divergence_takes_precedence():
    mixed = runs(**{R0: "divergence", R1: "infrastructure", R2: "incomplete"})
    assert v(rc=mixed)["verdict"] == "FAIL"
    assert v(rc={R0: "divergence", R1: "infrastructure"})["verdict"] == "FAIL"     # 23 runs never reported
    assert v(rc=runs(**{R1: "infrastructure", R2: "incomplete"}))["verdict"] == "NO VERDICT"


def test_verdict_integrity_gate_failure_precedes_divergence():
    for g in ("V1", "V2", "V3", "V5", "V6"):
        assert v(validity={**ALL_OK, g: False}, rc=runs(**{R0: "divergence"}))["verdict"] == "NO VERDICT"


def test_verdict_input_checks():
    with pytest.raises(CA.AcceptError):
        CA.verdict(PASSING, confirmatory=False, validity=ALL_OK, run_classes=runs())
    with pytest.raises(CA.AcceptError):
        v(validity={"V1": True})
    with pytest.raises(CA.AcceptError):
        v(validity={**ALL_OK, "V4": True})
    with pytest.raises(CA.AcceptError):
        v(rc=runs(**{R0: "crashed"}))
    with pytest.raises(CA.AcceptError):
        v(rc={**runs(), "extra": "ok"})
    with pytest.raises(CA.AcceptError):
        v(None)


def test_winner_rule_order():
    c = [{"name": "a", "verdict": "ACCEPT", "delta": 0.03, "pb_lower": 0.001, "n_params": 10, "registered_at": "2027-01-02T00:00:00Z"},
         {"name": "b", "verdict": "ACCEPT", "delta": 0.03, "pb_lower": 0.002, "n_params": 99, "registered_at": "2027-01-03T00:00:00Z"},
         {"name": "c", "verdict": "FAIL", "delta": 0.09, "pb_lower": 0.05, "n_params": 1, "registered_at": "2027-01-01T00:00:00Z"}]
    assert CA.winner(c)["name"] == "b"
    c[1]["pb_lower"] = 0.001
    assert CA.winner(c)["name"] == "a"
    assert CA.winner([c[2]]) is None


def test_collapse_and_run_classification_on_base_runs():
    for f in sorted((ART / "runs").glob("*__result.json")):
        cm = json.loads(f.read_text())["val_gt"]["confusion"]
        assert CA.classify_run(completed=True, attempts=1, loss_nonfinite=False, inner_confusion=cm) == "ok"
    assert CA.classify_run(completed=True, attempts=1, loss_nonfinite=False, inner_confusion=[[99, 1], [100, 0]]) == "divergence"
    assert CA.classify_run(completed=True, attempts=1, loss_nonfinite=True, inner_confusion=None) == "divergence"
    # infrastructure: exception outside forward/backward/loss; retried until MAX_ATTEMPTS, then classified
    assert CA.classify_run(completed=False, attempts=3, loss_nonfinite=False, exception_outside_compute=True) == "infrastructure"
    for n in (1, 2):
        with pytest.raises(CA.AcceptError, match="retry"):
            CA.classify_run(completed=False, attempts=n, loss_nonfinite=False, exception_outside_compute=True)
    # a retry that completes is an ordinary run
    assert CA.classify_run(completed=True, attempts=2, loss_nonfinite=False, inner_confusion=[[5, 5], [5, 5]]) == "ok"
    # non-finite loss is divergence even if the run also stopped with an exception; never retried
    assert CA.classify_run(completed=False, attempts=1, loss_nonfinite=True, exception_outside_compute=True) == "divergence"
    # exception inside the computation (not infrastructure, not NaN): incomplete, not retried
    assert CA.classify_run(completed=False, attempts=1, loss_nonfinite=False, exception_outside_compute=False) == "incomplete"
    with pytest.raises(CA.AcceptError):
        CA.classify_run(completed=False, attempts=3, loss_nonfinite=False)
    # collapse threshold is >= 0.99, unrounded
    assert CA.classify_run(completed=True, attempts=1, loss_nonfinite=False, inner_confusion=[[99, 0], [0, 1]]) == "divergence"
    assert CA.classify_run(completed=True, attempts=1, loss_nonfinite=False, inner_confusion=[[989, 0], [0, 11]]) == "ok"


def test_budget_counting():
    reg = [{"name": f"x{i}", "family": "F1", "status": s} for i, s in enumerate(("started", "withdrawn", "pre_training_validity_failure"))]
    b = CA.budget(reg)
    assert b["used"]["F1"] == 2 and b["remaining"] == 13
    with pytest.raises(CA.AcceptError):
        CA.budget(reg + [{"name": "y", "family": "F1", "status": "registered"}, {"name": "z", "family": "F1", "status": "registered"}])
    with pytest.raises(CA.AcceptError):
        CA.budget([{"name": "e", "family": "F5", "status": "started"}, {"name": "f", "family": "F5", "status": "registered"}])


def test_fold_file_check():
    assert CA.check_fold_file(ROOT / "data" / "splits" / "cv5_folds_v1.csv")["pass"]


def test_gate_r(base):
    y, groups, folds, arm = base
    idx = np.arange(len(y))
    st = {"r": {"idx": idx, "gt": arm[42]["gt"], "det": arm[42]["det"]}}
    assert CA.gate_r(y, st, {"r": {k: v.copy() for k, v in st["r"].items()}})["pass"]
    small = {"r": {**st["r"], "gt": st["r"]["gt"] + 5e-5}}
    assert CA.gate_r(y, st, small)["pass"]
    big = {"r": {**st["r"], "gt": st["r"]["gt"] + 2e-4}}
    assert not CA.gate_r(y, st, big)["pass"]
    flip = st["r"]["gt"].copy()
    flip[0] = flip[0][::-1] if flip[0].argmax() != flip[0][::-1].argmax() else np.roll(flip[0], 1)
    r = CA.gate_r(y, st, {"r": {**st["r"], "gt": flip}})
    assert not r["pass"] and r["R1_argmax_mismatches"] >= 1


def test_gate_v6(tmp_path):
    from PIL import Image
    rng = np.random.default_rng(0)
    base_img = (rng.random((256, 512)) * 255).astype(np.uint8)
    Image.fromarray(base_img).save(tmp_path / "p.png")
    Image.fromarray(base_img).resize((500, 250), Image.BILINEAR).save(tmp_path / "near.png")
    Image.fromarray((rng.random((256, 512)) * 255).astype(np.uint8)).save(tmp_path / "other.png")
    sha = lambda n: CV.sha256_file(tmp_path / n)
    prot = [{"id": "P", "group": "g1", "sha256": sha("p.png"), "path": tmp_path / "p.png"}]
    imp = [{"id": "exact", "group": "g9", "sha256": sha("p.png"), "path": tmp_path / "p.png"},
           {"id": "near", "group": "g8", "sha256": sha("near.png"), "path": tmp_path / "near.png"},
           {"id": "grp", "group": "g1", "sha256": sha("other.png"), "path": tmp_path / "other.png"},
           {"id": "clean", "group": "g7", "sha256": sha("other.png"), "path": tmp_path / "other.png"}]
    hits = {(h["import"], h["rule"]) for h in CA.gate_v6(imp, prot)["hits"]}
    assert ("exact", "sha256") in hits and ("near", "near_duplicate") in hits and ("grp", "group") in hits
    assert not any(i == "clean" for i, _ in hits)
    assert CA.gate_v6(imp[3:], prot)["pass"]


def test_heldout_report_from_stored_predictions(tmp_path):
    from dsutil import read_csv
    pool = [r for sp in CV.POOL_SPLITS for r in read_csv(ROOT / "data" / "splits" / f"combined_{sp}.csv")]
    y = np.array([CLASSES.index(r["target_class"]) if r["target_class"] in CLASSES else -1 for r in pool])
    run = "CAND_f0_s42"
    (tmp_path / "runs").mkdir()
    ck = tmp_path / "best.pth"
    ck.write_bytes(b"fixture checkpoint bytes")
    shutil.copy2(ART / "runs" / "CV5_BASE_f0_s42__heldout_pred.npz", tmp_path / "runs" / f"{run}__heldout_pred.npz")
    cvr = json.loads((ART / "runs" / "CV5_BASE_f0_s42__cv_run.json").read_text())
    cvr["checkpoint_sha256"] = CV.sha256_file(ck)
    (tmp_path / "runs" / f"{run}__cv_run.json").write_text(json.dumps(cvr))
    (tmp_path / "checkpoint_manifest.json").write_text(json.dumps({run: {"sha256": CV.sha256_file(ck)}}))
    names = [f"runs/{run}__heldout_pred.npz", f"runs/{run}__cv_run.json", "checkpoint_manifest.json"]
    (tmp_path / "SHA256SUMS.txt").write_text("".join(f"{CV.sha256_file(tmp_path / n)}  {n}\n" for n in names))
    man = CA.training_manifest(run=run, fold=0, seed=42, cfg={"name": "CAND"}, fit_rows=[], inner_rows=[], imports=[],
                               checkpoint_path=ck, fold_file_sha256=CV.FOLD_FILE_SHA256, best_epoch=cvr["best_epoch"],
                               fit_arrays_sha256="0" * 64, inner_arrays_sha256="1" * 64)
    ref = CA.write_training_manifest(ck, man)
    tm = tmp_path / ref["file"]
    rep = CA.heldout_report(tmp_path, run, y, checkpoint_path=ck, training_manifest_path=tm, model_id="m", version="v")
    assert rep["checkpoint_sha256"] == CV.sha256_file(ck) and rep["no_new_inference"] and rep["disclosure"] == CA.DISCLOSURE
    assert rep["n_findings"] == 592 and rep["split"].startswith("held-out CV fold 0")
    fake = dict(man, cv={**man["cv"], "trainer": "fake_trainer:train"})          # a pre-flight (fake-trainer) manifest
    (tmp_path / "fake_manifest.json").write_text(json.dumps(fake))
    with pytest.raises(CA.AcceptError, match="pre-flight"):
        CA.heldout_report(tmp_path, run, y, checkpoint_path=ck, training_manifest_path=tmp_path / "fake_manifest.json",
                          model_id="m", version="v")
    with pytest.raises(CA.AcceptError):
        CA.heldout_report(tmp_path, "CAND_f1_s42", y, checkpoint_path=ck, training_manifest_path=tm, model_id="m", version="v")
    ck.write_bytes(b"different bytes")
    with pytest.raises(CA.AcceptError):
        CA.heldout_report(tmp_path, run, y, checkpoint_path=ck, training_manifest_path=tm, model_id="m", version="v")
