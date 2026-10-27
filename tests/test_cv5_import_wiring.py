"""Tests of the PROPOSED, UNAPPLIED import wiring patches/cv5_import_wiring.patch for the frozen kaggle/make_cv5_notebook.py.

The patch is applied only to a temporary copy of the generator; the frozen file is checked to stay byte-identical. The manifest-enabled
import cell is executed on SYNTHETIC fixtures (tests/test_cv5_imports.py world); no real data, label or training is involved."""
import dataclasses
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_cv5_import_manifest as BM  # noqa: E402
import cv5_imports as CIM  # noqa: E402
import cv5_interventions as CIV  # noqa: E402
import cv5_lib as CV  # noqa: E402
import dentamind_kaggle as DK  # noqa: E402
import make_cv5_notebook as NB  # noqa: E402
import run_cv5_import_v6 as V6  # noqa: E402
from test_cv5_imports import PROVENANCE, built, world  # noqa: E402,F401  (fixture)

PATCH = ROOT / "patches" / "cv5_import_wiring.patch"
FROZEN = ROOT / "kaggle" / "make_cv5_notebook.py"
FROZEN_SHA = "4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641"     # Amendment 01b
IMPORTS = {"manifest_sha256": "a" * 64, "v6_record_sha256": "b" * 64, "reviewer_authorization_sha256": "c" * 64,
           "input_dir": "/kaggle/input/dentamind-cv5-imports"}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cfg(cid="PAD25"):
    return dataclasses.asdict(CIV.proposed_config(cid))


@pytest.fixture(scope="module")
def patched(tmp_path_factory):
    """The generator with the patch applied, in a temporary tree that mirrors the files it embeds."""
    t = tmp_path_factory.mktemp("patched")
    for rel in ("kaggle/make_cv5_notebook.py", "kaggle/make_notebook.py", "kaggle/cv5_lib.py", "kaggle/cv5_accept.py",
                "kaggle/cv5_interventions.py", "kaggle/cv5_imports.py", "scripts/dataset/make_cv_folds.py", "data/splits/cv5_folds_v1.csv"):
        (t / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, t / rel)
    import os
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(t.parent)}           # never let git find an enclosing repository
    r = subprocess.run(["git", "apply", str(PATCH)], cwd=t, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert _sha(t / "kaggle" / "make_cv5_notebook.py") != FROZEN_SHA, "patch was not applied to the temporary copy"
    spec = importlib.util.spec_from_file_location("make_cv5_notebook_patched", t / "kaggle" / "make_cv5_notebook.py")
    mod = importlib.util.module_from_spec(spec)
    saved = list(sys.path)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
    return mod


# ---------------------------------------------------------------------------------------------------- the patch itself
def test_patch_targets_the_frozen_file_and_is_not_applied():
    assert _sha(FROZEN) == FROZEN_SHA
    r = subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr                                          # applies cleanly ...
    assert _sha(FROZEN) == FROZEN_SHA                                           # ... and --check changed nothing
    text = PATCH.read_text(encoding="utf-8")
    assert text.count("diff --git") == 1 and "b/kaggle/make_cv5_notebook.py" in text   # only the generator is touched


def test_default_output_is_byte_identical_to_the_frozen_generator(patched):
    assert patched.CELLS == NB.CELLS
    assert json.dumps(patched._notebook(patched.CELLS), indent=1, ensure_ascii=False) + "\n" == \
        (ROOT / "kaggle" / "dentamind_5fold_cv.ipynb").read_text(encoding="utf-8")               # BASE notebook unchanged
    for cid in CIV.PROPOSED:
        assert patched.candidate_cells(cid, cfg(cid)) == NB.candidate_cells(cid, cfg(cid))   # imports off: identical notebook
        assert patched.candidate_cells(cid, cfg(cid), None) == NB.candidate_cells(cid, cfg(cid))
    embed = next(s for k, s in patched.candidate_cells("PAD25", cfg()) if "EMBEDDED_SHA256" in s)
    assert "kaggle/cv5_imports.py" not in embed


# ---------------------------------------------------------------------------------------------------- import mode structure
def test_import_mode_cells(patched):
    base = NB.candidate_cells("CROP384", cfg("CROP384"))
    cells = patched.candidate_cells("CROP384", cfg("CROP384"), IMPORTS)
    assert len(cells) == len(base) + 1
    for k, s in cells:
        if k == "code":
            compile(s, "<cell>", "exec")
    i_det = next(i for i, (_, s) in enumerate(cells) if "CI.build_detector_crops(" in s)
    imp = cells[i_det + 1][1]
    assert imp.startswith("# ---- 6b. registered training imports")
    assert all(IMPORTS[k] in imp for k in IMPORTS)
    order = ["CIM.load_import_manifest(", "CIM.load_reviewer_authorization(", "CIM.check_reviewer_bindings(", "CIM.load_v6_record(", "CIM.verify_image_files(", "CIM.check_independence(",
             "CIM.gate_v6_for_manifest(", "CIM.augment_plans(", "CI.build_crops(IMP_ROWS"]
    pos = [imp.index(x) for x in order]
    assert pos == sorted(pos)                                                   # every check precedes the augmentation
    assert "DATA_ROOT / r[\"image_path\"]" in imp and "calibration" in imp and "no calibration / test image is read" in imp
    unchanged = [c for c in cells if c != cells[i_det + 1]]
    diff = [(a, b) for a, b in zip(base, unchanged) if a != b]
    changed = {next((m for m in ("EMBEDDED_SHA256", "CA.run_isolated(", "run evidence", "package artifacts") if m in a[1]), "?")
               for a, _ in diff}
    assert changed == {"EMBEDDED_SHA256", "CA.run_isolated(", "run evidence", "package artifacts"}   # nothing else differs
    train = next(s for _, s in cells if "CA.run_isolated(" in s)
    assert '[r for r in plan["fit"] if "import_source_id" in r]' in train
    embed = next(s for _, s in cells if "EMBEDDED_SHA256" in s)
    assert CV.sha256_file(ROOT / "kaggle" / "cv5_imports.py") in embed


@pytest.mark.parametrize("bad", [
    {**IMPORTS, "manifest_sha256": "A" * 64}, {**IMPORTS, "v6_record_sha256": "b" * 63}, {**IMPORTS, "input_dir": "/tmp/x"},
    {**IMPORTS, "input_dir": "/kaggle/input/../working"}, {k: v for k, v in IMPORTS.items() if k != "v6_record_sha256"},
    {**IMPORTS, "extra": 1}])
def test_import_parameters_are_validated(patched, bad):
    with pytest.raises(ValueError):
        patched.candidate_cells("PAD25", cfg(), bad)


def test_writer_requires_a_registration_naming_both_hashes(patched, tmp_path):
    reg01 = tmp_path / "a01.md"
    reg01.write_text("candidates: PAD25")
    with pytest.raises(ValueError, match="Amendment 02"):
        patched.write_candidate_notebook("PAD25", cfg(), reg01, tmp_path / "nb.ipynb", IMPORTS)
    reg02 = tmp_path / "a02.md"
    reg02.write_text(f"manifest {IMPORTS['manifest_sha256']}")                  # V6 record hash missing
    with pytest.raises(ValueError, match="Amendment 02"):
        patched.write_candidate_notebook("PAD25", cfg(), reg01, tmp_path / "nb.ipynb", IMPORTS, reg02)
    assert not (tmp_path / "nb.ipynb").exists()
    reg02.write_text(f"manifest {IMPORTS['manifest_sha256']} v6 {IMPORTS['v6_record_sha256']}")         # authorization missing
    with pytest.raises(ValueError, match="Amendment 02"):
        patched.write_candidate_notebook("PAD25", cfg(), reg01, tmp_path / "nb.ipynb", IMPORTS, reg02)
    reg02.write_text(" ".join(IMPORTS[k] for k in ("manifest_sha256", "v6_record_sha256", "reviewer_authorization_sha256")))
    out = patched.write_candidate_notebook("PAD25", cfg(), reg01, tmp_path / "nb.ipynb", IMPORTS, reg02)
    assert IMPORTS["manifest_sha256"] in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------------- executing the import cell
def _stage(world):
    """Synthetic Kaggle-like import folder: manifest + local V6 record + images (all fixtures)."""
    d = world["data"]
    m = built(world)
    BM.write_once(m, d / "import_manifest.json")
    msha = _sha(d / "import_manifest.json")
    loaded = CIM.load_import_manifest(d / "import_manifest.json", msha)
    other = world["tmp"] / "protected.png"
    from PIL import Image
    Image.fromarray(np.random.default_rng(5).integers(0, 256, (400, 800), dtype=np.uint8)).save(other)
    res = CIM.gate_v6_for_manifest(loaded, [{"id": "p", "group": "pg", "sha256": _sha(other), "path": other}], d)
    rec = CIM.make_v6_record(loaded, res, {"fixture": True})
    vsha = V6.write_once(rec, d / "import_v6_record.json")
    shutil.copy2(world["auth"], d / "reviewer_authorization.json")
    world["asha"] = _sha(d / "reviewer_authorization.json")
    return msha, vsha


def _globals(world, tmp_path, pool_images=None):
    """Notebook state just before the import cell, on a synthetic 2-fold frame (POOL = 6 synthetic findings on 3 radiographs)."""
    from PIL import Image
    data = tmp_path / "pool"
    (data / "img").mkdir(parents=True)
    rng = np.random.default_rng(11)
    pool = []
    for i in range(3):
        p = data / "img" / f"cv{i}.png"
        if pool_images and i in pool_images:
            Image.open(pool_images[i]).resize((790, 395), Image.BILINEAR).save(p)
        else:
            Image.fromarray(rng.integers(0, 256, (400, 800), dtype=np.uint8)).save(p)
        for j in range(2):
            pool.append({"sample_id": f"cv{i}_{j}", "image_path": f"img/cv{i}.png", "image_sha256": _sha(p),
                         "radiograph_group": f"cvg{i}", "source_dataset": "dentex_train_disease", "bbox_xywh": json.dumps([100 + 200 * j, 100, 80, 60]), "class_index": str(j)})
    plans = {0: {"fit": pool[:2], "inner": pool[2:4], "heldout": pool[4:], "heldout_secondary": []},
             1: {"fit": pool[4:], "inner": pool[:2], "heldout": pool[2:4], "heldout_secondary": []}}
    X, Y, _ = CIV.build_crops(pool, data, None, {})
    for d in ("art", "cache"):
        (tmp_path / d).mkdir(exist_ok=True)
    return {"np": np, "json": json, "Path": Path, "log": lambda *a: None, "DK": DK, "CI": CIV, "CV": CV, "ART": tmp_path / "art",
            "CACHE": tmp_path / "cache", "SPLITS": ROOT / "data" / "splits", "POOL": pool, "DATA_ROOT": data, "FOLDS": [0, 1],
            "PLANS": plans, "FOLD_OF": {f"cvg{i}": i % 2 for i in range(3)}, "CANDIDATE": {"extra": {}}, "X_ALL": X, "Y_ALL": Y,
            "IDX": {r["sample_id"]: i for i, r in enumerate(pool)}}


def _cell(patched, world, msha, vsha):
    imp = dict(IMPORTS, manifest_sha256=msha, v6_record_sha256=vsha, reviewer_authorization_sha256=world["asha"])
    cells = patched.candidate_cells("PAD25", cfg(), imp)
    src = next(s for _, s in cells if s.startswith("# ---- 6b."))
    return src.replace(f"IMPORT_DIR = Path({IMPORTS['input_dir']!r})", f"IMPORT_DIR = Path({str(world['data'])!r})")


def test_import_cell_adds_imports_to_fitting_parts_only(patched, world, tmp_path):
    msha, vsha = _stage(world)
    g = _globals(world, tmp_path)
    before = {k: {n: [r["sample_id"] for r in p[n]] for n in p} for k, p in g["PLANS"].items()}
    n_before = len(g["X_ALL"])
    exec(compile(_cell(patched, world, msha, vsha), "<6b>", "exec"), g)
    imported = [r["sample_id"] for r in g["IMP_ROWS"]]
    assert len(imported) == 4
    for k in (0, 1):
        p = g["PLANS"][k]
        assert [r["sample_id"] for r in p["fit"]] == before[k]["fit"] + imported
        for n in ("inner", "heldout", "heldout_secondary"):
            assert [r["sample_id"] for r in p[n]] == before[k][n]
    assert len(g["X_ALL"]) == n_before + 4 and len(g["Y_ALL"]) == n_before + 4
    Xi, Yi, _ = DK.build_crops(CIM.import_rows(g["IMPORTS"]), world["data"])
    assert np.array_equal(g["X_ALL"][[g["IDX"][s] for s in imported]], Xi) and np.array_equal(g["Y_ALL"][n_before:], Yi)
    chk = json.loads((g["ART"] / "import_check.json").read_text())
    assert chk["manifest_sha256"] == msha and chk["identity"]["hits"] == 0 and chk["v6_cv_pool"]["pass"]
    assert chk["image_files"]["images_verified"] == 3


def test_import_cell_refuses_wrong_hashes_tampered_images_and_cv_pool_twins(patched, world, tmp_path):
    msha, vsha = _stage(world)
    for m, v, match in (("c" * 64, vsha, "not the registered"), (msha, "d" * 64, "V6 record SHA-256")):
        with pytest.raises(CIM.ImportRefused, match=match):
            exec(compile(_cell(patched, world, m, v), "<6b>", "exec"), _globals(world, tmp_path / m[:2]))
    good = world["asha"]
    world["asha"] = "e" * 64                                                    # stale / unregistered authorization version
    with pytest.raises(CIM.ImportRefused, match="reviewer authorization SHA-256"):
        exec(compile(_cell(patched, world, msha, vsha), "<6b>", "exec"), _globals(world, tmp_path / "auth"))
    world["asha"] = good
    twin_src = world["data"] / "raw/syn/u1.png"                                 # a CV-pool radiograph that is a near-copy of an import
    g = _globals(world, tmp_path / "twin", pool_images={0: twin_src})
    with pytest.raises(CIM.ImportRefused, match="gate V6"):
        exec(compile(_cell(patched, world, msha, vsha), "<6b>", "exec"), g)
    img = world["data"] / "raw/syn/u2.png"
    img.write_bytes(img.read_bytes() + b"\0")                                    # imported image altered after registration
    with pytest.raises(CIM.ImportRefused, match="not byte-identical"):
        exec(compile(_cell(patched, world, msha, vsha), "<6b>", "exec"), _globals(world, tmp_path / "alt"))


# ---------------------------------------------------------------------------------------------------- local V6 record
def test_v6_record_rules(world):
    d = world["data"]
    msha, vsha = _stage(world)
    m = CIM.load_import_manifest(d / "import_manifest.json", msha)
    assert CIM.load_v6_record(d / "import_v6_record.json", vsha, m)["imported_images"] == 3
    with pytest.raises(CIM.ImportRefused):
        CIM.make_v6_record(m, {"pass": False, "hits": [{"x": 1}], "imports": 3}, {})
    with pytest.raises(CIM.ImportRefused, match="written once"):
        V6.write_once({}, d / "import_v6_record.json")
    rec = json.loads((d / "import_v6_record.json").read_text())
    rec["manifest_sha256"] = "e" * 64                                           # a record of another manifest
    other = world["tmp"] / "v6_other.json"
    other.write_text(json.dumps(rec))
    with pytest.raises(CIM.ImportRefused, match="does not belong"):
        CIM.load_v6_record(other, _sha(other), m)


def test_local_v6_script_checks_every_protected_split(world, tmp_path):
    """run_cv5_import_v6.run on a synthetic project: a test-split image that is a near-copy of an import is refused."""
    from PIL import Image
    d = world["data"]
    msha, _ = _stage(world)
    splits, data = tmp_path / "proj_splits", tmp_path / "proj"
    (data / "img").mkdir(parents=True)
    (data / "raw/syn").mkdir(parents=True)
    for n in ("t1", "e1"):                                                      # protected pool images (twin, eval_locked)
        shutil.copy2(d / f"raw/syn/{n}.png", data / f"raw/syn/{n}.png")
    splits.mkdir()
    rows = {}
    for i, s in enumerate(("train", "validation", "calibration", "test")):
        p = data / "img" / f"{s}.png"
        Image.fromarray(np.random.default_rng(100 + i).integers(0, 256, (400, 800), dtype=np.uint8)).save(p)
        rows[s] = [{"sample_id": f"{s}0", "radiograph_group": f"g_{s}", "image_sha256": _sha(p), "image_path": f"img/{s}.png"}]
    for s, rr in rows.items():
        BM_write = splits / f"combined_{s}.csv"
        BM_write.write_text("sample_id,radiograph_group,image_sha256,image_path\n" +
                            "".join(f"{r['sample_id']},{r['radiograph_group']},{r['image_sha256']},{r['image_path']}\n" for r in rr))
    with pytest.raises(CIM.ImportRefused, match="not found locally"):          # V6 refuses when a protected image is missing
        V6.protected_images(splits, world["ann"] / "pool.csv", tmp_path / "empty")
    rec = V6.run(d / "import_manifest.json", msha, splits, world["ann"] / "pool.csv", data, d)
    assert rec["result"]["pass"] and rec["protected"]["combined_test"] == 1
    Image.open(d / "raw/syn/u3.png").resize((790, 395), Image.BILINEAR).save(data / "img" / "test.png")   # test twin of an import
    rows["test"][0]["image_sha256"] = _sha(data / "img" / "test.png")
    (splits / "combined_test.csv").write_text("sample_id,radiograph_group,image_sha256,image_path\n"
                                             f"test0,g_test,{rows['test'][0]['image_sha256']},img/test.png\n")
    with pytest.raises(CIM.ImportRefused):
        V6.run(d / "import_manifest.json", msha, splits, world["ann"] / "pool.csv", data, d)
