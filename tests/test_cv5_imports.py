"""Tests for kaggle/cv5_imports.py and scripts/dataset/build_cv5_import_manifest.py (CV5 training imports, DRAFT Amendment 02).

Everything clinical here is a SYNTHETIC test fixture (images, pool, reviewer, review log, provenance) in a temp folder. The real
fold file, split manifests and class-count report are only read. No label, manifest or count for the project is created."""
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset"):
    sys.path.insert(0, str(p))

import build_cv5_import_manifest as BM  # noqa: E402
import build_reviewer_authorization as BRA  # noqa: E402
import clinical_review as CR  # noqa: E402
import cv5_imports as IM  # noqa: E402
import cv5_lib as CV  # noqa: E402
from dsutil import CLASSES, read_csv  # noqa: E402

SPLITS = ROOT / "data" / "splits"
PROVENANCE = {"syn_source": {f: f"fixture {f}" for f in IM.SOURCE_FIELDS}}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture()
def world(tmp_path):
    """Synthetic annotation world: 3 unassigned radiographs, 1 'train'-locked twin, 1 eval_locked; one registered reviewer."""
    from PIL import Image
    data = tmp_path / "data"
    (data / "raw/syn").mkdir(parents=True)
    rng = np.random.default_rng(0)
    pool = []
    for i, (name, lock) in enumerate((("u1", "unassigned"), ("u2", "unassigned"), ("u3", "unassigned"), ("t1", "train"),
                                      ("e1", "eval_locked"))):
        p = data / f"raw/syn/{name}.png"
        Image.fromarray(rng.integers(0, 256, (400, 800), dtype=np.uint8)).save(p)
        pool.append({"pool_id": f"P{i}", "source_dataset": "syn_source", "image_id": name, "image_path": f"raw/syn/{name}.png",
                     "image_sha256": _sha(p), "radiograph_group": f"syn_g{i}", "split_lock": lock})
    ann = tmp_path / "ann"
    ann.mkdir()
    _write_csv(ann / "pool.csv", pool, list(pool[0]))
    _write_csv(ann / "reviewers.csv", [{"reviewer_id": "R1", "display_name": "Fixture Reviewer", "qualification": "fixture",
                                        "registration_no": "x", "ls_user": "r1@test", "attested_by": "fixture", "attested_on": "2026-10-25"}],
               CR.REVIEWER_FIELDS)
    splits = tmp_path / "splits"
    splits.mkdir()
    for s in ("validation", "calibration", "test"):
        _write_csv(splits / f"combined_{s}.csv", [{"image_sha256": "f" * 64}], ["image_sha256"])
    log = ann / "clinical_reviews.jsonl"
    regions = [("P0", "r1", "Periapical Lesion", [100, 100, 160, 150]), ("P0", "r2", "Deep Caries", [300, 120, 360, 170]),
               ("P1", "r1", "Deep Caries", [200, 200, 260, 260]), ("P2", "r1", "Periapical Lesion", [50, 300, 120, 360]),
               ("P3", "r1", "Deep Caries", [400, 100, 460, 160]), ("P4", "r1", "Periapical Lesion", [500, 100, 560, 160])]
    for pid, rid, label, box in regions:
        pr = next(r for r in pool if r["pool_id"] == pid)
        CR._append(log, {"type": "review", "pool_id": pid, "image_id": pr["image_id"], "image_sha256": pr["image_sha256"],
                         "source_dataset": "syn_source", "split_lock": pr["split_lock"], "region_id": rid, "label": label,
                         "decision": "confirmed", "fdi": "", "box_xyxy": box, "notes": "", "coverage": None, "reviewer_id": "R1",
                         "reviewer_user": "r1@test", "reviewed_at": "2026-10-25T00:00:00Z", "status": "accepted_label", "problems": []})
    CR._append(log, {"type": "review", "pool_id": "P2", "image_id": "u3", "image_sha256": pool[2]["image_sha256"],
                     "source_dataset": "syn_source", "split_lock": "unassigned", "region_id": "r9", "label": None, "decision": "uncertain",
                     "fdi": "", "box_xyxy": [10, 10, 40, 40], "notes": "", "coverage": None, "reviewer_id": "R1", "reviewer_user": "r1@test",
                     "reviewed_at": "2026-10-25T00:00:00Z", "status": "recorded_not_a_label", "problems": []})
    CR.export_verified(out=ann / "verified_findings.csv", log=log, pool_csv=ann / "pool.csv", splits_dir=splits)
    args = (ann / "verified_findings.csv", log, ann / "reviewers.csv", ann / "pool.csv", splits, data)
    auth = ann / "reviewer_authorization_v1.json"                               # fixture authorization (internal ids only)
    BRA.write_once(BRA.build(ann / "reviewers.csv", 1, "fixture issuer"), auth)
    return {"tmp": tmp_path, "data": data, "ann": ann, "splits": splits, "pool": pool, "log": log, "args": args, "auth": auth}


def built(world, **kw):
    return BM.build(*world["args"], copy.deepcopy(PROVENANCE), world["auth"], **kw)


def written(world, m=None, name="m.json"):
    m = m or built(world)
    out = world["tmp"] / name
    return out, BM.write_once(m, out)


# ---------------------------------------------------------------------------------------------------- building and loading
def test_builder_imports_only_verified_unassigned_findings(world):
    m = built(world)
    ids = {f["sample_id"] for f in m["findings"]}
    assert ids == {"clinician:P0:r1", "clinician:P0:r2", "clinician:P1:r1", "clinician:P2:r1"}
    assert any(e["row"] == "clinician:P3:r1" and "split_lock 'train'" in e["reason"] for e in m["excluded"])   # CV-specific
    assert not any("P4" in f["sample_id"] for f in m["findings"])                                              # eval_locked
    for f in m["findings"]:
        assert f["verification"]["status"] == "accepted_label" and f["verification"]["reviewer_id"] == "R1"
        assert f["split_lock"] == "unassigned" and f["source_id"] in m["sources"]
    assert m["inputs"]["review_log_sha256"] == _sha(world["log"])


def test_manifest_is_immutable_and_must_match_its_registered_hash(world):
    out, h = written(world)
    m = IM.load_import_manifest(out, h, reviewer_ids={"R1"})
    assert m["_summary"]["findings"] == 4 and m["_summary"]["radiographs"] == 3
    with pytest.raises(IM.ImportRefused, match="immutable"):
        BM.write_once(built(world), out)
    with pytest.raises(IM.ImportRefused, match="not the registered"):
        IM.load_import_manifest(out, "0" * 64)
    with pytest.raises(IM.ImportRefused, match="registered SHA-256"):
        IM.load_import_manifest(out, None)
    with pytest.raises(IM.ImportRefused, match="does not exist"):
        IM.load_import_manifest(world["tmp"] / "missing.json", h)
    j = json.loads(out.read_text())                                            # edited after building: refused even if re-hashed
    j["findings"][0]["target_class"] = "Caries"
    j["findings"][0]["class_index"] = 0
    out2 = world["tmp"] / "edited.json"
    out2.write_text(json.dumps(j))
    with pytest.raises(IM.ImportRefused, match="edited after it was built"):
        IM.load_import_manifest(out2, _sha(out2))


def test_default_is_disabled():
    assert IM.load_import_manifest(None, None) is None
    with pytest.raises(IM.ImportRefused):
        IM.load_import_manifest(None, "a" * 64)
    plans = {0: {"fit": [1], "inner": [2], "heldout": [3], "heldout_secondary": []}}
    assert IM.augment_plans(plans, None, {}) is plans
    assert IM.import_counts(None) == {c: {"findings": 0, "radiographs": 0} for c in CLASSES}


def test_builder_refuses_missing_inputs_broken_chain_and_missing_provenance(world):
    with pytest.raises(IM.ImportRefused, match="no provenance"):
        BM.build(*world["args"], {}, world["auth"])
    a = list(world["args"])
    a[0] = world["tmp"] / "nope.csv"
    with pytest.raises(IM.ImportRefused, match="required input missing"):
        BM.build(*a, PROVENANCE, world["auth"])
    lines = world["log"].read_text().splitlines()
    lines[0] = lines[0].replace('"confirmed"', '"corrected"')                  # tamper with the review log
    world["log"].write_text("\n".join(lines) + "\n")
    with pytest.raises(IM.ImportRefused, match="hash-chain"):
        built(world)


def _rehash(m):
    m["content_sha256"] = IM.content_sha256(m["findings"], m["sources"])
    return m


@pytest.mark.parametrize("mutate, msg", [
    (lambda m: m["findings"][0]["verification"].update(status="recorded_not_a_label"), "not an accepted clinician label"),
    (lambda m: m["findings"][0]["verification"].update(decision="uncertain"), "not an accepted clinician label"),
    (lambda m: m["findings"][0]["verification"].update(reviewer_id=""), "incomplete clinician-verification"),
    (lambda m: m["findings"][0].update(label_source=""), "missing fields"),
    (lambda m: m["sources"]["syn_source"].update(licence=""), "missing provenance / licence"),
    (lambda m: m["findings"][0].update(source_id="other"), "has no provenance record"),
    (lambda m: m["findings"][0].update(split_lock="train"), "only 'unassigned'"),
    (lambda m: m["findings"][1].update(sample_id=m["findings"][0]["sample_id"]), "duplicate sample_id"),
    (lambda m: m["findings"][1].update(bbox_xywh=m["findings"][0]["bbox_xywh"], image_sha256=m["findings"][0]["image_sha256"],
                                       radiograph_group=m["findings"][0]["radiograph_group"], image_path=m["findings"][0]["image_path"]),
     "duplicate finding"),
    (lambda m: m["findings"][1].update(image_sha256=m["findings"][2]["image_sha256"]), "two radiograph groups"),
    (lambda m: m["findings"][0].update(target_class="Healthy"), "invalid"),
])
def test_validation_rejects(world, mutate, msg):
    m = built(world)
    mutate(m)
    with pytest.raises(IM.ImportRefused, match=msg):
        IM.validate_manifest(_rehash(m), reviewer_ids={"R1"})


def test_unregistered_reviewer_and_empty_manifest_rejected(world):
    with pytest.raises(IM.ImportRefused, match="not registered"):
        IM.validate_manifest(built(world), reviewer_ids={"R2"})
    m = built(world)
    m["findings"] = []
    with pytest.raises(IM.ImportRefused, match="no findings"):
        IM.validate_manifest(_rehash(m))


# ---------------------------------------------------------------------------------------------------- independence
@pytest.fixture(scope="module")
def project():
    rows = {s: read_csv(SPLITS / f"combined_{s}.csv") for s in ("train", "validation", "calibration", "test")}
    pool = [r for s in CV.POOL_SPLITS for r in rows[s]]
    fold_of = CV.load_folds(SPLITS / "cv5_folds_v1.csv")
    return rows, pool, fold_of


def test_independence_rejects_shared_groups_and_images(world, project):
    rows, pool, _ = project
    prot = IM.protected_identities(rows, world["pool"])
    m = built(world)
    assert IM.check_independence(m, prot)["hits"] == 0
    for field, value in (("image_sha256", rows["test"][0]["image_sha256"]), ("radiograph_group", pool[0]["radiograph_group"]),
                         ("image_sha256", rows["calibration"][0]["image_sha256"]), ("radiograph_group", world["pool"][4]["radiograph_group"])):
        bad = copy.deepcopy(m)
        bad["findings"][0][field] = value
        with pytest.raises(IM.ImportRefused, match="share a radiograph group or image"):
            IM.check_independence(bad, prot)


def test_gate_v6_rejects_near_duplicate_of_protected_image(world):
    from PIL import Image
    m = built(world)
    src = world["data"] / m["findings"][0]["image_path"]
    twin = world["tmp"] / "protected_twin.png"
    Image.open(src).resize((790, 395), Image.BILINEAR).save(twin)              # re-encoded / resized copy, different bytes
    other = world["tmp"] / "protected_other.png"
    Image.fromarray(np.random.default_rng(9).integers(0, 256, (400, 800), dtype=np.uint8)).save(other)
    clean = [{"id": "o", "group": "pg", "sha256": _sha(other), "path": other}]
    assert IM.gate_v6_for_manifest(m, clean, world["data"])["pass"]
    with pytest.raises(IM.ImportRefused, match="gate V6"):
        IM.gate_v6_for_manifest(m, clean + [{"id": "t", "group": "pt", "sha256": _sha(twin), "path": twin}], world["data"])


# ---------------------------------------------------------------------------------------------------- fold plans
def test_imports_enter_only_the_fitting_part_of_every_fold(world, project):
    _, pool, fold_of = project
    fold_sha = _sha(SPLITS / "cv5_folds_v1.csv")
    plans = {k: CV.fold_plan(pool, fold_of, k) for k in range(5)}
    snapshot = json.dumps({k: {n: [r["sample_id"] for r in p[n]] for n in ("fit", "inner", "heldout", "heldout_secondary")}
                           for k, p in plans.items()})
    out, h = written(world)
    m = IM.load_import_manifest(out, h, reviewer_ids={"R1"})
    aug = IM.augment_plans(plans, m, fold_of)
    imported = {f["sample_id"] for f in m["findings"]}
    for k in range(5):
        a, p = aug[k], plans[k]
        assert a["fit"][:len(p["fit"])] == p["fit"] and {r["sample_id"] for r in a["fit"][len(p["fit"]):]} == imported
        for part in ("inner", "heldout", "heldout_secondary"):
            assert a[part] is p[part] and not imported & {r["sample_id"] for r in a[part]}
        assert a["imports"] == {"findings": 4, "manifest_sha256": h}
    assert json.dumps({k: {n: [r["sample_id"] for r in p[n]] for n in ("fit", "inner", "heldout", "heldout_secondary")}
                       for k, p in plans.items()}) == snapshot                  # original plans untouched
    assert _sha(SPLITS / "cv5_folds_v1.csv") == fold_sha == CV.FOLD_FILE_SHA256
    assert sum(len(p["heldout"]) for p in plans.values()) == 2851               # the CV5 population is unchanged
    clash = copy.deepcopy(m)
    clash["findings"][0]["radiograph_group"] = next(iter(fold_of))
    with pytest.raises(IM.ImportRefused, match="in the CV5 fold file"):
        IM.augment_plans(plans, clash, fold_of)


def test_import_rows_are_valid_crop_rows(world, project):
    import dentamind_kaggle as DK
    out, h = written(world)
    m = IM.load_import_manifest(out, h)
    rows = IM.import_rows(m)
    X, y, _ = DK.build_crops(rows, world["data"])
    assert X.shape == (4, 224, 224, 3) and list(y) == [CLASSES.index(f["target_class"]) for f in m["findings"]]


# ---------------------------------------------------------------------------------------------------- P2
def _synthetic_manifest(n_pl, pl_imgs, n_dc, dc_imgs):
    """In-memory counting fixture only (never written, never a project manifest)."""
    f = []
    for cls, n, k in (("Periapical Lesion", n_pl, pl_imgs), ("Deep Caries", n_dc, dc_imgs)):
        for i in range(n):
            f.append({"target_class": cls, "image_sha256": hashlib.sha256(f"{cls}{i % k}".encode()).hexdigest()})
    return {"findings": f}


def test_p2_cannot_be_met_by_empty_or_insufficient_imports():
    import expansion_report as ER
    base = IM.base_counts_from_report(ROOT / "reports" / "expanded_class_distribution.csv")
    assert base["Periapical Lesion"] == {"findings": 129, "radiographs": 94} and base["Deep Caries"] == {"findings": 467, "radiographs": 250}
    for c, t in IM.P2_TARGETS.items():
        assert ER.TARGET_TRAIN[c] == t
    s = IM.p2_status(base, None)
    assert not s["met"] and s["classes"]["Periapical Lesion"]["gap_findings"] == 171 and s["classes"]["Deep Caries"]["gap_radiographs"] == 150
    assert not IM.p2_status(base, _synthetic_manifest(10, 10, 10, 10))["met"]
    assert not IM.p2_status(base, _synthetic_manifest(171, 5, 283, 5))["met"]          # enough findings, too few radiographs
    assert not IM.p2_status(base, _synthetic_manifest(171, 106, 282, 150))["met"]      # one finding short
    assert IM.p2_status(base, _synthetic_manifest(171, 106, 283, 150))["met"]


# ---------------------------------------------------------------------------------------------------- protection
def test_imports_never_touch_protected_artifacts_or_the_default_notebook(world, project):
    protected = [ROOT / p for p in ("reports/cv5_acceptance_protocol.md", "reports/cv5_acceptance_protocol_proposal.md",
                                    "reports/cv5_results.md", "data/splits/cv5_folds_v1.csv", "Data/reports/test_set_ledger.json",
                                    "kaggle/artifacts_cv5_run1/cv5_results.json", "kaggle/cv5_lib.py", "kaggle/dentamind_kaggle.py",
                                    "kaggle/dentamind_5fold_cv.ipynb", "reports/expanded_class_distribution.csv")]
    before = {p: _sha(p) for p in protected}
    _, pool, fold_of = project
    out, h = written(world)
    m = IM.load_import_manifest(out, h)
    IM.augment_plans({k: CV.fold_plan(pool, fold_of, k) for k in range(2)}, m, fold_of)
    IM.p2_status(IM.base_counts_from_report(ROOT / "reports" / "expanded_class_distribution.csv"), m)
    assert {p: _sha(p) for p in protected} == before
    full = (ROOT / "kaggle" / "cv5_imports.py").read_text(encoding="utf-8")
    i = full.index("def notebook_import_cell(")                                # the notebook-cell TEMPLATE text is not module I/O
    j = len(full)                                                               # the template is the last function in the module
    src = full[:i] + full[j:]
    assert "write_text" not in src and "open(" not in src.replace("open(p, \"rb\")", "").replace("open(csv_path, newline=\"\", encoding=\"utf-8\")", "")
    import dataclasses
    import cv5_interventions as CIV
    import make_cv5_notebook as NB
    code = "\n".join(s for k, s in NB.candidate_cells("PAD25", dataclasses.asdict(CIV.proposed_config("PAD25")))
                     if k == "code" and "EMBEDDED_SHA256" not in s)
    assert "cv5_imports" not in code                                           # not wired: the candidate notebook is unchanged
