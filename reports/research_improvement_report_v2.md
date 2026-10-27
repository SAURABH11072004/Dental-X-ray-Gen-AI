# DentaMind AI: research improvement report, round 2 (2026-10-25)

Scope: preparing the independent review, the matching-rule registration, clinical-governance readiness, and the manuscript evidence
audit.
* No patch was applied.
* No approval, register, log or reviewer authorization was created.
* No image was shared and no data request was sent.
* No unregistered experiment was run, no test data was accessed, nothing was trained, and nothing was committed.

## 1. Integrity and tests (verified in this session)

| Item | SHA-256 (prefix) | Status |
|---|---|---|
| Protocol `reports/cv5_acceptance_protocol.md` | `0771b5f8` | unchanged |
| CV5 results `kaggle/artifacts_cv5_run1/cv5_results.json` | `52d94923` | unchanged; archive 88 / 88 entries OK |
| Fold file `data/splits/cv5_folds_v1.csv` | `9b767a48` | unchanged |
| Archive `kaggle/dentamind_5fold_cv_artifacts.zip` | `4ac56843` | unchanged |
| Ledger `Data/reports/test_set_ledger.json` | `f117c1a3` | unchanged; 5 entries |
| BASE code `kaggle/dentamind_kaggle.py` / `kaggle/cv5_lib.py` | `879faa93` / `72084f9b` | unchanged |
| Approvals module `kaggle/cv5_approvals.py` | `19d83c42` | unchanged (patch not applied) |
| Frozen generator `kaggle/make_cv5_notebook.py` | `4a5efda8` | unchanged |
| Patch set manifest; patches 1–3 | `55271334`; `33ec47e6`, `5e406287`, `31a2ba15` | unchanged |
| Approval-tooling patch | `de92744b` | unchanged; `apply --check` OK |
| Manuscript v3 (md / docx / audit) | `ec96748c` / `c83174ae` / `e918f092` | unchanged |
| Manuscript v2 (md / docx) | `993c7b66` / `5d754f84` | unchanged |
| Pre-audit set; Amendment 01b change set | – | 8 / 8; 12 / 12 |
| Working tree | – | the same 21 pre-existing modified files; 1 commit |

* **Tests:** the suite started at 553 passed and ended at **568 passed, 0 failed**. The 15 new tests are:
  - 4 supplementary tooling-review tests;
  - 6 M1 library tests (synthetic data);
  - 5 round-2 tests.
* **Integrity:** no protected hash differed.

## 2. Independent-review packet (approval tooling)
`reports/review/approval_tooling_review_packet_v1.md` (`93894ca4…`) contains:
* the exact patch, verbatim;
* the before-hash `19d83c42…` and the after-hash on a temporary copy `0221036c…`;
* scope and `POLICY` behaviour;
* the test evidence: 13 passed, 9 original plus 4 supplementary in `tests/test_cv5_approval_tooling_review_extra.py`;
* application, rollback and the reviewer checklist;
* six known limitations.

**Confirmed behaviours:**
* records are never overwritten;
* self-countersignature is rejected, including the same person under a second role (new test);
* a wrong scope, a wrong artifact or an edited artifact is rejected (new test);
* invalid ordering is rejected (missing predecessor, approval before the artifact, retrospective, advance);
* unauthorized or revoked roles are rejected;
* future-dated approvals are rejected.

**New observation R1 (low severity):** `make_approval_record` (live code) does not validate the scope at creation. Such a record can
never verify.

## 3. Matching-rule registration (draft)
`reports/cv5_matching_rule_registration_DRAFT.md` (`b2160a35…`) specifies:
* **Algorithm:** the reference one-to-one assignment is kept unchanged, plus a highest-IoU fallback for findings that lost their tooth
  box.
* **Overlapping findings:** they share one predicted class.
* **Evaluation:** all 2,851 primary findings; the primary metric is end-to-end macro-F1 (seed-mean Δ).
* **Safeguards:** precision and F1 safeguards plus a hard-harm rule. End-to-end recall cannot decrease by construction, so precision is
  the risk.
* **Uncertainty:** a paired radiograph bootstrap with B = 20,000.
* **Multiplicity:** Option A (recommended) is a secondary analysis at α = 0.05 using no budget slot. Option B is a new family F6,
  which needs a budget enlargement and k = 16.
* **Gates:** G1–G4.
* **Verdicts:** IMPROVED, NOT IMPROVED or NO VERDICT.

Two constraints found during drafting:
* Protocol §4.1 fixes one-to-one matching as the frame for classifier candidates, and no family covers matching. So this is not a
  routine Amendment 01 entry.
* `scripts/cv5_matching_m1.py` is a library with **no entry point**, tested on synthetic data only. **M1 has not been applied to CV5
  data and no M1 result exists.**

## 4. Clinical-governance readiness
`reports/clinical_review/clinical_governance_readiness_v1.md` (`76bd5c3b…`):
* **Blinding defect found in worksheet v1:** the DENTEX file name, image hash and exact box can be matched against the **public** DENTEX
  annotations to reveal the label.
* **Worksheet v2** (`effa7db6…`) contains only the review ID, an opaque image code, the FDI tooth and empty answer fields.
  - The mapping and box are in the coordinator-only key v2 (`c459f5da…`).
  - v1 is kept unchanged as a record and must not be given to reviewers.
* **Licence:** the official Hugging Face page (checked today) states CC BY-NC-SA 4.0 for all DENTEX elements. Showing images to
  reviewers for non-commercial research is within that licence. Institutional and ethics confirmation is still open.
* **Clinical-lead decision checklist:** C1–C11, all open. No clinical lead, credential or decision was invented.
* **Manual step:** the coordinator must move the keys and the v1 worksheet out of reviewers' reach.

## 5. Manuscript audit
**Re-checks of v3** (`ec96748c…`):
* **Number audit:** PASS, 222 traced, 0 untraced. The re-run report is **byte-identical** to the original v3 audit (`e918f092…`).
* **Citations:** 16 / 16 keys found. Flags: `guo` has no DOI; `bittar` is dated 2026; the other 4 flags are uncited entries.
* **Claims audit** (new tool `scripts/audit_manuscript_claims.py`): **FAIL** on one rule. v3, like v2, omits the disclosure that the
  internal test split was used earlier (5 ledger entries, 2 pending disclosures). The v1 draft contained it.

**Fix in v3.1** (`DentaMind_CV5_manuscript_v3_1_journal.*`; md `99c5d218…`, docx `ed1e518b…`, 21 pages):
* §2.1 now states the earlier test-split use; nothing else changed.
* **Number audit:** PASS (222 traced, 0 untraced).
* **Claims audit:** PASS (15 required statements present; no unnegated forbidden claim).
* **Citations:** same flags as v3.
* **Word file:** matches the source.
* v3 stays unchanged.
* The first v3.1 audit run flagged the version label "3.1" in the build note as an untraced number. I reworded the note and
  regenerated those three minutes-old v3.1 audit files.

**Confirmed in v3 / v3.1 text:**
* classifier-only and full-pipeline latency are reported separately (Table 5);
* the latency checkpoint is stated not to be a stored CV5 fold checkpoint;
* the uncontrolled power and thermal state is stated;
* no deployment-readiness, external-validation, clinical-validation or improvement claim is made;
* negative results are labelled as coming from the fixed validation split and not comparable with CV5.

**Use v3.1 going forward.** `submission_package_v2.md` and `publication_readiness_checklist_v2.md` refer to v2, and v2 says the
candidates "are registered". Those files are kept as records.

## 6. Remaining human approvals and data dependencies

| # | Who | What |
|---|---|---|
| 1 | Independent reviewer | review the tooling patch with the packet; record a verdict bound to `de92744b…` |
| 2 | Project owner | adopt the approval policy; issue approver register v1; approve and apply the tooling patch (backup → apply → after-hash `0221036c…` → tests) |
| 3 | Project owner | choose Option A or B for M1, set any δ, and approve the frozen registration; Option B also needs a budget and multiplicity amendment |
| 4 | Project owner | Amendment 03; patch set; Amendment 01c; Amendment 01; BASE-P2 failure policy; Amendment 02; BASE-P2 registration |
| 5 | Project owner → clinical lead | appoint a qualified CL; the CL decides C1–C11; PO countersigns |
| 6 | Institution / ethics | confirm reader-study requirements and reviewer confidentiality |
| 7 | Coordinator | separate the keys and the v1 worksheet; set up a viewer with coded images |
| 8 | Accountable test-set authorizer | record the two pending ledger disclosures (`c8f9b186…`, `91083588…`) |
| 9 | Authors / guide | confirm the licence wording (CC BY-NC-SA 4.0) and citation of both DENTEX papers; `guo` / `bittar` references; declarations; venue; overlap with earlier papers |
| 10 | Data | an eligible external dataset (none verified); P2 clinician-verified labels (0) |
| 11 | Compute | Kaggle sessions for BASE-P2, candidates and calibration re-prediction; M1 needs local CPU only once approved |

**Single highest-value next action:** the independent reviewer reviews `reports/review/approval_tooling_review_packet_v1.md`.
