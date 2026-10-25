#!/usr/bin/env python
"""Generate kaggle/denta_mind_training.ipynb from the cell sources below (single source of truth; keeps the notebook diffable).

    .venv\\Scripts\\python.exe kaggle\\make_notebook.py
"""
import json
from pathlib import Path

CELLS = []


def md(s):
    CELLS.append(("markdown", s.strip("\n")))


def code(s):
    CELLS.append(("code", s.strip("\n")))


md(r"""
# DentaMind AI - finding-classifier class-imbalance experiments (Kaggle GPU)

Trains and compares the four-class finding classifier (Caries, Deep Caries, Impacted, Periapical Lesion) under a fixed protocol:

| Run | Change vs BASE (exactly one factor) |
|---|---|
| `BASE` | current recipe C0r: ResNet-50, 224 px GT crops, AdamW 3e-4, cosine 15 ep, batch 32, inverse-frequency weights capped at 5 |
| `REF_unweighted` | plain cross-entropy (reference) |
| `A1_sqrt_weights`, `A2_effnum_weights` | Strategy A: alternative class weights (training split only) |
| `B_sampler` | Strategy B: weighted sampler p ~ n_c^-0.5, plain CE |
| `C_focal` | Strategy C: focal loss, gamma 2 |
| `D_official_val` | Strategy D: + DENTEX official-validation findings (verified, same taxonomy) in training |
| `E_*` | best *justified* combination: only components that passed the acceptance rule on validation |

Validation = the project's fixed validation split (epoch selection + acceptance). The test split (previously used) is evaluated only for
BASE and for candidates that pass. **Nothing here changes the production model, its checkpoints or its abstention threshold.**

**Before running:** Settings -> Accelerator **GPU (T4 or P100)**, Internet **On** (needs a phone-verified Kaggle account), and
**Add Input** -> your private dataset containing `dentamind_kaggle_bundle.zip` (built locally with `kaggle/build_kaggle_bundle.py`).
Radiographs are fetched from the official DENTEX release (Hugging Face, CC BY-NC-SA 4.0) and every file is SHA-256 checked.
""")

code(r"""
# ---- configuration -------------------------------------------------------------------------------------------------
import os, sys, json, time, shutil, subprocess, glob, zipfile, hashlib, dataclasses
from pathlib import Path

SEEDS = [42, 43, 44, 45, 46]          # same seeds as every earlier project experiment
RUN = ["BASE", "REF_unweighted", "A1_sqrt_weights", "A2_effnum_weights", "B_sampler", "C_focal", "D_official_val"]
RUN_E = True                          # combination run, only if justified by the acceptance rule
RUN_TEST_EVAL = True                  # test split: BASE + passing candidates only
TIME_BUDGET_H = 11.0                  # Kaggle sessions stop at 12 h; no new run is started after this budget
RESUME_FROM = None                    # e.g. "/kaggle/input/<previous-output>/dentamind_artifacts/runs" to continue earlier runs

# Local smoke test only (never needed on Kaggle): DENTAMIND_SMOKE=1 -> 1 epoch, 2 seeds, 3 experiments;
# DENTAMIND_WORK / DENTAMIND_DATA_ROOT / DENTAMIND_BUNDLE override the folders and the bundle location.
SMOKE = os.environ.get("DENTAMIND_SMOKE") == "1"
if SMOKE:
    SEEDS, RUN = [42, 43], ["BASE", "B_sampler", "D_official_val"]

ON_KAGGLE = Path("/kaggle/working").exists()
WORK = Path(os.environ.get("DENTAMIND_WORK") or ("/kaggle/working" if ON_KAGGLE else "kaggle_work")).resolve()
ART = WORK / "dentamind_artifacts"
RUNS = ART / "runs"
DATA_ROOT = Path(os.environ.get("DENTAMIND_DATA_ROOT") or ("/tmp/dentamind_data" if ON_KAGGLE else WORK / "data"))  # not exported
CODE = WORK / "code"
CACHE = Path("/tmp/dentamind_cache") if ON_KAGGLE else WORK / "crop_cache"
for d in (ART, RUNS, DATA_ROOT, CODE, CACHE):
    d.mkdir(parents=True, exist_ok=True)
T0 = time.time()
LOG = ART / "training_log.txt"

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")

if RESUME_FROM and Path(RESUME_FROM).is_dir():
    shutil.copytree(RESUME_FROM, RUNS, dirs_exist_ok=True)
    log("resumed run folders from", RESUME_FROM)
""")

code(r"""
# ---- 1. GPU and software ----------------------------------------------------------------------------------------------
import numpy as np, PIL, platform, torch, torchvision
env = {"python": platform.python_version(), "torch": torch.__version__, "torchvision": torchvision.__version__, "numpy": np.__version__,
       "pillow": PIL.__version__, "cuda_available": torch.cuda.is_available(), "cuda": torch.version.cuda,
       "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "gpu_count": torch.cuda.device_count(),
       "disk_free_gb_working": round(shutil.disk_usage(WORK).free / 1e9, 1), "disk_free_gb_data": round(shutil.disk_usage(DATA_ROOT).free / 1e9, 1),
       "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
try:
    env["nvidia_smi"] = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                                       capture_output=True, text=True, timeout=20).stdout.strip()
except Exception as e:
    env["nvidia_smi"] = f"unavailable: {e}"
log(json.dumps(env, indent=1))
(ART / "environment.json").write_text(json.dumps(env, indent=1))
if not torch.cuda.is_available():
    log("WARNING: no GPU. Enable Accelerator = GPU; 35+ ResNet-50 runs on CPU are not practical.")
""")

code(r"""
# ---- 2. locate the code/manifest bundle -------------------------------------------------------------------------------
def find_bundle():
    for z in ([os.environ["DENTAMIND_BUNDLE"]] if os.environ.get("DENTAMIND_BUNDLE") else []) +              glob.glob("/kaggle/input/**/dentamind_kaggle_bundle.zip", recursive=True):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(CODE)
        return f"zip {z}"
    for p in glob.glob("/kaggle/input/**/kaggle/dentamind_kaggle.py", recursive=True):   # Kaggle auto-extracted the zip
        shutil.copytree(Path(p).parent.parent, CODE, dirs_exist_ok=True)
        return f"folder {Path(p).parent.parent}"
    repo = Path.cwd().parent if (Path.cwd().parent / "kaggle/dentamind_kaggle.py").is_file() else None   # local run from kaggle/
    if repo:
        shutil.copytree(repo / "kaggle", CODE / "kaggle", dirs_exist_ok=True)
        for sub in ("scripts/dataset", "data/splits", "reports"):
            shutil.copytree(repo / sub, CODE / sub, dirs_exist_ok=True)
        for f in ("data/raw/external/dentex_hf/validation_triple.json", "docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json",
                  "docs/audit_evidence/ml_improvement/imbalance/results.json"):
            (CODE / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo / f, CODE / f)
        return f"local repository {repo}"
    raise SystemExit("bundle not found: attach the private dataset that contains dentamind_kaggle_bundle.zip")

log("bundle:", find_bundle())
bm = CODE / "BUNDLE_MANIFEST.json"
if bm.is_file():
    want = json.loads(bm.read_text())["files"]
    bad = [f for f, h in want.items() if hashlib.sha256((CODE / f).read_bytes()).hexdigest() != h]
    assert not bad, f"bundle files modified or corrupted: {bad}"
    log(f"bundle verified: {len(want)} files, SHA-256 match")
for p in (CODE / "kaggle", CODE / "scripts/dataset"):
    sys.path.insert(0, str(p))
import dentamind_kaggle as DK
import download_external as DX
if SMOKE:
    for c in DK.EXPERIMENTS.values():
        c.epochs = 1
from dsutil import CLASSES, sha256_file
""")

code(r"""
# ---- 3. images: official DENTEX release, verified against the manifests -------------------------------------------------
SPLITS = CODE / "data/splits"
ROWS = {s: DK.load_split(SPLITS, s) for s in ("train", "validation", "calibration", "test")}
ALL = [r for rs in ROWS.values() for r in rs]
log({s: len(v) for s, v in ROWS.items()})

def attach_existing(rel_dir, marker):
    # reuse an attached Kaggle dataset that already holds this folder (verified below like everything else)
    for m in glob.glob(f"/kaggle/input/**/{marker}", recursive=True):
        src = Path(m).parent
        dst = DATA_ROOT / rel_dir
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(src, dst, target_is_directory=True)
        return str(src)
    return None

dis = "training_data/quadrant-enumeration-disease"
src = attach_existing(dis, "quadrant-enumeration-disease/train_quadrant_enumeration_disease.json")
n_ok, problems = DK.verify_images([r for r in ALL if r["image_path"].startswith(dis)], DATA_ROOT)
if problems:
    log("DENTEX disease subset not complete locally -> fetching only that folder from the official archive (about 2.9 GB, range requests)")
    t = time.time()
    DX.fetch_dentex_disease_subset(DATA_ROOT)
    log(f"  fetched in {time.time() - t:.0f}s")
else:
    log("DENTEX disease subset from attached dataset:", src)

vd = "validation_data/quadrant_enumeration_disease/xrays"
vd_rows = [r for r in ALL if r["image_path"].startswith(vd)]
if vd_rows and DK.verify_images(vd_rows, DATA_ROOT)[1] and         not attach_existing("validation_data/quadrant_enumeration_disease", "quadrant_enumeration_disease/xrays/val_0.png"):
    spec = DX.DOWNLOADS["dentex_hf_validation_images"]
    zp = DATA_ROOT / "_archives/validation_data.zip"
    log("official validation images:", DX.download(spec["url"], zp, spec["bytes"], spec["sha256"]))
    DX.safe_extract(zp, DATA_ROOT)

n_ok, problems = DK.verify_images(ALL, DATA_ROOT)
log(f"verified images: {n_ok} distinct radiographs, problems: {problems}")
assert not problems, "stop: images missing or not byte-identical to the manifests"
""")

code(r"""
# ---- 4. annotation and leakage checks on the loaded manifests -------------------------------------------------------------
import collections
for s, rs in ROWS.items():
    for r in rs:
        assert CLASSES[int(r["class_index"])] == r["target_class"], r["sample_id"]
        assert r["split"] == s
groups = {s: {r["radiograph_group"] for r in rs} for s, rs in ROWS.items()}
shas = {s: {r["image_sha256"] for r in rs} for s, rs in ROWS.items()}
names = list(ROWS)
overlap = {f"{a} vs {b}": (len(groups[a] & groups[b]), len(shas[a] & shas[b])) for i, a in enumerate(names) for b in names[i + 1:]}
log("group / sha overlaps:", overlap)
assert all(v == (0, 0) for v in overlap.values()), "leakage: a radiograph appears in two splits"
assert {r["source_dataset"] for r in ROWS["validation"] + ROWS["test"] + ROWS["calibration"]} == {"dentex_train_disease"}
audit = json.loads((CODE / "reports/combined_split_audit.json").read_text())
assert audit["fixed_evaluation_sets"]["validation_identical_to_project_val"], "validation split differs from the project split"
for s in names:
    log(s, dict(collections.Counter((r["source_dataset"], r["target_class"]) for r in ROWS[s])))
""")

code(r"""
# ---- 5. class distribution and TRAINING-ONLY weights -------------------------------------------------------------------
y_dx = np.array([int(r["class_index"]) for r in ROWS["train"] if r["source_dataset"] == "dentex_train_disease"])
y_all = np.array([int(r["class_index"]) for r in ROWS["train"]])
before = {r["class"]: int(r["crops_after_crop_rule"]) for r in DK.read_csv(CODE / "reports/class_imbalance_before.csv") if r["split"] == "train"}
assert dict(zip(CLASSES, np.bincount(y_dx, minlength=4).tolist())) == before, "DENTEX training counts differ from the audited counts"
dist = {"train_dentex": dict(zip(CLASSES, np.bincount(y_dx, minlength=4).tolist())),
        "train_dentex+official_val": dict(zip(CLASSES, np.bincount(y_all, minlength=4).tolist())),
        "validation": dict(collections.Counter(r["target_class"] for r in ROWS["validation"])),
        "test": dict(collections.Counter(r["target_class"] for r in ROWS["test"]))}
weights = {f"{data}:{sch}": (lambda w: None if w is None else dict(zip(CLASSES, np.round(w, 4).tolist())))(DK.class_weights(np.bincount(y, minlength=4), sch))
           for data, y in (("dentex", y_dx), ("dentex+official_val", y_all)) for sch in ("none", "inverse_cap5", "sqrt", "effective_number")}
exposure = {"dentex": DK.sampler_exposure(y_dx), "dentex+official_val": DK.sampler_exposure(y_all)}
log(json.dumps({"distribution": dist, "class_weights_from_train_only": weights, "sampler_expected_draws_per_sample_per_epoch": exposure}, indent=1))
(ART / "class_distribution_and_weights.json").write_text(json.dumps({"distribution": dist, "weights": weights, "sampler_exposure": exposure}, indent=1))
""")

code(r"""
# ---- 6. crops (identical rule to production) + cached production-detector crops for validation --------------------------
t = time.time()
Xtr_all, ytr_all, mtr_all = DK.build_crops(ROWS["train"], DATA_ROOT, CACHE / "train_all.npz")
is_dx = np.array([r["source_dataset"] == "dentex_train_disease" for r in ROWS["train"]])
TRAIN = {"dentex": {"X": Xtr_all[is_dx], "y": ytr_all[is_dx]}, "dentex+official_val": {"X": Xtr_all, "y": ytr_all}}
Xva, yva, _ = DK.build_crops(ROWS["validation"], DATA_ROOT, CACHE / "val.npz")
VAL = {"X": Xva, "y": yva}
Xd, mi, missed = DK.build_detector_crops(ROWS["validation"], DATA_ROOT,
                                         CODE / "docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json",
                                         lambda r: r["project_image_id"])
Xte, yte, _ = DK.build_crops(ROWS["test"], DATA_ROOT, CACHE / "test.npz") if ROWS["test"] else (None, None, None)
log(f"crops: train {len(ytr_all)} (DENTEX {is_dx.sum()}), val {len(yva)} (detector-matched {len(mi)}, unmatched {missed}), "
    f"test {0 if yte is None else len(yte)}  [{time.time() - t:.0f}s]  disk free {DK.free_disk_gb()} GB")
""")

code(r"""
# ---- 7. train (resumable; one run per experiment x seed) ----------------------------------------------------------------
def budget_left():
    return TIME_BUDGET_H * 3600 - (time.time() - T0)

# every run trains in its own process (a CUDA fault cannot take down the remaining runs); failed attempts resume from the
# last completed epoch; a run that fails 3 times is recorded in runs/<exp>_s<seed>/failure.json and the notebook continues
NPZ = {k: DK.save_arrays(CACHE / f"arr_{k.replace('+', '_')}.npz", v) for k, v in TRAIN.items()}
NPZ_VAL = DK.save_arrays(CACHE / "arr_val.npz", VAL)
FAILED = []

def run_experiment(cfg):
    out = {}
    for sd in SEEDS:
        if budget_left() < 900:
            log("TIME BUDGET reached: no new run started. Save the notebook output, then rerun with RESUME_FROM set.")
            return out
        r = DK.train_run_isolated(cfg, sd, NPZ[cfg.data], NPZ_VAL, RUNS, log=log)
        if r.get("failed"):
            FAILED.append(f"{cfg.name}_s{sd}")
            log(f"{cfg.name} s{sd}: FAILED after retries - see runs/{cfg.name}_s{sd}/failure.json")
            continue
        out[sd] = r
        log(f"{cfg.name} s{sd}: best ep {r['best_epoch']} val macro-F1 {r['val_gt']['macro_f1']:.4f}  gpu-peak {r['gpu'].get('peak_alloc_mb')} MB  "
            f"disk {DK.free_disk_gb()} GB  elapsed {(time.time() - T0) / 3600:.2f} h")
    return out

TRAINED = {}
for name in RUN:
    TRAINED[name] = run_experiment(DK.EXPERIMENTS[name])
log("failed runs:", FAILED or "none")
""")

code(r"""
# ---- 8. validation evaluation (GT boxes + production-detector boxes) and the acceptance rule -----------------------------
def eval_runs(name, X=Xva, y=yva, det=True):
    res = {}
    for sd in SEEDS:
        ck = RUNS / f"{name}_s{sd}" / "best.pth"
        if ck.is_file():
            res[sd] = DK.evaluate_checkpoint(ck, X, y, Xd if det else None, mi if det else None)
    return res

EVAL = {name: eval_runs(name) for name in RUN}
ACC = {name: DK.acceptance(EVAL[name], EVAL["BASE"]) for name in RUN if name != "BASE" and EVAL.get(name)}
for n, a in ACC.items():
    log(f"{n:22s} pass={a.get('pass')}  gain={a.get('mean_gain_macro_f1', float('nan')):+.4f}  criteria={a.get('criteria')}")
(ART / "validation_eval.json").write_text(json.dumps({"eval": {k: {str(s): v for s, v in d.items()} for k, d in EVAL.items()},
                                                      "acceptance": ACC, "rule": DK.ACCEPT}, indent=1, default=float))
""")

code(r"""
# ---- 9. Experiment E: combination of components that individually passed (if any) ---------------------------------------
strategies = [n for n in ("A1_sqrt_weights", "A2_effnum_weights", "B_sampler", "C_focal") if ACC.get(n, {}).get("pass")]
best_strategy = max(strategies, key=lambda n: ACC[n]["mean_gain_macro_f1"]) if strategies else None
use_data = bool(ACC.get("D_official_val", {}).get("pass"))
E_NAME, E_NOTE = None, ""
if not RUN_E:
    E_NOTE = "not run (RUN_E = False)"
elif best_strategy and use_data:
    base = DK.EXPERIMENTS[best_strategy]
    cfgE = dataclasses.replace(base, name=f"E_{best_strategy}+D", data="dentex+official_val",
                               note=f"combination of passing components: {best_strategy} + official-val data")
    DK.EXPERIMENTS[cfgE.name] = cfgE
    TRAINED[cfgE.name] = run_experiment(cfgE)
    EVAL[cfgE.name] = eval_runs(cfgE.name)
    ACC[cfgE.name] = DK.acceptance(EVAL[cfgE.name], EVAL["BASE"])
    E_NAME, E_NOTE = cfgE.name, f"ran {cfgE.name}; pass={ACC[cfgE.name]['pass']}"
elif best_strategy or use_data:
    E_NOTE = f"no combination needed: only one component passed ({best_strategy or 'D_official_val'}); E = that experiment"
else:
    E_NOTE = "not run: no single strategy passed the acceptance rule, so no combination is justified"
log("Experiment E:", E_NOTE)
""")

code(r"""
# ---- 10. test split: BASE and passing candidates only (+ deployed reference if bundled) ----------------------------------
TEST = {}
passing = [n for n, a in ACC.items() if a.get("pass")]
if RUN_TEST_EVAL and Xte is not None:
    for name in ["BASE"] + passing:
        TEST[name] = eval_runs(name, Xte, yte, det=False)
    log("test evaluated for:", list(TEST), "(selection used validation only)")
dep = CODE / "data/checkpoints/dentex_findings_classification_v1.pth"
DEPLOYED = None
if dep.is_file():
    DEPLOYED = {"sha256": sha256_file(dep), "val": DK.evaluate_checkpoint(dep, Xva, yva, Xd, mi),
                "test": DK.evaluate_checkpoint(dep, Xte, yte) if (RUN_TEST_EVAL and Xte is not None) else None}
    log("deployed reference val macro-F1 (GT / det):", round(DEPLOYED["val"]["gt"]["macro_f1"], 4), round(DEPLOYED["val"]["det_matched"]["macro_f1"], 4))
(ART / "test_eval.json").write_text(json.dumps({"evaluated": {k: {str(s): v for s, v in d.items()} for k, d in TEST.items()},
                                                "deployed_reference": DEPLOYED,
                                                "ledger_note": "record this test use in data/reports/test_set_ledger.json after download"},
                                               indent=1, default=float))
""")

code(r"""
# ---- 11. results tables, plots, candidate selection --------------------------------------------------------------------
import csv, statistics as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def agg(vals):
    vals = [v for v in vals if v is not None]
    return (round(st.mean(vals), 4), round(st.stdev(vals), 4) if len(vals) > 1 else 0.0) if vals else (None, None)

rows = []
def add_rows(split, name, res, setting):
    seeds = sorted(res)
    if not seeds:
        return
    get = lambda f: [f(res[s]) for s in seeds]
    rec = {"split": split, "experiment": name, "setting": setting, "seeds": " ".join(map(str, seeds)), "n_seeds": len(seeds),
           "note": DK.EXPERIMENTS[name].note if name in DK.EXPERIMENTS else ""}
    for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "balanced_accuracy", "ece_10bin", "nll"):
        rec[f"{k}_mean"], rec[f"{k}_sd"] = agg(get(lambda r: r[setting].get(k)))
    for c in CLASSES:
        for m in ("precision", "recall", "f1", "false_positives"):
            rec[f"{c}_{m}_mean"], _ = agg(get(lambda r: r[setting]["per_class"][c][m]))
    ab = get(lambda r: (r[setting].get("abstention_production_rule") or {}).get("abstained"))
    rec["abstained_mean"], _ = agg(ab)
    rec["accepted_mean"], _ = agg(get(lambda r: (r[setting].get("abstention_production_rule") or {}).get("accepted")))
    if split == "validation" and name in ACC:
        rec["acceptance_pass"] = ACC[name].get("pass")
        rec["acceptance_detail"] = json.dumps(ACC[name].get("criteria"))
    rows.append(rec)

for name, res in EVAL.items():
    add_rows("validation", name, res, "gt")
    add_rows("validation", name, res, "det_matched")
for name, res in TEST.items():
    add_rows("test", name, res, "gt")
fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("split", "experiment", "setting", "n_seeds", "seeds"), k))
with open(ART / "imbalance_experiment_results.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

# confusion matrices (sum over seeds, validation, detector boxes)
names = [n for n in EVAL if EVAL[n]]
fig, axes = plt.subplots(1, len(names), figsize=(3.2 * len(names), 3.4))
for ax, n in zip(np.atleast_1d(axes), names):
    cm = np.sum([np.array(EVAL[n][s]["det_matched"]["confusion"]) for s in EVAL[n]], axis=0)
    ax.imshow(cm / cm.sum(1, keepdims=True), cmap="Blues", vmin=0, vmax=1)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, int(cm[i, j]), ha="center", va="center", fontsize=7)
    ax.set_title(n, fontsize=8)
    ax.set_xticks(range(4), ["C", "DC", "Imp", "PL"], fontsize=7)
    ax.set_yticks(range(4), ["C", "DC", "Imp", "PL"], fontsize=7)
fig.suptitle("Validation confusion matrices (rows = truth, detector-box crops, summed over seeds)", fontsize=9)
fig.tight_layout()
fig.savefig(ART / "confusion_matrices_validation.png", dpi=120)

# per-class bar chart DC / PL recall + precision
fig, ax = plt.subplots(figsize=(9, 3.6))
xs = np.arange(len(names))
for k, (c, m) in enumerate([("Deep Caries", "recall"), ("Deep Caries", "precision"), ("Periapical Lesion", "recall"), ("Periapical Lesion", "precision")]):
    v = [np.mean([EVAL[n][s]["det_matched"]["per_class"][c][m] for s in EVAL[n]]) for n in names]
    ax.bar(xs + (k - 1.5) * 0.2, v, 0.2, label=f"{c} {m}")
ax.set_xticks(xs, names, rotation=20, fontsize=7)
ax.set_ylim(0, 1)
ax.legend(fontsize=7)
ax.set_title("Minority classes, validation (detector boxes), mean over seeds", fontsize=9)
fig.tight_layout()
fig.savefig(ART / "minority_class_metrics.png", dpi=120)

# candidate selection (validation only): best passing experiment, its best seed on validation detector-box macro-F1
cand_name = max(passing, key=lambda n: ACC[n]["mean_gain_macro_f1"]) if passing else None
def best_seed(n):
    return max(EVAL[n], key=lambda s: EVAL[n][s]["det_matched"]["macro_f1"])
def median_seed(n):
    order = sorted(EVAL[n], key=lambda s: EVAL[n][s]["det_matched"]["macro_f1"])
    return order[len(order) // 2]
SELECTION = {"candidate": None if not cand_name else {"experiment": cand_name, "seed": best_seed(cand_name)},
             "baseline_record": {"experiment": "BASE", "seed": median_seed("BASE"), "why": "median-seed BASE run (representative)"},
             "rule": "acceptance rule on validation only; test never used for selection", "experiment_E": E_NOTE,
             "failed_runs": FAILED}
log(json.dumps(SELECTION, indent=1))
""")

code(r"""
# ---- 12. package artifacts -------------------------------------------------------------------------------------------------
pkg = ART / "package"
if pkg.exists():
    shutil.rmtree(pkg)
(pkg / "checkpoints").mkdir(parents=True)
def put_ck(exp, sd, role):
    src = RUNS / f"{exp}_s{sd}"
    for f in ("best.pth", "best.json"):
        shutil.copy2(src / f, pkg / "checkpoints" / f"{role}__{exp}_s{sd}{Path(f).suffix}")
if SELECTION["candidate"]:
    put_ck(SELECTION["candidate"]["experiment"], SELECTION["candidate"]["seed"], "candidate")
b = SELECTION["baseline_record"]
put_ck(b["experiment"], b["seed"], "baseline")

ck_manifest = {"runs": {}, "packaged": sorted(p.name for p in (pkg / "checkpoints").iterdir())}
for d in sorted(RUNS.iterdir()):
    if (d / "best.pth").is_file():
        r = json.loads((d / "result.json").read_text())
        ck_manifest["runs"][d.name] = {"sha256": r["checkpoint_sha256"], "bytes": (d / "best.pth").stat().st_size, "best_epoch": r["best_epoch"],
                                       "val_gt_macro_f1": r["val_gt"]["macro_f1"]}
(pkg / "checkpoint_manifest.json").write_text(json.dumps(ck_manifest, indent=1))

for f in ("imbalance_experiment_results.csv", "validation_eval.json", "test_eval.json", "environment.json", "training_log.txt",
          "class_distribution_and_weights.json", "confusion_matrices_validation.png", "minority_class_metrics.png"):
    if (ART / f).is_file():
        shutil.copy2(ART / f, pkg / f)
(pkg / "runs").mkdir()
for d in sorted(RUNS.iterdir()):
    if (d / "result.json").is_file():
        shutil.copy2(d / "result.json", pkg / "runs" / f"{d.name}.json")
(pkg / "experiment_configs.json").write_text(json.dumps({n: dataclasses.asdict(c) for n, c in DK.EXPERIMENTS.items()}, indent=1))
(pkg / "selection.json").write_text(json.dumps(SELECTION, indent=1))
for f in ("data/splits/combined_train.csv", "data/splits/combined_validation.csv", "data/splits/combined_calibration.csv",
          "data/splits/combined_test.csv", "data/splits/combined_excluded.csv", "reports/combined_split_audit.json",
          "reports/class_imbalance_before.csv", "reports/class_imbalance_after.csv", "reports/class_distribution_before.png",
          "reports/class_distribution_after.png", "reports/dataset_inventory.json", "reports/dataset_source_inventory.csv"):
    (pkg / f).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CODE / f, pkg / f)

hrs = (time.time() - T0) / 3600
lines = ["# DentaMind balanced-training artifacts", "",
         f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} on {env.get('gpu')} (torch {env['torch']}), runtime {hrs:.2f} h.", "",
         "**Production was not changed.** These are candidates for offline review only.", "",
         "## Acceptance (validation, vs BASE; project's pre-registered criteria)", "",
         "| Experiment | pass | mean macro-F1 gain (det) | DC recall delta | PL recall delta | criteria |", "|---|---|---|---|---|---|"]
for n, a in ACC.items():
    if "criteria" in a:
        lines.append(f"| {n} | {a['pass']} | {a['mean_gain_macro_f1']:+.4f} | {a['minority_recall_delta']['Deep Caries']:+.3f} | "
                     f"{a['minority_recall_delta']['Periapical Lesion']:+.3f} | {a['criteria']} |")
    else:
        lines.append(f"| {n} | {a.get('pass')} | - | - | - | {a.get('reason')} |")
lines += ["", f"Experiment E: {E_NOTE}", "", f"Selection: `{json.dumps(SELECTION)}`", "",
          "## Limitations", "",
          "* Validation is used for epoch selection and for the acceptance rule (optimistic for every method alike).",
          "* Periapical Lesion has 9 validation findings and 13 test findings: minority metrics are fragile.",
          "* The test split was used before (see the project's test-set ledger); there is no independent external test set.",
          "* The official DENTEX test labels use a different taxonomy and were not used.",
          "* No patient ids: separation is per radiograph, not per patient.",
          "* Abstention counts use the production entropy threshold fitted for the deployed model, not refitted.",
          "* Full per-run metrics: runs/*.json; all run checkpoint hashes: checkpoint_manifest.json."]
(pkg / "README.md").write_text("\n".join(lines))

sums = []
for p in sorted(pkg.rglob("*")):
    if p.is_file():
        sums.append(f"{sha256_file(p)}  {p.relative_to(pkg).as_posix()}")
(pkg / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
zp = WORK / "dentamind_balanced_training_artifacts.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(pkg.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(pkg).as_posix())
log(f"ARCHIVE {zp}  {zp.stat().st_size / 2**20:.1f} MB  sha256 {sha256_file(zp)}")
log("Download: notebook viewer -> Output -> dentamind_balanced_training_artifacts.zip (or `kaggle kernels output <user>/<slug>`).")
""")


def build():
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}, "kaggle": {"accelerator": "gpu", "isInternetEnabled": True}},
          "cells": []}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": kind, "id": f"cell-{i:02d}", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    out = Path(__file__).resolve().parent / "denta_mind_training.ipynb"
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(CELLS)} cells)")


if __name__ == "__main__":
    build()
