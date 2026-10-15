# Running DentaMind AI on Windows (PowerShell)

> **Verification status (2026-10-14).** Verified on this Windows 11 machine (Python 3.13, Node 24, RTX 3050 4 GB):
> manual setup (`.venv`, `pip install -r requirements-api.txt`, PyTorch `cu124` wheels, `npm install`), the real uvicorn
> and Vite servers, every API route group over HTTP, the UI in headless Edge, the 136-test suite, and real model training.
> **Not verified:** the `scripts\windows\*.ps1` wrappers (the `-ExecutionPolicy Bypass` they use was refused in the automated
> session, so the manual commands below were run instead). If a wrapper fails on your machine, the manual commands are the
> reference.

## Requirements and ports

| Item | Version / value |
|---|---|
| Python | 3.10 or newer (3.11 recommended); `py` launcher or `python` on PATH |
| Node.js / npm | Node 18+ (20 LTS recommended); npm is included with Node |
| Backend | `http://127.0.0.1:8000` (FastAPI via uvicorn; API docs at `/docs`) |
| Frontend | `http://localhost:5173` (Vite dev server; proxies `/api` to the backend) |
| Optional | Label Studio `8080` (`8081` in docker-compose), TensorBoard `6006` |

## Where the data is

| What | Location |
|---|---|
| 50 unlabeled test X-rays (TEST DATA, never used for training) | `Data\validation_data\quadrant_enumeration_disease\xrays\val_0.png ... val_49.png` |
| Annotated DENTEX data (present) | `Data\training_data\{quadrant, quadrant_enumeration, quadrant-enumeration-disease}\xrays\*.png` + the matching `train_*.json`; unlabeled: `Data\training_data\unlabelled\xrays` |
| Processed outputs (manifests, splits, reports) | `Data\processed`, `Data\splits`, `Data\results` |
| Uploaded images | `Data\uploads` |
| Application database (SQLite) | `runtime\dentamind.sqlite3` (outside the image folder; override with `DATABASE_URL`) |
| Model checkpoints | `Data\checkpoints` - `*.pth` plus a `*.json` sidecar each (measured metrics, class mapping, software versions) |
| Reports | `Data\reports` - dataset audit, evaluation reports, active-learning experiment |

`Data`, `data` or `DATA` next to the code is found automatically; set `DATA_ROOT` in `.env` to use another folder.

## 1. One-time setup

```powershell
cd "D:\Dentex-Gen Ai"
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
```

`setup.ps1` (skips any step that is already done):

1. copies `.env.example` to `.env` only if `.env` does not exist;
2. creates `.venv` with Python 3.10+ if it does not exist;
3. checks whether the backend packages import; only if not, runs `pip install -r requirements-api.txt`;
4. checks Node.js 18+ and `frontend\node_modules`; only if missing, runs `npm.cmd install` in `frontend`;
5. stops with a clear message and the next command if any install fails;
6. prints an environment report (`scripts\validate_environment.py`).

Manual equivalent:

```powershell
Copy-Item .env.example .env            # only if you do not have a .env yet
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
cd frontend; npm.cmd install; cd ..
```

PyTorch is **not** needed to start the application. Install it only for model training/inference:
`.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt` (see that file for the CUDA/CPU wheel choice).

## 2. Check the data pipeline (no server needed)

```powershell
.\.venv\Scripts\python.exe scripts\validate_dataset.py
.\.venv\Scripts\python.exe scripts\run_pipeline.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m pytest            # also works once requirements-api.txt is installed (pytest + pytest-cov)
```

Expected now: `state: test_data_only`, `test_data: 50 images, validation_ok=True`, unit tests `OK`
(`tests\test_skeleton.py` is skipped under plain unittest when pytest is missing, and runs under pytest).

## 3. Start the application

Both servers in their own windows, waits until they answer, then runs all checks and opens the browser:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\start_all.ps1
```

Or start them yourself in two PowerShell windows:

```powershell
# window 1 - backend (Ctrl+C to stop)
powershell -ExecutionPolicy Bypass -File scripts\windows\start_backend.ps1
# equivalent: .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# window 2 - frontend (Ctrl+C to stop)
powershell -ExecutionPolicy Bypass -File scripts\windows\start_frontend.ps1
# equivalent: cd frontend; npm.cmd run dev -- --port 5173 --strictPort
```

Both start scripts refuse to start if their port is already taken and name the process using it.
Use `-Port` (backend/frontend) and `-ApiTarget http://127.0.0.1:<port>` (frontend) for other ports, or set
`VITE_API_TARGET` in `frontend\.env` (template: `frontend\.env.example`).

## 4. Verify (real HTTP requests, changes nothing)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\check_running.ps1
```

It checks: backend health, dataset status, the image list, downloading the first X-ray, that detection reports a
missing model instead of results, the frontend page, and the frontend-to-backend proxy. It exits with code 1 if any
check fails. Then, in the browser at http://localhost:5173:

| Step | Expected result today |
|---|---|
| Overview | "main dataset pending", 50 test-data images, current model "None" |
| X-ray Analysis -> choose an image | the radiograph is displayed; dimensions and source "test_data" are shown |
| Upload a PNG/JPEG | it appears in the list with source "upload" and is stored in `Data\uploads` |
| Run Detection | "Dental model setup required" - no boxes, labels or scores are shown |
| Settings | "test data only", 50 test images, diagnostics listing what is missing |

## Environment variables (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DATA_ROOT` | auto (`Data`/`data`) | data folder |
| `MODEL_CHECKPOINT_DIR` | `<data>\checkpoints` | trained checkpoints (+ `.json` metadata sidecar) |
| `DATABASE_URL` | `runtime\dentamind.sqlite3` | SQLite file on a local disk, e.g. `sqlite:///C:/DentaMind/dentamind.sqlite3` |
| `LABEL_STUDIO_URL`, `LABEL_STUDIO_API_KEY` | `http://localhost:8080`, empty | optional annotation server |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | empty | optional; without them reports use the deterministic template |
| `FRONTEND_URL` | `http://localhost:5173` | allowed CORS origin |
| `MAX_UPLOAD_MB` | `25` | upload size limit |
| `AUTO_PROCESS_DATASET`, `AUTO_PROCESS_INTERVAL_S` | `true`, `15` | validate/manifest/split new data automatically (never trains automatically) |
| `VITE_API_TARGET` (in `frontend\.env`) | `http://127.0.0.1:8000` | where the dev server forwards `/api` |

## Feature status

| Works without a trained model | Unavailable until a trained dental checkpoint exists |
|---|---|
| Browsing/uploading X-rays, image quality metrics | Tooth detection, segmentation masks, finding classification |
| Dataset discovery, validation, splits, pipeline report | Grad-CAM explanations, model-based uncertainty (entropy, disagreement) |
| Active-learning selection (random; others need model scores), Label Studio export/import, approval gate | Evaluation metrics (mAP, F1, ECE) - none are shown or estimated |
| Report drafting/validation from supplied findings | Training (also needs the main annotated dataset and PyTorch) |

## HTTP 403 when installing packages

A 403 during `pip install` or `npm install` means a proxy, firewall or registry policy refused the download - it is
not a problem in the project. Diagnose without printing secrets:

```powershell
.\.venv\Scripts\python.exe -m pip config list           # custom index-url / proxy?
npm.cmd config get registry                             # should be https://registry.npmjs.org/
npm.cmd config get https-proxy
Get-ChildItem Env: | Where-Object Name -match 'proxy'   # HTTP(S)_PROXY set?
Invoke-WebRequest https://pypi.org/simple/fastapi/ -UseBasicParsing -Method Head
Invoke-WebRequest https://registry.npmjs.org/vite -UseBasicParsing -Method Head
```

* If the last two commands also return 403, your network blocks the registries: use a network that allows them, or
  ask IT to allow `pypi.org`, `files.pythonhosted.org` and `registry.npmjs.org`.
* If you are behind a company proxy, set it for the session: `$env:HTTPS_PROXY="http://proxy.company:8080"` (pip),
  `npm.cmd config set https-proxy http://proxy.company:8080` (npm).
* Do not disable TLS verification to get around this.
* Then re-run `setup.ps1`; it only installs what is still missing.

## Other problems

| Symptom | Fix |
|---|---|
| `running scripts is disabled on this system` | use `powershell -ExecutionPolicy Bypass -File ...` as shown, or `Set-ExecutionPolicy -Scope Process Bypass` |
| `npm : File ...npm.ps1 cannot be loaded` | use `npm.cmd` (the scripts already do) |
| `Python was not found; run without arguments to install from the Microsoft Store` | install Python from python.org, or turn off the "App execution alias" for python in Windows Settings |
| `Port 8000 ... already in use by PID ...` | `taskkill /PID <pid> /F`, or start with `-Port 8001` and the frontend with `-ApiTarget http://127.0.0.1:8001` |
| UI says "Cannot reach the DentaMind backend" | backend window closed or crashed; run `check_running.ps1 -BackendOnly` |
| `Cannot open the SQLite database ...` | the database folder must be on a local writable disk; set `DATABASE_URL` as in the table above |
| `Main dataset is not available` | expected until the DENTEX data is placed as described in "Where the data is" |


## Exact commands used on this machine (copy-paste)

```powershell
cd "D:\Dentex-Gen Ai"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
.\.venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124   # RTX 3050, driver 610
cd frontend; npm.cmd install; cd ..

# start (two windows, or Start-Process as below)
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
cd frontend; npm.cmd run dev          # http://localhost:5173
```

Check CUDA: `.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"`.
Pick the PyTorch wheel index that matches your own driver (`cu121`, `cu124`, `cpu`); do not copy `cu124` blindly.

**One training at a time.** A 4 GB card cannot run two trainings together (the second one stalls or fails with CUDA
out-of-memory). Restarting the API does not stop a training started from the command line.
