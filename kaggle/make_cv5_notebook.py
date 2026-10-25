#!/usr/bin/env python
"""Generate kaggle/dentamind_5fold_cv.ipynb: grouped 5-fold CV of the BASE classifier (protocol reports/cv5_protocol.md).

    .venv\\Scripts\\python.exe kaggle\\make_cv5_notebook.py

Reuses the GPU and bundle-verification cells of make_notebook.py unchanged. The bundle (private Kaggle dataset, version with
--with-deployed-checkpoint --with-external) provides dentamind_kaggle.py, dsutil, the split manifests, the production tooth detector
and the cached validation detector boxes. Three files that are not in that bundle are embedded here and hash-checked on Kaggle:
kaggle/cv5_lib.py, scripts/dataset/make_cv_folds.py and the approved fold file data/splits/cv5_folds_v1.csv.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import make_notebook as MN  # noqa: E402

EMBED = {"kaggle/cv5_lib.py": HERE / "cv5_lib.py",
         "scripts/dataset/make_cv_folds.py": ROOT / "scripts/dataset/make_cv_folds.py",
         "data/splits/cv5_folds_v1.csv": ROOT / "data/splits/cv5_folds_v1.csv"}
FILES = {k: p.read_bytes().decode("utf-8") for k, p in EMBED.items()}
SHAS = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in FILES.items()}

CELLS = [("markdown", """# DentaMind AI - grouped 5-fold cross-validation of the BASE finding classifier (Kaggle GPU)

Pre-registered protocol: `reports/cv5_protocol.md` (2026-10-24). Approved fold file `data/splits/cv5_folds_v1.csv` (P4 option B).
Unit = radiograph (DENTEX has no patient ids). BASE recipe unchanged; 5 folds x seeds 42-46 = 25 runs. Epoch selection on a
group-disjoint inner validation subset of the training folds; every held-out fold is predicted once per seed. **No test or
calibration image is read.** No new model is compared and no improvement is claimed.

**Before running:** GPU T4, Internet **On** (DENTEX images from the official archive), Add Input -> the private bundle dataset
(`dentamind_kaggle_bundle`, built with `--with-deployed-checkpoint --with-external`). Runs are resumable: if the session stops, add
this notebook's previous output as input and set `RESUME_FROM`. Output: `dentamind_5fold_cv_artifacts.zip`."""),
         ("code", """# ---- configuration -----------------------------------------------------------------------------------------------
import os, sys, json, time, shutil, subprocess, glob, zipfile, hashlib, dataclasses, collections
from pathlib import Path
import numpy as np

SEEDS = [42, 43, 44, 45, 46]          # protocol section 3
FOLDS = [0, 1, 2, 3, 4]               # all five folds; never reduced
TIME_BUDGET_H = 11.0                  # Kaggle sessions stop at 12 h; no new run starts after this budget
RESUME_FROM = None                    # e.g. "/kaggle/input/<this notebook's previous output>/cv5/runs"

# Local pipeline check only (never on Kaggle): DENTAMIND_SMOKE=1 -> 1 epoch, seed 42, all 5 folds; output marked SMOKE.
SMOKE = os.environ.get("DENTAMIND_SMOKE") == "1"
if SMOKE:
    SEEDS = [42]

ON_KAGGLE = Path("/kaggle/working").exists()
WORK = Path(os.environ.get("DENTAMIND_WORK") or ("/kaggle/working" if ON_KAGGLE else "kaggle_work_cv5")).resolve()
ART = WORK / "cv5"
RUNS = ART / "runs"
DATA_ROOT = Path(os.environ.get("DENTAMIND_DATA_ROOT") or ("/tmp/dentamind_data" if ON_KAGGLE else WORK / "data"))
CODE = WORK / "code"
CACHE = Path("/tmp/dentamind_cache_cv5") if ON_KAGGLE else WORK / "cache"
for d in (ART, RUNS, DATA_ROOT, CODE, CACHE):
    d.mkdir(parents=True, exist_ok=True)
T0 = time.time()
LOG = ART / "training_log.txt"

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\\n")

if RESUME_FROM and Path(RESUME_FROM).is_dir():
    shutil.copytree(RESUME_FROM, RUNS, dirs_exist_ok=True)
    log("resumed run folders from", RESUME_FROM)
log("CV5", "SMOKE (pipeline check, not a result)" if SMOKE else "full run", "seeds", SEEDS, "folds", FOLDS)"""),
         MN.CELLS[2],                       # GPU and software (unchanged)
         MN.CELLS[3],                       # bundle location + SHA-256 verification + imports DK, DX (unchanged)
         ("code", f"""# ---- 2b. files not in the bundle (embedded, hash-checked) -----------------------------------------------------------
EMBEDDED = {json.dumps(FILES)}
EMBEDDED_SHA256 = {json.dumps(SHAS)}
for rel, txt in EMBEDDED.items():
    assert hashlib.sha256(txt.encode("utf-8")).hexdigest() == EMBEDDED_SHA256[rel], f"embedded file changed: {{rel}}"
    (CODE / rel).parent.mkdir(parents=True, exist_ok=True)
    (CODE / rel).write_text(txt, encoding="utf-8", newline="")
    log("embedded", rel, EMBEDDED_SHA256[rel][:16])
import cv5_lib as CV
assert CV.sha256_file(CODE / "data/splits/cv5_folds_v1.csv") == CV.FOLD_FILE_SHA256"""),
         ("code", """# ---- 3. folds: approved file + gate 1 (protocol sections 2 and 7) -------------------------------------------------------
SPLITS = CODE / "data/splits"
ROWS = {s: DK.load_split(SPLITS, s) for s in ("train", "validation", "calibration", "test")}   # calibration/test: ids only
FOLD_OF = CV.load_folds(SPLITS / "cv5_folds_v1.csv")
GATE1 = CV.check_folds(FOLD_OF, ROWS)
log("gate 1 passed:", json.dumps({k: GATE1[k] for k in ("pool_groups", "pool_findings", "radiographs_per_fold")}))
POOL = [r for s in CV.POOL_SPLITS for r in ROWS[s]]
PRIMARY_ROWS = [r for r in POOL if r["source_dataset"] == CV.PRIMARY]
SECONDARY_ROWS = [r for r in POOL if r["source_dataset"] == CV.SECONDARY]
assert len(PRIMARY_ROWS) == 2851 and len(SECONDARY_ROWS) == 159, (len(PRIMARY_ROWS), len(SECONDARY_ROWS))
del ROWS["calibration"], ROWS["test"]          # nothing below can use them
PLANS = {k: CV.fold_plan(POOL, FOLD_OF, k) for k in FOLDS}
GATE2 = {k: CV.check_plan(PLANS[k], FOLD_OF) for k in FOLDS}
for k, g in GATE2.items():
    log(f"gate 2 fold {k}: fit {g['fit']['radiographs']} r / {g['fit']['findings']} f, inner {g['inner']['radiographs']} r / "
        f"{g['inner']['findings']} f, held-out {g['heldout']['radiographs']} r / {g['heldout']['findings']} f "
        f"(+ official-val {g['heldout_secondary']['findings']} f)")
(ART / "fold_plan.json").write_text(json.dumps({"fold_file_sha256": CV.FOLD_FILE_SHA256, "gate1": GATE1, "gate2": GATE2,
    "groups": {k: {n: sorted({r["radiograph_group"] for r in PLANS[k][n]}) for n in ("fit", "inner", "heldout", "heldout_secondary")}
               for k in FOLDS}}, indent=1))"""),
         ("code", """# ---- 4. images of the pool only (official archive, SHA-256 verified per image) ---------------------------------------------
dis = "training_data/quadrant-enumeration-disease"
if DK.verify_images([r for r in POOL if r["image_path"].startswith(dis)], DATA_ROOT)[1]:
    log("fetching the DENTEX disease subset from the official archive (about 2.9 GB, range requests)")
    t = time.time()
    DX.fetch_dentex_disease_subset(DATA_ROOT)
    log(f"  fetched in {time.time() - t:.0f}s")
vd = [r for r in POOL if r["image_path"].startswith("validation_data/")]
if vd and DK.verify_images(vd, DATA_ROOT)[1]:
    spec = DX.DOWNLOADS["dentex_hf_validation_images"]
    zp = DATA_ROOT / "_archives/validation_data.zip"
    log("official validation images:", DX.download(spec["url"], zp, spec["bytes"], spec["sha256"]))
    DX.safe_extract(zp, DATA_ROOT)
n_ok, problems = DK.verify_images(POOL, DATA_ROOT)
log(f"pool images verified: {n_ok} radiographs, problems: {problems}")
assert not problems, "stop: pool images missing or not byte-identical to the manifests\""""),
         ("code", """# ---- 5. crops (production crop rule) for every pool finding ---------------------------------------------------------------
t = time.time()
X_ALL, Y_ALL, _ = DK.build_crops(POOL, DATA_ROOT, CACHE / "pool_gt.npz")
IDX = {r["sample_id"]: i for i, r in enumerate(POOL)}
log(f"GT crops: {len(Y_ALL)} findings [{time.time() - t:.0f}s]")"""),
         ("code", """# ---- 6. production-detector boxes for every pool radiograph + gate 3 ------------------------------------------------------
DET_CACHE = ART / "detector_boxes_pool.json"
det_boxes = json.loads(DET_CACHE.read_text()) if DET_CACHE.is_file() else {}
det = CV.ProductionDetector(CODE / "data/checkpoints/dentex_teeth_detection_v1.pth")
t = time.time()
for r in POOL:
    k = r["project_image_id"]
    if k not in det_boxes:
        det_boxes[k] = det.boxes(DATA_ROOT / r["image_path"])
DET_CACHE.write_text(json.dumps(det_boxes))
del det
log(f"detector boxes for {len(det_boxes)} radiographs [{time.time() - t:.0f}s]")
cached = json.loads((CODE / "docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json").read_text())
GATE3 = CV.compare_detector(ROWS["validation"], det_boxes, cached)
log("gate 3 (detector reproduction on the 65 old-validation radiographs):",
    {k: v for k, v in GATE3.items() if k != "images_with_different_match"})
DET_OK = GATE3["pass"]
if not DET_OK:
    log("GATE 3 FAILED: detector-box results will NOT be reported (protocol section 7); GT-box results still are")
XD, MI, MISSED = DK.build_detector_crops(POOL, DATA_ROOT, DET_CACHE, lambda r: r["project_image_id"])
MATCHED = np.zeros(len(POOL), bool)
MATCHED[MI] = True
XD_OF = np.full(len(POOL), -1)
XD_OF[MI] = np.arange(len(MI))
log(f"detector-matched findings: {int(MATCHED.sum())} / {len(POOL)} (unmatched {MISSED})")"""),
         ("code", """# ---- 7. train 5 folds x seeds (resumable, isolated processes) and predict each held-out fold once ----------------------------
import torch, torchvision as tv
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FAILED = []

def budget_left():
    return TIME_BUDGET_H * 3600 - (time.time() - T0)

def predict_heldout(ck, rows):
    if not rows:
        return np.zeros(0, int), np.zeros((0, len(DK.CLASSES))), np.zeros((0, len(DK.CLASSES)))
    m = DK.new_model(torch, tv, pretrained=False)
    m.load_state_dict(torch.load(ck, map_location="cpu", weights_only=True), strict=True)
    m.to(dev)
    ii = np.array([IDX[r["sample_id"]] for r in rows])
    pg = DK.predict(torch, m, X_ALL[ii], dev)
    pd = np.full_like(pg, np.nan)
    has = MATCHED[ii]
    if has.any():
        pd[has] = DK.predict(torch, m, XD[XD_OF[ii[has]]], dev)
    del m
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return ii, pg, pd

for k in FOLDS:
    plan = PLANS[k]
    take = lambda rows: {"X": X_ALL[[IDX[r["sample_id"]] for r in rows]], "y": Y_ALL[[IDX[r["sample_id"]] for r in rows]]}
    fit_npz = DK.save_arrays(CACHE / f"f{k}_fit.npz", take(plan["fit"]))
    inner_npz = DK.save_arrays(CACHE / f"f{k}_inner.npz", take(plan["inner"]))
    cfg = CV.fold_config(k)
    for sd in SEEDS:
        out = RUNS / f"{cfg.name}_s{sd}"
        if (out / "heldout_pred.npz").is_file():
            log(f"{cfg.name} s{sd}: already predicted - skipped")
            continue
        if budget_left() < 900:
            log("TIME BUDGET reached: no new run started. Save the output, then rerun with RESUME_FROM set.")
            break
        r = DK.train_run_isolated(cfg, sd, fit_npz, inner_npz, RUNS, log=log)
        if r.get("failed"):
            FAILED.append(f"{cfg.name}_s{sd}")
            log(f"{cfg.name} s{sd}: FAILED after retries - see {out}/failure.json")
            continue
        ii, pg, pd = predict_heldout(out / "best.pth", plan["heldout"])
        ii2, pg2, pd2 = predict_heldout(out / "best.pth", plan["heldout_secondary"])
        np.savez(out / "heldout_pred.npz", idx=ii, gt=pg, det=pd, idx_sec=ii2, gt_sec=pg2, det_sec=pd2)
        (out / "cv_run.json").write_text(json.dumps({"fold": k, "seed": sd, "fit_findings": len(plan["fit"]),
            "inner_findings": len(plan["inner"]), "heldout_findings": len(plan["heldout"]),
            "heldout_secondary_findings": len(plan["heldout_secondary"]), "best_epoch": r["best_epoch"],
            "inner_val_macro_f1": r["val_gt"]["macro_f1"], "checkpoint_sha256": r["checkpoint_sha256"],
            "note": "result.json split_note is the generic BASE text; for CV the validation set is the fold's inner validation subset"}, indent=1))
        log(f"{cfg.name} s{sd}: best ep {r['best_epoch']} inner-val macro-F1 {r['val_gt']['macro_f1']:.4f}  "
            f"elapsed {(time.time() - T0) / 3600:.2f} h")
log("failed runs:", FAILED or "none")"""),
         ("code", """# ---- 8. out-of-fold evaluation (gates 4 and 5), aggregation, bootstrap, Caries vs Deep Caries ----------------------------------
P_IDX = np.array([IDX[r["sample_id"]] for r in PRIMARY_ROWS])
S_IDX = np.array([IDX[r["sample_id"]] for r in SECONDARY_ROWS])
pos = {g: i for i, g in enumerate(P_IDX)}
spos = {g: i for i, g in enumerate(S_IDX)}
n, ns, C = len(P_IDX), len(S_IDX), len(DK.CLASSES)
OOF, OOF_S, FOLD_OF_FINDING = {}, {}, np.full(n, -1)
missing_runs = []
for sd in SEEDS:
    o = {"gt": np.full((n, C), np.nan), "det": np.full((n, C), np.nan), "filled": np.zeros(n, int)}
    os_ = {"gt": np.full((ns, C), np.nan), "det": np.full((ns, C), np.nan)}
    for k in FOLDS:
        f = RUNS / f"{CV.run_name(k)}_s{sd}" / "heldout_pred.npz"
        if not f.is_file():
            missing_runs.append(f.parent.name)
            continue
        z = np.load(f)
        rows_i = np.array([pos[i] for i in z["idx"]])
        o["gt"][rows_i], o["det"][rows_i] = z["gt"], z["det"]
        o["filled"][rows_i] += 1
        FOLD_OF_FINDING[rows_i] = k
        if len(z["idx_sec"]):
            si = np.array([spos[i] for i in z["idx_sec"]])
            os_["gt"][si], os_["det"][si] = z["gt_sec"], z["det_sec"]
    OOF[sd], OOF_S[sd] = o, os_
assert not FAILED and not missing_runs, f"gate 4: runs missing {FAILED + missing_runs} - resume with RESUME_FROM; nothing is reported"
CV.check_oof(OOF, n, SEEDS)
log("gates 4 and 5 passed: every primary finding has exactly one out-of-fold prediction per seed")

y = Y_ALL[P_IDX]
m = MATCHED[P_IDX]
groups = np.array([r["radiograph_group"] for r in PRIMARY_ROWS])
POOLED = CV.pooled_reports(y, OOF, m, SEEDS)
settings = ["gt"] + (["det_matched"] if DET_OK else [])
SUMMARY = {s: {"macro_f1": CV.mean_sd([POOLED[sd][s]["macro_f1"] for sd in SEEDS]),
               "accuracy": CV.mean_sd([POOLED[sd][s]["accuracy"] for sd in SEEDS]),
               "ece_10bin": CV.mean_sd([POOLED[sd][s]["ece_10bin"] for sd in SEEDS]),
               "per_class": {c: {mm: CV.mean_sd([POOLED[sd][s]["per_class"][c][mm] for sd in SEEDS]) for mm in ("precision", "recall", "f1")}
                             for c in DK.CLASSES},
               "confusion_sum_over_seeds": np.sum([POOLED[sd][s]["confusion"] for sd in SEEDS], axis=0).tolist()} for s in settings}
BOOT = {"gt": CV.cluster_bootstrap(y, [OOF[sd]["gt"].argmax(1) for sd in SEEDS], groups)}
if DET_OK:
    BOOT["det_matched"] = CV.cluster_bootstrap(y, [np.nan_to_num(OOF[sd]["det"], nan=0).argmax(1) for sd in SEEDS], groups, valid=m)
PER_FOLD = {}
for k in FOLDS:
    sub = np.flatnonzero(FOLD_OF_FINDING == k)
    rep = CV.pooled_reports(y[sub], {sd: {kk: OOF[sd][kk][sub] for kk in ("gt", "det")} for sd in SEEDS}, m[sub], SEEDS)
    PER_FOLD[k] = {"radiographs": int(len(set(groups[sub]))), "findings": int(len(sub)), "detector_matched": int(m[sub].sum()),
                   **{s: {"macro_f1": CV.mean_sd([rep[sd][s]["macro_f1"] for sd in SEEDS]),
                          "per_class": {c: {mm: CV.mean_sd([rep[sd][s]["per_class"][c][mm] for sd in SEEDS]) for mm in ("precision", "recall", "f1")}
                                        for c in DK.CLASSES},
                          "confusion_sum_over_seeds": np.sum([rep[sd][s]["confusion"] for sd in SEEDS], axis=0).tolist()} for s in settings}}
FOLD_LEVEL = {s: CV.mean_sd([PER_FOLD[k][s]["macro_f1"]["mean"] for k in FOLDS]) for s in settings}
old_val = np.array([r["split"] == "validation" for r in PRIMARY_ROWS])
UNSEEN = CV.pooled_reports(y[old_val], {sd: {kk: OOF[sd][kk][old_val] for kk in ("gt", "det")} for sd in SEEDS}, m[old_val], SEEDS)
DET_UNSEEN = {"population": "65 old-validation radiographs (not in the detector's training assignment)", "findings": int(old_val.sum()),
              "macro_f1_det_matched": CV.mean_sd([UNSEEN[sd]["det_matched"]["macro_f1"] for sd in SEEDS]) if DET_OK else None,
              "macro_f1_gt": CV.mean_sd([UNSEEN[sd]["gt"]["macro_f1"] for sd in SEEDS])}
ys = Y_ALL[S_IDX]
SECONDARY = {"population": "DENTEX official-validation findings (never trained on)", "findings": int(ns),
             "gt_macro_f1": CV.mean_sd([DK.report(ys, OOF_S[sd]["gt"].argmax(1))["macro_f1"] for sd in SEEDS])}
CARIES = CV.caries_confusion(PRIMARY_ROWS, OOF, m, SEEDS)

for s in settings:
    log(f"pooled out-of-fold macro-F1 ({s}): {SUMMARY[s]['macro_f1']['mean']:.4f} +- {SUMMARY[s]['macro_f1']['sd']:.4f} over seeds; "
        f"radiograph bootstrap 95% CI {BOOT[s]['ci95'][0]:.4f}-{BOOT[s]['ci95'][1]:.4f}; fold-level mean {FOLD_LEVEL[s]['mean']:.4f} "
        f"+- {FOLD_LEVEL[s]['sd']:.4f}")
log("Caries/Deep Caries findings confused by all seeds (GT boxes):", CARIES["confused_by_all_seeds_gt"], "of", CARIES["n"])

RESULTS = {"protocol": "reports/cv5_protocol.md", "smoke": SMOKE, "seeds": SEEDS, "folds": FOLDS, "environment": env,
           "gates": {"1_folds": True, "2_plans": True, "3_detector": {k: v for k, v in GATE3.items()}, "4_runs_complete": True,
                     "5_one_prediction_per_finding": True},
           "population": {"primary_findings": int(n), "primary_radiographs": int(len(set(groups))), "detector_matched": int(m.sum())},
           "pooled_per_seed": {str(sd): POOLED[sd] for sd in SEEDS}, "summary": SUMMARY, "bootstrap": BOOT,
           "per_fold": {str(k): v for k, v in PER_FOLD.items()}, "fold_level_macro_f1": FOLD_LEVEL,
           "detector_unseen_subset": DET_UNSEEN, "secondary_official_val": SECONDARY,
           "caries_confusion": {k: v for k, v in CARIES.items() if k != "records"}}
(ART / "cv5_results.json").write_text(json.dumps(RESULTS, indent=1, default=float))
import csv
with open(ART / "caries_confusion_findings.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(CARIES["records"][0]))
    w.writeheader()
    w.writerows(CARIES["records"])
with open(ART / "oof_predictions.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["sample_id", "radiograph_group", "fold", "true_class", "detector_matched"] +
               [f"s{sd}_{s}_{c}" for sd in SEEDS for s in ("gt", "det") for c in DK.CLASSES])
    for i, r in enumerate(PRIMARY_ROWS):
        w.writerow([r["sample_id"], r["radiograph_group"], int(FOLD_OF_FINDING[i]), r["target_class"], bool(m[i])] +
                   [("" if np.isnan(v) else round(float(v), 6)) for sd in SEEDS for s in ("gt", "det") for v in OOF[sd][s][i]])"""),
         ("code", """# ---- 9. package artifacts ---------------------------------------------------------------------------------------------------
pkg = ART / "package"
if pkg.exists():
    shutil.rmtree(pkg)
(pkg / "runs").mkdir(parents=True)
ck = {}
for d in sorted(RUNS.iterdir()):
    for f in ("result.json", "cv_run.json"):
        if (d / f).is_file():
            shutil.copy2(d / f, pkg / "runs" / f"{d.name}__{f}")
    if (d / "heldout_pred.npz").is_file():
        shutil.copy2(d / "heldout_pred.npz", pkg / "runs" / f"{d.name}__heldout_pred.npz")
    if (d / "best.pth").is_file():
        ck[d.name] = {"sha256": CV.sha256_file(d / "best.pth"), "bytes": (d / "best.pth").stat().st_size,
                      "kept_at": f"notebook output cv5/runs/{d.name}/best.pth"}
(pkg / "checkpoint_manifest.json").write_text(json.dumps(ck, indent=1))
for f in ("cv5_results.json", "oof_predictions.csv", "caries_confusion_findings.csv", "fold_plan.json", "detector_boxes_pool.json",
          "training_log.txt", "environment.json"):
    if (ART / f).is_file():
        shutil.copy2(ART / f, pkg / f)
for rel in ("data/splits/cv5_folds_v1.csv", "kaggle/cv5_lib.py", "scripts/dataset/make_cv_folds.py"):
    (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CODE / rel, pkg / rel)
(pkg / "experiment_configs.json").write_text(json.dumps({CV.run_name(k): dataclasses.asdict(CV.fold_config(k)) for k in FOLDS}, indent=1))
(pkg / "README.md").write_text("\\n".join([
    "# DentaMind CV5-BASE artifacts" + (" (SMOKE - pipeline check, NOT a result)" if SMOKE else ""), "",
    f"Protocol reports/cv5_protocol.md. Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} on {env.get('gpu')} "
    f"(torch {env['torch']}), runtime {(time.time() - T0) / 3600:.2f} h. Seeds {SEEDS}, folds {FOLDS}.", "",
    "No test or calibration image was read. No model was promoted. Checkpoints stay in the notebook output (hashes in",
    "checkpoint_manifest.json); per-run held-out predictions are in runs/*__heldout_pred.npz.", "",
    "Main numbers: cv5_results.json (summary, bootstrap, per_fold, detector_unseen_subset, secondary_official_val, caries_confusion)."]))
sums = [f"{CV.sha256_file(p)}  {p.relative_to(pkg).as_posix()}" for p in sorted(pkg.rglob("*")) if p.is_file()]
(pkg / "SHA256SUMS.txt").write_text("\\n".join(sums) + "\\n")
zp = WORK / ("dentamind_5fold_cv_artifacts_SMOKE.zip" if SMOKE else "dentamind_5fold_cv_artifacts.zip")
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(pkg.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(pkg).as_posix())
log(f"ARCHIVE {zp}  {zp.stat().st_size / 2**20:.1f} MB  sha256 {CV.sha256_file(zp)}")""")]


# ------------------------------------------------------------------------------------------------------------------------------
# Candidate notebooks (reports/cv5_acceptance_protocol.md, revision 3). The BASE notebook above is unchanged. A candidate notebook
# uses the same frame (cells 1-8: configuration, GPU, bundle, folds, images, crops, detector) and replaces the training cell: every
# run is trained by cv5_accept.run_isolated (section-9 retry rules; exception origin recorded per attempt) and its worker writes the
# run's training manifest right after the trainer saves and hashes best.pth. All 25 runs are classified into run_status.json and
# packaged as run evidence before any aggregation; aggregation runs only when all 25 runs are valid and complete.
CANDIDATE_EMBED = {**EMBED, "kaggle/cv5_accept.py": HERE / "cv5_accept.py", "kaggle/cv5_interventions.py": HERE / "cv5_interventions.py"}
ACCEPT_PROTOCOL = "reports/cv5_acceptance_protocol.md"


def _sub(src: str, old: str, new: str) -> str:
    if src.count(old) != 1:
        raise ValueError(f"expected exactly one occurrence of {old[:60]!r}")
    return src.replace(old, new)


def _check_candidate(candidate_id: str, cfg: dict) -> None:
    import re
    sys.path.insert(0, str(ROOT / "scripts" / "dataset"))
    import dentamind_kaggle as DK
    if not re.fullmatch(r"[A-Za-z0-9]+", candidate_id) or candidate_id.upper() == "BASE":
        raise ValueError("candidate id: letters and digits only, and not BASE")
    import cv5_interventions as CI
    fields = {f.name for f in __import__("dataclasses").fields(DK.ExpConfig)}
    if set(cfg) != fields:
        raise ValueError(f"candidate config must give every ExpConfig field exactly: missing {sorted(fields - set(cfg))}, "
                         f"unknown {sorted(set(cfg) - fields)}")
    CI.check_single_intervention(DK.ExpConfig(**cfg))          # V3: exactly one intervention key, nothing else


def candidate_cells(candidate_id: str, cfg: dict) -> list:
    """Cells of the CV5 notebook for one registered candidate (cfg: complete DK.ExpConfig field dict)."""
    _check_candidate(candidate_id, cfg)
    files = {k: p.read_bytes().decode("utf-8") for k, p in CANDIDATE_EMBED.items()}
    shas = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in files.items()}
    head = ("markdown", f"""# DentaMind AI - CV5 candidate `{candidate_id}` vs the BASE reference (Kaggle GPU)

Approved protocol: `{ACCEPT_PROTOCOL}` (revision 3). Same frame as CV5-BASE: approved fold file `data/splits/cv5_folds_v1.csv`,
5 folds x seeds 42-46 = 25 runs, epoch selection on the inner validation subset only. **No test or calibration image is read.**

Every run trains in an isolated process. Infrastructure failures (CUDA runtime / out of memory / timeout / lost process) are retried
up to 3 attempts in total; a computation exception, a non-finite loss or a failed training-manifest write is final and is never
retried. Each run writes its own training manifest right after saving its checkpoint. `run_status.json` classifies all 25 runs and is
packaged before any aggregation. This notebook computes no acceptance verdict.""")
    embed = ("code", f"""# ---- 2b. files not in the bundle (embedded, hash-checked) + candidate definition -------------------------------------------
EMBEDDED = {json.dumps(files)}
EMBEDDED_SHA256 = {json.dumps(shas)}
for rel, txt in EMBEDDED.items():
    assert hashlib.sha256(txt.encode("utf-8")).hexdigest() == EMBEDDED_SHA256[rel], f"embedded file changed: {{rel}}"
    (CODE / rel).parent.mkdir(parents=True, exist_ok=True)
    (CODE / rel).write_text(txt, encoding="utf-8", newline="")
    log("embedded", rel, EMBEDDED_SHA256[rel][:16])
import cv5_lib as CV
import cv5_accept as CA
assert CV.sha256_file(CODE / "data/splits/cv5_folds_v1.csv") == CV.FOLD_FILE_SHA256
assert not os.environ.get(CA.PREFLIGHT_TRAINER_ENV), "the pre-flight trainer switch is set: a candidate notebook never uses it"
import cv5_interventions as CI
CANDIDATE_ID = {candidate_id!r}
CANDIDATE = {cfg!r}

def RUN_NAME(k):
    return f"CV5_{{CANDIDATE_ID}}_f{{k}}"

def CAND_CFG(k):
    return dataclasses.replace(DK.ExpConfig(**CANDIDATE), name=RUN_NAME(k))

V3 = CI.check_single_intervention(DK.ExpConfig(**CANDIDATE))
log("V3 config diff vs BASE:", V3, "- trainer", CA.trainer_for(CAND_CFG(0)))
EXPECTED_RUNS = [(k, sd, f"{{RUN_NAME(k)}}_s{{sd}}") for k in FOLDS for sd in SEEDS]
assert SMOKE or len(EXPECTED_RUNS) == 25, "all 25 runs are required"
log("candidate", CANDIDATE_ID, "runs expected:", len(EXPECTED_RUNS))""")
    train = ("code", """# ---- 7. train the candidate: 5 folds x seeds, section-9 retry rules, per-run training manifest ------------------------------
import torch, torchvision as tv
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
FAILED = []

def budget_left():
    return TIME_BUDGET_H * 3600 - (time.time() - T0)

def predict_heldout(ck, rows):
    if not rows:
        return np.zeros(0, int), np.zeros((0, len(DK.CLASSES))), np.zeros((0, len(DK.CLASSES)))
    m = CI.new_model(torch, tv, CANDIDATE["extra"], pretrained=False)
    m.load_state_dict(torch.load(ck, map_location="cpu", weights_only=True), strict=True)
    m.to(dev)
    ii = np.array([IDX[r["sample_id"]] for r in rows])
    pg = DK.predict(torch, m, X_ALL[ii], dev)
    pd = np.full_like(pg, np.nan)
    has = MATCHED[ii]
    if has.any():
        pd[has] = DK.predict(torch, m, XD[XD_OF[ii[has]]], dev)
    del m
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return ii, pg, pd

TAG = CI.crop_tag(CANDIDATE["extra"])
for k in FOLDS:
    plan = PLANS[k]
    take = lambda rows: {"X": X_ALL[[IDX[r["sample_id"]] for r in rows]], "y": Y_ALL[[IDX[r["sample_id"]] for r in rows]]}
    fit_npz = DK.save_arrays(CACHE / f"f{k}_fit_{TAG}.npz", take(plan["fit"]))
    inner_npz = DK.save_arrays(CACHE / f"f{k}_inner_{TAG}.npz", take(plan["inner"]))
    rows_json = CA.write_rows(CACHE / f"f{k}_rows.json", plan["fit"], plan["inner"])
    cfg = CAND_CFG(k)
    for sd in SEEDS:
        name = f"{cfg.name}_s{sd}"
        out = RUNS / name
        if (out / "heldout_pred.npz").is_file():
            log(f"{name}: already predicted - skipped")
            continue
        if budget_left() < 900:
            log("TIME BUDGET reached: no new run started. Save the output, then rerun with RESUME_FROM set.")
            break
        r = CA.run_isolated(cfg, sd, k, fit_npz, inner_npz, rows_json, RUNS, log=log)
        if r["status"] != "completed":
            FAILED.append(name)
            log(f"{name}: {r['status']} {r.get('class', '')} - {r.get('reason', '')}")
            continue
        st = CA.run_status(RUNS, name, k, sd)
        if not (st["class"] == "incomplete" and st.get("reason") == "held-out prediction missing"):
            FAILED.append(name)                 # divergence (collapse / non-finite loss) or manifest not verified: no prediction
            log(f"{name}: {st['class']} - manifest problems {st['manifest']['problems']}, collapse share {st['collapse_share']:.4f}")
            continue
        try:
            ii, pg, pd = predict_heldout(out / "best.pth", plan["heldout"])
            ii2, pg2, pd2 = predict_heldout(out / "best.pth", plan["heldout_secondary"])
        except Exception as e:
            FAILED.append(name)
            log(f"{name}: held-out prediction failed:", CA.record_prediction_failure(out, e))
            continue
        np.savez(out / "heldout_pred.npz", idx=ii, gt=pg, det=pd, idx_sec=ii2, gt_sec=pg2, det_sec=pd2)
        res = json.loads((out / "result.json").read_text(encoding="utf-8"))
        done = [a for a in r["attempts"] if a["status"] == "completed"][-1]
        (out / "cv_run.json").write_text(json.dumps({"fold": k, "seed": sd, "run": name, "candidate": CANDIDATE_ID,
            "fit_findings": len(plan["fit"]), "inner_findings": len(plan["inner"]), "heldout_findings": len(plan["heldout"]),
            "heldout_secondary_findings": len(plan["heldout_secondary"]), "best_epoch": res["best_epoch"],
            "inner_val_macro_f1": res["val_gt"]["macro_f1"], "checkpoint_sha256": res["checkpoint_sha256"],
            "training_manifest": done["manifest"], "attempts": len(r["attempts"]),
            "exception_origins": [a.get("origin") for a in r["attempts"] if a["status"] != "completed"],
            "note": "result.json split_note is the generic BASE text; for CV the validation set is the fold's inner validation subset"}, indent=1))
        log(f"{name}: best ep {res['best_epoch']} inner-val macro-F1 {res['val_gt']['macro_f1']:.4f}  "
            f"elapsed {(time.time() - T0) / 3600:.2f} h")
RUN_STATUS = CA.collect_status(RUNS, EXPECTED_RUNS)
(ART / "run_status.json").write_text(json.dumps(RUN_STATUS, indent=1, default=str))
log("run classes:", dict(collections.Counter(RUN_STATUS["run_classes"].values())), "- all 25 valid and complete:", RUN_STATUS["all_ok"])
log("failed runs:", FAILED or "none")""")
    evidence = ("code", """# ---- 7b. run evidence (always packaged, also when runs failed): status, attempts, failures, manifests ------------------------
ev = ART / "run_evidence"
if ev.exists():
    shutil.rmtree(ev)
(ev / "runs").mkdir(parents=True)
EVIDENCE_FILES = ("result.json", "cv_run.json", "best.json", CA.MANIFEST_NAME, CA.ATTEMPTS_FILE, CA.FAILURE_FILE, CA.PREDICTION_FAILURES_FILE)
for _, _, name in EXPECTED_RUNS:
    d = RUNS / name
    for f in EVIDENCE_FILES + tuple(p.name for p in sorted(d.glob("attempt_*.json"))) if d.is_dir() else ():
        if (d / f).is_file():
            shutil.copy2(d / f, ev / "runs" / f"{name}__{f}")
for f in ("run_status.json", "training_log.txt"):
    if (ART / f).is_file():
        shutil.copy2(ART / f, ev / f)
sums = [f"{CV.sha256_file(p)}  {p.relative_to(ev).as_posix()}" for p in sorted(ev.rglob("*")) if p.is_file()]
(ev / "SHA256SUMS.txt").write_text("\\n".join(sums) + "\\n")
EVZ = WORK / f"dentamind_cv5_{CANDIDATE_ID}_run_evidence{'_SMOKE' if SMOKE else ''}.zip"
with zipfile.ZipFile(EVZ, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ev.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(ev).as_posix())
log(f"RUN EVIDENCE {EVZ}  sha256 {CV.sha256_file(EVZ)}")""")
    agg = CELLS[10][1]
    agg = _sub(agg, 'f = RUNS / f"{CV.run_name(k)}_s{sd}" / "heldout_pred.npz"', 'f = RUNS / f"{RUN_NAME(k)}_s{sd}" / "heldout_pred.npz"')
    agg = _sub(agg, 'assert not FAILED and not missing_runs, f"gate 4: runs missing {FAILED + missing_runs} - resume with RESUME_FROM; nothing is reported"',
               'assert RUN_STATUS["all_ok"] and not FAILED and not missing_runs, (f"gate 4: not all {len(EXPECTED_RUNS)} runs are valid and "\n'
               '    f"complete (run_status.json): {FAILED + missing_runs} - no candidate number is reported")')
    agg = _sub(agg, '"protocol": "reports/cv5_protocol.md"', f'"protocol": "{ACCEPT_PROTOCOL}", "candidate": CANDIDATE_ID')
    pkg = CELLS[11][1]
    pkg = _sub(pkg, 'for f in ("result.json", "cv_run.json"):', 'for f in EVIDENCE_FILES + tuple(p.name for p in sorted(d.glob("attempt_*.json"))):')
    pkg = _sub(pkg, '"training_log.txt", "environment.json"):', '"training_log.txt", "environment.json", "run_status.json"):')
    pkg = _sub(pkg, 'for rel in ("data/splits/cv5_folds_v1.csv", "kaggle/cv5_lib.py", "scripts/dataset/make_cv_folds.py"):',
               'for rel in ("data/splits/cv5_folds_v1.csv", "kaggle/cv5_lib.py", "kaggle/cv5_accept.py", "kaggle/cv5_interventions.py", '
               '"scripts/dataset/make_cv_folds.py"):')
    pkg = _sub(pkg, '{CV.run_name(k): dataclasses.asdict(CV.fold_config(k)) for k in FOLDS}', '{RUN_NAME(k): dataclasses.asdict(CAND_CFG(k)) for k in FOLDS}')
    pkg = _sub(pkg, '"# DentaMind CV5-BASE artifacts"', 'f"# DentaMind CV5 candidate {CANDIDATE_ID} artifacts"')
    pkg = _sub(pkg, 'f"Protocol reports/cv5_protocol.md. Generated', f'f"Protocol {ACCEPT_PROTOCOL}. Generated')
    pkg = _sub(pkg, '("dentamind_5fold_cv_artifacts_SMOKE.zip" if SMOKE else "dentamind_5fold_cv_artifacts.zip")',
               '(f"dentamind_cv5_{CANDIDATE_ID}_artifacts_SMOKE.zip" if SMOKE else f"dentamind_cv5_{CANDIDATE_ID}_artifacts.zip")')
    crops = ("code", _sub(CELLS[7][1], 'X_ALL, Y_ALL, _ = DK.build_crops(POOL, DATA_ROOT, CACHE / "pool_gt.npz")',
                          'X_ALL, Y_ALL, _ = CI.build_crops(POOL, DATA_ROOT, CACHE / f"pool_gt_{CI.crop_tag(CANDIDATE[\'extra\'])}.npz", '
                          'CANDIDATE["extra"])\nlog("crop rule:", CI.resolve(CANDIDATE["extra"]), "crops", X_ALL.shape)'))
    det = ("code", _sub(CELLS[8][1], 'XD, MI, MISSED = DK.build_detector_crops(POOL, DATA_ROOT, DET_CACHE, lambda r: r["project_image_id"])',
                        'XD, MI, MISSED = CI.build_detector_crops(POOL, DATA_ROOT, DET_CACHE, lambda r: r["project_image_id"], CANDIDATE["extra"])'))
    return [head, CELLS[1], CELLS[2], CELLS[3], embed, CELLS[5], CELLS[6], crops, det, train, evidence, ("code", agg), ("code", pkg)]


def _notebook(cells: list) -> dict:
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}, "kaggle": {"accelerator": "gpu", "isInternetEnabled": True}},
          "cells": []}
    for i, (kind, src) in enumerate(cells):
        cell = {"cell_type": kind, "id": f"cell-{i:02d}", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    return nb


def write_candidate_notebook(candidate_id: str, cfg: dict, registration, out) -> Path:
    """Writes a candidate notebook only for a candidate named in an existing dated registration amendment (protocol section 4.5)."""
    reg = Path(registration)
    if not reg.is_file() or candidate_id not in reg.read_text(encoding="utf-8"):
        raise ValueError(f"no registration amendment naming candidate {candidate_id!r}: {reg}")
    out = Path(out)
    out.write_text(json.dumps(_notebook(candidate_cells(candidate_id, cfg)), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main():
    nb = _notebook(CELLS)
    out = HERE / "dentamind_5fold_cv.ipynb"
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(CELLS)} cells); embedded: " + ", ".join(f"{k} {v[:12]}" for k, v in SHAS.items()))


if __name__ == "__main__":
    main()
