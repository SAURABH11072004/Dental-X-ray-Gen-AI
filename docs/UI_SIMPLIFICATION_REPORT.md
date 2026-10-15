# UI simplification report

Date 2026-10-14. Scope: turn the research dashboard into an end-user dental X-ray review application **without deleting any research feature, backend route, model, annotation or evidence**.
Everything below was verified in a real browser (headless Edge) against the real FastAPI backend (token authentication and rate limiting active) and the real Vite dev server, using real checkpoints and a real radiograph (`val_12.png`, 2794 x 1316 px).

## 1. What changed

| Area | Before | After |
|---|---|---|
| Sidebar | Home, X-ray Analysis, Tooth Segmentation, Reports + a collapsible research group | **Home, X-ray Analysis, Reports, Review Findings** and, in the footer, **About & Limitations, Settings** |
| Research / developer pages | collapsible group in the sidebar | **Hidden by default.** Settings -> "Show Research / Developer Tools" reveals a labelled section with Tooth Segmentation, Uncertainty, Active Learning, Annotations, Model Training, Experiments, Model Registry. Every page and route still works by URL and shows a "Research / Developer Tool" banner. The switch is a browser-side display preference; it is **not** a login (the API token protects the server). |
| Review Findings | part of the Annotations page | new route `/review` that reuses the existing region-review component (queue, decisions with history, second-person approval). "Review this region" in the inspector opens it for that image. |
| X-ray Analysis | five or six buttons incl. Run Detection / Run Segmentation / Calculate Uncertainty / Explain / Generate Draft Report | one primary **Analyze X-ray** (the full pipeline, which already computes uncertainty). Left: upload / selector / dimensions / file size / quality / layer toggles. Centre: large viewer (zoom, fit, reset), legend, loading overlay, review summary. Below: region list and region details. After an analysis the button becomes "Analysis ready" with an explicit "Analyze again" (no duplicate inference). |
| Overlay labels | `#14` for tooth numbers, `det 7` otherwise | **`14`** = tooth number assigned by the numbering model; **`14?`** = proposed, needs checking (red); **`R7`** = *Region 7*, no tooth number (grey; 7 is only the detection order). A legend explains it. Labels are placed without overlapping; a label that cannot be placed is omitted and the box stays clickable and listed. |
| Classification wording | "Detected class", "Closest trained finding" | **Candidate class / Closest trained class**, raw score labelled "raw model score", a short statement that the classifier has no healthy class and that a class is not evidence the finding is present. No healthy or normal result is shown anywhere. |
| Uncertainty | separate Uncertainty page plus a Calculate button | shown inside X-ray Analysis automatically: combined value, entropy, flip disagreement, mask and detection instability, image-quality warnings kept separate, a review recommendation ("N of M regions are recommended for human review"), the sentence "Uncertainty indicates model doubt, not a confirmed error...", and the **measured reliability** of each signal (entropy and flip: moderate; mask: very weak; detection: weak). Detailed distributions stay in the research page. |
| Reports | language held in local state | default language preference (Settings); list, preview, EN/HI/MR, HTML/TXT/JSON export, reviewer-name field with explicit "Mark reviewed" (disabled until a name is typed), persistent status. Hindi/Marathi carry the prominent "awaiting linguistic review" notice. **No PDF or edit controls are shown** (not implemented). |
| Home | experiments, models/GPU, dataset statistics, leakage, several overlapping cards | **Upload X-ray** button, readiness indicator, recent analyses, latest report, findings awaiting review, model availability (4 tasks). Dataset facts moved to a collapsed "Training data facts" section on About (files vs unique radiographs, annotated vs unlabeled). |
| Model status | version strings and a GPU line | availability only (**Available / Unavailable**) for detection, segmentation, classification and numbering, **derived from `/api/models`** (verified checkpoints), with the backend's reason when a file is rejected. Architectures, paths and metrics stay in the Model Registry. |
| About & Limitations | generic text | what it can do, models available now, limits (no healthy class, scores are not probabilities, uncertainty is doubt, limited data, unreviewed Hindi/Marathi, unverified reviewer names). |
| Settings | diagnostics only | display preferences (default report language, overlay options, research-tools switch) above the existing read-only diagnostics. |
| Backend (small) | - | `size_bytes` added to the image record so the file size is shown (uploads and dataset images). |

Frontend files touched: `components/{Sidebar,Topbar,DetectionOverlay,PredictionInspector,ModelStatusPanel,ResearchBanner,DatasetInfo,UncertaintyScoreCard,ImageUploader,RegionReview}.jsx`, `pages/{Analysis,Overview,About,Settings,Reports,ReviewFindings,Uncertainty}.jsx`, `lib/{prefs,fullAnalysis}.js`, `App.jsx`; backend: `backend/services/images.py`. Nothing was removed from `pages/` or the API.

## 2. Verification (real browser, real servers)

Run: `node docs/audit_evidence/ui_simplified.mjs` (new, end-user flow) and `node docs/audit_evidence/audit_ui.mjs` (existing full audit, updated to the new controls). Screenshots: `docs/audit_evidence/shots_simplified/`.

| Harness | PASS | FAIL | BLOCKED |
|---|---:|---:|---:|
| `ui_simplified.mjs` (navigation, Home, analysis, labels, selection, inspector, uncertainty, report, languages, exports, review, responsive, keyboard) | 86 | 0 | 0 |
| `audit_ui.mjs` (all 13 routes incl. research pages, every control crawled with POSTs aborted, upload errors, overlay geometry, report persistence) | 37 | 0 | 0 |
| `review_workflow.mjs` (review, duplicate refusal, self-approval refusal, approval, export, EN->HI report, other pages) | 26 | 0 | 0 |
| `geo_check.mjs` (32 drawn rects == 32 API boxes, viewBox == image size, screen offset under 0.3 px) | 1 | 0 | 0 |
| Unit / integration tests | 205 | 0 | 0 |

### Detailed results of `ui_simplified.mjs`

| ID | Input | Expected | Actual | Result |
|---|---|---|---|---|
| S-NAV-1 | default sidebar links | ["Home","X-ray Analysis","Reports","Review Findings","About & Limitations","Settings"] | ["Home","X-ray Analysis","Reports","Review Findings","About & Limitations","Settings"] | **PASS** |
| S-NAV-2 | research links absent by default | none of 7 research labels in the sidebar | none | **PASS** |
| S-NAV-3 | hidden page still reachable by URL: /uncertainty | renders with the Research / Developer Tool banner | h1='Uncertainty' banner=1 | **PASS** |
| S-NAV-3 | hidden page still reachable by URL: /active-learning | renders with the Research / Developer Tool banner | h1='Active Learning' banner=1 | **PASS** |
| S-NAV-3 | hidden page still reachable by URL: /annotations | renders with the Research / Developer Tool banner | h1='Annotation Studio' banner=1 | **PASS** |
| S-NAV-3 | hidden page still reachable by URL: /training | renders with the Research / Developer Tool banner | h1='Model Training' banner=1 | **PASS** |
| S-NAV-3 | hidden page still reachable by URL: /experiments | renders with the Research / Developer Tool banner | h1='Experiment Comparison' banner=1 | **PASS** |
| S-NAV-3 | hidden page still reachable by URL: /models | renders with the Research / Developer Tool banner | h1='Model Registry' banner=1 | **PASS** |
| S-NAV-3 | hidden page still reachable by URL: /segmentation | renders with the Research / Developer Tool banner | h1='Segmentation' banner=1 | **PASS** |
| S-NAV-4 | Settings -> Show Research / Developer Tools | 7 research links appear under a clearly labelled heading | RESEARCH / DEVELOPER TOOLS Tooth Segmentation Uncertainty Active Learning Annotations Model Training Experiments Model Registry | **PASS** |
| S-NAV-5 | preference persists after reload | research nav still visible | count=1 | **PASS** |
| S-NAV-6 | switch it off again | hidden | count=0 | **PASS** |
| S-HOME-1 | Home shows upload CTA, readiness, recent analyses, latest report, pending reviews, models | all present; no charts / experiments / dataset cards | cta=1 readiness=1 | **PASS** |
| S-HOME-2 | model availability equals the backend registry | [["detection",true],["segmentation",true],["classification",true],["numbering",true]] | [["detection",true],["segmentation",true],["classification",true],["numbering",true]] | **PASS** |
| S-HOME-3 | no architecture names or checkpoint paths on Home | none | none | **PASS** |
| S-HOME-4 | Upload X-ray button | goes to /analysis | http://localhost:5173/analysis | **PASS** |
| S-AN-1 | upload shows dimensions, file size and quality | 2794 x 1316 px, file size in MB, quality line | Image val_12.png Dimensions 2794 × 1316 px File size 2.8 MB Image quality no warnings | **PASS** |
| S-AN-2 | primary button label | 'Analyze X-ray' | Analyze X-ray | **PASS** |
| S-AN-3 | one click runs the whole pipeline | one POST /api/analyze/full, 200, steps ok | 200 calls=1 regions=32 | **PASS** |
| S-AN-4 | overlay label text vs API numbering status | assigned -> '14', unconfirmed -> '14?', none -> 'R7'; never a bare region index as a tooth number | shown=27 omitted=5 tooth=26 proposed=1 regionOnly=5 mismatches=[] | **PASS** |
| S-AN-5 | rendered labels overlap each other | 0 overlapping label pairs | labels=27 overlapping pairs=0 | **PASS** |
| S-AN-6 | legend explains the labels | legend present with tooth / proposed / region / selected | 14 tooth number from the numbering model 14? proposed number, needs checking R7 region without a tooth number (R = region, 7 = detection ord | **PASS** |
| S-AN-7 | click a box -> same region highlighted in the list and the inspector | row, inspector title and box all refer to region 4 | row='47' title='Region 4 (tooth 47)' | **PASS** |
| S-AN-8 | click a list row -> the box turns amber and the inspector follows | region 8, stroke #A75B04 (selected amber) | title='Region 8 (tooth 45)' stroke=#A75B04 | **PASS** |
| S-AN-9 | inspector shows tooth number, raw scores, candidate-class wording, uncertainty, review links | all parts present | all present | **PASS** |
| S-AN-10 | tooth number in the inspector equals the API (or 'Unassigned') | 45 | 45 | **PASS** |
| S-AN-11 | no diagnosis wording: classes are 'candidate' / 'closest trained class' | no 'diagnos(ed\|is)' claims, no 'healthy' result, 'not evidence' disclaimer present | disease-claim=false healthy-result=false | **PASS** |
| S-AN-12 | uncertainty inside X-ray Analysis: explanation, 4 signals with measured reliability, review recommendation | short explanation + 4 sigval lines (mask/detection 'weak') + 'recommended for human review' | Uncertainty indicates model doubt, not a confirmed error. Th \| sigval=4 weak=2 \| rec=true | **PASS** |
| S-AN-TBL | findings table columns and help note | Region, Tooth number, Candidate class, Score, Review status, Action + an explanatory note | ["Region","Tooth number","Candidate class","Score","Review status","Action"] help=1 | **PASS** |
| S-AN-UNC | metric definitions and AUROC values sit in a collapsed 'How uncertainty is calculated' | details closed by default, definitions present inside | {"open":false,"len":1580} | **PASS** |
| S-AN-NODUP | no developer-style duplicate actions in the end-user workspace | 0 | 0 | **PASS** |
| S-AN-13 | returning to the page keeps the valid analysis; no duplicate inference | 'Analysis ready', analyze calls still 1 | ready=1 calls=1 | **PASS** |
| S-AN-14 | attention heatmap for a region with a candidate class | 200 and heatmap image drawn | 200 images=31 | **PASS** |
| S-MOB-1 | phone (390px) after an analysis: viewer position | viewer card starts within the first screen (top < 600px) and is at least 340px wide; upload section  | {"viewerTop":482,"viewerWidth":366,"zoom":[36,36,36,36],"outside":0,"sw":390,"iw":390,"uploaderOpen":false} | **PASS** |
| S-MOB-2 | touch targets and horizontal overflow at 390px | zoom buttons >= 36px; no control outside the viewport; no horizontal page scroll | zoom=36,36,36,36 outside=0 scrollWidth=390 | **PASS** |
| S-MOB-3 | tap a region box on the phone | region details panel scrolls into view and names the region | {"top":76,"h":1237,"vh":844,"title":"Region 6 (no tooth number)"} | **PASS** |
| S-STALE-1 | choose a different image after an analysis | no boxes, no region list, no 'Analysis ready', 'Analyze X-ray' offered again, and NO automatic infer | {"boxes":0,"table":0,"analyze":1,"ready":0,"calls":0} | **PASS** |
| S-STALE-2 | go back to the first image | its analysis is not shown from the other image (stale data never reused for a different id) | boxes=0 | **PASS** |
| S-ERR-1 | analysis request answered 503 (model missing; simulated at the network layer) | clear 'required model is not available' message with the backend hint; no crash; no invented result | A required model is not available No dental detection model is available. Place a trained detection checkpoint. | **PASS** |
| S-ERR-2 | analysis request answered 500 (simulated) | error text shown, button usable again | true enabled=true | **PASS** |
| S-STALE-3 | re-run after the simulated errors | exactly one real request, results back | calls=1 | **PASS** |
| S-REP-1 | Generate report from the analysis | 200, report opens in English with status 'Awaiting review', ONE neutral safety note, limitations | 200 RPT-971B4DE415 | **PASS** |
| S-REP-CLEAN | report body is clean: no big 'UNCONFIRMED RESEARCH DRAFT' banner, no 'Generated by: template' line, one safety | banner text absent from the visible page, 1 safety note, details closed, sections in the required or | banner=false generatedBy=false notes=1 techOpen=false h3=["Summary","Findings","Regions requiring manual review","Limitations · uncertainty" | **PASS** |
| S-REP-TECH | technical details (ids, model versions, generator) are kept, inside the collapsed section | contains report id, model versions, 'template' | Technical detailsReport idRPT-971B4DE415Image idup_6c461ec61f59Modelsdetection: dentex_teeth_detection_v1 · segmentation: dentex_teeth_segme | **PASS** |
| S-REP-LIST | report list rows are compact: id, image name, date, status, Open; no draft banner / generator / disclaimer tex | row has id, an image name, a date, 'Awaiting review', an Open button, and none of the removed string | {"t":"RPT-971B4DE415 Awaiting review val_12.png 14/10/2026, 11:00:31 pm EN · HI · MR Open (viewing)","open":true} | **PASS** |
| S-REP-2 | saved reports list shows the new report | listed | true | **PASS** |
| S-REP-3 | language options are exactly the supported ones | English, हिन्दी, मराठी | ["English","हिन्दी — translation awaiting review","मराठी — translation awaiting review"] | **PASS** |
| S-REP-4 | EN -> HI -> MR -> EN: structured ids/versions kept, no inference, review label only on hi/mr | ids present in all, 0 inference requests, ling notice hi=1 mr=1 en=0 | ids=66 missing(hi)=0 missing(mr)=0 infer=0 ling hi/mr/en=1/1/0 | **PASS** |
| S-REP-5 | every export control shown works; no PDF / edit control is shown | HTML, TXT, JSON each 200 non-empty; 0 PDF/edit controls | HTML:200:28773 TXT:200:21603 JSON:200:108629 pdf/edit=0 | **PASS** |
| S-REP-6 | browser download of the Marathi HTML export | contains report id, Marathi text and the review-pending notice | download=true ok=true | **PASS** |
| S-REP-7 | 'Mark reviewed' needs a reviewer name | disabled until a name is typed | disabled=true | **PASS** |
| S-REP-8 | review action persists | status reviewed_research_draft, reviewer name stored, still not 'validated' | reviewed_research_draft by UI Test Reviewer | **PASS** |
| S-REV-1 | Review Findings page lists regions needing review and explains why | queue shown with reasons; reviewer names are not verified | Review Findings Regions that need a person to look at them: uncertain candidate classes, tooth numbers that are unassigned or unconfirmed, a | **PASS** |
| S-REV-2 | 'Review this region' link (href captured from the inspector) opens that image's review task | /review?image=<id> with the image's regions drawn in the review panel | /review?image=up_6c461ec61f59 boxes=32 | **PASS** |
| S-RSP-desktop | / at 1440px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1440 innerWidth=1440 sidebar=true selector=false | **PASS** |
| S-RSP-desktop | /analysis at 1440px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1440 innerWidth=1440 sidebar=true selector=false | **PASS** |
| S-RSP-desktop | /reports at 1440px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1440 innerWidth=1440 sidebar=true selector=false | **PASS** |
| S-RSP-desktop | /review at 1440px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1440 innerWidth=1440 sidebar=true selector=false | **PASS** |
| S-RSP-desktop | /about at 1440px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1440 innerWidth=1440 sidebar=true selector=false | **PASS** |
| S-RSP-desktop | /settings at 1440px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1440 innerWidth=1440 sidebar=true selector=false | **PASS** |
| S-RSP-tablet | / at 1024px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1024 innerWidth=1024 sidebar=true selector=false | **PASS** |
| S-RSP-tablet | /analysis at 1024px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1024 innerWidth=1024 sidebar=true selector=false | **PASS** |
| S-RSP-tablet | /reports at 1024px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1024 innerWidth=1024 sidebar=true selector=false | **PASS** |
| S-RSP-tablet | /review at 1024px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1024 innerWidth=1024 sidebar=true selector=false | **PASS** |
| S-RSP-tablet | /about at 1024px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1024 innerWidth=1024 sidebar=true selector=false | **PASS** |
| S-RSP-tablet | /settings at 1024px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=1024 innerWidth=1024 sidebar=true selector=false | **PASS** |
| S-RSP-view-tablet | viewer card size at 1024px | viewer at least 300px wide | [420,566] | **PASS** |
| S-RSP-tablet-portrait | / at 768px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=768 innerWidth=768 sidebar=false selector=true | **PASS** |
| S-RSP-tablet-portrait | /analysis at 768px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=768 innerWidth=768 sidebar=false selector=true | **PASS** |
| S-RSP-tablet-portrait | /reports at 768px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=768 innerWidth=768 sidebar=false selector=true | **PASS** |
| S-RSP-tablet-portrait | /review at 768px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=768 innerWidth=768 sidebar=false selector=true | **PASS** |
| S-RSP-tablet-portrait | /about at 768px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=768 innerWidth=768 sidebar=false selector=true | **PASS** |
| S-RSP-tablet-portrait | /settings at 768px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=768 innerWidth=768 sidebar=false selector=true | **PASS** |
| S-RSP-view-tablet-portrait | viewer card size at 768px | viewer at least 300px wide | [720,566] | **PASS** |
| S-RSP-phone | / at 390px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=390 innerWidth=390 sidebar=false selector=true | **PASS** |
| S-RSP-phone | /analysis at 390px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=390 innerWidth=390 sidebar=false selector=true | **PASS** |
| S-RSP-phone | /reports at 390px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=390 innerWidth=390 sidebar=false selector=true | **PASS** |
| S-RSP-phone | /review at 390px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=390 innerWidth=390 sidebar=false selector=true | **PASS** |
| S-RSP-phone | /about at 390px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=390 innerWidth=390 sidebar=false selector=true | **PASS** |
| S-RSP-phone | /settings at 390px | no horizontal page scroll; sidebar at >=1024, page selector below | scrollWidth=390 innerWidth=390 sidebar=false selector=true | **PASS** |
| S-RSP-view-phone | viewer card size at 390px | viewer at least 300px wide | [366,566] | **PASS** |
| S-A11Y-1 | Tab reaches the sidebar links and shows a visible focus ring | ring present | {"tag":"A","text":"Home","ring":true} | **PASS** |
| S-A11Y-2 | interactive controls on X-ray Analysis have an accessible name | 0 unlabeled | unlabeled=0 | **PASS** |
| S-A11Y-3 | WCAG AA colour contrast of all visible text (contrast.mjs, 15 page states incl. research pages) | 0 failing text/background combinations; measurement fresh (< 45 min) | failing=0 end-user=0 age=4min | **PASS** |
| S-CON-1 | browser console errors during the whole run | none except intended 4xx | ["Failed to load resource: the server responded with a status of 503 (Service Unavailable)","Failed to load resource: the server responded w | **PASS** |
| S-CON-2 | HTTP >= 400 responses during the run (excluding the two simulated failures of S-ERR-1/2) | none | [] | **PASS** |

## 3. Defects found while building this

* **Overlay labels could be mistaken for tooth numbers**: an unnumbered region was labelled by its detection index. Now it is `R<n>` with a legend, and an unconfirmed number is `14?`.
* **Three "Show on image" checkboxes were disabled without a reason** before an analysis (found by the crawl): they now say "Available after an analysis".
* **Duplicate image details** (uploader and page card) were removed.
* My test scripts initially mis-stated several expectations (text that CSS upper-cases, a selector that also matched label rectangles, full page reloads where in-app navigation was meant); they were corrected and are not application defects.

## 4. Not verified / remaining issues (stated plainly)

* **Colour contrast** is now measured for visible text only (WCAG AA on computed colours, 15 page states). Not covered: non-text contrast (borders, icons, focus rings), hover/pressed/error states, text drawn inside the SVG overlay (those label colours were chosen by calculation: white on #0D7D7F 4.9:1, on #C44343 5.0:1, on #A75B04 5.1:1, on #64748B 4.8:1), and Hindi/Marathi screen-reader behaviour.
* **Phone**: the viewer now follows the image controls and the upload section collapses once an image is chosen, but a 2794 px panorama on a 390 px screen is shown at about 12% so some labels are omitted (by design, to avoid overlap); use the zoom buttons, which are 36 px touch targets. Pinch-zoom gestures were not tested.
* **No frontend unit tests exist** in this project; verification is the browser audits above.
* **De-duplication of inference is in memory**: switching pages keeps a valid analysis and does not call the models again, but a full browser reload forgets it (the backend still stores every analysis).
* **Single-model buttons** (Run Detection, Run Segmentation, standalone uncertainty) were removed from the end-user workspace because the full pipeline covers them; segmentation alone remains on the hidden Tooth Segmentation research page and all API routes are unchanged.
* **Research tools are hidden, not protected**: anyone using this browser can switch them on; the API token protects the server, not individual pages. No role system exists.
* The Hindi and Marathi wording is still awaiting review by a native-speaking dental professional. Reviewer names are typed text and not verified.

## 5. Final polish pass (verification and polish round)

**Accessibility failure.** The previous report listed colour contrast as BLOCKED because no contrast measurement existed; no check had actually failed. A real measurement (`contrast.mjs`: WCAG 2.x ratio of every visible text element against its effective background, 15 page states including the research pages) found **15 failing text/background combinations (10 on end-user pages)**, all caused by the colour tokens: teal text and teal buttons (4.1:1), warning amber (3.0-3.2:1), error red (3.7-4.1:1), success green (4.3:1), muted grey (4.4:1), a greyed "disabled-looking" label (2.6:1) and chart legend colours. Fix: the same colour family, darkened just enough: teal #0F8B8D -> #0D7D7F, warn #D97706 -> #A75B04, error #DC4C4C -> #C44343, ok #16856B -> #158067, muted #64748B -> #617187 (navy, white and light-grey backgrounds unchanged). Result of the re-measurement: **0 failing combinations on all 15 page states** (`docs/audit_evidence/contrast.json`), and the browser check S-A11Y-3 reads that file and passes.

**Mobile workspace.** Below 1024 px the order is now: image controls (Analyze button first, image facts), then the **viewer**, then the layer toggles, then region details/list; the upload and image selector collapse behind "Change image" once an image is chosen; zoom buttons are 36 px touch targets; tapping a region box scrolls the region details into view (shown above the list). On desktop the layout is unchanged.

**End-user journey on the real backend** (all in `ui_simplified.mjs`): upload; one-click analysis (exactly one request); labels vs the API; region selection from box and from list; candidate class and uncertainty; report generation; EN/HI/MR switching without inference; HTML/TXT/JSON export (status 200 each) and a browser download; reopening the saved report; reviewer sign-off persisted in the database; review workflow; plus **stale results** (choosing another image clears boxes, list and "Analysis ready" and triggers no automatic request), **duplicate requests** (counted: one per click), and **API errors** (a simulated 503 "model missing" shows the backend's message and hint, a simulated 500 shows the error and leaves the button usable; no invented result in either case). The two simulated failures are excluded from the console/HTTP error check, and nothing else logged an error.

**Intermittent failure observed once, not reproduced:** one earlier full-audit run recorded a single `net::ERR_CONNECTION_REFUSED` for the health poll (browser to the Vite dev server; the backend process had not restarted and its log shows no error). The same audit passed 37 of 37 on the immediate re-run and in the final run. Cause not identified.

## 6. Refinement round: reports, review, Home and Analysis details

**Reports (`pages/Reports.jsx`, `components/ReportPreview.jsx`, `lib/reportStatus.js`).** The report list is now compact: each saved report is a small card with its id, the **image file name** (new `image_name` field on `GET /api/reports`, display only), date, review status ("Awaiting review" / "Reviewed"), "EN - HI - MR" availability and an **Open** button; 8 rows per page with "Show more", a scroll container, and an empty state. The large amber banner with "UNCONFIRMED RESEARCH DRAFT" and "Generated by: template" was **removed from the component** (not hidden with CSS); the page shows one neutral safety note, "Research output - not a confirmed diagnosis. Requires qualified professional review." (Hindi/Marathi show the report's own translated disclaimer), plus the status chip. The body follows the requested order: heading and status, image and date, summary, findings table, areas requiring human review, uncertainty and limitations, review (who, when, typed-name caveat), then "Record a review" and "Export". Report id, model versions, generator, finding descriptions, localisation check and validation sit in a collapsed **Technical details** section. Findings, tooth numbers, scores, uncertainty, limitations and the Hindi/Marathi "awaiting linguistic review" notice are unchanged. Language options are labelled "translation awaiting review"; "Mark reviewed" stays disabled until a name of at least two characters is typed (reason shown as text, not only a tooltip). Exported HTML/TXT/JSON are unchanged and keep the full disclaimer and limitations.

**X-ray Analysis.** Findings table columns are now Region, Tooth number, Candidate class, Score, Review status (Needs review / No flag, plus Low confidence), Action (Details), with a visible help note explaining `R7`, `(check)`, Low confidence and Score. Uncertainty shows the overall value and the four signals compactly; definitions, measured reliability (AUROC), weights and thresholds moved into a collapsed "How uncertainty is calculated". Overlay labels are clamped inside the image bounds.

**Review Findings.** Queue items show Pending / "n saved" / "n approved"; the save button is guarded against double clicks (one submission) and shows a visible reason while disabled; the success message says the review is saved and waits for a second named person; "Region 7" replaces "Region #7".

**Home.** Header text and layout as requested; the latest-report card shows the image name and review status.

**Verification of this round** (real browser, real backend; commands `node docs/audit_evidence/contrast.mjs`, `ui_simplified.mjs`, `audit_ui.mjs`, `geo_check.mjs`, `review_workflow.mjs`, and `scripts
un_audit_suite.ps1`):

| Check | PASS | FAIL |
|---|---:|---:|
| `ui_simplified.mjs` incl. new report-clean / list / technical-details / table-columns / uncertainty-details checks, phone, stale-result, error and contrast checks | 86 | 0 |
| `audit_ui.mjs` | 37 | 0 |
| `review_workflow.mjs` (now with a double-click test) | 27 | 0 |
| `geo_check.mjs` | 1 | 0 |
| Contrast measurement (15 page states) - failing text/background combinations | 0 | - |
| Unit / integration tests | 205 | 0 |
| Live API (139 checks, +1 for the report-list fields), per-model 27, reports 61, security 23, training API 20, approved-annotation dry run 9 | all | 0 |

Failures seen on the way (all fixed): the report-list date was 4.41:1 on the selected row (now darker grey); my scripts still expected the removed banner, the old uncertainty wording and the old list buttons; one test counted table buttons that sit inside the table's own scroll container as "outside the viewport". Console and backend: no tracebacks or 500s; the only error responses are the two simulated failures of the error-handling test and the harness' intended 4xx/5xx refusals.

**Data note (please read).** The four reports named in the request (`RPT-B48B6B2A84`, `RPT-7359C1901A`, `RPT-929931A846`, `RPT-8FE7BD20E0`) were created by this project's own test runs (uploads of `val_12`, 16:15-16:20 UTC), not by a user, and were removed by the backed-up cleanup script together with other test records; they exist only in the database backups (outside the repository). The cleanup deletes every report created after the audit cutoff, so **a report created by hand in the UI after that time would also have been removed**; if you keep real reports, tell me and the cleanup cutoff will be changed to an explicit list of test ids. No checkpoint, manifest, split or evaluation report changed (41 files compared).

**Not done / limits.** Table sorting and filtering were not added (the brief allowed this only if reliable). Report history shows a single review (who/when); the backend stores no multi-step history for reports. A separate "Approved" report state does not exist (approval exists for region reviews only). Contrast covers text only. No frontend unit tests exist.

## 7. Unchanged (confirmed)

All 8 checkpoint files, the manifests, splits and evaluation reports were compared by SHA-256 against the snapshot taken before this work: no differences (`integrity_ui.json`). The database was backed up before every cleanup and returned to its baseline (3 uploads, 1 AL round, 50 experiments); records created by the tests were removed.
The only backend change is the extra `size_bytes` field. Token authentication, loopback restriction and rate limiting were left as they were and were active in every test.
