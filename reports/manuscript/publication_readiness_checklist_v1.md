# Publication-readiness checklist: manuscript v1 (baseline-and-protocol report)

Date 2026-10-25. Applies to `reports/manuscript/DentaMind_CV5_manuscript_v1_submission_draft.md`; its SHA-256 is recorded in
`reports/manuscript/manuscript_v1_number_audit.md`.
* The assistant decides none of the open items below and has filled none of them in.
* "Done" means verified in this session.

## A. Evidence and integrity (done)

| # | Item | Status | Evidence |
|---|---|---|---|
| A1 | CV5 archive verified | done: 88 / 88 | `kaggle/artifacts_cv5_run1/SHA256SUMS.txt`; archive `4ac56843…` |
| A2 | Negative-result sources verified | done | imbalance run 61 / 61; external run 39 / 39; ensemble file hash only (`f208246a…`, not checksum-archived) |
| A3 | Every manuscript number traced | done: 0 untraced | `reports/manuscript/manuscript_v1_number_audit.md` |
| A4 | Recall reported with its evaluation setting | done | manuscript §3.3 and §4.3 |
| A5 | Latency | not measured; not reported or estimated | `[cost.latency]` is NOT AVAILABLE |
| A6 | Candidate results | absent; described as not trained | manuscript §4.8 |
| A7 | Negative findings and limitations | included | manuscript §4.6 and §5 |
| A8 | Cited keys in the bibliography; DOIs resolve | done: 16 / 16 keys; 15 DOIs resolved, titles match; `guo` has no DOI | `reports/manuscript/citation_audit_v1.md` |

## B. Author and supervisor decisions (open)

| # | Decision | Responsible | Notes |
|---|---|---|---|
| B1 | Whether to submit a baseline-and-protocol paper at all, or wait for candidate results | authors + guide | the manuscript makes no improvement claim and must not gain one without the protocol's evidence |
| B2 | Author order, affiliations, corresponding author, CRediT contributions | authors | names are kept exactly as given; nothing else is assumed |
| B3 | Supervisor (guide) review and approval to submit | Dr. Pradnya Narkhede | not requested or recorded by the assistant |
| B4 | Venue: journal or conference, article type, word and figure limits, template | authors + guide | no venue chosen; formatting not started |
| B5 | Whether the earlier papers in `documents/` overlap with this one (prior publication or submission) | authors | dual-submission and self-plagiarism rules of the venue apply; no similarity guarantee is given |
| B6 | Figures: which to include, and regeneration from archived artifacts only | authors | none embedded in v1 |

## C. Ethics, licensing and data (open)

| # | Item | Responsible | Notes |
|---|---|---|---|
| C1 | Ethics statement for secondary use of public, de-identified DENTEX data | authors, per institutional rules | whether an ethics committee waiver is needed is an institutional decision; nothing is claimed |
| C2 | DENTEX licence and terms of use, quoted exactly from the official source | authors | redistribution of images is not assumed to be allowed |
| C3 | Data availability statement | authors | draft text in manuscript §7 |
| C4 | Code availability: repository, licence, release tag | authors | no public release exists |
| C5 | Disclosure of prior test-split use | accountable test-set authorizer | two ledger disclosures are pending (`reports/p5_disclosure_entry.json` `c8f9b186…`, `kaggle/artifacts_external_run1/ledger_disclosure_entry.json` `91083588…`); the manuscript reports no test result |
| C6 | Protocol approval evidence | project owner | the protocol file records an approval statement of 2026-10-25; no signed approval record exists (S0 policy not adopted) |
| C7 | Clinical claims | — | none made; no clinical lead appointed; keep "not validated for clinical use" |

## D. Declarations (open; placeholders in manuscript §7)

| # | Item | Responsible |
|---|---|---|
| D1 | Funding | authors |
| D2 | Conflicts of interest | authors |
| D3 | Use of AI assistance, per the venue's policy | authors |
| D4 | Acknowledgements (e.g. Kaggle compute) | authors |

## E. Bibliography (partly done)

| # | Item | Status |
|---|---|---|
| E1 | All cited keys exist | done |
| E2 | DOIs resolve, with matching title, year and first author | done for 15 cited entries (machine check, 2026-10-25) |
| E3 | `guo` (ICML 2017, PMLR) has no DOI | open: confirm against PMLR volume 70 |
| E4 | `bittar` is dated 2026 | open: confirm volume and pages are final |
| E5 | Each cited source supports the sentence citing it | **open: authors must read the sources**; a resolved DOI does not show this |

## F. Not possible before more work (blocked; do not fill)
* Any improvement claim: candidates need registration, the BASE-P2 run, the CV runs and protocol verdicts.
* Clinician-verified data: P2 targets unmet; 0 verified labels.
* Clinical validation: none planned in this scope.
* Latency claims: would need a new, planned measurement.
