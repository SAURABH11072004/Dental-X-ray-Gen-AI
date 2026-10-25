# DentaMind AI: research improvement report, round 1 (2026-10-25)

All statements below were checked against files in this session. "Measured" means it was run here.

## 0. State verified before any work
* **Integrity:** pre-audit 8 / 8; Amendment 01b change set 12 / 12; CV5 archive 88 / 88 entries.
* **Protected files:** protocol `0771b5f8…`, CV5 results `52d94923…`, fold file `9b767a48…`, archive `4ac56843…`, ledger `f117c1a3…`,
  `dentamind_kaggle.py` `879faa93…`, `cv5_lib.py` `72084f9b…`, bundle v3 `9d070fc7…`, patch set `55271334…`, tooling patch
  `de92744b…`, manuscript v2 `5d754f84…` (docx) / `993c7b66…` (md). **No integrity failure.**
* **Approvals:** there is no `reports/approvals/` directory and no approval record, register, log, reviewer authorization or import
  manifest. Amendments 01, 01b, 02 and 03 are DRAFT; 01c is an empty skeleton. Details:
  `reports/cv5_candidate_run_readiness_v1.md`.

## 1. Ranked results

| Rank | Improvement | Outcome | Evidence |
|---|---|---|---|
| 1 | **Latency** | **MEASURED** on the RTX 3050 Laptop GPU, run twice. Classifier: 4.96 ms per crop at batch 1 and 2.91 ms at batch 64 on GPU; 65.4 ms at batch 1 on CPU. End-to-end: median 251.3 ms per radiograph (second run 241.7 ms) | `scripts/benchmark_latency.py`; `reports/latency_benchmark_rtx3050_run{1,2}.*` |
| 2 | **Error attribution** | **COMPLETED** from archived outputs; all 3 reproduction gates passed. The detector misses only 3 findings. 22 of 29 unmatched periapical lesions are matching conflicts (one tooth box, several findings). Deep caries is lost mostly to box-extent mismatch. Classification causes 66–92 % of end-to-end errors | `scripts/cv5_error_attribution.py`; `reports/cv5_error_attribution.*` |
| 2b | Matching / detector candidate | **PROPOSED, not evaluated** (evaluating it now would be post-hoc selection) | `reports/cv5_matching_rule_proposal_DRAFT.md` |
| 3 | Clinician re-reading of the 110 findings | **PREPARED, BLOCKED** (no clinical lead, no data-sharing confirmation). Blinded worksheet of 220 items: 110 targets and 110 class-matched controls, with no label or model output shown; coordinator key kept separate | `scripts/build_clinician_review_queue.py`; `reports/clinical_review/*` |
| 4 | Calibration | **REGISTRATION DRAFTED; code and tests ready; NOT RUN.** Temperature scaling cannot change macro-F1, so it needs its own endpoints (NLL primary) | `reports/cv5_calibration_experiment_registration_DRAFT.md`; `src/dentexmodel/uncertainty/temperature.py`; `tests/test_temperature_scaling.py` |
| 5 | External validation | **ELIGIBILITY ASSESSED; no eligible verified source yet.** Cluj failed the label check; Hanoi is positives only; the DENTEX official test release is not independent; Tufts needs access; institutional data needs an agreement | `reports/external_validation_eligibility_v1.md` |
| 6 | Published-method comparison | **FEASIBILITY ASSESSED.** HierarchicalDet (MIT, code only, no weights) solves a detection / AP task, not comparable without same-fold retraining plus a frozen conversion rule. It would be a new candidate | `reports/published_method_comparison_feasibility_v1.md` |
| 7 | Registered candidates C1–C3 | **NOT READY**: every approval gate is missing; nothing trained | `reports/cv5_candidate_run_readiness_v1.md` |
| – | Manuscript | **v3 created** (v2 preserved): adds Section 2.9 / 3.4 / Table 3 / Fig. 6 (attribution) and Section 2.10 / 3.8 / Table 5 (latency), and corrects v2's statement that candidates "are registered" (they are drafted only). Audit: 222 traced, 0 untraced; the Word file matches the source | `reports/manuscript/DentaMind_CV5_manuscript_v3_journal.{md,docx,pdf}`; `manuscript_v3_number_audit.md` |

**Correction notice:** manuscript v2 (§4.4) and `submission_package_v2.md` (reviewer table) say the candidates are "registered".
That is inaccurate: Amendment 01 is an unregistered draft. Both v2 files are kept unchanged as records; use v3.

## 2. Dependency graph

```
LOCAL, DONE NOW ......... latency (measured) · error attribution · review queue · calibration code · eligibility · feasibility · manuscript v3
                                       │
HUMAN AUTHORIZATION ..... [IR] review tooling patch → [PO] adopt policy + register v1 → apply tooling patch
                                       ├─► [PO] Amendment 03 → [PO+IR] patch set → plan v2 steps 5–12 → Amendment 01c
                                       ├─► [PO] Amendment 01 (C1–C3; optionally M1 matching, HierarchicalDet) → Amendment 02 → BASE-P2
                                       └─► [PO] calibration amendment (separate endpoints)
CLINICIAN ............... [PO] appoint clinical lead → governance decision → blinded re-reading (220 items) → signed results file
LICENSED DATA ........... authors choose an external source → access + licence → clinician label verification → frozen external protocol
KAGGLE COMPUTE .......... BASE-P2 run · C1–C3 runs · calibration re-prediction (inference only) · HierarchicalDet pilot
LOCAL COMPUTE (after OK). M1 re-scoring (no training) · external inference (RTX 3050 sufficient)
```

## 3. Single highest-value next action
**An independent reviewer reviews `patches/cv5_approvals_policy_tooling.patch`, and the project owner adopts the approval policy.**
Every experiment that could change the paper's conclusions depends on that step:
* candidates;
* matching rule M1, which is cheap: re-scoring only;
* calibration;
* BASE-P2.

**In parallel, appoint a clinical lead.** This unblocks the re-reading, which needs no compute.
