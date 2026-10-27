"""Temperature-scaling module of the DRAFT calibration experiment (synthetic data only)."""
import numpy as np
import pytest

from dentexmodel.uncertainty.calibration import expected_calibration_error
from dentexmodel.uncertainty.temperature import fit_per_fold, fit_temperature, nll, softmax


def _data(t_true, n=4000, c=4, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 2.0, (n, c))
    y = np.array([rng.choice(c, p=softmax(base[i:i + 1])[0]) for i in range(n)])
    return base * t_true, y          # logits that are over-confident by factor t_true


def test_recovers_known_temperature():
    logits, y = _data(2.5)
    assert fit_temperature(logits, y) == pytest.approx(2.5, rel=0.08)


def test_reduces_nll_and_ece_but_never_changes_predictions():
    logits, y = _data(3.0, seed=1)
    t = fit_temperature(logits, y)
    assert nll(logits, y, t) < nll(logits, y, 1.0)
    assert expected_calibration_error(softmax(logits, t), y) < expected_calibration_error(softmax(logits), y)
    assert (softmax(logits, t).argmax(1) == softmax(logits).argmax(1)).all()


def test_per_fold_refuses_any_partition_but_inner_validation():
    logits, y = _data(1.5, n=500)
    assert set(fit_per_fold({0: {"partition": "inner_validation", "logits": logits, "labels": y}})) == {0}
    for bad in ("heldout", "test", "calibration", None):
        with pytest.raises(PermissionError):
            fit_per_fold({0: {"partition": bad, "logits": logits, "labels": y}})


def test_rejects_empty_or_mismatched_input():
    with pytest.raises(ValueError):
        fit_temperature(np.zeros((0, 4)), [])
    with pytest.raises(ValueError):
        fit_temperature(np.zeros((3, 4)), [0, 1])
