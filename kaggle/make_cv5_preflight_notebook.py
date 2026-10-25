#!/usr/bin/env python
"""Generate kaggle/dentamind_cv5_preflight.ipynb: a NO-TRAINING Kaggle pre-flight of the CV5 candidate notebook path.

    .venv\\Scripts\\python.exe kaggle\\make_cv5_preflight_notebook.py

What it runs: the candidate notebook's own training-loop, run-evidence and aggregation cells (taken verbatim from
make_cv5_notebook.candidate_cells), the candidate definition block, and cv5_accept.run_isolated with real subprocesses. What it
replaces: the bundle, fold file, DENTEX images, crops and detector cells. Instead a synthetic frame (random uint8 crops, synthetic row
ids, no labels from any data set) is built in memory, and training is done by kaggle/cv5_preflight_trainer.py, which saves untrained
randomly initialised ResNet-50 weights. Nothing here reads a DENTEX file, imports labels or trains a model; all runs are recorded as
pre-flight and are never eligible for final-model selection. Attach NO input dataset.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import make_cv5_notebook as NB  # noqa: E402
import make_notebook as MN  # noqa: E402

EMBED = {"kaggle/dentamind_kaggle.py": HERE / "dentamind_kaggle.py", "kaggle/cv5_lib.py": HERE / "cv5_lib.py",
         "kaggle/cv5_accept.py": HERE / "cv5_accept.py", "kaggle/cv5_interventions.py": HERE / "cv5_interventions.py",
         "kaggle/cv5_preflight_trainer.py": HERE / "cv5_preflight_trainer.py",
         "scripts/dataset/dsutil.py": ROOT / "scripts/dataset/dsutil.py",
         "scripts/dataset/make_cv_folds.py": ROOT / "scripts/dataset/make_cv_folds.py"}
CANDIDATE_ID = "PREFLIGHT"
TRAIN_SEEDS = [42, 43, 44, 45]                  # seed 46 is deliberately never started: 5 required runs missing
# scripted section-9 outcomes; every other started run is "ok"
PLAN = {"CV5_PREFLIGHT_f1_s43": "infra_once", "CV5_PREFLIGHT_f2_s44": "compute", "CV5_PREFLIGHT_f2_s43": "inf_loss",
        "CV5_PREFLIGHT_f3_s45": "collapse", "CV5_PREFLIGHT_f3_s42": "ambiguous_cuda",
        "CV5_PREFLIGHT_f4_s44": "kill_after_checkpoint", "CV5_PREFLIGHT_f4_s43": "killed"}
EXPECTED_CLASS = {"ok": "ok", "infra_once": "ok", "compute": "incomplete", "inf_loss": "divergence", "collapse": "divergence",
                  "ambiguous_cuda": "incomplete", "kill_after_checkpoint": "incomplete", "killed": "infrastructure"}
EXPECTED_ATTEMPTS = {"ok": 1, "infra_once": 2, "compute": 1, "inf_loss": 1, "collapse": 1, "ambiguous_cuda": 1,
                     "kill_after_checkpoint": 1, "killed": 3}


def _cell(cells, marker):
    hits = [src for kind, src in cells if kind == "code" and marker in src]
    if len(hits) != 1:
        raise ValueError(f"candidate cell with {marker!r}: {len(hits)} found")
    return hits[0]


def build_cells() -> list:
    sys.path.insert(0, str(ROOT / "scripts" / "dataset"))
    import dataclasses
    import cv5_interventions as CI
    # a real single-intervention config (C2 crop padding) so the V3 gate and the intervention module are exercised; the fake
    # trainer ignores it and no crop is built from any radiograph
    cfg = dataclasses.asdict(dataclasses.replace(CI.proposed_config("PAD25"), name="PREFLIGHT",
                                                 note="PREFLIGHT: fake trainer, no training"))
    cand = NB.candidate_cells(CANDIDATE_ID, cfg)
    defs = _cell(cand, "EMBEDDED_SHA256")
    defs = defs[defs.index("CANDIDATE_ID = "):]                    # the candidate definition block, verbatim
    train = _cell(cand, "CA.run_isolated(")
    evidence = _cell(cand, "run evidence (always packaged")
    agg = _cell(cand, 'assert RUN_STATUS["all_ok"]')
    files = {k: p.read_bytes().decode("utf-8") for k, p in EMBED.items()}
    shas = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in files.items()}
    cells_sha = {name: hashlib.sha256(src.encode("utf-8")).hexdigest() for name, src in
                 (("definitions", defs), ("training", train), ("evidence", evidence), ("aggregation", agg))}
    head = ("markdown", f"""# DentaMind AI - CV5 candidate path PRE-FLIGHT (no training, no DENTEX data)

Exercises the candidate notebook path of `kaggle/make_cv5_notebook.py` on Kaggle: isolated training subprocesses, section-9 retry
rules, per-run training manifests, run-status serialization, the run-evidence archive, and the gate-4 stop of aggregation.

* **No input dataset may be attached.** No DENTEX image, label, split manifest or fold file is read; the frame is synthetic.
* Training is replaced by `cv5_preflight_trainer.py`, which saves **untrained, randomly initialised** ResNet-50 weights. No model is
  trained and no number produced here is a result. Every run is recorded as pre-flight and is never eligible for final-model selection.
* Scripted outcomes: {json.dumps(PLAN)}; seed 46 is never started.
* Output: `dentamind_cv5_preflight_output.zip` with `preflight_report.json` (PASS/FAIL per check).""")
    embed = ("code", f"""# ---- P1. embedded code (no bundle, no data), candidate definition, pre-flight trainer ---------------------------------------
inputs = sorted(glob.glob("/kaggle/input/*"))
log("attached inputs:", inputs or "none")
assert not inputs, "PRE-FLIGHT: detach every input dataset - no DENTEX data may be available to this notebook"
EMBEDDED = {json.dumps(files)}
EMBEDDED_SHA256 = {json.dumps(shas)}
for rel, txt in EMBEDDED.items():
    assert hashlib.sha256(txt.encode("utf-8")).hexdigest() == EMBEDDED_SHA256[rel], f"embedded file changed: {{rel}}"
    (CODE / rel).parent.mkdir(parents=True, exist_ok=True)
    (CODE / rel).write_text(txt, encoding="utf-8", newline="")
    log("embedded", rel, EMBEDDED_SHA256[rel][:16])
for p in (CODE / "kaggle", CODE / "scripts/dataset"):
    sys.path.insert(0, str(p))
import dentamind_kaggle as DK
import cv5_lib as CV
import cv5_accept as CA
import cv5_interventions as CI
CANDIDATE_CELLS_SHA256 = {json.dumps(cells_sha)}
PLAN = {json.dumps(PLAN)}
EXPECTED_CLASS = {json.dumps(EXPECTED_CLASS)}
EXPECTED_ATTEMPTS = {json.dumps(EXPECTED_ATTEMPTS)}
(ART / "preflight_plan.json").write_text(json.dumps(PLAN, indent=1))
os.environ["DENTAMIND_PREFLIGHT_PLAN"] = str(ART / "preflight_plan.json")
os.environ[CA.PREFLIGHT_TRAINER_ENV] = "cv5_preflight_trainer:train"
log("pre-flight trainer:", os.environ[CA.PREFLIGHT_TRAINER_ENV], "(saves untrained random weights; nothing is trained)")
# ---- candidate definition block (verbatim from make_cv5_notebook.candidate_cells) ----
""" + defs)
    synth = ("code", f"""# ---- P2. synthetic frame instead of folds / images / crops / detector (no DENTEX file is read) ---------------------------------
rng = np.random.default_rng(0)
C = len(DK.CLASSES)
def _rows(k, part, n, src):
    return [{{"sample_id": f"syn_f{{k}}_{{part}}_{{i}}", "project_image_id": f"syn_img_f{{k}}_{{part}}_{{i // 2}}",
             "image_sha256": hashlib.sha256(f"syn{{k}}{{part}}{{i}}".encode()).hexdigest(), "image_path": f"synthetic/f{{k}}/{{part}}/{{i}}.png",
             "source_dataset": src, "radiograph_group": f"syn_g_f{{k}}_{{part}}_{{i // 2}}", "target_class": DK.CLASSES[i % C],
             "split": "train"}} for i in range(n)]
PLANS = {{k: {{"fold": k, "fit": _rows(k, "fit", 16, CV.PRIMARY), "inner": _rows(k, "inner", 8, CV.PRIMARY),
              "heldout": _rows(k, "heldout", 6, CV.PRIMARY), "heldout_secondary": _rows(k, "sec", 2, CV.SECONDARY)}} for k in FOLDS}}
POOL = [r for k in FOLDS for part in ("fit", "inner", "heldout", "heldout_secondary") for r in PLANS[k][part]]
PRIMARY_ROWS = [r for k in FOLDS for r in PLANS[k]["heldout"]]
SECONDARY_ROWS = [r for k in FOLDS for r in PLANS[k]["heldout_secondary"]]
IDX = {{r["sample_id"]: i for i, r in enumerate(POOL)}}
X_ALL = rng.integers(0, 256, size=(len(POOL), DK.CROP_SIZE, DK.CROP_SIZE, 3), dtype=np.uint8)
Y_ALL = np.array([DK.CLASSES.index(r["target_class"]) for r in POOL])
MATCHED = rng.random(len(POOL)) > 0.2
MI = np.flatnonzero(MATCHED)
XD = X_ALL[MI]
XD_OF = np.full(len(POOL), -1)
XD_OF[MI] = np.arange(len(MI))
SEEDS_ALL = list(SEEDS)
SEEDS = {TRAIN_SEEDS}                     # seed 46 is never started
log(f"synthetic frame: {{len(POOL)}} synthetic findings, crops {{X_ALL.shape}}, training seeds {{SEEDS}} of {{SEEDS_ALL}}")""")
    gate = ("code", """# ---- P3. aggregation must be refused: run the candidate aggregation cell verbatim --------------------------------------------
SEEDS = SEEDS_ALL
AGG_REFUSED, AGG_MESSAGE = False, None
try:
    exec(compile(CANDIDATE_AGGREGATION, "<candidate aggregation cell>", "exec"), globals())
except AssertionError as e:
    AGG_REFUSED, AGG_MESSAGE = True, str(e)
log("aggregation refused:", AGG_REFUSED, "-", AGG_MESSAGE)""")
    check = ("code", """# ---- P4. pre-flight checks, report, output archive ---------------------------------------------------------------------------
import zipfile as _zf
checks = {}
def check(name, ok, detail=None):
    checks[name] = {"pass": bool(ok), "detail": detail}
    log(("PASS " if ok else "FAIL ") + name, "" if detail is None else detail)
st = json.loads((ART / "run_status.json").read_text())
check("run_status.json lists all 25 required runs", len(st["runs"]) == 25 and st["n_expected"] == 25, len(st["runs"]))
check("not all runs ok", st["all_ok"] is False)
for k, sd, name in EXPECTED_RUNS:
    s = st["runs"][name]
    if sd not in SEEDS_TRAINED:
        check(f"{name} never started -> incomplete", s["class"] == "incomplete" and s.get("reason") == "not started", s["class"])
        continue
    mode = PLAN.get(name, "ok")
    check(f"{name} [{mode}] class", s["class"] == EXPECTED_CLASS[mode], s["class"])
    check(f"{name} [{mode}] attempts", s.get("attempts") == EXPECTED_ATTEMPTS[mode], s.get("attempts"))
    check(f"{name} never eligible (pre-flight)", s.get("final_model_eligible") is False)
    d = RUNS / name
    mf = d / CA.MANIFEST_NAME
    if mode in ("ok", "infra_once", "inf_loss", "collapse"):
        m = json.loads(mf.read_text())
        ck = CV.sha256_file(d / "best.pth")
        v = CA.verify_run_manifest(d, name, k, sd)
        check(f"{name} manifest verifies", v["ok"], v["problems"])
        check(f"{name} manifest <-> checkpoint <-> run", m["checkpoint_sha256"] == ck and (m["cv"]["run"], m["cv"]["fold"], m["cv"]["seed"]) == (name, k, sd)
              and m["cv"]["trainer"] == "cv5_preflight_trainer:train")
        if mode in ("ok", "infra_once"):
            cvr = json.loads((d / "cv_run.json").read_text())
            check(f"{name} cv_run.json references manifest + checkpoint", cvr["checkpoint_sha256"] == ck and
                  cvr["training_manifest"]["sha256"] == CV.sha256_file(mf), cvr["exception_origins"])
            check(f"{name} held-out predictions written", (d / "heldout_pred.npz").is_file())
        else:
            check(f"{name} diverged run not predicted", not (d / "heldout_pred.npz").exists())
    else:
        check(f"{name} has no manifest", not mf.exists())
        check(f"{name} has no held-out predictions", not (d / "heldout_pred.npz").exists())
    if mode == "kill_after_checkpoint":
        check(f"{name}: checkpoint exists but run final-incomplete, no late manifest",
              (d / "best.pth").is_file() and (d / CA.FAILURE_FILE).is_file() and not mf.exists() and
              (d / "preflight_calls.txt").read_text() == "1", json.loads((d / CA.FAILURE_FILE).read_text())["reason"])
    if mode in ("compute", "ambiguous_cuda"):
        check(f"{name}: not retried", (d / "preflight_calls.txt").read_text() == "1")
    if mode == "infra_once":
        a = json.loads((d / CA.ATTEMPTS_FILE).read_text())
        check(f"{name}: origins recorded", [x.get("origin") for x in a] == ["infrastructure", None], [x.get("type") for x in a])
    if mode == "killed":
        a = json.loads((d / CA.ATTEMPTS_FILE).read_text())
        check(f"{name}: SIGKILL recorded as infrastructure", all(x["type"] == "killed" and x["returncode"] in CA.KILLED_RETURNCODES for x in a),
              [x["returncode"] for x in a])
check("aggregation refused at gate 4", AGG_REFUSED and "gate 4" in (AGG_MESSAGE or ""), AGG_MESSAGE)
check("no candidate result written", not (ART / "cv5_results.json").exists() and not (ART / "oof_predictions.csv").exists())
check("candidate cells used verbatim", all(hashlib.sha256(src.encode()).hexdigest() == CANDIDATE_CELLS_SHA256[n] for n, src in
      (("training", CANDIDATE_TRAINING), ("evidence", CANDIDATE_EVIDENCE), ("aggregation", CANDIDATE_AGGREGATION))))
with _zf.ZipFile(EVZ) as z:
    names = set(z.namelist())
    sums = dict(reversed(l.split("  ", 1)) for l in z.read("SHA256SUMS.txt").decode().splitlines())
    bad = [n for n, h in sums.items() if hashlib.sha256(z.read(n)).hexdigest() != h]
check("run-evidence archive: SHA256SUMS verify", not bad and len(sums) > 0, f"{len(sums)} files")
check("run-evidence archive has run_status.json and every started run's attempts", "run_status.json" in names and all(
      f"runs/{n}__{CA.ATTEMPTS_FILE}" in names for k, sd, n in EXPECTED_RUNS if sd in SEEDS_TRAINED))
ok_v = {"V1": True, "V2": True, "V3": True, "V5": True, "V6": None}
v1 = CA.verdict(None, confirmatory=True, validity=ok_v, run_classes=st["run_classes"])
check("verdict with divergences present: FAIL", v1["verdict"] == "FAIL", v1["reason"])
no_div = {r: ("ok" if c == "divergence" else c) for r, c in st["run_classes"].items()}
v2 = CA.verdict(None, confirmatory=True, validity=ok_v, run_classes=no_div)
check("verdict without divergence, runs missing: NO VERDICT", v2["verdict"] == "NO VERDICT", v2["reason"])
check("no DENTEX data present", not any(DATA_ROOT.rglob("*")) and not glob.glob("/kaggle/input/*"))
PASSED = all(c["pass"] for c in checks.values())
report = {"preflight": "CV5 candidate path, no training", "result": "PASS" if PASSED else "FAIL", "n_checks": len(checks),
          "n_failed": sum(not c["pass"] for c in checks.values()), "checks": checks, "environment": env,
          "embedded_sha256": EMBEDDED_SHA256, "candidate_cells_sha256": CANDIDATE_CELLS_SHA256, "plan": PLAN,
          "run_evidence_zip_sha256": CV.sha256_file(EVZ)}
(ART / "preflight_report.json").write_text(json.dumps(report, indent=1, default=str))
OUTZ = WORK / "dentamind_cv5_preflight_output.zip"
with _zf.ZipFile(OUTZ, "w", _zf.ZIP_DEFLATED) as z:
    for p in (ART / "preflight_report.json", ART / "run_status.json", ART / "training_log.txt", EVZ):
        z.write(p, p.name)
log(f"PREFLIGHT RESULT: {report['result']} ({report['n_checks']} checks, {report['n_failed']} failed)")
log(f"OUTPUT {OUTZ}  sha256 {CV.sha256_file(OUTZ)}")
removed = 0
for p in list(RUNS.glob("*/best.pth")) + list(RUNS.glob("*/state.pt")):  # untrained random weights: not kept as notebook output
    p.unlink()
    removed += 1
for p in CACHE.glob("f*_*.npz"):
    p.unlink()
log(f"removed {removed} untrained pre-flight weight files and the synthetic arrays")""")
    keep = ("code", "# ---- P2b. keep the verbatim candidate cell sources for P3/P4 -----------------------------------------------------------\n"
                    f"CANDIDATE_TRAINING = {train!r}\nCANDIDATE_EVIDENCE = {evidence!r}\nCANDIDATE_AGGREGATION = {agg!r}\n"
                    "SEEDS_TRAINED = list(SEEDS)")
    return [head, NB.CELLS[1], MN.CELLS[2], embed, synth, keep, ("code", train), ("code", evidence), gate, check]


def main(out=None):
    out = Path(out) if out else HERE / "dentamind_cv5_preflight.ipynb"
    out.write_text(json.dumps(NB._notebook(build_cells()), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
