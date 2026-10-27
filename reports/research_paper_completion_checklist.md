# Research paper completion checklist

Date 2026-10-25. The paper documents in `documents/` are **not modified** by this checklist.

* Every number cited below is copied from the named evidence file.
* No candidate result exists. No improvement over BASE and no clinical validity may be claimed.
* Authors (keep exactly): Nilesh Sonawane, Saurabh Mali, Sadhyoj Hanwate, Sachet Lothe. Guide: Dr. Pradnya Narkhede, Department of
  Computer Engineering, PCCOE, Pune.

## 1. Sections that can be written now from existing evidence

| Section | Evidence | Note |
|---|---|---|
| System description (DentaMind pipeline: tooth detector → finding classifier → abstention → report) | code, `reports/training_summary.md` | describes the research prototype; no deployment claim |
| Data: DENTEX, project splits, radiograph grouping, leakage rule | `reports/combined_split_audit.json`, `reports/cv5_folds_v1_summary.md`, `reports/training_summary.md` | include the 95 / 250 official-test duplicates finding |
| Evaluation methodology: grouped 5-fold CV (unit = radiograph), inner validation, seeds, radiograph bootstrap | `reports/cv5_protocol.md`, `reports/cv5_results.md` | pre-registered; no amendments |
| Acceptance protocol for future candidates | `reports/cv5_acceptance_protocol.md` (rev 3) | describe as a pre-specified protocol; **no candidate has been evaluated** |
| Negative results: imbalance strategies, external data (X2_hanoi), 5-seed ensemble | `reports/training_summary.md`, `reports/external_data_results.md`, `reports/ensemble_evaluation.md` | all FAIL under their own rules; report as such |
| Reproducibility and integrity measures | test-set ledger, SHA256SUMS, training manifests, `reports/cv5_candidate_path_freeze.md` | — |

## 2. Verified BASE CV results (cite exactly; `reports/cv5_results.md`)
* **Population:** 2,851 out-of-fold `dentex_train_disease` findings from 541 radiographs; 2,745 detector-matched.
* **Detector-box macro-F1:** **0.677 ± 0.008** over seeds 42–46 (radiograph bootstrap 95 % CI 0.652–0.701).
* **GT-box macro-F1:** **0.698 ± 0.007** (CI 0.675–0.718).
* **Fold-level macro-F1:** 0.675 ± 0.032 (detector), 0.697 ± 0.020 (GT). This is descriptive; folds are not independent replicates.
* **Weak classes, detector boxes:** Deep Caries recall 0.440 ± 0.018; Periapical Lesion recall 0.432 ± 0.033.
* **Main confusions:** DC → Caries (45 % of GT-box DC predictions); PL → Caries (36 %).
* **Calibration:** raw-softmax ECE about 0.11 out of fold.
* **Limitations to state with these numbers:**
  - The bootstrap covers radiograph resampling given the trained models, not training-set variation.
  - Five models, each trained on about 380 radiographs.
  - Detector-box results partly use radiographs from the detector's training set. The detector-unseen subset gives 0.685, but rests
    on only 331 findings.
  - These are not test results and are not comparable with earlier single-split numbers.

## 3. Candidate results: unavailable
* C1 (384 px crops), C2 (0.25 context padding), C3 (ConvNeXt-Tiny): implemented and pre-flight tested only. They are **not
  registered** (Amendment 01 unsigned) and **not trained**.
* **No ACCEPT / FAIL / NO VERDICT exists for any candidate.** Placeholder text must say "not yet evaluated". It must not show expected
  values.
* BASE-P2: not registered and not run (blocked by data).

## 4. Data and clinician-review milestones required first
1. P2 met: PL +171 findings / +106 radiographs; DC +283 / +150. Clinician-verified through the P1 route (`reports/data_acquisition_checklist.md`).
2. Gate V6 passed on the frozen imports manifest.
3. Amendments 01 (signed), 01b (implementation freeze) and 02 (BASE-P2) in force.
4. BASE-P2 and candidate CV runs completed, with verdicts under protocol rev 3.
5. At most one ledger-recorded test evaluation of the V-a artifact, only after a confirmatory ACCEPT.

## 5. Mandatory disclosures
- [ ] **No patient identifiers in DENTEX.** Independence is at radiograph level only; no patient-level generalisation is claimed.
- [ ] **Prior test-set use:**
  - the internal test split has 5 historical ledger entries;
  - two BASE test evaluations (2026-10-16, 2026-10-24) have disclosures **pending the accountable person's authorization**;
  - any future test number is not an untouched estimate.
- [ ] **Selection effects:**
  - all confirmatory candidates share the same 541 evaluation radiographs;
  - the winner's gain is optimistically biased;
  - the fold 0 report used for the final artifact is not independent confirmation of the winner;
  - the margin rule was written knowing the earlier single-split results.
- [ ] **Synthetic pre-flight testing:** the candidate pipeline was exercised on synthetic data with an untrained fake trainer. This
      verifies engineering only and says nothing about model performance.
- [ ] **Single-centre data** (DENTEX). The external-data experiment failed. No multi-centre claim.
- [ ] **Label ambiguity:** the 110-finding Caries / Deep Caries review list is a clinician-review request, not a set of label errors.

## 6. Claims that must stay unsupported until further experiments exist
* Any candidate improving on BASE, or "state of the art".
* Clinical validity, clinical acceptability, diagnostic accuracy in practice, or readiness for deployment.
* Generalisation to other centres, devices or populations, or patient-level performance.
* Effects of the additional (P2) data.
* Calibrated probabilities after post-hoc calibration (not studied under any protocol).

## 7. Submission prerequisites
- [ ] All numbers traced to evidence files (a QC pass like `documents/Research_Paper_QC_Report.md`, redone against `cv5_results.md`).
- [ ] The two pending ledger disclosures recorded by the accountable person, so the test-history statement is complete.
- [ ] The venue's ethics / data-use statement for DENTEX and any new source (licence and provenance from the data checklist).
- [ ] Author list and affiliation exactly as above. Contribution statement agreed by the authors.
- [ ] Code / data availability statement listing hashes of the frozen code and of the archived CV5 artifacts (`4ac56843…`).
- [ ] Similarity and AI-detector checks run by the authors. **No guaranteed outcome is claimed.**
- [ ] Owner decision to update the paper. The paper is not edited until then.
