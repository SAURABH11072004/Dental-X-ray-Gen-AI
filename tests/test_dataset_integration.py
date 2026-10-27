"""Dataset-integration pipeline (scripts/dataset): label mapping, parsers, crop rule, duplicate detection, remote-zip reader and
the persisted combined manifests (split isolation, fixed evaluation sets)."""
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/dataset"))

import adapters  # noqa: E402
import dsutil  # noqa: E402
import remote_zip_list as RZ  # noqa: E402


# ------------------------------------------------------------------------------------------------------------ label mapping
def test_dentex_names_map_exactly():
    assert dsutil.canonical_finding("Caries", "dentex_en") == "Caries"
    assert dsutil.canonical_finding("Deep Caries", "dentex_en") == "Deep Caries"
    assert dsutil.canonical_finding("DeepCaries", "dentex_en") == "Deep Caries"
    assert dsutil.canonical_finding("Periapical Lesion", "dentex_en") == "Periapical Lesion"
    assert dsutil.canonical_finding("impacted", "dentex_en") == "Impacted"


@pytest.mark.parametrize("label", ["lesion", "radiolucency", "Infection", "healthy", "Filling", "", None, "Caries deep?"])
def test_generic_or_other_labels_are_not_mapped(label):
    assert dsutil.canonical_finding(label, "dentex_en") is None


def test_turkish_taxonomy_is_never_mapped():
    for lab in ("1-çürük", "2-küretaj", "6-gömülü", "7-lezyon", "0-saglam"):
        assert dsutil.canonical_finding(lab, "dentex_tr_labelme") is None


def test_unknown_taxonomy_raises():
    with pytest.raises(ValueError):
        dsutil.canonical_finding("Caries", "some_new_dataset")


# ---------------------------------------------------------------------------------------------------------------- parsers
def _coco(tmp_path, cat_order):
    cats3 = [{"id": i, "name": n} for i, n in enumerate(cat_order)]
    d = {"images": [{"id": 7, "file_name": "a.png", "width": 100, "height": 80}, {"id": 8, "file_name": "b.png", "width": 50, "height": 50}],
         "annotations": [
             {"id": 1, "image_id": 7, "bbox": [10, 10, 20, 20], "category_id_1": 0, "category_id_2": 5, "category_id_3": cat_order.index("Deep Caries")},
             {"id": 2, "image_id": 7, "bbox": [10, 10, 0, 20], "category_id_1": 1, "category_id_2": 0, "category_id_3": 0},
             {"id": 3, "image_id": 7, "bbox": [30, 30, 10, 10], "category_id_1": 3, "category_id_2": 7, "category_id_3": cat_order.index("Periapical Lesion")}],
         "categories_1": [{"id": i, "name": str(i + 1)} for i in range(4)],
         "categories_2": [{"id": i, "name": str(i + 1)} for i in range(8)], "categories_3": cats3}
    p = tmp_path / "x.json"
    p.write_text(json.dumps(d))
    return p


@pytest.mark.parametrize("order", [["Impacted", "Caries", "Periapical Lesion", "Deep Caries"],
                                   ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]])
def test_coco_parser_maps_by_name_not_id(tmp_path, order):
    imgs, recs = adapters.parse_dentex_coco(_coco(tmp_path, order), "dir", "src")
    by_id = {r["annotation_id"]: r for r in recs}
    assert by_id[1]["target_class"] == "Deep Caries" and by_id[1]["fdi_tooth"] == 16
    assert by_id[3]["target_class"] == "Periapical Lesion" and by_id[3]["fdi_tooth"] == 48
    assert by_id[2]["target_class"] is None and "degenerate" in by_id[2]["mapping_note"]       # zero-width box dropped
    assert imgs["b.png"]["n_annotations"] == 0                                                 # unannotated image: no records
    assert all(r["original_label"] is not None for r in recs)


def test_coco_parser_requires_disease_level(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(json.dumps({"images": [], "annotations": [], "categories_1": []}))
    with pytest.raises(ValueError):
        adapters.parse_dentex_coco(p, "d", "s")


def test_labelme_parser_keeps_labels_and_maps_nothing(tmp_path):
    d = {"shapes": [{"label": "7-lezyon-46", "points": [[1, 2], [11, 2], [11, 22]], "shape_type": "polygon"},
                    {"label": "1-çürük-26", "points": [[0, 0], [5, 5], [0, 5]], "shape_type": "polygon"}],
         "imagePath": "test_9.png", "imageWidth": 100, "imageHeight": 50}
    (tmp_path / "test_9.json").write_text(json.dumps(d), encoding="utf-8")
    _, recs = adapters.parse_labelme_tr(tmp_path, "dir", "t")
    assert [r["original_label"] for r in recs] == ["7-lezyon", "1-çürük"]
    assert [r["fdi_tooth"] for r in recs] == [46, 26]
    assert recs[0]["bbox_xywh"] == [1, 2, 10, 20]
    assert all(r["target_class"] is None for r in recs)


# -------------------------------------------------------------------------------------------------------------- crop rule
def test_crop_region_identical_to_production():
    from dentexmodel.training.trainers import crop_region as prod
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (300, 500, 3), dtype=np.uint8)
    boxes = [(10, 10, 60, 90), (0, 0, 3, 3), (480, 280, 520, 320), (100.4, 50.7, 101.9, 200.2), (-5, -5, 40, 40)]
    boxes += [tuple(rng.uniform(0, 500, 4)) for _ in range(30)]
    for b in boxes:
        b = (min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3]))
        a, p = dsutil.crop_region(img, b, 224), prod(img, b, 224)
        assert (a is None) == (p is None)
        if a is not None:
            assert np.array_equal(a, p)


def test_crop_box_geometry_matches_crop_rule():
    img = np.zeros((80, 100, 3), np.uint8)
    for bb in ([10, 10, 20, 20], [99, 79, 3, 3], [0, 0, 2, 2], [50, 50, 1, 30]):
        x1, y1, x2, y2 = dsutil.crop_box_xyxy(bb, 100, 80)
        ok = (x2 - x1) >= 4 and (y2 - y1) >= 4
        assert ok == (dsutil.crop_region(img, (bb[0], bb[1], bb[0] + bb[2], bb[1] + bb[3])) is not None)


# ---------------------------------------------------------------------------------------------------------- duplicates
def test_near_duplicate_two_stage_rule():
    a = np.random.default_rng(1).normal(size=(128, 256)).astype(np.float32)
    thumbs = {"x": a, "y": a * 1.0001 + 1e-4, "z": np.random.default_rng(2).normal(size=(128, 256)).astype(np.float32)}
    # (key, sha256, dhash, path); the thumbnail function receives the path, here the key itself
    items = [("x", "sha1", 0b1010, "x"), ("y", "sha2", 0b1011, "y"), ("z", "sha3", 0b1000, "z"), ("w", "sha1", 0b1010, "w")]
    norm = {k: (v - v.mean()) / v.std() for k, v in thumbs.items()}
    norm["w"] = norm["x"]
    conf, n_cand, _ = dsutil.near_duplicate_pairs(items, thumb_fn=lambda k: norm[k])
    keys = {frozenset(c[:2]) for c in conf}
    assert frozenset(("x", "y")) in keys                      # hash close + correlated -> confirmed
    assert all("z" not in k for k in keys)                    # hash close but uncorrelated -> rejected
    assert frozenset(("x", "w")) not in keys                  # identical SHA-256 is an exact duplicate, not a near duplicate
    assert n_cand >= 3


def test_dhash_stable_under_reencoding(tmp_path):
    from PIL import Image
    rng = np.random.default_rng(3)
    arr = (np.add.outer(np.arange(64), np.arange(128)) % 255).astype(np.uint8)
    arr = np.clip(arr + rng.integers(0, 5, arr.shape), 0, 255).astype(np.uint8)
    Image.fromarray(arr).save(tmp_path / "a.png")
    Image.fromarray(arr).save(tmp_path / "b.jpg", quality=92)
    assert bin(dsutil.dhash(tmp_path / "a.png") ^ dsutil.dhash(tmp_path / "b.jpg")).count("1") <= 4


# ------------------------------------------------------------------------------------------------------- remote zip reader
def _serve(monkeypatch, blob):
    def fake_get(url, start, end, retries=5):
        n = len(blob)
        s = start if start >= 0 else n + start
        return blob[s:end + 1], f"bytes {s}-{min(end, n - 1)}/{n}"
    monkeypatch.setattr(RZ, "_get", fake_get)


def test_remote_zip_list_and_fetch(monkeypatch, tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("d/label/a.json", json.dumps({"k": "ü" * 300}), compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("d/input/a.png", b"\x89PNG" + bytes(range(256)) * 10, compress_type=zipfile.ZIP_STORED)
        z.writestr("other/x.txt", b"no")
    blob = buf.getvalue()
    _serve(monkeypatch, blob)
    lst = RZ.list_remote_zip("u")
    assert [m["name"] for m in lst["members"]] == ["d/label/a.json", "d/input/a.png", "other/x.txt"]
    m = lst["members"][0]
    assert json.loads(RZ.fetch_member("u", m))["k"] == "ü" * 300
    assert RZ.extract_prefix("u", "d/", str(tmp_path), lst, log_every=0) == 2
    assert (tmp_path / "d/input/a.png").read_bytes() == b"\x89PNG" + bytes(range(256)) * 10
    assert not (tmp_path / "other").exists()
    bad = dict(m, crc32="00000000")
    with pytest.raises(ValueError):
        RZ.fetch_member("u", bad)


# -------------------------------------------------------------------------------------------------- persisted manifests
SPL = ROOT / "data/splits"
needs_manifests = pytest.mark.skipif(not (SPL / "combined_train.csv").is_file(), reason="run scripts/dataset/build_combined_manifest.py")


@needs_manifests
def test_combined_splits_are_isolated():
    rows = {s: dsutil.read_csv(SPL / f"combined_{s}.csv") for s in ("train", "validation", "calibration", "test")}
    names = list(rows)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            for key in ("radiograph_group", "image_sha256", "image_path"):
                assert not ({r[key] for r in rows[a]} & {r[key] for r in rows[b]}), (a, b, key)
    for s, rs in rows.items():
        for r in rs:
            assert dsutil.CLASSES[int(r["class_index"])] == r["target_class"]
            assert r["split"] == s
    # external data only in training; evaluation sets are pure DENTEX project splits
    for s in ("validation", "calibration", "test"):
        assert {r["source_dataset"] for r in rows[s]} == {"dentex_train_disease"}
    ids = [r["sample_id"] for rs in rows.values() for r in rs]
    assert len(ids) == len(set(ids))


@needs_manifests
def test_validation_and_test_equal_project_splits():
    split = json.loads((SPL / "dentex_splits.json").read_text(encoding="utf-8"))["assignments"]
    for name, proj in (("validation", "val"), ("test", "test"), ("calibration", "calibration")):
        rows = dsutil.read_csv(SPL / f"combined_{name}.csv")
        assert rows and all(split[r["project_image_id"]] == proj for r in rows)
    train = dsutil.read_csv(SPL / "combined_train.csv")
    assert all(split[r["project_image_id"]] == "train" for r in train if r["source_dataset"] == "dentex_train_disease")
    audit = json.loads((ROOT / "reports/combined_split_audit.json").read_text(encoding="utf-8"))
    assert audit["fixed_evaluation_sets"]["validation_identical_to_project_val"]
    assert audit["fixed_evaluation_sets"]["test_identical_to_project_test"]
    assert audit["leakage_checks"]["all_zero"]
    for name, h in audit["outputs_sha256"].items():          # manifests unchanged since the audit was written
        assert dsutil.sha256_file(SPL / name) == h, name


@needs_manifests
def test_no_official_test_labels_and_no_healthy_class():
    for s in ("train", "validation", "calibration", "test"):
        rows = dsutil.read_csv(SPL / f"combined_{s}.csv")
        assert all(r["source_dataset"] != "dentex_official_test" for r in rows)
        assert {r["target_class"] for r in rows} <= set(dsutil.CLASSES)
    excl = dsutil.read_csv(SPL / "combined_excluded.csv")
    assert any(r["source_dataset"] == "dentex_official_test" for r in excl)
