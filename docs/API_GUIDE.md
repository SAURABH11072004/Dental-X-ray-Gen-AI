# API guide

FastAPI app `backend.main:app`. Interactive docs: `http://127.0.0.1:8000/docs`; schema: `/openapi.json`.
All errors share one shape: `{"error": {"code", "message", "hint", "details"}}`. A missing model is **HTTP 503**
(`no_checkpoint` / `model_unavailable`), a missing dataset is **409**, bad input is **422**, an unknown id is **404**.
The API never returns invented predictions: with no usable checkpoint, inference routes answer 503 and say what to do.

Start it: `.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`

## Authentication, loopback restriction and rate limits

* Every `/api` route except `GET /api/health` (and `/docs`, `/openapi.json`) needs the API token: `Authorization: Bearer <token>` or `X-API-Key: <token>`. Missing or wrong token -> **401** `unauthorized`.
  The token is `DENTAMIND_API_TOKEN` if set, otherwise the random value the backend writes to `runtime/api_token.txt` on first start (git-ignored; delete the file to rotate it). `DENTAMIND_AUTH=off` disables the token check for local development.
* The Vite dev proxy adds the header on the server side (it reads the same file), so the browser UI needs no configuration and the token is never part of the frontend bundle.
* Clients that are not on the loopback interface get **403** unless `DENTAMIND_ALLOW_REMOTE=1` is set (do that only on a trusted network).
* Per-client limits per minute: uploads 60, heavy inference 120, control endpoints (training, model management, dataset processing, import/approve) 20, other writes 300, reads 1500, failed authentications 20. Exceeding one gives **429** with `Retry-After`. `DENTAMIND_RATE_LIMIT=off` is for tests only.
* `GET /api/health` returns `version` (the application version, 0.2.0) and service status without secrets.
* `POST /api/training/start` accepts `"dry_run": true` (validate everything, start nothing) and answers **409** `job_already_running` while another job runs; `max_train_images` / `max_val_images` exist for SMOKE tests only.

PowerShell example: `Invoke-RestMethod http://127.0.0.1:8000/api/models -Headers @{Authorization="Bearer $((Get-Content runtimepi_token.txt -Raw).Trim())"}`

## System and dataset

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health?probes=true` | backend, database, dataset state, GPU/torch, checkpoint count, Label Studio / TensorBoard / LLM reachability |
| GET | `/api/system/gpu`, `/api/system/settings`, `/api/overview` | device info; non-secret settings + diagnostics; counts for the home page |
| GET | `/api/dataset/status` | state `main_available` / `test_data_only` / `missing`, one entry per source folder |
| POST | `/api/dataset/process?force=` | discovery -> manifest -> validation -> splits (idempotent, cached by fingerprint) |
| GET | `/api/dataset/manifest?which=&limit=&offset=` | rows incl. `split`, `content_hash`, `duplicate_of` |
| GET | `/api/dataset/validation?which=` | validation issue counts and examples |
| GET | `/api/dataset/leakage` | result of `scripts/check_leakage.py` (split overlap, per-model training sets, near-duplicates) |
| GET | `/api/dataset/audit` | the file written by `scripts/audit_dataset.py` (404 `audit_missing` until it is run) |

## Images

| Method | Path | Notes |
|---|---|---|
| GET | `/api/images?source=all|uploads|dataset|test_data&limit=&offset=` | ids are unique across sub-sets (`q_train_673`, `qed_train_673`, ...) |
| GET | `/api/images/{id}`, `/file`, `/thumbnail?size=`, `/quality` | only ids present in the manifest or the upload table are served; ids are never used as paths |
| POST | `/api/images/upload` | multipart `file`. PNG/JPEG only: extension **and** magic bytes are checked, size limit `MAX_UPLOAD_MB` (default 25), the stored name is derived from the content hash, never from the client file name |

## Inference

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/predict` | `{image_id, with_classification}` | detector (+ finding classifier when its checkpoint exists); response includes model version, scores, numbering checks and the classifier's `limitations` |
| POST | `/api/predict/batch` | `{image_ids: [<=25]}` | per-image `ok/error`; a missing model aborts with 503 once |
| GET | `/api/analyses/{id}`, `/api/analyses/{id}/overlay?min_score=` | | stored result; PNG with the detections drawn on the original image |
| POST | `/api/analyze/full` | `{image_id, segmentation, uncertainty}` | the pipeline: preprocess -> detect -> number -> segment -> match -> classify -> uncertainty. Returns `steps` (ok/unavailable/failed + reason), `regions` (id, FDI + status, matched mask, candidate/abstained class, per-region uncertainty, flags), image-level `uncertainty` record, `summary`; saved as analysis kind `full` (+ an `uncertainty` record) |
| POST | `/api/uncertainty/image` | `{image_id}` | runs the pipeline and returns the saved uncertainty record |
| POST | `/api/segment` | `{image_id}` | 503 until a segmentation checkpoint is active |
| POST | `/api/explain` | `{image_id, box}` | Grad-CAM of the classifier for one box, computed from the real model |
| POST | `/api/uncertainty/score`, GET `/api/uncertainty/table` | | image-quality signals are always real; model signals are `unavailable` (never 0) when their inputs are missing |

## Models, training, evaluation

| Method | Path | Notes |
|---|---|---|
| GET | `/api/models` | checkpoints with sidecar metadata; inconsistent sidecars are listed as `rejected: ...` and cannot be activated |
| POST | `/api/models/select`, `/api/models/promote` | activate a checkpoint (`promote` needs `approved_by` + `confirm`) |
| GET | `/api/training/prerequisites?task=&architecture=` | why training can or cannot start |
| POST | `/api/training/start` | runs in a background thread; `epochs`, `batch_size`, `learning_rate`, `image_size`, `device`, `seed`, `pretrained`, `label_mode` |
| GET | `/api/training/status/{job}`, `/api/training/jobs` | real per-epoch metrics and log tail; POST `/api/training/stop/{job}` |
| POST | `/api/models/{model_id}/evaluate` | starts `scripts/evaluate_model.py` (validation or calibration split only) as a background job |
| GET | `/api/evaluations`, `/api/evaluations/{name}?format=json|md` | evaluation reports from `Data/reports/eval_*.json` |
| GET | `/api/experiments`, `/compare`, `/series`, `/export` | recorded runs |

A job started by a CLI process (`scripts/train_model.py`) is owned by that process; restarting the API does not interrupt it.
Jobs whose owning process is gone are marked `interrupted`.

## Region review (in-app annotation)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/reviews/queue` | images with regions awaiting review, ordered by image-level combined uncertainty |
| POST | `/api/reviews` | `{image_id, region_id|null, action, corrected_class, corrected_fdi, notes, reviewer}`; actions: confirm_candidate, correct_class, reject_candidate, set_tooth_number, mark_number_unassigned, specialist_review, unusable_image. Duplicate decisions -> 409; a changed decision becomes a new revision |
| GET | `/api/reviews`, `/api/reviews/history?image_id=&region_id=` | current reviews / full audit history |
| POST | `/api/reviews/approve`, `/reject` | `{ids, approver}`; the approver must differ from the reviewer |
| GET | `/api/reviews/export?format=json|csv` | approved reviews usable for training only (pool/upload images); test/validation/labelled images are excluded and counted |

## Active learning, annotation, reports

| Method | Path | Notes |
|---|---|---|
| POST | `/api/active-learning/score-pool?n=&seed=` + GET `/score-pool/{job}` | background job: runs the uncertainty pipeline on n unscored pool images so the strategies have real signals |
| GET | `/api/active-learning/info`, `/pool`, `/rounds`, `/rounds/{id}/tasks` | the pool excludes the locked test split and pixel-duplicates of labeled images |
| POST | `/api/active-learning/select`, `/export` | `random` / `entropy` / `disagreement` / `combined`; unavailable signals are reported, not zero-filled |
| GET/POST | `/api/annotations/...` | Label Studio config/connection, import, approve, reject; only approved records may enter training |
| POST | `/api/reports/generate`, `/{id}/validate`, `/{id}/review` | evidence-grounded draft; LLM output is validated and falls back to the template; `review` needs a reviewer name |
| GET | `/api/reports`, `/api/reports/{id}?lang=en|hi|mr` | `lang` adds a `localized` block (same ids/versions/values) and a `localization_check` |
| GET | `/api/reports/{id}/export?format=html|txt|json&lang=en|hi|mr` | UTF-8; refused with `localization_mismatch` if the translation does not match the English report; see `docs/MULTILINGUAL_REPORTS.md` |

## Security notes

- Secrets (`LABEL_STUDIO_API_KEY`, `LLM_API_KEY`) are read from the environment only and never returned.
- Paths come from the manifest / database, not from request parameters. `..`, `\` and drive-letter ids return 404.
- Uploaded files are decoded as images and never executed. The evaluation report route accepts only `eval_<name>` stems.
- The test split cannot be evaluated or trained on through the API.
