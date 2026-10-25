"""Tests for kaggle/ensemble_eval.py (5-seed BASE ensemble, protocol reports/ensemble_protocol.md)."""
import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset"):
    sys.path.insert(0, str(p))

import dentamind_kaggle as DK  # noqa: E402
import ensemble_eval as EV  # noqa: E402
from dsutil import CLASSES  # noqa: E402


def _probs(n, seed):
    rng = np.random.default_rng(seed)
    z = rng.random((n, len(CLASSES))) + 1e-3
    return z / z.sum(1, keepdims=True)


# ---------------------------------------------------------------------------------------------------- probability averaging
def test_average_is_elementwise_mean_and_a_distribution():
    ps = [_probs(7, s) for s in range(5)]
    avg = EV.average_probs(ps)
    assert np.allclose(avg, sum(ps) / 5)
    assert np.allclose(avg.sum(1), 1.0)


def test_average_does_not_depend_on_member_order():
    ps = [_probs(9, s) for s in range(5)]
    assert np.allclose(EV.average_probs(ps), EV.average_probs(ps[::-1]))


def test_average_of_identical_members_is_that_member():
    p = _probs(4, 0)
    assert np.allclose(EV.average_probs([p] * 5), p)


def test_average_can_change_the_argmax_majority_vote_would_not():
    # two members confidently say class 0, three members weakly say class 1 -> mean probability picks class 0
    strong0 = np.array([[0.98, 0.01, 0.005, 0.005]])
    weak1 = np.array([[0.30, 0.40, 0.15, 0.15]])
    avg = EV.average_probs([strong0, strong0, weak1, weak1, weak1])
    assert avg.argmax(1)[0] == 0


@pytest.mark.parametrize("bad", [
    [],
    [np.ones((3, 3)) / 3],                                     # wrong number of classes
    [_probs(3, 0), _probs(4, 1)],                              # different number of rows
    [_probs(3, 0), np.full((3, 4), 0.5)],                      # rows do not sum to 1
    [_probs(3, 0), np.array([[np.nan, 0.5, 0.25, 0.25]] * 3)],  # non-finite
])
def test_average_rejects_invalid_member_outputs(bad):
    with pytest.raises(EV.EnsembleError):
        EV.average_probs(bad)


# ---------------------------------------------------------------------------------------------------- class ordering
def test_class_order_is_the_deployed_order():
    assert list(CLASSES) == ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
    EV.check_class_order(["Caries", "Deep Caries", "Impacted", "Periapical Lesion"])


def test_permuted_class_order_is_rejected():
    with pytest.raises(EV.EnsembleError):
        EV.check_class_order(["Deep Caries", "Caries", "Impacted", "Periapical Lesion"])


def test_member_with_wrong_number_of_outputs_is_rejected(tmp_path):
    torch = pytest.importorskip("torch")
    tv = pytest.importorskip("torchvision")
    m = DK.new_model(torch, tv, pretrained=False)
    m.fc = torch.nn.Linear(m.fc.in_features, len(CLASSES) + 1)
    p = tmp_path / "five_classes.pth"
    torch.save(m.state_dict(), p)
    with pytest.raises(EV.EnsembleError):
        EV.load_member(p, torch, tv, torch.device("cpu"))


# ---------------------------------------------------------------------------------------------------- missing checkpoints
def _fake_members(tmp_path, seeds=(42, 43, 44, 45, 46)):
    members = {}
    for s in seeds:
        p = tmp_path / f"BASE_s{s}.pth"
        p.write_bytes(f"weights {s}".encode())
        members[s] = hashlib.sha256(p.read_bytes()).hexdigest()
    return members


def test_all_members_present_and_hashes_match(tmp_path):
    members = _fake_members(tmp_path)
    got = EV.verify_members(tmp_path, members)
    assert sorted(got) == sorted(members)


def test_missing_member_stops_evaluation(tmp_path):
    members = _fake_members(tmp_path)
    (tmp_path / "BASE_s44.pth").unlink()
    with pytest.raises(EV.EnsembleError, match="BASE_s44: missing"):
        EV.verify_members(tmp_path, members)


def test_modified_member_stops_evaluation(tmp_path):
    members = _fake_members(tmp_path)
    (tmp_path / "BASE_s45.pth").write_bytes(b"other weights")
    with pytest.raises(EV.EnsembleError, match="BASE_s45: sha256"):
        EV.verify_members(tmp_path, members)


def test_registered_members_are_the_five_base_seeds():
    assert sorted(EV.MEMBERS) == [42, 43, 44, 45, 46]
    assert all(len(h) == 64 for h in EV.MEMBERS.values())
    assert len(set(EV.MEMBERS.values())) == 5


# ---------------------------------------------------------------------------------------------------- reproducibility
def test_macro_f1_matches_the_project_report_definition():
    rng = np.random.default_rng(3)
    for _ in range(20):
        y = rng.integers(0, 4, 60)
        p = np.where(rng.random(60) < 0.7, y, rng.integers(0, 4, 60))
        assert EV.macro_f1(y, p) == pytest.approx(DK.report(y, p)["macro_f1"])


def test_member_predictions_are_deterministic():
    torch = pytest.importorskip("torch")
    tv = pytest.importorskip("torchvision")
    torch.manual_seed(0)
    m = DK.new_model(torch, tv, pretrained=False)
    X = np.random.default_rng(0).integers(0, 255, (3, 224, 224, 3), dtype=np.uint8)
    a = DK.predict(torch, m, X, torch.device("cpu"))
    b = DK.predict(torch, m, X, torch.device("cpu"))
    assert np.array_equal(a, b)
    assert np.allclose(a.sum(1), 1.0, atol=1e-5)


def test_bootstrap_is_reproducible_with_its_seed():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 4, 80)
    ens = np.where(rng.random(80) < 0.8, y, 0)
    mem = [np.where(rng.random(80) < 0.7, y, 1) for _ in range(5)]
    a = EV.bootstrap_diff(y, ens, mem, n_boot=200, seed=0)
    b = EV.bootstrap_diff(y, ens, mem, n_boot=200, seed=0)
    assert a == b
    assert a["ci95"][0] <= a["mean"] <= a["ci95"][1]


# ---------------------------------------------------------------------------------------------------- gates
def _rep(macro, per_class):
    return {"macro_f1": macro, "per_class": {c: {"precision": p, "recall": r, "f1": f} for c, (p, r, f) in per_class.items()}}


def _setting(macro, dc=(0.6, 0.5, 0.55), pl=(0.5, 0.7, 0.58)):
    pc = {"Caries": (0.89, 0.89, 0.89), "Deep Caries": dc, "Impacted": (0.93, 0.94, 0.935), "Periapical Lesion": pl}
    return {"gt": _rep(macro + 0.02, pc), "det_matched": _rep(macro, pc)}


def test_acceptance_passes_a_clear_gain_and_fails_otherwise():
    members = {s: _setting(m) for s, m in zip((42, 43, 44, 45, 46), (0.70, 0.74, 0.70, 0.75, 0.76))}
    good = _setting(0.80, dc=(0.62, 0.52, 0.57), pl=(0.52, 0.72, 0.60))
    assert EV.ensemble_acceptance(good, members)["pass"]
    small = _setting(0.74, dc=(0.62, 0.52, 0.57), pl=(0.52, 0.72, 0.60))
    r = EV.ensemble_acceptance(small, members)
    assert not r["pass"] and not r["criteria"]["1_gain_gt_0.027_and_beats_4_of_5"]
    lower_pl = _setting(0.80, dc=(0.62, 0.52, 0.57), pl=(0.60, 0.60, 0.60))
    r = EV.ensemble_acceptance(lower_pl, members)
    assert not r["pass"] and not r["criteria"]["2_minority_recall_not_lower"]


def test_reproduction_check_uses_the_tolerance():
    local = {42: {"gt": {"macro_f1": 0.744}, "det_matched": {"macro_f1": 0.701}}}
    assert EV.reproduction_check(local, {"42": {"gt": {"macro_f1": 0.7444}, "det_matched": {"macro_f1": 0.7009}}})["pass"]
    assert not EV.reproduction_check(local, {"42": {"gt": {"macro_f1": 0.7444}, "det_matched": {"macro_f1": 0.69}}})["pass"]
