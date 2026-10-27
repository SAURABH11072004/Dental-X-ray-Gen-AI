# CV5 acceptance protocol: decisions needed and drafted wording

Date 2026-10-24. Companion to `reports/cv5_acceptance_protocol_proposal.md` (revision 2, **NOT APPROVED**, unchanged, SHA-256
`98d6e223…`) and `reports/cv5_acceptance_final_audit.md`.

**Status and constraints:**
* This file **drafts wording and recommendations only**. It does not approve, amend or replace the proposal. The proposal stays NOT
  APPROVED, and the drafted text is inserted only after the owner decides.
* No model was trained, no data imported, no experiment started. No protocol, result, fold file, ledger entry or artifact was changed.
* **New values:** wherever a number below is new (not already registered or derived in the proposal), it is marked **[NEW VALUE:
  needs approval]**. Registered criteria (δ, P-A to P-D, S1–S6 margins, D8 flags, bootstrap settings) are **not** changed.

**Superseded 2026-10-25:** the owner approved all open items. The merged, approved text is `reports/cv5_acceptance_protocol.md` (revision 3). This file is kept unchanged below as the drafting record.

**Update 2026-10-25: owner decisions recorded.**
* See `reports/cv5_acceptance_owner_decisions.md` (decisions on B-1 – E-3) and the owner's follow-up of the same day.
* The final drafted wording for revision 3 is in `reports/cv5_acceptance_protocol_rev3_wording.md`. It is **not merged**; the proposal
  is unchanged and NOT APPROVED.
* Current status per item:

  | ID | Status (2026-10-25) |
  |---|---|
  | B-1, B-3 | decided: approved, with an identity-level independence check (V6) |
  | B-2 | decided: BASE-P2 vs BASE is exploratory |
  | B-4 | decided: approved |
  | D-1 | decided: 15-candidate lifetime budget; every outcome counts |
  | D-2 | decided: **option (i)**. No exploratory candidates on the 541-radiograph CV population; register all first-round confirmatory candidates before viewing BASE-P2 results; no test-set selection. This replaces option (b) in Part D.2 |
  | D-3 | winner rule: provisional. The owner's follow-up item 4 ("reuse stored BASE predictions only after exact reproduction is verified and the fold file is unchanged") matches proposal **D3** (§4.3), not this winner rule; it is recorded as a confirmation of D3 |
  | E-1 | decided: ≥ 99 % of inner-validation GT-box predictions at the selected epoch; failure classes as in Part E (updated) |
  | E-2 | rejected as written; replaced by **V-a** (Part E, G7 updated) |
  | E-3 | decided: approved for insertion |
  | U9 | decided: full-pool retraining and the median-epoch rule removed (V-a) |
  | U1–U8 | **second owner round (2026-10-25):**<br>• U1/U2: margins, δ and flags are fixed for the first round; no re-derivation from BASE-P2<br>• U3: register before BASE-P2 is run; BASE-P2 is the comparator<br>• U4: exact prediction check plus predeclared tolerance<br>• U5: a pre-training failure uses no slot<br>• U6: cumulative lifetime k (this supersedes Part D.1's per-family k and "no adjustment across families")<br>• U7: frozen hard-harm rule covering recall and precision<br>• U8: every applicable safeguard<br>Open values and choices are in the revision 3 file §R |
  | V-a | approved conditionally (genuine manifest, verified hash, report from stored predictions, disclosure) |
  | D-3 | approved provisionally (second round) |
  | Revision 3 | direction approved; final document not approved |

**Facts used (read from disk):**
* `scripts/dataset/build_annotation_pool.py`, lines 13–18. The annotation pool contains one row per radiograph group, and "a group
  that contains any diagnosis-labelled radiograph is NOT in the pool". `split_lock`:
  - `train`: twin of a project train radiograph;
  - `eval_locked`: twin of a validation / calibration / test radiograph; it must not enter training;
  - `unassigned`: a new radiograph whose split is set by a documented protocol.
* Pool today (`data/annotation/annotation_pool.csv`, 6,006 groups):

  | Source | split_lock | Groups |
  |---|---|---:|
  | Hanoi | unassigned | 3,863 |
  | DENTEX unlabelled | unassigned | 1,537 |
  | DENTEX quadrant-enumeration | train | 251 |
  | DENTEX quadrant-enumeration | eval_locked | 105 |
  | DENTEX official test | unassigned | 155 |
  | DENTEX quadrant | train | 55 |
  | DENTEX quadrant | eval_locked | 24 |
  | DENTEX quadrant-enumeration-disease | unassigned | 16 |

* `scripts/dataset/clinical_review.py` (around line 263) excludes eval_locked and evaluation-hash radiographs at export.
  `verified_to_manifest.py` (P1, hardened) re-checks eligibility before any row reaches a training manifest.
* `src/dentexmodel/evaluation/test_ledger.py`:
  - `authorize` requires a named authorizer, a reason of at least 20 characters, and a validation report for the **same checkpoint
    hash**;
  - only one new non-historical `final_metrics` candidate per task and split version is allowed;
  - `retrospective_disclosure` entries do not use that slot.
* Ledger: 5 historical entries, SHA-256 `f117c1a3…`.

---

## Part A. Category definitions (item 6)

| Category | What it is | What it can support | Label in every report |
|---|---|---|---|
| **A1 Completed baseline evidence** | CV5-BASE run 1 (`reports/cv5_results.md`, artifacts `kaggle/artifacts_cv5_run1/`). Observed, final, not a candidate | Reference values and noise margins. Never re-run under a changed protocol | "Observed BASE (CV5 run 1)" |
| **A2 Existing test-set history** | 5 historical ledger entries (production models) and 2 **pending** retrospective disclosures of BASE test evaluations (2026-10-16 Kaggle v2, `reports/p5_disclosure_entry.json`; 2026-10-24 external-data run, `kaggle/artifacts_external_run1/ledger_disclosure_entry.json`), plus the test numbers already reported (e.g. BASE test macro-F1 0.705 ± 0.031) | Historical context only. Not candidate evidence. They show the test split is **already used** | "Historical test result (test split previously used)" |
| **A3 Exploratory comparison** | Any candidate run before the P2 targets are met, any run not registered under §4.5, and every analysis listed in proposal §7.1 | Hypothesis generation only. **Never** ACCEPT, never promotion, never test-set use | "EXPLORATORY: not a confirmatory result" |
| **A4 Confirmatory comparison** | A candidate registered under §4.5 **after** P2 is met (and G2), with all validity gates passed | The only route to ACCEPT / FAIL / NO VERDICT | "Confirmatory (CV5 acceptance protocol)" |
| **A5 Future ledger-recorded test evaluation** | At most one, after a confirmatory ACCEPT and the winner rule (Part D), through `test_ledger.authorize` | Descriptive only. **Not** an untouched estimate (A2). Cannot change any verdict, threshold or model | "Final test evaluation (ledger entry #…, test split previously used)" |

A result may move only **up** this table by being run again under the stricter category's rules. An exploratory result can never be
relabelled as confirmatory.

---

## Part B. Resolving P1 label imports vs CV5 held-out evaluation (G3, G2, G4, G5)

### B.1 The conflict

* P1 (approved 2026-10-16) admits newly clinician-verified labels to **training only**.
* P4's note ("regenerate and re-review the folds after verified labels are added") assumed new radiographs would join the CV pool.
* In 5-fold CV every pool radiograph is held out once. Adding imported radiographs to the pool would therefore **evaluate** them,
  against P1.

### B.2 Recommended resolution: "frozen evaluation population, training-only imports"

Proposed text for a new proposal section §3.1:

> **§3.1 Imported labels and evaluation independence.**
> 1. *Evaluation labels are frozen.* Every held-out and inner-validation label in a CV5 comparison is an original DENTEX
>    expert label of the approved fold file's population (`cv5_folds_v1.csv`, 581 groups). Imports never add, remove or change an
>    evaluation label. The fold file is **not** regenerated because of imports.
> 2. *Imports are training-only, in every fold.* Rows admitted through the P1 route (`verified_to_manifest.py`) are added to the
>    **fitting** part of **every** fold. They are never placed in inner-validation (epoch selection) or in a held-out fold, and they
>    never contribute to any out-of-fold metric.
> 3. *Only radiographs outside the evaluation population can be imported.* By construction of `build_annotation_pool.py`, groups
>    containing a diagnosis-labelled radiograph are not in the annotation pool. The `eval_locked` twins and evaluation hashes are
>    refused at export and again in `verified_to_manifest.py`.
> 4. *Independence gate V6 (new validity gate, run before any training that uses imports).* Re-run the gate-1 checks with the
>    imported images added. Every imported image must be outside all of these, by radiograph group, exact SHA-256 and the confirmed
>    near-duplicate rule (dHash ≤ 4 plus correlation ≥ 0.97, as in the existing leakage check):
>    * the 581-group CV pool;
>    * the calibration split;
>    * the test split;
>    * the eval_locked groups.
>
>    Any hit is refused, and the run gets NO VERDICT until the hit is removed.
> 5. *Corrections to existing DENTEX labels are not imports.* A clinician opinion on a finding already in the CV pool (for example
>    the 110 findings in `reports/cv5_caries_clinician_review_list.csv`) cannot enter through P1, because the pool excludes those
>    radiographs. Such opinions are used in no confirmatory comparison. They need a separate, owner-approved label-revision protocol
>    and may meanwhile be reported only as an exploratory sensitivity analysis.
> 6. *Per-source reporting (P3).* Imported rows are reported by source; Hanoi rows need a complete four-class review (P3).

**Rationale:**
* This keeps P1 literal (training only) and keeps the evaluation population and its labels identical across BASE, every candidate and
  every later reference run. Paired comparisons stay paired.
* It removes the need to regenerate folds.

**Consequences:**
* The P4 instruction to regenerate folds after verified labels are added is **superseded for CV5 acceptance work** (owner decision
  **B-1**).
* Folds on an enlarged evaluation population could still be proposed later under a separate protocol.

### B.3 Consequence for the BASE reference after P2 (replaces the audit's U3 recommendation)

The BASE reference must be trained on the same data as the candidates. Once imports exist, a new reference run is needed:
* **BASE-P2:** the unchanged BASE recipe, with the imports in every fold's fitting part (B.2 item 2);
* same v1 folds, inner-validation, seeds 42–46 and detector boxes;
* registered by its own dated amendment **before** any confirmatory candidate.

BASE-P2 is a **reference**, not a candidate. It cannot be ACCEPTED, and the stored CV5 run 1 predictions remain the comparator only for
exploratory work.

**Owner decision B-2:** is the comparison BASE-P2 vs BASE (the effect of the imported data)
* (a) reported as exploratory only (recommended: it was not pre-registered as an F3 candidate, and the margins were derived from
  BASE); or
* (b) registered as a confirmatory F3 candidate under the full protocol?

### B.4 Drafted wording for G2, G4, G5

* **G2 (P1 route as a P2 precondition):**
  > Only labels admitted through the P1 route (`verified_to_manifest.py`, review-log chain verified, current reviewer registry)
  > count toward P2. Rows must also pass gate V6. Original DENTEX labels count as already counted by `expansion_report.py`.
* **G4 (P2 counting basis):**
  > P2 is met when `scripts/dataset/expansion_report.py`, run on the current manifests and verified labels, reports a gap of 0
  > findings and 0 radiographs for both Periapical Lesion and Deep Caries. P2 is a pool-level condition, not a per-fold
  > requirement. Under B.2 every fold's fitting part contains all imports plus about 70 % of the DENTEX pool, and the per-fold
  > fitting counts are reported (descriptive).
* **G5 (which P2 version applies):**
  > The P2 version in force on the date a confirmatory candidate (or BASE-P2) is registered applies to it. P2 may be revised only
  > before, never after, any confirmatory result exists, and any revision is a dated owner decision.
  > Today: provisional P2 of 2026-10-16. PL ≥ 300 findings from ≥ 200 radiographs (now 129 / 94); DC ≥ 750 from ≥ 400 (now
  > 467 / 250).

---

## Part C. Paired radiograph-level bootstrap and unrounded comparisons (item 5; N1, N4)

Specification only. **Not implemented and not executed.**

### C.1 Inputs

* For each arm A ∈ {BASE reference, candidate}, each seed s ∈ {42…46} and each primary finding i, one out-of-fold predicted class in
  each setting (detector boxes, GT boxes).
* The detector-matched flag of each finding, from the reference run's `detector_boxes_pool.json`.
* The radiograph group of each finding, from the fold file.
* **Primary radiographs:** the groups of the `dentex_train_disease` findings (541 in run 1).

### C.2 Point estimates

* For each arm, setting and seed: compute the metric (macro-F1, and per-class precision / recall / F1) on **all** findings of the
  setting. In the detector setting these are the matched findings.
* The macro-F1 definition is `cv5_lib.macro_f1`: the mean of the four per-class F1 values, with an undefined precision, recall or F1
  counted as 0.
* Seed-mean: M_A = (1/5) Σ_s metric_A,s.
* Δ = M_candidate − M_BASE.

### C.3 Bootstrap

1. One generator, `numpy.random.default_rng(0)`, created once per comparison.
2. Repeat B = 2,000 times:
   - draw 541 primary radiographs **with replacement**;
   - take all findings of each drawn radiograph, with multiplicity;
   - in the detector setting, drop unmatched findings **after** drawing.
3. In each resample b, compute the metric for **all 10 arm-seed combinations on the same multiset of findings**. Then
   Δ_b = mean over seeds of the candidate metric − mean over seeds of the BASE metric.
4. The same B draws are reused for every metric and both settings (safeguard CIs included). There are no separate draws per metric.
5. **CI:** the percentile interval of {Δ_b}, `numpy.percentile` (default linear interpolation).
   - With k candidates in the family (Part D), the two-sided level is 1 − 0.05/k, i.e. percentiles 100·(0.025/k) and
     100·(1 − 0.025/k).
   - k = 1 gives 2.5 / 97.5.
6. **P-B passes** if the lower percentile is > 0 (strict).
7. **Degenerate resamples:** if a class has zero support in a resample, its recall and F1 count as 0 for **both** arms, by the
   definition above. The number of such resamples per class is reported. Resamples are never discarded.
8. **Recorded:** the generator seed, B, k, the ordered list of drawn group IDs (or their hash), and every Δ_b, in the result JSON.

### C.4 Unrounded comparisons (N1)

Proposed text:

> All criteria are evaluated on unrounded IEEE-754 double-precision values exactly as computed: Δ, CI bounds, win counts and safeguard
> deltas. Rounding is applied only for display (3 decimals) and never before a comparison. The criteria are:
> * P-A: Δ ≥ 0.027;
> * P-B: lower bound > 0;
> * P-C and P-D: per-seed or per-fold Δ > 0;
> * S1–S6: Δ ≥ −margin.
>
> The result JSON stores the raw values. The P-A operator is **≥ 0.027**, following owner D1/D2. The earlier single-split rule
> (`ACCEPT`, `dentamind_kaggle.py:501`) used **> 0.027**. The value is unchanged; the operator differs and is disclosed here.

### C.5 Wording for N5 (P-C setting)

> P-C: for each seed s, the pooled out-of-fold macro-F1 of candidate seed s minus BASE seed s, **detector boxes, matched primary
> findings**. P-C passes if this difference is > 0 for ≥ 4 of the 5 seeds.

---

## Part D. Finite candidate budget and deterministic winner selection (item 4; G6, G9, G10)

### D.1 Budget [NEW VALUES: need approval]

Proposed text:

> **Candidate budget (fixed before any candidate is registered).**
> * Each intervention family F1–F4 has a **lifetime** budget of **3 distinct candidate configurations**, counting exploratory and
>   confirmatory registrations together. Re-running the same configuration (identical config diff) as confirmatory after an
>   exploratory run does not use additional budget.
> * F5 (ensembling) has a budget of **1 design** (E1/E2, §6.1).
> * Combination experiments (§6) have a budget of **2**, each combining only components that were individually ACCEPTED.
> * **Total lifetime budget: 4 × 3 + 1 + 2 = 15 candidate configurations.** It is not reset by new rounds or protocol amendments;
>   only an explicit owner decision recorded in this protocol can enlarge it, and any enlargement is disclosed in every later report.
> * **Multiplicity:** k for a family is the number of distinct configurations registered in that family so far (exploratory and
>   confirmatory, maximum 3). It is applied to P-B as in Part C.5. Combination experiments and the F5 design use k = 1. No adjustment
>   across families: each family answers its own question. This is stated as a limitation.

**Rationale:**
* A lifetime cap makes the total number of looks at the same out-of-fold radiographs finite and known (G6).
* Counting exploratory configurations in k answers G10 without pretending that exploratory results can be kept from influencing later
  choices.

**Alternatives for the owner:**
* 2 rounds × 3 per family (total 27; k up to 6);
* or exploratory runs not counted in k, which requires G10 option (a) below.

### D.2 G10: exploratory results and confirmatory selection [DECIDED 2026-10-25: option (i) below; (a) and (b) not adopted]

* **(i) Adopted:** no exploratory candidate runs on the 541-radiograph CV population. All first-round confirmatory candidates are
  registered before any BASE-P2 result is viewed. The test set is never used for selection.
  - Consequence: in D.1, k counts only the confirmatory configurations registered in the family.
  - Open: per round or cumulative (revision 3 wording, A-U6).

Original options, kept for the record:

* **(a) Forbid:** exploratory results may not influence which configurations are registered as confirmatory. Not verifiable in
  practice.
* **(b) Recommended: allow with accounting.** Exploratory results may inform the choice, provided all of the following hold:
  - every exploratory configuration in the family counts toward the budget and toward k (D.1);
  - the confirmatory registration lists every exploratory run in that family, with links;
  - the report states that confirmatory and exploratory runs share most held-out radiographs, so selection-related optimism
    is possible.

### D.3 Deterministic winner selection (G9) [rule needs approval]

Proposed text:

> **Winner rule.**
> * **Eligible:** confirmatory candidates with verdict ACCEPT only.
> * **Order** (each step only breaks exact ties of the previous step, on unrounded values):
>   1. larger seed-mean Δ macro-F1 (detector boxes);
>   2. larger P-B lower bound;
>   3. fewer trainable parameters;
>   4. earlier registration timestamp in the amendment log.
> * **Within a family** the rule picks the family winner. **Across families**, the same rule applied to all eligible candidates,
>   including ACCEPTED combination experiments, picks the single candidate that may proceed to D7 / A5.
> * The winner's Δ is reported as **optimistically biased by selection** (winner's curse). The non-selected ACCEPTED candidates
>   are reported in full.
> * Selection is never re-run after test results exist.

**Rationale:**
* Every step uses a value fixed before the test evaluation.
* Parameter count is deterministic, whereas latency carries measurement noise.
* The registration timestamp guarantees a unique result.

---

## Part E. Drafted wording for the remaining audit gaps

* **G1, updated 2026-10-25 (owner E-1):**
  - **Collapse:** ≥ 99 % of the run's inner-validation predictions fall in one class, using GT boxes, at the selected epoch.
  - **Infrastructure failure:** up to 3 attempts, then NO VERDICT.
  - **NaN or infinite loss, or collapse:** FAIL, with no retry.
  - **Incomplete run:** NO VERDICT.
  - **Budget:** every outcome counts toward the 15-candidate lifetime budget.
  - Final wording is in the revision 3 file, §9. The text below is superseded where it differs.
* **G1 (divergence vs infrastructure failure), original draft:** [the 99 % value is a NEW VALUE: needs approval]
  > A run is an **infrastructure failure** if its log ends in an exception raised outside the forward/backward/loss computation:
  > a CUDA runtime error, out of memory, a process timeout or a lost Kaggle session. It is retried with the identical config and seed,
  > up to 3 attempts (`train_run_isolated(attempts=3)`, `kaggle/dentamind_kaggle.py:535`). A run is a **divergence** if
  > (i) the training loss becomes NaN or ±inf, or (ii) at the selected epoch, ≥ 99 % of inner-validation predictions fall into one
  > class. A divergence is a recipe failure (candidate FAIL) and is not retried. The classification is made from the log, recorded
  > in the result JSON, and cannot be changed after the verdict.

  Alternative to 99 %: "100 % (all inner-validation predictions one class)". This is stricter about what counts as collapse and needs
  no tuned number.
* **G6, G9, G10:** see Part D.
* **G7, updated 2026-10-25:** the owner **rejected** the procedural report below, because a report on training data is not an
  independent validation report. It is replaced by **V-a**:
  - The final artifact is the winner's fold 0 / seed 42 checkpoint.
  - Its validation report is that checkpoint's existing held-out fold 0 report.
  - There is no full-pool retrain, and the ledger requirement is unchanged.
  - A disclosure is mandatory: fold 0 was part of the candidate-comparison population, so the report is not independent confirmation
    of the selected winner.
  - Prerequisite found in code: `authorize` refuses a checkpoint without a `training_manifest`. CV5 runs do not write one today.
  - Final wording is in the revision 3 file, §10.3. The text and "Alternative" below are withdrawn. The claim in the "Alternative"
    that a fold model "also trained on part of the validation split" applies to training, not to its own held-out fold.
* **G7 (ledger validation-first rule vs final model), original draft, withdrawn:**
  > The single final-test model is fixed before the test evaluation (U9). If it is a model retrained on the full CV5 pool, the
  > `eval_<version>_val.json` report that `authorize` requires is produced on the frozen validation split and carries the statement
  > "procedural: computed on radiographs included in this model's training data; not a performance estimate". The ledger code is
  > not changed.

  Alternative: choose one pre-designated CV fold model as the final model. This avoids nothing: every fold model also trained on part
  of the validation split, because the CV pool contains it. So the procedural report is needed either way.
* **G8 (test history):**
  > The DENTEX internal test split has already been used: 5 historical ledger entries, and BASE test evaluations on 2026-10-16 and
  > 2026-10-24 whose disclosures are pending. A future test result is therefore **not an untouched or unbiased estimate**, and every
  > report of it carries the ledger's `test_status_for_report` block.
* **N2 (latency reference):**
  > Latency is measured in the candidate's notebook session, on the same GPU, with the same script. The candidate and one BASE
  > reference checkpoint are each measured at batch 64 (time per crop) and at batch 1, 5 repetitions after warm-up, median reported.
  > The D8 flag is raised if either ratio (candidate / BASE) exceeds 2. Earlier measurements (ensemble report: 2.9 / 7.7 ms) are not
  > used as the reference.
* **N3 (GPU-hours):**
  > Reported as (i) total notebook wall-clock runtime and (ii) the sum of per-run training times from `runs/*__result.json`, for the
  > candidate and the BASE reference run, with GPU type and count. BASE run 1: 1.37 h total notebook runtime (archive README).
  > Its training-time sum is computed from its result files when the first candidate report is written.
* **N4:** see Part C.3.
* **N5:** see Part C.5.
* **N6 (ensemble E1 wording):**
  > E1 = seeds 42–46 of the **BASE reference run for the fold file and training data in force** (CV5 run 1 for exploratory work;
  > BASE-P2 for confirmatory work). E2 = seeds 47–51, trained with the same recipe and data. E1 shares its members with the BASE
  > comparator, so only E2 is an independent replication. Both must pass (U8).
* **§5.2 wording fix:**
  > "none was chosen after seeing any candidate's CV5 results" (the earlier single-split X2_hanoi and ensemble results were known; see
  > the disclosure).

---

## Part F. Unresolved decisions U1–U9

Each question is quoted in full from proposal §14, with a recommended resolution, the rationale, and whether owner approval is needed.

**U1.** "When P2 is met and the pool grows, are the numeric margins kept as frozen here, or re-derived by the same rule from the new
BASE CV run?"
* **Recommended:** keep frozen. Report the margins re-derived from BASE-P2 next to them, as information only.
* **Rationale:** thresholds must not move after more data is seen. Under Part B the evaluation population does not grow; only training
  data does. BASE-P2 noise may be smaller, which makes the frozen margins lenient rather than strict. That limitation is stated.
* **Needs approval:** yes.

**U2.** "Are δ = 0.027 and the D8 flags also kept unchanged for the new pool?"
* **Recommended:** yes, unchanged.
* **Rationale:** δ and the flags are practical-relevance judgements by the owner (D1, D8), not noise estimates.
* **Needs approval:** yes.

**U3.** "After P2, BASE must be re-run under CV5 on the regenerated, re-approved fold file (P4). Should that BASE re-run be
pre-registered as part of this protocol or as a separate amendment?"
* **Recommended (revised by Part B):** do not regenerate the fold file. Register **BASE-P2** (BASE recipe plus imports, v1 folds) in a
  separate dated amendment before any confirmatory candidate.
* **Rationale:** this keeps P1 literal, keeps evaluation pairing intact, and keeps the approved fold file and its hash unchanged.
* **Needs approval:** yes, together with B-1 (superseding P4's regeneration note for this work) and B-2.

**U4.** "Gate R scope: how many stored BASE checkpoints are re-evaluated (1 or all 25), and is any probability tolerance allowed
besides identical predicted classes and identical metrics?"
* **Recommended:** all 25. Identical argmax for every finding in both settings, and identical pooled metrics. Report the maximum
  absolute probability difference, without gating on it.
* **Rationale:** one checkpoint cannot vouch for 25. Argmax and metrics are what the comparison uses. Bit-identical probabilities can
  differ across CUDA builds for harmless reasons.
* **Needs approval:** yes.

**U5.** "If gate R fails: retrain BASE concurrently in the candidate environment (≈1.4 GPU-h, then use it as the comparator), or stop
until the environment is fixed?"
* **Recommended:** stop and report (NO VERDICT). A concurrent BASE retrain only with owner approval, case by case.
* **Rationale:** D3 allows reuse only after verified reproduction. An automatic retrain would silently create a second BASE reference.
* **Needs approval:** yes.

**U6.** "Multiplicity method for k > 1 candidates in a round."
* **Recommended:** Bonferroni on the P-B level (Part C.3 step 5), with k defined as in Part D.1 (distinct configurations in the
  family, exploratory included). The other checks stay unadjusted.
* **Rationale:** valid under any dependence between candidates evaluated on the same folds, and simple to audit. The other checks are
  fixed thresholds, not tests.
* **Needs approval:** yes.

**U7.** "Keep S7 (end-to-end DC/PL recall) and the hard-harm rule from revision 1?"
* **Recommended:** keep both. The hard-harm rule uses the Part C interval for Δ recall, at the 95 % level (k-adjusted like P-B).
* **Rationale:** S7 catches findings lost to matching. The hard-harm rule stops a clearly lower minority recall from passing on a
  favourable point estimate. Neither depends on any candidate result.
* **Needs approval:** yes. Whether the hard-harm CI is k-adjusted is part of this decision.

**U8.** "Ensemble substitute for P-C (no per-seed replicates)."
* **Recommended:** E1 and E2 must each pass P-A, P-B, P-D and all safeguards against the BASE reference's 5-seed mean, with E1/E2 as
  defined in N6.
* **Rationale:** requiring both disjoint ensembles to pass is the replication analogue of P-C, and E2 is the independent one.
* **Needs approval:** yes.

**U9.** "Which single model goes to the test set after an ACCEPT, and how it is trained."
* **DECIDED 2026-10-25:** the winner's fold 0 / seed 42 checkpoint (V-a). No full-pool retraining and no median-epoch rule. The
  recommendation below is withdrawn.
* **Original recommendation (withdrawn):** the Part D.3 winner, retrained once on the full CV5 pool **plus imports** with the BASE-identical recipe:
  - fixed epoch count = median of that candidate's 25 selected epochs, rounded down to an integer if the median is fractional
    [NEW rounding rule: needs approval];
  - seed 42;
  - no inner-validation selection.

  Registered before the test evaluation. Validation report handled as in G7.
* **Rationale:** CV yields 25 fold models and D7 allows one test evaluation. Fixing the rule in advance prevents choosing it after
  seeing the test.
* **Needs approval:** yes.

---

## Part G. Summary of decisions requiring explicit owner approval

**Updated 2026-10-25:** see the status table at the top of this file. Still open:
* the revision 3 wording as a whole;
* the V-a §10.3 text;
* D-3 (winner rule);
* U1–U8;
* ambiguities A-U1 to A-U8.

The table below is the original 2026-10-24 list.

| ID | Decision | Recommended |
|---|---|---|
| B-1 | Imports are training-only in every fold; the evaluation population and labels stay frozen (v1 folds); P4's fold-regeneration note is superseded for this work | approve |
| B-2 | BASE-P2 vs BASE (effect of imported data): exploratory or a confirmatory F3 candidate | exploratory |
| B-3 | Gate V6 (import independence) added as a validity gate | approve |
| B-4 | Clinician opinions on existing pool findings (e.g. the 110-finding review list) are excluded from confirmatory work until a separate label-revision protocol exists | approve |
| D-1 | Lifetime budget: 3 configurations per family F1–F4, 1 F5 design, 2 combinations; 15 in total | approve, or the 2-round alternative |
| D-2 | G10: exploratory results may inform selection, counted in budget and k | option (b) |
| D-3 | Winner rule: Δ, then P-B lower bound, then parameters, then registration time | approve |
| E-1 | G1 collapse definition: ≥ 99 %, or 100 % of inner-validation predictions in one class | choose |
| E-2 | G7: procedural validation report for the final model, ledger code unchanged | approve |
| E-3 | Wording fixes N1–N6, G2, G4, G5, G8 and §5.2 (no new values) | approve for insertion |
| U1–U9 | as in Part F | as recommended |

**Outside this protocol (unchanged blockers):**
* P2 is not met: PL needs 171 more findings from 106 more radiographs; DC needs 283 more findings from 150 more radiographs. There are
  0 clinician-verified imports.
* Both ledger disclosures (P5; the external-data run) await the owner's named authorization.
* The acceptance function, the paired bootstrap and gates R / V6 are specified but **not implemented**. They are to be written with
  tests only after approval.
