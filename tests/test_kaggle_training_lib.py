"""kaggle/dentamind_kaggle.py: training-only class weights, sampler, losses, metrics, acceptance rule, checkpoint save/resume and
compatibility with the production classifier construction."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts", ROOT / "scripts/dataset"):
    sys.path.insert(0, str(p))

import dentamind_kaggle as DK  # noqa: E402

torch = pytest.importorskip("torch")
COUNTS = [1550, 438, 412, 120]


# ----------------------------------------------------------------------------------------------------------- class weights
def test_inverse_cap5_equals_existing_experiment_code():
    import ml_cls_train
    for counts in (COUNTS, [1635, 467, 448, 129], [10, 10, 10, 10], [1000, 10, 50, 3]):
        np.testing.assert_allclose(DK.class_weights(counts, "inverse_cap5"), ml_cls_train.class_weights(counts, "weights"), rtol=1e-12)
        np.testing.assert_allclose(DK.class_weights(counts, "sqrt"), ml_cls_train.class_weights(counts, "weights_sqrt"), rtol=1e-12)


@pytest.mark.parametrize("scheme", ["inverse_cap5", "sqrt", "effective_number"])
def test_weights_normalised_capped_and_ordered(scheme):
    w = DK.class_weights(COUNTS, scheme)
    assert np.isclose((w * np.array(COUNTS)).sum(), sum(COUNTS))          # average sample weight 1
    raw = sum(COUNTS) / (4 * np.array(COUNTS, float))
    assert w.max() / w.min() <= raw.max() / raw.min() + 1e-9                # the cap (applied before renormalising) only shrinks ratios
    assert w[3] >= w[1] >= w[0] and w[3] > w[0]                            # rarer class never gets a smaller weight
    assert DK.class_weights(COUNTS, "none") is None


def test_weights_need_every_class():
    with pytest.raises(ValueError):
        DK.class_weights([5, 0, 3, 1], "inverse_cap5")


@pytest.mark.skipif(not (ROOT / "data/splits/combined_train.csv").is_file(), reason="manifests not built")
def test_weights_come_from_training_rows_only():
    tr = DK.load_split(ROOT / "data/splits", "train")
    va = DK.load_split(ROOT / "data/splits", "validation")
    y_tr = np.array([int(r["class_index"]) for r in tr if r["source_dataset"] == "dentex_train_disease"])
    assert np.bincount(y_tr, minlength=4).tolist() == COUNTS                # the audited training counts
    y_both = np.concatenate([y_tr, [int(r["class_index"]) for r in va]])
    assert not np.allclose(DK.class_weights(np.bincount(y_tr), "inverse_cap5"), DK.class_weights(np.bincount(y_both), "inverse_cap5"))


# --------------------------------------------------------------------------------------------------------------- sampler
def test_sampler_stays_in_training_indices_and_rebalances():
    y = np.repeat([0, 1, 2, 3], COUNTS)
    rng = np.random.default_rng(0)
    draws = np.concatenate([DK.sampler_indices(y, rng) for _ in range(20)])
    assert draws.min() >= 0 and draws.max() < len(y)
    share = np.bincount(y[draws], minlength=4) / len(draws)
    expected = np.sqrt(COUNTS) / np.sqrt(COUNTS).sum()                    # p ~ n^-0.5 per sample -> class share ~ sqrt(n)
    np.testing.assert_allclose(share, expected, atol=0.01)
    exp = DK.sampler_exposure(y)
    assert exp["Periapical Lesion"] < 3.0                                  # bounded repetition: < 3 draws per PL crop per epoch
    assert np.isclose(sum(exp[c] * n for c, n in zip(DK.CLASSES, COUNTS)), len(y), rtol=1e-3)   # values rounded to 3 decimals


# ---------------------------------------------------------------------------------------------------------------- losses
def test_focal_loss_reduces_to_ce_and_downweights_easy():
    g = torch.Generator().manual_seed(0)
    lo = torch.randn(64, 4, generator=g)
    t = torch.randint(0, 4, (64,), generator=g)
    ce = torch.nn.functional.cross_entropy(lo, t)
    assert torch.isclose(DK.focal_loss(torch, lo, t, gamma=0.0), ce)
    assert DK.focal_loss(torch, lo, t, gamma=2.0) < ce
    easy = torch.tensor([[10.0, 0, 0, 0]])
    assert DK.focal_loss(torch, easy, torch.tensor([0]), 2.0) < 1e-6 * torch.nn.functional.cross_entropy(easy, torch.tensor([0])) + 1e-9


# --------------------------------------------------------------------------------------------------------------- metrics
def test_report_counts_and_abstention():
    y = np.array([0, 0, 1, 1, 2, 3, 3, 3])
    p = np.array([0, 1, 1, 1, 2, 3, 0, 3])
    prob = np.full((8, 4), 0.02)
    prob[np.arange(8), p] = 0.94
    prob[1] = [0.3, 0.3, 0.2, 0.2]                                          # uncertain -> abstains under the production rule
    r = DK.report(y, p, prob)
    assert r["confusion"][3] == [1, 0, 0, 2]
    assert r["per_class"]["Deep Caries"]["precision"] == pytest.approx(2 / 3)
    assert r["per_class"]["Caries"]["false_positives"] == 1
    assert r["macro_f1"] == pytest.approx(np.mean([v["f1"] for v in r["per_class"].values()]))
    ab = r["abstention_production_rule"]
    assert ab["abstained"] == 1 and ab["accepted"] == 7


def test_matching_is_one_to_one_greedy():
    gt = [[0, 0, 10, 10], [20, 0, 30, 10], [100, 100, 110, 110]]
    pred = [[1, 0, 11, 10], [0, 0, 10, 9], [21, 0, 31, 10]]
    m = DK.match(gt, pred)
    assert m[0][0] == 1 and m[1][0] == 2 and 2 not in m
    assert len({j for j, _ in m.values()}) == len(m)


def _fake_eval(f1_det, rec_dc=0.5, rec_pl=0.6, prec=0.6, f1_gt=None):
    pc = {c: {"precision": prec, "recall": {"Deep Caries": rec_dc, "Periapical Lesion": rec_pl}.get(c, 0.9), "f1": 0.7} for c in DK.CLASSES}
    return {"det_matched": {"macro_f1": f1_det, "per_class": pc}, "gt": {"macro_f1": f1_gt if f1_gt is not None else f1_det, "per_class": pc}}


def test_acceptance_rule():
    base = {s: _fake_eval(0.70 + 0.001 * s) for s in range(5)}
    good = {s: _fake_eval(0.75 + 0.001 * s, 0.55, 0.65) for s in range(5)}
    assert DK.acceptance(good, base)["pass"]
    small = {s: _fake_eval(0.71 + 0.001 * s, 0.55, 0.65) for s in range(5)}       # gain 0.01 < 0.027
    assert not DK.acceptance(small, base)["pass"]
    recall_drop = {s: _fake_eval(0.75 + 0.001 * s, 0.40, 0.65) for s in range(5)}  # macro-F1 up but Deep Caries recall down
    a = DK.acceptance(recall_drop, base)
    assert not a["pass"] and not a["criteria"]["2_minority_recall_not_lower"]
    prec_drop = {s: _fake_eval(0.75 + 0.001 * s, 0.55, 0.65, prec=0.45) for s in range(5)}   # many more false positives
    assert not DK.acceptance(prec_drop, base)["criteria"]["5_minority_precision_drop_le_0.10"]
    assert not DK.acceptance({0: good[0]}, base)["pass"]                           # too few seeds


# -------------------------------------------------------------------------------------------- save / resume (tiny model)
class Tiny(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.c = torch.nn.Conv2d(3, 4, 5, stride=4)
        self.fc = torch.nn.Linear(4, 4)

    def forward(self, x):
        return self.fc(self.c(x).mean((2, 3)))


def _data(n=24, seed=0):
    r = np.random.default_rng(seed)
    return {"X": r.integers(0, 255, (n, 32, 32, 3), dtype=np.uint8), "y": np.arange(n) % 4}


def test_train_resume_is_identical_to_uninterrupted(monkeypatch, tmp_path):
    monkeypatch.setattr(DK, "new_model", lambda torch_, tv, pretrained=True: Tiny())
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    cfg = DK.ExpConfig("T", epochs=3, batch_size=8)
    tr, va = _data(), _data(12, 1)
    full = DK.train_run(cfg, 1, tr, va, tmp_path / "a", log=lambda *a: None)

    calls = {"n": 0}
    real = DK.predict

    def crash_once(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:                      # dies during epoch 2 validation, after epoch 1 was checkpointed
            raise KeyboardInterrupt
        return real(*a, **k)
    monkeypatch.setattr(DK, "predict", crash_once)
    with pytest.raises(KeyboardInterrupt):
        DK.train_run(cfg, 1, tr, va, tmp_path / "b", log=lambda *a: None)
    assert (tmp_path / "b/T_s1/state.pt").is_file() and not (tmp_path / "b/T_s1/result.json").exists()
    monkeypatch.setattr(DK, "predict", real)
    resumed = DK.train_run(cfg, 1, tr, va, tmp_path / "b", log=lambda *a: None)
    assert [round(h["train_loss"], 6) for h in resumed["history"]] == [round(h["train_loss"], 6) for h in full["history"]]
    assert resumed["checkpoint_sha256"] == full["checkpoint_sha256"]
    assert not (tmp_path / "b/T_s1/state.pt").exists()                       # cleaned up after completion
    again = DK.train_run(cfg, 1, tr, va, tmp_path / "b", log=lambda *a: None)  # finished runs are skipped
    assert again["checkpoint_sha256"] == full["checkpoint_sha256"]
    side = json.loads((tmp_path / "b/T_s1/best.json").read_text())
    assert side["promoted"] is False and side["class_names"] == DK.CLASSES and side["checkpoint_sha256_full"] == full["checkpoint_sha256"]


def test_sampler_and_focal_runs_train(monkeypatch, tmp_path):
    monkeypatch.setattr(DK, "new_model", lambda torch_, tv, pretrained=True: Tiny())
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    for cfg in (DK.ExpConfig("S", sampler="sqrt_inverse", weights="none", epochs=1, batch_size=8),
                DK.ExpConfig("F", loss="focal", weights="none", epochs=1, batch_size=8)):
        r = DK.train_run(cfg, 0, _data(), _data(8, 2), tmp_path, log=lambda *a: None)
        assert np.isfinite(r["history"][0]["train_loss"])


# ------------------------------------------------------------------------------------------------ production compatibility
def test_candidate_format_loads_with_production_construction(tmp_path):
    tv = pytest.importorskip("torchvision")
    from dentexmodel.inference.registry import validate_sidecar
    from dentexmodel.inference.torch_models import _load_state
    m = DK.new_model(torch, tv, pretrained=False)
    torch.save(m.state_dict(), tmp_path / "c.pth")
    prod = tv.models.resnet50(weights=None)
    prod.fc = torch.nn.Linear(prod.fc.in_features, 4)
    prod.load_state_dict(_load_state(torch, str(tmp_path / "c.pth"), torch.device("cpu")), strict=True)
    side = {"task": "classification", "architecture": "resnet50", "class_names": DK.CLASSES, "num_classes": 4}
    assert validate_sidecar(side) == []


def test_deployed_checkpoint_loads_into_training_architecture():
    ck = ROOT / "data/checkpoints/dentex_findings_classification_v1.pth"
    if not ck.is_file():
        pytest.skip("deployed checkpoint not present")
    tv = pytest.importorskip("torchvision")
    m = DK.new_model(torch, tv, pretrained=False)
    m.load_state_dict(torch.load(ck, map_location="cpu", weights_only=True), strict=True)


def test_notebook_cells_parse():
    import ast
    nb = json.loads((ROOT / "kaggle/denta_mind_training.ipynb").read_text(encoding="utf-8"))
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code) >= 10
    for c in code:
        ast.parse("".join(c["source"]))
    src = "".join("".join(c["source"]) for c in code)
    for must in ("verify_images", "acceptance", "train_run", "dentamind_balanced_training_artifacts.zip", "SHA256SUMS.txt", "RUN_TEST_EVAL"):
        assert must in src


# ------------------------------------------------------------------------------------------- process-isolated training
def test_isolated_run_trains_in_subprocess_and_skips_when_done(tmp_path):
    pytest.importorskip("torchvision")
    r = np.random.default_rng(5)
    tr = DK.save_arrays(tmp_path / "tr.npz", {"X": r.integers(0, 255, (16, 64, 64, 3), dtype=np.uint8), "y": np.arange(16) % 4})
    va = DK.save_arrays(tmp_path / "va.npz", {"X": r.integers(0, 255, (8, 64, 64, 3), dtype=np.uint8), "y": np.arange(8) % 4})
    cfg = DK.ExpConfig("ISO", epochs=1, batch_size=8)
    logs = []
    res = DK.train_run_isolated(cfg, 3, tr, va, tmp_path / "runs", log=logs.append)
    assert not res.get("failed"), res
    assert (tmp_path / "runs/ISO_s3/best.pth").is_file() and res["best_epoch"] == 1
    again = DK.train_run_isolated(cfg, 3, tr, va, tmp_path / "runs", log=logs.append)
    assert again["checkpoint_sha256"] == res["checkpoint_sha256"] and any("skipped" in l for l in logs)


def test_isolated_run_records_failure_and_does_not_raise(tmp_path):
    cfg = DK.ExpConfig("BAD", epochs=1)
    res = DK.train_run_isolated(cfg, 1, tmp_path / "missing.npz", tmp_path / "missing_val.npz", tmp_path / "runs",
                                log=lambda *a: None, attempts=2)
    assert res["failed"] and len(res["errors"]) == 2
    assert json.loads((tmp_path / "runs/BAD_s1/failure.json").read_text())[0]["returncode"] != 0


def test_ce_partial_equals_cross_entropy_without_partial_labels():
    import torch
    torch.manual_seed(0)
    lo, y = torch.randn(16, 4), torch.randint(0, 4, (16,))
    w = torch.tensor([0.4, 1.4, 1.5, 5.0])
    assert torch.allclose(DK.ce_partial(torch, lo, y, w), torch.nn.functional.cross_entropy(lo, y, weight=w))
    assert torch.allclose(DK.ce_partial(torch, lo, y), torch.nn.functional.cross_entropy(lo, y))


def test_ce_partial_caries_any_is_log_of_summed_probability():
    import torch
    lo = torch.tensor([[2.0, 1.0, -1.0, 0.0], [0.0, 0.0, 3.0, 0.0]])
    y = torch.tensor([DK.PARTIAL_CARIES, 2])
    w = torch.tensor([0.5, 2.0, 1.0, 4.0])
    p = torch.softmax(lo, 1)
    l0, l1 = -torch.log(p[0, 0] + p[0, 1]), -torch.log(p[1, 2])
    want = (0.5 * l0 + 1.0 * l1) / (0.5 + 1.0)            # partial sample carries the Caries weight
    assert torch.allclose(DK.ce_partial(torch, lo, y, w), want)


def test_class_counts_ignore_partial_labels():
    import numpy as np
    assert DK.class_counts(np.array([0, 0, 1, 3, DK.PARTIAL_CARIES, DK.PARTIAL_CARIES])).tolist() == [2, 1, 0, 1]
