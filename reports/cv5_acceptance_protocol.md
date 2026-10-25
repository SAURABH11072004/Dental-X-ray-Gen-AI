# CV5 acceptance protocol: candidate models compared with the BASE reference under grouped 5-fold CV

**Status: APPROVED, revision 3 (2026-10-25). In force for candidates registered after this date.**
* **Approval:** the project owner approved all open items in the session of 2026-10-25 ("you have all approval go ahead"), after two
  rounds of itemised decisions. The approval accepted the recommended option for every item still open in
  `reports/cv5_acceptance_protocol_rev3_wording.md` §R.
* **History:**
  - Revision 2: `reports/cv5_acceptance_protocol_proposal.md`, SHA-256 `98d6e223…`. It was never approved and is kept unchanged as
    the historical record.
  - Decision trail: `reports/cv5_acceptance_final_audit.md`, `reports/cv5_acceptance_decisions_needed.md`,
    `reports/cv5_acceptance_owner_decisions.md`, `reports/cv5_acceptance_protocol_rev3_wording.md`.
* **No candidate has been trained or evaluated.** Every threshold below is a **criterion for future candidates**, not an observed
  result.
* **Confirmatory work cannot start yet:** P2 is not met (§3).
* **Changes** to this protocol are dated amendments. They apply only to candidates registered afterwards, and never after any
  candidate result exists for the affected rule.

Inputs:
* `reports/cv5_protocol.md` and `reports/cv5_results.md` (CV5-BASE run 1);
* `reports/cv5_base_noise.json` (script `scripts/cv5_base_noise.py`);
* `reports/protocol_change_proposals.md` (P1–P5);
* `reports/expanded_class_distribution.csv`;
* `src/dentexmodel/evaluation/test_ledger.py`.

---

## 1. Observed BASE evidence (CV5-BASE run 1; copied, not changed)

Source: `kaggle/artifacts_cv5_run1/cv5_results.json`, run "DentaMind 5-fold CV BASE" v1. All 88 archive files were verified against
SHA256SUMS.txt.

**Population:** 2,851 pooled out-of-fold `dentex_train_disease` findings from 541 radiographs (2,745 detector-matched), fold file
`cv5_folds_v1.csv` (SHA-256 `9b767a48…`).

| Observed BASE (mean ± SD over seeds 42–46) | Detector boxes | GT boxes |
|---|---|---|
| Macro-F1 | 0.677 ± 0.008 (radiograph bootstrap 95 % CI 0.652–0.701) | 0.698 ± 0.007 (0.675–0.718) |
| Deep Caries precision / recall / F1 | 0.546 / 0.440 / 0.487 | 0.576 / 0.496 / 0.533 |
| Periapical Lesion precision / recall / F1 | 0.401 / 0.432 / 0.416 | 0.485 / 0.451 / 0.467 |
| ECE (10 bins) / NLL | 0.107 / 0.666 | 0.109 / 0.663 |
| Fold-level macro-F1, mean ± SD over folds (descriptive) | 0.675 ± 0.032 | 0.697 ± 0.020 |

### 1.1 BASE-vs-BASE noise (descriptive support for the margins)

This compares the stored BASE seeds with one another on the identical out-of-fold findings (`reports/cv5_base_noise.json`). Five seeds
give only a **rough** estimate of training variability. The maxima indicate scale; they are not error rates.

| Detector boxes, BASE vs BASE | Max \|Δ\| over the 10 single-seed pairs | Max \|Δ\|, 2-seed mean vs the other 3 seeds' mean (10 splits) |
|---|---:|---:|
| Macro-F1 | 0.022 | 0.0137 |
| Deep Caries recall | 0.039 | 0.0289 |
| Periapical Lesion recall | 0.090 | 0.0467 |
| Deep Caries precision | 0.062 | 0.0321 |
| Periapical Lesion precision | 0.047 | 0.0341 |
| F1: Caries / Deep Caries / Impacted / PL | 0.007 / 0.041 / 0.019 / 0.055 | 0.0041 / 0.0265 / 0.0099 / 0.0293 |
| GT-box macro-F1 | 0.020 | 0.0097 |

* **Paired radiograph bootstrap** (2,000 resamples): the SD of a single-seed BASE-vs-BASE difference is about 0.013 for detector-box
  macro-F1 and about 0.05 for PL recall.
* **Fold level:** single-seed macro-F1 differences reach 0.073 (SD 0.029).

---

## 2. Scope

**Applies to** any candidate finding classifier proposed to replace BASE, evaluated by grouped 5-fold CV of the DENTEX
training/validation radiographs on `cv5_folds_v1.csv`.

**Out of scope (each needs its own protocol):**
* tooth-detector changes;
* label-set or class-mapping changes;
* post-hoc calibration studies (§7.1);
* any change to `cv5_folds_v1.csv`. It is not regenerated under this protocol (§3.1); a new evaluation population needs its own
  protocol;
* label revisions of existing pool findings (§3.1 item 5).

**Not covered:** deployment. Passing means "better than the BASE reference on DENTEX cross-validation under these rules". It is
**not** evidence of clinical acceptability, clinical validity, patient-level generalization or multi-centre performance (§8).

---

## 3. Data readiness and evidence categories

* **Confirmatory comparisons** are the only ones that can yield ACCEPT. They start only when P2 is met.
  - **P2 counting basis:** P2 is met when `scripts/dataset/expansion_report.py`, run on the current manifests and verified labels,
    reports a gap of 0 findings and 0 radiographs for both Periapical Lesion and Deep Caries. It is a pool-level condition. Per-fold
    fitting counts are reported, descriptively.
  - **P2 version:** the version in force on the date a confirmatory candidate, or BASE-P2, is registered applies to it. P2 may be
    revised only before any confirmatory result exists, by a dated owner decision. In force today is the provisional P2 of 2026-10-16:
    - PL ≥ 300 findings from ≥ 200 radiographs (now 129 / 94);
    - DC ≥ 750 from ≥ 400 (now 467 / 250).
  - **What counts toward P2:** only labels admitted through the P1 route (`verified_to_manifest.py`, review-log chain verified,
    current reviewer registry) that also pass gate V6. Original DENTEX labels count as `expansion_report.py` already counts them.
  - **No confirmatory comparison can start today** (0 clinician-verified imports).
* **No exploratory candidate runs on the CV5 evaluation population.**
  - No candidate configuration is trained or evaluated on the 541 primary radiographs of `cv5_folds_v1.csv` (or their folds) except
    as a registered confirmatory candidate.
  - Candidates are chosen from information available before registration: the literature, CV5-BASE run 1, and the earlier
    single-split results already disclosed.
  - The DENTEX test split is never used to choose, rank or tune candidates.
* **Evidence categories:**

  | Category | Content | Supports | Report label |
  |---|---|---|---|
  | A1 Completed baseline | CV5-BASE run 1 (`reports/cv5_results.md`, `kaggle/artifacts_cv5_run1/`) | reference values and noise margins | "Observed BASE (CV5 run 1)" |
  | A2 Test-set history | 5 historical ledger entries; 2 pending retrospective disclosures of BASE test evaluations (2026-10-16; 2026-10-24) | context only; shows the test split is already used | "Historical test result (test split previously used)" |
  | A3 Exploratory | the §7.1 analyses, and the BASE-P2 vs CV5-BASE run 1 comparison | hypotheses only; never ACCEPT, promotion or test use, and never input to first-round candidate selection | "EXPLORATORY: not a confirmatory result" |
  | A4 Confirmatory | a candidate registered under §4.5 after P2 is met, with all validity gates passed | the only route to ACCEPT / FAIL / NO VERDICT | "Confirmatory (CV5 acceptance protocol)" |
  | A5 Future ledger test | at most one, after a confirmatory ACCEPT and the winner rule (§10.2) | descriptive only; **not** an untouched estimate | "Final test evaluation (ledger entry #…, test split previously used)" |

  A result can never be relabelled into a stricter category.

### 3.1 Imported labels and evaluation independence

1. **Evaluation labels are frozen.** Every held-out and inner-validation label is an original DENTEX expert label of
   `cv5_folds_v1.csv` (581 groups). Imports never add, remove or change an evaluation label, and the fold file is not regenerated.
   P4's regeneration note is superseded for this protocol.
2. **Imports are training-only, in every fold.** P1 rows enter the **fitting** part of every fold. They never enter inner-validation
   or a held-out fold, and never contribute to an out-of-fold metric.
3. **Only radiographs outside the evaluation population can be imported.** `build_annotation_pool.py` excludes every group that
   contains a diagnosis-labelled radiograph. `eval_locked` twins and evaluation hashes are refused at export and again in
   `verified_to_manifest.py`.
4. **Gate V6 (identity-level import independence; mandatory).** It runs before any training that uses imports. Every imported image
   must lie outside the 581-group CV pool, the calibration split, the test split and the `eval_locked` groups, on each of three checks:
   - radiograph group identity;
   - exact SHA-256;
   - the confirmed near-duplicate rule (dHash Hamming ≤ 4 **and** pixel correlation ≥ 0.97).

   Any hit is refused, and the run gets NO VERDICT until the hit is removed. Patient-level identity cannot be checked, because DENTEX
   has no patient IDs (§8).
5. **Corrections to existing pool labels are excluded.** Clinician opinions on findings already in the CV pool (for example
   `reports/cv5_caries_clinician_review_list.csv`) are used in no confirmatory comparison until an owner-approved label-revision
   protocol exists.
6. **Per-source reporting (P3)** applies to imported rows.

### 3.2 BASE reference after imports: BASE-P2

* **Recipe:** the unchanged BASE recipe, with the imports in every fold's fitting part, on the v1 folds, seeds 42–46, the same
  inner-validation and the same detector boxes.
* **Registration:** by its own dated amendment.
* **Role:**
  - **BASE-P2 is a reference run, not a candidate.** It is never ACCEPTED and does not count toward the budget.
  - It is the **predeclared comparator** for confirmatory candidates that use the imports.
  - Its training data differ from CV5-BASE run 1, because it adds the imports. Every report states this, and BASE-P2 is never
    described as the same baseline.
  - Its comparison with CV5-BASE run 1 is exploratory (A3).
* **Sequencing.** All first-round candidates are registered, with frozen configurations, **before BASE-P2 is run**, because training
  logs print metrics. Order:
  1. candidate registration amendment;
  2. BASE-P2 registration amendment;
  3. BASE-P2 run;
  4. gate R on BASE-P2 in the candidate environment;
  5. candidate training.

---

## 4. Experiment design and candidate comparison procedure

1. **Frame:** the candidate uses exactly the reference's evaluation frame:
   * the approved fold file and its per-fold fitting / inner-validation split (`fold_plan`, inner K = 8, seed 42 + k, inner fold 0);
   * seeds 42–46;
   * the same held-out radiographs and findings;
   * the same detector boxes (`detector_boxes_pool.json` of the reference run) and the same matching (IoU ≥ 0.5, one-to-one);
   * imports, if any, only in each fold's fitting part (§3.1).

   Gates 1–5 of `cv5_protocol.md` apply unchanged.
2. **Pairing:** for every primary finding, fold and seed s, the candidate's held-out prediction is paired with the reference prediction
   for the same finding, fold and seed. The comparator is always the BASE reference (CV5-BASE run 1 without imports; BASE-P2 with
   imports), never an earlier accepted candidate.
3. **Reference reuse: only after exact reproduction and an unchanged fold file.**
   - Stored reference predictions may be reused only if **both** hold:
     - (a) the fold file is byte-identical to the one they were produced on (SHA-256 `9b767a48…`, checked before use); and
     - (b) gate R passes in the candidate's notebook and environment.
   - **Gate R:** before the candidate trains, every stored checkpoint of the reference run is re-evaluated on its own held-out fold,
     in both settings, with the stored detector boxes. For BASE-P2 that is 25 checkpoints, each matched by SHA-256 to its checkpoint
     manifest.
     - **R1 (exact):** for every finding, the recomputed predicted class equals the stored out-of-fold argmax. Zero mismatches are
       allowed.
     - **R2 (tolerance):** the maximum absolute difference between recomputed and stored class probabilities, over all findings,
       classes, settings and checkpoints, is ≤ **1 × 10⁻⁴**.
     - **R3:** accuracy, macro-F1 and per-class precision / recall / F1, which are deterministic functions of the argmax, are
       recomputed and must be equal. ECE and NLL differences are reported, not gated.
     - **Recorded** in the result JSON: argmax mismatches, the maximum probability difference, and the R3 comparison.
     - Gate R runs in the candidate's Kaggle environment. A different software stack (for example the local PC) is known to change
       predictions (`reports/ensemble_evaluation.md`).
   - **If (a) or (b) fails:**
     - it is a validity failure before candidate training, and the stored predictions are not used;
     - training does not start until the cause is found, documented and resolved by a dated amendment;
     - **no budget slot is used** (§10.1).
4. **Epoch selection:** same rule as BASE (best inner-validation macro-F1), unless the selection rule is itself the declared
   intervention. The held-out fold is never used for epoch selection, early stopping, thresholds, calibration or hyperparameters.
5. **Pre-registration.** Before any training, a dated amendment fixes:
   * the candidates (at most 3 per family per round, within the budget);
   * each candidate's exact config diff against `EXPERIMENTS["BASE"]`;
   * how each was chosen. The choice used no held-out out-of-fold prediction of any candidate, no BASE-P2 result (first round), and no
     test data;
   * the running lifetime count of registered candidates (§10.1);
   * the comparator (CV5-BASE run 1 or BASE-P2).

   Hyperparameter search, if any, runs inside inner-validation only. No candidate may be added after any result of its round is seen.
6. **Order of operations:** amendment, gate V6 (if imports are used), gate R, candidate training, gates V1–V5, verdict.

---

## 5. Confirmatory acceptance criteria (all must pass)

**Setting:**
* primary setting: detector boxes, matched primary findings;
* statistic: seed-mean over 42–46 of pooled out-of-fold metrics;
* Δ = candidate − reference on identical findings.

**Unrounded comparisons:**
* All criteria are evaluated on unrounded IEEE-754 double-precision values exactly as computed. Rounding is for display only
  (3 decimals).
* The P-A operator is **≥**. The earlier single-split `ACCEPT` rule (`kaggle/dentamind_kaggle.py:501`) used **>**. The value is
  unchanged; the operator difference is disclosed.
* **Ties:** "beats" means Δ > 0 strictly.

### 5.1 Primary checks (all four required)

| # | Check | Value |
|---|---|---|
| P-A | Seed-mean Δ macro-F1 ≥ δ | **δ = 0.027** |
| P-B | Paired radiograph-level percentile bootstrap CI of Δ macro-F1: lower bound > 0 | Appendix C: `default_rng(0)`, **B = 20,000**, two-sided level **1 − 0.05/15** (percentiles 0.16667 and 99.83333) |
| P-C | Candidate beats the reference in ≥ 4 of 5 seeds | for each seed s: pooled out-of-fold macro-F1 of candidate seed s minus reference seed s, detector boxes, matched primary findings; > 0 for ≥ 4 of 5 |
| P-D | Candidate beats the reference in ≥ 4 of 5 folds | per held-out fold: seed-mean candidate macro-F1 minus seed-mean reference macro-F1 on that fold's matched findings; > 0 for ≥ 4 of 5 |

### 5.2 Safeguards (frozen margins from CV5-BASE run 1; detector boxes, seed means unless stated)

**Margin rule**, frozen before any candidate exists: take the largest 2-vs-3 BASE seed-arm |Δ| in §1.1, round it up to the next 0.01,
with a floor of 0.02. None was chosen after seeing any candidate's CV5 results. The earlier single-split X2_hanoi and ensemble results
were known; those verdicts remain FAIL under their own protocols. The margins are **not** re-derived from BASE-P2. They, δ and the D8
flags stay fixed for the first confirmatory round; any later recalibration needs a new, prospectively registered protocol.

| # | Candidate Δ must be ≥ −margin | Margin |
|---|---|---:|
| S1 | Deep Caries recall | 0.03 |
| S2 | Periapical Lesion recall | 0.05 |
| S3 | Deep Caries precision | 0.04 |
| S4 | Periapical Lesion precision | 0.04 |
| S5a–d | F1: Caries / Deep Caries / Impacted / Periapical Lesion | 0.02 / 0.03 / 0.02 / 0.03 |
| S6 | GT-box macro-F1 (GT setting, all primary findings) | 0.02 |
| S7 | **End-to-end** recall of Deep Caries / Periapical Lesion: all primary findings, unmatched counted wrong | 0.03 / 0.05 |

**Hard-harm rule (H):**
* **Protected quantities:** Deep Caries and Periapical Lesion, recall and precision (detector boxes).
* **Interval:** the paired percentile bootstrap of Appendix C, on the same draws, at the **unadjusted two-sided 95 % level**
  (percentiles 2.5 / 97.5).
* **FAIL if the upper bound of the Δ interval is < 0** for any of the four quantities, i.e. a statistically clear decrease, even when
  the point estimate is within the S margin.
* **Why unadjusted:** a multiplicity-adjusted, wider interval would make harm harder to detect and so favour candidates.
* Frozen; never used to select among candidates.

**Uncertainty reporting:** for every safeguard metric, the 95 % paired bootstrap CI of Δ is reported next to the point estimate. S1–S7
decide on the point estimate against the margin.

**Interpretation limits:**
* Passing a safeguard means only that the drop is within the range BASE shows against itself, or that no clear decrease was detected.
  It is not evidence of clinical acceptability.
* The PL margins are wide because the class is small (100 detector-matched findings). This does not mean PL errors matter less.

### 5.3 Validity gates (a failure means NO VERDICT, not FAIL)

* **V1:** CV gates 1–5 pass for the candidate.
* **V2:** gate R and the fold-file check pass (§4.3).
* **V3:** the config-diff gate passes. The candidate differs from BASE in exactly one declared family (§6), or is a registered
  combination.
* **V4:** all 25 runs complete (§9).
* **V5:** the archive SHA-256 and every SHA256SUMS entry verify locally before any number is reported.
* **V6:** gate V6 passes (§3.1 item 4), for every candidate or reference run that uses imports.

### 5.4 Verdict

* **ACCEPT:** V1–V6, P-A to P-D, S1–S7 and H all pass, **and** the comparison is confirmatory (§3).
* **FAIL:** any primary check, safeguard or H fails, or a divergence occurs (§9).
* **NO VERDICT:** any validity gate fails, or an infrastructure or incomplete outcome (§9).
* **EXPLORATORY** applies only to A3 analyses. No candidate receives an exploratory verdict.

There is no partial accept.

---

## 6. One intervention per experiment

| Family | Examples | Isolation rule |
|---|---|---|
| F1 Crop / input | crop size (e.g. 384 px), context padding, resolution | backbone, data, loss, sampling unchanged |
| F2 Architecture / backbone | ConvNeXt, EfficientNet, ViT; pretrained weights | crop, data, loss unchanged; a backbone-native input size is declared as part of F2 |
| F3 Training data | one external source per candidate (P3 per-source reporting) | added rows only in the fitting part; gate V6; never in inner-validation or held-out |
| F4 Loss / sampling / augmentation | weights, focal loss, samplers, augmentations | one change per candidate |
| F5 Ensembling | multi-seed averaging of reference-recipe models | separate experiment only (§6.1) |

* Combinations are separately registered experiments of individually ACCEPTED components, compared with the reference.
* Ensembling is never combined with another intervention.

### 6.1 Ensembles

* **Members:** two disjoint five-member ensembles per fold.
  - **E1** = seeds 42–46 of the reference run for the training data in force: BASE-P2 for confirmatory work with imports, CV5-BASE
    run 1 only if the ensemble is registered without imports.
  - **E2** = seeds 47–51, trained with the same recipe and the same data (including the same imports).
  - E1 shares its members with the comparator, so only E2 is an independent replication.
* **Passing:** E1 and E2 must **each** pass P-A, P-B, P-D, every applicable safeguard (S1–S7) and H against the reference 5-seed mean.
  P-D is computed per fold against the reference seed-mean on the same held-out radiographs. P-C is not applicable.
* The F5 design is one candidate configuration in the budget. Latency (§7) is reported prominently.

---

## 7. Secondary criteria (reported; they do not change the verdict)

| Item | What is reported | Flag |
|---|---|---|
| Calibration | raw-softmax ECE (10 bins) and NLL, seed-mean, paired bootstrap Δ; reliability diagrams | ECE worse than the reference by > 0.03 |
| Inference latency | measured in the candidate's notebook session, same GPU, same script; the candidate and one reference checkpoint each at batch 64 (time per crop) and at batch 1; 5 repetitions after warm-up; median | either ratio (candidate / reference) > 2. Earlier measurements (ensemble report) are not the reference |
| Compute cost | (i) total notebook wall-clock runtime; (ii) the sum of per-run training times from `runs/*__result.json`, for the candidate and the reference run, with GPU type and count; peak GPU memory. CV5-BASE run 1: 1.37 h total runtime, including downloads | – |
| Model size | parameter count and checkpoint size; whether inference fits the local 4 GB GPU | – |
| Reproducibility record | environment versions, embedded code hashes, config, seeds, checkpoint manifest, training manifests, fold-file hash, reference hash, notebook version | missing item → V5 failure |

* A flagged candidate may still be ACCEPTED. The flag is recorded for any later deployment decision, which is outside this protocol.
* No temperature or threshold may be fitted on held-out out-of-fold predictions.

### 7.1 Exploratory analyses (never part of the verdict)

* Per-fold and per-seed tables.
* Caries / Deep Caries confusion by tooth type and box size.
* Detector-unseen subset.
* DENTEX official-validation findings.
* Per-source external evaluations.
* Production abstention counts.
* Inner-validation temperature-scaling analyses.
* Any undeclared subgroup.
* BASE-P2 vs CV5-BASE run 1.

The calibration split stays reserved.

---

## 8. Statistical units and limits

* **Independent unit:** the radiograph. DENTEX has no patient identifiers. Identity checks (V6) are radiograph-level. **No
  patient-level independence or generalization is claimed**, and no clinical validity is claimed.
* **Folds are not independent replicates:** training sides share 3 of 4 folds. P-D is a consistency check.
* **Seeds vary training randomness on the same data.** P-C is a consistency check.
* **What the bootstrap covers:** radiograph sampling, given the trained models. It does not capture training-set variation. CV is not
  claimed to give "N times more independent evidence" or a guaranteed narrower interval.
* **Multiplicity:** P-B uses Bonferroni with a fixed lifetime k = 15. This controls the chance of any false P-B pass over the whole
  budget at 0.05 under any dependence, at the cost of a stricter interval.
* **No independent confirmation of the winner exists inside this design.**
  - Every confirmatory candidate is evaluated on the same 541 primary radiographs.
  - The winner's Δ is optimistically biased by selection.
  - The fold 0 report of §10.3 comes from the same radiographs.
* **Detector caveat:** the detector trained on part of the pool.
* **Single source:** DENTEX only.

---

## 9. Failure handling and run classification

Each training run (fold × seed) is classified from its log. The classification is recorded in the result JSON **before** any verdict
and is not changed afterwards.

| Class | Definition | Handling | Candidate outcome |
|---|---|---|---|
| **Infrastructure failure** | the log ends in an exception outside the forward, backward or loss computation: CUDA runtime error, out of memory, process timeout, lost session | retried with the identical config and seed, up to **3 attempts** in total per run (`train_run_isolated(attempts=3)`, `kaggle/dentamind_kaggle.py:535`; `RESUME_FROM`); every attempt logged | any run still failing after 3 attempts: **NO VERDICT** |
| **Divergence** | (i) training loss NaN or ±inf at any logged step; or (ii) **collapse**: at the selected epoch, ≥ **0.99** of the run's inner-validation GT-box predictions fall in one class | not retried | **FAIL** |
| **Incomplete** | integrity gate 4 or 5 fails for a reason not covered above | folds and seeds are never dropped or substituted | **NO VERDICT** |

**Collapse population:**
* all four-class primary findings in that run's inner-validation part (`fold_plan.json`), predicted with GT boxes, at the selected
  epoch;
* computed from the predicted-class column sums of `runs/<run>__result.json` → `val_gt.confusion`;
* compared unrounded.

For reference (CV5-BASE run 1, descriptive): the largest share was 0.586–0.711 across the 25 runs, always Caries.

**Budget accounting:**
* A candidate counts toward the lifetime budget (§10.1) once its training starts, at the first training step of any of its runs.
  From then on every outcome counts.
* A validity failure **before** candidate training (fold-file check, gate V6, gate R) uses no slot. Its cause must be resolved first.
* A registered candidate cannot otherwise be withdrawn before it starts. A withdrawal anyway **counts as a used slot**, because
  reference results may be visible after registration.

**Other events:**
* Validity-gate failure: NO VERDICT, with the cause documented.
* Bug found after results are seen: fix it, write a dated amendment, rerun the whole candidate, and report both runs. Thresholds stay
  unchanged.

Every registered candidate is reported.

---

## 10. Budget, winner, test set and ledger

### 10.1 Candidate budget
* **Lifetime budget: 15 candidate configurations.**
  - 3 for each of the families F1–F4;
  - 1 F5 ensemble design;
  - 2 combinations of individually ACCEPTED components.
* Counting follows §9. The budget is never reset by rounds or amendments. Only a recorded owner decision can enlarge it; an enlargement
  is disclosed in every later report and requires a new multiplicity amendment before any further candidate runs.
* BASE-P2 and gate-R reproductions are reference runs and do not count.

### 10.2 Winner rule
* **Eligible:** confirmatory candidates that pass **every** criterion (verdict ACCEPT).
* **Order:** each step breaks only exact ties of the previous step, on unrounded values:
  1. highest seed-mean Δ macro-F1 (detector boxes; the P-A quantity);
  2. higher P-B lower bound;
  3. fewer trainable parameters;
  4. earlier registration timestamp.
* **Scope:** within a family the rule gives the family winner. Across all eligible candidates, including ACCEPTED combinations, it gives
  the single candidate that may proceed to §10.3.
* **Reporting:** the winner's Δ is reported as optimistically biased by selection. The other ACCEPTED candidates are reported in full.
* Selection is never re-run after test results exist.

### 10.3 Final artifact and its validation report (V-a)
* **Final artifact:** the winner's **fold 0, seed 42** checkpoint from its confirmatory CV5 run.
  - Fixed on 2026-10-25, before any candidate exists, by the rule "lowest fold index, lowest seed".
  - There is no retraining: no full-pool retrain and no fixed-epoch rule.
* **Conditions.** All must hold, or there is no test evaluation:
  1. **Genuine training manifest**, written by the checkpoint's own training run at training time and never reconstructed afterwards.
  2. **Verified checkpoint hash.** The downloaded checkpoint's SHA-256 equals the entries in `checkpoint_manifest.json`, in
     `runs/<run>__cv_run.json` (`checkpoint_sha256`), and in the training manifest.
  3. **Held-out report from stored predictions only.**
     - It is computed from `runs/<run>__heldout_pred.npz`, verified against the run's `SHA256SUMS.txt`. **No new inference.**
     - It is written as the `eval_<version>_val.json` that `test_ledger.authorize` requires, with the checkpoint's `checkpoint_sha256`.
     - It is labelled "held-out CV fold 0 (stored predictions)". The ledger's validation-first requirement and its code are not
       changed.
  4. **Disclosure**, in that report and in every test report:
     > "Held-out fold 0 was part of the population on which all confirmatory candidates were compared and the winner was selected.
     > This report is independent of the checkpoint's training data but not independent confirmation of the selected winner."

### 10.4 Test-set use
* The DENTEX internal test split (73 radiographs) and the calibration split are never used for training, epoch selection, candidate
  selection, ranking, thresholds, calibration or tuning.
* **At most one** final test evaluation, of the §10.3 artifact only, after a confirmatory ACCEPT. It:
  - goes through `test_ledger.authorize` with a named authorizer and written reason;
  - respects the one-new-candidate-per-split-version rule;
  - is appended to the hash-chained ledger;
  - is reported as it is.
* **The test result is not an untouched or unbiased estimate.** The split has 5 historical ledger entries and two BASE test
  evaluations (2026-10-16, 2026-10-24). Every report carries the `test_status_for_report` block.
* No tuning follows the test evaluation.
* **Precondition:** both pending disclosures (`reports/p5_disclosure_entry.json`;
  `kaggle/artifacts_external_run1/ledger_disclosure_entry.json`) are recorded with the owner's named authorization.

---

## 11. Reporting rules

* Observed values and thresholds are always labelled as such. Candidate reports show both, with seed-level values, numbers of findings
  and radiographs, and CIs.
* No threshold, margin or primary metric changes after results are seen.
* Wording for a confirmatory pass: "accepted under the CV5 acceptance protocol on DENTEX training/validation radiographs". Never
  "clinically validated", "clinically acceptable", "generalizes to patients" or "multi-centre".
* No paper update from any candidate without a separate owner decision.

---

## 12. Relation to earlier rules

| Item | Old `ACCEPT` (single validation split; valid for experiments already reported under it) | This protocol |
|---|---|---|
| Gain | > 0.027, ≥ 4/5 seed pairs, ≥ 20/25 cross pairs | ≥ 0.027, paired CI (k = 15) > 0, ≥ 4/5 seeds, ≥ 4/5 folds |
| DC / PL recall | not lower | drop ≤ 0.03 / ≤ 0.05; end-to-end likewise; no clear decrease (H) |
| Minority precision | drop ≤ 0.10 | drop ≤ 0.04; no clear decrease (H) |
| Class F1 | drop ≤ 0.05 | drop ≤ 0.02 / 0.03 / 0.02 / 0.03 |
| GT macro-F1 | drop ≤ 0.02 | drop ≤ 0.02 |

The CV5 rule is implemented as a new function (`kaggle/cv5_accept.py`). The existing `ACCEPT` code is unchanged.

---

## 13. Decision record

| # | Decision | Date | Where |
|---|---|---|---|
| D1–D10 | owner recommendations (revision 2) | 2026-10-24 | throughout |
| B-1, B-3 | imports training-only; frozen v1 evaluation population; gate V6 | 2026-10-25 | §3.1 |
| B-2 | BASE-P2 is a reference; its comparison with BASE is exploratory | 2026-10-25 | §3.2 |
| B-4 | corrections to pool labels excluded | 2026-10-25 | §3.1 |
| D-1 | 15-candidate lifetime budget | 2026-10-25 | §10.1 |
| D-2 | no exploratory candidates on the CV5 population; no test-set selection | 2026-10-25 | §3 |
| D3 | reference reuse only after exact reproduction and with an unchanged fold file | 2026-10-25 | §4.3 |
| D-3 | winner rule | 2026-10-25 | §10.2 |
| E-1 | collapse ≥ 99 %; failure classes | 2026-10-25 | §9 |
| E-2 / V-a | procedural report rejected; fold 0 / seed 42 with four conditions | 2026-10-25 | §10.3 |
| E-3 | wording fixes | 2026-10-25 | §3, §5, §6.1, §7, §10.4 |
| U1, U2 | margins, δ and flags fixed for the first round; no re-derivation from BASE-P2 | 2026-10-25 | §5.2 |
| U3 | register before BASE-P2 is run; BASE-P2 is the comparator | 2026-10-25 | §3.2 |
| U4 | gate R: R1 exact, R2 ≤ 1 × 10⁻⁴, R3 | 2026-10-25 | §4.3 |
| U5 | pre-training validity failure uses no slot; withdrawal counts | 2026-10-25 | §9 |
| U6 | Bonferroni, fixed lifetime k = 15; B = 20,000 | 2026-10-25 | §5.1, App. C |
| U7 | S7 mandatory; H at unadjusted 95 %, DC/PL recall and precision, fail if upper bound < 0 | 2026-10-25 | §5.2 |
| U8 | E1 and E2 each pass every applicable criterion; P-D per fold against the reference | 2026-10-25 | §6.1 |
| U9 | final artifact per V-a; no full-pool retrain | 2026-10-25 | §10.3 |

---

## Appendix C. Paired radiograph-level bootstrap

**C.1 Inputs.**
* For each arm A ∈ {reference, candidate}, each seed s ∈ {42…46} and each primary finding i: one out-of-fold predicted class in each
  setting (detector boxes, GT boxes).
* The detector-matched flag of each finding, from the reference run's `detector_boxes_pool.json`.
* The radiograph group of each finding, from the fold file.
* **Primary radiographs:** the groups of the `dentex_train_disease` findings (541).

**C.2 Point estimates.**
* For each arm, setting and seed: the metric on **all** findings of the setting. In the detector setting these are the matched
  findings; for S7, all primary findings with unmatched counted wrong.
* Macro-F1 is the mean of the four per-class F1 values. An undefined precision, recall or F1 counts as 0.
* Seed-mean: M_A = (1/5) Σ_s metric_A,s. Δ = M_candidate − M_reference.

**C.3 Bootstrap.**
1. One generator, `numpy.random.default_rng(0)`, created once per comparison.
2. Repeat **B = 20,000** times:
   - draw 541 primary radiographs **with replacement**;
   - take all findings of each drawn radiograph, with multiplicity;
   - in the detector setting, drop unmatched findings **after** drawing.
3. In each resample, compute the metric for all 10 arm-seed combinations on the same multiset of findings.
   Δ_b = mean over seeds of the candidate metric − mean over seeds of the reference metric.
4. The same draws are reused for every metric and every setting.
5. **CI:** the percentile interval of {Δ_b} (`numpy.percentile`, linear interpolation).
   - P-B: two-sided level 1 − 0.05/15, i.e. percentiles 100·(0.025/15) and 100·(1 − 0.025/15).
   - Safeguard reporting and H: 2.5 / 97.5.
6. **P-B passes** if the lower percentile is > 0. **H fails** if any protected upper 97.5 percentile is < 0.
7. **Degenerate resamples:** a class with zero support has recall and F1 counted as 0 for both arms. The count of such resamples per
   class is reported. Resamples are never discarded.
8. **Recorded** in the result JSON: the seed, B, k, a hash of the ordered drawn group IDs, and every Δ_b of macro-F1.
