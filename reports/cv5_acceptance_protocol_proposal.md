# PROPOSAL (not approved): acceptance protocol for candidate models compared with BASE under grouped 5-fold CV

**Status: DRAFT PROPOSAL, revision 2 (2026-10-24). NOT APPROVED. Not in force.**
* Revision 1 (2026-10-24) proposed decisions D1–D10. On 2026-10-24 the owner sent **recommended decisions** for D1–D10, which this
  revision incorporates (§13).
* The owner asked that the document **not** be marked approved. Final approval, and the open points U1–U9 (§14), are still needed
  before any candidate is registered or run.
* No candidate has been trained or evaluated. Production, the deployed checkpoint, the CV5-BASE artifacts, earlier protocols and
  results, and the research paper are unchanged.
* Every threshold below is a **proposed future criterion**, not an observed result.

Inputs reviewed:
* `reports/cv5_protocol.md` and `reports/cv5_results.md` (completed CV5-BASE run, used as baseline evidence and not modified);
* `reports/cv5_base_noise.json` (BASE-vs-BASE noise; script `scripts/cv5_base_noise.py`);
* `reports/protocol_change_proposals.md` (P1–P5) and `reports/expanded_class_distribution.csv` (P2 status);
* `reports/external_data_results.md` (X2_hanoi: FAIL) and `reports/ensemble_evaluation.md` (5-seed BASE ensemble: FAIL);
* `ACCEPT` in `kaggle/dentamind_kaggle.py`;
* `src/dentexmodel/evaluation/test_ledger.py`.

---

## 1. Observed BASE evidence (completed; copied, not changed)

Source: `kaggle/artifacts_cv5_run1/cv5_results.json`, run "DentaMind 5-fold CV BASE" v1. All 88 archive files were verified against
SHA256SUMS.txt.

**Population:** 2,851 pooled out-of-fold `dentex_train_disease` findings from 541 radiographs (2,745 detector-matched), fold file
`cv5_folds_v1.csv`.

| Observed BASE (mean ± SD over seeds 42–46) | Detector boxes | GT boxes |
|---|---|---|
| Macro-F1 | 0.677 ± 0.008 (radiograph bootstrap 95 % CI 0.652–0.701) | 0.698 ± 0.007 (0.675–0.718) |
| Deep Caries precision / recall / F1 | 0.546 / 0.440 / 0.487 | 0.576 / 0.496 / 0.533 |
| Periapical Lesion precision / recall / F1 | 0.401 / 0.432 / 0.416 | 0.485 / 0.451 / 0.467 |
| ECE (10 bins) / NLL | 0.107 / 0.666 | 0.109 / 0.663 |
| Fold-level macro-F1, mean ± SD over folds (descriptive) | 0.675 ± 0.032 | 0.697 ± 0.020 |

### 1.1 BASE-vs-BASE noise (descriptive support for the margins; D10)

`scripts/cv5_base_noise.py` → `reports/cv5_base_noise.json`.
* It compares the stored BASE seeds with one another on the identical out-of-fold findings. No candidate, test image or new training
  is involved.
* **Caveat (D10):** five seeds give only a **rough** estimate of training variability. A 2-vs-3 seed split is not the same as a 5-vs-5
  comparison. The maxima below indicate scale; they are not error rates or guarantees.

| Detector boxes, BASE vs BASE | Max \|Δ\| over the 10 single-seed pairs | Max \|Δ\| between a 2-seed mean and the other 3 seeds' mean (10 splits) |
|---|---:|---:|
| Macro-F1 | 0.022 | 0.0137 |
| Deep Caries recall | 0.039 | 0.0289 |
| Periapical Lesion recall | 0.090 | 0.0467 |
| Deep Caries precision | 0.062 | 0.0321 |
| Periapical Lesion precision | 0.047 | 0.0341 |
| F1: Caries / Deep Caries / Impacted / PL | 0.007 / 0.041 / 0.019 / 0.055 | 0.0041 / 0.0265 / 0.0099 / 0.0293 |
| GT-box macro-F1 | 0.020 | 0.0097 |

Further observations:
* **Paired radiograph bootstrap** (2,000 resamples): the SD of a single-seed BASE-vs-BASE difference is about 0.013 for macro-F1 with
  detector boxes, and about 0.05 for Periapical Lesion recall.
* **Fold level:** single-seed macro-F1 differences within one fold reach up to 0.073 (SD 0.029).

---

## 2. Scope

**Applies to:** any candidate finding classifier proposed to replace BASE, evaluated by grouped 5-fold CV of the DENTEX training and
validation radiographs.

**Out of scope (each needs its own protocol):**
* tooth-detector changes;
* label-set or class-mapping changes;
* post-hoc calibration studies (§7.1);
* any change to a fold file without P4 approval.

**Not covered:** deployment. Passing this protocol means "better than BASE on DENTEX cross-validation under these rules". It is **not**
evidence of clinical acceptability, clinical validity, patient-level generalization or multi-centre performance (§8).

---

## 3. Data readiness and experiment classes (D5)

* **Confirmatory comparisons** (the only ones that can yield ACCEPT) start only when the P2 data targets are met. The P2 targets are
  provisional (owner, 2026-10-16) and the counting rule is in `scripts/dataset/expansion_report.py`.
* **Status at this revision** (`reports/expanded_class_distribution.csv`, unchanged):

  | Class | Current (train split) | P2 target | Met? |
  |---|---|---|---|
  | Periapical Lesion | 129 findings / 94 radiographs | ≥ 300 / ≥ 200 | no |
  | Deep Caries | 467 findings / 250 radiographs | ≥ 750 / ≥ 400 | no |

  0 new clinician-verified labels have been imported. **No confirmatory comparison can start today.**
* **Exploratory comparisons** before P2 is met are allowed only as a documented exception (dated amendment with reason). Their results
  are labelled **EXPLORATORY**, never get an ACCEPT verdict, and cannot be used to promote a model. They still follow §4–§9, so their
  numbers are comparable, but the verdict line reads "exploratory: criteria met / not met".
* **When P2 is met, the data changes**, so the fold file and the BASE reference must be renewed before confirmatory work:
  - P4 requires the folds to be regenerated and re-reviewed after verified labels are added;
  - BASE must be re-run under CV5 on the new fold file to produce the reference predictions;
  - see U1–U3.

---

## 4. Experiment design and candidate comparison procedure

1. **Frame:** the candidate uses exactly BASE's evaluation frame:
   * the approved fold file and its per-fold fitting / inner-validation split (`fold_plan`, inner K = 8, seed 42 + k, inner fold 0);
   * seeds 42–46;
   * the same held-out radiographs and findings;
   * the same production detector boxes (`detector_boxes_pool.json` from the BASE reference run) and the same matching (IoU ≥ 0.5,
     one-to-one).
   * Gates 1–5 of `cv5_protocol.md` apply unchanged.
2. **Pairing:** for every primary finding, fold and seed s, the candidate's held-out prediction is paired with the BASE reference
   prediction for the same finding, fold and seed s. The comparator is always BASE, never an earlier accepted candidate.
3. **BASE reference: reuse only after exact reproduction (D3).**
   - Stored BASE predictions may be reused only for the fold file they were produced on. Today that is `cv5_folds_v1.csv` with
     `kaggle/artifacts_cv5_run1/oof_predictions.csv` (SHA-256 checked).
   - **Reproduction gate R:** in the candidate's notebook and environment, before the candidate trains, the stored CV5-BASE checkpoints
     are re-evaluated on their held-out folds. The gate passes only if:
     - the predicted class equals the stored out-of-fold argmax for **every** finding, in both settings; and
     - every recomputed pooled metric equals the stored value.
   - The number of checkpoints that must be re-evaluated and the probability tolerance are open (U4). The proposed default is all 25,
     with the maximum absolute probability difference reported.
   - If gate R fails, the stored predictions are **not** used. What happens next is open (U5).
4. **Epoch selection:** same rule as BASE (best inner-validation macro-F1), unless the selection rule is itself the declared
   intervention. The held-out fold is never used for epoch selection, early stopping, thresholds, calibration or hyperparameters.
5. **Pre-registration per family round (D9):** before any training, a dated amendment fixes:
   * the candidates, at most **3** per intervention family per round;
   * each candidate's exact config diff against `EXPERIMENTS["BASE"]`;
   * how the candidates were chosen (e.g. literature, inner-validation pilot), and that the choice did not use any held-out
     out-of-fold prediction or test data;
   * the multiplicity handling (§5.1, P-B; U6).

   Hyperparameter search, if any, runs inside the inner-validation subset only. No candidate may be added to a round after any of its
   results are seen.
6. **Order of operations:** the amendment is written, then gate R, then the candidate's training, then the gates V1–V5 (§5.3), then the
   verdict.

---

## 5. Confirmatory acceptance criteria (proposed; all must pass)

**Setting:**
* primary setting: detector boxes, matched primary findings;
* statistic: seed-mean over 42–46 of pooled out-of-fold metrics;
* Δ = candidate − BASE on identical findings.

**Ties:** "beats" means Δ > 0 strictly; a tie counts as not beating.

### 5.1 Primary checks (D1, D2): all four required

| # | Check | Proposed value |
|---|---|---|
| P-A | Seed-mean Δ macro-F1 ≥ minimum practically meaningful improvement **δ** | **δ = 0.027** (D1; unchanged from `ACCEPT["gain_min"]`, above every BASE-vs-BASE difference in §1.1) |
| P-B | **Paired radiograph-level** 95 % percentile bootstrap CI of Δ macro-F1 lies entirely above 0 | 2,000 resamples, seed 0; resample the primary radiographs with replacement; both arms on the same resampled findings; statistic = seed-mean candidate − seed-mean BASE. With k > 1 candidates in a round, the confidence level is adjusted for multiplicity (proposed: Bonferroni, two-sided 1 − 0.05/k; U6) |
| P-C | Candidate beats BASE in **≥ 4 of 5 seed pairs** | Seed pair s = candidate seed s vs BASE seed s, pooled out-of-fold macro-F1 |
| P-D | Candidate beats BASE in **≥ 4 of 5 folds** | Per held-out fold: seed-mean candidate macro-F1 vs seed-mean BASE macro-F1 on that fold's matched findings |

The old cross-pair rule (≥ 20/25) is dropped (D2).

### 5.2 Per-class safeguards (D4): frozen BASE-derived margins, detector boxes, seed means

**Margin rule**, frozen before any candidate exists: take the largest 2-vs-3 BASE seed-arm |Δ| in §1.1 (detector boxes; GT for the
GT-box safeguard), round it up to the next 0.01, with a floor of 0.02. Each margin below can be traced to `reports/cv5_base_noise.json`.

| # | Safeguard: candidate Δ must be ≥ −margin | Margin | BASE 2-vs-3 max \|Δ\| |
|---|---|---:|---:|
| S1 | Deep Caries recall | **0.03** | 0.0289 |
| S2 | Periapical Lesion recall | **0.05** | 0.0467 |
| S3 | Deep Caries precision | **0.04** | 0.0321 |
| S4 | Periapical Lesion precision | **0.04** | 0.0341 |
| S5a | Caries F1 | **0.02** | 0.0041 (floor applies) |
| S5b | Deep Caries F1 | **0.03** | 0.0265 |
| S5c | Impacted F1 | **0.02** | 0.0099 (floor applies) |
| S5d | Periapical Lesion F1 | **0.03** | 0.0293 |
| S6 | GT-box macro-F1 | **0.02** | 0.0097 (GT setting; floor applies) |

This resolves the "0.02–0.03" range in D4 to exact per-class values. They are the values written in revision 1 under the same rule;
none was chosen after seeing a candidate.

**Uncertainty reporting (D4):** for every safeguard metric, the paired radiograph bootstrap 95 % CI of Δ is reported next to the
point estimate. The decision uses the point estimate against the margin.

**Interpretation limits (D4):**
* Passing a safeguard means only that the drop is within the range BASE shows against itself. It is **not** evidence of clinical
  acceptability.
* The Periapical Lesion margins are wide because the class is small (100 detector-matched findings) and BASE varies widely there. This
  does not mean PL errors matter less.

**Not covered by the owner's D4 recommendation (still open, U7):**
* S7, end-to-end recall check: DC and PL recall with unmatched findings counted as wrong, same margins as S1 and S2;
* the hard-harm rule: fail if the 95 % CI upper bound of Δ recall for DC or PL is below −margin.

Both were in revision 1. They are kept here as **proposed**, pending a decision.

**Disclosure:** the X2_hanoi and ensemble results (single split) were known when the margin rule was written. Those verdicts are not
re-adjudicated and remain FAIL under their own protocols.

### 5.3 Validity gates (a failure means NO VERDICT, not FAIL)

* **V1:** CV gates 1–5 pass for the candidate.
* **V2:** gate R passes, or the U5 fallback was applied as approved.
* **V3:** the config-diff gate passes. The candidate differs from BASE in exactly one declared family (§6).
* **V4:** all 25 runs complete (§9).
* **V5:** the archive SHA-256 and every SHA256SUMS entry verify locally before any number is reported.

### 5.4 Verdict

* **ACCEPT:** V1–V5, P-A to P-D and S1–S6 (plus S7 and the hard-harm rule if approved) all pass, **and** the comparison is
  confirmatory (§3).
* **FAIL:** any primary check or safeguard fails.
* **NO VERDICT:** any validity gate fails.
* **EXPLORATORY:** a pre-P2 exception run, reported as criteria met / not met, never ACCEPT.

There is no partial accept.

---

## 6. One intervention per experiment

| Family | Examples | Isolation rule |
|---|---|---|
| F1 Crop / input | crop size (e.g. 384 px), context padding, resolution | backbone, data, loss, sampling unchanged |
| F2 Architecture / backbone | ConvNeXt, EfficientNet, ViT; pretrained weights | crop, data, loss unchanged; a backbone-native input size is declared as part of F2 |
| F3 Training data | one external source per candidate (P3 per-source reporting), clinician-verified labels (P1) | added rows only in the fitting part; never in inner-validation or held-out; image-hash disjoint from the CV pool and the test and calibration splits |
| F4 Loss / sampling / augmentation | weights, focal loss, samplers, augmentations | one change per candidate |
| F5 Ensembling | multi-seed averaging of BASE-recipe models | separate experiment only (D6, §6.1) |

* Combinations are a **new**, separately pre-registered experiment, run only after each component has passed on its own, and compared
  with BASE.
* Ensembling is never combined with another intervention in the same experiment.

### 6.1 Ensembles (D6)

* Ensembling stays a separate family.
* If evaluated: 10 BASE-recipe seeds per fold (42–51) form **two disjoint pre-defined five-member ensembles**:
  - E1 = seeds 42–46 (the stored CV5-BASE checkpoints, after gate R);
  - E2 = seeds 47–51 (newly trained).
* The **same frozen acceptance criteria** apply. P-C ("≥ 4/5 seed pairs") cannot be computed as written, because an ensemble has no
  per-seed replicates. Proposed substitution (U8): both E1 and E2 must each satisfy P-A, P-B, P-D and all safeguards against the BASE
  5-seed mean.
* Latency (§7) is reported prominently.

---

## 7. Secondary criteria (reported; they do not change the verdict)

| Item | What is reported | Flag (D8) |
|---|---|---|
| Calibration | raw-softmax ECE (10 bins) and NLL, seed-mean, paired bootstrap Δ; reliability diagrams | **ECE worse than BASE by > 0.03** (BASE observed 0.107, detector boxes) |
| Inference latency | Tesla T4, batch 64 per crop and single crop, 5 repetitions after warm-up; ratio to BASE | **> 2× BASE** per-crop latency |
| Compute cost | **GPU-hours** for the 25 CV runs (BASE observed 1.37 h total notebook runtime); peak GPU memory | – |
| Model size | **parameter count and checkpoint size**; whether inference fits the local 4 GB GPU | – |
| Reproducibility record | environment versions, embedded code hashes, config, seeds, checkpoint manifest, fold-file hash, BASE reference hash, notebook version | missing item → V5 failure |

* A flagged candidate may still be ACCEPTED on discrimination. A flag is recorded for any later deployment decision, which is outside
  this protocol.
* No temperature or threshold may be fitted on held-out out-of-fold predictions.

### 7.1 Exploratory analyses (labelled exploratory; never part of the verdict)

* Per-fold and per-seed tables.
* Caries / Deep Caries confusion by tooth type and box size, and changes in the clinician-review list.
* Detector-unseen subset (65 old-validation radiographs).
* DENTEX official-validation findings (never trained on).
* Per-source external evaluations; the Cluj labels are definition-mapped and have a known label fault.
* Production abstention counts.
* Inner-validation temperature-scaling analyses.
* Any subgroup not declared in the amendment.

Post-hoc calibration for deployment needs its own protocol. The calibration split stays reserved.

---

## 8. Statistical units and limits

* **Independent unit:** the radiograph. DENTEX has no patient identifiers, so two radiographs of one patient may fall in different
  folds. **No patient-level independence or generalization is claimed**, and no clinical validity is claimed.
* **Folds are not independent replicates:** training sides share 3 of 4 folds. P-D is a consistency check, not a statistical test, and
  no fold-level CI is computed.
* **Seeds vary training randomness on the same data:** they are not independent samples of radiographs or patients. P-C is a
  consistency check.
* **What the bootstrap covers:** radiograph sampling, given the trained models. It does not capture training-set variation. CV is not
  claimed to give "N times more independent evidence" or a guaranteed narrower interval.
* **Detector caveat:** the detector trained on part of the pool. The detector-unseen subset is reported (exploratory).
* **Single source:** DENTEX only. No multi-centre claim.

---

## 9. Failure handling

| Event | Handling |
|---|---|
| Infrastructure failure (CUDA fault, out of memory, timeout, session loss) | resume the identical config and seed (`RESUME_FROM`); up to 3 attempts per run; logged |
| Training divergence (NaN or inf loss, collapse to one class on inner-validation) | not retried with another seed; the candidate is FAIL |
| Run still missing after 3 attempts | NO VERDICT; reported as incomplete; folds and seeds are never dropped or substituted |
| Validity-gate failure | NO VERDICT; cause documented; rerun only after a dated amendment |
| Bug found after results are seen | fix, dated amendment, rerun the **whole** candidate; both runs reported; thresholds unchanged |

Every candidate that is started is reported, including FAIL, NO VERDICT and exploratory runs.

---

## 10. Test set and ledger (D7)

* The DENTEX internal test split (73 radiographs) is never used for training, epoch selection, model selection, thresholds,
  calibration or candidate tuning. The calibration split is likewise outside CV.
* **At most one** final test evaluation may follow, and only after a candidate is ACCEPTED in a **confirmatory** comparison. It must:
  - go through `test_ledger.authorize` with a **named authorizer** and written reason;
  - respect the ledger's one-new-candidate-per-test-split-version rule;
  - be appended to the hash-chained ledger;
  - be reported as it is.
* **No tuning follows the test evaluation.** It cannot change the verdict, any threshold, or the model.
* **Which model is tested is open (U9).** CV produces 25 fold models, not one deployable model. The final model and the rule for
  training it (e.g. retraining on the full pool with a fixed epoch count) must be pre-registered before the test evaluation.
* **Precondition:** the two pending disclosures are recorded first, with the owner's named authorization:
  - P5 (the 2026-10-16 baseline test evaluation);
  - the external-data run's BASE test evaluation (`kaggle/artifacts_external_run1/ledger_disclosure_entry.json`).

---

## 11. Reporting rules

* Observed BASE values and proposed thresholds are always labelled as such. Candidate reports show both, with seed-level values,
  numbers of findings and radiographs, and CIs.
* No threshold, margin or primary metric changes after results are seen. Changes are dated amendments that apply only to candidates
  registered afterwards.
* Wording for a confirmatory pass: "accepted under the CV5 acceptance protocol on DENTEX training/validation radiographs". Never
  "clinically validated", "clinically acceptable", "generalizes to patients" or "multi-centre".
* No paper update from any candidate without a separate owner decision.

---

## 12. Relation to earlier rules

| Item | Old `ACCEPT` (single validation split; still valid for experiments already reported under it) | This proposal (CV5) |
|---|---|---|
| Gain | > 0.027, ≥ 4/5 seed pairs, ≥ 20/25 cross pairs | ≥ 0.027, paired CI > 0, ≥ 4/5 seed pairs, ≥ 4/5 folds |
| DC / PL recall | not lower | drop ≤ 0.03 / ≤ 0.05 |
| Minority precision | drop ≤ 0.10 | drop ≤ 0.04 |
| Class F1 | drop ≤ 0.05 | drop ≤ 0.02 / 0.03 / 0.02 / 0.03 (C / DC / Imp / PL) |
| GT macro-F1 | drop ≤ 0.02 | drop ≤ 0.02 |

The CV5 rule would be implemented as a new, tested function only after final approval. The existing code is unchanged.

---

## 13. Decision record (owner recommendations of 2026-10-24, incorporated; final approval pending)

| # | Owner recommendation (2026-10-24) | Where | Status |
|---|---|---|---|
| D1 | Keep δ = +0.027; paired radiograph-level 95 % CI above zero | §5.1 P-A, P-B | incorporated; pending approval |
| D2 | All four primary checks required | §5.1 | incorporated; pending approval |
| D3 | Reuse stored BASE predictions only after exact reproduction in the candidate environment | §4.3 | incorporated; details U4, U5 |
| D4 | Frozen BASE-derived margins; report uncertainty; passing is not clinical acceptability | §5.2 | incorporated, exact per-class values resolved; S7 and hard-harm rule open (U7) |
| D5 | Wait for P2 before confirmatory comparisons; exceptions documented and exploratory | §3 | incorporated; consequences U1–U3 |
| D6 | Ensembling separate; two disjoint five-member ensembles from ten seeds; same frozen protocol | §6.1 | incorporated; P-C substitution open (U8) |
| D7 | At most one final ledger-recorded test evaluation after acceptance; no later tuning | §10 | incorporated; final-model rule open (U9) |
| D8 | Flags: ECE > +0.03, latency > 2×; report GPU-hours and model size | §7 | incorporated; pending approval |
| D9 | ≤ 3 pre-specified candidates per family round; selection and multiplicity documented before running | §4.5, §5.1 | incorporated; method open (U6) |
| D10 | Accept the noise script and JSON as descriptive support, with the five-seed caveat | §1.1 | incorporated; pending approval |

## 14. Unresolved points requiring the owner's explicit decision

| # | Question | Why it matters | Proposed default (not decided) |
|---|---|---|---|
| U1 | When P2 is met and the pool grows, are the **numeric margins** kept as frozen here, or re-derived by the same rule from the new BASE CV run? | D4 says "frozen", but the margins were measured on today's 541-radiograph pool; more PL/DC data should reduce BASE noise | keep the numbers frozen; report the re-derived values alongside as information only |
| U2 | Are δ = 0.027 and the D8 flags also kept unchanged for the new pool? | Same reason as U1 | keep unchanged |
| U3 | After P2, BASE must be re-run under CV5 on the regenerated, re-approved fold file (P4). Should that BASE re-run be pre-registered as part of this protocol or as a separate amendment? | The stored predictions only cover `cv5_folds_v1.csv` | a separate short amendment naming the new fold file and its hash |
| U4 | Gate R scope: how many stored BASE checkpoints are re-evaluated (1 or all 25), and is any probability tolerance allowed besides identical predicted classes and identical metrics? | "Exact reproduction" is otherwise not fully defined | all 25 checkpoints; identical argmax and metrics required; maximum probability difference reported, not gated |
| U5 | If gate R fails: retrain BASE concurrently in the candidate environment (about 1.4 GPU-h, then use it as the comparator), or stop until the environment is fixed? | D3 covers only the success case | stop and report; retraining BASE concurrently only with owner approval per case |
| U6 | Multiplicity method for k > 1 candidates in a round | D9 requires it fixed before running | Bonferroni on the P-B confidence level (two-sided 1 − 0.05/k); other checks unadjusted |
| U7 | Keep S7 (end-to-end DC/PL recall) and the hard-harm rule from revision 1? | Not in the owner's D4 list | keep both |
| U8 | Ensemble substitute for P-C (no per-seed replicates) | D6 says "same frozen protocol", but P-C cannot be computed for an ensemble | E1 and E2 must each pass P-A, P-B, P-D and all safeguards |
| U9 | Which single model goes to the test set after an ACCEPT, and how it is trained | CV produces 25 fold models, and D7 allows one test evaluation | pre-register a full-pool retraining rule (fixed epoch count = median of the 25 selected epochs, seed 42) before any test use |

Until these points and the decisions in §13 are approved, this document is a proposal only. No candidate experiment may be registered
or run under it.
