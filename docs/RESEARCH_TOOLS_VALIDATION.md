# Research tools and active learning - validation report

Audit date 2026-10-14. Scope: uncertainty estimation, active-learning selection, annotation integration (Label Studio), training management, experiment tracking, TensorBoard.
Everything below was run on this machine (Windows 11, Python 3.13, torch 2.6.0+cu124, RTX 3050 Laptop 4 GB). Raw evidence is in `docs/audit_evidence/`.
Nothing was simulated except where a row says "synthetic fixture" (unit tests only).

## 1. Uncertainty estimation

### Exact formulas (from `docs/UNCERTAINTY_AND_ACTIVE_LEARNING.md`, `src/dentexmodel/uncertainty/`, `backend/services/pipeline.py`)

| Signal | Definition | Needs | Range |
|---|---|---|---|
| entropy | Shannon entropy of the classifier softmax over the 4 trained classes, divided by log 4 | classifier | 0 (certain) .. 1 (uniform) |
| flip disagreement | Jensen-Shannon divergence between the classifier on a crop and on its horizontally flipped crop, divided by log 2 | classifier | 0..1 |
| mask instability | 1 - IoU between each mask and the mask predicted on the flipped image (flipped back) | segmenter | 0..1 |
| detection instability | 1 - IoU of each box against its best match on the flipped image (shown, not in the combined score) | detector | 0..1 |
| combined | weighted mean of the **available** signals among entropy 0.4, flip disagreement 0.4, mask instability 0.2; weights renormalised | any | 0..1 |

A signal that cannot be computed is `unavailable` with a reason and is never counted as 0. Image-level values are means over regions.

### What was verified in this audit

| ID | Test | Result |
|---|---|---|
| UNC-003 | uniform 4-class softmax (0.25 each) -> entropy | **1.0** exactly - PASS |
| UNC-004 | one-hot softmax -> entropy | **0.0** - PASS |
| UNC-005..007 | empty / non-numeric / missing probabilities | 4xx or `unavailable`, never a fake 0 - PASS |
| UNC-001/002 | `POST /api/uncertainty/image` on a real upload | every signal has `value`+`status`+`reason`; all computed values finite and in [0,1] - PASS |
| UNC-008 | `GET /api/uncertainty/table` after the call | the new record is listed with its values - PASS |
| UI-E-005 | browser: "Calculate Uncertainty" | real POST; the combined score shown equals the response - PASS |
| unit | `tests/test_uncertainty_eval.py`, `test_review_pipeline.py` | missing signals never become zero; combined renormalises - PASS |

### Is the measure validated against real errors? (stored evaluation, `Data/reports/uncertainty_evaluation.md`, not re-run here)

Classifier on ground-truth tooth crops, thresholds chosen on the calibration split, evaluated once on the held-out test split (354 crops):
AUROC for detecting the classifier's mistakes - entropy **0.768**, flip disagreement **0.745**; ECE **0.048** (temperature scaling to 0.036 computed but **not applied**).
Error rate among entropy-flagged crops 34.4 % vs 6.2 % among unflagged; the flag marks 54 % of crops.

**Therefore:** the score is a *ranking signal* with moderate evidence of usefulness for the classifier only. It is **not a calibrated probability of error**, the thresholds
(entropy 0.397, flip 0.076) are provisional (one split, one seed), and mask/detection instability have **no** validation against segmentation or detection errors (status PARTIAL).
True ensemble disagreement does not exist (only one checkpoint per task) and is reported as unavailable (status NOT IMPLEMENTED).

## 2. Active-learning selection (live API, `scripts` log: `docs/audit_evidence/al_selection_runs.json`)

| Step of the required workflow | Evidence | Result |
|---|---|---|
| 1. load eligible unlabelled examples | `GET /api/active-learning/pool`: 1,558 eligible; 206 test-split and 40 duplicates-of-labelled images excluded; 30 already scored | PASS |
| 2. exclude unavailable/invalid images | pool is built from the manifest (`file_exists`, `duplicate_of` filters) | PASS |
| 3. compute the acquisition score | entropy rounds list `entropy=0.644 (rank 1/30)`; combined rounds list `U=0.290 from entropy=.., disagreement=.., mask_instability=..` | PASS |
| 4. deterministic with a seed | random seed 7 twice -> identical 10 ids; seed 8 -> different ids; entropy twice -> identical ids | PASS |
| 5. apply the budget | budget 10 -> exactly 10 selected, batches of 5 | PASS |
| 6. save ids and reasons | each stored round has `selected_ids` and per-item `reason`, `score`, `signals`, quality flags | PASS |
| 7. avoid re-selecting annotated items | `exclude_ids` = approved/labelled ids; unit-tested | PASS (unit) |
| 8. record model and dataset versions | dataset fingerprint recorded; **model version was null** in rounds made before this audit's fix (random draws legitimately have none) - now the model that produced the signals is stored | defect fixed |
| 9. import reviewed annotations | file import path unit-tested with a synthetic Label Studio fixture; live import BLOCKED (section 4) | PARTIAL |
| 10. verify annotations before they become eligible for retraining | only **approved** reviews on pool/upload images are exportable; test/val/calibration/labelled images are flagged `usable_for_training = 0` (browser workflow: self-approval refused, second approver accepted) | PASS |
| Test split never used | none of the selected ids is in the test split; `LeakageError` is raised if a test id is passed (`select_candidates`) | PASS |
| Signals unavailable | a candidate with no entropy is skipped with reason `entropy unavailable`, not scored 0 | PASS |

Only 30 of 1,558 pool images had real uncertainty records when the audit ran, so the entropy/combined strategies ranked **30** candidates (the response says `rank 1/30`).
Use "Score pool images" (a real GPU job over unscored pool images) before drawing conclusions from a selection.

## 3. Random vs entropy experiment - reproduction

### Original experiment (`Data/reports/active_learning_experiment.md`, GPU, 3 seeds, budgets 60-300, finding classification, ResNet-18, 160 px, 8 epochs)

Macro-F1 at 300 labelled radiographs: random 0.706, entropy 0.706, combined 0.720; paired differences to random averaged -0.005 (entropy) and -0.011 (combined) - **no consistent benefit**.

### Reproduction attempted here (reduced, CPU, `docs/audit_evidence/al_reproduction_cpu_seed0.json`)

Same code and hyper-parameters, same pool (476 radiographs), same validation split (65 radiographs / 331 crops), **seed 0, budgets 60 and 120, random vs entropy only**.
Run on the CPU because the 4 GB GPU was occupied by the API; written to a scratch folder with `--no-db` so no historical result was touched
(the script gained `--out-dir`, `--device`, `--no-db` and now stores per-round selection manifests for this purpose).

| | original (GPU) | reproduction (CPU) |
|---|---:|---:|
| round 0, 60 radiographs: macro-F1 / accuracy (identical for both strategies by design) | 0.4814 / 0.7402 | 0.5016 / 0.7402 |
| 120 radiographs, random | 0.6388 / 0.7674 | **0.6771** / 0.7976 |
| 120 radiographs, entropy | 0.6438 / 0.7825 | **0.5880** / 0.7402 |

Checks that hold: same pool size, same validation crops (331), **identical initial labelled set for both strategies** (same `labeled_sha`), accuracy of round 0 identical (0.7402),
the two strategies picked different radiographs afterwards (only 5 of 60 in common). Checks that do **not** hold: the numbers are not bit-identical - macro-F1 differs by 0.02-0.09.

**Interpretation (stated plainly):** for the same seed, a CPU run and a GPU run of the *same* training give macro-F1 values up to 0.09 apart (entropy@120: 0.644 vs 0.588), which is larger than the
strategy differences reported in the original study (|mean difference| <= 0.011). The CPU reproduction even reverses the ordering at this single cell (entropy worse than random).
So the honest conclusions are: (a) the original finding "entropy selection did not beat random" is **reproduced in direction on the CPU** and **not contradicted**;
(b) neither run provides evidence that uncertainty-guided selection helps; (c) differences between strategies in this setup are below the run-to-run / device noise;
(d) the full original grid (3 seeds x 5 budgets x 3 strategies, ~30 min on GPU) was **not** repeated, and the cause of the CPU/GPU gap (floating-point differences amplified by 8-epoch fine-tuning on ~250 crops) was **not isolated**.
No result was edited to make active learning look better or worse.

## 4. Annotation integration (Label Studio)

| ID | Test | Result |
|---|---|---|
| ANN-001 | `GET /api/annotations/connection` with no Label Studio running | truthful "not reachable / API key not configured" state - PASS |
| ANN-002 | `POST /api/annotations/import-from-label-studio` without server/key | clear error, nothing imported - PASS |
| ANN-003/004 | malformed tasks; approving a non-existent annotation | no 5xx, nothing approved - PASS |
| AL export | `POST /api/active-learning/export {round_id}` -> 10 Label Studio tasks with `data.image` url, `image_id`, width, height, score and reason; unknown round -> 404; `push_to_label_studio` without a key -> 502 with "download the manifest and import it manually" | PASS |
| live import/export with a real Label Studio | Label Studio is **not installed or running** here and no API key exists | **BLOCKED** (recovery: install Label Studio, set `LABEL_STUDIO_URL` / `LABEL_STUDIO_API_KEY` in `.env`) |
| category mapping, bbox/polygon conversion | `tests/test_annotation_reporting.py` with a synthetic fixture (labelled TEST DATA) | PASS (unit only) |

Retraining on approved annotations is wired behind `use_approved_annotations` and is **never automatic**; it was not executed end-to-end and its effect is unmeasured.

## 5. Training management

| Check | Evidence | Result |
|---|---|---|
| prerequisites | `GET /api/training/prerequisites` | PASS |
| configuration validation | epochs 0, learning-rate -1, unknown task, empty name, image size 8 -> HTTP 422; unknown architecture / path-like `resume_checkpoint` refused | PASS |
| unknown job status / stop | 404 `job_not_found` (was 400 before this audit) | defect fixed |
| progress and error reporting | historical jobs list real statuses and errors (e.g. a CUDA out-of-memory failure of an earlier segmentation run); errors are now served without tracebacks or absolute paths | PASS |
| recovery from failure / restart | a live CLI job is no longer marked interrupted by an API restart (pid ownership); unit-tested | PASS (unit) |
| GPU memory reporting | `/api/system/gpu` and `/api/health` report used/total MB (63 MB idle -> about 1.3 GB after the first detector+classifier request -> 1.6 GB after the full pipeline) | PASS |
| CPU fallback | a server with CUDA hidden runs real inference on the CPU (6.7-22.8 s per predict, 11-53 s per full analysis, depending on load) | PASS |
| **smoke test** (labelled as such) | `scripts/train_model.py --task classification --architecture resnet18 --device cpu --epochs 1 --max-train-images 8 --max-val-images 4 --no-pretrained` with a temporary checkpoint folder and database: exit 0 in 11 s, sidecar + `.pth` written; real checkpoints SHA-256 identical afterwards | PASS |
| API-started training, live cancel, duplicate-job refusal against the real trainer | **not executed**: it would write into the real checkpoint registry and occupy the 4 GB GPU; covered only by unit tests with a fake trainer | PARTIAL |
| evaluate endpoint | **defect:** four Evaluate clicks started four concurrent GPU evaluations that all failed (CUDA out of memory, paging file too small, array allocation) - fixed: 409 while another job runs, plus a visible confirmation in the UI | defect fixed |

## 6. TensorBoard and experiment tracking

* **TensorBoard: BLOCKED.** The `tensorboard` package is not installed (`import tensorboard` fails), `Data/runs/` contains no event files, and `/api/health` correctly reports it unreachable.
  Training code writes event files only when the package is importable. Recovery: `pip install tensorboard`, train, then `tensorboard --logdir Data/runs`.
  No chart was populated with invented numbers.
* **Experiment tracking: PASS.** `GET /api/experiments` returns 50 real rows: 45 from `scripts/run_al_experiment.py` (3 seeds x 3 strategies x 5 budgets) and 5 supervised training runs. The Experiments page renders them.
  The CPU reproduction in section 3 used `--no-db`, so it added **no** rows.
* The experiments table is written only by real training/evaluation processes (`scripts/train_model.py`, `run_al_experiment.py`); the API cannot insert metrics.

## 7. Limitations and what this audit did *not* establish

* Evaluation metrics of detection, segmentation and numbering were **not** re-run (cost, GPU occupied, locked test split); only the classification validation metrics were reproduced on the CPU
  (accuracy 0.8218 vs 0.8248 stored; macro-F1 0.7114 vs 0.7179; per-class F1 within 0.025), which shows the stored numbers are of the right size but not bit-reproducible across devices.
* The uncertainty thresholds and every active-learning conclusion come from one dataset, one validation split and three seeds.
* Active learning for detection/segmentation (retraining those detectors per round) has not been run.

## 8. Reproducibility commands

```powershell
# API-level checks of this document (API on :8000)
.\.venv\Scripts\python.exe scripts\audit_live_api.py
# selection determinism / budget / test-split exclusion
# (the six POST /api/active-learning/select calls and their saved results: docs\audit_evidence\al_selection_runs.json)
# reduced AL reproduction (CPU, scratch output, no DB rows)
.\.venv\Scripts\python.exe scripts\run_al_experiment.py --seeds 0 --strategies random entropy --rounds 1 --device cpu --no-db --out-dir <scratch-folder>
# classification validation re-evaluation without overwriting the stored report
.\.venv\Scripts\python.exe scripts\evaluate_model.py --checkpoint dentex_findings_classification_v1.pth --split val --device cpu --out-dir <scratch-folder>
# training smoke test with temporary outputs
$env:MODEL_CHECKPOINT_DIR="<scratch>\ckpt"; $env:DATABASE_URL="sqlite:///<scratch>/smoke.sqlite3"
.\.venv\Scripts\python.exe scripts\train_model.py --task classification --architecture resnet18 --name audit_smoke_cpu --epochs 1 --batch-size 4 --image-size 64 --device cpu --num-workers 0 --max-train-images 8 --max-val-images 4 --no-pretrained
# full original experiment (about 30 minutes on the GPU; stop the API first)
.\.venv\Scripts\python.exe scripts\run_al_experiment.py --seeds 0 1 2
```
