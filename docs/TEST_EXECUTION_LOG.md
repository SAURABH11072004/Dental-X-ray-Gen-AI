# Test execution log

Audit date 2026-10-14, machine `SAURABH` (Windows 11 Home 10.0.26300, Python 3.13.0, Node v24.20.0, Edge headless for the browser runs, NVIDIA GeForce RTX 3050 Laptop GPU 4 GB, torch 2.6.0+cu124).
Times are local (UTC+5:30) unless a field says UTC. Everything listed was actually executed; harness bugs and failed runs are listed too, because they are part of the record.
Raw output of each step is in `docs/audit_evidence/` (named below). Test verdicts live in the `SUMMARY` lines / JSON files, **not** in the exit codes (a harness exits 0 even when it recorded a FAIL).

## 1. Final suite - `powershell -NoProfile -File scripts\run_audit_suite.ps1` (servers running; recorded in `docs/audit_evidence/suite_log.json`)

| Step | Command | Exit code | Duration | Verdict (from the step's own log) | Log |
|---|---|---:|---:|---|---|
| unit_tests | `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` | 0 | 52.9 s | **180 tests, OK** (0 failures, 0 errors, 0 skipped) | `unit_tests.log` |
| live_api | `.\.venv\Scripts\python.exe scripts\audit_live_api.py` | 0 | 40.2 s | **137 PASS, 1 FAIL** (API-002: `/api/health` reports `version: "unknown"`, cosmetic) | `live_api.log`, `live_api_tests.json` |
| models | `.\.venv\Scripts\python.exe scripts\audit_models.py` | 0 | 60.8 s | **27 PASS, 0 FAIL** | `models.log`, `model_audit.json` |
| reports | `.\.venv\Scripts\python.exe scripts\audit_reports.py` | 0 | 10.1 s | **58 PASS, 0 FAIL** | `reports.log`, `report_audit.json` |
| no_numbering | `.\.venv\Scripts\python.exe scripts\audit_no_numbering.py` | 0 | 10.4 s | **PASS** (numbering step `unavailable`, 0 of 32 regions numbered, report lists no numbering model) | `no_numbering.log`, `no_numbering_check.json` |
| windows_check_running | `powershell -NoProfile -File scripts\windows\check_running.ps1` | 0 | 2.6 s | all checks `[ OK ]` (backend health, dataset status, image list, image download, real detection, frontend page, frontend proxy) | `windows_check_running.log` |

## 2. Browser runs (Node 24 + playwright-core + Edge, real Vite :5173 and real FastAPI :8000)

| Run | Command | Exit code | Result | Evidence |
|---|---|---:|---|---|
| Browser audit, final | `node audit_ui.mjs` | 1 (*) | **34 PASS, 0 FAIL** (13 routes, controls crawl, upload errors, real upload -> analysis -> uncertainty -> Grad-CAM -> report -> HI/MR -> export -> persistence) | `ui_audit.json`, `ui_audit_run.log`, `ui_controls_clicked.txt`, `shots/` |
| Overlay geometry | `node geo_check.mjs` | 0 | **PASS** - 32 rects == 32 API boxes, viewBox == natural size 2794x1316, on-screen offset < 0.3 px | `overlay_geometry.json`, `shots/overlay_geometry.png` |
| Browser performance | `node perf_ui.mjs` | 0 | measured (see `SECURITY_AND_DEPLOYMENT_AUDIT.md` section 4) | `ui_perf.json` |
| Review workflow | `node phase.mjs <shots>` | 0 | **27 PASS, 0 FAIL** (two 400s in the console are the intended duplicate and self-approval refusals) | `review_workflow_run.log`, `shots_phase/` |

(*) The Node process exits 1 **after** printing its summary and writing `ui_audit.json`, because Playwright raises an unhandled `TargetClosedError` while the browser is closing (stack in `ui_audit_err.log`). The verdicts are in `ui_audit.json`; the exit code carries no test information.

## 3. Chronological record of the audit (including failed and superseded runs)

| # | What was run | Exit | Outcome / note |
|---|---|---:|---|
| 1 | `git status` | 128 | `detected dubious ownership in repository at 'D:/'` (the repo root is the drive root). Re-run per command with `git -c safe.directory=D:/`: status works; `git log` -> 128 `your current branch 'main' does not have any commits yet`. No global git setting was changed. |
| 2 | `Get-NetTCPConnection -LocalPort 8000,5173`; `GET /api/health`; `Get-ChildItem Data\checkpoints` | 0 | both servers healthy, 4 checkpoints + 4 sidecars, GPU 2.6-3.4 GB used by the already-running API |
| 3 | SHA-256 of all checkpoint files, file counts/bytes of `training_data`, `validation_data`, `splits`, `uploads`, hash of the DB | 0 | baseline saved as `snapshot_before.json` |
| 4 | baseline `python -m unittest discover -s tests -v` | 0 | 161 tests OK in 50.6 s |
| 5 | `scripts\audit_live_api.py` (first execution) | 1 | harness bug: `ImportError: cannot import name 'load_settings'` after 3 harness-expectation FAILs (it assumed HTTP 400; the app correctly answers 422). Real findings in this run: overlay 404 for full analyses (D04), a review accepted for a non-existent image (D06), wrong status codes (D10), size message unit (D11) |
| 6 | restart of the API after each batch of fixes (4 times) | - | only my own server process was restarted; no job was running |
| 7 | `scripts\audit_live_api.py` runs 2-5 | 0 | 134/3 -> 136/1 -> 137/1 PASS/FAIL as defects D04, D06, D10 and (with the added route sweep) D08 were fixed; the one remaining FAIL is cosmetic (D16) |
| 8 | **first browser crawl** `audit_ui.mjs` (before POSTs were blocked) | 1 | 26 PASS / 6 FAIL. It found D01 (Reports crash), D02 (concurrent evaluations), D03 (numbering `Use` 422) **and** clicked state-changing buttons - side effects disclosed in `FINAL_ACCEPTANCE_REPORT.md`, defect D23 |
| 9 | `scripts\check_leakage.py --help` | 0 | **the script has no `--help`: it ran and regenerated `Data/reports/leakage_check.*`** with identical results (794/113/113/113 distinct films, all overlaps 0). Disclosed. |
| 10 | second browser crawl (POSTs aborted) | 1 | 30 PASS / 4 FAIL: overlay selector bug in my script, two idempotent-control cases, one download-abort false positive |
| 11 | `scripts\train_model.py ... --device cpu --max-train-images 8 ...` (temporary checkpoint dir + DB) | 0 | smoke test succeeded in 11.4 s; real checkpoints unchanged |
| 12 | `scripts\evaluate_model.py --checkpoint dentex_findings_classification_v1.pth --split val --device cpu --out-dir <scratch>` | 0 | 39 s; accuracy 0.8218 vs 0.8248 stored, macro-F1 0.7114 vs 0.7179; original report and sidecar untouched |
| 13 | `scripts\run_al_experiment.py --seeds 0 --strategies random entropy --rounds 1 --device cpu --no-db --out-dir <scratch>` | 0 | ~8 min; macro-F1 random@120 0.6771, entropy@120 0.5880 (original GPU: 0.6388 / 0.6438); no DB rows, original result file untouched |
| 14 | `scripts\audit_reports.py` first runs | 1 / 0 | harness `IndexError` (fixed) then 56-58 PASS; real findings: validator gaps D05; my own first fix broke real reports (spelling `DeepCaries` vs `Deep Caries`) and was caught by this run before release |
| 15 | `scripts\audit_models.py` runs | 1 / 0 | `KeyError 'items'` (image-list limit is 1000; harness bug), then 23 PASS/4 FAIL (RLE orientation assumption in my checker; tampered-sidecar finding D07), then 27/0 |
| 16 | PowerShell: parse of the 6 scripts; `check_running.ps1`; `start_backend.ps1` / `start_frontend.ps1` while the ports are busy | 0 / 0 / 1 / 1 | parse errors 0; both start scripts refuse with a clear message (exit 1 is the intended behaviour) |
| 17 | `start_backend.ps1 -Port 8031` and `start_frontend.ps1 -Port 5190 -ApiTarget http://127.0.0.1:8031` (hidden windows) then `check_running.ps1 -ApiPort 8031 -WebPort 5190` | 0 | all checks OK; afterwards port 8031 stayed occupied by an orphan `--reload` worker (D17); it was identified (parent pid = the stopped supervisor) and stopped; ports 8000/5173 never interrupted |
| 18 | `npm.cmd run build` (frontend) | 0 | built in 7-9 s on every run (chunk-size warning only) |
| 19 | measurements: cold start, first/second prediction, health with/without probes, GPU memory | 0 | `startup_timing.json` |
| 20 | `scripts\audit_cleanup.py --cutoff 2026-10-14T10:15:00` (dry run, then `--apply` four times, each with a DB backup) | 0 | restored the baseline: analyses 0, reports 0, reviews 0, exports 0, AL rounds 1 (pre-existing), uploads 3 (pre-existing), jobs 12, experiments 50 |
| 21 | data-integrity comparison against `snapshot_before.json` | 0 | all 8 checkpoint files byte-identical; `training_data` 3,606 files / 14,725,611,903 bytes and `validation_data` 51 files / 201,044,945 bytes identical; `docs/audit_evidence/data_integrity.json` |

## 4. Totals across all executed harnesses (final state)

| Harness | PASS | FAIL | BLOCKED | PARTIAL / other |
|---|---:|---:|---:|---|
| Unit/integration (`unittest`) | 180 | 0 | - | 0 skipped |
| Live API (`audit_live_api.py`) | 137 | 1 (cosmetic, D16) | 0 | - |
| Per-model + failure scenarios (`audit_models.py`) | 27 | 0 | 0 | - |
| Reports / languages (`audit_reports.py`) | 58 | 0 | 0 | - |
| Browser audit (`audit_ui.mjs`) | 34 | 0 | 0 | - |
| Review workflow (browser) | 27 | 0 | 0 | - |
| Overlay geometry, no-numbering, Windows check | 3 | 0 | 0 | - |
| **Total** | **466** | **1** | **0** | |

Not executed (reasons in `FUNCTIONALITY_AUDIT.md`): live Label Studio, live LLM, TensorBoard, Docker build, `setup.ps1`, `start_all.ps1`, API-started training against the real trainer, the full original active-learning grid, re-evaluation of detection/segmentation/numbering (the test split is locked and the GPU was occupied).

## 5. Second pass - remaining findings (same day)

Servers restarted after each batch of backend changes (only my own server processes). Final suite: `powershell -NoProfile -File scriptsun_audit_suite.ps1` -> every step exit 0 (`suite_log.json`).

| Step | Command | Exit | Result |
|---|---|---:|---|
| unit tests | `python -m unittest discover -s tests -v` | 0 | **205 OK** (was 180) |
| live API | `scriptsudit_live_api.py` | 0 | **138 PASS, 0 FAIL** (version check now passes) |
| per-model | `scriptsudit_models.py` | 0 | 27 PASS |
| reports | `scriptsudit_reports.py` | 0 | **61 PASS** (3 new linguistic-review checks) |
| no numbering | `scriptsudit_no_numbering.py` | 0 | PASS |
| approved-annotation dry run | `scriptsudit_approved_training.py` | 0 | **9 PASS** (first run: 7/2 because a 429 from the previous step's rate-limit burst; re-run after the window: 9/0) |
| training API (real smoke runs) | `scriptsudit_training_api.py` | 0 | **20 PASS** (first run 19/1: TAPI-12 found that a cancelled job still wrote a checkpoint - fixed - then 20/0) |
| security (live) | `scriptsudit_security_live.py` | 0 | **23 PASS** (first runs failed 5 and 1 checks because my test's own unauthenticated probes filled the failed-authentication bucket - the limiter worked; the test now waits for the window) |
| windows check | `scripts\windows\check_running.ps1` | 0 | all OK, `version=0.2.0` |
| browser audit | `node audit_ui.mjs` | 1 (*) | **39 PASS, 0 FAIL** (first run 37/2: my script switched the report language before the export check and the Uncertainty page did not pass the new `signal_validation` field - the latter was a real UI gap, fixed) |
| overlay geometry | `node geo_check.mjs` | 0 | PASS |
| review workflow | `node phase.mjs` | 0 | 27/27 on a clean database (one chained run failed its export check because the script read the export before the approval was persisted; now polls) |
| instability validation | `scripts\evaluate_instability.py --images 30` | 0 | mask AUROC 0.59, detection AUROC 0.64 (validation split; weak) |
| integrity | SHA-256 of 41 files vs the snapshot taken at the start of the pass | 0 | 0 differences (`integrity_round2.json`) |

Other incidents in this pass (kept for the record): a Python heredoc patch turned `` in `scriptsudit_*.py` and `runtimepi_token` into bell characters in two PowerShell scripts (the Windows check then sent no token and got 401); found by the suite, fixed, and a scan for control characters in scripts/backend/frontend/tests is clean.
(*) same unhandled `TargetClosedError` at browser close as before; verdicts are in `ui_audit.json`.
