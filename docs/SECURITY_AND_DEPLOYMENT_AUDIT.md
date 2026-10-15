# Security, reliability and Windows deployment audit

Audit date 2026-10-14, project `D:\Dentex-Gen Ai`, Windows 11 Home 10.0.26300, Python 3.13.0 (`.venv`), Node v24.20.0, RTX 3050 Laptop GPU 4 GB.
This is a **basic functional review of a local research tool**. It is not a security certification, a penetration test or a statement of production readiness.

## 1. Windows environment (all commands actually run)

| Item | Evidence | Result |
|---|---|---|
| Python executable / venv | `.venv\Scripts\python.exe` -> Python 3.13.0, `sys.prefix = D:\Dentex-Gen Ai\.venv` | PASS |
| Backend dependencies | fastapi 0.143.0, uvicorn 0.54.0, pydantic 2.14.1, numpy 2.5.4, Pillow 12.3.0, python-multipart 0.0.32, torch 2.6.0+cu124, torchvision 0.21.0+cu124 import and run | PASS |
| Frontend dependencies | `npm ls --depth=0`: react 18.3.1, react-router-dom 6.30.6, vite 5.4.21, tailwindcss 3.4.19, recharts 2.15.4, lucide-react 0.460.0; `vite build` succeeds | PASS |
| Declared vs imported packages | static import scan of `src`, `backend`, `scripts`, `tests`: everything the running app imports is declared. Undeclared imports (`detectron2`, `cv2`, `skimage`, `lightning`, `torchmetrics`, `albumentations`, `tqdm`, `importlib_metadata`) belong to the **original DENTEX research modules** (`detector.py`, `imageproc.py`, `models/*`, `torchdataset.py`, `fileutils.py`) or to optional code paths (`cv2`/`skimage` in `preprocess.py`) that the app does not import. No package was installed, upgraded or removed | PASS (note) |
| PowerShell scripts | all six `scripts\windows\*.ps1` parse (0 syntax errors); `check_running.ps1` exit 0 against :8000/:5173; `start_backend.ps1` and `start_frontend.ps1` started real servers on :8031/:5190 and `check_running.ps1 -ApiPort 8031 -WebPort 5190` passed; both refuse cleanly (exit 1, plain message) when their port is busy | PASS |
| `setup.ps1`, `start_all.ps1` | parsed but **not executed**: they reinstall packages / open windows and a browser | not run |
| Execution policy | effective policy is `RemoteSigned` (CurrentUser); local scripts run with `powershell -NoProfile -File ...`. The documented `-ExecutionPolicy Bypass` flag is **not needed** here and is blocked in some managed environments | note |
| Working directories / relative paths | scripts resolve the project root from their own location; the API resolves `Data`, `runtime`, `Data/checkpoints` relative to the project root (`/api/system/settings` returns relative paths) | PASS |
| API base URL and proxy | Vite proxies `/api` to `http://127.0.0.1:8000` (`vite.config.js`, override `VITE_API_TARGET`); `check_running.ps1` "Frontend proxy -> backend" OK; the browser audit ran through :5173 | PASS |
| Ports 8000 / 5173 | listening and answering; busy-port refusal verified | PASS |
| Database path / permissions | `runtime\dentamind.sqlite3` inside the project, read/write; an unusable `DATABASE_URL` (`Z:\...`) makes the server exit with code 1 and `Cannot open the SQLite database at ... Set DATABASE_URL in .env` | PASS |
| GPU detection and CPU fallback | `/api/health` reports the RTX 3050 and CUDA; a server started with `CUDA_VISIBLE_DEVICES=-1` reports `cuda_available:false` and still ran real detector+classifier+segmenter+numbering inference on the CPU | PASS |
| Pitfall found | `start_backend.ps1` runs uvicorn with `--reload`. Stopping only the supervisor process on Windows leaves an orphan **worker** that keeps the port; stop the whole process tree (`taskkill /PID <pid> /T /F`) | documented |

## 2. Security checks (60 live checks in these areas, plus code review)

| Area | What was tested | Result |
|---|---|---|
| Upload type/size validation | extension allow-list (png/jpg/jpeg), magic-byte signature, full decode, dimension limits, 25 MiB cap (message was mislabelled MB/MiB - fixed), 20000x20000 PNG rejected, 9 invalid payload types rejected with 422 and a code; nothing from a rejected upload remains on disk | PASS |
| Path traversal / safe filenames | upload named `../../../evil_traversal.png` is stored as `up_<sha256-prefix>.png` inside `Data\uploads` only (display name kept, 120 chars max); `..%2F..%2F` and `%2e%2e` in route parameters -> 404; file routes resolve ids through `safe_join` | PASS |
| API error handling | uniform JSON envelope `{error:{code,message,hint}}`; no stack trace, no absolute path, no SQL text in any of the 40 validation/security responses or the 32-route GET sweep | PASS |
| Job errors / logs | **defect found:** failed training/evaluation jobs were served with raw tracebacks and absolute paths (e.g. the `.venv\Lib\site-packages\...` path). **Fixed:** the API now serves the final exception line only; log tails keep frames but show file names instead of absolute paths; the raw text stays in the database | fixed |
| Secrets / API keys | `.env` is git-ignored, only `.env.example` exists; no hard-coded key in `*.py/*.js/*.jsx/*.yml/*.md`; `/api/system/settings` returns `label_studio_api_key_set: false` (a boolean, never the key) and `llm_base_url_set` instead of the URL | PASS |
| Unsafe HTML in reports | React renders text nodes only (no `dangerouslySetInnerHTML`, `innerHTML`, `eval` in `frontend/src`); the HTML export escapes every field: a reviewer name `<script>alert(1)</script>` appears escaped, exports contain no `<script>`, `<iframe>` or `on*=` handlers | PASS |
| SQL | every value is a bound parameter (`?`); table/column/`ORDER BY`/`WHERE` fragments are developer-supplied constants - no request field reaches them (grep of all `db.list` / `count` call sites); SQL meta-characters in ids return 404 | PASS |
| Cross-origin | allow-list: the configured frontend URL, `http://localhost:5173`, `http://127.0.0.1:5173`; pre-flight from the Vite origin allowed, from `https://evil.example` not allowed; no credentials | PASS |
| Debug / development routes | no debug flag; `/docs`, `/redoc`, `/openapi.json` are enabled (Swagger UI) - intended for local use; scripts bind `127.0.0.1` only | note |
| Exposure of local files | only registered image ids can be downloaded; dataset status endpoints state the configured data folder on purpose (the UI tells the user where to place data) | PASS (note) |
| Authentication / authorisation | **Implemented in the second pass** (`backend/security.py`): shared API token (`runtime/api_token.txt`, git-ignored, or `DENTAMIND_API_TOKEN`) required on every `/api` route except `GET /api/health`, and on `/docs`/`/openapi.json`; the Vite proxy adds it server-side so it never reaches browser code; non-loopback clients get 403; the token is never logged or returned. 23 live checks (`security_live.json`) incl. 19 protected routes denied without a token and allowed with it | PASS (single local user; no accounts or roles) |
| Rate limiting / quotas | per-client sliding windows: upload 60/min, heavy inference 120/min, control (training, model management, dataset processing) 20/min, other writes 300/min, reads 1500/min, failed authentication 20/min; 429 + `Retry-After` + JSON envelope; verified live | PASS (in-memory, per process; not DoS protection) |
| Transport security | plain HTTP on loopback; no TLS configured; **no TLS verification was disabled** and no package index or registry setting was changed | note |

## 3. Data and privacy

* **Originals and checkpoints preserved:** SHA-256 of all 8 checkpoint files (`.pth` + `.json` sidecars) is identical before and after the audit; training/validation image directories have the same file counts and byte totals (details in `docs/FINAL_ACCEPTANCE_REPORT.md`).
* **No external transmission:** the only outbound calls in the application code are (a) a TCP/HTTP probe of the configured TensorBoard and Label Studio URLs (loopback), (b) Label Studio calls when a URL and key are configured, (c) the LLM report call **only** when `LLM_BASE_URL/KEY/MODEL` are set. With the shipped configuration `llm.mode = template`, nothing leaves the machine; the local report generator needs no key.
* **Git:** the repository root is the **whole `D:\` drive** (`git rev-parse --show-toplevel` = `D:/`), the branch has **no commits**, and Git refuses to run without a `safe.directory` exception because the drive root is owned by SYSTEM. `.gitignore` inside the project correctly ignores `data/` (matches `Data/` on Windows), `runtime/`, `.env`, `*.sqlite3`, `frontend/dist/` - verified with `git check-ignore -v` for X-rays, uploads, checkpoints, the database and reports. **Recommendation:** initialise a repository inside `D:\Dentex-Gen Ai` instead of using the drive root, otherwise `git add -A` from `D:\` would stage unrelated personal folders. Nothing was committed or staged by this audit.
* **Test vs demo data:** synthetic fixtures exist only in `src/dentexmodel/data/synthetic.py`, are used by unit tests (labelled "SYNTHETIC TEST DATA"), and are discoverable by the app only with an explicit `include_synthetic` flag and a `_synthetic_test` folder, which does not exist. The "test data" images the UI offers are the real unlabeled `validation_data` radiographs and are flagged `is_test_data`.
* **Records created by the audit** (uploads, analyses, reports, reviews, AL rounds, exported batches) were removed by `scripts\audit_cleanup.py` after a database backup; ids are in `docs/audit_evidence/cleanup_log_*.json`. Jobs and experiments (history) were kept.

## 4. Performance and stability (measured, this machine)

| Measurement | Value | Source |
|---|---|---|
| API cold start to first healthy `/api/health` | **4.1 s** | `startup_timing.json` |
| First prediction after start (loads detector + classifier) | **9.59 s**; second call 0.59 s | same |
| First full analysis after that (also loads segmenter + numbering) | 5.75 s | same |
| Upload of a 1976x976 PNG (validate, hash, store, quality flags) | 0.10 s | `UPL-001` |
| Steady-state latency on the GPU, 8 repeats each (median / max) | `/predict` 0.39 / 0.41 s; `/segment` 0.37 / 0.46 s; `/analyze/full` 1.17 / 1.26 s | `model_audit.json` |
| GPU memory (nvidia-smi) | 0 MB idle -> 1293 MB after the first prediction -> 1573 MB after the first full analysis; no growth over 24 repeated requests (3711 -> 3711 MB, shared with a running browser audit) | same; **peak allocation was not instrumented** |
| Response sizes | `/predict` 12924 B; `/analyze/full` 82 kB, 104 kB, 86 kB (includes RLE masks) | `startup_timing.json`, `model_audit.json` |
| CPU only (CUDA hidden) | `/predict` 200 device=cpu n=33; full pipeline 10.6 s - the same results (33 vs 33 detections) but one to two orders of magnitude slower; timing varies with machine load (earlier run: 22.8 s and 53.4 s) | `MOD-CPU-*` |
| Frontend production build | `vite build` succeeds in about 8-9 s (one chunk > 500 kB warning) | `npm run build` |
| Large-image rendering in the browser | largest radiograph in the set (3076x1536, qed_train_637): image decoded in the viewer in 19 ms; full analysis HTTP 3820 ms; table + 30 overlay boxes visible after 6539 ms; response 111 kB; JS heap 362 MB. Typical film (2794x1316, val_12): decoded 169 ms, analysis HTTP 2257 ms, UI complete 4603 ms, 32 boxes. | `ui_perf.json` |
| Repeated requests and cleanup | 24 inference requests leave `Data\uploads` unchanged; the system temp folder entry count went 1238 -> 1237 (not attributable to the app); the same image twice gives identical detections | `MOD-CLEAN`, `MOD-DET-REPEAT` |
| Health endpoint | `?probes=false` (what the UI polls every 20 s) about 0.5 s; with service probes **was 6.5-8 s, now about 2 s** (IPv6 `localhost` + sequential timeouts; probes now concurrent on 127.0.0.1) | defect fixed |

## 5. Dependency and test integrity

| Suite | Result |
|---|---|
| Unit/integration tests `python -m unittest discover -s tests -v` | **205 tests, 0 failures, 0 errors, 0 skipped** (161 existing + 44 regression tests added for audit findings) |
| Tests that were not run | Docker build, `setup.ps1`, live Label Studio, live LLM, TensorBoard (not installed) |
| Synthetic fixtures | labelled TEST DATA in `tests/helpers.py` / `synthetic.py`; they never stand in for real-inference tests (the live harnesses call the real servers) |
| Test mode vs demo mode | the app has no "test mode" switch; unit tests build their own temporary settings (`TmpCase`) and never touch `Data\` or `runtime\`; the live audit scripts only call the running servers |

Suite runs recorded by `scripts\run_audit_suite.ps1` (`docs/audit_evidence/suite_log.json`):

| Command | Exit code | Duration |
|---|---|---|
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe -m unittest discover -s tests -v` | 0 | 48.6 s |
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe scripts\audit_live_api.py` | 0 | 38.5 s |
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe scripts\audit_models.py` | 0 | 55.7 s |
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe scripts\audit_reports.py` | 0 | 10.2 s |
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe scripts\audit_no_numbering.py` | 0 | 9.6 s |
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe scripts\audit_approved_training.py` | 0 | 6.2 s |
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe scripts\audit_training_api.py` | 0 | 25.2 s |
| `powershell -NoProfile -File scripts\windows\check_running.ps1` | 0 | 2.1 s |
| `D:\Dentex-Gen Ai\.venv\Scripts\python.exe scripts\audit_security_live.py` | 0 | 192.1 s |

## 6. Windows runbook (verified)

```powershell
cd "D:\Dentex-Gen Ai"
# terminal 1 - API
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000      # or: powershell -NoProfile -File scripts\windows\start_backend.ps1
# terminal 2 - UI (http://localhost:5173)
cd frontend; npm.cmd run dev                                                              # or: powershell -NoProfile -File scripts\windows\start_frontend.ps1
# health check - real HTTP requests, exit code 0 only if every check passes
powershell -NoProfile -File scripts\windows\check_running.ps1
# stop a server started with --reload: kill the process TREE
taskkill /PID <pid> /T /F
```

If setup is blocked: `pip install -r requirements-api.txt` needs network access to the package index; a corporate proxy should be configured with the standard `pip` proxy settings, not by disabling TLS verification.
The CUDA build of PyTorch comes from `https://download.pytorch.org/whl/cu124`.

## 7. Open items (not fixed, by decision)

1. Authentication is a single shared token for one local user (no accounts/roles); rate limits are in-memory per process. Reviewer/approver names remain self-declared text. Keep the API on `127.0.0.1`.
2. Git repository root is `D:\` and has no commits.
3. (Fixed in the second pass: `/api/health` now reports version 0.2.0.)
4. Documentation shows `-ExecutionPolicy Bypass` although it is not required.
5. `/docs` (Swagger UI) is enabled but now requires the token.
6. Re-running "Evaluate" for a model overwrites that model's validation report by design.
