"""Tests for kaggle/cv5_interventions.py: candidate interventions C1 (384 px crops), C2 (0.25 context padding), C3 (ConvNeXt-Tiny).
Synthetic images only; no DENTEX image or label is read and no model is trained."""
import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset"):
    sys.path.insert(0, str(p))

import cv5_accept as CA  # noqa: E402
import cv5_interventions as CI  # noqa: E402
import cv5_lib as CV  # noqa: E402
import dentamind_kaggle as DK  # noqa: E402
import dsutil  # noqa: E402

torch = pytest.importorskip("torch")
tv = pytest.importorskip("torchvision")


# ---------------------------------------------------------------------------------------------------- BASE stays BASE
def test_base_code_and_recipe_are_unchanged():
    bundle = {"kaggle/dentamind_kaggle.py": "879faa93cb313b47", "scripts/dataset/dsutil.py": "debeb7f08f7e5176"}   # Kaggle bundle v3
    for f, h in bundle.items():
        assert CV.sha256_file(ROOT / f).startswith(h), f
    assert dataclasses.asdict(DK.EXPERIMENTS["BASE"]) == {
        "name": "BASE", "loss": "ce", "weights": "inverse_cap5", "sampler": "none", "data": "dentex", "gamma": 2.0, "beta": 0.999,
        "epochs": 15, "batch_size": 32, "lr": 3e-4, "wd": 1e-4, "hflip": 0.5, "contrast": 0.1,
        "note": "current recipe (C0r): inverse-frequency weights capped at 5", "extra": {}}
    assert (DK.CROP_SIZE, DK.CROP_PAD, dsutil.CROP_SIZE, dsutil.CROP_PAD) == (224, 0.10, 224, 0.10)
    assert CI.DEFAULTS == {"crop_size": 224, "crop_pad": 0.10, "backbone": "resnet50"}


def test_resolve_and_single_intervention_gate():
    assert CI.resolve({}) == CI.DEFAULTS
    for bad in ({"crop_sz": 384}, {"crop_size": 384.0}, {"crop_size": True}, {"crop_size": 8}, {"crop_pad": -0.1},
                {"crop_pad": 1.5}, {"backbone": "vit_b_16"}):
        with pytest.raises(CI.InterventionError):
            CI.resolve(bad)
    with pytest.raises(CI.InterventionError):                                     # BASE itself is not a candidate
        CI.check_single_intervention(DK.EXPERIMENTS["BASE"])
    fam = {"CROP384": ("crop_size", "F1", 384), "PAD25": ("crop_pad", "F1", 0.25), "CNXTT": ("backbone", "F2", "convnext_tiny")}
    for cid, (k, f, v) in fam.items():
        cfg = CI.proposed_config(cid)
        assert CI.check_single_intervention(cfg) == {"key": k, "family": f, "value": v}
        assert CA.trainer_for(cfg) == CI.TRAINER == CA.INTERVENTION_TRAINER
    two = dataclasses.replace(DK.EXPERIMENTS["BASE"], extra={"crop_size": 384, "crop_pad": 0.25})
    lr = dataclasses.replace(CI.proposed_config("PAD25"), lr=1e-4)
    for cfg in (two, lr):
        with pytest.raises(CI.InterventionError):
            CI.check_single_intervention(cfg)
    assert CA.trainer_for(DK.EXPERIMENTS["BASE"]) == CA.DEFAULT_TRAINER
    noop = dataclasses.replace(DK.EXPERIMENTS["BASE"], extra={"crop_size": 224})  # explicit default is no intervention
    with pytest.raises(CI.InterventionError):
        CI.check_single_intervention(noop)


# ---------------------------------------------------------------------------------------------------- crops (C1, C2)
def _img(path, arr):
    from PIL import Image
    Image.fromarray(arr).save(path)


def _row(i, path, box, cls=0):
    x, y, w, h = box
    return {"sample_id": f"s{i}", "image_path": path, "bbox_xywh": json.dumps([x, y, w, h]), "class_index": str(cls),
            "source_dataset": "dentex_train_disease", "radiograph_group": f"g_{path}", "project_image_id": path}


@pytest.fixture()
def images(tmp_path):
    rng = np.random.default_rng(0)
    H, W = 300, 600
    gx = np.tile(np.linspace(0, 255, W).astype(np.uint8), (H, 1))            # value encodes the column
    _img(tmp_path / "grad.png", np.stack([gx] * 3, -1))
    _img(tmp_path / "rand.png", rng.integers(0, 256, (H, W, 3), dtype=np.uint8))
    _img(tmp_path / "a.png", np.full((H, W, 3), 50, np.uint8))
    _img(tmp_path / "b.png", np.full((H, W, 3), 200, np.uint8))
    rows = [_row(0, "rand.png", (100, 80, 120, 60)), _row(1, "rand.png", (0, 0, 40, 30), 1),            # top-left corner
            _row(2, "rand.png", (560, 270, 40, 30), 2), _row(3, "grad.png", (200, 100, 100, 50), 3),    # bottom-right corner
            _row(4, "a.png", (580, 10, 20, 20)), _row(5, "b.png", (0, 280, 20, 20))]
    return tmp_path, rows, (H, W)


def test_default_crops_are_byte_identical_to_base(images):
    root, rows, _ = images
    Xb, yb, mb = DK.build_crops(rows, root)
    Xc, yc, mc = CI.build_crops(rows, root, None, {})
    assert Xb.shape == (len(rows), 224, 224, 3) and np.array_equal(Xb, Xc) and np.array_equal(yb, yc) and mb == mc
    assert (DK.CROP_SIZE, DK.CROP_PAD) == (224, 0.10)


def test_c1_crops_384(images):
    root, rows, _ = images
    X, y, _ = CI.build_crops(rows, root, None, {"crop_size": 384})
    assert X.shape == (len(rows), 384, 384, 3) and X.dtype == np.uint8
    assert (DK.CROP_SIZE, DK.CROP_PAD) == (224, 0.10)                           # restored
    from PIL import Image
    img = np.asarray(Image.open(root / "rand.png").convert("RGB"))
    for i in range(3):                                                          # same region as BASE, only resampled
        x, y_, w, h = json.loads(rows[i]["bbox_xywh"])
        assert np.array_equal(X[i], dsutil.crop_region(img, (x, y_, x + w, y_ + h), 384, 0.10))
    Xb, _, _ = DK.build_crops(rows, root)
    down = np.stack([np.asarray(Image.fromarray(c).resize((224, 224), Image.BILINEAR)) for c in X]).astype(int)
    assert np.abs(down - Xb.astype(int)).mean() < 12                           # box alignment: same region at two resolutions


def test_c2_padding_geometry_and_clipping(images):
    root, rows, (H, W) = images
    X, _, _ = CI.build_crops(rows, root, None, {"crop_pad": 0.25})
    assert X.shape == (len(rows), 224, 224, 3)
    g = X[3, :, :, 0].astype(float)                                             # gradient image: value = 255 * col / (W - 1)
    x1, x2 = 200 - 0.25 * 100, 300 + 0.25 * 100                                 # 175 .. 325 (inside the image)
    assert abs(g[:, 0].mean() - 255 * x1 / (W - 1)) < 2 and abs(g[:, -1].mean() - 255 * x2 / (W - 1)) < 2
    gb, _, _ = DK.build_crops(rows[3:4], root)
    assert abs(gb[0, :, 0, 0].mean() - 255 * (200 - 10) / (W - 1)) < 2         # BASE pad 0.10 -> 190
    from PIL import Image
    img = np.asarray(Image.open(root / "rand.png").convert("RGB"))
    for i, box in ((1, (0, 0, 40, 40 * 0 + 30)), (2, (560, 270, 600, 300))):    # corners: region clipped to the image
        x, y_, w, h = json.loads(rows[i]["bbox_xywh"])
        assert np.array_equal(X[i], dsutil.crop_region(img, (x, y_, x + w, y_ + h), 224, 0.25))
    x, y_, w, h = 0, 0, 40, 30
    cx1, cy1, cx2, cy2 = max(0, x - 0.25 * w), max(0, y_ - 0.25 * h), min(W, x + w + 0.25 * w), min(H, y_ + h + 0.25 * h)
    assert (cx1, cy1) == (0, 0) and cx2 == 50 and cy2 == 37.5


def test_padding_never_mixes_radiographs(images):
    root, rows, _ = images
    for extra in ({}, {"crop_pad": 0.25}, {"crop_size": 384}):
        X, _, _ = CI.build_crops(rows, root, None, extra)
        assert np.all(X[4] == 50) and np.all(X[5] == 200)                       # each crop only contains its own image's pixels


def test_crop_cache_name_must_carry_the_crop_rule(images, tmp_path):
    root, rows, _ = images
    with pytest.raises(CI.InterventionError):
        CI.build_crops(rows, root, tmp_path / "pool_gt.npz", {"crop_size": 384})
    f = tmp_path / f"pool_gt_{CI.crop_tag({'crop_size': 384})}.npz"
    X1, _, _ = CI.build_crops(rows, root, f, {"crop_size": 384})
    X2, _, _ = CI.build_crops(rows, root, f, {"crop_size": 384})               # cache hit
    assert np.array_equal(X1, X2) and CI.crop_tag({}) == "s224_p0.10" and CI.crop_tag({"crop_pad": 0.25}) == "s224_p0.25"


def test_crop_rule_restores_constants_on_error(images):
    root, rows, _ = images
    bad = [dict(rows[0], image_path="missing.png")]
    with pytest.raises(Exception):
        CI.build_crops(bad, root, None, {"crop_size": 384})
    assert (DK.CROP_SIZE, DK.CROP_PAD) == (224, 0.10)


def test_detector_crops_follow_the_crop_rule(images, tmp_path):
    root, rows, _ = images
    det = {r["project_image_id"]: [] for r in rows}
    for r in rows[:3]:
        x, y, w, h = json.loads(r["bbox_xywh"])
        det[r["project_image_id"]].append([x + 1, y + 1, x + w + 1, y + h, 0.9])     # IoU >= 0.5 with the GT box
    (tmp_path / "det.json").write_text(json.dumps(det))
    key = lambda r: r["project_image_id"]                                        # noqa: E731
    Xb, mb, nb = DK.build_detector_crops(rows, root, tmp_path / "det.json", key)
    Xd, md, nd = CI.build_detector_crops(rows, root, tmp_path / "det.json", key, {})
    assert np.array_equal(Xb, Xd) and np.array_equal(mb, md) and nb == nd == 3
    X3, m3, n3 = CI.build_detector_crops(rows, root, tmp_path / "det.json", key, {"crop_size": 384})
    assert X3.shape == (3, 384, 384, 3) and np.array_equal(m3, mb) and (DK.CROP_SIZE, DK.CROP_PAD) == (224, 0.10)


# ---------------------------------------------------------------------------------------------------- models (C3)
def test_base_model_and_predictions_unchanged():
    torch.manual_seed(0)
    a = DK.new_model(torch, tv, pretrained=False)
    torch.manual_seed(0)
    b = CI.new_model(torch, tv, {}, pretrained=False)
    sa, sb = a.state_dict(), b.state_dict()
    assert sa.keys() == sb.keys() and all(torch.equal(sa[k], sb[k]) for k in sa)
    X = np.random.default_rng(1).integers(0, 256, (3, 224, 224, 3), dtype=np.uint8)
    pa, pb = DK.predict(torch, a, X, torch.device("cpu")), DK.predict(torch, b, X, torch.device("cpu"))
    assert np.array_equal(pa, pb) and pa.shape == (3, 4)


def test_convnext_tiny_shapes_classes_and_checkpoint_roundtrip(tmp_path):
    m = CI.new_model(torch, tv, {"backbone": "convnext_tiny"}, pretrained=False)
    assert type(m).__name__ == "ConvNeXt" and m.classifier[2].out_features == len(DK.CLASSES) == 4
    assert 27e6 < sum(p.numel() for p in m.parameters()) < 29e6
    cpu = torch.device("cpu")
    for size in (224, 384):
        X = np.random.default_rng(size).integers(0, 256, (2, size, size, 3), dtype=np.uint8)
        p = DK.predict(torch, m, X, cpu)
        assert p.shape == (2, 4) and np.allclose(p.sum(1), 1, atol=1e-5)
    ck = tmp_path / "best.pth"
    torch.save(m.state_dict(), ck)
    m2 = CI.new_model(torch, tv, {"backbone": "convnext_tiny"}, pretrained=False)
    m2.load_state_dict(torch.load(ck, map_location="cpu", weights_only=True), strict=True)
    X = np.random.default_rng(3).integers(0, 256, (2, 224, 224, 3), dtype=np.uint8)
    assert np.array_equal(DK.predict(torch, m, X, cpu), DK.predict(torch, m2, X, cpu))
    with pytest.raises(RuntimeError):                                          # a ConvNeXt checkpoint never loads into BASE
        CI.new_model(torch, tv, {}, pretrained=False).load_state_dict(torch.load(ck, weights_only=True), strict=True)


def test_model_rule_restores_dk_new_model():
    orig = DK.new_model
    with CI.model_rule({"backbone": "convnext_tiny"}):
        assert type(DK.new_model(torch, tv, pretrained=False)).__name__ == "ConvNeXt"
    assert DK.new_model is orig


def test_model_rule_with_resnet_backbone_does_not_recurse():
    """C1 / C2 keep ResNet-50: DK.train_run's new_model call must build exactly the BASE model, not recurse."""
    with CI.model_rule({"crop_size": 384}):
        torch.manual_seed(0)
        a = DK.new_model(torch, tv, pretrained=False)
    torch.manual_seed(0)
    b = DK.new_model(torch, tv, pretrained=False)
    assert type(a).__name__ == "ResNet" and all(torch.equal(x, y) for x, y in zip(a.state_dict().values(), b.state_dict().values()))


# ---------------------------------------------------------------------------------------------------- trainer
def test_base_config_delegates_to_the_unchanged_trainer(monkeypatch):
    seen = {}
    monkeypatch.setattr(DK, "train_run", lambda cfg, seed, train, val, out_dir, log=print: seen.setdefault("base", (cfg.name, seed)))
    CI.train_run(DK.EXPERIMENTS["BASE"], 42, {"X": np.zeros((1, 224, 224, 3))}, {"X": np.zeros((1, 224, 224, 3))}, ".")
    assert seen["base"] == ("BASE", 42)


def test_candidate_trainer_builds_the_backbone_and_records_provenance(monkeypatch, tmp_path):
    seen = {}

    def fake_train(cfg, seed, train, val, out_dir, log=print):
        m = DK.new_model(torch, tv)                                            # what DK.train_run calls
        seen.update(model=type(m).__name__, crop=(DK.CROP_SIZE, DK.CROP_PAD))
        out = Path(out_dir) / f"{cfg.name}_s{seed}"
        out.mkdir(parents=True)
        ck = out / "best.pth"
        ck.write_bytes(b"w")
        ck.with_suffix(".json").write_text(json.dumps({"architecture": "resnet50", "image_size": DK.CROP_SIZE, "crop_pad": DK.CROP_PAD}))
        return {"checkpoint": str(ck), "config": dataclasses.asdict(cfg)}

    monkeypatch.setattr(DK, "train_run", fake_train)
    monkeypatch.setattr(CI, "new_model", lambda torch_, tv_, extra, pretrained=True:
                        tv_.models.convnext_tiny(weights=None) if CI.resolve(extra)["backbone"] == "convnext_tiny"
                        else CI.BASE_NEW_MODEL(torch_, tv_, pretrained=False))
    orig = DK.new_model
    cfg = dataclasses.replace(CI.proposed_config("CNXTT"), name="CV5_CNXTT_f0")
    X = {"X": np.zeros((2, 224, 224, 3), np.uint8)}
    res = CI.train_run(cfg, 42, X, X, tmp_path)
    assert seen == {"model": "ConvNeXt", "crop": (224, 0.10)} and DK.new_model is orig
    side = json.loads(Path(res["checkpoint"]).with_suffix(".json").read_text())
    assert side["architecture"] == "convnext_tiny" and side["intervention"] == {"backbone": "convnext_tiny"}
    cfg1 = dataclasses.replace(CI.proposed_config("CROP384"), name="CV5_CROP384_f0")
    with pytest.raises(CI.InterventionError):                                  # 224 px arrays with a 384 px rule: refused
        CI.train_run(cfg1, 42, X, X, tmp_path)
    X384 = {"X": np.zeros((2, 384, 384, 3), np.uint8)}
    res = CI.train_run(cfg1, 42, X384, X384, tmp_path)
    side = json.loads(Path(res["checkpoint"]).with_suffix(".json").read_text())
    assert seen["crop"] == (384, 0.10) and side["image_size"] == 384 and side["intervention"] == {"crop_size": 384}
    assert (DK.CROP_SIZE, DK.CROP_PAD) == (224, 0.10)


def test_preflight_trainer_is_never_a_real_trainer():
    import make_cv5_notebook as NB
    assert "cv5_preflight_trainer:train" not in CA.REAL_TRAINERS
    cells = NB.candidate_cells("CROP384", dataclasses.asdict(CI.proposed_config("CROP384")))
    embed = next(s for k, s in cells if "EMBEDDED_SHA256" in s)
    assert "kaggle/cv5_preflight_trainer.py" not in embed and "kaggle/cv5_interventions.py" in embed
    for cid in CI.PROPOSED:
        code = "\n".join(s for k, s in NB.candidate_cells(cid, dataclasses.asdict(CI.proposed_config(cid)))
                         if k == "code" and "EMBEDDED_SHA256" not in s)                 # embedded sources excluded
        assert "CI.build_crops(" in code and "CI.build_detector_crops(" in code and "CI.new_model(torch, tv, CANDIDATE" in code
        assert "DK.build_crops(" not in code and "DK.build_detector_crops(" not in code and "DK.new_model(" not in code


# ---------------------------------------------------------------------------------------------------- candidate code bundle
def test_candidate_bundle_is_versioned_and_never_overwrites(tmp_path):
    import zipfile
    import build_candidate_bundle as BB
    base = tmp_path / "base.zip"
    with zipfile.ZipFile(base, "w") as z:
        z.writestr("BUNDLE_MANIFEST.json", json.dumps({"built": "x", "files": {f: CV.sha256_file(ROOT / f) for f in BB.RELIES_ON}}))
    m = BB.build(7, dist=tmp_path, base_bundle=base)
    out = tmp_path / "dentamind_cv5_candidate_code_v7.zip"
    with zipfile.ZipFile(out) as z:
        man = json.loads(z.read("CANDIDATE_BUNDLE_MANIFEST.json"))
        assert all(hashlib_sha(z.read(f)) == h for f, h in man["files"].items())
        assert not any(n.endswith((".pth", ".png", ".jpg")) for n in z.namelist())
    assert m["bundle_sha256"] == CV.sha256_file(out) and "kaggle/cv5_interventions.py" in man["files"]
    with pytest.raises(SystemExit):                                            # same version again: refused
        BB.build(7, dist=tmp_path, base_bundle=base)
    drift = tmp_path / "drift.zip"
    with zipfile.ZipFile(drift, "w") as z:
        z.writestr("BUNDLE_MANIFEST.json", json.dumps({"files": {f: "0" * 64 for f in BB.RELIES_ON}}))
    with pytest.raises(SystemExit):                                            # base-bundle code changed: refused
        BB.build(8, dist=tmp_path, base_bundle=drift)


def hashlib_sha(b: bytes) -> str:
    import hashlib
    return hashlib.sha256(b).hexdigest()
