"""Train/inference consistency and edge cases of the classification path (synthetic images only; no evaluation data, no labels).

Guards the assumption behind every reported number: the deployed inference path feeds the classifier exactly the crops and
normalisation it was trained with (CV5 / Kaggle training: kaggle/dentamind_kaggle.py; production: src/dentexmodel)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import dentamind_kaggle as DK  # noqa: E402
import dsutil  # noqa: E402

from dentexmodel.data.preprocess import load_gray  # noqa: E402
from dentexmodel.errors import ModelUnavailableError  # noqa: E402
from dentexmodel.inference.registry import classifier_preprocessing_problems  # noqa: E402
from dentexmodel.inference.torch_models import _normalize, _prep_crops  # noqa: E402
from dentexmodel.training.trainers import crop_region as prod_crop_region  # noqa: E402
from dentexmodel.uncertainty.calibration import expected_calibration_error  # noqa: E402

GOOD = {"task": "classification", "crop_pad": 0.10, "image_size": 224,
        "normalize": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}}


def _info(meta):
    return SimpleNamespace(metadata=meta, model_id="fixture/classifier.pth")


def _panoramic(tmp_path, rgb_equal=True, seed=0):
    rng = np.random.default_rng(seed)
    g = rng.integers(0, 256, (300, 600), dtype=np.uint8)
    a = np.stack([g, g, g], 2) if rgb_equal else rng.integers(0, 256, (300, 600, 3), dtype=np.uint8)
    p = tmp_path / ("eq.png" if rgb_equal else "col.png")
    Image.fromarray(a, "RGB").save(p)
    return p


# ------------------------------------------------------------------------------- preprocessing must be stated, never guessed
def test_complete_sidecar_has_no_preprocessing_problems():
    assert classifier_preprocessing_problems(GOOD) == []


@pytest.mark.parametrize("change", [
    {"crop_pad": None}, {"crop_pad": 1.0}, {"crop_pad": -0.1}, {"crop_pad": True}, {"crop_pad": "0.1"},
    {"image_size": None}, {"image_size": 224.0}, {"image_size": 8},
    {"normalize": None}, {"normalize": {"mean": [0.5, 0.5], "std": [0.2, 0.2, 0.2]}},
    {"normalize": {"mean": [0.5, 0.5, 0.5], "std": [0.2, 0.0, 0.2]}}, {"normalize": {"mean": [0.5, 0.5, 0.5]}}])
def test_incomplete_or_invalid_preprocessing_is_reported(change):
    meta = {**GOOD, **change}
    meta = {k: v for k, v in meta.items() if v is not None}
    assert classifier_preprocessing_problems(meta)


def test_inference_refuses_to_guess_preprocessing():
    img = np.zeros((100, 100, 3), np.float32)
    for missing in ("crop_pad", "normalize", "image_size"):
        meta = {k: v for k, v in GOOD.items() if k != missing}
        with pytest.raises(ModelUnavailableError) as e:
            _prep_crops(img, [[10, 10, 50, 50]], _info(meta), 224)
        assert e.value.code == "sidecar_preprocessing_missing"


def test_deployed_sidecar_states_the_cv5_training_preprocessing():
    side = json.loads((ROOT / "Data" / "checkpoints" / "dentex_findings_classification_v1.json").read_text(encoding="utf-8"))
    assert classifier_preprocessing_problems(side) == []
    assert side["crop_pad"] == DK.CROP_PAD == dsutil.CROP_PAD and side["image_size"] == DK.CROP_SIZE == dsutil.CROP_SIZE
    assert tuple(side["normalize"]["mean"]) == DK.MEAN and tuple(side["normalize"]["std"]) == DK.STD
    assert side["class_names"] == DK.CLASSES


# ------------------------------------------------------------------------------- identical inputs at training and inference
def test_inference_crops_equal_training_crops_for_dentex_style_images(tmp_path):
    """DENTEX panoramics are RGB with three equal channels (all 755 local images checked on 2026-10-25). For such images the
    inference loader (grayscale -> 3 channels, float 0-1) must give byte-identical crops to the training loader (RGB uint8)."""
    p = _panoramic(tmp_path)
    train_img = np.asarray(Image.open(p).convert("RGB"))
    infer_img = np.repeat(load_gray(p)[..., None], 3, axis=2)
    boxes = [[10, 20, 90, 150], [300.4, 50.6, 380.2, 260.9], [550, 200, 640, 330], [0, 0, 600, 300]]
    ok, crops = _prep_crops(infer_img, boxes, _info(GOOD), 224)
    assert ok == [0, 1, 2, 3]
    for c, b in zip(crops, boxes):
        assert np.array_equal(c, dsutil.crop_region(train_img, b, 224, 0.10))


def test_training_and_production_crop_rules_are_identical(tmp_path):
    img = np.asarray(Image.open(_panoramic(tmp_path)).convert("RGB"))
    for b in ([10, 20, 90, 150], [-5, -5, 30, 30], [590, 290, 700, 400], [100.5, 100.5, 103.0, 103.0]):
        a, c = dsutil.crop_region(img, b, 224, 0.10), prod_crop_region(img, b, 224, 0.10)
        assert (a is None and c is None) or np.array_equal(a, c)


def test_colour_uploads_are_reduced_to_grayscale_at_inference(tmp_path):
    """Documented limitation (not a DENTEX issue): a colour image is converted to grayscale at inference, while training never
    saw colour images. The pipeline therefore cannot be assumed valid for non-radiograph or colour-processed uploads."""
    p = _panoramic(tmp_path, rgb_equal=False)
    infer_img = np.repeat(load_gray(p)[..., None], 3, axis=2)
    assert np.array_equal(infer_img[..., 0], infer_img[..., 2])
    assert not np.array_equal(np.asarray(Image.open(p).convert("RGB")), (infer_img * 255).round().astype(np.uint8))


def test_normalisation_matches_training():
    torch = pytest.importorskip("torch")
    x = np.random.default_rng(1).integers(0, 256, (3, 224, 224, 3), dtype=np.uint8)
    dev = torch.device("cpu")
    prod = _normalize(torch, x, _info(GOOD), dev)
    train = DK.norm(torch, torch.from_numpy(x).permute(0, 3, 1, 2).float() / 255.0, dev)
    assert torch.equal(prod, train)


# ------------------------------------------------------------------------------- metric and matching definitions
def test_cv5_ece_equals_the_app_ece():
    rng = np.random.default_rng(2)
    logits = rng.normal(0, 2, (2000, 4))
    prob = np.exp(logits) / np.exp(logits).sum(1, keepdims=True)
    prob[:4] = [[0.5, 0.5, 0, 0], [0.3, 0.3, 0.2, 0.2], [0.7, 0.1, 0.1, 0.1], [1.0, 0, 0, 0]]   # confidences on bin edges
    y = rng.integers(0, 4, 2000)
    cv5 = DK.report(y, prob.argmax(1), prob)["ece_10bin"]
    assert cv5 == pytest.approx(expected_calibration_error(prob, y, n_bins=10), abs=1e-12)


def test_matching_edge_cases():
    assert DK.match([], [[0, 0, 10, 10]]) == {} and DK.match([[0, 0, 10, 10]], []) == {}
    assert DK.match([[0, 0, 10, 10]], [[0, 0, 10, 20]]) == {0: (0, 0.5)}            # IoU exactly 0.5 is a match
    assert DK.match([[0, 0, 10, 10]], [[0, 0, 10, 20.1]]) == {}                      # IoU 100/201 < 0.5 is not
    assert DK.match([[5, 5, 5, 5]], [[5, 5, 5, 5]]) == {}                             # zero-area boxes never match
    m = DK.match([[0, 0, 10, 10], [0, 0, 10, 10]], [[0, 0, 10, 10]])                 # one box, two findings: one-to-one
    assert len(m) == 1


def test_crop_region_edge_cases():
    img = np.zeros((100, 200, 3), np.uint8)
    assert dsutil.crop_region(img, [10, 10, 12, 12], 224, 0.10) is None              # < 4 px after padding
    c = dsutil.crop_region(img, [-50, -50, 300, 300], 224, 0.10)                    # clipped to the image
    assert c.shape == (224, 224, 3) and c.dtype == np.uint8
    assert dsutil.crop_region(img, [250, 150, 300, 200], 224, 0.10) is None          # entirely outside the image
