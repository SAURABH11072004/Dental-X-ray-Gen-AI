# DentaMind AI: project completion status

Date 2026-10-25. Status per requirement, each with its evidence.

| Status | Meaning |
|---|---|
| **PASS** | done and verified in this repository or on Kaggle (stated) |
| **BLOCKED BY DATA** | needs clinician-verified data that does not exist yet |
| **BLOCKED BY HUMAN AUTHORIZATION** | needs a decision or signature by the accountable person |
| **NOT VERIFIED** | implemented, but not yet exercised on real data |
| **NOT STARTED** | not done |

## 1. Integrity of existing evidence

| Requirement | Status | Evidence |
|---|---|---|
| Approved protocol unchanged | PASS | `reports/cv5_acceptance_protocol.md` `0771b5f8…` |
| Historical revision 2 proposal unchanged | PASS | `98d6e223…` |
| CV5 protocol / results / noise report / fold file unchanged | PASS | pre-audit hash list: 8 / 8 OK; fold file `9b767a48…` |
| Archived CV5-BASE artifacts intact | PASS | `kaggle/dentamind_5fold_cv_artifacts.zip` `4ac56843…`; 88 / 88 SHA256SUMS entries OK |
| Test-set ledger unchanged and chain intact | PASS | `f117c1a3…`; 5 entries; `verify_chain` → no problems |
| BASE notebook and BASE code unchanged | PASS | `dentamind_5fold_cv.ipynb` `dd65c7c7…` (byte-identical regeneration tested); `dentamind_kaggle.py` `879faa93…`, `dsutil.py` `debeb7f0…`, `cv5_lib.py` `72084f9b…`; Kaggle data bundle v3 `9d070fc7…` not rebuilt |
| First candidate-path freeze verified before changes | PASS | 7 / 7 OK at start of this phase; 5 later changed by design and recorded in Amendment 01b draft |

## 2. Engineering implementation

| Requirement | Status | Evidence |
|---|---|---|
| Acceptance function, paired bootstrap, verdict rules, winner rule, budget | PASS | `kaggle/cv5_accept.py`; `tests/test_cv5_accept.py` (21) |
| Candidate-run path: isolation, retry rules, exception origin, per-run manifests, run status, evidence archive | PASS | `tests/test_cv5_candidate_runs.py` (26); Kaggle pre-flight v1 and v2 PASS (150 / 150) |
| No late manifest; conservative exception classification; pre-flight isolation | PASS | freeze review; tests; Kaggle pre-flight |
| C1 384 px crops | PASS (synthetic) / NOT VERIFIED (real data) | `kaggle/cv5_interventions.py`; tests; synthetic smoke; real-data crops and T4 memory unverified |
| C2 0.25 context padding | PASS (synthetic) / NOT VERIFIED (real data) | geometry, clipping and isolation tests; synthetic smoke |
| C3 ConvNeXt-Tiny | PASS (synthetic) / NOT VERIFIED (Kaggle weights download in a real run) | shape, class, checkpoint round-trip tests; synthetic smoke |
| BASE unchanged by interventions | PASS | byte-identical default crops; identical BASE model weights and predictions; BASE code pinned to bundle v3 hashes |
| Versioned candidate-code bundle, no overwrite | PASS | `kaggle/dist/dentamind_cv5_candidate_code_v1.zip` `8ce64d26…`; `reports/cv5_candidate_bundle_v1_manifest.json` |
| Gate R and gate V6 | PASS (unit) / NOT VERIFIED (real data) | implemented and unit-tested; never run on real comparator checkpoints or imports |
| Adding P1 imports to each fold's fitting part in the CV notebook | NOT STARTED | required by Amendment 02; depends on the imports manifest format |

## 3. Testing

| Requirement | Status | Evidence |
|---|---|---|
| Full local test suite | PASS | 440 passed |
| Synthetic pre-flight (local) | PASS | 150 / 150 |
| Synthetic pre-flight (Kaggle, no training, no inputs, Internet off) | PASS | `btechgd10/dentamind-cv5-candidate-preflight` v2: "Successfully ran in 175.4s", PASS 150 / 150 (read from the log) |
| Candidate notebook data cells (folds / images / crops / detector) | NOT VERIFIED | need a registered candidate run |
| Aggregation with all 25 runs complete (real) | NOT VERIFIED | unit-tested only |

## 4. Data acquisition

| Requirement | Status | Evidence |
|---|---|---|
| P2: PL +171 findings / +106 radiographs; DC +283 / +150 | BLOCKED BY DATA | `reports/expanded_class_distribution.csv`; 0 verified imports (`verified_findings.csv` does not exist) |
| Access requests to data holders | BLOCKED BY HUMAN AUTHORIZATION | drafts only in `reports/data_requests/`; sending is the owner's action |
| Clinician review of the 525-task queue | BLOCKED BY HUMAN AUTHORIZATION | needs registered clinicians |
| Operational checklist | PASS | `reports/data_acquisition_checklist.md` |
| Gate V6 on the real imports | BLOCKED BY DATA | — |

## 5. Registration, BASE-P2, training, selection

| Requirement | Status | Evidence |
|---|---|---|
| Candidate registration (Amendment 01) | BLOCKED BY HUMAN AUTHORIZATION | draft `reports/cv5_amendment_01_candidate_registration.md`, unsigned; 0 budget slots used |
| Implementation freeze (Amendment 01b) | BLOCKED BY HUMAN AUTHORIZATION | draft `reports/cv5_amendment_01b_implementation.md`; takes effect with 01 |
| BASE-P2 registration (Amendment 02) | BLOCKED BY DATA | draft skeleton `reports/cv5_amendment_02_base_p2.md`; imports manifest pending |
| BASE-P2 run | BLOCKED BY DATA | — |
| Candidate training (25 runs per candidate) | BLOCKED BY DATA | also needs Amendments 01, 01b and 02 in force |
| Verdicts, winner rule, V-a final artifact | NOT STARTED | depend on candidate runs |
| Final ledger-recorded test evaluation | NOT STARTED | only after a confirmatory ACCEPT; at most one |

## 6. Test-ledger disclosures

| Requirement | Status | Evidence |
|---|---|---|
| P5 disclosure (2026-10-16 BASE test evaluation) | BLOCKED BY HUMAN AUTHORIZATION | `reports/p5_disclosure_entry.json`; needs the accountable person's own name |
| External-data run disclosure (2026-10-24) | BLOCKED BY HUMAN AUTHORIZATION | `kaggle/artifacts_external_run1/ledger_disclosure_entry.json` |

## 7. Research paper readiness

| Requirement | Status | Evidence |
|---|---|---|
| Completion checklist | PASS | `reports/research_paper_completion_checklist.md` |
| Sections from existing evidence (methods, data, BASE CV results, negative results) | NOT STARTED | the paper is not edited without an owner decision |
| Candidate results section | BLOCKED BY DATA | no candidate evaluated |
| Test-history disclosure complete | BLOCKED BY HUMAN AUTHORIZATION | pending ledger disclosures |
| Submission | NOT STARTED | prerequisites in the checklist §7 |

## Next actions for the project owner
1. **Record the two ledger disclosures with your own name:**
   ```
   .venv\Scripts\python.exe scripts\test_set_ledger.py --record-disclosure reports\p5_disclosure_entry.json --authorized-by "<your name>" --reason "..."
   .venv\Scripts\python.exe scripts\test_set_ledger.py --record-disclosure kaggle\artifacts_external_run1\ledger_disclosure_entry.json --authorized-by "<your name>" --reason "..."
   ```
2. **Review Amendment 01:** keep or change C1 / C2 / C3, then sign §8. This also brings 01b into effect.
3. **Start data acquisition:**
   - send the access requests you choose;
   - register clinician reviewers;
   - run review batches through the P1 route until `expansion_report.py` shows P2 met.
4. **Then complete Amendment 02:**
   - fill in the frozen imports manifest and hashes;
   - approve the code that adds imports to each fold's fitting part;
   - sign.

---

## Addendum 2026-10-25 (data-import implementation)

This adds to the table above; it does not edit it. Rows that change status:

| Requirement | Status now | Evidence |
|---|---|---|
| Adding P1 imports to each fold's fitting part | PASS (logic, synthetic tests) / NOT STARTED (notebook wiring) | `kaggle/cv5_imports.py` + `scripts/dataset/build_cv5_import_manifest.py`; `tests/test_cv5_imports.py` 22 passed. Wiring into `kaggle/make_cv5_notebook.py` changes a frozen file (Amendment 01b) and needs a separately authorized dated change |
| Import independence on identities (group / image SHA-256 / pool split lock) | PASS (synthetic) | rejections tested; under CV only `unassigned` pool radiographs are importable (stricter than P1, as protocol §3.1 item 3 requires) |
| Gate V6 near-duplicate check on imports | PASS (synthetic) / BLOCKED BY DATA (real) | `gate_v6_for_manifest` tested with a resized twin |
| Full local test suite | PASS | 462 passed |
| Intake template, data-request checklist, human authorization checklist | PASS | `reports/templates/`, `reports/data_request_checklist.md`, `reports/human_authorization_checklist.md` |

Unchanged:
* P2 is BLOCKED BY DATA (0 verified imports).
* Ledger disclosures and Amendment 01 are BLOCKED BY HUMAN AUTHORIZATION.
* BASE-P2 and candidate training are BLOCKED BY DATA.

## Addendum 2026-10-25 (import wiring proposal)

| Requirement | Status | Evidence |
|---|---|---|
| Notebook wiring of imports | NOT STARTED (applied) / PASS (proposal, synthetic tests) | `patches/cv5_import_wiring.patch`, **unapplied**; `kaggle/make_cv5_notebook.py` unchanged (`4a5efda8…`); `tests/test_cv5_import_wiring.py` 14 passed on a temporary patched copy |
| Applying the wiring change | BLOCKED BY HUMAN AUTHORIZATION | changes a frozen file; needs a separately authorized dated change |
| Local full gate V6 record | PASS (synthetic) / BLOCKED BY DATA (real) | `scripts/dataset/run_cv5_import_v6.py` |
| Full local test suite | PASS | 476 passed |

## Addendum 2026-10-25 (BASE-P2 path, reviewer authorization, review package)

| Requirement | Status | Evidence |
|---|---|---|
| Separate BASE-P2 generator with frozen registration | PASS (synthetic) / BLOCKED BY DATA + HUMAN AUTHORIZATION (use) | `kaggle/make_base_p2_notebook.py`; `tests/test_cv5_base_p2.py` 20 passed |
| Reviewer-authorization artifact and manifest binding | PASS (synthetic) / BLOCKED BY HUMAN AUTHORIZATION (issuing v1) | `scripts/dataset/build_reviewer_authorization.py`; `tests/test_reviewer_authorization.py` 11 passed |
| Import wiring patch (shared template, authorization check) | proposal, **unapplied** | `patches/cv5_import_wiring.patch` (`ed26e064…`); frozen generator unchanged |
| Review package | PASS | `reports/cv5_patch_review_package.md` |
| Full local test suite | PASS | 507 passed |

## Addendum 2026-10-25 (Amendment 03 draft: D-B1 to D-B6)

| Requirement | Status | Evidence |
|---|---|---|
| Decisions D-B1 to D-B6, formal draft | PASS (draft) / BLOCKED BY HUMAN AUTHORIZATION (in force) | `reports/cv5_amendment_03_decisions_DB1_DB6.md`, NOT IN FORCE |
| Human approval records, metric sealing, BASE-P2 failure gate | PASS (synthetic) | `kaggle/cv5_approvals.py`; `tests/test_cv5_approvals.py` 12, `tests/test_cv5_base_p2.py` 24 |
| Reviewer qualification, clinical lead, second reader, adjudication (D-B5) | BLOCKED BY HUMAN AUTHORIZATION | clinical governance; not decided by the assistant |
| Patch application plan | PASS (plan) / NOT STARTED (execution) | `reports/cv5_patch_application_plan.md`; patch `ed26e064…` unapplied |
| Full local test suite | PASS | 524 passed |

## Addendum 2026-10-25 (approval package)

| Requirement | Status | Evidence |
|---|---|---|
| BASE-P2 failure policy (F1–F6) | BLOCKED BY HUMAN AUTHORIZATION | `reports/cv5_decision_base_p2_failure_policy.md` (options only; existing protocol rules quoted separately) |
| Clinical governance (D-B5) | BLOCKED BY HUMAN AUTHORIZATION (clinical lead) | `reports/templates/clinical_governance_decision_template.md` (empty template) |
| Approval checklist for Amendment 03 and the patch; approval-mechanism gaps G1–G7 | PASS (prepared) / BLOCKED BY HUMAN AUTHORIZATION | `reports/cv5_approval_checklist_amendment03_and_patch.md`; no approval record exists |
| Patch application plan verified by dry run | PASS (dry run) | plan addendum; patch `ed26e064…` unapplied; generator `4a5efda8…` unchanged |

## Addendum 2026-10-25 (pre-authorization audit)

| Requirement | Status | Evidence |
|---|---|---|
| Pre-authorization audit and decision packet | PASS (prepared) | `reports/cv5_pre_authorization_decision_packet.md`; integrity re-verified; 524 tests passed |
| Patch application | **NO-GO** | plan gaps A–E (rollback scope, unreviewed test edits, 01c timing, bundle file list missing `cv5_imports.py`, step-8 regeneration over protected files); approvals pending |

## Addendum 2026-10-25 (consolidated plan v2)

| Requirement | Status | Evidence |
|---|---|---|
| Consolidated patch plan (defects A–E) | PASS (plan, dry run) / NO-GO (execution) | `reports/cv5_patch_application_plan_v2.md`; `patches/cv5_patch_set_v1.json`; dry run: 191 CV5 tests, notebook identity, scratch bundle v2, rollback all verified |
| Test-pin and bundle-builder patches | PASS (prepared) / BLOCKED BY HUMAN REVIEW | `patches/cv5_test_pin_update.patch`, `patches/cv5_bundle_builder_imports.patch` (unapplied) |
| Amendment 01c | draft skeleton, unsigned | `reports/cv5_amendment_01c_DRAFT.md` |
| Approval policy | BLOCKED BY HUMAN AUTHORIZATION | `reports/cv5_approval_policy_DRAFT.md`; needs a tooling patch for new scopes |

## Addendum 2026-10-25 (master execution)

| Requirement | Status | Evidence |
|---|---|---|
| Integrity re-verified (protected files, patch set, ledger, archive) | PASS (verified) | `reports/publication_readiness_and_dependencies.md` §1 |
| Approval-tooling patch (new scopes, register, log, ordering, countersignature) | PASS (prepared, 9 tests) / BLOCKED BY HUMAN AUTHORIZATION (apply) | `patches/cv5_approvals_policy_tooling.patch` (unapplied) |
| Patch set application | BLOCKED BY HUMAN AUTHORIZATION | no approval exists |
| Results traceability (133 rows from verified artifacts) | PASS (verified) | `reports/results_traceability.*` |
| Manuscript draft (verified numbers; candidate sections blocked) | PASS (draft) | `reports/manuscript/DentaMind_CV5_manuscript_DRAFT.md` |
| Data / P2, clinical governance, BASE-P2, candidates | BLOCKED BY DATA / CLINICAL LEAD / HUMAN AUTHORIZATION / INFRASTRUCTURE | dependency graph §4 |
| Publication readiness | baseline-and-protocol report possible; improvement claim NOT supported | §5 |
| Full test suite | PASS | 533 passed, 0 failed |

## Addendum 2026-10-25 (manuscript v1 finalization)

| Requirement | Status | Evidence |
|---|---|---|
| Archive and traceability re-verified | PASS (verified) | CV5 archive 88 / 88; imbalance run 61 / 61; external run 39 / 39 |
| Negative-findings traceability (49 rows; validation split, not CV5) | PASS (verified) | `scripts/build_negative_findings_traceability.py`; `reports/negative_findings_traceability.*` |
| Finalized manuscript draft (separate file; earlier draft unchanged) | PASS (draft) / NOT SUBMITTED | `reports/manuscript/DentaMind_CV5_manuscript_v1_submission_draft.md` |
| Number and citation audit | PASS: 134 traced, 62 declared constants, 0 untraced | `scripts/audit_manuscript_numbers.py`; `reports/manuscript/manuscript_v1_number_audit.md` |
| Bibliography audit | PASS (16 / 16 keys; 15 DOIs resolved online) / OPEN (`guo` has no DOI; `bittar` dated 2026; sources must be read by the authors) | `scripts/audit_bibliography.py`; `reports/manuscript/citation_audit_v1.md` |
| Publication-readiness checklist | prepared; author, supervisor, venue, ethics, licence and declaration items OPEN | `reports/manuscript/publication_readiness_checklist_v1.md` |
| Latency, candidate results, clinical claims | not reported (not measured / not run / not validated) | manuscript sections 4.7, 4.8 and 5 |
| Full test suite | PASS | 538 passed, 0 failed (533 + 5 in `tests/test_manuscript_audit.py`) |

## Addendum 2026-10-25 (journal manuscript v2)

| Requirement | Status | Evidence |
|---|---|---|
| Journal-format manuscript (prose, structured abstract, 3 tables, 5 figures, 16 numbered references) | PASS (draft) / NOT SUBMITTED | `reports/manuscript/DentaMind_CV5_manuscript_v2_journal.docx` (+ `.pdf`, audited `.md` source) |
| Number audit v2 | PASS: 170 traced, 0 untraced; Word file matches the source (165 / 165 numbers) | `reports/manuscript/manuscript_v2_number_audit.md` |
| Per-class bootstrap CIs (post-hoc, descriptive; reproduce the archived macro-F1 CIs exactly) | PASS (computed from archived predictions) | `scripts/per_class_bootstrap_cv5.py`; `reports/cv5_per_class_bootstrap.*` |
| Figures from verified artifacts | PASS | `scripts/make_manuscript_figures.py`; `reports/manuscript/figures_v2/` (manifest with hashes) |
| Cover letter, highlights, venue guidance | prepared (template; authors fill in) | `reports/manuscript/submission_package_v2.md` |
| Readiness checklist v2 | technical work done; author, guide, venue, ethics, licence, declaration and overlap items OPEN | `reports/manuscript/publication_readiness_checklist_v2.md` |
| Journal acceptance | cannot be guaranteed; depends on the venue, reviewers and the open author items | - |
| Full test suite | PASS | 543 passed, 0 failed (538 + 5 in `tests/test_manuscript_v2.py`) |

## Addendum 2026-10-25 (research improvement round 1)

| Requirement | Status | Evidence |
|---|---|---|
| State re-verified (protected hashes, archive 88 / 88, approvals) | PASS; no integrity failure; no approval records exist | `reports/research_improvement_report_v1.md` section 0 |
| Latency benchmark | MEASURED (RTX 3050 Laptop GPU, 2 runs; end-to-end median 251.3 / 241.7 ms per radiograph) | `reports/latency_benchmark_rtx3050_run{1,2}.*` |
| Error attribution | PASS (3 reproduction gates) | `reports/cv5_error_attribution.*` |
| Matching-rule candidate | PROPOSED; not evaluated (would be post-hoc) | `reports/cv5_matching_rule_proposal_DRAFT.md` |
| Clinician re-reading | PREPARED / BLOCKED BY CLINICAL LEAD | `reports/clinical_review/` |
| Calibration experiment | DRAFT registration + code + 4 tests; NOT RUN | `reports/cv5_calibration_experiment_registration_DRAFT.md` |
| External validation | eligibility assessed; no eligible verified source | `reports/external_validation_eligibility_v1.md` |
| Published-method comparison | feasibility assessed | `reports/published_method_comparison_feasibility_v1.md` |
| Candidate runs C1-C3 | NOT READY (all approval gates missing) | `reports/cv5_candidate_run_readiness_v1.md` |
| Manuscript v3 | PASS (222 traced, 0 untraced; Word file matches); v2 preserved; v2 'registered' wording corrected in v3 | `reports/manuscript/DentaMind_CV5_manuscript_v3_journal.*` |
| Full test suite | PASS | 553 passed, 0 failed (543 + 4 temperature-scaling + 6 improvement-round tests) |

## Addendum 2026-10-25 (research improvement round 2)

| Requirement | Status | Evidence |
|---|---|---|
| Integrity re-verified | PASS; no protected hash differed | `reports/research_improvement_report_v2.md` section 1 |
| Independent-review packet for the approval-tooling patch | PREPARED (13 tests pass on a temporary copy; patch NOT applied) | `reports/review/approval_tooling_review_packet_v1.md` |
| Matching rule M1 registration | DRAFT; library tested on synthetic data only; NOT RUN on CV5 | `reports/cv5_matching_rule_registration_DRAFT.md`; `scripts/cv5_matching_m1.py` |
| Clinical-review blinding | v1 defect found (public labels traceable); v2 worksheet with opaque codes; v1 kept | `reports/clinical_review/clinical_governance_readiness_v1.md` |
| Clinical governance | BLOCKED BY CLINICAL LEAD (C1-C11 open) | same |
| Manuscript v3 claims audit | FAIL: earlier test-split use not disclosed (also in v2) | `reports/manuscript/manuscript_v3_claims_audit.md` |
| Manuscript v3.1 | PASS (numbers 222 / 0 untraced; claims; citations 16 / 16 keys); v3 preserved | `reports/manuscript/DentaMind_CV5_manuscript_v3_1_journal.*` |
| Full test suite | PASS | 568 passed, 0 failed |

## Addendum 2026-10-25 (approval and execution preparation)

| Requirement | Status | Evidence |
|---|---|---|
| Independent-reviewer checklist (blank; includes unknown-scope item D4) | PREPARED; no verdict | `reports/review/independent_reviewer_checklist_v1.md` |
| Clinical-review file access | inspected (read-only): world-readable, untracked, not git-ignored, GitHub remote present; procedure PROPOSED, not executed | `reports/clinical_review/access_control_procedure_v1_PROPOSED.md` |
| M1 route decision memo | DRAFT; registration draft's Option A rationale found incomplete (protocol section 3); addendum appended | `reports/cv5_matching_rule_decision_memo_DRAFT.md` |
| Action register | 24 rows; none signed | `reports/action_register_v1.md` |
| Relevant tests | PASS (30) | tooling, M1 library, round 1, round 2 |
