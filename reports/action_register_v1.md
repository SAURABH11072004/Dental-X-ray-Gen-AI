# DentaMind AI: action register v1 (2026-10-25)

**Status key:**
* PENDING: waiting for the accountable human.
* DRAFT: a prepared document awaiting a decision.
* BLOCKED: a dependency is not met.
* READY: can start once a human acts.

**Rules:**
* No row is signed or approved.
* No person is named. Roles are functions, filled by humans the project owner appoints.
* "Evidence" means what the human must produce or check; the assistant has not produced it on their behalf.

## 1. Approval tooling and protocol path

| # | Task | Accountable role | Required evidence | Blocking dependencies | Status |
|---|---|---|---|---|---|
| R1 | Review the approval-tooling patch, including item D4 (unknown-scope behaviour) | Independent reviewer | completed `reports/review/independent_reviewer_checklist_v1.md`; self-computed hashes A1–A5; 13 tests re-run; verdict bound to patch `de92744b…` | none | READY |
| R2 | Adopt the approval policy (bootstrap) | Project owner | approval statement bound to `cv5_approval_policy_DRAFT.md` `1bd2a0cd…` | R1 verdict (recommended first) | PENDING |
| R3 | Issue approver register v1 (real role holders) | Project owner | register file whose content hash is recorded | R2 | PENDING |
| R4 | Apply the tooling patch: backup, apply, after-hash `0221036c…`, full test suite | Project owner (authorizes), coordinator / engineer (executes) | backup hash `19d83c42…`; post-apply hash; test log | R1, R2 | BLOCKED |
| R5 | Decide Amendment 03, then the patch set, plan v2 steps 5–12 and Amendment 01c | Project owner (+ independent reviewer countersignature) | approval records under the applied tooling | R3, R4 | BLOCKED |
| R6 | Decide Amendment 01 (candidates), the BASE-P2 failure policy, Amendment 02 and BASE-P2 registration | Project owner | approval records | R5; P2 for confirmatory runs | BLOCKED |
| R7 | Decide the M1 route: settle the protocol §3 interpretation ("candidate configuration"?), then choose A1, A2 or B | Project owner | written decision **before** any M1 outcome; route documents approved (`cv5_matching_rule_decision_memo_DRAFT.md`) | R3–R4 to record it; B also needs P2 | DRAFT |

## 2. Clinical review

| # | Task | Accountable role | Required evidence | Blocking dependencies | Status |
|---|---|---|---|---|---|
| C1 | Appoint a qualified clinical lead | Project owner | appointment record; the CL's own qualification statement | none | PENDING |
| C2 | Complete the governance decisions C1–C11 (`clinical_governance_readiness_v1.md`) | Clinical lead (+ project-owner countersignature) | completed `reports/templates/clinical_governance_decision_template.md`; approval record | C1, R4 | BLOCKED |
| C3 | Confirm reader-study requirements (ethics, confidentiality) | Institution / ethics committee | written confirmation | C1 | PENDING |
| C4 | Secure the coordinator files (5 files listed in `access_control_procedure_v1_PROPOSED.md` §2); decide `.gitignore` before any commit or push | Project owner (authorizes), coordinator (executes) | restricted copies with verified hashes; access-denied test by a second person | owner authorization | PENDING |
| C5 | Run blinded reading with worksheet v2 (`effa7db6…`) | Clinical lead and readers | signed results file (new version); original labels untouched | C2, C3, C4 | BLOCKED |

## 3. Test-set ledger

| # | Task | Accountable role | Required evidence | Blocking dependencies | Status |
|---|---|---|---|---|---|
| L1 | Record the two pending retrospective disclosures (`reports/p5_disclosure_entry.json` `c8f9b186…`; `kaggle/artifacts_external_run1/ledger_disclosure_entry.json` `91083588…`) | Accountable test-set authorizer | ledger entries via the ledger CLI, with a named authorizer; chain verified | none | PENDING |

## 4. Manuscript (current: `reports/manuscript/DentaMind_CV5_manuscript_v3_1_journal.docx`, `ed1e518b…`; v3 and v2 unchanged)

| # | Task | Accountable role | Required evidence | Blocking dependencies | Status |
|---|---|---|---|---|---|
| M1 | References: read every cited source and confirm it supports its sentence; confirm `guo` (ICML 2017, PMLR vol. 70, no DOI) and `bittar` (dated 2026: final volume and pages) | Authors | annotated reference check; corrected bibliography if needed | none | PENDING |
| M2 | Declarations: corresponding author (line 11); ethics statement and licence wording (line 67); ethics, funding, competing interests, CRediT contributions, code availability, AI-assistance statement, acknowledgements (lines 341–348) | Authors (ethics per institution) | filled text; nothing copied from the assistant's placeholders as fact | C3 for the ethics wording | PENDING |
| M3 | Licence wording: DENTEX is **CC BY-NC-SA 4.0** per the official Hugging Face page (checked 2026-10-25); cite **both** DENTEX papers (`hamamciArxiv`, `hamamciMiccai`, both already cited) | Authors | quoted licence text in §2.1 | none | PENDING |
| M4 | Prior test-split disclosure (§2.1 of v3.1): confirm the wording ("5 historical entries … two further baseline test evaluations is pending"). **Update the text if L1 is recorded before submission** | Authors + test-set authorizer | ledger state at submission time | L1 | PENDING |
| M5 | Journal choice, then reformatting to its template | Authors + guide | chosen venue with verified scope, fees and indexing (`submission_package_v2.md` §3 is guidance only) | none | PENDING |
| M6 | Overlap with earlier papers in `documents/` (prior submission or publication) | Authors + guide | declaration to the journal; similarity check by the journal | M5 | PENDING |
| M7 | Approval to submit | All four authors + guide | written agreement | M1–M6 | BLOCKED |
| M8 | Note: `submission_package_v2.md` and `publication_readiness_checklist_v2.md` refer to v2, and v2 says candidates "are registered". Do **not** use them as-is with v3.1 | Authors | an updated package when the venue is known | M5 | PENDING |

## 5. Data and compute (not available)

| # | Task | Accountable role | Required evidence | Blocking dependencies | Status |
|---|---|---|---|---|---|
| D1 | P2 clinician-verified labels (PL +171 findings / +106 radiographs; DC +283 / +150) | Clinical lead + readers | verified-label imports via the P1 route | C2, reviewer authorization | BLOCKED |
| D2 | External validation dataset (none eligible today) | Authors | licence, access, clinician label verification, frozen protocol (`external_validation_eligibility_v1.md`) | C1 | BLOCKED |
| D3 | Kaggle sessions for BASE-P2, candidates and calibration re-prediction | Project owner | session logs, archived outputs with SHA256SUMS | R6, D1 | BLOCKED |

## 6. Verified in this session vs not verified

**Verified:**
* all protected hashes, including:
  - pre-audit 8 / 8 and Amendment 01b 12 / 12;
  - protocol `0771b5f8…`, ledger `f117c1a3…`, `cv5_approvals.py` `19d83c42…`;
  - tooling patch `de92744b…`, packet `93894ca4…`;
  - manuscript v3.1 md `99c5d218…` and docx `ed1e518b…`; v3 `ec96748c…`; v2 `993c7b66…`;
* 30 relevant tests passed (tooling 13, M1 library 6, round-1 6, round-2 5);
* no `reports/approvals/` directory exists;
* the v2 worksheet holds no mapping, box or identifier;
* the file permissions and git status of the clinical-review folder;
* all 18 protocol quotes in the decision memo match the protocol text.

**Not verified:**
* whether the GitHub remote is public;
* the reviewer's own re-run of the tests;
* any human identity, decision or signature;
* that the readers cannot access restricted files (needs C4);
* that the cited sources support their sentences (M1);
* the journal requirements (M5).


---

## Addendum 2026-10-25 (status update; rows above unchanged)

**Factual status changes:**
* **C4 (secure coordinator files):** read-only inspection done.
  - Repository **public** on GitHub (`SAURABH11072004/Dental-X-ray-Gen-AI`).
  - Restricted files are not tracked, staged or in history, and not on the remote. They are untracked and **not git-ignored**.
  - All local accounts can read them; `saura` is an enabled non-admin account.
  - An extra restricted item was found: the CV5 archive `kaggle/dentamind_5fold_cv_artifacts.zip` contains a copy of
    `caries_confusion_findings.csv`.
  - Plan: `reports/security/clinical_files_access_control_plan_PROPOSED.md`. Status remains **PENDING owner approval**.
  - Baseline access test (`scripts/security/check_clinical_access.ps1`, as `chand`): FAIL, as expected; **access is not fixed**.
* **R1 (independent review):** handoff checklist `reports/review/R1_handoff_checklist_v1.md`. A minimal 4-file set was verified to
  reproduce 13 passed without the restricted files. Status remains **READY** (no reviewer named; nothing sent; no verdict).

**Proposed next actions (each needs the accountable human):**

| # | Task | Accountable role | Required evidence | Blocking dependencies | Status |
|---|---|---|---|---|---|
| S1 | Approve and apply plan Step 1 (`.gitignore` lines) **before any commit or push** | Project owner | `git check-ignore -v` output for F1–F6 | none | PENDING |
| S2 | Name coordinator, reviewer and test accounts; approve plan Steps 2–4 (exact `icacls` commands) | Project owner | written approval of the exact action list | S1 recommended first | PENDING |
| S3 | Run the access test as a non-privileged account; record the result | Test-account holder + second person | script output with RESULT: PASS | S2 executed | BLOCKED |
| S4 | Decide whether the GitHub repository should stay public (repository setting; outside this plan) | Project owner | owner decision | none | PENDING |
| S5 | Check copies outside the project folder (Kaggle outputs, downloads, backups, cloud sync) and the Kaggle notebook's visibility | Project owner | inventory | none | PENDING |
| R1a | Choose the IR and send H1–H7 with their hashes | Project owner | sent-message record with the hash table | none | PENDING |


---

## Addendum 2026-10-25 (research improvement round 2; rows above unchanged)

**Factual status changes:**
* **Production inference defect fixed.** A classifier sidecar missing preprocessing keys no longer runs silently with guessed
  preprocessing; it is now refused. 22 consistency tests were added; the full suite gives 590 passed. Details:
  `reports/research_improvement_round2.md` §4.
* **Leakage verified on artifacts:** fold plan 0 violations; split audit 0 overlaps.
* **S5 (external copies / Kaggle), partly done (read-only):**
  - Kaggle notebooks and the dataset are not publicly visible (anonymous 404 versus 200 for known public pages).
  - Restricted copies were found only in the assistant's session scratchpad (`dry_tree/`, `cv5_smoke/`).
  - Other machines, backups and cloud sync were not searched.
  - Status: PENDING the owner's confirmation in Kaggle settings, and approval to delete the scratchpad copies.
* **Recommended first research step:** blinded clinician re-reading (C1–C5 in this register). It needs no compute and no candidate
  budget.

**Proposed next actions:**

| # | Task | Accountable role | Required evidence | Blocking dependencies | Status |
|---|---|---|---|---|---|
| S6 | Approve deleting the assistant's scratchpad copies of restricted files (`scratchpad/dry_tree/`, `scratchpad/cv5_smoke/`) | Project owner | written approval; deletion confirmed by a name search | none | PENDING |
| S7 | Confirm in Kaggle that `dentamind-5-fold-cv-base` and the other project notebooks / dataset are private and not shared | Project owner | screenshot or note of the sharing settings | none | PENDING |
| E1 | Review and accept the production inference change (`registry.py`, `torch_models.py`; rollback copies in the scratchpad) | Project owner / engineer | code review; 590-test run | none | PENDING |
