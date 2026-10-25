# Experiment registration DRAFT: detector-to-finding matching rule M1 (one tooth box may serve several findings)

Date 2026-10-25.

**Status: DRAFT. NOT REGISTERED. NOT RUN.**
* It takes effect only through a human approval record bound to this file's SHA-256. The approval tooling and policy must be in force
  first.
* The existing matching rule, all archived results and manuscript v3 are unchanged.
* **No claim is made that M1 improves performance.**

## 1. Motivation (what was known at drafting time)
Source: `reports/cv5_error_attribution.md`, a descriptive analysis of archived CV5-BASE run 1 outputs. It passed three reproduction
gates.

| Known | Not known (never computed) |
|---|---|
| Structure: 55 primary findings (Caries 16, Deep Caries 14, Impacted 3, Periapical Lesion 22) are unmatched only because their IoU ≥ 0.5 tooth box was assigned to another finding ("U2") | the predicted class of any U2 finding under M1 |
| Reference end-to-end recall per class and seed (archived) | any M1 metric, delta, interval or verdict |
| 66–92 % of end-to-end errors come from classification on matched boxes | |

The drafter has not looked at the stored predictions of the boxes that U2 findings would inherit.

## 2. Status options (owner decides before approval; recommendation in bold)

| Option | What it is | Budget / multiplicity | Note |
|---|---|---|---|
| **A, pre-registered secondary analysis (recommended)** | a pipeline change evaluated on the archived reference predictions; it is not a CV5 classifier candidate and cannot be "ACCEPTED" under protocol §7 | uses no slot of the 15; its own single primary test at two-sided α = 0.05 (§6) | protocol §4.1 fixes one-to-one matching as the frame for **classifier** candidates; Option A leaves that frame untouched |
| B, new candidate family "F6 matching" | a confirmatory candidate under the acceptance protocol | needs an owner budget enlargement (15 → 16) **and** a multiplicity amendment (k = 16), per §10.1, before any run | heavier; it changes the Bonferroni level for every later candidate |

## 3. Algorithm (frozen at registration)
1. **Detector boxes:** the archived `kaggle/artifacts_cv5_run1/detector_boxes_pool.json`, score ≥ 0.3. No re-detection.
2. **Reference assignment:** greedy one-to-one by IoU ≥ 0.5 (`kaggle/dentamind_kaggle.match`). **It is never altered.**
3. **Fallback:** a finding left unmatched by step 2 gets the box with the highest IoU ≥ 0.5 among all boxes of its image. Ties are
   broken by higher detector score, then lower box index.
4. **Inherited prediction:**
   - the fallback box's crop is the crop already classified for its reference owner (same image, so the same radiograph group and
     the same fold);
   - the finding takes the owner's stored out-of-fold detector-box prediction for each seed;
   - **no new inference.**
5. **Overlapping findings:** findings sharing one box receive the same predicted class. If their true classes differ, at most one is
   correct. Each finding counts once in every metric (a shared wrong prediction is a false positive for the predicted class).
6. **Implementation:** `scripts/cv5_matching_m1.py`, a library with no entry point.
   - Its tests in `tests/test_cv5_matching_m1.py` use synthetic data only.
   - They check: the reference part is identical to production; shared-box handling; no low-overlap fallback; tie-breaking; refusal
     when a fallback box has no owner; and that end-to-end recall cannot decrease.

## 4. Evaluation
* **Population:** all 2,851 primary findings (CV5 held-out predictions, seeds 42–46). The 159 secondary findings are excluded, as in
  the protocol. No calibration or test data is used.
* **Unit and pairing:** finding × seed, paired between the reference rule and M1 (same classifier predictions). Uncertainty unit:
  the radiograph.
* **Primary metric:**
  - **end-to-end macro-F1** over the four classes and all primary findings, where an unmatched finding is a false negative of its
    class and a false positive of none (`end_to_end_scores`);
  - statistic: the seed-mean Δ (M1 − reference).
* **Secondary metrics** (reported with 95 % CIs, not tested):
  - end-to-end recall, precision and F1 per class;
  - the number of newly matched findings per class;
  - the detector-matched setting under each rule. Its denominator differs between rules, so it is descriptive only.
* **Class safeguards** (fail if violated). By construction end-to-end recall cannot decrease, so the safeguards target precision:
  - **SG1:** seed-mean Δ end-to-end precision ≥ −0.04 for Deep Caries and for Periapical Lesion (the protocol's S3 / S4 margins);
  - **SG2:** seed-mean Δ end-to-end F1 ≥ −0.02 for Caries and Impacted, and ≥ −0.03 for Deep Caries and Periapical Lesion (the
    protocol's S5 margins);
  - **H (hard harm):** fail if the unadjusted 95 % paired bootstrap upper bound of Δ end-to-end precision is < 0 for Deep Caries or
    for Periapical Lesion.
* **Uncertainty:**
  - a paired radiograph-level percentile bootstrap: resample radiograph groups with `default_rng(0)` and B = 20,000; recompute both
    arms on each draw; take the seed-mean Δ;
  - this is the protocol's Appendix C procedure.

## 5. Decision rule (Option A)
* **IMPROVED:** all of the following hold.
  - the seed-mean Δ end-to-end macro-F1 is > 0;
  - the two-sided 95 % bootstrap lower bound is > 0;
  - Δ > 0 in ≥ 4 of 5 seeds and in ≥ 4 of 5 folds;
  - SG1, SG2 and H all pass.
* **NOT IMPROVED:** any of the above fails while the gates pass.
* **NO VERDICT:** any gate in §7 fails.
* **Minimum effect.** No minimum effect δ is set. Only 55 findings can change, so the achievable effect is small by design.
  - An owner who requires a practical threshold must fix it **before approval**, without computing any M1 outcome.
  - Under Option B, the protocol's δ = 0.027 applies unchanged.

## 6. Multiplicity
* **Option A:**
  - one primary hypothesis at two-sided α = 0.05;
  - the safeguards are failure conditions, not additional tests for success;
  - secondary metrics are estimation only.
  - This analysis does not draw on the CV5 candidate budget. It is disclosed in every report as a separate pre-registered analysis.
* **Option B:**
  - level 1 − 0.05/k with k = 16 after the required amendment;
  - otherwise exactly protocol §5.

## 7. Gates (all must pass, or NO VERDICT)
* **G1:** the fold file SHA-256 is `9b767a48…`. The archived inputs (`oof_predictions.csv`, `detector_boxes_pool.json`,
  `cv5_results.json`) match `SHA256SUMS.txt`, and the manifests equal the CV5 bundle copies.
* **G2:** the reference arm, recomputed, reproduces the archived matched flags for every finding and the archived per-seed end-to-end
  recall exactly (as in `scripts/cv5_error_attribution.py`).
* **G3:** every fallback box has a reference owner in the same image and fold, so no new inference is needed.
* **G4:** the number of fallback findings per class equals the U2 counts in §1: 16 / 14 / 3 / 22.

## 8. Reporting
* Every outcome is reported, including NOT IMPROVED and NO VERDICT. It is labelled "pre-registered secondary analysis of the matching
  rule" (Option A).
* It is not a classifier improvement, not a clinical result and not a test-set result.
* Manuscript changes go into a new version; v3 stays unchanged.

## 9. Preconditions before any run
1. The approval policy is adopted and the approval-tooling patch is applied (review packet
   `reports/review/approval_tooling_review_packet_v1.md`).
2. The owner chooses Option A or B and fills §5 (any δ). This file is then frozen, and its SHA-256 is approved with an approval
   record (scope to be defined in the policy; a matching-analysis scope does not yet exist in the tooling).
3. Under Option B, the budget enlargement and multiplicity amendment are approved first.
4. A reviewed run script is written; it wraps `scripts/cv5_matching_m1.py`, gates G1–G4 and the bootstrap. Compute is local CPU, with
   no training and no GPU.


---

## Addendum 2026-10-25: status options re-assessed (draft unchanged above)
* The recommendation in section 2 ("Option A ... uses no slot ... leaves that frame untouched") is **incomplete**. Protocol section 3
  states: "No candidate configuration is trained or evaluated on the 541 primary radiographs of `cv5_folds_v1.csv` (or their folds)
  except as a registered confirmatory candidate."
* Confirmatory comparisons cannot start before P2 is met.
* Whether M1 counts as a "candidate configuration" is an owner decision.
* Updated options (A1 own protocol, A2 exploratory amendment, B confirmatory family): `reports/cv5_matching_rule_decision_memo_DRAFT.md`.
* This registration remains NOT REGISTERED and NOT RUN.
