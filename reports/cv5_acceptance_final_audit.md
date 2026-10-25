# Final consistency audit: `reports/cv5_acceptance_protocol_proposal.md` (revision 2)

Date 2026-10-24. **Audit findings only.**
* The proposal was not edited and remains **NOT APPROVED**. No experiment was started, and no model, production file, paper, result or
  ledger was changed.
* Everything was checked against files on disk, with read-only commands.

## 0. Audited files (SHA-256 at audit time)

| File | SHA-256 |
|---|---|
| `reports/cv5_acceptance_protocol_proposal.md` (audited) | `98d6e2233110ef93075c06b79261ccba4ce57dd22f72fa5af7e31b68cc02b9c0` |
| `reports/cv5_protocol.md` | `7f9df866f997d983aeb4de981917ce35107ab8c3b5d8a771a4f34153fd47c56f` |
| `reports/cv5_results.md` | `020a0bffb7f5e147e7e66cec0d92c7796676558a7da7f2fa3018449e74c31c9b` |
| `kaggle/artifacts_cv5_run1/` (88 files) | all entries of `SHA256SUMS.txt` verify; `cv5_results.json` `52d94923…`, `oof_predictions.csv` `a90d16d8…` |
| `data/splits/cv5_folds_v1.csv` | `9b767a4822844ccf0c4bf33d299e6e37420d1458a38035af0c3a3cb9107b47a6` (= approved hash) |
| `reports/cv5_base_noise.json` / `scripts/cv5_base_noise.py` | `4f277bdb…` / `df92e36f…` |
| `reports/protocol_change_proposals.md` (P1–P5) | `dbc326f6…` |
| `reports/expanded_class_distribution.csv` (P2 status) | `170ca185…` |
| `Data/reports/test_set_ledger.json` | `f117c1a3…` (5 entries; unchanged since 2026-10-16) |

**Verdict key:**
* **PASS:** consistent and unambiguous.
* **PASS with note:** consistent, but a wording or detail should be tightened before approval.
* **GAP:** an inconsistency or undefined point that must be resolved before approval.

---

## 1. Thresholds defined and traceable (check 1)

| Threshold in proposal | Value | Stated source | Verified against | Result |
|---|---|---|---|---|
| Minimum gain δ (P-A) | ≥ 0.027 | `ACCEPT["gain_min"]` + owner D1 | `kaggle/dentamind_kaggle.py:37` `gain_min: 0.027` | PASS with note N1 |
| Bootstrap (P-B) | 95 % percentile, 2,000 resamples, seed 0, radiograph unit | CV5 protocol §5 | `kaggle/cv5_lib.py:35` `BOOT_N, BOOT_SEED = 2000, 0` | PASS |
| Seed wins (P-C) | ≥ 4/5 | `ACCEPT["seed_pairs_min"]` + D2 | `dentamind_kaggle.py:37` `seed_pairs_min: 4` | PASS |
| Fold wins (P-D) | ≥ 4/5 | owner D2 (judgement, not data-derived) | owner instruction 2026-10-24 | PASS (source is owner judgement, stated as such) |
| S1 DC recall | 0.03 | margin rule, BASE 2-vs-3 max 0.0289 (det) | `cv5_base_noise.json` → 0.0289 | PASS |
| S2 PL recall | 0.05 | 0.0467 (det) | 0.0467 | PASS |
| S3 DC precision | 0.04 | 0.0321 (det) | 0.0321 | PASS |
| S4 PL precision | 0.04 | 0.0341 (det) | 0.0341 | PASS |
| S5a–d F1 C / DC / Imp / PL | 0.02 / 0.03 / 0.02 / 0.03 | 0.0041 (floor) / 0.0265 / 0.0099 (floor) / 0.0293 (det) | 0.0041 / 0.0265 / 0.0099 / 0.0293 | PASS |
| S6 GT macro-F1 | 0.02 | 0.0097 (GT, floor) | 0.0097 | PASS |
| ECE flag | > +0.03 | owner D8 (judgement); BASE observed ECE 0.107 | `cv5_results.json` det ECE 0.1071 | PASS |
| Latency flag | > 2× BASE | owner D8 (judgement) | – | GAP N2 (the BASE latency reference is not specified) |
| GPU-hours reference | BASE 1.37 h | CV5 run | README of the archive: 1.37 h **total notebook runtime** | PASS with note N3 |
| Candidate cap | ≤ 3 per family per round | owner D9 | – | PASS; see G6 (rounds not capped) |
| Retry attempts | 3 | (implicit) | `dentamind_kaggle.py:535` `attempts=3` | PASS (the source should be cited) |
| Multiplicity | Bonferroni on P-B | proposed only (U6) | – | open (U6) |

**Margin rule:** the rule (round the BASE 2-vs-3 max |Δ| up to the next 0.01, floor 0.02) reproduces every one of the ten margins
exactly from `cv5_base_noise.json`. No margin was set by hand.

**Observed BASE numbers in proposal §1 and §1.1:** all were re-read from `cv5_results.json` and `cv5_base_noise.json`, and all match:
* 0.677 ± 0.008, CI 0.652–0.701;
* 0.698 ± 0.007, CI 0.675–0.718;
* DC 0.546/0.440/0.487 and 0.576/0.496/0.533;
* PL 0.401/0.432/0.416 and 0.485/0.451/0.467;
* fold-level 0.675 ± 0.032 and 0.697 ± 0.020;
* single-seed pair maxima, bootstrap SD 0.013, fold-level max 0.073 / SD 0.029;
* 100 detector-matched PL findings.

The noise JSON's per-seed macro-F1 and PL recall equal the CV5 results to within 1e-12 for every seed and both settings.

**Notes:**
* **N1:** the old rule used a strict `> 0.027` (`dentamind_kaggle.py:501`). The proposal uses `≥ 0.027`, following the owner's D1/D2
  wording, yet describes δ as "unchanged from `ACCEPT`". The value is unchanged; the operator is not. **Recommendation:** state the
  change explicitly. Also state that all comparisons use unrounded floating-point values; rounding before the comparison could change
  a borderline verdict.
* **N2:** the latency flag needs a defined BASE reference and measurement. **Recommendation:** re-measure one BASE checkpoint in the
  same session, on the same GPU, with the same script as the candidate. Raise the flag if **either** the batch-64 per-crop **or** the
  single-crop latency exceeds 2×. The ensemble report's 2.9 / 7.7 ms are a different session and should not be the reference.
* **N3:** 1.37 h includes image download and detector inference. **Recommendation:** report both the total notebook runtime and the
  sum of per-run training times from `runs/*__result.json`, for the candidate and BASE.

## 2. Paired radiograph-level CI (check 2): PASS with note

* §5.1 P-B: "resample the primary radiographs with replacement; both arms on the same resampled findings; statistic = seed-mean
  candidate − seed-mean BASE". The CI is therefore built from candidate-minus-BASE differences, recomputed on the **identical
  resampled radiographs** for both arms. §4.2 pairs each candidate prediction with the BASE prediction for the same finding, fold and
  seed.
* **Note N4:** three details are implied but not written. They should be spelled out before approval:
  - all 10 model arms (5 candidate seeds, 5 BASE seeds) use the **same** radiograph draw in each resample;
  - in the detector setting, the 541 primary radiographs are resampled and unmatched findings are dropped **after** resampling, as in
    `cv5_lib.cluster_bootstrap(valid=…)`;
  - the safeguard CIs use the same procedure.
* **Implementation status:** the existing `cluster_bootstrap` is single-arm. The paired version does not exist yet, and the proposal
  says (§12) it is to be implemented and tested only after approval. Consistent.

## 3. Win counts, ties, failure handling (check 3)

| Item | Finding | Result |
|---|---|---|
| Seed wins | §5.1 P-C: seed s vs seed s, pooled out-of-fold macro-F1. The setting (detector boxes) is inherited from the §5 heading, not repeated in the row | PASS with note N5: write "detector boxes, matched findings" into P-C |
| Fold wins | §5.1 P-D: per held-out fold, seed-mean candidate vs seed-mean BASE macro-F1 on the fold's matched findings | PASS |
| Ties | §5: "beats means Δ > 0 strictly; a tie counts as not beating" | PASS |
| Infrastructure failure | resume the identical config and seed, ≤ 3 attempts, then NO VERDICT; folds and seeds never dropped or substituted | PASS |
| Divergence | "NaN/inf loss, collapse to one class on inner-validation" → FAIL | **GAP G1:** "collapse to one class" is undefined, and so is who classifies a failure as infrastructure vs divergence |
| Bug after results | whole candidate rerun, both runs reported, thresholds unchanged | PASS |

* **G1 recommendation:**
  - define collapse as "at the selected epoch, ≥ 99 % of inner-validation predictions are one class";
  - classify a failure as infrastructure only if the log shows an exception outside the loss computation (CUDA error, OOM, timeout,
    session loss);
  - treat everything else as divergence.
  - Both definitions should be fixed before approval.

## 4. All primary checks and safeguards required (check 4): PASS, conditional on U7

* §5.4: ACCEPT only if V1–V5, P-A to P-D and S1–S6 all pass, and the comparison is confirmatory. "No partial accept".
* S7 and the hard-harm rule are written as "if approved". Until U7 is decided, the exact list of required safeguards is not final.
  This is correctly flagged as open, not silently assumed.

## 5. No confirmatory work before P2 and clinician verification (check 5)

* **Consistent:**
  - §3 and §5.4 restrict ACCEPT to confirmatory comparisons, which "start only when the P2 data targets are met".
  - The current P2 status quoted (PL 129/94 vs ≥ 300/200; DC 467/250 vs ≥ 750/400; 0 new clinician-verified labels) matches
    `reports/expanded_class_distribution.csv` rows 32 and 34 and the "verified (clinician, new) … 0" row.
* **GAP G2: clinician-verification route not stated as a condition.**
  - P2 counts "verified labels, no duplication".
  - P1 (approved with hardening) admits new labels only through `verified_to_manifest.py`, with review-log chain verification and a
    reviewer-registry check.
  - The proposal cites the counting rule but does not state that only labels admitted through that P1 route count toward P2.
  - **Recommendation:** add this as an explicit precondition.
* **GAP G3: P1 vs CV conflict.**
  - P1 says verified labels may enter **training only**, with validation, calibration and test frozen.
  - In 5-fold CV every pool radiograph is held out once, so newly verified labels in the pool would also be **evaluated**.
  - Either P1 must be read as allowing held-out evaluation of verified labels under CV, or verified-label radiographs must be
    training-only in every fold (outside the out-of-fold metrics).
  - Owner decision needed; it also affects U3.
* **GAP G4: P2 counting basis vs CV.**
  - P2 counts the `combined_train` split plus verified labels.
  - Each CV fold fits on about 70 % of the pool (fitting part only), and `combined_validation` is also in the pool.
  - "P2 met" therefore does not mean each fold's fitting set reaches the targets.
  - **Recommendation:** state that P2 is evaluated by the existing `expansion_report.py` rule and is **not** a per-fold requirement,
    or define a per-fold rule.
* **GAP G5: P2 is provisional.**
  - P2 was approved provisionally, to be "revisited after batch 1".
  - **Recommendation:** the proposal should state that the P2 version in force when a confirmatory candidate is **registered** applies,
    and that P2 may not be revised after any candidate result is seen.

## 6. Ensemble design (check 6): PASS with note

* §6 lists F5 as its own family. §6 states ensembling is never combined with another intervention. §6.1 defines E1 = seeds 42–46 and
  E2 = seeds 47–51, two disjoint five-member ensembles, with the same frozen criteria (P-C substitution open, U8). Consistent with D6.
* **Note N6:** §6.1 says E1 uses "the stored CV5-BASE checkpoints, after gate R".
  - Under D5, a confirmatory ensemble comparison happens only after P2 is met. At that point the fold file is regenerated (U3) and the
    stored v1 checkpoints no longer apply.
  - **Recommendation:** reword to "the BASE reference run's checkpoints for the fold file in force".
  - Also note that E1 shares its members with the BASE comparator, so E2 is the only independent replication.

## 7. Test-set policy and pending disclosures (check 7)

| Point | Proposal | Ledger code / files | Result |
|---|---|---|---|
| Test never used for training, selection, calibration or tuning | §10 | – | PASS |
| At most one final evaluation, after a confirmatory ACCEPT, named authorizer, reason | §10 | `authorize`: named authorizer (2–64 chars), reason ≥ 20 chars | PASS |
| One new candidate per test-split version | §10 | `authorize`: refuses a second non-historical `final_metrics` entry for the same task and split assignment | PASS. No non-historical classification entry exists today, so the slot is free |
| Pending disclosures recorded first | §10 names P5 (`reports/p5_disclosure_entry.json`, evaluated 2026-10-16T11:53:27Z) and the external-data run (`kaggle/artifacts_external_run1/ledger_disclosure_entry.json`, 2026-10-24T13:39:06Z) | both files exist; both are task `classification`, 73 images / 354 findings; kind `retrospective_disclosure`, which does **not** use up the candidate slot | PASS |
| **Validation-first rule** | not mentioned | `authorize` refuses a checkpoint without `eval_<version>_val.json` for the **same file hash** | **GAP G7** |
| Test already used | §10: "reported as it is" | ledger statement: the test split is already used, so a later result is "not an untouched estimate" (5 historical entries + 2 pending disclosures of BASE test runs) | **GAP G8** |

* **G7:** under U9's default (one model retrained on the full pool), the frozen validation split is part of that model's training
  data. A validation report for that file would then be computed on training radiographs, while the ledger requires one before any
  test evaluation. **Owner decision needed:** accept a validation report labelled "computed on training data, procedural only", or
  choose a different final-model rule (e.g. one designated fold model).
* **G8 recommendation:** §10 should say the final test result is **not** an untouched or unbiased estimate, because the split has
  already been used for BASE evaluations.

## 8. Candidate cap and multiplicity before training (check 8)

* **PASS:** §4.5 requires a dated amendment **before any training** that fixes the candidates (≤ 3 per family per round), the config
  diffs, how candidates were chosen, and the multiplicity handling. No candidate can be added after results are seen. The method itself
  is open (U6).
* **GAP G6: the number of rounds is not capped**, and multiplicity is handled only within a round. Repeated rounds of 3 in one family
  can search freely over the same out-of-fold radiographs. **Recommendation:** either cap the rounds per family, or require every round
  to report the cumulative number of candidates tested in that family.
* **GAP G9: no selection rule if several candidates pass.**
  - If more than one candidate in a round is ACCEPTED, the proposal does not say which one may go forward. This matters for D7's
    single test slot and for any promotion.
  - **Recommendation:** pre-register "largest seed-mean Δ macro-F1; ties broken by the smaller model".
  - The selected candidate's Δ is then optimistically biased (winner's curse), and this should be stated.
* **GAP G10: exploratory runs feeding confirmatory selection.**
  - §3 allows documented pre-P2 exploratory runs.
  - §4.5 forbids choosing candidates using held-out out-of-fold predictions.
  - The post-P2 pool will **contain** the current 541 radiographs, so choosing a confirmatory candidate because of an exploratory
    result uses out-of-fold predictions on largely the same radiographs. This contradicts §4.5.
  - **Owner decision needed:** either forbid using exploratory results for selection, or allow it with disclosure and count every
    exploratory candidate in the family's multiplicity k.

## 9. Unresolved decisions U1–U9 (check 9)

**Result:** all nine are listed in §14, each with a question, why it matters, and a proposed default. **Gap:** the proposal gives a
default but not always the rationale for that default. The rationale is supplied below; the recommended resolution equals the
proposal's default unless stated.

| # | Recommended resolution | Rationale |
|---|---|---|
| U1 | Keep the numeric margins frozen; report margins re-derived on the new pool as information only | Re-deriving after the data change would let the thresholds move once more data is seen. Freezing them is the conservative, pre-registered choice. With more PL/DC data the true BASE noise is likely smaller, so frozen margins are, if anything, lenient. That limitation should be stated |
| U2 | Keep δ = 0.027 and the D8 flags unchanged | Same reasoning as U1. δ is a practical-relevance threshold, not a noise estimate, so it should not depend on pool size |
| U3 | A separate dated amendment that registers the regenerated fold file (P4 re-review) and the new BASE CV run, **before** any candidate | The stored predictions are valid only for `cv5_folds_v1.csv` (hash-locked). A separate amendment keeps this approved protocol stable. Depends on G3 |
| U4 | Re-evaluate all 25 stored BASE checkpoints. Require identical argmax for every finding in both settings and identical pooled metrics. Report the maximum probability difference without gating on it | One checkpoint cannot show that all 25 reproduce. Argmax and metric identity is what the comparison uses. Requiring bit-identical probabilities across CUDA builds may fail for harmless reasons |
| U5 | If gate R fails: stop and report. A concurrent BASE retrain in the candidate's environment only with owner approval, case by case | D3 allows reuse only after reproduction. An automatic retrain would add about 1.4 GPU-h and a second BASE reference without review |
| U6 | Bonferroni on the P-B confidence level (two-sided 1 − 0.05/k, k = candidates in the round, cumulative per G6/G10 if adopted). P-A, P-C, P-D and the safeguards stay unadjusted | Simple and conservative. It is valid under any dependence between candidates trained on the same folds. The other checks are fixed thresholds, not tests |
| U7 | Keep S7 (end-to-end DC/PL recall) and the hard-harm rule | S7 guards against findings lost through matching. The hard-harm rule stops a clearly worse minority recall from passing on a favourable point estimate. Neither depends on any candidate result |
| U8 | E1 and E2 must each pass P-A, P-B, P-D and all safeguards against the BASE 5-seed mean | P-C needs per-seed replicates, which an ensemble lacks. Requiring both disjoint ensembles to pass is the replication analogue. E2 is the independent one (N6) |
| U9 | Pre-register the final model **before** the test evaluation. Proposed: retrain on the full pool for the median of the 25 selected epochs, seed 42. Resolve G7 at the same time | CV gives 25 fold models, and D7 allows one test evaluation. The final-model rule must not be chosen after test results. Because of G7, an alternative (one pre-designated fold model) may fit the ledger rules better; this is the owner's choice |

## 10. Other checks

* **Status and scope:** the proposal is marked "DRAFT PROPOSAL, revision 2 … NOT APPROVED. Not in force". It states that no candidate
  has been trained and that production, artifacts and the paper are unchanged. §2 and §8 make no claim of patient-level
  generalization, clinical validity or multi-centre performance. PASS.
* **Wording:** §5.2 says "none [of the margins] was chosen after seeing a candidate", while its own disclosure says the X2_hanoi and
  ensemble single-split results were known. **Recommendation:** say "after seeing any candidate's CV5 results".
* **Isolation of interventions (§6):** one family per candidate, combinations only as new experiments after each component passes.
  Consistent with the owner's requirement 7. PASS.

## 11. Remaining blockers before the proposal can be approved

**Owner decisions needed** (none can be resolved without inventing a policy):
* U1–U9;
* G3 (P1 "training only" vs held-out evaluation under CV);
* G7 (ledger validation-first rule vs a full-pool final model);
* G10 (may exploratory results inform confirmatory selection);
* G6 (round cap or cumulative multiplicity);
* G9 (selection rule if several candidates pass).

**Text fixes to make after those decisions** (wording only, no new values):
* N1 (≥ vs >, no rounding);
* N2 (latency reference);
* N3 (GPU-hours definition);
* N4 (bootstrap details);
* N5 (P-C setting);
* N6 (E1 wording);
* G1 (collapse and failure classification);
* G2 (P1 route as a P2 precondition);
* G4 (P2 counting basis);
* G5 (which P2 version applies);
* G8 (test result not untouched);
* the §5.2 wording above.

**Preconditions outside the proposal:**
* The P2 targets are not met: PL needs 171 more findings from 106 more radiographs; DC needs 283 more findings from 150 more
  radiographs. No clinician-verified labels have been imported yet.
* Both ledger disclosures await the owner's named authorization: P5, and the external-data run.
* The paired bootstrap and the CV5 acceptance function are not implemented yet (to be done after approval, with tests).

**Conclusion:** the proposal is internally consistent on all threshold values, which are traceable and exactly reproducible from their
sources. It is consistent with the CV5 protocol, the results, the fold file and the ledger code on every point checked, except the gaps
above. It should stay **NOT APPROVED** until the listed decisions are made and the text fixes applied. No confirmatory experiment can
start in any case until P2 is met.
