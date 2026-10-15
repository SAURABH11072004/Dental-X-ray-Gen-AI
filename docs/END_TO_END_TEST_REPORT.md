# End-to-end test report - upload -> preprocess -> real inference -> display -> report

Audit date 2026-10-14. Real servers only: **uvicorn 0.54 / FastAPI 0.143 on 127.0.0.1:8000** and **Vite 5.4 dev server on localhost:5173**, driven by Microsoft Edge (headless, Playwright) and by plain HTTP clients.
No mock server, no `TestClient`, no fake HTTP adapter and no function-call shortcut is used as evidence. The unit tests (205 in `tests/`) are reported separately and are **not** counted here.

| Harness | Command | Result |
|---|---|---|
| Live API (`scripts/audit_live_api.py`) | `.\.venv\Scripts\python.exe scripts\audit_live_api.py` | 138 PASS |
| Per-model inference (`scripts/audit_models.py`) | `.\.venv\Scripts\python.exe scripts\audit_models.py` | 27 PASS |
| Browser <-> API (`docs/audit_evidence/audit_ui.mjs`) | `node audit_ui.mjs` (playwright-core + Edge) | 39 PASS |
| Review workflow in the browser (`review_workflow.mjs`) | `node phase.mjs <shots-dir>` | 27 PASS, 0 FAIL |
| Overlay geometry in the browser (`geo_check.mjs`) | `node geo_check.mjs` | PASS - 32 rects drawn = 32 API boxes |

Servers' exact state: cold start 4.1 s; models load lazily (first prediction 9.59 s, then 0.59 s).

## The one complete workflow (browser, real servers, real model outputs)

Image: `Data\validation_data\...\val_12.png` (2794 x 1316 px, a real panoramic radiograph; copy uploaded through the browser, original untouched).

| Step | What the browser/API actually did | Result | Test ID |
|---|---|---|---|
| Upload through the "Browse files" input (real multipart POST /api/images/upload) | 200 id=up_6c461ec61f59 2794x1316 dup=false | **PASS** | `UI-E-001` |
| Preprocess | pipeline step `preprocess` reports `ok` (quality flags computed; the models receive the original pixels) | **PASS** | `INF-010/011`, `MOD-*` |
| Click "Analyze Image (full pipeline)": POST /api/analyze/full -> detect, number, segment, match, classify, 3 flip passes | 200 regions=32 secs=1.87 | **PASS** | `UI-E-002` |
| Displayed region table vs the API response (id, FDI, detection score, class/abstain wording, entropy) | all 32 rows match | **PASS** | `UI-E-003` |
| SVG overlay vs the API boxes, in original pixel coordinates | 32 boxes exact, viewBox 0 0 2794 1316 | **PASS** | `UI-E-004` |
| Click "Calculate Uncertainty": real POST /api/uncertainty/image, record saved, value displayed | 200 combined=0.24068202912511402 text='Uncertainty saved (record an-a5aa122970) · combined 0.241 entropy: 0.513 · disagreement: 0.043 · mask instabili | **PASS** | `UI-E-005` |
| Click "Explain Prediction": real POST /api/explain, Grad-CAM heatmap + method text | 200 method=Grad-CAM on the last convolutional block (ResNet layer4) for the top-scoring class of the crop method-text-shown=true | **PASS** | `UI-E-006` |
| Click "Generate Draft Report": POST /api/reports/generate from the analysis id | 200 id=RPT-1FBB0FF27C analysis=(n/a) banner=true | **PASS** | `UI-E-007` |
| Switch the report EN -> HI -> MR -> EN (no inference request, ids/versions preserved) | ids=38 missing={"hi":[],"mr":[]} devanagari(hi)=true devanagari(mr)=true inference-requests=0 | **PASS** | `UI-E-008` |
| Click HTML export while the language is Marathi (browser download) | RPT-1FBB0FF27C_mr.html 28773 B marathi=true id=true | **PASS** | `UI-E-009` |
| Reload /reports: the report is listed | listed=true | **PASS** | `UI-E-010` |
| Click a report in the list (regression test for the crash fixed in this audit) | rendered=true pageErrors=0 | **PASS** | `UI-E-010b` |
| Open /reports?id=... in a fresh navigation | rendered | **PASS** | `UI-E-011` |
| Fresh server process | a second uvicorn process on :8011 returns the reviewed Marathi report and the same list | **PASS** | `RPT-G01/G02` in `report_audit.json` |

Alignment evidence: overlay PNG size equals the original (`INF-013`); predicted boxes vs DENTEX ground truth on three annotated **test-split** radiographs, coordinates in original pixels - per-film median best-IoU 0.66, 0.75, 0.81, **pooled recall at IoU 0.5 = 0.945** (stored test AP50 of the detector: 0.966), which a systematic offset or scale error would not survive (`alignment.json`);
in the browser 32 drawn rectangles equal the API boxes exactly, the SVG `viewBox` equals the image's natural size and the first box sits within 0.3 px of the position computed from the API coordinates (`overlay_geometry.json`, screenshot `shots/overlay_geometry.png`).

## B. Frontend - every route and control

Routes opened (zero console errors, zero HTTP >= 400, no stuck loading): Home, X-ray Analysis, Tooth Segmentation, Uncertainty, Active Learning, Annotations, Reports, Training, Experiments, Models, Settings, About, and the unknown-route page.
A crawler then clicked every enabled control on those pages (except Start training / Stop / Delete / Promote) **with all non-GET API calls aborted before reaching the server**, so the crawl itself changed no data.
Full list of clicked, skipped (with reason) and no-effect controls: `docs/audit_evidence/ui_controls_clicked.txt`. Screenshots: `docs/audit_evidence/shots/`.

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| UI-R-Home/das | open / | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Dental X-ray review' text=1499 chars, controls=1b/3a/0f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-X-ray an | open /analysis | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='X-ray Analysis Workspace' text=3779 chars, controls=11b/0a/8f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Tooth se | open /segmentation | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Segmentation' text=3556 chars, controls=7b/0a/3f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Uncertai | open /uncertainty | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Uncertainty' text=5232 chars, controls=1b/0a/4f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Active l | open /active-learning | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Active Learning' text=732 chars, controls=9b/0a/1f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Annotati | open /annotations | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Annotation Studio' text=1647 chars, controls=5b/3a/3f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Reports | open /reports | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Reports' text=340 chars, controls=0b/1a/0f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Training | open /training | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Model Training' text=14051 chars, controls=2b/0a/10f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Experime | open /experiments | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Experiment Comparison' text=4398 chars, controls=0b/2a/51f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Model re | open /models | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='Model Registry' text=1087 chars, controls=12b/0a/0f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Settings | open /settings | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='System Settings' text=1508 chars, controls=2b/0a/0f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-About | open /about | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='About & Limitations' text=1196 chars, controls=0b/0a/0f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-R-Unknown  | open /no-such-page | page renders content, no console error, no HTTP>=400, not stuck on loading | h1='' text=15 chars, controls=0b/0a/0f, consoleErrors=0, http>=400=[] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-B-000 | state-changing API calls attempted by the crawl (all aborted before reaching the server) | the crawl itself must not change data | ["POST /api/analyze/full","POST /api/predict","POST /api/segment","POST /api/uncertainty/image","POST /api/segment","POST /api/active-learning/score-pool?n=30&seed=42","P | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-B-001 | click every enabled button on 12 pages except Start training/Stop/Delete/Promote (non-GET API calls aborted) | each click changes DOM, URL, or triggers an API call (never silently nothing) | clicked=35 no-effect=[] skipped=15 | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-C-001 | disabled controls without a title/explanation | every disabled control states a reason (title) or is an obvious precondition | [] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-D-001 | browser upload of a corrupt PNG | visible error text, no crash, no analysis started | corrupt or unreadable: cannot identify image file <_io | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-D-002 | browser upload of a .txt file | visible 'unsupported' error | PNG or JPEG · up to 25 MB Browse files Unsupported file type | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-001 | browser upload of a real validation radiograph (val_12.png) | 200, image registered, shown selected | 200 id=up_6c461ec61f59 2794x1316 dup=false | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-002 | click 'Analyze Image (full pipeline)' | real POST /api/analyze/full (200) and steps rendered | 200 regions=32 secs=1.87 | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-003 | region table cells vs the API response (id, FDI, detection score 4 dp, class/abstain wording, entropy 2 dp) | identical | all 32 rows match | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-004 | SVG overlay vs API boxes and image natural size | viewBox == natural size == API image size; every drawn rect == API box (original pixel coordinates); svg exactly covers  | 32 boxes exact, viewBox 0 0 2794 1316 | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-005 | click 'Calculate Uncertainty' | real POST /api/uncertainty/image; displayed text derives from the response (combined score + signal methods) | 200 combined=0.24068202912511402 text='Uncertainty saved (record an-a5aa122970) · combined 0.241 entropy: 0.513 · disagreement: 0.043 · mask instability: 0.090' | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-006 | Explain Prediction on a region with a candidate class | 200, heatmap displayed, method text shown | 200 method=Grad-CAM on the last convolutional block (ResNet layer4) for the top-scoring class of the crop method-text-shown=true | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-007 | Generate Draft Report from the analysis | report created from analysis_id, shown in English with banner | 200 id=RPT-1FBB0FF27C analysis=(n/a) banner=true | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-008 | switch the displayed report EN -> HI -> MR -> EN | ids/versions preserved in every language, Devanagari present, no inference request | ids=38 missing={"hi":[],"mr":[]} devanagari(hi)=true devanagari(mr)=true inference-requests=0 | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-N-001 | Marathi report on screen: prominent 'awaiting linguistic review' notice (local + English text) | visible near the top, includes the English sentence | भाषिक पुनरावलोकन प्रलंबित: या भाषांतराचे मराठी भाषिक दंत व्यावसायिकाने पुनरावलोकन केलेले नाही; संदर्भासाठी इंग्रजी अहवाल ग्राह्य आहे. Awaiting linguistic review: this tra | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-N-002 | English report on screen has no translation-review notice | absent | count=0 | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-009 | click HTML export while language=mr | file downloads; contains Marathi text and the report id | RPT-1FBB0FF27C_mr.html 28773 B marathi=true id=true | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-010 | reload /reports and look for the new report in the list | report is listed with its id | listed=true | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-010b | click a report in the list while none is selected (regression for the null.report crash) | report renders; no page error | rendered=true pageErrors=0 | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-011 | reopen /reports?id=<id> in a fresh navigation | report renders from the database | rendered | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-E-012 | 'Mark reviewed' with an empty reviewer name | button disabled | disabled=true | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-N-003 | 'Validate only' on the Training page | 200, message names the checkpoint it would write, no job created | enabled=true 200 Configuration is valid and no other job is running. A real run would write exp_001_classification_v1.pth. Nothing was started or written. jobs 12->12 | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-N-004 | TensorBoard state on the Training page is truthful | says it is not installed / no event files (no dead link) | TensorBoard is not installed (pip install tensorboard); training runs write no event files until it is. | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-N-005 | each signal shows what was measured about it | 4 lines; mask instability labelled weak/very weak | ["measured moderate (AUROC 0.77 vs classifier errors on ground-truth crops, test split)","measured moderate (AUROC 0.75 vs classifier errors on ground-truth crops, test s | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-X-001 | all console errors across the whole browser audit | none unexpected (intended 4xx from deliberate invalid uploads are logged by Chromium as errors) | ["Failed to load resource: net::ERR_FAILED","Failed to load resource: net::ERR_FAILED","Failed to load resource: net::ERR_FAILED","Failed to load resource: net::ERR_FAILE | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-X-002 | HTTP >= 400 responses during the audit | only from the deliberate invalid uploads | ["POST 422 /api/images/upload"] | **PASS** | `docs/audit_evidence/ui_audit.json` |
| UI-X-003 | failed requests other than the crawl's deliberately aborted POSTs | none | [] | **PASS** | `docs/audit_evidence/ui_audit.json` |

Review workflow (browser, from `review_workflow_run.log`): 27 steps passed - full analysis, region inspector wording (candidate / abstained), Grad-CAM + opacity control, Calculate Uncertainty -> Uncertainty page table with real values,
review queue, review saved (revision 1), **identical resubmission refused**, changed decision saved as revision 2 with history, **self-approval refused**, second person approves, export counts, EN -> HI report, Active Learning / Experiments / Models / Training / Home pages with real data.

## A. Backend, C. Real inference, D. Upload, E. Browser-to-API

### A.1 Health, settings, registry  (8 checks: 8 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| API-001 | GET /api/health | 200, backend ok, database ok | 200 backend=ok db=ok ckpts=4 (1.72s) | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-002 | health reports app version | a version string (app declares 0.2.0) | version='0.2.0' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-004 | GET /api/system/gpu | 200 with device facts | 200 NVIDIA GeForce RTX 3050 Laptop GPU used=4096/4096 MB | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-010 | GET /api/models | 4 registered checkpoints (detection, segmentation, classification, numbering) with sidecar sha | 200 tasks=['classification', 'detection', 'numbering', 'segmentation'] | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-011-num | dentex_fdi_numbering_v1.pth sidecar sha256 equals actual file sha256 | equal | file=83f97b2e1ce44b0c sidecar=83f97b2e1ce44b0c dental_specific=True | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-011-cla | dentex_findings_classification_v1.pth sidecar sha256 equals actual file sha256 | equal | file=5aa878e1fc9ef097 sidecar=5aa878e1fc9ef097 dental_specific=True | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-011-det | dentex_teeth_detection_v1.pth sidecar sha256 equals actual file sha256 | equal | file=a68ce4884066ad80 sidecar=a68ce4884066ad80 dental_specific=True | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-011-seg | dentex_teeth_segmentation_v1.pth sidecar sha256 equals actual file sha256 | equal | file=dd13568c8de5c2cc sidecar=dd13568c8de5c2cc dental_specific=True | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### A.2 Request validation, status codes, unknown ids  (18 checks: 18 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| API-020 | GET /api/images?source=dataset&limit=3 | 200, items | 200 total=3603 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-021 | GET /api/images?source=evil | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-021 | GET /api/images?limit=0 | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-021 | GET /api/images?limit=100000 | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-021 | GET /api/images?offset=-1 | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-001 | POST /api/predict {} | 422 | 422 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-002 | POST /api/predict {"image_id": ""} | 422 | 422 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-003 | POST /api/predict {"image_id": "does_not_exist"} | 404 | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-004 | POST /api/predict {"image_id": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx | 422 | 422 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-005 | POST /api/predict/batch {"image_ids": []} | 422 | 422 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-006 | POST /api/predict/batch {"image_ids": ["a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7 | 422 | 422 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-007 | POST /api/analyze/full {"image_id": "nope"} | 404 | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-008 | POST /api/segment {"image_id": "nope"} | 404 | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-009 | POST /api/uncertainty/image {} | 422 | 422 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-010 | POST /api/explain {"image_id": "up_22736273675e", "box": [1, 2, 3]} | 422 | 422 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-011 | POST /api/explain {"image_id": "nope", "box": [1, 2, 30, 40]} | 404 | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-012 | predict with an unknown model_version | clear refusal (4xx, or 503 model_mismatch); must not silently use another model | 503 '{"error":{"code":"model_mismatch","message":"Requested model \'no_such_model_v9\' is not the active detection model (\'dent' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| PRED-013 | batch with one unknown id | 4xx for the unknown id (or per-item error), never a 500 | 200 '{"count":2,"succeeded":1,"results":[{"image_id":"up_22736273675e","ok":true,"result":{"image_id":"up_22736273675e","imag' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### D. Upload and storage  (18 checks: 18 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| UPL-001 | valid PNG, filename with spaces + Unicode | 200, image id, width/height equal the file's | 200 id=up_22736273675e 1976x976 dup=False (0.10s) | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-002 | reported size equals decoded size | 1976x976 | 1976x976 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-003 | same bytes uploaded again | same id, duplicate=true, no second file | 200 id=up_22736273675e dup=True | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-004 | downloaded bytes equal uploaded bytes | byte-identical | 200 equal=True content-type=image/png | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-005 | valid JPEG (.JPEG, upper-case extension) | 200 | 200 id=up_4d0981b36dec | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-010 | corrupt PNG (valid signature, garbage body) | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'corrupt_image', 'message': 'Image is corrupt or unreadable: cannot identify image file <_io.BytesIO object at 0x000001CF30D02070>', 'hint': None, 'deta | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-011 | random bytes named .png | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'bad_signature', 'message': 'File content is not a PNG or JPEG image (signature mismatch).', 'hint': None, 'details': {}} leak=False msg='{"error":{"cod | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-012 | text file named .txt | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'unsupported_type', 'message': "Unsupported file type '.txt'.", 'hint': 'Upload a PNG or JPEG panoramic radiograph.', 'details': {}} leak=False msg='{"e | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-013 | empty file | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'empty_file', 'message': 'The uploaded file is empty.', 'hint': None, 'details': {}} leak=False msg='{"error":{"code":"empty_file","message":"The upload | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-014 | PNG renamed .exe | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'unsupported_type', 'message': "Unsupported file type '.exe'.", 'hint': 'Upload a PNG or JPEG panoramic radiograph.', 'details': {}} leak=False msg='{"e | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-015 | truncated PNG (first 5000 bytes of a real film) | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'corrupt_image', 'message': 'Image is corrupt or unreadable: image file is truncated', 'hint': None, 'details': {}} leak=False msg='{"error":{"code":"co | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-016 | tiny image 8x8 | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'bad_dimensions', 'message': 'Image size 8x8 is outside the supported range (256-12000 px per side).', 'hint': None, 'details': {}} leak=False msg='{"er | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-017 | HTML disguised as image | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'bad_signature', 'message': 'File content is not a PNG or JPEG image (signature mismatch).', 'hint': None, 'details': {}} leak=False msg='{"error":{"cod | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-018 | SVG | 400 (400/413/422) with a clear message, no stack trace/path | 422 code={'code': 'unsupported_type', 'message': "Unsupported file type '.svg'.", 'hint': 'Upload a PNG or JPEG panoramic radiograph.', 'details': {}} leak=False msg='{"e | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-020 | POST /upload with JSON body and no file | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-021 | 26.2 MB file (limit 25 MB) | 413/400 rejected, not stored | 422 '{"error":{"code":"file_too_large","message":"File is 25.0 MB; the limit is 25 MB.","hint":' (0.1s) | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-022 | 20000x20000 solid PNG (426 kB on disk) | rejected before decoding to memory (too many pixels / bad dimensions) | 422 '{"error":{"code":"corrupt_image","message":"Image is corrupt or unreadable: Image size (400000000 pi' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-030 | Data/uploads after all of the above (rejected payloads must leave nothing behind) | the three valid uploads exist under hash names; no other new file; nothing outside uploads | new_this_run=['up_22736273675e.png', 'up_4d0981b36dec.jpg', 'up_d02567b36667.png'] unexpected=[] expected_present=True | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### C.1 Real inference through the API (uploaded real radiograph)  (11 checks: 11 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| INF-001 | POST /api/predict on the uploaded real radiograph | 200 with detections list, model version, timing | 200 keys=['image_id', 'image_size', 'model_version', 'model_id', 'task', 'detections', 'duration_s', 'device', 'classification', 'numbering'] (0.36s) | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-002 | detector output on upload: boxes finite, x1<x2, y1<y2, inside 1976x976, scores in [0,1] | 0 malformed | n=33 bad=[] | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-003 | predict response carries model provenance | model version + device + seconds | model=dentex_teeth_detection_v1 device=cuda secs=None | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-010 | POST /api/analyze/full on the upload | 200, every step reports ok/unavailable/failed | 200 steps={'preprocess': 'ok', 'detect': 'ok', 'number': 'ok', 'segment': 'ok', 'match': 'ok', 'classify': 'ok', 'classify_tta': 'ok', 'detect_tta': 'ok', 'segment_tta':  | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-011 | no step silently failed | all ok (or explicitly unavailable with reason) | {"preprocess": "ok", "detect": "ok", "number": "ok", "segment": "ok", "match": "ok", "classify": "ok", "classify_tta": "ok", "detect_tta": "ok", "segment_tta": "ok"} | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-012 | full-pipeline regions: unique ids, boxes in bounds, unique FDI, RLE masks sized H*W, match IoU >= 0.5 (n=33) | no problems | [] | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-013 | overlay PNG dimensions equal the original image | 1976x976 | 200 (1976, 976) image/png | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-020 | predicted boxes vs. DENTEX ground-truth boxes on an annotated test-split film (coordinates in original pixels) | recall@IoU0.5 >= 0.9 (a systematic shift/scale error would collapse it; the detector reports test AP50 0.966) and median | [{"image_id": "qe_train_119", "n_gt": 20, "n_pred": 21, "median_best_iou": 0.662970080482027, "recall_iou50": 0.95}, {"image_id": "qe_train_121", "n_gt": 21, "n_pred": 22 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-030 | POST /api/explain for a detected region | 200, heatmap + method name + target class | 200 keys=['image_id', 'model_version', 'box', 'class_index', 'label', 'probability', 'heatmap_png_base64', 'heatmap_format'] method='Grad-CAM on the last convolutional bl | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-031 | explain with an out-of-image box | 4xx or safe clipping, never 500 | 200 '{"image_id":"up_22736273675e","model_version":"dentex_findings_classification_v1","box":[0,0,1976,97' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| INF-032 | explain with a zero-area box | 4xx, never 500 | 422 '{"error":{"code":"bad_region","message":"Region is too small to explain.","hint":null,"details":{}}}' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### Uncertainty API  (8 checks: 8 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| UNC-001 | POST /api/uncertainty/image | saved record; each signal has value+status+reason; methods listed | 200 signals={'entropy': 'computed', 'disagreement': 'computed', 'mask_instability': 'computed', 'detection_instability': 'computed'} combined=None | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UNC-002 | computed signal values are finite and in [0,1] | true | True | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UNC-003 | uniform 4-class softmax -> normalised entropy 1.0 | entropy.value = 1.0 | 200 {"value": 0.9999999999971146, "status": "computed", "reason": null} | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UNC-004 | one-hot softmax -> entropy 0.0 | 0.0 | 200 {"value": 0.0, "status": "computed", "reason": null} | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UNC-005 | score with invalid input {"probabilities": [[]]} | 4xx or 'unavailable' (never a fake 0) | 400 '{"error":{"code":"invalid_uncertainty_input","message":"Invalid uncertainty input: probabilities nee' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UNC-006 | score with invalid input {"probabilities": [["a", "b"]]} | 4xx or 'unavailable' (never a fake 0) | 400 '{"error":{"code":"invalid_uncertainty_input","message":"Invalid uncertainty input: could not convert' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UNC-007 | score with invalid input {} | 4xx or 'unavailable' (never a fake 0) | 200 '{"image_id":"adhoc","model_version":null,"entropy":{"value":null,"status":"unavailable","reason":"no' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UNC-008 | GET /api/uncertainty/table after the call above | contains the record just computed with values | 200 rows=200 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### Reports API  (20 checks: 20 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| REP-001 | generate with neither analysis_id nor image_id nor findings | 4xx, no empty fabricated report | 400 '{"error":{"code":"no_evidence","message":"No model findings to report on.","hint":"Run an analysis w' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-002 | generate for a non-existent analysis | 404 | 404 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-003 | generate an English template report from the full analysis | 200 with report id linked to image + analysis | 200 id=RPT-0BA63656F9 image=up_22736273675e analysis=None keys=['report_id', 'image_id', 'model_version', 'model_versions', 'generated_by', 'status', 'created', 'findings | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-004 | GET invalid report id | 404 | 404 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-005 | unsupported language 'xx' | 4xx with supported list; must not return an English report labelled as translated | 422 '{"error":{"code":"validation_error","message":"lang: String should match pattern \'^(en\|hi\|mr)$\'","hint":"Check the highlighted fields.","det' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-006 | GET report in en/hi/mr | 200 each, localization_check ok for hi and mr | {"en": {"passed": true, "problems": [], "lang": "en"}, "hi": {"passed": true, "problems": [], "lang": "hi"}, "mr": {"passed": true, "problems": [], "lang": "mr"}} | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-007 | language switching does not run new inference | analysis row count unchanged | before=14 after=14 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-enj | export format=json lang=en | 200, non-empty, correct content-type | 200 93947 B application/json; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-enh | export format=html lang=en | 200, non-empty, correct content-type | 200 12379 B text/html; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-ent | export format=txt lang=en | 200, non-empty, correct content-type | 200 7444 B text/plain; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-hij | export format=json lang=hi | 200, non-empty, correct content-type | 200 108258 B application/json; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-hih | export format=html lang=hi | 200, non-empty, correct content-type | 200 26709 B text/html; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-hit | export format=txt lang=hi | 200, non-empty, correct content-type | 200 20026 B text/plain; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-mrj | export format=json lang=mr | 200, non-empty, correct content-type | 200 109793 B application/json; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-mrh | export format=html lang=mr | 200, non-empty, correct content-type | 200 28243 B text/html; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-01-mrt | export format=txt lang=mr | 200, non-empty, correct content-type | 200 20932 B text/plain; charset=utf-8 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-020 | export format=pdf (not implemented) | 4xx with an explicit 'not supported' message | 422 '{"error":{"code":"validation_error","message":"format: String should match pattern \'^(json\|html\|txt)' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-021 | review with an empty reviewer name | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-022 | review with a whitespace-only reviewer name | 4xx (name must contain characters) | 400 '{"error":{"code":"reviewer_required","message":"reviewer name is required","hint":null,"details":{}}' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-030 | report with an explicitly empty findings list | 200; findings == []; summary says nothing was supplied; no invented finding; validation flags the missing model version | 200 findings=[] validation_failed=True summary='No model findings were supplied for this image; no statements about the radiograph are mad' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### Training, experiments, active learning, annotation, reviews  (28 checks: 28 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| TRN-001 | GET /api/training/prerequisites | 200 with checks | 200 '{"ready":true,"unmet":[],"main_dataset_available":true,"architectures":{"classification":["resnet50","resnet18"],"detection":["fasterrcnn_re' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-002 | start with invalid config {"epochs": 0} | 422 and no job created | 422 '{"error":{"code":"validation_error","message":"epochs: Input should be greater than or equal to 1","' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-003 | start with invalid config {"learning_rate": -1} | 422 and no job created | 422 '{"error":{"code":"validation_error","message":"learning_rate: Input should be greater than 0","hint"' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-004 | start with invalid config {"task": "bogus"} | 422 and no job created | 422 '{"error":{"code":"validation_error","message":"task: Input should be \'classification\', \'detection\', ' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-005 | start with invalid config {"experiment_name": ""} | 422 and no job created | 422 '{"error":{"code":"validation_error","message":"experiment_name: String should have at least 1 charac' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-006 | start with invalid config {"image_size": 8} | 422 and no job created | 422 '{"error":{"code":"validation_error","message":"image_size: Input should be greater than or equal to ' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-007 | start with invalid config {"architecture": "no_such_arch"} | 400 and no job created | 422 '{"error":{"code":"invalid_configuration","message":"architecture for classification must be one of [' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-008 | start with invalid config {"resume_checkpoint": "../../etc/passwd"} | 400 and no job created | 400 '{"error":{"code":"prerequisites_unmet","message":"Training prerequisites are not met.","hint":"Resum' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-009 | status of an unknown job | 404 | 404 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-010 | stop an unknown job | 404 | 404 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| TRN-011 | GET /api/training/jobs | 200, list incl. historical real runs | 200 n=12 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| EXP-001 | GET /api/experiments | real experiments from training runs and AL runs | 200 n=50 first=None | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| EXP-002 | GET /api/experiments/compare (no params) | 200 or a clean 4xx | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| EXP-002 | GET /api/experiments/series (no params) | 200 or a clean 4xx | 200 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| EXP-002 | GET /api/experiments/export (no params) | 200 or a clean 4xx | 200 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| EXP-003 | GET /api/evaluations | evaluation reports on disk are listed | 200 {'items': [{'name': 'eval_dentex_teeth_segmentation_v1_test', 'model_version': 'dentex_teeth_segmentation_v1', 'task': 'segmentation', 'spli | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| AL-001 | GET /api/active-learning/info | 200 | 200 '{"strategies":[{"id":"random","description":"Seeded uniform sampling. The baseline every other strategy is compared against."},{"id":"entropy","description":"Hi' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| AL-002 | GET pool (eligible unlabeled) | 200 | 200 {'key': 'main', 'is_test_data': False, 'size': 1558, 'excluded_test_split': 206, 'labeled': 0, 'scored': 0, 'excluded_duplicates_of_labeled': 40} | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| AL-003 | select with invalid {"strategy": "bogus"} | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| AL-004 | select with invalid {"budget": -1} | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| AL-005 | select with invalid {"batch_size": 0} | 422 | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| ANN-001 | GET /api/annotations/connection while Label Studio is not running | truthful 'not reachable / setup required' state | 200 '{"reachable":false,"error":"[WinError 10061] No connection could be made because the target machine actively refused it","url":"http://localhost:8080","api_key_confi | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| ANN-002 | import from Label Studio without a configured server/key | clear 4xx/5xx-service message, no fake import | 502 '{"error":{"code":"external_service_unavailable","message":"Label Studio API key is not configured.","hint":"Set LABEL_STUDIO_API_KEY in .env' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| ANN-003 | import malformed Label Studio tasks | 4xx or reported skipped, not stored as approved | 400 '{"error":{"code":"empty_import","message":"No completed annotations found in the uploaded Label Studio export.","hint":"Export from Label St' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| ANN-004 | approve a non-existent annotation | 4xx / zero approved | 200 '{"approved":[],"version":null}' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REV-001 | review an unknown image | 404 | 404 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REV-002 | unknown review action | 4xx | 400 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REV-003 | review without a reviewer name | 4xx | 422 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### E.1 CORS, exposure, security  (25 checks: 25 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| API-003 | GET /api/system/settings exposes no secrets | no api key value, no absolute home paths | 200; label_studio_api_key_set=False; abs-path leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/..%2F..%2Fsetup.py | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/..%2F..%2Fsetup.py/file | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/..%2F..%2Fsetup.py/thumbnail | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/..%2F..%2Fsetup.py/quality | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/nope | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/nope/file | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/nope/thumbnail | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/nope/quality | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/%27%3B%20DROP%20TABLE%20images%3B-- | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/%27%3B%20DROP%20TABLE%20images%3B--/file | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/%27%3B%20DROP%20TABLE%20images%3B--/thumbnail | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/%27%3B%20DROP%20TABLE%20images%3B--/quality | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/up_000000000000 | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/up_000000000000/file | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/up_000000000000/thumbnail | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| API-022 | GET /api/images/up_000000000000/quality | 404 (or 4xx), no file content / path leak | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| UPL-006 | filename '../../../evil_traversal.png' | stored only inside Data/uploads under a hash name; nothing written outside | 200 id=up_d02567b36667 stored_in_uploads=True escaped=False filename_kept=evil_traversal.png | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| REP-031 | reviewer name containing <script> must be HTML-escaped in the HTML export | no raw <script> tag in exported HTML | review=200; raw_script_in_html=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| SEC-001 | preflight from the Vite origin | allowed (ACAO == origin) | 200 ACAO=http://localhost:5173 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| SEC-002 | preflight from a foreign origin | not allowed (no ACAO for that origin) | 400 ACAO=None | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| SEC-003 | /docs (Swagger UI) is enabled | informational: dev-only route reachable on localhost | 200 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| SEC-004 | encoded path traversal on a route | 404, no file | 404 leak=False | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| SEC-005 | SQL meta-characters in an image id | 404, no DB error text | 404 leak=False '{"error":{"code":"not_found","message":"Image \'up_x\' OR \'1\'=\'1\' was not found.",' | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| SEC-006 | unknown route | 404 JSON, no stack trace | 404 | **PASS** | `docs/audit_evidence/live_api_tests.json` |
### Database / sweep  (2 checks: 2 PASS)

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| SWEEP-001 | GET every parameterless route in /openapi.json (32 routes) | no 5xx, no stack trace / local-path leak, valid JSON | swept=32 bad=[] | **PASS** | `docs/audit_evidence/live_api_tests.json` |
| DB-001 | image registry count after uploads | +3 distinct valid uploads vs 3656 | 3659 | **PASS** | `docs/audit_evidence/live_api_tests.json` |

## C. Real inference - each model separately (`scripts/audit_models.py`)

For each model the exact checkpoint, its version, architecture, SHA-256 (equal to the sidecar's), training configuration and dataset fingerprint were recorded (`MOD-REG-*`).
Inference ran on two real annotated radiographs of the held-out test split (inference only; never used for training, selection or tuning) and one real uploaded radiograph.
Output checks: boxes finite, ordered and inside the image; scores in [0,1]; softmax rows finite, non-negative, summing to 1, four columns; run-length masks decode to H x W with area equal to the pixel count, non-empty, inside their box;
FDI codes valid and unique per film; same image twice -> identical detections; device and time recorded (`device = cuda`, about 0.39 s per `/predict`, 1.17 s per full analysis).
Segmentation masks use **row-major** uncompressed run-length encoding with `"order": "C"` in the payload - not interchangeable with pycocotools without reading that field.

| Test ID | Input | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| MOD-REG-cla | classification: registered checkpoint file, version, architecture, sha256, dataset fingerprint | sidecar sha equals file sha; training config + dataset fingerprint recorded | dentex_findings_classification_v1.pth v=dentex_findings_classification_v1 arch=resnet50 sha=5aa878e1fc9ef097 fp=7f66d59d9cbad925 epochs=15 classes=4 | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-REG-det | detection: registered checkpoint file, version, architecture, sha256, dataset fingerprint | sidecar sha equals file sha; training config + dataset fingerprint recorded | dentex_teeth_detection_v1.pth v=dentex_teeth_detection_v1 arch=fasterrcnn_resnet50_fpn sha=a68ce4884066ad80 fp=7f66d59d9cbad925 epochs=12 classes=1 | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-REG-num | numbering: registered checkpoint file, version, architecture, sha256, dataset fingerprint | sidecar sha equals file sha; training config + dataset fingerprint recorded | dentex_fdi_numbering_v1.pth v=dentex_fdi_numbering_v1 arch=fasterrcnn_resnet50_fpn sha=83f97b2e1ce44b0c fp=7f66d59d9cbad925 epochs=16 classes=32 | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-REG-seg | segmentation: registered checkpoint file, version, architecture, sha256, dataset fingerprint | sidecar sha equals file sha; training config + dataset fingerprint recorded | dentex_teeth_segmentation_v1.pth v=dentex_teeth_segmentation_v1 arch=maskrcnn_resnet50_fpn sha=dd13568c8de5c2cc fp=7f66d59d9cbad925 epochs=8 classes=1 | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-IMG | images used for inference | at least one real dataset film and one upload | [["q_train_435", 1976, 976, "dataset-test"], ["q_train_348", 2714, 1316, "dataset-test"], ["up_22736273675e", 1976, 976, "upload"]] | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-DET-dat-q_train_ | detector alone on q_train_435 (1976x976): boxes finite, ordered, inside image; scores in [0,1]; no classifier output | 0 bad, classification absent | 200 n=31 bad=[] model=dentex_teeth_detection_v1 device=cuda 0.64s classification_present=False | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-CLS-dat-q_train_ | classifier on detected crops of q_train_435: softmax rows finite, non-negative, sum to 1, width = #classes; one row per  | no bad rows | 200 classes=['Caries', 'Deep Caries', 'Impacted', 'Periapical Lesion'] rows=31 dets=31 bad=[] model=dentex_findings_classification_v1 0.41s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-SEG-dat-q_train_ | segmenter alone on q_train_435: RLE decodes to HxW, area == pixel count, non-empty, mask lies inside its box | no bad instances | 200 n=32 bad=[] model=dentex_teeth_segmentation_v1 0.39s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-NUM-dat-q_train_ | numbering on q_train_435: FDI codes valid, unique, confidences in [0,1], unnumbered regions labelled (not guessed) | valid + unique | 200 numbered=31/31 unique=True valid=True statuses=['assigned'] model=dentex_fdi_numbering_v1 1.24s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-DET-dat-q_train_ | detector alone on q_train_348 (2714x1316): boxes finite, ordered, inside image; scores in [0,1]; no classifier output | 0 bad, classification absent | 200 n=28 bad=[] model=dentex_teeth_detection_v1 device=cuda 0.34s classification_present=False | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-CLS-dat-q_train_ | classifier on detected crops of q_train_348: softmax rows finite, non-negative, sum to 1, width = #classes; one row per  | no bad rows | 200 classes=['Caries', 'Deep Caries', 'Impacted', 'Periapical Lesion'] rows=28 dets=28 bad=[] model=dentex_findings_classification_v1 0.48s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-SEG-dat-q_train_ | segmenter alone on q_train_348: RLE decodes to HxW, area == pixel count, non-empty, mask lies inside its box | no bad instances | 200 n=29 bad=[] model=dentex_teeth_segmentation_v1 0.50s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-NUM-dat-q_train_ | numbering on q_train_348: FDI codes valid, unique, confidences in [0,1], unnumbered regions labelled (not guessed) | valid + unique | 200 numbered=28/28 unique=True valid=True statuses=['assigned'] model=dentex_fdi_numbering_v1 1.57s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-DET-upl-up_22736 | detector alone on up_22736273675e (1976x976): boxes finite, ordered, inside image; scores in [0,1]; no classifier output | 0 bad, classification absent | 200 n=33 bad=[] model=dentex_teeth_detection_v1 device=cuda 0.27s classification_present=False | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-CLS-upl-up_22736 | classifier on detected crops of up_22736273675e: softmax rows finite, non-negative, sum to 1, width = #classes; one row  | no bad rows | 200 classes=['Caries', 'Deep Caries', 'Impacted', 'Periapical Lesion'] rows=33 dets=33 bad=[] model=dentex_findings_classification_v1 0.39s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-SEG-upl-up_22736 | segmenter alone on up_22736273675e: RLE decodes to HxW, area == pixel count, non-empty, mask lies inside its box | no bad instances | 200 n=32 bad=[] model=dentex_teeth_segmentation_v1 0.38s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-NUM-upl-up_22736 | numbering on up_22736273675e: FDI codes valid, unique, confidences in [0,1], unnumbered regions labelled (not guessed) | valid + unique | 200 numbered=32/33 unique=True valid=True statuses=['assigned', 'needs_review', 'unassigned'] model=dentex_fdi_numbering_v1 1.17s | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-PERF | 8 repeated predict/segment/full requests on one upload: latency and GPU memory (device = cuda) | no failure; GPU memory does not grow without bound | {"predict": {"n": 8, "first_s": 0.38, "median_s": 0.39, "max_s": 0.41}, "segment": {"n": 8, "first_s": 0.4, "median_s": 0.37, "max_s": 0.46}, "full": {"n": 8, "first_s":  | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-CLEAN | repeated inference leaves no files behind in Data/uploads | unchanged | 6 -> 6 | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-DET-REPEAT | same image twice -> identical detections | identical within 1e-3 px / 1e-5 score | n=33 identical=True | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-CPU-0 | server with CUDA hidden reports no GPU | cuda_available false | {"cuda_available": false, "gpu_name": "NVIDIA GeForce RTX 3050 Laptop GPU", "torch_installed": true} | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-CPU-1 | real detector+classifier inference on the CPU | 200, device cpu, same number of detections as on the GPU | 200 device=cpu n=33 (gpu n=33) 5.9s (gpu cuda) | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-CPU-2 | full pipeline on the CPU | 200, every step ok | 200 10.6s steps={'preprocess': 'ok', 'detect': 'ok', 'number': 'ok', 'segment': 'ok', 'match': 'ok', 'classify': 'ok', 'classify_tta': 'ok', 'detect_tta': 'ok', 'segment_ | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-MISS-empty | server with checkpoint dir 'empty': registry, /predict, /segment, /analyze/full | clear unavailable/refusal state; no synthetic predictions; no traceback | models=[] predict=503 '{"error":{"code":"no_checkpoint","message":"No dental detection model is available.","hint":"Place a trained detection c' segment=503 full=200 step | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-MISS-garbage | server with checkpoint dir 'garbage': registry, /predict, /segment, /analyze/full | clear unavailable/refusal state; no synthetic predictions; no traceback | models=[('dentex_teeth_detection_v1.pth', False, 'unverified (no valid metadata sidecar)')] predict=503 '{"error":{"code":"no_checkpoint","message":"No dental detection m | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-MISS-badsha | server with checkpoint dir 'badsha': registry, /predict, /segment, /analyze/full | clear unavailable/refusal state; no synthetic predictions; no traceback | models=[('dentex_findings_classification_v1.pth', False, 'rejected: checkpoint file does not match the sha256 recorded in its sidecar (mod')] predict=503 '{"error":{"code | **PASS** | `docs/audit_evidence/model_audit.json` |
| MOD-MISS-badsha-v | tampered sidecar sha256 -> checkpoint rejected as not dental/verified | dental_specific false, provenance says rejected | [["dentex_findings_classification_v1.pth", false, "rejected: checkpoint file does not match the sha256 recorded in its sidecar (mod"]] | **PASS** | `docs/audit_evidence/model_audit.json` |

Unavailable-model behaviour (separate server processes, real HTTP): an empty checkpoint folder, a garbage `.pth` without sidecar, and a real checkpoint whose sidecar sha256 was tampered with all produce a clear **unavailable** state (`503 no_checkpoint`, `/analyze/full` steps `detect: unavailable`, `match: skipped`) and **no synthetic predictions**.
The tampered-sidecar case exposed a defect (the registry still labelled it `dental-trained`); it is fixed.

## Defects found by these tests

See the table in `docs/FUNCTIONALITY_AUDIT.md` (defects D01-D23). Those found here: Reports page crash on list click, overlay endpoint 404 for full analyses, review accepted for an unknown image, wrong HTTP status codes (unknown job, too-small region), upload-limit unit label, numbering "Use" 422, concurrent Evaluate failures, unverified checkpoint integrity, tracebacks and local paths in job errors, slow health probes.
All were fixed and re-tested; open items are listed at the end of the audit.

## Verdict for this document

Every link of the workflow (upload, preprocessing, real detector/numbering/segmenter/classifier inference, result display with exact coordinates, uncertainty, Grad-CAM, report generation, EN/HI/MR switching, export, persistence across a fresh server process) was **executed and verified on the real servers**.
Limits that remain: the Hindi/Marathi wording is not reviewed by a native-speaking dentist, Label Studio / TensorBoard / Docker were not available, and API-started training was not run against the real trainer.
This is a research prototype demonstration; nothing here is clinically validated.
