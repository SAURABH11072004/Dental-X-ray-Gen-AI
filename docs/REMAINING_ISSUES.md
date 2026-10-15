# Remaining issues after the second pass

Date 2026-10-14 (second pass over `FINAL_ACCEPTANCE_REPORT.md` / `FUNCTIONALITY_AUDIT.md`). Evidence: `docs/audit_evidence/`. Status words: **FIXED** (verified by an executed test), **PARTIAL**, **BLOCKED** (needs something not available here), **NOT IMPLEMENTED** (absent, with the scope decision).

**Application state: still DEMO READY** for a local research demonstration. Not production-ready, not clinically validated.

## 1. Fixed in this pass (and how it was verified)

| # | Issue | Fix | Verification |
|---|---|---|---|
| 1 | `/api/health` reported `version: "unknown"` | `backend/version.py` (`APP_VERSION = "0.2.0"`, same as FastAPI and `frontend/package.json`) used by the app and the health endpoint; no secrets in the response | live `API-002` PASS (was the only failing live check), `SEC2-03`, `check_running.ps1` prints `version=0.2.0` |
| 2 | No authentication, loopback restriction or rate limiting | `backend/security.py`: shared API token (`runtime/api_token.txt`, git-ignored, or `DENTAMIND_API_TOKEN`) on every `/api` route except `GET /api/health`; non-loopback clients refused; per-client rate limits (control endpoints 20/min, failed authentication 20/min, ...); the Vite proxy injects the token **server-side**, so it is not in browser code | `security_live.json` **23/23**: 19 protected routes (upload, predict, reports, review sign-off, training start/stop, model select/promote/evaluate, dataset process, docs) answer 401 without the token and work with it; wrong token / wrong scheme 401; token absent from responses, source, built frontend, docs; 429 + `Retry-After`; **19 unit tests** (`tests/test_security_and_training_api.py`) |
| 3 | Training start had no conflict guard | `JobManager.running_jobs()`; start **and** dry run answer 409 while any job runs; jobs of dead processes do not block | `training_api.json` TAPI-04/05, unit tests |
| 4 | `resume_checkpoint` accepted any existing file via `..` | only a registered, verified checkpoint of the same task | SEC2-12, TAPI-15/16, unit tests |
| 5 | A **cancelled** job still wrote a checkpoint that the registry treated as a verified model | no checkpoint on cancel | TAPI-12 (failed before the fix) now PASS; `CancelledRunTests` |
| 6 | No harmless way to validate a training request | `dry_run` in `POST /api/training/start` and a "Validate only" button on the Training page; returns the checkpoint name it *would* write, creates nothing | TAPI-01/02, SEC2-13/14, UI-N-003 |
| 7 | Training API never exercised end to end | real SMOKE training through the API on a separate server (temporary checkpoint folder and database, CUDA hidden): progress, success, sidecar sha256, experiment row, no overwrite on repeat, cancel, error paths | `training_api.json` **20/20**; real `Data\checkpoints` byte-identical afterwards |
| 8 | Mask / detection instability were never validated | `scripts/evaluate_instability.py` on the validation split (30 films, 851 mask regions, 878 boxes): AUROC **0.59** (mask IoU < 0.8) and **0.64** (false-positive boxes, only 27) - **weak**; shown next to each signal in the API record and UI | `instability_validation.json` (also `Data/reports/`), `SignalValidationTests`, UI-N-005 |
| 9 | TensorBoard link shown although it is not installed | backend reports installed / event-file state; UI shows the truthful message | UI-N-004 |
| 10 | Hindi / Marathi "not reviewed" status was small print | prominent bilingual "awaiting linguistic review" line at the top of HTML, TXT and the on-screen report + `linguistic_review` JSON field; no value, id or finding changed | RPT-C10/C11, UI-N-001/002, 2 new unit tests; reports audit **61/61** |
| 11 | Retraining on approved annotations had never been checked end to end | dry-run verification: pool-image review approved by a second person becomes eligible; validation-split review is excluded | `approved_training_dry_run.json` **9/9** (no training executed) |
| 12 | Prerequisites route rejected task `numbering` | added | unit/live |

## 2. Still open

| Item | Status | Why / what would close it |
|---|---|---|
| Mask and detection instability as error detectors | **PARTIAL** | measured and weak (AUROC 0.59 / 0.64). They are displayed with that label; they must not be described as validated. Closing it needs a better signal (ensemble of independently trained models), not more UI. |
| Probability calibration | **PARTIAL** | ECE 0.048 (test) is measured; temperature scaling helped on test (0.036) but not on the calibration split (0.071 -> 0.076), so it is **not applied**. Scores stay "uncalibrated model scores"; no calibrated probability of error is offered anywhere. |
| Random vs entropy active-learning study | **PARTIAL** | the original finding (no consistent benefit over random) is preserved unchanged. The full 3-seed grid was not repeated (about 30 GPU-minutes; not justified by this pass). A single-seed CPU reproduction differed by up to 0.09 macro-F1 from the GPU run, which is larger than the strategy differences, so no claim about active learning should be made without a fixed device, more seeds and a paired test. |
| Training on approved annotations (the actual training) | **PARTIAL** | eligibility and prerequisites verified by dry run; the training itself was never run, so its effect is unmeasured. |
| Re-evaluation of detection / segmentation / numbering | **PARTIAL** | stored metrics were not re-run (cost, locked test split, GPU shared with the API); only the classifier's validation metrics were reproduced (CPU, within 0.007 macro-F1). |
| Windows scripts `setup.ps1`, `start_all.ps1` | **PARTIAL** | the other four scripts were run for real; these two reinstall packages / open windows and a browser, which this pass was told not to do automatically. |
| Hindi / Marathi linguistic quality | **BLOCKED** | needs a native-speaking dental professional. The reports say so prominently; no native-language clinical accuracy is claimed. |
| Label Studio live import/export | **BLOCKED** | not installed or configured. **Not needed for the current demonstration** (in-app region review exists); file export and the "not configured" states are verified. Recovery: install Label Studio and set `LABEL_STUDIO_URL` / `LABEL_STUDIO_API_KEY`. |
| TensorBoard | **BLOCKED** | package not installed and no event files exist; **not needed for the demonstration** (experiments come from the database). Recovery: `pip install tensorboard`, then train. |
| Live LLM report mode | **BLOCKED** | optional by design; the local template path needs no key and sends nothing out. |
| Docker | **BLOCKED** | local Windows setup works reliably; image build not attempted (multi-GB, network). |
| Ensemble disagreement | **NOT IMPLEMENTED** | only one checkpoint per task exists, so there are no real model outputs to compute it from; it is reported as "unavailable". It is not claimed anywhere. |
| PDF export, report-text editing | **NOT IMPLEMENTED** | not part of the agreed scope: reports are regenerated from structured findings (editing would let text drift from the evidence) and the HTML export prints to PDF from the browser. |
| Authentication scope | limitation | one shared token for one local user; no accounts/roles; reviewer names are self-declared. Rate limits are in-memory. Keep the API on `127.0.0.1`. |
| Git | open | the repository root is the whole `D:\` drive with no commits. Nothing was initialised, committed or pushed (approval needed). |
| `-ExecutionPolicy Bypass` in older docs | open (documentation) | not required; scripts run with `powershell -NoProfile -File ...`. |

## 3. Test counts (final run of this pass)

| Harness | PASS | FAIL | Note |
|---|---:|---:|---|
| Unit / integration (`unittest`) | **205** | 0 | was 180; +25 (security 19, training safety, i18n, signal validation, cancellation, ...) |
| Live API (`audit_live_api.py`) | **138** | 0 | was 137/1 |
| Per-model + failure scenarios | 27 | 0 | |
| Reports and languages | **61** | 0 | was 58 (+3 linguistic-review checks) |
| Live security | **23** | 0 | new |
| Training API (real smoke runs, separate server) | **20** | 0 | new |
| Approved-annotation dry run | **9** | 0 | new |
| No-numbering acceptance check | 1 | 0 | |
| Browser audit | **39** | 0 | was 34; +5 new UI checks |
| Review workflow (browser) | 27 | 0 | passes 27/27 on a clean database; in one chained run its *export* check failed because the script read the export before the approval was persisted - the script now polls; not an application defect |
| **Total** | **550** | **0** | no skipped tests; blocked items are listed above, not counted as passed |

## 4. Changes to data, database and artifacts

* **Checkpoints, manifests, splits, original X-rays, annotations, evaluation reports:** compared by SHA-256 before and after (41 files): **0 differences** (`integrity_round2.json`). No dataset split was regenerated, no model retrained.
* **Added file:** `Data/reports/instability_validation.json` (new measurement; nothing overwritten).
* **Database:** backed up first (`dentamind_start.sqlite3` plus a backup before every cleanup, kept outside the repository). Test runs created analyses, reports, reviews and uploads; **only those records** were removed with `scripts/audit_cleanup.py`. Final state equals the baseline: 3 uploads, 0 analyses/reports/reviews, 1 AL round, 12 jobs, 50 experiments. The smoke trainings ran in a temporary checkpoint folder and database that were deleted.
* **New runtime file:** `runtime/api_token.txt` (git-ignored; created on first start; delete it to rotate the token).
* **Configuration/packages:** no package installed or upgraded; `.env` untouched.
* **Git:** untouched (no init, commit or push).

## 5. Start and verify

```powershell
cd "D:\Dentex-Gen Ai"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000          # terminal 1 (creates runtime\api_token.txt on first start)
cd frontend; npm.cmd run dev                                                                # terminal 2 -> http://localhost:5173 (the proxy adds the token)
powershell -NoProfile -File scripts\windows\check_running.ps1                                # exit 0 = healthy (reads the token itself)
powershell -NoProfile -File scripts\run_audit_suite.ps1                                      # ~9 minutes; logs in docs\audit_evidence\
```
Calling the API by hand needs the header: `Invoke-RestMethod http://127.0.0.1:8000/api/models -Headers @{Authorization="Bearer $((Get-Content runtime\api_token.txt -Raw).Trim())"}`.
Set `DENTAMIND_AUTH=off` only for local development (loopback-only still applies). The `scripts\audit_security_live.py` step deliberately fills the rate limits and takes about 3 minutes; wait a minute before using other tools.

## 6. Is the application still demo-ready?

**Yes.** After every change the full suite was re-run against the restarted servers; real X-ray inference (detector, numbering, segmenter, classifier), uncertainty, Grad-CAM, region review, English / Hindi / Marathi report generation, export and retrieval all pass, and the browser workflow works through the authenticated proxy. The honest limits are those in section 2: weak instability signals, uncalibrated scores, no demonstrated benefit of active learning, unreviewed Hindi/Marathi wording, and integrations that were not installed.

## 7. Update after the UI simplification and the final polish pass

The application is still **demo-ready**. This section supersedes the browser counts in section 3; backend counts are unchanged.

| Item | Status | Evidence |
|---|---|---|
| Colour contrast (previously "not measured") | **FIXED**: a real WCAG AA measurement of all visible text found 15 failing combinations (10 on end-user pages); after darkening teal / amber / red / green / muted tokens it finds **0 on 15 page states** | `contrast.json`, browser check S-A11Y-3 PASS |
| Mobile X-ray workspace | **FIXED**: viewer follows the image controls, upload collapses once an image is chosen, 36 px zoom targets, no horizontal scroll at 390 px, region details scroll into view on tap | S-MOB-1/2/3 PASS, screenshots `shots_simplified/mobile_*.png` |
| Stale results, duplicate requests, API errors | verified: other image clears results and starts no request; one request per click; simulated 503 and 500 show clear messages and leave the app usable | S-STALE-1/2/3, S-ERR-1/2 PASS |
| End-user journey (upload -> analysis -> regions -> candidate classes/uncertainty -> report -> EN/HI/MR -> exports -> reopen -> sign-off -> review) | verified on the real backend | `ui_simplified.json` |

Tests executed in this pass (all counts are from the output files):
* Unit / integration 205 pass, 0 fail. Live API 138/138, per-model 27/27, reports 61/61, live security 23/23, training API 20/20, approved-annotation dry run 9/9, Windows check OK. Frontend production build OK.
* Browser: end-user suite **80 pass, 0 fail, 0 blocked**; full browser audit **37 pass, 0 fail**; review workflow **26 pass**; overlay geometry **pass**.
* Console / backend: no console error other than the two deliberately simulated failures; backend stderr has no traceback; the only 5xx responses in its access log are the intended 502/503 refusals (Label Studio / LLM not configured, missing-model scenarios).
* Integrity: 41 files (checkpoints, manifests, splits, evaluation reports) byte-identical; database back to baseline.

Still limited / not verified:
* Contrast covers visible **text** only; non-text contrast, hover/error states, overlay-label text (set by calculation) and screen-reader behaviour were not measured. Pinch-zoom on touch devices was not tested; on a phone the whole panorama is shown at ~12% and some labels are omitted to avoid overlap.
* One earlier full-audit run saw a single `ERR_CONNECTION_REFUSED` (browser to Vite) that did not recur in two re-runs; the cause was not identified.
* Everything listed in section 2 remains open (instability signals weak, scores uncalibrated, active-learning benefit unproven, unreviewed Hindi/Marathi wording, Label Studio / TensorBoard / LLM / Docker not set up, ensemble disagreement, PDF export and report editing not implemented).

## 8. Update after the report / review / Home refinement

Application still **demo-ready**. Details and results: `docs/UI_SIMPLIFICATION_REPORT.md` section 6.

* Fixed: report list and body clutter (banner and "Generated by" removed from the component, one neutral safety note, technical details collapsed), compact list with image name/date/status/Open, findings-table columns, collapsed uncertainty definitions, label clamping, double-click-safe review save with visible reasons, Home layout, one real contrast failure (4.41:1 list date).
* Tests executed: unit 205/205; live API 139/139; per-model 27/27; reports 61/61; security 23/23; training API 20/20; approved-annotation dry run 9/9; browser end-user suite 86/86; full browser audit 37/37; review workflow 27/27; overlay geometry pass; contrast measurement 0 failing combinations; frontend build OK. No test was skipped; none is counted as passed if blocked.
* Open: table sorting/filtering not implemented; reports keep a single review record (no multi-step history) and have no separate "Approved" state; text contrast only (no non-text contrast, no screen-reader test); no frontend unit tests; everything in section 2 above still applies.
* Data: the four test reports named in the request were test output and exist only in backups; the cleanup script removes all reports after its cutoff, so real reports created later by hand would be removed too (see the data note in the UI report).
