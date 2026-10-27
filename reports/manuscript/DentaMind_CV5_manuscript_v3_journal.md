# Classifying dental findings on panoramic radiographs: a cross-validated baseline, negative results and a pre-registered acceptance protocol on the DENTEX dataset

**Source file for the journal manuscript, version 3.** Bracketed tags in backticks give the source of each number. `scripts/build_manuscript_docx.js` strips them when building `DentaMind_CV5_manuscript_v3_journal.docx`. The audit is in `reports/manuscript/manuscript_v3_number_audit.md`. Draft, not submitted. Changes from v2: post-hoc error attribution (Section 2.9, Section 3.4, Table 3, Fig. 6); measured inference latency (Section 2.10, Section 3.8, Table 5); and a corrected statement on candidate registration (Section 4.4). Earlier drafts are unchanged.

## Title page

Nilesh Sonawane, Saurabh Mali, Sadhyoj Hanwate, Sachet Lothe; guide: Dr. Pradnya Narkhede.

Department of Computer Engineering, Pimpri Chinchwad College of Engineering (PCCOE), Pune, India.

Corresponding author: [to be named by the authors, with e-mail address].

## Abstract

**Objectives:** Classifiers of dental findings on panoramic radiographs are usually reported on a single split, which gives unstable estimates for rare classes. We aimed to establish a cross-validated, fully traceable baseline on a public benchmark and to report how far common remedies for class imbalance improve it.

**Methods:** We used the disease subset of the DENTEX dataset, which has four finding classes: caries, deep caries, impacted tooth and periapical lesion. The pool held 2,851 findings on 541 radiographs `[pop.findings]` `[pop.radiographs]`. A ResNet-50 classifier was evaluated with radiograph-grouped 5-fold cross-validation and five training seeds. We report seed-averaged out-of-fold metrics with radiograph-level bootstrap intervals, in three settings: ground-truth boxes, detector boxes, and the end-to-end pipeline. Before any new candidate model was trained, we froze an acceptance protocol for future candidates.

**Results:** Macro-F1 was 0.677 (95 % CI 0.652–0.701) on detector boxes `[det_matched.macro_f1.mean]` `[det_matched.boot.ci95]` and 0.698 (0.675–0.718) on ground-truth boxes `[gt.macro_f1.mean]` `[gt.boot.ci95]`. Recall on detector boxes was lowest for deep caries, 0.440 (0.397–0.485) `[boot:results/det_matched/per_class/Deep Caries/recall]`, and for periapical lesions, 0.432 (0.341–0.528) `[boot:results/det_matched/per_class/Periapical Lesion/recall]`. Deep caries was predicted as caries in 45 % of cases `[cv5:summary/gt/confusion_sum_over_seeds/1]`. A post-hoc error attribution showed that 22 of 129 periapical lesions received no detector-matched crop because their tooth box was assigned to another finding on the same tooth `[attr:per_class/Periapical Lesion]`; misclassification of matched crops nevertheless remained the largest error source for every class. On a laptop RTX 3050 GPU, the full detection-and-classification pipeline took a median of 251 ms per radiograph `[lat1:end_to_end_gpu/ms_per_radiograph/total]`. None of the earlier remedies met its pre-registered acceptance rule: class re-weighting, balanced sampling, focal loss, additional official data, external data and seed ensembling.

**Conclusions:** On DENTEX, the baseline is moderate overall and weak on the two most clinically consequential classes. Common imbalance remedies did not change this measurably. These estimates, the archived artifacts and the frozen protocol provide a reference against which future improvements can be tested without post-hoc selection.

**Keywords:** panoramic radiography; dental caries; periapical lesion; deep learning; cross-validation; reproducibility.

## 1. Introduction

Panoramic radiographs are a routine overview examination in dentistry. Automated analysis of them has advanced quickly with deep learning, and published work covers several tasks:

* tooth detection and numbering [CITE: putra; peker; tang; ayhan];
* periapical lesion detection [CITE: szabo];
* caries detection [CITE: bittar];
* multi-label diagnosis of several conditions [CITE: raeisi].

The DENTEX challenge made a hierarchically annotated set of panoramic radiographs publicly available, with quadrant, tooth and diagnosis labels [CITE: hamamciArxiv; hamamciMiccai]. This allows methods to be compared on common data.

Most reports, however, give performance on a single train/test partition. Two problems follow for the clinically important minority classes:

* **Instability:** a small test set holds few minority examples, so one split can make a method look better or worse by chance.
* **Leakage and selection:** repeated evaluation and model selection on the same held-out data inflate reported performance [CITE: kapoor].

An improvement claimed on such evidence can be hard to reproduce.

This study takes the opposite approach. We first establish a cross-validated baseline whose uncertainty is quantified and whose every number is traceable to archived, checksum-verified artifacts. Our contributions are:

1. a radiograph-grouped 5-fold, five-seed cross-validated baseline for four-class finding classification on DENTEX, with radiograph-level bootstrap intervals, reported separately for ground-truth boxes, detector boxes and the end-to-end pipeline;
2. an error analysis of the confusions among caries, deep caries and periapical lesion;
3. a report of negative results: six imbalance strategies, external training data and a seed ensemble all failed their pre-registered acceptance rules;
4. an acceptance protocol for future candidate models, frozen before any candidate was trained, with explicit safeguards against post-hoc selection;
5. an attribution of end-to-end errors to detection, box matching and classification, and a measured inference latency of the pipeline.

We make no claim that any model improves on the baseline.

## 2. Materials and methods

### 2.1 Data

We used the quadrant-enumeration-disease subset of DENTEX [CITE: hamamciArxiv], whose diagnosis labels were provided by the dataset's expert annotators. The four classes are caries, deep caries, impacted tooth and periapical lesion.

The primary pool held 2,851 findings on 541 radiographs `[pop.findings]` `[pop.radiographs]`. Of these, 2,745 findings could be matched to a box produced by the tooth detector `[pop.det_matched]`. The 159 findings of the DENTEX official validation release were evaluated as a secondary set `[secondary.findings]`.

The classes are strongly imbalanced. Over five seeds there were 8,775 caries predictions on ground-truth boxes, one per finding and seed, compared with 645 for periapical lesions `[cv5:summary/gt/confusion_sum_over_seeds/0]` `[cv5:summary/gt/confusion_sum_over_seeds/3]`.

The project's separate calibration and test splits were not read by any cross-validation run. DENTEX provides no patient identifiers, so all analyses are at radiograph level.

Ethics: [statement to be provided by the authors according to institutional rules for secondary use of public, de-identified data]. Licence: [the DENTEX terms of use, to be quoted by the authors].

### 2.2 Leakage control

Before folds were assigned, radiographs were grouped. A group merged exact duplicates, identified by SHA-256 hash, with confirmed near-duplicates (perceptual-hash Hamming distance of at most 4 and thumbnail correlation of at least 0.97). Folds were then assigned by group. The fold assignment is stored as a versioned file whose hash is given in Supplementary Material S1.

### 2.3 Classifier and detector

**Classifier.** Each finding was classified from a crop around its bounding box (224 pixels, with 0.10 context padding). The network was a ResNet-50 [CITE: resnet] pretrained on ImageNet [CITE: imagenet], with a four-class output layer and 23,516,228 trainable parameters `[cost.parameters]`. Training details:

* loss: cross-entropy with inverse-frequency class weights, capped at 5;
* optimiser: AdamW, learning rate 3e-4, weight decay 1e-4;
* schedule: 15 epochs, batch size 32;
* augmentation: horizontal flipping and contrast changes.

**Detector.** Detector boxes came from the project's Faster R-CNN with a feature pyramid network [CITE: ren; fpn]. Each detector box was matched one-to-one to a finding at an intersection-over-union of at least 0.5.

### 2.4 Cross-validation design

The design had 5 folds and seeds 42 to 46, giving 25 training runs (Fig. 1).

* For each held-out fold, the classifier was trained on the remaining folds.
* A group-disjoint inner validation split was removed from those training folds and used only to select the epoch.
* Every finding in the pool therefore received exactly one out-of-fold prediction per seed.

### 2.5 Evaluation settings

We report three settings, which answer different questions and must not be mixed:

* **Ground-truth (GT) boxes:** every finding is classified from its annotated box. This measures class separation given perfect localisation.
* **Detector boxes (matched):** only findings with a matched detector box are classified, using that box. This measures classification on what the detector finds.
* **End-to-end:** all findings are counted, and a finding without a matched detector box is an error. This is closest to what a user of the full pipeline would see.

### 2.6 Statistical analysis

**Metrics.** We report macro-F1 and per-class precision, recall and F1, computed on pooled out-of-fold predictions for each seed and averaged over seeds.

**Uncertainty.** We used a radiograph-level percentile bootstrap of the seed-mean (2,000 resamples, random seed 0), which resamples whole radiograph groups. Per-class intervals were computed afterwards with the same resampling procedure. As a check, this recomputation reproduced the archived macro-F1 intervals exactly.

**Calibration.** Calibration was summarised by the expected calibration error over 10 bins [CITE: naeini; guo].

**Fold-level spread.** We report the spread across folds as a description only. The folds are not independent replicates, because their training sets overlap.

### 2.7 Earlier improvement experiments

Before the cross-validation study, we evaluated several remedies on the project's fixed validation split against the same baseline recipe:

* six imbalance strategies: an unweighted reference, square-root class weights, effective-number class weights, a class-balanced sampler, focal loss, and additional training data from the DENTEX official validation release;
* the addition of an external dataset;
* an ensemble of the five baseline seeds.

Each experiment had an acceptance rule registered before it was run. For the imbalance strategies, the rule required a mean macro-F1 gain of at least 0.027, improvement in at least 4 of 5 seed pairs and in at least 20 of 25 cross pairs, and class-level safeguards `[neg.imbalance.rule]`. These experiments used a different population and different rules from the cross-validation study, so their numbers are not comparable with Section 3.1–3.6.

### 2.8 Pre-registered acceptance protocol for future candidates

A written protocol fixes how any future candidate model will be judged against the baseline. It was frozen on 25 October 2026, before any candidate was trained, and its hash is recorded in Supplementary Material S1. A candidate is accepted only if all of the following hold.

**Primary checks:**
* **Gain:** the seed-mean macro-F1 gain is at least 0.027.
* **Confidence:** the lower bound of a paired radiograph-level bootstrap interval of the gain is above zero. The interval uses B = 20,000 resamples at the two-sided level 1 − 0.05/15, a Bonferroni correction over a fixed lifetime budget of 15 candidate configurations.
* **Consistency:** the candidate wins in at least 4 of 5 seeds and in at least 4 of 5 folds.

**Class-level safeguards with fixed margins** cover recall and precision of deep caries and periapical lesion, per-class F1, ground-truth-box macro-F1 and end-to-end minority recall.

**Hard-harm rule:** the candidate fails if the unadjusted 95 % interval of the change in any protected minority-class metric lies wholly below zero.

**Safeguards against post-hoc analysis:**
* candidates must be registered with frozen configurations before the reference is re-run, and each counts toward the budget once its training starts;
* evaluation labels are frozen;
* the test split can be used at most once, for a single confirmed winner, through a hash-chained ledger that requires a named authoriser, and the result must then be reported as coming from a previously used split.

**Disclosure:** the safeguard margins were set after the results of Section 2.7 were known. Those verdicts were not revisited.

### 2.9 Error attribution (post-hoc, descriptive)

After the cross-validation results were final, we attributed each end-to-end error to a stage of the pipeline, using only archived outputs. No model was retrained and no new prediction was made. Each finding was assigned to one of four groups:

* **No overlapping box:** no detector box (score of at least 0.3) overlaps the finding.
* **Low-overlap box:** a box overlaps the finding, but with an intersection-over-union below 0.5.
* **Matching conflict:** a box with an intersection-over-union of at least 0.5 exists but was assigned, under one-to-one matching, to another finding.
* **Matched:** the finding received a detector box; each seed's prediction on it was then counted as correct or misclassified.

The analysis was accepted only if it reproduced the archive exactly: the matched flags of all findings, the per-seed end-to-end recall of every class, and the count of consistently confused findings.

### 2.10 Inference latency

Latency was measured after the study on one machine, following the measurement definition of the acceptance protocol. It decides nothing.

* **Hardware and software:** a laptop with an NVIDIA GeForce RTX 3050 Laptop GPU (4 GB), PyTorch 2.6 and CUDA 12.4. Power and thermal state were not controlled.
* **Model:** the baseline classifier architecture with a checksum-verified baseline-recipe checkpoint. The cross-validation checkpoints themselves are not stored locally.
* **Classifier alone:** batch sizes 1 and 64, in 32-bit floating point, with GPU synchronisation, warm-up and five timed repetitions; we report the median.
* **End-to-end:** per radiograph, covering image decoding, tooth detection, cropping and classification of all detected teeth. We used 20 fixed training-pool radiographs, two warm-up images and five repetitions; no label was used.
* **Repeatability:** the whole benchmark was run twice.

## 3. Results

### 3.1 Overall performance

Table 1 gives the pooled out-of-fold results. Macro-F1 was 0.677 on detector boxes and 0.698 on ground-truth boxes, and the seed-to-seed standard deviation was below 0.01 in both settings `[det_matched.macro_f1.mean]` `[gt.macro_f1.mean]` `[det_matched.macro_f1.sd]` `[gt.macro_f1.sd]`.

**Table 1.** Pooled out-of-fold performance (mean ± SD over five seeds; radiograph-bootstrap 95 % CI).

| Setting | Findings | Macro-F1 | 95 % CI | Accuracy | Source |
|---|---|---|---|---|---|
| Detector boxes (matched) | 2,745 | 0.677 ± 0.008 | 0.652–0.701 | 0.807 | `[pop.det_matched]` `[det_matched.macro_f1.mean]` `[det_matched.macro_f1.sd]` `[det_matched.boot.ci95]` `[det_matched.accuracy.mean]` |
| Ground-truth boxes | 2,851 | 0.698 ± 0.007 | 0.675–0.718 | 0.804 | `[pop.findings]` `[gt.macro_f1.mean]` `[gt.macro_f1.sd]` `[gt.boot.ci95]` `[gt.accuracy.mean]` |

### 3.2 Per-class performance

Table 2 shows that performance differs widely between classes:

* **Impacted teeth and caries:** both were classified reliably.
* **Deep caries:** F1 was 0.487 on detector boxes `[boot:results/det_matched/per_class/Deep Caries/f1]`.
* **Periapical lesion:** F1 was 0.416 on detector boxes `[boot:results/det_matched/per_class/Periapical Lesion/f1]`. Its intervals were the widest, which reflects its small number of examples.

**Table 2.** Per-class precision, recall and F1 (seed mean; radiograph-bootstrap 95 % CI).

| Class | Setting | Precision | Recall | F1 | Source |
|---|---|---|---|---|---|
| Caries | Detector | 0.848 (0.830–0.866) | 0.883 (0.869–0.895) | 0.865 (0.853–0.877) | `[boot:results/det_matched/per_class/Caries/precision]` `[boot:results/det_matched/per_class/Caries/recall]` `[boot:results/det_matched/per_class/Caries/f1]` |
| Caries | GT | 0.847 (0.828–0.865) | 0.874 (0.860–0.888) | 0.860 (0.848–0.872) | `[boot:results/gt/per_class/Caries/precision]` `[boot:results/gt/per_class/Caries/recall]` `[boot:results/gt/per_class/Caries/f1]` |
| Deep caries | Detector | 0.546 (0.495–0.591) | 0.440 (0.397–0.485) | 0.487 (0.446–0.526) | `[boot:results/det_matched/per_class/Deep Caries/precision]` `[boot:results/det_matched/per_class/Deep Caries/recall]` `[boot:results/det_matched/per_class/Deep Caries/f1]` |
| Deep caries | GT | 0.576 (0.529–0.619) | 0.496 (0.451–0.539) | 0.533 (0.494–0.570) | `[boot:results/gt/per_class/Deep Caries/precision]` `[boot:results/gt/per_class/Deep Caries/recall]` `[boot:results/gt/per_class/Deep Caries/f1]` |
| Impacted | Detector | 0.935 (0.913–0.954) | 0.945 (0.928–0.961) | 0.940 (0.925–0.953) | `[boot:results/det_matched/per_class/Impacted/precision]` `[boot:results/det_matched/per_class/Impacted/recall]` `[boot:results/det_matched/per_class/Impacted/f1]` |
| Impacted | GT | 0.913 (0.888–0.935) | 0.949 (0.929–0.966) | 0.931 (0.913–0.945) | `[boot:results/gt/per_class/Impacted/precision]` `[boot:results/gt/per_class/Impacted/recall]` `[boot:results/gt/per_class/Impacted/f1]` |
| Periapical lesion | Detector | 0.401 (0.310–0.490) | 0.432 (0.341–0.528) | 0.416 (0.333–0.494) | `[boot:results/det_matched/per_class/Periapical Lesion/precision]` `[boot:results/det_matched/per_class/Periapical Lesion/recall]` `[boot:results/det_matched/per_class/Periapical Lesion/f1]` |
| Periapical lesion | GT | 0.485 (0.403–0.564) | 0.451 (0.370–0.531) | 0.467 (0.393–0.534) | `[boot:results/gt/per_class/Periapical Lesion/precision]` `[boot:results/gt/per_class/Periapical Lesion/recall]` `[boot:results/gt/per_class/Periapical Lesion/f1]` |

### 3.3 Recall across evaluation settings

Minority-class recall fell at each step from ground-truth boxes to the end-to-end pipeline (Fig. 3):

* **Deep caries:** 0.496 on ground-truth boxes and 0.440 on detector boxes `[gt.Deep Caries.recall.mean]` `[det_matched.Deep Caries.recall.mean]`; end-to-end recall ranged from 0.375 to 0.410 across seeds `[e2e.seed42.Deep Caries.recall]` `[e2e.seed43.Deep Caries.recall]` `[e2e.seed44.Deep Caries.recall]` `[e2e.seed45.Deep Caries.recall]` `[e2e.seed46.Deep Caries.recall]`.
* **Periapical lesion:** 0.451 and 0.432 `[gt.Periapical Lesion.recall.mean]` `[det_matched.Periapical Lesion.recall.mean]`; end-to-end 0.302 to 0.372 `[e2e.seed42.Periapical Lesion.recall]` `[e2e.seed43.Periapical Lesion.recall]` `[e2e.seed44.Periapical Lesion.recall]` `[e2e.seed45.Periapical Lesion.recall]` `[e2e.seed46.Periapical Lesion.recall]`.

None of these values is a clinical sensitivity.

### 3.4 Error analysis

The dominant errors were confusions with caries (Fig. 2):

* **Deep caries:** on ground-truth boxes, 1,083 of 2,415 predictions for deep-caries findings (45 %) were caries `[cv5:summary/gt/confusion_sum_over_seeds/1]`.
* **Periapical lesion:** 229 of 645 periapical-lesion predictions (36 %) were caries `[cv5:summary/gt/confusion_sum_over_seeds/3]`.

All five seeds agreed on the confusion for 110 caries and deep-caries findings `[cv5:caries_confusion/confused_by_all_seeds_gt]`. These findings have been listed for review by a clinician. We do not claim that they are labelling errors.

**Where end-to-end errors arise (Table 3; Fig. 6).** The error attribution reproduced the archived matched flags, end-to-end recall and confusion count exactly.

* **The detector rarely missed a tooth.** Only 3 findings, all deep caries, had no overlapping detector box `[attr:per_class/Deep Caries]`.
* **Periapical lesions were lost mainly at matching.** Of 129 periapical lesions, 22 received no matched crop through a matching conflict and 7 through a low-overlap box `[attr:per_class/Periapical Lesion]`. In a matching conflict, the tooth carried another finding, which took the tooth box under one-to-one matching.
* **Deep caries was lost mainly at localisation.** Of 483 deep-caries findings, 34 overlapped a tooth box only with an IoU below 0.5, against 14 matching conflicts `[attr:per_class/Deep Caries]`.
* **Classification still dominated.** Misclassification of matched crops accounted for a proportion of end-to-end errors between 0.662 for periapical lesions `[attr:per_class/Periapical Lesion]` and 0.919 for caries `[attr:per_class/Caries]`.

**Table 3.** Attribution of end-to-end errors (post-hoc; findings, and finding × seed predictions for error shares).

| Class | Findings | No overlapping box | IoU < 0.5 | Matching conflict | Share of errors from detection or matching | Share of errors from classification | Source |
|---|---|---|---|---|---|---|---|
| Caries | 1,755 | 0 | 2 | 16 | 0.081 | 0.919 | `[attr:per_class/Caries]` |
| Deep caries | 483 | 3 | 34 | 14 | 0.174 | 0.826 | `[attr:per_class/Deep Caries]` |
| Impacted | 484 | 0 | 5 | 3 | 0.233 | 0.767 | `[attr:per_class/Impacted]` |
| Periapical lesion | 129 | 0 | 7 | 22 | 0.338 | 0.662 | `[attr:per_class/Periapical Lesion]` |

### 3.5 Variation across folds and subsets

**Folds.** Detector-box macro-F1 was 0.675 ± 0.032 across folds `[det_matched.fold_level.mean]` `[det_matched.fold_level.sd]`. Per-fold means ranged from 0.647 to 0.725 `[det_matched.fold3.macro_f1.mean]` `[det_matched.fold0.macro_f1.mean]` (Fig. 4). This range is wider than the spread between seeds, which illustrates how much a single split can mislead.

**Radiographs not seen by the detector** (331 findings `[unseen.findings]`): macro-F1 was 0.685 on detector boxes and 0.710 on ground-truth boxes `[unseen.det.mean]` `[unseen.gt.mean]`.

**Official validation release:** ground-truth-box macro-F1 was 0.706 ± 0.054 `[secondary.gt.mean]` `[secondary.gt.sd]`.

### 3.6 Calibration

The expected calibration error was 0.107 on detector boxes and 0.109 on ground-truth boxes `[det_matched.ece.mean]` `[gt.ece.mean]`. The output scores should therefore not be read as probabilities without recalibration.

### 3.7 Negative results

No strategy reached the pre-registered minimum gain (Table 4; Fig. 5):

* **Imbalance strategies:** the largest gain, 0.0042, came from the unweighted reference `[neg.imbalance.REF_unweighted.gain]`, and focal loss had the lowest, −0.0138 `[neg.imbalance.C_focal.gain]`.
* **External data:** the gain was −0.0005 `[neg.external.gain]`. The recall change was −0.049 for deep caries `[neg.external.Deep Caries.recall_delta]` and −0.057 for periapical lesions `[neg.external.Periapical Lesion.recall_delta]`.
* **Seed ensemble:** the gain was 0.0072 `[neg.ensemble.gain]`, but the ensemble beat only 2 of its 5 members `[neg.ensemble.members_beaten]`. The 95 % interval of the gain, −0.0317 to 0.0481, included zero `[neg.ensemble.boot.ci95]`.

**Table 4.** Earlier improvement experiments (fixed validation split; gain in detector-box macro-F1 over the baseline; none passed its rule).

| Experiment | Gain | Cross pairs better (of 25) | Passed | Source |
|---|---|---|---|---|
| Unweighted reference | 0.0042 | 14 | No | `[neg.imbalance.REF_unweighted.gain]` `[neg.imbalance.REF_unweighted.cross_pairs]` `[neg.imbalance.REF_unweighted.pass]` |
| Square-root class weights | −0.0086 | 11 | No | `[neg.imbalance.A1_sqrt_weights.gain]` `[neg.imbalance.A1_sqrt_weights.cross_pairs]` `[neg.imbalance.A1_sqrt_weights.pass]` |
| Effective-number class weights | 0.0008 | 12 | No | `[neg.imbalance.A2_effnum_weights.gain]` `[neg.imbalance.A2_effnum_weights.cross_pairs]` `[neg.imbalance.A2_effnum_weights.pass]` |
| Class-balanced sampler | −0.0037 | 12 | No | `[neg.imbalance.B_sampler.gain]` `[neg.imbalance.B_sampler.cross_pairs]` `[neg.imbalance.B_sampler.pass]` |
| Focal loss | −0.0138 | 8 | No | `[neg.imbalance.C_focal.gain]` `[neg.imbalance.C_focal.cross_pairs]` `[neg.imbalance.C_focal.pass]` |
| Plus official validation data | −0.0043 | 11 | No | `[neg.imbalance.D_official_val.gain]` `[neg.imbalance.D_official_val.cross_pairs]` `[neg.imbalance.D_official_val.pass]` |
| Plus external dataset | −0.0005 | 11 | No | `[neg.external.gain]` `[neg.external.cross_pairs]` `[neg.external.pass]` |
| Five-seed ensemble | 0.0072 | – | No | `[neg.ensemble.gain]` `[neg.ensemble.pass]` |

### 3.8 Computational resources

The 25 training runs took 1.04 GPU-hours in total on a Tesla T4 `[cost.train_hours]` `[env.gpu]`, counting epoch time only. Peak GPU memory was 1,736 MB `[cost.peak_gpu_mb]`, and each checkpoint was 94,354,861 bytes `[cost.checkpoint_bytes]`. The cross-validation artifacts contain no latency `[cost.latency]`; the separate measurement of Section 2.10 is given in Table 5.

**Table 5.** Inference latency on one laptop (NVIDIA GeForce RTX 3050 Laptop GPU, 4 GB; median of five repetitions, with the range over repetitions; benchmark run 1).

| Measurement | Batch | Median (range) | Throughput | Source |
|---|---|---|---|---|
| Classifier only, GPU, ms per crop | 1 | 4.96 (4.69–5.43) | 202 crops/s | `[lat1:model_only_gpu_fp32/0/ms_per_crop]` `[lat1:model_only_gpu_fp32/0/throughput_crops_per_s_median]` |
| Classifier only, GPU, ms per crop | 64 | 2.91 | 344 crops/s | `[lat1:model_only_gpu_fp32/1/ms_per_crop]` `[lat1:model_only_gpu_fp32/1/throughput_crops_per_s_median]` |
| Classifier only, CPU, ms per crop | 1 | 65.4 | 15 crops/s | `[lat1:model_only_cpu_fp32/0/ms_per_crop]` `[lat1:model_only_cpu_fp32/0/throughput_crops_per_s_median]` |
| End-to-end, GPU, ms per radiograph | – | 251.3 (5th–95th percentile 209.0–282.5) | – | `[lat1:end_to_end_gpu/ms_per_radiograph/total]` |

**End-to-end breakdown.**
* **Stages:** detection took a median of 84.5 ms `[lat1:end_to_end_gpu/ms_per_radiograph/detector]` and classification of all detected teeth 89.1 ms `[lat1:end_to_end_gpu/ms_per_radiograph/classify]`.
* **Boxes:** the detector produced a median of 29 boxes per radiograph `[lat1:end_to_end_gpu/detector_boxes_per_image]`.
* **Memory:** peak GPU memory was 698 MB `[lat1:end_to_end_gpu/peak_allocated_mb]`.
* **Repeatability:** a second, independent run gave an end-to-end median of 241.7 ms `[lat2:end_to_end_gpu/ms_per_radiograph/total]`.
* **Not included:** image upload, tooth numbering, segmentation and report generation.

## 4. Discussion

### 4.1 Principal findings

On a public benchmark and under a leakage-controlled, cross-validated design, a standard ResNet-50 finding classifier performs well on impacted teeth and caries but poorly on deep caries and periapical lesions. These two classes carry the most clinical consequence. The leading error is that both are predicted as caries:

* Deep caries and caries lie on a continuum of lesion depth, and the boundary between them is partly a matter of the annotator's judgement.
* Periapical lesions are rare in the pool and appear as subtle changes at the root apex, while the crop is centred on the annotated tooth.

The consistently confused findings may contain label noise as well as model error. Only a clinician's re-reading could separate the two, and none has been done. A blinded re-reading design is prepared, with an equal number of never-confused control findings so that readers cannot tell which items are suspected, but it has not been carried out.

The error attribution locates the losses more precisely, and it points to different remedies for the two weak classes:

* **Periapical lesions:** the tooth detector found the relevant tooth, but one-to-one matching gave the tooth box to another finding on the same tooth. A matching rule that lets one tooth box serve several findings could therefore recover some periapical lesions without any retraining.
* **Deep caries:** losses came mostly from a mismatch between finding boxes and tooth boxes.
* **Classification:** classification errors on correctly localised teeth remained the largest component for every class.

We have not evaluated any of these remedies. Doing so on the present data would be an unregistered, post-hoc analysis, so they belong to the registered candidate process.

### 4.2 Why the remedies did not help

Re-weighting, re-sampling, focal loss, additional official data, external data and ensembling all failed their pre-registered rules. Most gains were close to zero and small next to the gain threshold. A plausible explanation is that the limit lies in the amount and consistency of minority-class evidence rather than in the training objective. This is a hypothesis and was not tested.

Reporting these failures matters. Each strategy, evaluated on a single split without a pre-specified rule, could have produced a favourable-looking number by chance.

### 4.3 Why cross-validation and a frozen protocol

The spread of per-fold macro-F1 was several times larger than the spread between seeds. A single held-out fold could therefore have suggested either a much better or a much worse model.

The frozen protocol is meant to make future improvement claims credible. It fixes in advance:

* the gain threshold;
* a multiplicity-corrected confidence requirement;
* consistency across seeds and folds;
* safeguards for the minority classes, including a hard-harm rule;
* the candidate budget;
* single, ledger-controlled use of the test split.

The protocol does not remove selection bias in favour of an eventual winner. Every candidate is evaluated on the same radiographs, and the protocol states this openly.

### 4.4 Limitations

* **Data.** The data come from a single public dataset without patient identifiers. Independence holds only at radiograph level, and there is no external test set.
* **Detector overlap.** The detector was trained on part of the pool. On the subset it had not seen, performance was not lower, but that subset is small.
* **Comparability.** The cross-validated estimates are not test-set results and cannot be compared directly with earlier single-split figures.
* **Labels.** All labels are the original dataset labels; no clinician re-read them.
* **Earlier experiments.** These used a different split and different rules.
* **Untested settings.** We did not study other crop sizes, other architectures, matching rules or detector improvements. Candidates of this kind have been drafted for registration under the protocol, but none has yet been registered or trained.
* **Post-hoc analyses.** The per-class intervals and the error attribution were computed after the main results were known. They are descriptive and were not used to select or tune any model.
* **Latency.** It was measured on one laptop GPU without control of power or thermal state, using a baseline-recipe checkpoint of the same architecture. Other hardware will give different values.
* **Calibration.** No recalibration was applied. Fitting a temperature without leakage needs the inner-validation predictions, which were not archived; a registered experiment is drafted.
* **Intended use.** The system is a research prototype and has not been validated for clinical use.

## 5. Conclusion

On DENTEX, a cross-validated ResNet-50 baseline reached a macro-F1 of 0.68 on detector boxes and 0.70 on ground-truth boxes `[det_matched.macro_f1.mean]` `[gt.macro_f1.mean]`, with low recall for deep caries and periapical lesions. Common imbalance remedies, extra data and ensembling did not improve it under pre-registered rules. We provide the estimates, their uncertainty, fully traceable artifacts and a frozen acceptance protocol as a reference for future work on these clinically important classes.

## Declarations

* **Ethics approval and consent to participate:** [to be provided by the authors].
* **Funding:** [to be provided by the authors].
* **Competing interests:** [to be provided by the authors].
* **Author contributions:** [CRediT statement to be provided by the authors].
* **Data availability:** DENTEX is available from its official source. Fold assignments, manifests and the archived cross-validation artifacts, with SHA-256 checksums, are described in Supplementary Material S1.
* **Code availability:** [repository and release to be decided by the authors].
* **Use of AI-assisted tools:** [statement to be provided by the authors according to the journal's policy].
* **Acknowledgements:** [to be provided by the authors].

## Figure legends

**Figure 1.** Study design. The radiograph-grouped 5-fold cross-validation with five seeds produces out-of-fold predictions in three evaluation settings. The bootstrap resamples whole radiographs. The calibration and test splits were held out, and the acceptance protocol for future candidates was frozen before any candidate was trained.

**Figure 2.** Confusion matrices, summed over five seeds, for ground-truth boxes (left) and matched detector boxes (right). Cells show row proportions, with counts in parentheses.

**Figure 3.** Recall per class in three evaluation settings. Error bars show radiograph-bootstrap 95 % intervals; dots show the end-to-end recall of each seed.

**Figure 4.** Detector-box macro-F1 per held-out fold. Dots are seeds, bars are fold means, and the dashed line is the pooled estimate.

**Figure 5.** Macro-F1 gain over the baseline for the earlier improvement experiments on the fixed validation split. The dashed line marks the pre-registered minimum gain. The error bar shows the bootstrap interval for the ensemble.

**Figure 6.** Post-hoc attribution of end-to-end predictions (finding × seed) per class. The categories are: no overlapping detector box; a detector box with intersection-over-union below 0.5; a matching conflict, where the box was assigned to another finding on the same tooth; misclassification on a matched box; and correct.

## Supplementary Material S1: reproducibility

**Archived artifacts and integrity checks** (all verified on 25 October 2026):

| Artifact | SHA-256 (prefix) | Check |
|---|---|---|
| Cross-validation archive | `4ac56843` | 88 of 88 entries match their checksums |
| Imbalance experiment run | per file | 61 of 61 entries match their checksums |
| External-data run | per file | 39 of 39 entries match their checksums |
| Ensemble result file | `f208246a` | hash only; not part of a checksummed archive |
| Fold assignment file | `9b767a48` | — |
| Acceptance protocol (revision 3) | `0771b5f8` | — |

**Traceability.** Every number in this manuscript is traced to these artifacts by machine-readable tables: 133 rows for the cross-validation results, 49 rows for the negative results, and the per-class bootstrap file. The error attribution and the two latency benchmark runs are stored as machine-readable files with the hashes of their inputs and checkpoints. An automated audit checks each number against its source.

**Environment.** Training ran on Kaggle with a Tesla T4 GPU `[env.gpu]`.

**To reproduce:**
1. Obtain DENTEX from its official source.
2. Build the data bundle with the repository scripts.
3. Run the cross-validation notebook.
4. Compare the resulting checksums and results with the archive.

GPU non-determinism can change the trained weights. Metrics are then expected to agree within seed variation, not bit for bit.
