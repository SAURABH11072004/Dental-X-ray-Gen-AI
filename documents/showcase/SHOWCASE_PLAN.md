# DentaMind AI: showcase plan

Prepared 2026-10-15. Everything below was checked on this machine that day, unless marked otherwise.
Companion handout: `documents/DentaMind_AI_Project_Guide.pdf`.

## 1. Start the app (verified commands)

Open **two** PowerShell windows in `D:\Dentex-Gen Ai`.

| Window | Command | Ready when |
|---|---|---|
| 1 - backend | `.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` | `Application startup complete.` |
| 2 - frontend | `cd frontend` then `npm.cmd run dev` | `VITE ... ready` and `Local: http://localhost:5173/` |

Check: open http://127.0.0.1:8000/api/health. It should show `"backend":"ok"`, `"database":"ok"` and `"checkpoints_loaded":4`.

| What | URL |
|---|---|
| App (use this) | **http://localhost:5173/** |
| X-ray Analysis | http://localhost:5173/analysis |
| Reports | http://localhost:5173/reports |
| About & Limitations | http://localhost:5173/about |
| Model Registry | http://localhost:5173/models |
| API health | http://127.0.0.1:8000/api/health |
| API docs (needs the token in `runtime\api_token.txt`; not for the demo) | http://127.0.0.1:8000/docs |

## 2. Verified on 2026-10-15

| Check | Result |
|---|---|
| Frontend responds | 200 |
| Backend health | ok; database ok; 4 checkpoints registered and active; GPU (RTX 3050, 4 GB) available |
| Full analysis in the browser, `val_0` | **27 regions, 4.4 s**; 26 numbered, 26 with masks, 20 flagged for review |
| Same analysis via the API (first call after start, loads models) | all 9 steps ok, 6.8 s |
| Report generation | `RPT-8C9DE6104F` created and displayed (research-draft banner, awaiting review) |
| About & Limitations | all sections and dynamic facts display; leakage check 17/18 passed + 1 named warning |
| Unit tests | **233 / 233 pass** |
| Optional services | Label Studio, TensorBoard and LLM not running; reports use built-in templates (intended) |

## 3. Eight-slide outline (verified numbers only; every metric labelled)

**Slide 1 - DentaMind AI: dental X-ray analysis research prototype**
- Problem: reading a panoramic X-ray (OPG) tooth by tooth is slow; a structured, reviewable draft can help a person focus.
- Banner: *Research use only - not a diagnosis, not clinically validated.*

**Slide 2 - What it does (live demo here)**
- Pipeline: load -> detect teeth -> number (FDI) -> outline -> closest finding per tooth -> uncertainty -> draft report (EN / HI / MR).
- Every output is a draft until a named person reviews it.

**Slide 3 - How it is built**
- React + Vite frontend (:5173) -> FastAPI backend (:8000, token-protected, local only) -> 4 PyTorch models + SQLite.
- Runs fully offline on one laptop GPU (4 GB).

**Slide 4 - Data, done carefully**
- Public DENTEX dataset: 3,653 files -> 2,716 unique radiographs -> 1,133 annotated (the subsets overlap).
- Splits per unique radiograph: 794 train / 113 validation / 113 calibration / 113 test; identical copies never cross splits.
- Leakage audit: 17 of 18 checks pass; 1 warning (3 unlabeled demo files equal test films; never scored).

**Slide 5 - Teeth: detection, outlines, numbers** *(label: validation / historical test)*

| | Validation | Test (historical) |
|---|---|---|
| Detection precision / recall | 0.962 / 0.984 | 0.960 / 0.974 |
| Segmentation mask AP@0.5 | 0.980 | 0.974 |
| Exact FDI number (matched teeth) | 93.6 % | 96.8 % |

**Slide 6 - Findings classifier: honest numbers** *(validation)*

| | True tooth boxes | In the app (detector boxes, end-to-end) |
|---|---|---|
| Accuracy | 0.825 | 0.792 |
| Macro-F1 | 0.718 | 0.634 |
| Deep Caries recall | 0.467 | 0.333 |
| Periapical Lesion recall | 0.778 (7/9) | 0.444 (4/9) |

- Strong for Caries and Impacted; weak for the two rare findings (13 : 1 class imbalance).
- No "healthy" class: every tooth gets its closest finding.

**Slide 7 - What we tried and what we learned** *(validation, 5 seeds each, rules fixed in advance)*
- 6 imbalance methods and threshold tuning: none beat the baseline (0.764 macro-F1, true boxes).
- Box-jitter training: 0.720 vs 0.723 detector-box macro-F1, did not pass.
- Training-recipe study: re-running the production trainer reproduced the deployed model bit for bit. Over 5 seeds both recipes reach about 0.72 detector-box macro-F1. The deployed run is the weakest of five (0.651).
- Lesson: report negative results; one run is not a measurement.

**Slide 8 - Limitations and next steps**
- Limits: rare findings weak; one answer per tooth (8 findings sit on two-finding teeth); no patient IDs; one dataset; test split already used.
- Next: more dentist-labelled Deep Caries / Periapical Lesion; a reliable "no finding" class; a multi-label classifier; an external test set.

## 4. Demo checklist

Before the audience arrives (about 10 min):
- [ ] Laptop on AC power; close other heavy programs (Chrome tabs, games). **Do not run any training or experiment** - the 4 GB GPU must stay free.
- [ ] Start backend and frontend (section 1); open http://127.0.0.1:8000/api/health and confirm `ok` and `checkpoints_loaded: 4`.
- [ ] Open http://localhost:5173/analysis, choose **Test data (unlabeled)** and **val_0**, and press **Analyze X-ray** once as a warm-up
      (the first run loads the models; later runs take about 4-5 s).
- [ ] Open the guide PDF and `documents/showcase/screenshots/` in another window, ready as the fallback.

Live demo (5-7 min):
1. **X-ray Analysis** -> source **Test data (unlabeled)** -> image **val_0** -> **Analyze X-ray**.
2. Point out the legend: teal `14` = tooth number, red `14?` = number needs checking (not disease), grey `R7` = region without a number.
   Tick **Segmentation masks** to show outlines.
3. Read the summary line: "20 of 27 regions are recommended for human review" - the tool shows its doubt.
4. Tick **Candidate classes**: a `~Caries` label means *closest trained class*, not a finding.
5. **Generate report** -> the draft report opens; switch **Language** to Hindi or Marathi; note "Awaiting review".
6. **About & Limitations** -> expand **Training data facts**: unique radiographs, the leakage check, the named warning.
7. (Optional) **Model Registry**: "Internal test split already used" banner, legacy provenance labels.

Images to use / avoid:
- **Use:** `val_0` (verified). Other validation_data images that are not copies of any labelled film are also safe, for example
  `val_10`, `val_11`, `val_12`, `val_15`, `val_16`.
- **Avoid:** files labelled "same film as train-split ..." in the picker (predictions there look better than reality), and
  `val_4`, `val_22`, `val_29` (copies of test films).
- **Do not use "All sources" or "My uploads"** in front of the audience: they include a personal WhatsApp image and a non-dental
  marketing graphic uploaded earlier.

## 5. Fallback plan

| If... | Then |
|---|---|
| Backend does not start | Re-run the window-1 command; if port 8000 is busy, a previous backend is still running - close that window or end its python process, then start again. |
| Frontend does not start | `cd frontend`, `npm.cmd run dev` again; if port 5173 is busy, use the URL Vite prints instead. |
| Analysis fails or is very slow | Press **Analyze again** once. If it still fails, switch to the screenshots below and continue the story. |
| GPU out of memory | Close other GPU programs; restart the backend (frees its GPU memory); analyse again. |
| Nothing works / no laptop | Present from screenshots + the guide PDF. |

Screenshots ready for fallback:
- `documents/showcase/screenshots/` (taken 2026-10-15 on this build):
  `00_image_selected_before_analysis.jpg`, `01_analysis_val0_27_regions.jpg`, `02_report_draft_val0.jpg`,
  `03_about_limitations_data_facts.jpg`.
- `docs/audit_evidence/shots_simplified/` (2026-10-14): `analysis_1440.png`, `home_1440.png`, `report_mr_1440.png` (Marathi report),
  `mobile_analysis_top.png`.
- `docs/audit_evidence/shots/` (2026-10-14): one screenshot per page (`route__*.png`), `e2e_analysis.png`, `e2e_report_mr.png`,
  `overlay_geometry.png`.

Note: screenshots from 2026-10-14 predate the newer Model Registry and About-page additions (test-set banner, provenance labels).

## 6. Remaining issues (none blocking the demo)

- **Scripts calling the API through the frontend proxy from Windows PowerShell 5.1** got `401` on some POST requests. The browser
  works; this only affects command-line scripts. For scripts, call `http://127.0.0.1:8000` directly with the token. Not fixed
  (not startup-blocking, and the browser path was verified).
- First analysis after a backend start takes a few extra seconds (model loading) - do the warm-up.
- Label Studio, TensorBoard and an LLM are not configured; reports come from the built-in template. Say so if asked.
- Hindi / Marathi report wording has not been reviewed by a native-speaking dentist.
- The test run added one analysis of `val_0` and report `RPT-8C9DE6104F` to the app database (useful as a ready example).
- Scientific limits (slide 8) are real and should be stated, not hidden.
