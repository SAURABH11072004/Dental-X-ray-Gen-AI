# Multilingual written-report test report

Audit date 2026-10-14. Scope: English, Hindi (hi) and Marathi (mr) - the only languages the API offers (`GET /api/reports/{id}` returns
`languages: {en, hi, mr}` and the UI selector is built from it). Every other language code is refused with HTTP 422, so nothing is advertised that does not exist.

**Result: 61 checks passed, 0 failed, 0 blocked, 0 partial** in `scripts/audit_reports.py` (run against the live API plus two short-lived extra server processes),
plus 21/21 report checks in `scripts/audit_live_api.py` and the browser checks below.
All figures here come from `docs/audit_evidence/report_audit.json`, `live_api_tests.json` and `ui_audit.json`; nothing was typed in by hand.

## What "supported" means here - and what it does not

| Language | Generated from real analysis | Structured content identical to English | Script renders in the browser | Native dental-domain review of the wording |
|---|---|---|---|---|
| English | yes (template) | (source) | yes | not applicable |
| Hindi | yes | yes - 1/1 structural check, plus numbers/abstentions/disclaimer/leak checks | yes (Devanagari screenshot reviewed) | **NOT DONE** - flag `translation_reviewed_by_native_dental_professional = false` is returned and shown |
| Marathi | yes | yes | yes (screenshot `docs/audit_evidence/shots/e2e_report_mr.png` reviewed: conjuncts and spacing legible) | **NOT DONE** - same flag |

Hindi and Marathi are produced from **fixed sentence templates**, not machine translation and not an LLM. Values, ids and versions are copied verbatim from the English
report, and `verify_localization` refuses to export a localised report if any of them differ. That guarantees *integrity*; it does not guarantee that a native-speaking dentist
would choose the same terminology. Do not describe the Hindi/Marathi wording as clinically reviewed.

## How the report is built and checked

1. `POST /api/analyze/full` runs the real pipeline on a real radiograph (detector, numbering, segmenter, classifier, uncertainty) - audit source image `up_d02567b36667`, analysis `an-7e576f445f`.
2. `POST /api/reports/generate {analysis_id}` builds the evidence (one finding per region, linked by region id) and a template report; `validate_report` compares report and evidence.
3. `GET /api/reports/{id}?lang=hi|mr` renders the localised view from the stored English report + evidence. **No model is called** (verified: the analysis-table row count is unchanged by language switches, and the browser issues no inference request when the language is changed).

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\audit_reports.py          # needs the API on :8000; also starts temporary servers on :8011 and :8012
.\.venv\Scripts\python.exe scripts\audit_live_api.py         # REP-* rows
node docs\audit_evidence\audit_ui.mjs                          # browser rows (needs playwright-core + Edge; see FUNCTIONALITY_AUDIT.md)
```

Export files produced by the audit (real API output, three formats x three languages): `docs/audit_evidence/report_{en,hi,mr}.{html,json,txt}`,
and the Marathi HTML downloaded through the browser: `docs/audit_evidence/ui_export_mr.html`.

## Results - `scripts/audit_reports.py`

| ID | Check | Expected | Actual | Result |
|---|---|---|---|---|
| RPT-A01 | real full-pipeline analysis as the source | 200 with regions | 200 image=up_d02567b36667 regions=33 analysis=an-7e576f445f | **PASS** |
| RPT-A02 | generate EN template report from the analysis | report id, image id, model versions, status = unconfirmed research draft | RPT-B82CE18066 image=up_d02567b36667 status=unconfirmed_research_draft models={'detection': 'dentex_teeth_detection_v1', 'segmentation': 'dentex_teeth_segmentation_v1', ' | **PASS** |
| RPT-A03 | regeneration from the same analysis | new report id, identical findings (deterministic template) | ids differ=True findings identical=True | **PASS** |
| RPT-B01 | languages advertised to the UI | exactly the languages that have complete templates | {"en": "English", "hi": "हिन्दी", "mr": "मराठी"} | **PASS** |
| RPT-B02 | lang='xx' | 4xx with the list of supported languages (no English fallback labelled as translation) | 422 {"error":{"code":"validation_error","message":"lang: String should match pattern '^(en\|hi\|mr)$'","hint":"Check | **PASS** |
| RPT-B02 | lang='fr' | 4xx with the list of supported languages (no English fallback labelled as translation) | 422 {"error":{"code":"validation_error","message":"lang: String should match pattern '^(en\|hi\|mr)$'","hint":"Check | **PASS** |
| RPT-B02 | lang='HI' | 4xx with the list of supported languages (no English fallback labelled as translation) | 422 {"error":{"code":"validation_error","message":"lang: String should match pattern '^(en\|hi\|mr)$'","hint":"Check | **PASS** |
| RPT-B02 | lang='' | 4xx with the list of supported languages (no English fallback labelled as translation) | 422 {"error":{"code":"validation_error","message":"lang: String should match pattern '^(en\|hi\|mr)$'","hint":"Check | **PASS** |
| RPT-B02 | lang='en;drop' | 4xx with the list of supported languages (no English fallback labelled as translation) | 422 {"error":{"code":"validation_error","message":"lang: String should match pattern '^(en\|hi\|mr)$'","hint":"Check | **PASS** |
| RPT-B02 | lang='../en' | 4xx with the list of supported languages (no English fallback labelled as translation) | 422 {"error":{"code":"validation_error","message":"lang: String should match pattern '^(en\|hi\|mr)$'","hint":"Check | **PASS** |
| RPT-C01-hi | hi: finding ids, FDI, kind, label, score, uncertainty, review status, model versions, ids, status identical to English | exactly equal (no add/remove/alter) | 33 findings vs 33; equal=True | **PASS** |
| RPT-C02-hi | hi: server-side verify_localization | passed, no problems | {"passed": true, "problems": [], "lang": "hi"} | **PASS** |
| RPT-C03-hi | hi: every decimal value in the English narrative appears verbatim | none missing | missing=[] | **PASS** |
| RPT-C04-hi | hi: abstained regions identical | same list | en=21 hi=21 | **PASS** |
| RPT-C05-hi | hi: research-draft + professional-review disclaimer and 'unconfirmed' status present | present, non-empty, in the target script | status_text='असत्यापित शोध मसौदा' disclaimer='यह मॉडल के आउटपुट से तैयार किया गया शोध मसौदा है। यह नैदानिक' | **PASS** |
| RPT-C06-hi | hi: untranslated English words inside translated prose (after removing ids, versions and bracketed class names) | none (or only technical tokens) | {} | **PASS** |
| RPT-C07-hi | hi: no treatment instructions | no treatment words | found=[] | **PASS** |
| RPT-C01-mr | mr: finding ids, FDI, kind, label, score, uncertainty, review status, model versions, ids, status identical to English | exactly equal (no add/remove/alter) | 33 findings vs 33; equal=True | **PASS** |
| RPT-C02-mr | mr: server-side verify_localization | passed, no problems | {"passed": true, "problems": [], "lang": "mr"} | **PASS** |
| RPT-C03-mr | mr: every decimal value in the English narrative appears verbatim | none missing | missing=[] | **PASS** |
| RPT-C04-mr | mr: abstained regions identical | same list | en=21 mr=21 | **PASS** |
| RPT-C05-mr | mr: research-draft + professional-review disclaimer and 'unconfirmed' status present | present, non-empty, in the target script | status_text='अपुष्ट संशोधन मसुदा' disclaimer='हा मॉडेलच्या आउटपुटवरून तयार केलेला संशोधन मसुदा आहे. हे वैद' | **PASS** |
| RPT-C06-mr | mr: untranslated English words inside translated prose (after removing ids, versions and bracketed class names) | none (or only technical tokens) | {} | **PASS** |
| RPT-C07-mr | mr: no treatment instructions | no treatment words | found=[] | **PASS** |
| RPT-C10-hi | hi: 'awaiting linguistic review' label in the JSON, near the top of the HTML and of the TXT export | present in all three | status=awaiting_linguistic_review html=True txt-top=True | **PASS** |
| RPT-C10-mr | mr: 'awaiting linguistic review' label in the JSON, near the top of the HTML and of the TXT export | present in all three | status=awaiting_linguistic_review html=True txt-top=True | **PASS** |
| RPT-C11-en | English export carries no translation-review label | absent | True | **PASS** |
| RPT-C08-en | en: no treatment instructions | no treatment words | found=[] | **PASS** |
| RPT-C09-en | en: every sentence mentioning diagnosis/confirmed/present/affected is a negation or limitation | all negated | 16 sentences, all negated=True; e.g. [' It has no healthy class, so a class name here is not a statement that the finding is present.', ' The classification model has no  | **PASS** |
| RPT-D01-en | HTML export (en) well-formed, lang attribute, charset, no script/handlers | true | 12379 B ct=text/html; charset=utf-8 lang-attr=True charset=True bad=[] | **PASS** |
| RPT-D02-en | JSON export (en) parses and carries the same finding ids | same ids | 200 keys=['report', 'evidence', 'validation', 'localized', 'localization_check'] | **PASS** |
| RPT-D03-en | TXT export (en) contains report id, every finding id, model versions | all present | 7444 chars | **PASS** |
| RPT-D01-hi | HTML export (hi) well-formed, lang attribute, charset, no script/handlers | true | 26709 B ct=text/html; charset=utf-8 lang-attr=True charset=True bad=[] | **PASS** |
| RPT-D02-hi | JSON export (hi) parses and carries the same finding ids | same ids | 200 keys=['report', 'evidence', 'validation', 'localized', 'localization_check'] | **PASS** |
| RPT-D03-hi | TXT export (hi) contains report id, every finding id, model versions | all present | 8622 chars | **PASS** |
| RPT-D01-mr | HTML export (mr) well-formed, lang attribute, charset, no script/handlers | true | 28243 B ct=text/html; charset=utf-8 lang-attr=True charset=True bad=[] | **PASS** |
| RPT-D02-mr | JSON export (mr) parses and carries the same finding ids | same ids | 200 keys=['report', 'evidence', 'validation', 'localized', 'localization_check'] | **PASS** |
| RPT-D03-mr | TXT export (mr) contains report id, every finding id, model versions | all present | 8868 chars | **PASS** |
| RPT-E01 | empty findings | truthful refusal or safe, flagged output | 200 {"report": {"report_id": "RPT-19D697F7C7", "image_id": "up_d02567b36667", "model_version": null, "model_versions": {"detection": null}, "generated_by" | **PASS** |
| RPT-E02 | missing confidence/score | truthful refusal or safe, flagged output | 200 {"report": {"report_id": "RPT-3323129CB2", "image_id": "up_d02567b36667", "model_version": "dentex_teeth_detection_v1", "model_versions": {"detection" | **PASS** |
| RPT-E03 | no tooth number | truthful refusal or safe, flagged output | 200 {"report": {"report_id": "RPT-7EA7BCDC69", "image_id": "up_d02567b36667", "model_version": "dentex_teeth_detection_v1", "model_versions": {"detection" | **PASS** |
| RPT-E04 | invalid FDI 99 | truthful refusal or safe, flagged output | 200 {"report": {"report_id": "RPT-67753C5658", "image_id": "up_d02567b36667", "model_version": "dentex_teeth_detection_v1", "model_versions": {"detection" | **PASS** |
| RPT-E04v | invalid FDI 99: report flagged invalid, not exportable as clean | validation_failed true | validation_failed=True | **PASS** |
| RPT-E05 | label outside the 4 trained classes ('Healthy') | truthful refusal or safe, flagged output | 200 {"report": {"report_id": "RPT-38CCE8EED7", "image_id": "up_d02567b36667", "model_version": "dentex_teeth_detection_v1", "model_versions": {"detection" | **PASS** |
| RPT-E05v | label outside the 4 trained classes ('Healthy'): report flagged invalid, not exportable as clean | validation_failed true | validation_failed=True | **PASS** |
| RPT-E06 | probability out of range 1.7 | truthful refusal or safe, flagged output | 200 {"report": {"report_id": "RPT-4559361376", "image_id": "up_d02567b36667", "model_version": "dentex_teeth_detection_v1", "model_versions": {"detection" | **PASS** |
| RPT-E06v | probability out of range 1.7: report flagged invalid, not exportable as clean | validation_failed true | validation_failed=True | **PASS** |
| RPT-E07 | injected 'confirmed diagnosis' text in a finding | truthful refusal or safe, flagged output | 200 {"report": {"report_id": "RPT-ABE0C029B6", "image_id": "up_d02567b36667", "model_version": "dentex_teeth_detection_v1", "model_versions": {"detection" | **PASS** |
| RPT-E08 | LLM mode without configuration | truthful refusal or safe, flagged output | 502 {"error": {"code": "external_service_unavailable", "message": "LLM is not configured.", "hint": "Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env,  | **PASS** |
| RPT-E09 | unknown mode | truthful refusal or safe, flagged output | 422 {"error": {"code": "validation_error", "message": "mode: Input should be 'auto', 'template' or 'llm'", "hint": "Check the highlighted fields.", "detai | **PASS** |
| RPT-E10 | unknown analysis | truthful refusal or safe, flagged output | 404 {"error": {"code": "not_found", "message": "Analysis 'an-doesnotexist' not found.", "hint": null, "details": {}}} | **PASS** |
| RPT-F01 | review with empty reviewer | 422 | 422 | **PASS** |
| RPT-F02 | report not marked reviewed by those failed attempts | status unconfirmed | unconfirmed_research_draft | **PASS** |
| RPT-F03 | report list contains the audit reports and links to the right image | ids listed | True total=11 | **PASS** |
| RPT-F04 | review of an audit-created report by a named reviewer | status reviewed + reviewer stored | 200 {'report_id': 'RPT-9855A6F1BA', 'image_id': 'up_d02567b36667', 'model_version': 'dentex_teeth_detection_v1', 'model_versions': {'detection': 'dentex_t | **PASS** |
| RPT-G00 | second server process started on :8011 (fresh process, same database) | healthy | True | **PASS** |
| RPT-G01 | reopen the reviewed report from a fresh process (Marathi) | same report, reviewed_by = 'Audit Reviewer (test)', still verified | 200 reviewed_by=Audit Reviewer (test) check=True | **PASS** |
| RPT-G02 | list in the fresh process equals the list in the main process | same ids | 11 vs 11 | **PASS** |
| RPT-H01 | server started with an unusable database path | clear failure (exit with message) or health shows database error; no silent fake DB | exited: "inError 3] The system cannot find the path specified: 'Z:\\\\'. The folder must be on a local, writable disk (network, cloud-synced or virtual drives can break S | **PASS** |
| RPT-I01 | template keys of English present in Hindi and Marathi | no missing keys | {"hi": [], "mr": []} | **PASS** |
| RPT-I02 | translation flagged as not natively reviewed | translation_reviewed_by_native_dental_professional == false and note says so | hi=False mr=False | **PASS** |

## Results - report rows of `scripts/audit_live_api.py`

| ID | Input | Expected | Actual | Result |
|---|---|---|---|---|
| REP-001 | generate with neither analysis_id nor image_id nor findings | 4xx, no empty fabricated report | 400 '{"error":{"code":"no_evidence","message":"No model findings to report on.","hint":"Run an analysis w' | **PASS** |
| REP-002 | generate for a non-existent analysis | 404 | 404 | **PASS** |
| REP-003 | generate an English template report from the full analysis | 200 with report id linked to image + analysis | 200 id=RPT-0BA63656F9 image=up_22736273675e analysis=None keys=['report_id', 'image_id', 'model_version', 'model_versions', 'generated_by',  | **PASS** |
| REP-004 | GET invalid report id | 404 | 404 | **PASS** |
| REP-005 | unsupported language 'xx' | 4xx with supported list; must not return an English report labelled as translated | 422 '{"error":{"code":"validation_error","message":"lang: String should match pattern \'^(en\|hi\|mr)$\'","hint":"Check the highlighted fields | **PASS** |
| REP-006 | GET report in en/hi/mr | 200 each, localization_check ok for hi and mr | {"en": {"passed": true, "problems": [], "lang": "en"}, "hi": {"passed": true, "problems": [], "lang": "hi"}, "mr": {"passed": true, "problem | **PASS** |
| REP-007 | language switching does not run new inference | analysis row count unchanged | before=14 after=14 | **PASS** |
| REP-01-enj | export format=json lang=en | 200, non-empty, correct content-type | 200 93947 B application/json; charset=utf-8 | **PASS** |
| REP-01-enh | export format=html lang=en | 200, non-empty, correct content-type | 200 12379 B text/html; charset=utf-8 | **PASS** |
| REP-01-ent | export format=txt lang=en | 200, non-empty, correct content-type | 200 7444 B text/plain; charset=utf-8 | **PASS** |
| REP-01-hij | export format=json lang=hi | 200, non-empty, correct content-type | 200 108258 B application/json; charset=utf-8 | **PASS** |
| REP-01-hih | export format=html lang=hi | 200, non-empty, correct content-type | 200 26709 B text/html; charset=utf-8 | **PASS** |
| REP-01-hit | export format=txt lang=hi | 200, non-empty, correct content-type | 200 20026 B text/plain; charset=utf-8 | **PASS** |
| REP-01-mrj | export format=json lang=mr | 200, non-empty, correct content-type | 200 109793 B application/json; charset=utf-8 | **PASS** |
| REP-01-mrh | export format=html lang=mr | 200, non-empty, correct content-type | 200 28243 B text/html; charset=utf-8 | **PASS** |
| REP-01-mrt | export format=txt lang=mr | 200, non-empty, correct content-type | 200 20932 B text/plain; charset=utf-8 | **PASS** |
| REP-020 | export format=pdf (not implemented) | 4xx with an explicit 'not supported' message | 422 '{"error":{"code":"validation_error","message":"format: String should match pattern \'^(json\|html\|txt)' | **PASS** |
| REP-021 | review with an empty reviewer name | 422 | 422 | **PASS** |
| REP-022 | review with a whitespace-only reviewer name | 4xx (name must contain characters) | 400 '{"error":{"code":"reviewer_required","message":"reviewer name is required","hint":null,"details":{}}' | **PASS** |
| REP-030 | report with an explicitly empty findings list | 200; findings == []; summary says nothing was supplied; no invented finding; validation flags the missing model version | 200 findings=[] validation_failed=True summary='No model findings were supplied for this image; no statements about the radiograph are mad' | **PASS** |
| REP-031 | reviewer name containing <script> must be HTML-escaped in the HTML export | no raw <script> tag in exported HTML | review=200; raw_script_in_html=False | **PASS** |

## Results - browser (real Vite + real FastAPI)

| ID | Input | Expected | Actual | Result |
|---|---|---|---|---|
| UI-E-007 | Generate Draft Report from the analysis | report created from analysis_id, shown in English with banner | 200 id=RPT-1FBB0FF27C analysis=(n/a) banner=true | **PASS** |
| UI-E-008 | switch the displayed report EN -> HI -> MR -> EN | ids/versions preserved in every language, Devanagari present, no inference request | ids=38 missing={"hi":[],"mr":[]} devanagari(hi)=true devanagari(mr)=true inference-requests=0 | **PASS** |
| UI-E-009 | click HTML export while language=mr | file downloads; contains Marathi text and the report id | RPT-1FBB0FF27C_mr.html 28773 B marathi=true id=true | **PASS** |
| UI-E-010 | reload /reports and look for the new report in the list | report is listed with its id | listed=true | **PASS** |
| UI-E-010b | click a report in the list while none is selected (regression for the null.report crash) | report renders; no page error | rendered=true pageErrors=0 | **PASS** |
| UI-E-011 | reopen /reports?id=<id> in a fresh navigation | report renders from the database | rendered | **PASS** |
| UI-E-012 | 'Mark reviewed' with an empty reviewer name | button disabled | disabled=true | **PASS** |

## Defects found by this test and fixed

| # | Defect | Root cause | Fix | Regression test |
|---|---|---|---|---|
| 1 | A report whose finding had probability **1.7** or label **"Healthy"** (a class no model can output) was accepted as valid | `validate_report` compared the report with its evidence but never checked the evidence itself | evidence scores must be finite and within 0-1; labels must be one of the app's finding names (spacing/case-insensitive); the report is flagged `validation_failed` otherwise | `tests/test_audit_regressions.py::ReportValidatorEvidenceTests` |
| 2 | A report whose only finding is **"Deep Caries"** was flagged as "mentions finding 'caries' that is not in the evidence" | the vocabulary scan matched the word *caries* inside *Deep Caries* | names of findings that are in the evidence are removed from the text before the other class names are searched | same class (`test_deep_caries_only_report...`, `test_text_naming_a_finding_absent...`) |
| 3 | My own first fix for #1 broke every real report (spelling `DeepCaries` in the config vs `Deep Caries` from the models) | the new label check compared raw strings | spelling-insensitive comparison; caught by the audit's live run before release | `test_config_spelling_without_spaces_matches_model_class_names` |

## Not implemented / not testable (stated, not hidden)

* **Draft editing** - there is no edit route; reports are regenerated, never hand-edited (findings must come from model outputs).
* **PDF / print export** - `format=pdf` returns 422 with the supported formats. Use the browser's *Print* on the HTML export.
* **Live LLM drafting** - not configured here (no key); `mode=llm` returns 502 `LLM is not configured` with a hint; the template path needs no key and sends nothing off the machine.
* **Review sign-off by a verified person** - reviewer names are self-declared strings; there is no authentication. A report that fails validation cannot be signed off.
* **Test data left behind** - the audit created reports in the app database; they are listed and removed by the clean-up step documented in `docs/FINAL_ACCEPTANCE_REPORT.md`.
