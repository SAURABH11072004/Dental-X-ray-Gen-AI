"""Tests for the BASE-P2 reference generator kaggle/make_base_p2_notebook.py (DRAFT Amendment 02). Registrations, amendments, imports
and reviewers here are SYNTHETIC fixtures in temp folders; nothing is trained and no real registration exists."""
import copy
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import cv5_imports as CIM  # noqa: E402
import cv5_lib as CV  # noqa: E402
import dentamind_kaggle as DK  # noqa: E402
import make_base_p2_notebook as BP  # noqa: E402
import make_cv5_notebook as NB  # noqa: E402
from test_cv5_import_wiring import _globals, _stage  # noqa: E402
from test_cv5_imports import built, world  # noqa: E402,F401  (fixture)

IMP = {"manifest_sha256": "1" * 64, "v6_record_sha256": "2" * 64, "reviewer_authorization_sha256": "3" * 64,
       "input_dir": "/kaggle/input/dentamind-cv5-imports"}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _amendments(tmp, imports, signed=True):
    """Fixture amendment files (NOT the project's amendments) with a filled or empty signature row."""
    who = "Fixture Owner" if signed else ""
    a1 = tmp / "a01.md"
    a1.write_text(f"# fixture amendment 01\n| Registered by (owner's own full name) | {who} |\n", encoding="utf-8")
    a2 = tmp / "a02.md"
    a2.write_text(f"# fixture amendment 02\n{imports['manifest_sha256']} {imports['v6_record_sha256']} "
                  f"{imports['reviewer_authorization_sha256']}\n| Registered by (owner's own full name) | {who} |\n", encoding="utf-8")
    return a1, a2


def _registration(tmp, imports=IMP, **over):
    a1, a2 = _amendments(tmp, imports)
    reg = BP.registration_template()
    reg.update(registered_by="Fixture Owner", registered_at="2026-10-25T00:00:00Z", amendment_01_sha256=_sha(a1),
               amendment_02_sha256=_sha(a2), fold_file_sha256=CV.FOLD_FILE_SHA256, imports=dict(imports),
               code_sha256=BP.current_code_sha256())
    reg.update(over)
    return reg, a1, a2


def test_template_lists_everything_and_is_refused_as_is(tmp_path):
    t = BP.registration_template()
    assert set(t) == set(BP.REGISTRATION_FIELDS) and t["config"] == dataclasses.asdict(DK.EXPERIMENTS["BASE"])
    assert set(t["code_sha256"]) == set(BP.CODE_FILES) and "kaggle/make_base_p2_notebook.py" in t["code_sha256"]
    a1, a2 = _amendments(tmp_path, IMP)
    with pytest.raises(ValueError, match="placeholders"):
        BP.validate_registration(t, a1, a2)


def test_valid_registration_passes(tmp_path):
    reg, a1, a2 = _registration(tmp_path)
    BP.validate_registration(reg, a1, a2)


@pytest.mark.parametrize("change, msg", [
    (lambda r: r["config"].update(lr=1e-4), "not exactly EXPERIMENTS"),
    (lambda r: r["config"].update(extra={"crop_size": 384}), "not exactly EXPERIMENTS"),
    (lambda r: r.update(seeds=[42, 43, 44, 45]), "seeds / folds"),
    (lambda r: r.update(fold_file_sha256="0" * 64), "fold file"),
    (lambda r: r["code_sha256"].update({"kaggle/cv5_accept.py": "0" * 64}), "code changed since registration"),
    (lambda r: r["code_sha256"].pop("kaggle/cv5_imports.py"), "code_sha256 must list"),
    (lambda r: r["imports"].update(manifest_sha256="XYZ"), "imports"),
    (lambda r: r.update(required_outputs=["run_status.json"]), "required outputs"),
    (lambda r: r.update(split_semantics="imports anywhere"), "split semantics"),
    (lambda r: r.update(amendment_01_sha256="0" * 64), "amendment_01_sha256"),
    (lambda r: r.update(registered_by=" "), "registered_by"),
    (lambda r: r.pop("imports"), "incomplete"),
])
def test_unregistered_or_altered_registration_is_refused(tmp_path, change, msg):
    reg, a1, a2 = _registration(tmp_path)
    change(reg)
    with pytest.raises(ValueError, match=msg):
        BP.validate_registration(reg, a1, a2)


def test_unsigned_or_mismatched_amendments_are_refused(tmp_path):
    reg, a1, a2 = _registration(tmp_path)
    u1, u2 = _amendments(tmp_path / "u" if (tmp_path / "u").mkdir() is None else tmp_path, IMP, signed=False)
    reg2 = dict(reg, amendment_01_sha256=_sha(u1), amendment_02_sha256=_sha(u2))
    with pytest.raises(ValueError, match="not signed"):
        BP.validate_registration(reg2, u1, u2)
    a2.write_text(a2.read_text().replace(IMP["v6_record_sha256"], ""))           # Amendment 02 no longer names the V6 record
    reg3 = dict(reg, amendment_02_sha256=_sha(a2))
    with pytest.raises(ValueError, match="does not name imports.v6_record_sha256"):
        BP.validate_registration(reg3, a1, a2)
    with pytest.raises(ValueError, match="amendment_02_sha256"):
        BP.validate_registration(reg3, a1, None)


def test_cells_are_base_only_and_never_ask_the_candidate_generator_for_base(tmp_path, monkeypatch):
    reg, a1, a2 = _registration(tmp_path)
    calls = []
    real = NB.candidate_cells
    monkeypatch.setattr(NB, "candidate_cells", lambda cid, cfg, *a: calls.append((cid, cfg)) or real(cid, cfg, *a))
    cells = BP.base_p2_cells(reg, json.dumps(reg))
    assert calls and all(c[1]["extra"] for c in calls)                          # only a proposed candidate's text, never BASE
    code = [s for k, s in cells if k == "code"]
    for s in code:
        compile(s, "<cell>", "exec")
    gen = "\n".join(s for s in code if "EMBEDDED_SHA256 = " not in s)
    for bad in ("CANDIDATE", "CAND_CFG", "CI.", "cv5_interventions", "convnext"):
        assert bad not in gen, bad
    assert "m = DK.new_model(torch, tv, pretrained=False)" in gen and 'TAG = "s224_p0.10"' in gen and "BASE_P2_CFG(k)" in gen
    assert cells[7] == NB.CELLS[7] and cells[8] == NB.CELLS[8]                   # BASE crop and detector cells, unchanged
    imp = cells[9][1]
    assert imp == CIM.notebook_import_cell(reg["imports"], 'DK.build_crops(IMP_ROWS, IMPORT_DIR, CACHE / "imports_gt_s224_p0.10.npz")')
    embed = cells[4][1]
    assert "REGISTRATION_SHA256" in embed and 'dataclasses.asdict(DK.EXPERIMENTS["BASE"]) == REGISTRATION["config"]' in embed
    assert "CA.trainer_for(BASE_P2_CFG(0)) == CA.DEFAULT_TRAINER" in embed and "PREFLIGHT_TRAINER_ENV" in embed
    assert CV.sha256_file(ROOT / "kaggle" / "cv5_imports.py") in embed and "kaggle/cv5_interventions.py" not in embed
    pkg = cells[-1][1]
    assert "reviewer_authorization.json" in pkg and "base_p2_registration.json" in pkg and '"reference": "BASE-P2"' in cells[-3][1]
    agg, seal = cells[-3][1], cells[-2][1]
    assert "pooled out-of-fold macro-F1" not in agg and "confused by all seeds" not in agg and "SEALED (not logged)" in agg
    assert seal.startswith("# ---- 8b. seal BASE-P2") and "sealed_metrics_manifest.json" in pkg and "Main numbers:" not in pkg


def test_writer_refuses_invalid_and_writes_once(tmp_path):
    reg, a1, a2 = _registration(tmp_path)
    rp = tmp_path / "reg.json"
    rp.write_text(json.dumps(reg))
    out = BP.write_base_p2_notebook(rp, a1, a2, tmp_path / "base_p2.ipynb")
    nb = json.loads(out.read_text(encoding="utf-8"))
    assert len(nb["cells"]) == 15 and _sha(rp) in "".join(nb["cells"][0]["source"])
    with pytest.raises(ValueError, match="written once"):
        BP.write_base_p2_notebook(rp, a1, a2, out)
    bad = dict(reg, config=dict(reg["config"], epochs=1))
    rp2 = tmp_path / "reg2.json"
    rp2.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="refused"):
        BP.write_base_p2_notebook(rp2, a1, a2, tmp_path / "x.ipynb")
    assert not (tmp_path / "x.ipynb").exists()


def test_frozen_files_and_base_notebook_unchanged():
    assert _sha(ROOT / "kaggle" / "make_cv5_notebook.py") == "4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641"
    assert json.dumps(NB._notebook(NB.CELLS), indent=1, ensure_ascii=False) + "\n" == \
        (ROOT / "kaggle" / "dentamind_5fold_cv.ipynb").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------------- executing the BASE-P2 import cell
def test_base_p2_import_cell_trains_imports_only_and_keeps_heldout(world, tmp_path):
    msha, vsha = _stage(world)
    imports = {"manifest_sha256": msha, "v6_record_sha256": vsha, "reviewer_authorization_sha256": world["asha"],
               "input_dir": "/kaggle/input/fixture"}
    reg, _, _ = _registration(tmp_path, imports=imports)
    src = BP.base_p2_cells(reg, json.dumps(reg))[9][1].replace("IMPORT_DIR = Path('/kaggle/input/fixture')",
                                                               f"IMPORT_DIR = Path({str(world['data'])!r})")
    g = _globals(world, tmp_path / "g")
    before = {k: {n: [r["sample_id"] for r in p[n]] for n in p} for k, p in g["PLANS"].items()}
    exec(compile(src, "<base-p2 6b>", "exec"), g)
    imported = [r["sample_id"] for r in g["IMP_ROWS"]]
    for k in (0, 1):
        assert [r["sample_id"] for r in g["PLANS"][k]["fit"]] == before[k]["fit"] + imported
        for n in ("inner", "heldout", "heldout_secondary"):
            assert [r["sample_id"] for r in g["PLANS"][k][n]] == before[k][n]
    Xi, _, _ = DK.build_crops(CIM.import_rows(g["IMPORTS"]), world["data"])
    assert Xi.shape[1:] == (224, 224, 3) and np.array_equal(g["X_ALL"][-len(imported):], Xi)
    chk = json.loads((g["ART"] / "import_check.json").read_text())
    assert chk["reviewer_authorization"]["authorization_version"] == 1 and chk["identity"]["hits"] == 0


def test_base_p2_import_cell_rejects_duplicate_and_protected_radiographs(world, tmp_path):
    msha, vsha = _stage(world)
    imports = {"manifest_sha256": msha, "v6_record_sha256": vsha, "reviewer_authorization_sha256": world["asha"],
               "input_dir": "/kaggle/input/fixture"}
    reg, _, _ = _registration(tmp_path, imports=imports)
    src = BP.base_p2_cells(reg, json.dumps(reg))[9][1].replace("IMPORT_DIR = Path('/kaggle/input/fixture')",
                                                               f"IMPORT_DIR = Path({str(world['data'])!r})")
    g = _globals(world, tmp_path / "twin", pool_images={1: world["data"] / "raw/syn/u2.png"})   # CV-pool near-copy of an import
    with pytest.raises(CIM.ImportRefused, match="gate V6"):
        exec(compile(src, "<6b>", "exec"), g)
    g = _globals(world, tmp_path / "grp")
    g["FOLD_OF"] = dict(g["FOLD_OF"], **{world["pool"][0]["radiograph_group"]: 0})   # an imported group inside the CV population
    with pytest.raises(CIM.ImportRefused, match="in the CV5 fold file"):
        exec(compile(src, "<6b>", "exec"), g)


# ---------------------------------------------------------------------------------------------------- DRAFT Amendment 03 (D-B2 - D-B4)
import cv5_approvals as CAP  # noqa: E402


def _approve(path, scope, tmp, name="Fixture Approver"):
    rec = CAP.make_approval_record(scope, path, name, "fixture role", "Fixture approval statement for a test only.",
                                   approved_at="2026-10-25T00:00:00+00:00")
    out = tmp / f"approval_{scope}.json"
    out.write_text(json.dumps(rec))
    return out


def test_metrics_policy_and_attempt_rules(tmp_path):
    reg, a1, a2 = _registration(tmp_path)
    for change, msg in ((dict(metrics_policy="logged"), "metrics_policy"), (dict(attempt=0), "attempt"),
                        (dict(prior_attempt={"run_status_sha256": "0" * 64, "resolution_approval_sha256": "0" * 64}), "first attempt"),
                        (dict(attempt=2), "prior_attempt")):
        with pytest.raises(ValueError, match=msg):
            BP.validate_registration(dict(reg, **change), a1, a2)


def _run_status(tmp, ok=True, name="run_status.json"):
    runs = {f"CV5_BASEP2_f{k}_s{s}": "ok" for k in range(5) for s in range(42, 47)}
    if not ok:
        runs["CV5_BASEP2_f3_s44"] = "divergence"
    p = tmp / name
    p.write_text(json.dumps({"run_classes": runs, "n_expected": 25, "all_ok": ok}))
    return p


def test_second_attempt_needs_a_failed_status_and_an_approved_resolution(tmp_path):
    failed = _run_status(tmp_path, ok=False)
    res = _approve(failed, "base_p2_failure_resolution", tmp_path)
    prior = {"run_status_sha256": _sha(failed), "resolution_approval_sha256": _sha(res)}
    reg, a1, a2 = _registration(tmp_path, attempt=2, prior_attempt=prior)
    BP.validate_registration(reg, a1, a2, failed, res)
    with pytest.raises(ValueError, match="required"):
        BP.validate_registration(reg, a1, a2)
    good = _run_status(tmp_path, ok=True, name="complete.json")
    with pytest.raises(ValueError, match="no failure to resolve"):
        BP.validate_registration(dict(reg, prior_attempt={**prior, "run_status_sha256": _sha(good)}), a1, a2, good,
                                 _approve(good, "base_p2_failure_resolution", tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path))
    other = _approve(a1, "base_p2_failure_resolution", tmp_path / "y" if (tmp_path / "y").mkdir() is None else tmp_path)
    with pytest.raises(ValueError, match="failure resolution not approved"):
        BP.validate_registration(reg, a1, a2, failed, other)


def test_writer_verifies_human_approvals_when_required(tmp_path):
    reg, a1, a2 = _registration(tmp_path)
    rp = tmp_path / "reg.json"
    rp.write_text(json.dumps(reg))
    with pytest.raises(ValueError, match="approval record for"):
        BP.write_base_p2_notebook(rp, a1, a2, tmp_path / "nb1.ipynb", require_approvals=True)
    apps = {"amendment_01_registration": _approve(a1, "amendment_01_registration", tmp_path),
            "amendment_02_registration": _approve(a2, "amendment_02_registration", tmp_path),
            "base_p2_registration": _approve(rp, "base_p2_registration", tmp_path)}
    wrong = dict(apps, base_p2_registration=_approve(a1, "base_p2_registration", tmp_path / "w" if (tmp_path / "w").mkdir() is None else tmp_path))
    with pytest.raises(ValueError, match="base_p2_registration"):
        BP.write_base_p2_notebook(rp, a1, a2, tmp_path / "nb2.ipynb", approvals=wrong)
    assert BP.write_base_p2_notebook(rp, a1, a2, tmp_path / "nb3.ipynb", approvals=apps, require_approvals=True).is_file()
    assert not (tmp_path / "nb1.ipynb").exists() and not (tmp_path / "nb2.ipynb").exists()


def test_seal_cell_seals_and_removes_metric_files(tmp_path):
    reg, _, _ = _registration(tmp_path)
    seal = BP.base_p2_cells(reg, json.dumps(reg))[-2][1]
    art, runs, work = tmp_path / "art", tmp_path / "runs", tmp_path / "work"
    for d in (art, runs, work):
        d.mkdir()
    expected = [(k, s, f"CV5_BASEP2_f{k}_s{s}") for k in range(5) for s in range(42, 47)]
    secret = "macro_f1 0.123456 (fixture value)"
    for f in CAP.SEALED_RESULTS:
        (art / f).write_text(secret)
    for _, _, n in expected:
        (runs / n).mkdir()
        (runs / n / "heldout_pred.npz").write_bytes(b"fixture predictions")
    logged = []
    g = {"json": json, "ART": art, "RUNS": runs, "WORK": work, "EXPECTED_RUNS": expected, "SMOKE": False, "RUN_ID": "BASEP2",
         "log": lambda *a: logged.append(" ".join(map(str, a)))}
    exec(compile(seal, "<seal>", "exec"), g)
    man = json.loads((art / "sealed_metrics_manifest.json").read_text())
    assert len(man["files"]) == 3 + 25 and man["archive_sha256"] == _sha(work / "dentamind_cv5_BASEP2_SEALED_metrics.zip")
    assert not any((art / f).exists() for f in CAP.SEALED_RESULTS) and not any((runs / n / "heldout_pred.npz").exists() for _, _, n in expected)
    assert "0.123456" not in json.dumps(man) and not any("0.123456" in l for l in logged)
