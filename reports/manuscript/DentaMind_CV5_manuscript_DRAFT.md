# DRAFT MANUSCRIPT: NOT FOR SUBMISSION

**Status (2026-10-25):** draft built only from verified artifacts.
* Every number is traceable to `reports/results_traceability.json` (row IDs in brackets, e.g. `[det_matched.macro_f1.mean]`).
* Sections that depend on experiments not yet run are marked **[BLOCKED]** and contain no numbers.
* Citations use keys of `documents/dentist-research-references.bib`. That bibliography was **not re-verified** in this session; every
  entry must be checked against its DOI before submission.
* The existing paper documents in `documents/` are unchanged.

---

**Working title:** Cross-validated baseline and a pre-registered acceptance protocol for finding classification on panoramic dental
radiographs (DENTEX)

**Authors:** Nilesh Sonawane, Saurabh Mali, Sadhyoj Hanwate, Sachet Lothe. **Guide:** Dr. Pradnya Narkhede, Department of Computer
Engineering, PCCOE, Pune.
*[Author order, affiliations, corresponding author and contribution statements: to be provided by the authors.]*

## Abstract (draft; candidate results [BLOCKED])

**Background.** Deep-learning classification of dental findings on panoramic radiographs is commonly reported on single splits, which
yield unstable estimates for rare classes.

**Methods.** We evaluated a ResNet-50 finding classifier [CITE: resnet] on the DENTEX disease subset [CITE: hamamciArxiv]. We used
grouped 5-fold cross-validation at radiograph level:
* 541 radiographs, 2,851 findings `[pop.radiographs]` `[pop.findings]`;
* 5 seeds;
* epoch selection on an inner validation split;
* a radiograph-level bootstrap.

Findings were classified both from ground-truth (GT) boxes and from boxes of a Faster R-CNN tooth detector [CITE: ren].

**Results.** Detector-box macro-F1 was 0.677 (95 % CI 0.652–0.701) `[det_matched.macro_f1.mean]` `[det_matched.boot.ci95]`. GT-box
macro-F1 was 0.698 (0.675–0.718) `[gt.macro_f1.mean]` `[gt.boot.ci95]`. Deep Caries and Periapical Lesion had the lowest recall
(detector boxes 0.440 and 0.432) `[det_matched.Deep Caries.recall.mean]` `[det_matched.Periapical Lesion.recall.mean]`.

We also pre-registered an acceptance protocol for candidate improvements:
* paired bootstrap with lifetime Bonferroni correction;
* class safeguards and a hard-harm rule.

[BLOCKED: no candidate has been evaluated under it.]

**Conclusions.** Cross-validated performance of the baseline is moderate. It is weakest for the clinically important deep-caries and
periapical classes, so these estimates are the reference for any future claim of improvement. The results are radiograph-level and
single-centre, and have no clinical validation.

## 1. Introduction
* **Context:** automated tooth detection and numbering [CITE: putra; peker; tang; ayhan], periapical lesion detection [CITE: szabo],
  multi-label diagnosis [CITE: raeisi], caries detection [CITE: bittar], and the DENTEX benchmark [CITE: hamamciArxiv; hamamciMiccai].
* **Problem:** single-split evaluation and data leakage threaten reproducibility in ML-based science [CITE: kapoor]. Rare classes
  (Periapical Lesion: 129 training findings) make split-dependent estimates unstable. *[Source of 129: `reports/expanded_class_distribution.csv`.]*
* **Contributions (only those supported by evidence):**
  1. a grouped 5-fold CV baseline with seed and radiograph-bootstrap uncertainty, archived with full hashes;
  2. a pre-registered, hash-frozen acceptance protocol for future candidates, including leakage controls for clinician-verified data
     imports;
  3. an error analysis of the Caries / Deep Caries / Periapical Lesion confusions.

  *[Contribution 4, a validated improvement: BLOCKED.]*

## 2. Data
* **Source:** DENTEX [CITE: hamamciArxiv], disease subset; English labels; four classes: Caries, Deep Caries, Impacted, Periapical
  Lesion. *[Licence and terms of use: to be quoted from the DENTEX source by the authors.]*
* **Population:**
  - 541 primary radiographs, 2,851 findings `[pop.radiographs]` `[pop.findings]`;
  - 2,745 findings matched to a detector box `[pop.det_matched]`;
  - secondary: 159 DENTEX official-validation findings `[secondary.findings]`.
* **Grouping and leakage:**
  - radiograph groups merge exact (SHA-256) and confirmed near-duplicate images (dHash Hamming ≤ 4 with thumbnail correlation ≥ 0.97);
  - folds are assigned by group (`data/splits/cv5_folds_v1.csv`, sha256 `9b767a48…`).
* **Patient identity:** DENTEX has no patient identifiers. All independence is at radiograph level, and no patient-level conclusion is
  drawn.
* **Held-out data:** the calibration and test splits were not read by any CV run.
* **Prior use of the test split:** the internal test split has 5 historical ledger entries and two BASE test evaluations with
  disclosures pending authorization. Any future test result is not an untouched estimate.
* **Clinician-verified imports:** none exist. The import pipeline is implemented but unused. [BLOCKED: P2 data targets unmet.]

## 3. Methods
* **Classifier:** ResNet-50 [CITE: resnet], ImageNet-pretrained [CITE: imagenet], 4-way head, 23,516,228 parameters
  `[cost.parameters]`. 224 px crops with 0.10 context padding; inverse-frequency class weights capped at 5; AdamW, lr 3e-4, wd 1e-4;
  15 epochs, batch 32; horizontal flip and contrast augmentation.
* **Detector:** the production Faster R-CNN with FPN [CITE: ren; fpn]. Detector boxes are matched to findings at IoU ≥ 0.5, one-to-one.
* **Cross-validation:**
  - 5 folds × seeds 42–46 = 25 runs;
  - each fold trains on the remaining folds minus a group-disjoint inner validation split used only for epoch selection;
  - every held-out finding receives exactly one prediction per seed.
* **Statistics:**
  - macro-F1 and per-class precision / recall / F1;
  - seed mean ± SD;
  - radiograph-level percentile bootstrap (2,000 resamples, seed 0) of the seed-mean;
  - calibration: ECE with 10 bins [CITE: naeini; guo];
  - end-to-end recall counts unmatched findings as errors.
* **Pre-registered acceptance protocol** (`reports/cv5_acceptance_protocol.md`, revision 3):
  - Δ macro-F1 ≥ 0.027;
  - a paired bootstrap lower bound > 0 at level 1 − 0.05/15 (B = 20,000);
  - wins in ≥ 4 / 5 seeds and ≥ 4 / 5 folds;
  - class safeguards S1–S7 and a hard-harm rule.

  The thresholds were frozen before any candidate existed.

## 4. Results (CV5-BASE run 1)

**Table 1. Pooled out-of-fold macro-F1** (mean ± SD over seeds; bootstrap 95 % CI).

| Setting | Macro-F1 | 95 % CI | Source |
|---|---|---|---|
| Detector boxes (matched) | 0.677 ± 0.008 | 0.652–0.701 | `[det_matched.macro_f1.mean]` `[det_matched.macro_f1.sd]` `[det_matched.boot.ci95]` |
| GT boxes | 0.698 ± 0.007 | 0.675–0.718 | `[gt.macro_f1.mean]` `[gt.macro_f1.sd]` `[gt.boot.ci95]` |

**Table 2. Per-class performance:** values in `reports/cv5_results.md`, traceable via the `{setting}.{class}.{metric}.mean / .sd` rows.
Lowest recall:
* Deep Caries: detector 0.440, GT 0.496 `[det_matched.Deep Caries.recall.mean]` `[gt.Deep Caries.recall.mean]`;
* Periapical Lesion: detector 0.432, GT 0.451 `[det_matched.Periapical Lesion.recall.mean]` `[gt.Periapical Lesion.recall.mean]`.

**Fold-level variation** (descriptive; the folds are not independent replicates): detector-box macro-F1 0.675 ± 0.032 across folds
`[det_matched.fold_level.mean]` `[det_matched.fold_level.sd]`. Per-fold means range 0.647–0.725 `[det_matched.fold0…4.macro_f1.mean]`.

**Subsets:**
* Detector-unseen radiographs (331 findings): 0.685 detector / 0.710 GT `[unseen.det.mean]` `[unseen.gt.mean]`.
* Official validation: GT 0.706 `[secondary.gt.mean]`, with a wide spread across seeds `[secondary.gt.sd]`.

**Calibration:** ECE about 0.11 `[det_matched.ece.mean]` `[gt.ece.mean]`.

**Error analysis:** Deep Caries findings are predicted as Caries in 45 % of GT-box predictions, and Periapical Lesion as Caries in 36 %.
Deep-caries confusion rises with box size (`reports/cv5_results.md` §6). 110 consistently confused findings are listed for clinician
review; this is not a claim of label error.

**Resources:**
* 1.04 training GPU-hours over the 25 runs on a Tesla T4 `[cost.train_hours]` `[env.gpu]`;
* peak GPU memory 1,736 MB `[cost.peak_gpu_mb]`;
* checkpoint 94.35 MB `[cost.checkpoint_bytes]`;
* inference latency: not measured in these artifacts `[cost.latency]`.

**Candidate comparisons:** [BLOCKED. Candidates C1 (384 px crops), C2 (0.25 context padding) and C3 (ConvNeXt-Tiny) are implemented
and pre-flight tested only. They are not registered, not trained and not evaluated. No result exists.]

## 5. Discussion and limitations
* **Single-centre, radiograph-level data** without patient identifiers; no external validation. An earlier external-data experiment
  failed its own pre-registered criteria (`reports/external_data_results.md`).
* **Detector overlap:** the detector was trained on part of the pool. The detector-unseen subset does not indicate inflation, but it
  is small.
* **Not a test-set result,** and not comparable with earlier single-split numbers.
* **Negative results are reported:** imbalance strategies, external data and a 5-seed ensemble all failed their acceptance rules.
* **Clinical safety and intended use:** a research prototype; not validated for clinical use, not a medical device, no diagnostic
  claims.

## 6. Declarations [to be completed by the authors; nothing is assumed]
* **Ethics approval / consent:** [authors: state the applicable statement for public de-identified DENTEX data, per institutional
  rules].
* **Funding:** [authors].
* **Conflicts of interest:** [authors].
* **Author contributions:** [authors].
* **Data availability:** DENTEX via its official source. The fold file, manifests and archived CV artifacts are listed with SHA-256 in
  `reports/results_traceability.json`.
* **Code availability:** [authors decide the repository / release]. Code hashes are in `reports/cv5_amendment_01b_implementation.md`.

## 7. Reproducibility checklist (status)

| Item | Status |
|---|---|
| Archived CV artifacts with SHA256SUMS (88 / 88 verified) | done |
| Fold file and protocol hashes | done |
| Results traced to artifacts | done (`reports/results_traceability.*`) |
| Candidate experiments | BLOCKED |
| Test-set evaluation | not performed for any candidate; prior uses disclosed (pending authorization) |
| Venue formatting | no venue selected |
