# DentaMind AI - final acceptance report

Acceptance date 2026-10-14. Project `D:\Dentex-Gen Ai`. Every outcome below was produced by running the **real** FastAPI backend and the **real** Vite frontend, with real checkpoints on real radiographs;
no mocked inference was used in any acceptance test. Companion documents: `FUNCTIONALITY_AUDIT.md` (60-feature inventory and defect register), `END_TO_END_TEST_REPORT.md`,
`MULTILINGUAL_REPORT_TEST_REPORT.md`, `RESEARCH_TOOLS_VALIDATION.md`, `SECURITY_AND_DEPLOYMENT_AUDIT.md`, `TEST_EXECUTION_LOG.md`. Raw evidence: `docs/audit_evidence/`.

## Overall verdict

# **DEMO READY** - for a local demonstration of a research prototype

The essential local workflow - upload a radiograph, real detection / numbering / segmentation / classification, uncertainty, Grad-CAM, region review, English / Hindi / Marathi research-draft reports, export and reopening - works with real model outputs, and every link of it was verified end to end.
This verdict does **not** mean production readiness, clinical validity or regulatory suitability. Nothing in the system is clinically validated, the classifier has no "healthy" class, and the Hindi and Marathi wording has not been reviewed by a native-speaking dental professional.
Items that stay open are listed under "Failed and blocked tests" and "Known limitations".

> **Update (second pass, same day).** The remaining findings were worked through; see `REMAINING_ISSUES.md`. Changes to the statements below: `/api/health` now reports version 0.2.0 (the one FAIL is fixed); token authentication, loopback restriction and rate limiting are implemented and verified (23 live checks); the training API was exercised with real smoke runs (20 checks) and gained a dry run and a conflict guard; mask/detection instability were measured (AUROC 0.59 / 0.64: weak) and are labelled as such; Hindi/Marathi reports carry a prominent "awaiting linguistic review" line. Final counts: 205 unit tests, 550 passing checks in all harnesses, 0 failing. The verdict stays **DEMO READY**. Where a line below says "no authentication" or "version unknown", it describes the state before this pass.

## 1. Summary of the system

* **Models** (PyTorch 2.6, torchvision 0.21, trained on the DENTEX panoramic radiograph data in `Data\training_data`): tooth detection (Faster R-CNN R50-FPN), tooth segmentation (Mask R-CNN R50-FPN), FDI tooth numbering (Faster R-CNN, 32 classes), four-class finding classification (ResNet-50; **no healthy class**, so its output is a *candidate class*, not a finding).
* **Pipeline** (`POST /api/analyze/full`): preprocess -> detect -> number -> segment -> match (one-to-one IoU) -> classify -> uncertainty; every step reports `ok / unavailable / failed` with a reason; regions carry content-derived ids.
* **Uncertainty:** normalised entropy, flip-TTA disagreement, mask/detection instability; high-entropy regions are abstained (no class named) and routed to manual review. Thresholds are provisional.
* **Human review:** in-app region review with audit history, duplicate refusal, a second named approver, and export of approved reviews that never includes test/validation/labelled images.
* **Active learning:** pool scoring plus random / entropy / combined selection with seeds, budgets, saved reasons and a hard test-split exclusion; the measured result is **no consistent benefit over random**.
* **Reports:** deterministic templates in English, Hindi and Marathi generated from the same structured findings; HTML, TXT and JSON export; validation and named-reviewer sign-off; no external service needed.
* **Stack:** FastAPI + SQLite + React 18/Vite 5/Tailwind; Windows scripts; 180 unit tests.

## 2. The 20 acceptance tests

| ID | Action | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| AT-01 | start FastAPI: `.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` | server starts | healthy 4.1 s after launch on a clean start | **PASS** | `startup_timing.json` |
| AT-02 | start Vite: `cd frontend; npm.cmd run dev` | UI on :5173 proxying `/api` | HTTP 200; proxy to the API verified; also started with `start_frontend.ps1` on :5190 | **PASS** | `windows_check_running.log`, `windows_scripts.log` |
| AT-03 | confirm backend health | backend/database ok, 4 checkpoints, GPU facts | `GET /api/health` ok; `check_running.ps1` exit 0 | **PASS** | `live_api_tests.json` API-001 |
| AT-04 | upload a valid dental X-ray (browser and API) | stored under a hash id, original bytes returned unchanged | PNG, JPEG and Unicode/space filename accepted; duplicate detected; download byte-identical | **PASS** | UPL-001..005, UI-E-001 |
| AT-05 | reject invalid / corrupted images | 4xx with a clear message, nothing stored | corrupt, truncated, wrong signature, `.txt`, `.exe`, SVG, HTML, empty, 8x8, 26 MB and 20000x20000 all refused (422) and nothing left on disk; browser shows the message | **PASS** | UPL-010..022/030, UI-D-001/002 |
| AT-06 | run actual detection inference | real boxes, valid geometry | 31 / 28 / 33 detections on two test-split films and one upload, device `cuda`, ~0.4 s; boxes finite and inside the image; identical on repeat | **PASS** | `model_audit.json` MOD-DET-* |
| AT-07 | run classification where supported | softmax per crop, abstention logic | four columns, rows sum to 1; candidate class shown as "not a finding"; high-entropy regions abstained | **PASS** | MOD-CLS-*, UI-E-003 |
| AT-08 | run actual segmentation where supported | valid masks | 32 / 29 / 32 instances; masks decode to H x W, area == pixel count, inside their boxes | **PASS** | MOD-SEG-* |
| AT-09 | predictions, confidence values and overlays match backend outputs | identical | all 32 table rows equal the API; 32 SVG rects equal the API boxes exactly; viewBox == image size; on-screen position within 0.3 px; overlay PNG size == original; pooled recall@0.5 vs DENTEX ground truth 0.945 | **PASS** | UI-E-003/004, `overlay_geometry.json`, INF-013/020, `alignment.json` |
| AT-10 | unavailable tooth numbering is not fabricated | no FDI numbers, step marked unavailable | with the numbering checkpoint removed: step `number: unavailable`, **0 of 32 regions numbered**, all flagged for review, the report names no numbering model; with all models missing the pipeline stops with `detect: unavailable` and invents nothing | **PASS** | `no_numbering_check.json`, MOD-MISS-* |
| AT-11 | calculate uncertainty and verify its source | signals from real passes, methods stated, unavailable != 0 | `POST /api/uncertainty/image` saves a record; entropy 1.0 for uniform / 0.0 for one-hot input; displayed combined score equals the response; thresholds labelled provisional | **PASS** | UNC-001..008, UI-E-005 |
| AT-12 | generate an English report from the analysis | report from structured findings, research-draft banner | generated from the real analysis id; banner "UNCONFIRMED RESEARCH DRAFT"; abstained wording, no "predicted" | **PASS** | UI-E-007, RPT-A01/A02 |
| AT-13 | switch to Hindi and Marathi without changing structured findings | identical ids, FDI, scores, versions, review status; no new inference | all identical (58 report checks); Devanagari rendered; no inference request on switching | **PASS** | UI-E-008, RPT-C01..C09 |
| AT-14 | export the report | HTML / TXT / JSON in each language | 9 API exports well-formed and escaped; browser download of the Marathi HTML | **PASS** | UI-E-009, RPT-D01..D03 |
| AT-15 | reopen the report and verify persistence | same content after reload and in a fresh process | listed after reload; reopened by URL; a second server process returns the reviewed Marathi report and the same list | **PASS** | UI-E-010/011, RPT-G01/G02 |
| AT-16 | verify model registry metadata and evaluation links | version, architecture, sha256, dataset fingerprint, evaluation reports | 4 registered models, sidecar sha256 == file sha256, `eval_status "evaluated on test, val"` and report names; `/api/evaluations/{name}` serves JSON/MD and refuses path-like names | **PASS** | API-010/011, `live_api_tests.json`, model list |
| AT-17 | every visible control works or says why it is unavailable | no silent buttons | final crawl clicked 56 controls with POSTs aborted: none without effect; disabled controls carry a reason. **Not clicked:** Start training, Stop, Promote (state-changing; validated through the API instead). State-changing buttons "Use", "Evaluate", "Re-process dataset" and "Score pool images" were exercised by the first crawl (and the Evaluate defect it exposed was fixed) | **PARTIAL** | `ui_controls_clicked.txt`, UI-B-001, UI-C-001 |
| AT-18 | check logs for errors; inspect the browser console | no unexpected errors | API access log of the final server process (1,650 lines at the time of checking): 1,467 x 200, 97 x 422, 62 x 404, 18 x 400, 4 x 502 (LLM / Label Studio not configured) and 2 x 503 (unavailable / unknown model) - all intended refusals - **no 500 and no traceback**; browser console: only the deliberate 4xx of invalid uploads / refusals; the audit's two earlier page errors were fixed | **PASS** | access log counts, UI-X-001..003 |
| AT-19 | run the available unit and integration tests | all pass | **180 tests OK** | **PASS** | `unit_tests.log` |
| AT-20 | verify no user data, original image or checkpoint was deleted or overwritten | unchanged | all 8 checkpoint files byte-identical (SHA-256); `training_data` 3,606 files / 14,725,611,903 bytes and `validation_data` 51 files / 201,044,945 bytes identical; original reports untouched; 3 original uploads intact. **Regenerated by the audit (disclosed below):** derived manifests, the splits file (same counts) and `leakage_check.*` (same results) | **PASS** (with disclosure) | `data_integrity.json`, `snapshot_before.json` |

**Acceptance totals: 19 PASS, 0 FAIL, 0 BLOCKED, 1 PARTIAL (AT-17).**

## 3. Test totals (all harnesses, final state)

| Harness | PASS | FAIL | BLOCKED |
|---|---:|---:|---:|
| Unit / integration tests | 180 | 0 | 0 |
| Live API (138 checks, including a 32-route GET sweep) | 137 | 1 (cosmetic: health `version: "unknown"`) | 0 |
| Per-model inference and failure scenarios | 27 | 0 | 0 |
| Reports and languages | 58 | 0 | 0 |
| Browser audit | 34 | 0 | 0 |
| Review workflow (browser) | 27 | 0 | 0 |
| Overlay geometry, no-numbering, Windows check | 3 | 0 | 0 |
| **Total** | **466** | **1** | **0** |

Functionality audit (`FUNCTIONALITY_AUDIT.md`): **60 features - 42 PASS, 1 FAIL, 5 BLOCKED, 7 PARTIAL, 5 NOT IMPLEMENTED.** 15 defects were found and fixed during the audit, 7 low-severity items remain open.

## 4. Real checkpoints used (`Data\checkpoints\`; sidecar `.json` next to each file)

| Task | File | Version | Architecture | SHA-256 (first 16) | Epochs | Dataset fingerprint |
|---|---|---|---|---|---:|---|
| detection | `dentex_teeth_detection_v1.pth` | dentex_teeth_detection_v1 | fasterrcnn_resnet50_fpn | `a68ce4884066ad80` | 12 | `7f66d59d9cbad925` |
| segmentation | `dentex_teeth_segmentation_v1.pth` | dentex_teeth_segmentation_v1 | maskrcnn_resnet50_fpn | `dd13568c8de5c2cc` | 8 | `7f66d59d9cbad925` |
| classification | `dentex_findings_classification_v1.pth` | dentex_findings_classification_v1 | resnet50 | `5aa878e1fc9ef097` | 15 | `7f66d59d9cbad925` |
| numbering | `dentex_fdi_numbering_v1.pth` | dentex_fdi_numbering_v1 | fasterrcnn_resnet50_fpn | `83f97b2e1ce44b0c` | 16 | `7f66d59d9cbad925` (registered: `evaluated_on.passed = true`) |

The registry now verifies each file against the sidecar hash (a mismatch is rejected); all four match.

## 5. Actual model metrics and evaluation splits

Stored one-time results from earlier runs in `Data\reports\eval_*` (the test split is locked behind `--final-test` and was not used for model selection; the segmentation and classification test reports were regenerated once after selection to add IoU / Dice and ROC-AUC, with the same checkpoints). Splits are grouped by pixel hash, so the same radiograph never appears in two splits (794 / 113 / 113 / 113 distinct films).

| Model | Validation split | Test split (held out) |
|---|---|---|
| Detection | mAP 0.560, AP50 0.978 (69 images, 2,000 teeth) | mAP **0.515**, AP50 **0.966** (63 images, 1,790 teeth) |
| Segmentation | box mAP 0.569, mask AP50 0.980 | box mAP 0.530, mask AP50 **0.974**, mean mask IoU **0.780**, Dice **0.873** (1,753 matched teeth) |
| Classification (given ground-truth boxes) | accuracy 0.825, macro-F1 0.718 (65 films, 331 crops) | accuracy **0.785**, macro-F1 **0.646**, macro ROC-AUC (one-vs-rest) **0.910** (73 films, 354 crops); weakest class: Periapical Lesion (recall 0.31, n = 13) |
| Numbering | exact accuracy among localised teeth 0.936, coverage 0.979 | exact accuracy **0.968**, coverage **0.969**, strict (all ground-truth teeth) **0.938**, quadrant accuracy 0.999 |
| Uncertainty signals (classifier errors, test) | - | AUROC entropy **0.768**, flip disagreement **0.745**; ECE 0.048 (not recalibrated) |

Reproduction in this audit: the classifier's validation metrics re-run on the CPU gave accuracy 0.822 and macro-F1 0.711 (stored 0.825 / 0.718): the stored numbers are of the right size but **not bit-reproducible across devices**. Detection, segmentation and numbering were not re-evaluated.
Active learning: the original 3-seed study found no consistent benefit of entropy or combined selection over random sampling (macro-F1 at 300 labelled films 0.706 / 0.706 / 0.720); the CPU re-run of one seed showed device-level variation (up to 0.09) larger than those differences.

## 6. Multilingual verification

* **Languages offered and verified: English, Hindi (hi), Marathi (mr)** - the only ones the API/UI advertise; any other code returns 422.
* Verified for hi and mr: identical findings / scores / ids / versions / review status; every decimal of the English narrative present verbatim; abstained regions unchanged; research-draft disclaimer present in the target script; no untranslated English prose; no treatment wording; HTML/TXT/JSON exports; Devanagari rendering in the browser (screenshots `docs/audit_evidence/shots/e2e_report_mr.png`, `shots_phase/phase_report_hi.png`).
* **Not verified:** linguistic quality by a native-speaking dental professional (flag `translation_reviewed_by_native_dental_professional = false` is returned and displayed). Do not present the translations as clinically reviewed.

## 7. Failed and blocked tests

| Item | Status | Detail / recovery |
|---|---|---|
| Health endpoint version string | FAIL (cosmetic) | `GET /api/health` returns `version: "unknown"` because the project runs from source (no installed package metadata) |
| Region-level and viewer controls: Start training, Stop, Promote | not clicked | state-changing; validated by API tests; deliberately not clicked to protect the registry and the GPU |
| Label Studio live import/export | BLOCKED | no Label Studio server/API key; file export and the "not configured" states are verified; recovery: install Label Studio, set `LABEL_STUDIO_URL` and `LABEL_STUDIO_API_KEY` |
| TensorBoard | BLOCKED | `tensorboard` not installed; `Data\runs` has no event files; recovery: `pip install tensorboard` |
| Hindi / Marathi linguistic review | BLOCKED | needs a native-speaking dental professional |
| Live LLM report mode | BLOCKED | not configured (optional); the local template mode needs no key |
| Docker build, `setup.ps1`, `start_all.ps1` | not run | multi-GB image build / package reinstall / opens windows and a browser |
| API-started training against the real trainer | PARTIAL | covered by a CPU CLI smoke test and unit tests; not run against the real registry/GPU |
| Full original AL grid, re-evaluation of detection / segmentation / numbering | not repeated | cost, occupied GPU, locked test split |

## 8. Known limitations

* Research software; **no clinical validation**; outputs are model predictions that may be wrong; reports are unconfirmed research drafts that need qualified professional review.
* The classifier has no healthy class; its top class is a candidate for review, never a diagnosis. Uncertainty scores are ranking signals, not calibrated probabilities; the review thresholds are provisional (one split, one seed) and send about half of the regions to manual review.
* Flip disagreement / mask / detection instability are test-time augmentation of one network, not an ensemble; ensemble disagreement is unavailable.
* One dataset (DENTEX), one split, one training seed per model; performance on other scanners, populations or projections is unknown.
* No authentication or rate limiting: keep the API on `127.0.0.1`. Reviewer and approver names are self-declared.
* Git: the repository root is the whole `D:\` drive and has no commits (see the security audit).

## 9. Startup commands (Windows, PowerShell)

```powershell
cd "D:\Dentex-Gen Ai"
# one-time (already done on this machine): .venv, pip install -r requirements-api.txt, torch cu124 build, cd frontend; npm install
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000     # terminal 1  (API docs: http://127.0.0.1:8000/docs)
cd frontend; npm.cmd run dev                                                           # terminal 2  (UI: http://localhost:5173)
powershell -NoProfile -File scripts\windows\check_running.ps1                           # health check with real requests (exit 0 = all good)
.\.venv\Scripts\python.exe -m unittest discover -s tests                                # 180 unit tests
powershell -NoProfile -File scripts\run_audit_suite.ps1                                 # the full audit suite recorded in TEST_EXECUTION_LOG.md
```
GPU: detected automatically (CUDA); with no GPU the same models run on the CPU (about 7-23 s per prediction and 11-53 s per full analysis on this machine). Stop a `--reload` server with `taskkill /PID <pid> /T /F`.

## 10. Repeatable teacher-demo script (about 12 minutes; every step was exercised in this acceptance)

1. **Start (1 min).** Open two terminals as in section 9 and `check_running.ps1`; open http://localhost:5173. Say: "research prototype, models trained on DENTEX, not a diagnostic tool."
2. **Home (1 min).** Point to dataset definitions ("entries" vs distinct radiographs), the leakage summary (0 overlaps), model list with versions and the GPU panel.
3. **Upload and analyse (2 min).** X-ray Analysis -> *Browse files* -> choose a copy of `Data\validation_data\quadrant_enumeration_disease\xrays\val_12.png` -> *Analyze Image (full pipeline)*. Show the step list (each `ok`), the numbered teeth, segmentation masks, and the region table. Expect about 32 regions in 2-6 s.
4. **Honest classification (1 min).** Click a region marked "no reliable candidate": explain abstention and that the classifier has no healthy class.
5. **Uncertainty (1 min).** *Calculate Uncertainty* -> Uncertainty page: signals, methods, "thresholds provisional", regions needing review.
6. **Explainability (30 s).** Select a region with a candidate class -> *Explain Prediction* -> Grad-CAM with the opacity slider and the method note.
7. **Review (2 min).** Annotations -> review queue -> confirm a candidate with a reviewer name; resubmit (refused as duplicate); change the decision (revision 2, history kept); try to approve as the same person (refused), approve as a second person.
8. **Report (2 min).** X-ray Analysis -> *Generate Draft Report*; switch English -> Hindi -> Marathi and show that ids, FDI numbers and scores stay identical and the research-draft banner remains; export HTML; point out that Hindi/Marathi wording awaits expert review.
9. **Research tools (1 min).** Active Learning (pool scoring, strategies) and Experiments: show the real measured result that uncertainty selection did **not** beat random sampling.
10. **Close (30 s).** Models page: sha256-verified checkpoints and evaluation links; About & Limitations.

Reset between demonstrations: `scripts\audit_cleanup.py --cutoff <time> --apply` removes only records created after the given UTC time (it backs up the database first).

## 11. What the audit changed (disclosure)

* **Code and tests added or changed** (all listed in `FUNCTIONALITY_AUDIT.md`, defects D01-D15): Reports page, Models page, Annotations/Active-learning/viewer controls, evaluate/select/review routes, overlay, report validator, checkpoint integrity check, job-error sanitising, health probes, error codes, split-provenance hash, AL/evaluation reproduction options. 19 regression tests were added (`tests/test_audit_regressions.py`).
* **Side effects of the audit's own first browser crawl** (before the crawler blocked POSTs): it created `Data\checkpoints\active_models.json` (removed afterwards), started four Evaluate jobs that failed on GPU memory (kept in the job history), ran one real pool-scoring job (kept), re-processed the dataset (derived manifests and the splits file were rewritten with unchanged counts), and an accidental `check_leakage.py --help` regenerated the leakage report with identical results.
* **Records created in the app database** (several hundred analyses, about a hundred reports, reviews, exports, AL rounds and the audit's uploads) were removed with a database backup first; the database is back to its pre-audit baseline (3 uploads, 1 AL round, 12 jobs, 50 experiments). The ids are in `docs/audit_evidence/cleanup_log_*.json`.
* No package was installed, upgraded or removed; no dataset file, annotation or checkpoint was deleted or overwritten; nothing was committed to Git; TLS verification was never changed.

## 12. Recommended next improvements

1. Have a native-speaking dental professional review the Hindi and Marathi templates (`src/dentexmodel/reporting/i18n.py`).
2. Add authentication (or keep strictly loopback) before any shared use; replace self-declared reviewer names with accounts.
3. Repeat the active-learning study with a fixed device, more seeds and a paired statistical test before drawing any conclusion; add an ensemble (several seeds per task) so disagreement can be measured.
4. Re-evaluate detection / segmentation / numbering from the stored checkpoints on a separate validation set (other scanners) and report confidence intervals; calibrate the classifier (temperature scaling is computed but not applied).
5. Add a "healthy / no finding" class or a reject option trained on negative teeth so the classifier output can be interpreted as a finding.
6. Initialise Git inside the project folder, commit code only (data, checkpoints and the database are already git-ignored), and add CI running `scripts\run_audit_suite.ps1`.
7. Install TensorBoard and Label Studio and complete their live verification; add PDF export if needed.
8. Fix the cosmetic `version: "unknown"` (read the version from `setup.cfg` or a constant).
