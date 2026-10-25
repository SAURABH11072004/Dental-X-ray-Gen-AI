# Cross-validated baseline and a pre-registered acceptance protocol for finding classification on panoramic dental radiographs (DENTEX)

**Document status (2026-10-25): finalized DRAFT v1, NOT SUBMITTED.**
* Supersedes nothing: the earlier draft `reports/manuscript/DentaMind_CV5_manuscript_DRAFT.md` is kept unchanged.
* Scope: a **baseline-and-protocol report**. It makes **no improvement claim**, contains **no candidate results** and **no clinical
  validation claim**.
* Every result number carries a bracketed source tag in the same paragraph, bullet or table row:
  - a row ID of `reports/results_traceability.json` (CV5-BASE run 1);
  - a `neg.` row ID of `reports/negative_findings_traceability.json` (earlier validation-split experiments);
  - a `cv5:` JSON path, read directly from the checksum-verified `kaggle/artifacts_cv5_run1/cv5_results.json`.
* `scripts/audit_manuscript_numbers.py` checks every tag, every number and every citation key; its report is
  `reports/manuscript/manuscript_v1_number_audit.md`.
* Declarations, venue formatting and bibliography verification are author tasks (`reports/manuscript/publication_readiness_checklist_v1.md`).

**Authors:** Nilesh Sonawane, Saurabh Mali, Sadhyoj Hanwate, Sachet Lothe.
**Guide:** Dr. Pradnya Narkhede, Department of Computer Engineering, PCCOE, Pune.
*[Author order, affiliations, corresponding author and contribution statements: to be confirmed by the authors.]*

---

## Abstract

**Background.** Classifiers of dental findings on panoramic radiographs are often reported on a single train/test split. For rare
classes, such estimates depend strongly on the split.

**Methods.** We evaluated a ResNet-50 finding classifier [CITE: resnet] on the disease subset of DENTEX [CITE: hamamciArxiv] with
grouped 5-fold cross-validation at radiograph level. The pool held 2,851 findings on 541 radiographs `[pop.findings]` `[pop.radiographs]`.
We trained five seeds per fold and computed a radiograph-level bootstrap. Findings were classified from ground-truth (GT) boxes and from
boxes of a Faster R-CNN tooth detector [CITE: ren].

**Results.** Detector-box macro-F1 was 0.677 ± 0.008 (95 % CI 0.652–0.701) `[det_matched.macro_f1.mean]` `[det_matched.macro_f1.sd]` `[det_matched.boot.ci95]`.
GT-box macro-F1 was 0.698 ± 0.007 (95 % CI 0.675–0.718) `[gt.macro_f1.mean]` `[gt.macro_f1.sd]` `[gt.boot.ci95]`.
Recall was lowest for Deep Caries (0.440) and Periapical Lesion (0.432) on detector boxes `[det_matched.Deep Caries.recall.mean]` `[det_matched.Periapical Lesion.recall.mean]`.
Three earlier improvement attempts (re-weighting and sampling strategies, external training data, a seed ensemble) all failed their
pre-registered acceptance rules. We also froze an acceptance protocol for future candidates before any candidate was trained.

**Conclusions.** The baseline is moderate overall and weakest on the two clinically most important classes. These cross-validated
estimates are the reference for any later claim of improvement. All results are radiograph-level and from a single public dataset;
the system has no clinical validation.

## 1. Introduction

Deep learning has been applied to many tasks on dental radiographs:
* tooth detection and numbering [CITE: tang; ayhan];
* periapical lesion detection [CITE: szabo];
* caries detection [CITE: bittar];
* multi-label diagnosis [CITE: raeisi];
* reviews of the field [CITE: putra; peker].

The DENTEX challenge provides hierarchically annotated panoramic radiographs with four diagnosis classes [CITE: hamamciArxiv; hamamciMiccai].

Two problems limit what single-split results can show:
1. **Leakage and split dependence** threaten the reproducibility of ML-based science [CITE: kapoor].
2. **Rare classes give unstable estimates.** In our pool, Periapical Lesion accounts for 645 GT-box predictions over five seeds, i.e. one per finding and seed, against 8,775 for Caries `[cv5:summary/gt/confusion_sum_over_seeds/3]` `[cv5:summary/gt/confusion_sum_over_seeds/0]`.

**Contributions** (only those the evidence supports):
1. A grouped 5-fold cross-validated baseline with seed and radiograph-bootstrap uncertainty. Its artifacts are archived and every number
   is traceable by SHA-256.
2. An error analysis of the Caries / Deep Caries / Periapical Lesion confusions.
3. A report of three negative results under their own pre-registered rules.
4. A hash-frozen acceptance protocol for future candidates, with explicit safeguards against post-hoc selection.

We do **not** claim that any model improves on the baseline.

## 2. Data

**Source.** DENTEX [CITE: hamamciArxiv], quadrant-enumeration-disease subset, with English diagnosis labels in four classes: Caries,
Deep Caries, Impacted and Periapical Lesion. *[Licence and terms of use: the authors must quote them from the official DENTEX source.]*

**Population.**
* Primary pool: 2,851 findings on 541 radiographs `[pop.findings]` `[pop.radiographs]`.
* Of these, 2,745 findings were matched to a detector box `[pop.det_matched]`.
* Secondary set: 159 findings of the DENTEX official validation release `[secondary.findings]`.

**Grouping and leakage control.**
* Radiograph groups merge exact duplicates (SHA-256) and confirmed near-duplicates (difference hash within a Hamming distance of 4 and
  thumbnail correlation of at least 0.97).
* Folds are assigned by group. The fold file is `data/splits/cv5_folds_v1.csv` (SHA-256 `9b767a48…`).

**Patient identity.** DENTEX provides no patient identifiers. Independence holds at radiograph level only, and we draw no
patient-level conclusion.

**Held-out data.**
* The project's calibration and test splits were read by no CV run.
* The internal test split has been used before: 5 historical ledger entries, plus two BASE test evaluations whose disclosures await
  authorization. No test result is reported here, and any future one would not be an untouched estimate.

**Clinician-verified labels.** None exist. All labels are the original DENTEX expert labels.

## 3. Methods

### 3.1 Classifier and detector
* **Classifier:** ResNet-50 [CITE: resnet] pretrained on ImageNet [CITE: imagenet], with a 4-way head.
  - Size: 23,516,228 trainable parameters `[cost.parameters]`.
  - Input: 224-pixel crops with 0.10 context padding.
  - Loss: inverse-frequency class weights capped at 5.
  - Optimiser: AdamW, learning rate 3e-4, weight decay 1e-4.
  - Schedule: 15 epochs, batch size 32.
  - Augmentation: horizontal flip and contrast.
* **Detector:** the project's Faster R-CNN with a feature pyramid network [CITE: ren; fpn].
  - Detector boxes are matched one-to-one to findings at IoU ≥ 0.5.
  - The detector was trained on part of the pool; see §5.

### 3.2 Cross-validation
* 5 folds × seeds 42–46 gives 25 training runs.
* Each run trains on four folds, minus a group-disjoint inner validation split that is used only to select the epoch.
* Every held-out finding receives exactly one prediction per seed.

### 3.3 Statistics
* **Metrics:** macro-F1 and per-class precision, recall and F1, reported as the mean ± SD over seeds of pooled out-of-fold predictions.
* **Uncertainty:** a radiograph-level percentile bootstrap (2,000 resamples, seed 0) of the seed-mean macro-F1.
* **Calibration:** expected calibration error (ECE) with 10 bins [CITE: naeini; guo].
* **Evaluation settings for recall.** Three settings are reported, and the values must not be mixed:
  1. *GT boxes:* every primary finding is classified from its annotated box.
  2. *Detector boxes (matched):* only the 2,745 findings with a matched detector box `[pop.det_matched]`.
  3. *End-to-end:* all 2,851 primary findings `[pop.findings]`; a finding without a matched detector box counts as an error.

### 3.4 Pre-registered acceptance protocol for future candidates
The protocol is `reports/cv5_acceptance_protocol.md` (revision 3, SHA-256 `0771b5f8…`).
* **Approval.** The file records approval by the project owner in the session of 2026-10-25. That approval is a written statement in
  the protocol file, not a signed record.
* **Status.** No candidate has been trained or evaluated under it.

A candidate is accepted only if all of the following hold, against the BASE reference:
* **P-A:** seed-mean Δ macro-F1 ≥ 0.027.
* **P-B:** the lower bound of a paired radiograph-level percentile bootstrap interval of Δ macro-F1 is > 0, at the two-sided level
  1 − 0.05/15 (B = 20,000). This is a Bonferroni correction over a fixed lifetime budget of 15 candidate configurations.
* **P-C and P-D:** the candidate wins in at least 4 of 5 seeds and in at least 4 of 5 folds.
* **S1–S7:** class safeguards with frozen margins, covering Deep Caries and Periapical Lesion recall and precision, per-class F1,
  GT-box macro-F1 and end-to-end minority recall.
* **H (hard harm):** fail if the unadjusted 95 % paired interval of Δ lies wholly below zero for Deep Caries or Periapical Lesion
  recall or precision.

**Safeguards against post-hoc analysis** (all from the protocol text):
* **Fixed in advance:** thresholds, margins and the lifetime budget were frozen before any candidate existed.
* **Registration and budget:** candidates must be registered with frozen configurations before the reference re-run (BASE-P2), and
  each one counts toward the budget once its training starts.
* **Frozen labels:** evaluation labels are frozen; label revisions enter no confirmatory comparison without an approved label-revision
  process.
* **Test-set control:** the test split may be used at most once, for a confirmatory winner, through a hash-chained ledger with a named
  authorizer. Even then it is reported as a previously used split.
* **Disclosure:** the margins were set after the earlier single-split results of §4.6 were known. Those verdicts stay FAIL under their
  own protocols and are not re-evaluated.

## 4. Results (CV5-BASE run 1)

### 4.1 Overall performance

**Table 1. Pooled out-of-fold macro-F1** (mean ± SD over five seeds; radiograph-bootstrap 95 % CI).

| Setting | Macro-F1 | 95 % CI | Accuracy | Source |
|---|---|---|---|---|
| Detector boxes (matched) | 0.677 ± 0.008 | 0.652–0.701 | 0.807 | `[det_matched.macro_f1.mean]` `[det_matched.macro_f1.sd]` `[det_matched.boot.ci95]` `[det_matched.accuracy.mean]` |
| GT boxes | 0.698 ± 0.007 | 0.675–0.718 | 0.804 | `[gt.macro_f1.mean]` `[gt.macro_f1.sd]` `[gt.boot.ci95]` `[gt.accuracy.mean]` |

### 4.2 Per-class performance

**Table 2. Per-class precision, recall and F1** (mean ± SD over seeds).

| Class | Setting | Precision | Recall | F1 | Source |
|---|---|---|---|---|---|
| Caries | detector | 0.848 ± 0.003 | 0.883 ± 0.007 | 0.865 ± 0.003 | `[det_matched.Caries.precision.mean]` `[det_matched.Caries.precision.sd]` `[det_matched.Caries.recall.mean]` `[det_matched.Caries.recall.sd]` `[det_matched.Caries.f1.mean]` `[det_matched.Caries.f1.sd]` |
| Caries | GT | 0.847 ± 0.004 | 0.874 ± 0.005 | 0.860 ± 0.004 | `[gt.Caries.precision.mean]` `[gt.Caries.precision.sd]` `[gt.Caries.recall.mean]` `[gt.Caries.recall.sd]` `[gt.Caries.f1.mean]` `[gt.Caries.f1.sd]` |
| Deep Caries | detector | 0.546 ± 0.024 | 0.440 ± 0.018 | 0.487 ± 0.017 | `[det_matched.Deep Caries.precision.mean]` `[det_matched.Deep Caries.precision.sd]` `[det_matched.Deep Caries.recall.mean]` `[det_matched.Deep Caries.recall.sd]` `[det_matched.Deep Caries.f1.mean]` `[det_matched.Deep Caries.f1.sd]` |
| Deep Caries | GT | 0.576 ± 0.018 | 0.496 ± 0.012 | 0.533 ± 0.012 | `[gt.Deep Caries.precision.mean]` `[gt.Deep Caries.precision.sd]` `[gt.Deep Caries.recall.mean]` `[gt.Deep Caries.recall.sd]` `[gt.Deep Caries.f1.mean]` `[gt.Deep Caries.f1.sd]` |
| Impacted | detector | 0.935 ± 0.011 | 0.945 ± 0.007 | 0.940 ± 0.007 | `[det_matched.Impacted.precision.mean]` `[det_matched.Impacted.precision.sd]` `[det_matched.Impacted.recall.mean]` `[det_matched.Impacted.recall.sd]` `[det_matched.Impacted.f1.mean]` `[det_matched.Impacted.f1.sd]` |
| Impacted | GT | 0.913 ± 0.013 | 0.949 ± 0.009 | 0.931 ± 0.007 | `[gt.Impacted.precision.mean]` `[gt.Impacted.precision.sd]` `[gt.Impacted.recall.mean]` `[gt.Impacted.recall.sd]` `[gt.Impacted.f1.mean]` `[gt.Impacted.f1.sd]` |
| Periapical Lesion | detector | 0.401 ± 0.020 | 0.432 ± 0.033 | 0.416 ± 0.023 | `[det_matched.Periapical Lesion.precision.mean]` `[det_matched.Periapical Lesion.precision.sd]` `[det_matched.Periapical Lesion.recall.mean]` `[det_matched.Periapical Lesion.recall.sd]` `[det_matched.Periapical Lesion.f1.mean]` `[det_matched.Periapical Lesion.f1.sd]` |
| Periapical Lesion | GT | 0.485 ± 0.019 | 0.451 ± 0.047 | 0.467 ± 0.033 | `[gt.Periapical Lesion.precision.mean]` `[gt.Periapical Lesion.precision.sd]` `[gt.Periapical Lesion.recall.mean]` `[gt.Periapical Lesion.recall.sd]` `[gt.Periapical Lesion.f1.mean]` `[gt.Periapical Lesion.f1.sd]` |

### 4.3 Recall in context: three evaluation settings
The same minority-class recall gives different numbers in the three settings of §3.3. They answer different questions:
* **GT boxes:** how well the classifier separates classes given a perfect box.
  - Deep Caries 0.496 `[gt.Deep Caries.recall.mean]`.
  - Periapical Lesion 0.451 `[gt.Periapical Lesion.recall.mean]`.
* **Detector boxes (matched):** classification quality on the subset that the detector localises.
  - Deep Caries 0.440 `[det_matched.Deep Caries.recall.mean]`.
  - Periapical Lesion 0.432 `[det_matched.Periapical Lesion.recall.mean]`.
* **End-to-end** (unmatched findings count as errors): what a user of the full pipeline would see. Per seed:
  - Deep Caries 0.375 to 0.410 `[e2e.seed42.Deep Caries.recall]` `[e2e.seed43.Deep Caries.recall]` `[e2e.seed44.Deep Caries.recall]` `[e2e.seed45.Deep Caries.recall]` `[e2e.seed46.Deep Caries.recall]`.
  - Periapical Lesion 0.302 to 0.372 `[e2e.seed42.Periapical Lesion.recall]` `[e2e.seed43.Periapical Lesion.recall]` `[e2e.seed44.Periapical Lesion.recall]` `[e2e.seed45.Periapical Lesion.recall]` `[e2e.seed46.Periapical Lesion.recall]`.

None of these is a test-set or clinical sensitivity. Below a detection operating point, a missed lesion stays missed.

### 4.4 Variation across folds and subsets
* **Folds** (descriptive only: the training sides share three of four folds, so folds are not independent replicates).
  - Detector-box macro-F1 across folds: 0.675 ± 0.032 `[det_matched.fold_level.mean]` `[det_matched.fold_level.sd]`.
  - Per-fold means: 0.725, 0.652, 0.662, 0.647 and 0.689 `[det_matched.fold0.macro_f1.mean]` `[det_matched.fold1.macro_f1.mean]` `[det_matched.fold2.macro_f1.mean]` `[det_matched.fold3.macro_f1.mean]` `[det_matched.fold4.macro_f1.mean]`.
* **Detector-unseen radiographs** (331 findings `[unseen.findings]`): detector boxes 0.685, GT boxes 0.710 `[unseen.det.mean]` `[unseen.gt.mean]`.
* **Official validation release** (GT boxes): 0.706 ± 0.054 `[secondary.gt.mean]` `[secondary.gt.sd]`. The small set makes the
  seed spread wide.

### 4.5 Calibration and error analysis
* **Calibration:** ECE 0.107 on detector boxes and 0.109 on GT boxes `[det_matched.ece.mean]` `[gt.ece.mean]`. Confidence scores
  should not be read as probabilities without recalibration.
* **Deep Caries confused with Caries:** 1,083 of 2,415 GT-box Deep Caries predictions (45 %), summed over seeds `[cv5:summary/gt/confusion_sum_over_seeds/1]`.
* **Periapical Lesion confused with Caries:** 229 of 645 (36 %) `[cv5:summary/gt/confusion_sum_over_seeds/3]`.
* **Box size:** the Caries / Deep Caries confusion varies with box size (`reports/cv5_results.md` §6).
* **Consistently confused findings:** 110 findings were confused by all five seeds on GT boxes `[cv5:caries_confusion/confused_by_all_seeds_gt]`.
  They are listed in `reports/cv5_caries_clinician_review_list.csv` for clinician review. **This is not a claim of label error.**

### 4.6 Negative results (earlier experiments; validation split, not CV5)
The three experiments below were evaluated on the project's seed-42 validation split, against BASE, under the rule pre-registered for
each. Their population and rules differ from CV5, so they are **not comparable** with §4.1–4.5. Periapical Lesion has only 9
validation findings, so the minority deltas are fragile.

Every attempt failed. The rule for the imbalance strategies required a mean macro-F1 gain ≥ 0.027, at least 4 of 5 seed pairs and at
least 20 of 25 cross pairs better, plus class safeguards `[neg.imbalance.rule]`.

**Table 3. Imbalance strategies** (detector boxes; gain = mean macro-F1 gain over BASE).

| Strategy | Gain | Cross pairs better (of 25) | Passed | Source |
|---|---|---|---|---|
| Unweighted reference | 0.0042 | 14 | no | `[neg.imbalance.REF_unweighted.gain]` `[neg.imbalance.REF_unweighted.cross_pairs]` `[neg.imbalance.REF_unweighted.pass]` |
| Square-root class weights | −0.0086 | 11 | no | `[neg.imbalance.A1_sqrt_weights.gain]` `[neg.imbalance.A1_sqrt_weights.cross_pairs]` `[neg.imbalance.A1_sqrt_weights.pass]` |
| Effective-number class weights | 0.0008 | 12 | no | `[neg.imbalance.A2_effnum_weights.gain]` `[neg.imbalance.A2_effnum_weights.cross_pairs]` `[neg.imbalance.A2_effnum_weights.pass]` |
| Class-balanced sampler | −0.0037 | 12 | no | `[neg.imbalance.B_sampler.gain]` `[neg.imbalance.B_sampler.cross_pairs]` `[neg.imbalance.B_sampler.pass]` |
| Focal loss | −0.0138 | 8 | no | `[neg.imbalance.C_focal.gain]` `[neg.imbalance.C_focal.cross_pairs]` `[neg.imbalance.C_focal.pass]` |
| Plus official-validation training data | −0.0043 | 11 | no | `[neg.imbalance.D_official_val.gain]` `[neg.imbalance.D_official_val.cross_pairs]` `[neg.imbalance.D_official_val.pass]` |

**External training data.** Adding an external dataset (the X2 configuration) gave a gain of −0.0005 `[neg.external.gain]`, with 11
of 25 cross pairs better `[neg.external.cross_pairs]`. Minority recall fell:
* Deep Caries −0.049 `[neg.external.Deep Caries.recall_delta]`;
* Periapical Lesion −0.057 `[neg.external.Periapical Lesion.recall_delta]`.

It failed its rule `[neg.external.pass]`.

**Five-seed ensemble.** Averaging the five BASE seeds gave a gain of 0.0072 `[neg.ensemble.gain]`. It beat 2 of 5 members
`[neg.ensemble.members_beaten]`, and the bootstrap 95 % CI of the gain was −0.0317 to 0.0481 `[neg.ensemble.boot.ci95]`, so it
included zero. It failed its rule `[neg.ensemble.pass]`.

### 4.7 Resources
* **Training compute:** 1.04 GPU-hours, summed over the 25 runs on a Tesla T4 `[cost.train_hours]` `[env.gpu]`. This counts epoch
  time only; data preparation and the detector are excluded.
* **Memory and storage:** peak GPU memory 1,736 MB `[cost.peak_gpu_mb]`; checkpoint size 94,354,861 bytes `[cost.checkpoint_bytes]`.
* **Inference latency:** **not measured** in the CV5 artifacts `[cost.latency]`. No estimate is given.

### 4.8 Candidate comparisons
**None.** Three candidates are implemented and pre-flight tested only: 384-pixel crops, 0.25 context padding, and ConvNeXt-Tiny. They
are not registered, trained or evaluated, and no result exists for them.

## 5. Discussion and limitations
* **What the results show.** The baseline separates Impacted and Caries well. It is weak on Deep Caries and Periapical Lesion, which
  are mostly confused with Caries. This fits the visual continuum between caries depths, and the small number of periapical
  examples.
* **What the negative results show.** Re-weighting, re-sampling, focal loss, adding external data and seed ensembling did not give a
  gain that met the pre-registered rules. The constraint appears to be data and labels rather than the training recipe. This is a
  hypothesis, not a tested result.
* **Single public dataset, radiograph level.** There are no patient identifiers and no external validation set.
* **Detector overlap.** The detector was trained on part of the pool. The detector-unseen subset shows no sign of inflation, but it is
  small.
* **Not test-set results.** The values are not comparable with earlier single-split numbers of this project, which used other
  populations and protocols.
* **Selection on the same data.** Any future winner is evaluated on the same 541 radiographs, so its gain would be optimistically
  biased by selection. The protocol states this, and it is not removed by the Bonferroni correction.
* **Labels.** All labels are the original DENTEX labels. No clinician has re-read them for this work.
* **Intended use.** A research prototype: not validated for clinical use, not a medical device, and making no diagnostic claim.

## 6. Conclusion
Under grouped 5-fold cross-validation, a ResNet-50 finding classifier reaches moderate macro-F1 on DENTEX. Its recall is lowest for
Deep Caries and Periapical Lesion. Several standard remedies failed their pre-registered rules. We report these estimates, their
uncertainty and a frozen acceptance protocol as the reference for future work, and we make no claim of improvement.

## 7. Declarations (to be completed by the authors; nothing is assumed)
* **Ethics approval / consent:** [authors, per institutional rules for public, de-identified data].
* **Funding:** [authors].
* **Conflicts of interest:** [authors].
* **Author contributions:** [authors].
* **Data availability:** DENTEX through its official source. Fold file, manifests and archived artifacts are listed with SHA-256 in
  Appendix A.
* **Code availability:** [authors decide repository and release]. Code hashes are in Appendix A.
* **Use of AI assistance:** [authors state it according to the venue's policy].

## References
Keys of `documents/dentist-research-references.bib` cited here: resnet, imagenet, ren, fpn, hamamciArxiv, hamamciMiccai, kapoor,
naeini, guo, putra, peker, tang, ayhan, szabo, raeisi, bittar. The bibliography has not been verified against DOIs in this session; see
`reports/manuscript/citation_audit_v1.md`.

---

## Appendix A. Reproducibility

**A.1 Archived artifacts** (all verified in this session).

| Artifact | SHA-256 | Check |
|---|---|---|
| CV5 archive `kaggle/dentamind_5fold_cv_artifacts.zip` | `4ac56843…` | 88 / 88 entries match `SHA256SUMS.txt` |
| Imbalance run `checkpoints/kaggle_candidates/dc9c505b/` | per file | 61 / 61 entries match `SHA256SUMS.txt` |
| External run `kaggle/artifacts_external_run1/` | per file | 39 / 39 entries match `SHA256SUMS.txt` |
| Ensemble result `reports/ensemble_evaluation_kaggle.json` | `f208246a…` | not part of a checksummed archive; hash only |
| Fold file `data/splits/cv5_folds_v1.csv` | `9b767a48…` | — |
| Acceptance protocol `reports/cv5_acceptance_protocol.md` | `0771b5f8…` | — |
| Test-set ledger `Data/reports/test_set_ledger.json` | `f117c1a3…` | 5 entries, hash chain intact |

**A.2 Code.**
* CV5 library `kaggle/cv5_lib.py` `72084f9b…`.
* Training module `kaggle/dentamind_kaggle.py` `879faa93…`.
* Notebook generator `kaggle/make_cv5_notebook.py` `4a5efda8…`.
* BASE notebook `kaggle/dentamind_5fold_cv.ipynb` `dd65c7c7…`.

**A.3 Traceability builders.**
* `scripts/build_results_traceability.py` → `reports/results_traceability.json` (133 rows).
* `scripts/build_negative_findings_traceability.py` → `reports/negative_findings_traceability.json` (49 rows).

Both refuse to report a file that fails its checksum, and both refuse to overwrite earlier output.

**A.4 Environment.** Kaggle, Tesla T4 `[env.gpu]`, torch `[env.torch]`. The total notebook wall-clock time appears only in the Kaggle
log, not as an artifact field `[cost.notebook_runtime]`.

**A.5 To reproduce:**
1. Obtain DENTEX from its official source.
2. Build the bundle with the repository's Kaggle scripts.
3. Run the BASE notebook on a T4 GPU.
4. Compare the new `SHA256SUMS.txt` and `cv5_results.json` with the archive.

GPU non-determinism can change the trained weights. In that case, metrics are expected to agree within seed variation, not bit for bit.

## Appendix B. Readiness checklist (summary; the full list is `reports/manuscript/publication_readiness_checklist_v1.md`)

| Item | Status |
|---|---|
| Every result number traced and audited | done; see the audit report |
| Candidate results | absent by design |
| Inference latency | not measured; not reported |
| Bibliography checked against DOIs | **open (authors)** |
| Declarations | **open (authors)** |
| Venue choice and formatting | **open (authors / supervisor)** |
| DENTEX licence wording | **open (authors)** |
| Ledger disclosures of prior test-split use | **open (accountable test-set authorizer)** |
