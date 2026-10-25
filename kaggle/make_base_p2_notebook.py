#!/usr/bin/env python
"""BASE-P2 reference notebook generator (protocol reports/cv5_acceptance_protocol.md rev 3 section 3.2; DRAFT Amendment 02).

BASE-P2 = the unchanged BASE recipe (EXPERIMENTS["BASE"], ResNet-50, 224 px / pad 0.10) on the approved v1 folds, seeds 42-46, with
the registered clinician-verified imports added to the FITTING part of every fold only. It is a reference run, never a candidate, and
uses no budget slot. This generator is separate from the candidate generator: it never asks make_cv5_notebook.candidate_cells for a
BASE configuration (which that function refuses). It reuses the candidate path's training / evidence / aggregation / package cell
TEXT, generated for a proposed candidate, and replaces every candidate-specific expression by exact, asserted substitutions.

Nothing is generated without a frozen registration file (REGISTRATION_FORMAT) that:
* is referenced from both signed amendments (01 registers the candidates first; 02 registers BASE-P2), by their own SHA-256;
* fixes the config (exactly EXPERIMENTS["BASE"]), seeds, folds, fold-file SHA-256, the import manifest / V6 record / reviewer-
  authorization SHA-256 values and Kaggle input folder, the SHA-256 of every code file the notebook embeds or relies on, and the
  required output files.
The notebook itself re-checks the code hashes and the config before anything runs. No file here trains or evaluates anything.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (HERE, ROOT / "scripts" / "dataset"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import make_cv5_notebook as NB  # noqa: E402  (frozen; only read)

REGISTRATION_FORMAT = "dentamind-cv5-base-p2-registration-v1"
RUN_ID = "BASEP2"
SEEDS = [42, 43, 44, 45, 46]
FOLDS = [0, 1, 2, 3, 4]
EMBED = {**NB.EMBED, "kaggle/cv5_accept.py": HERE / "cv5_accept.py", "kaggle/cv5_imports.py": HERE / "cv5_imports.py",
         "kaggle/cv5_approvals.py": HERE / "cv5_approvals.py"}
CODE_FILES = {**{k: v for k, v in EMBED.items() if k.endswith(".py")},
              "kaggle/dentamind_kaggle.py": HERE / "dentamind_kaggle.py", "scripts/dataset/dsutil.py": ROOT / "scripts/dataset/dsutil.py",
              "kaggle/make_cv5_notebook.py": HERE / "make_cv5_notebook.py", "kaggle/make_notebook.py": HERE / "make_notebook.py",
              "kaggle/make_base_p2_notebook.py": Path(__file__).resolve()}
BUNDLE_CODE = ("kaggle/dentamind_kaggle.py", "scripts/dataset/dsutil.py")      # come from the Kaggle data bundle, checked in the notebook
REQUIRED_OUTPUTS = ["run_status.json", "import_check.json", "sealed_metrics_manifest.json", "SEALED metrics archive (cv5_results.json, "
                    "oof_predictions.csv, caries_confusion_findings.csv, runs/RUN__heldout_pred.npz)", "checkpoint_manifest.json",
                    "fold_plan.json", "detector_boxes_pool.json", "environment.json", "training_log.txt", "imports/import_manifest.json",
                    "imports/import_v6_record.json", "imports/reviewer_authorization.json", "base_p2_registration.json",
                    "runs/RUN__best.training_manifest.json + attempt records for all 25 runs", "run_evidence archive", "SHA256SUMS.txt"]
REGISTRATION_FIELDS = ("format", "registered_by", "registered_at", "amendment_01_sha256", "amendment_02_sha256", "config", "seeds",
                       "folds", "fold_file_sha256", "split_semantics", "imports", "code_sha256", "required_outputs",
                       "metrics_policy", "attempt", "prior_attempt")
METRICS_POLICY = "sealed"            # DRAFT Amendment 03 D-B3: held-out metrics / predictions sealed until the release condition
SPLIT_SEMANTICS = ("imports in the fitting part of every fold only; inner validation, held-out and secondary held-out assignments of "
                   "cv5_folds_v1.csv unchanged; calibration and test never read")
_SIGNED_ROW = re.compile(r"^\|\s*Registered by \(owner's own full name\)\s*\|\s*([^|]*?)\s*\|", re.M)


def _sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def current_code_sha256() -> dict:
    return {k: _sha(p) for k, p in CODE_FILES.items()}


def registration_template() -> dict:
    """What a registration must contain; every <...> must be replaced by the owner from real, frozen artifacts."""
    import dentamind_kaggle as DK
    return {"format": REGISTRATION_FORMAT, "registered_by": "<owner's own full name>", "registered_at": "<YYYY-MM-DDTHH:MM:SSZ>",
            "amendment_01_sha256": "<sha256 of the SIGNED Amendment 01 file>", "amendment_02_sha256": "<sha256 of the SIGNED Amendment 02 file>",
            "config": dataclasses.asdict(DK.EXPERIMENTS["BASE"]), "seeds": SEEDS, "folds": FOLDS,
            "fold_file_sha256": "<CV.FOLD_FILE_SHA256>", "split_semantics": SPLIT_SEMANTICS,
            "imports": {"manifest_sha256": "<registered import manifest sha256>", "v6_record_sha256": "<local V6 record sha256>",
                        "reviewer_authorization_sha256": "<reviewer authorization version sha256>", "input_dir": "/kaggle/input/<dataset>"},
            "code_sha256": {k: "<sha256 at registration>" for k in CODE_FILES}, "required_outputs": REQUIRED_OUTPUTS,
            "metrics_policy": METRICS_POLICY, "attempt": 1, "prior_attempt": None}


def validate_registration(reg: dict, amendment_01, amendment_02, prior_run_status=None, prior_resolution=None) -> None:
    """Refuses unless the registration is complete, frozen and consistent with the code and the signed amendments. A registration
    with attempt > 1 (DRAFT Amendment 03 D-B4) must cite the failed BASE-P2 run status and an approved failure resolution."""
    import cv5_approvals as CAP
    import cv5_imports as CIM
    import cv5_lib as CV
    import dentamind_kaggle as DK
    probs = []
    missing = [k for k in REGISTRATION_FIELDS if k not in reg]
    if missing:
        raise ValueError(f"registration incomplete: missing {missing}")
    if reg["format"] != REGISTRATION_FORMAT:
        probs.append("wrong registration format")
    if any("<" in str(v) for v in _leaves(reg)):
        probs.append("registration still contains template placeholders (<...>)")
    if not str(reg["registered_by"]).strip():
        probs.append("registered_by missing")
    if reg["config"] != dataclasses.asdict(DK.EXPERIMENTS["BASE"]):
        probs.append("config is not exactly EXPERIMENTS['BASE'] (BASE-P2 is the unchanged BASE recipe)")
    if reg["seeds"] != SEEDS or reg["folds"] != FOLDS:
        probs.append("seeds / folds differ from 42-46 / 0-4")
    if reg["fold_file_sha256"] != CV.FOLD_FILE_SHA256 or _sha(ROOT / "data/splits/cv5_folds_v1.csv") != CV.FOLD_FILE_SHA256:
        probs.append("fold file SHA-256 is not the approved one")
    if reg["split_semantics"] != SPLIT_SEMANTICS:
        probs.append("split semantics differ from the registered wording")
    try:
        CIM.check_import_params(reg["imports"])
    except ValueError as e:
        probs.append(f"imports: {e}")
    cur = current_code_sha256()
    if set(reg["code_sha256"]) != set(cur):
        probs.append(f"code_sha256 must list exactly {sorted(cur)}")
    else:
        changed = sorted(k for k in cur if reg["code_sha256"][k] != cur[k])
        if changed:
            probs.append(f"code changed since registration: {changed}")
    if reg["required_outputs"] != REQUIRED_OUTPUTS:
        probs.append("required outputs differ from the registered list")
    if reg["metrics_policy"] != METRICS_POLICY:
        probs.append(f"metrics_policy must be {METRICS_POLICY!r} (held-out metrics sealed until the release condition)")
    att, prior = reg["attempt"], reg["prior_attempt"]
    if not isinstance(att, int) or att < 1:
        probs.append("attempt must be an integer >= 1")
    elif att == 1 and prior is not None:
        probs.append("a first attempt cites no prior attempt")
    elif att > 1:
        if not isinstance(prior, dict) or set(prior) != {"run_status_sha256", "resolution_approval_sha256"}:
            probs.append("attempt > 1 must cite prior_attempt {run_status_sha256, resolution_approval_sha256}")
        elif not prior_run_status or not prior_resolution:
            probs.append("attempt > 1: the failed run_status.json and the failure-resolution approval record are required")
        else:
            try:
                res = CAP.check_failure_resolution(prior_run_status, prior_resolution)
                if res["failed_run_status_sha256"] != prior["run_status_sha256"] or _sha(prior_resolution) != prior["resolution_approval_sha256"]:
                    probs.append("prior_attempt hashes do not match the cited failed run status / resolution approval")
            except CAP.BaseP2NotReady as e:
                probs.append(str(e))
    for key, path in (("amendment_01_sha256", amendment_01), ("amendment_02_sha256", amendment_02)):
        p = Path(path) if path else None
        if not p or not p.is_file() or _sha(p) != reg[key]:
            probs.append(f"{key}: amendment file missing or not the registered version")
            continue
        m = _SIGNED_ROW.search(p.read_text(encoding="utf-8"))
        if not m or not m.group(1).strip():
            probs.append(f"{key}: amendment is not signed (the 'Registered by' row is empty)")
    if amendment_02 and Path(amendment_02).is_file():
        txt = Path(amendment_02).read_text(encoding="utf-8")
        for k in ("manifest_sha256", "v6_record_sha256", "reviewer_authorization_sha256"):
            if reg["imports"].get(k) and reg["imports"][k] not in txt:
                probs.append(f"Amendment 02 does not name imports.{k}")
    if probs:
        raise ValueError("BASE-P2 registration refused: " + "; ".join(probs))


def _leaves(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _leaves(v)
    elif isinstance(o, list):
        for v in o:
            yield from _leaves(v)
    else:
        yield o


def _sub(src: str, old: str, new: str) -> str:
    if src.count(old) != 1:
        raise ValueError(f"template drift: expected exactly one {old[:70]!r}")
    return src.replace(old, new)


def _candidate_templates() -> dict:
    """Training / evidence / aggregation / package cell text of the candidate path, generated for a PROPOSED candidate (never BASE)."""
    import cv5_interventions as CIV
    cells = NB.candidate_cells("PAD25", dataclasses.asdict(CIV.proposed_config("PAD25")))
    pick = lambda m: next(s for k, s in cells if k == "code" and m in s)          # noqa: E731
    return {"train": pick("CA.run_isolated("), "evidence": pick("run evidence (always packaged"),
            "agg": pick('assert RUN_STATUS["all_ok"]'), "pkg": pick("package artifacts")}


def base_p2_cells(reg: dict, registration_text: str) -> list:
    import cv5_imports as CIM
    t = _candidate_templates()
    train = t["train"]
    train = _sub(train, 'm = CI.new_model(torch, tv, CANDIDATE["extra"], pretrained=False)', 'm = DK.new_model(torch, tv, pretrained=False)')
    train = _sub(train, 'TAG = CI.crop_tag(CANDIDATE["extra"])', 'TAG = "s224_p0.10"                      # BASE crop rule')
    train = _sub(train, 'rows_json = CA.write_rows(CACHE / f"f{k}_rows.json", plan["fit"], plan["inner"])',
                 'rows_json = CA.write_rows(CACHE / f"f{k}_rows.json", [r for r in plan["fit"] if "import_source_id" not in r], '
                 'plan["inner"],\n                               [r for r in plan["fit"] if "import_source_id" in r])')
    train = _sub(train, 'cfg = CAND_CFG(k)', 'cfg = BASE_P2_CFG(k)')
    train = _sub(train, '"run": name, "candidate": CANDIDATE_ID,', '"run": name, "reference": "BASE-P2",')
    train = _sub(train, "# ---- 7. train the candidate:", "# ---- 7. train BASE-P2 (reference, not a candidate):")
    ev = _sub(t["evidence"], 'for f in ("run_status.json", "training_log.txt"):', 'for f in ("run_status.json", "training_log.txt", "import_check.json"):')
    agg = _sub(t["agg"], '"candidate": CANDIDATE_ID', '"reference": "BASE-P2", "registration_sha256": REGISTRATION_SHA256')
    i0 = agg.index("for s in settings:\n    log(f\"pooled out-of-fold macro-F1")
    i1 = agg.index('CARIES["n"])\n', i0) + len('CARIES["n"])\n')
    if agg.count("for s in settings:\n    log(f\"pooled out-of-fold macro-F1") != 1:
        raise ValueError("template drift: pooled-metric log block")
    agg = agg[:i0] + ('log("BASE-P2 held-out metrics computed and SEALED (not logged); release only under the registered release '
                      'condition (DRAFT Amendment 03 D-B3)")\n') + agg[i1:]
    pkg = t["pkg"]
    pkg = _sub(pkg, '{RUN_NAME(k): dataclasses.asdict(CAND_CFG(k)) for k in FOLDS}', '{RUN_NAME(k): dataclasses.asdict(BASE_P2_CFG(k)) for k in FOLDS}')
    pkg = _sub(pkg, '"training_log.txt", "environment.json", "run_status.json"):',
               '"training_log.txt", "environment.json", "run_status.json", "sealed_metrics_manifest.json"):')
    pkg = _sub(pkg, '"Main numbers: cv5_results.json (summary, bootstrap, per_fold, detector_unseen_subset, secondary_official_val, caries_confusion)."',
               '"Held-out metrics and predictions are SEALED in a separate archive (sealed_metrics_manifest.json); release only under the '
               'registered release condition (DRAFT Amendment 03 D-B3)."')
    pkg = _sub(pkg, 'f"# DentaMind CV5 candidate {CANDIDATE_ID} artifacts"', '"# DentaMind CV5 BASE-P2 reference artifacts (protocol section 3.2)"')
    pkg = _sub(pkg, '"kaggle/cv5_interventions.py", ', '"kaggle/cv5_imports.py", ')
    pkg = _sub(pkg, '(pkg / "checkpoint_manifest.json").write_text(json.dumps(ck, indent=1))',
               '(pkg / "checkpoint_manifest.json").write_text(json.dumps(ck, indent=1))\n(pkg / "imports").mkdir()\n'
               'for f in ("import_manifest.json", "import_v6_record.json", "reviewer_authorization.json"):\n'
               '    shutil.copy2(IMPORT_DIR / f, pkg / "imports" / f)\n'
               'shutil.copy2(ART / "import_check.json", pkg / "imports" / "import_check.json")\n'
               '(pkg / "base_p2_registration.json").write_text(REGISTRATION_TEXT, encoding="utf-8")')
    seal = """# ---- 8b. seal BASE-P2 held-out metrics and predictions (DRAFT Amendment 03 D-B3) ------------------------------------------------
import cv5_approvals as CAP
_seal = {f: ART / f for f in CAP.SEALED_RESULTS}
for _, _, name in EXPECTED_RUNS:
    _seal[f"runs/{name}__heldout_pred.npz"] = RUNS / name / "heldout_pred.npz"
SEALED_ZIP = WORK / f"dentamind_cv5_{RUN_ID}_SEALED_metrics{'_SMOKE' if SMOKE else ''}.zip"
SEALED = CAP.make_sealed_archive(_seal, SEALED_ZIP)
(ART / "sealed_metrics_manifest.json").write_text(json.dumps(SEALED, indent=1))
for _p in _seal.values():                       # only the sealed archive keeps them; nothing with values stays in the open output
    _p.unlink()
log(f"SEALED METRICS {SEALED_ZIP.name}  sha256 {SEALED['archive_sha256']} ({len(SEALED['files'])} files; values not logged)")"""
    out = []
    for name, src in (("train", train), ("evidence", ev), ("agg", agg), ("pkg", pkg)):
        src = src.replace("CANDIDATE_ID", "RUN_ID")
        for bad in ("CANDIDATE", "CAND_CFG", "CI.", "cv5_interventions"):
            if bad in src:
                raise ValueError(f"template drift: {bad!r} left in the BASE-P2 {name} cell")
        out.append(src)
    train, ev, agg, pkg = out
    files = {k: p.read_bytes().decode("utf-8") for k, p in EMBED.items()}
    shas = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in files.items()}
    reg_sha = hashlib.sha256(registration_text.encode("utf-8")).hexdigest()
    head = ("markdown", f"""# DentaMind AI - CV5 BASE-P2 reference run (Kaggle GPU)

Protocol `reports/cv5_acceptance_protocol.md` revision 3, section 3.2. **Reference run, not a candidate**: the unchanged BASE recipe on the
approved fold file, seeds 42-46, with the registered clinician-verified imports in the fitting part of every fold only. Inner validation
and held-out assignments are unchanged; no calibration or test image is read. Its comparison with CV5-BASE run 1 is EXPLORATORY.
Registration SHA-256 `{reg_sha}`. Attach the private Kaggle data bundle (v3) and the registered imports dataset.""")
    embed = ("code", f"""# ---- 2b. embedded files, frozen registration, BASE-P2 definition ----------------------------------------------------------------
EMBEDDED = {json.dumps(files)}
EMBEDDED_SHA256 = {json.dumps(shas)}
for rel, txt in EMBEDDED.items():
    assert hashlib.sha256(txt.encode("utf-8")).hexdigest() == EMBEDDED_SHA256[rel], f"embedded file changed: {{rel}}"
    (CODE / rel).parent.mkdir(parents=True, exist_ok=True)
    (CODE / rel).write_text(txt, encoding="utf-8", newline="")
    log("embedded", rel, EMBEDDED_SHA256[rel][:16])
REGISTRATION_TEXT = {registration_text!r}
REGISTRATION_SHA256 = {reg_sha!r}
assert hashlib.sha256(REGISTRATION_TEXT.encode("utf-8")).hexdigest() == REGISTRATION_SHA256
REGISTRATION = json.loads(REGISTRATION_TEXT)
for rel, h in REGISTRATION["code_sha256"].items():                     # every embedded / bundle code file is the registered version
    if rel in EMBEDDED_SHA256:
        assert EMBEDDED_SHA256[rel] == h, f"embedded {{rel}} is not the registered version"
for rel in {list(BUNDLE_CODE)!r}:
    assert hashlib.sha256((CODE / rel).read_bytes()).hexdigest() == REGISTRATION["code_sha256"][rel], f"bundle {{rel}} is not the registered version"
import cv5_lib as CV
import cv5_accept as CA
assert CV.sha256_file(CODE / "data/splits/cv5_folds_v1.csv") == CV.FOLD_FILE_SHA256 == REGISTRATION["fold_file_sha256"]
assert not os.environ.get(CA.PREFLIGHT_TRAINER_ENV), "the pre-flight trainer switch is set: BASE-P2 never uses it"
assert dataclasses.asdict(DK.EXPERIMENTS["BASE"]) == REGISTRATION["config"], "BASE recipe differs from the registered config"
assert SEEDS == REGISTRATION["seeds"] and FOLDS == REGISTRATION["folds"], "seeds / folds differ from the registration"
RUN_ID = {RUN_ID!r}

def RUN_NAME(k):
    return f"CV5_{{RUN_ID}}_f{{k}}"

def BASE_P2_CFG(k):
    return dataclasses.replace(DK.EXPERIMENTS["BASE"], name=RUN_NAME(k))

assert CA.trainer_for(BASE_P2_CFG(0)) == CA.DEFAULT_TRAINER, "BASE-P2 must use the unchanged BASE trainer"
EXPECTED_RUNS = [(k, sd, f"{{RUN_NAME(k)}}_s{{sd}}") for k in FOLDS for sd in SEEDS]
assert SMOKE or len(EXPECTED_RUNS) == 25, "all 25 runs are required"
log("BASE-P2 reference, registration", REGISTRATION_SHA256[:16], "registered by", REGISTRATION["registered_by"], "- runs:", len(EXPECTED_RUNS))""")
    imp = ("code", CIM.notebook_import_cell(reg["imports"], 'DK.build_crops(IMP_ROWS, IMPORT_DIR, CACHE / "imports_gt_s224_p0.10.npz")'))
    return [head, NB.CELLS[1], NB.CELLS[2], NB.CELLS[3], embed, NB.CELLS[5], NB.CELLS[6], NB.CELLS[7], NB.CELLS[8], imp,
            ("code", train), ("code", ev), ("code", agg), ("code", seal), ("code", pkg)]


APPROVAL_SCOPES = {"amendment_01_registration": "amendment_01", "amendment_02_registration": "amendment_02",
                   "base_p2_registration": "registration"}


def write_base_p2_notebook(registration_path, amendment_01, amendment_02, out, approvals: dict | None = None,
                           require_approvals: bool = False, prior_run_status=None, prior_resolution=None) -> Path:
    """Writes the BASE-P2 notebook only for a valid, frozen registration referenced by both signed amendments. approvals
    {scope: record path} (DRAFT Amendment 03 D-B2): when given - and always when require_approvals - each of APPROVAL_SCOPES must be
    a valid human approval record bound to the exact file (amendment 01, amendment 02, registration)."""
    import cv5_approvals as CAP
    text = Path(registration_path).read_text(encoding="utf-8")
    reg = json.loads(text)
    validate_registration(reg, amendment_01, amendment_02, prior_run_status, prior_resolution)
    if require_approvals or approvals:
        files = {"amendment_01": amendment_01, "amendment_02": amendment_02, "registration": registration_path}
        for scope, which in APPROVAL_SCOPES.items():
            rec = (approvals or {}).get(scope)
            if not rec:
                raise ValueError(f"approval record for {scope} required")
            try:
                CAP.verify_approval(rec, files[which], scope)
            except CAP.ApprovalError as e:
                raise ValueError(f"{scope}: {e}") from e
    out = Path(out)
    if out.exists():
        raise ValueError(f"{out} exists: the BASE-P2 notebook is written once per registration")
    out.write_text(json.dumps(NB._notebook(base_p2_cells(reg, text)), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(registration_template(), indent=1))
