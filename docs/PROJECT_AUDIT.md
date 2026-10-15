# Project audit (Phase 1) and what was changed

Audit date 2026-10-14. Frameworks actually in use: Python 3.13, FastAPI 0.143 / uvicorn 0.54 / pydantic 2.14, PyTorch 2.6.0+cu124 /
torchvision 0.21, NumPy 2.5, Pillow 12.3, SQLite (stdlib); frontend React 18.3, Vite 5.4, Tailwind 3.4, Recharts 2.12, React Router 6.26.
No ESLint/Prettier configuration exists in the project, so "frontend linting" = the Vite production build (which parses every file) plus the
browser runs below; no separate linter was run. Detectron2 is not used.

## Architecture map

| Layer | Where | Notes |
|---|---|---|
| Core library | `src/dentexmodel/` | data discovery/manifest/splits, training (torchvision), inference wrappers, uncertainty maths, reporting (template + i18n), annotation/review store |
| API | `backend/` (`api/*.py` routers, `services/*.py` logic, `schemas/`) | FastAPI, SQLite metadata in `runtime/dentamind.sqlite3`; background work in threads (training jobs, pool scoring, evaluations) |
| Frontend | `frontend/src/` (`pages/`, `components/`, `lib/`, `services/api.js`) | 12 pages; Vite dev server proxies `/api` |
| Models | `Data/checkpoints/*.pth` + `.json` sidecar | detection, segmentation, numbering (FDI), classification; see `docs/MODEL_TRAINING.md` |
| Scripts | `scripts/` | audit, leakage, train, evaluate, predict, uncertainty evaluation, AL experiment, benchmark |
| Tests | `tests/` | unittest, 160+ tests (see `docs/QUALITY_AUDIT.md` for the latest run) |

Model loading/inference paths: `inference/registry.py` (checkpoint scan + sidecar validation + active selection) -> `inference/torch_models.py`
(`detect_teeth`, `segment_teeth`, `number_teeth`, `classify_regions`, `explain_region`) -> `backend/services/analysis.py` (single-model calls) and
`backend/services/pipeline.py` (the full pipeline added in this phase).

## Page-by-page status before this phase (traced button -> handler -> endpoint)

| Page / control | Handler -> endpoint | Status before | Root cause / gap |
|---|---|---|---|
| Home | `/api/overview`, audit | functional | counted entries and distinct films without explaining them (Issue D) |
| Analysis: Detection / Segmentation / Report | `/api/predict`, `/api/segment`, `/api/reports/generate` | functional, but each model was a separate call, joined **by list order** | Issue C: classification, numbering and masks were paired with detections by index |
| Analysis: Calculate Uncertainty | `/api/uncertainty/score` with probabilities of the *selected* region only | **placeholder in effect** | with no region selected nothing was computable; the backend stores a record only when a combined score exists, so nothing was ever saved -> empty Uncertainty page (Issue A) |
| Analysis: Explain | `/api/explain` (Grad-CAM) | functional | grayscale, fixed opacity, not stored |
| Uncertainty | `/api/uncertainty/table` | empty | read only saved records (none existed) |
| Active Learning | `/api/active-learning/*` | selection engine functional | no uncertainty signals existed to rank by; "combined" silently fell back |
| Annotations | `/api/annotations/*` | partial | only Label Studio import/approve/export; no in-app review, no audit trail |
| Reports | `/api/reports/*` | functional | listed *every* tooth as a finding with a forced class (Issue B); validator rejected its own text for >= 11 regions (fixed earlier) |
| Training / Experiments / Registry | `/api/training/*`, `/api/experiments`, `/api/models` | functional | experiments only recorded training runs; registry lacked evaluation links (fixed earlier) |

## Root causes of the issues you listed, and the fixes

- **A - empty Uncertainty page.** Button sent the wrong thing and nothing was persisted. Fix: `POST /api/uncertainty/image` and
  `POST /api/analyze/full` run the real pipeline (detector, numbering, segmenter, classifier + horizontal-flip passes), compute entropy,
  flip-TTA disagreement, mask instability and detection instability from the actual outputs, store the record (image id, model versions,
  timestamp, method text, thresholds) and the page reads it. Unavailable signals show their reason.
- **B - misleading classification.** The classifier has no healthy class. Fix (also earlier): closest-class wording everywhere; new in this
  phase: regions whose normalised entropy is above the calibration-split threshold are **abstained** (no class named, manual review); a class score
  is never called a probability of disease; reports list abstained regions separately.
- **C - association by position.** Fix: one backend result with a `regions` array; each region has a content-derived id, and the mask, tooth number and class
  probabilities are attached to it by documented spatial matching (one-to-one greedy IoU >= 0.5), with `needs_review`/`unassigned` states and flags for
  unmatched items. The UI table, overlay, inspector, reviews and reports all use those ids.
- **D - dataset figures.** Re-verified (`scripts/audit_dataset.py`, `scripts/check_leakage.py`): definitions are now on the Home page; duplicates (pixel-identical) share a split;
  near-duplicates were checked by perceptual hash + pixel correlation (0 confirmed across splits).
- **E - drafts not diagnoses.** Kept and strengthened: reports carry counts, model versions, flags, limitations, provisional-threshold notice, and the
  research-draft banner in all languages; `reviewed` status needs a named reviewer *and* a passing validation.

## Features now functional vs still limited

Functional and verified (real checkpoints, real HTTP, real browser): upload, preprocessing metadata, detection, FDI numbering, segmentation, classification
candidate/abstain, uncertainty (4 signals + combined), Grad-CAM, region review with audit history and second-person approval, pool scoring, uncertainty-guided selection,
random-vs-entropy-vs-combined experiment, English/Hindi/Marathi reports with HTML/TXT/JSON export, experiments and registry pages.

Still limited: see `docs/KNOWN_LIMITATIONS.md` (no healthy class, provisional thresholds, no ensemble, self-declared reviewer identity, no authentication,
Label Studio/LLM/TensorBoard unverified).
