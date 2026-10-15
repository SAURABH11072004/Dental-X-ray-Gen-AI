# Multilingual written reports (English, Hindi, Marathi)

Local and template-based: no translation API, no network. Code: `src/dentexmodel/reporting/i18n.py`; endpoints
`GET /api/reports/{id}?lang=en|hi|mr` and `GET /api/reports/{id}/export?format=html|txt|json&lang=...`; UI: Reports page
language selector + HTML / TXT / JSON download buttons.

## How it works
1. The report is first built and validated in English from structured model output (`template_report` + `validate_report`).
2. A localised version is rendered from the **same structured report** with fixed sentence templates per language. It cannot
   add a finding, number or claim: it only rephrases the facts it is given.
3. Copied verbatim in every language: finding ids (`F1`...), model versions (detection / numbering / classification), FDI
   tooth numbers, scores and uncertainty values (ASCII digits, same rounding), review status, and the original English class
   name (shown as `दंतक्षय (Caries)`).
4. `verify_localization` re-checks every localised report against the English one (ids, versions, decimals, structured fields,
   class names, status). The API attaches the result and **refuses to export** a translation that does not match.
5. Every language keeps the research-draft banner, the disclaimer, and the limitation that the classifier has no healthy class.
   No clinical recommendation is generated in any language.

## Verified (2026-10-14)
`tests/test_i18n_reports.py` (8 tests) and a real-browser run (`upload -> detect -> number -> segment -> English report ->
Hindi -> Marathi -> download HTML/TXT/JSON`): identical finding ids and decimal values across the three languages, model
versions preserved, status still "unconfirmed research draft", exports downloaded with Devanagari text.

## Limits
- **The Hindi and Marathi wording has not been reviewed by a native-speaking dental professional.** Each localised report says
  so; the English report is the reference. Have a qualified reviewer approve the templates before any real use.
- Fixed templates only: no free-text translation of reviewer comments, and no other languages yet (add a block to `T` and `LABELS`).
- The HTML export relies on a Devanagari font installed on the reader's machine (Noto Sans Devanagari / Nirmala UI / Mangal).
