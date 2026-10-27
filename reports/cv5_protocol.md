# Pre-registered protocol: grouped 5-fold cross-validation of the BASE finding classifier (CV5-BASE)

Status: **written 2026-10-24, before any cross-validation training or evaluation.** Changes after results are seen are recorded as
dated amendments with their reason. Governance: proposal P4 (approved with a review gate, 2026-10-16,
`reports/protocol_change_proposals.md`). The owner approved the exact fold file on 2026-10-24 (option B below).

## 1. Purpose and scope

The goal is a more reliable estimate of the BASE classifier's DENTEX performance, as the baseline for later controlled comparisons.
This experiment **compares no new model**. It changes nothing in training (no larger crops, backbones, ensembles, losses or external
data) and claims no improvement. Production, the deployed checkpoint, earlier artifacts and the paper are not changed.

Owner note: proposal P2 (provisional data targets, approved 2026-10-16) is not met (Periapical Lesion 129 training findings vs a
target of 300). The owner chose to run this baseline-only CV now. P2 still applies to later model comparisons.

## 2. Data, grouping unit and folds

* **Independent unit: the radiograph.** DENTEX has no patient identifiers (`reports/combined_split_audit.json`:
  "patient_level: not possible"). Patient-level independence is **not** claimed; two radiographs of one patient may fall in different
  folds. Exact and near duplicates (SHA-256; dHash ≤ 4 confirmed by correlation ≥ 0.97) were already merged into groups, and 0 near
  duplicates were confirmed in the pool.
* **Pool:** the 581 radiograph groups of `combined_train` and `combined_validation`: 541 `dentex_train_disease` radiographs (2,851
  findings) and 40 `dentex_official_val` radiographs (159 findings). **Excluded:** the calibration split (64 radiographs, kept for
  later calibration fitting) and the test split (73 radiographs). No test or calibration image is read, cropped or predicted. Their
  manifests are read only to confirm that none of their radiographs or image hashes is in the pool (gate 1).
* **Fold file (approved, owner 2026-10-24, option B):** `data/splits/cv5_folds_v1.csv`, SHA-256
  `9b767a4822844ccf0c4bf33d299e6e37420d1458a38035af0c3a3cb9107b47a6`. It was made by `scripts/dataset/make_cv_folds.py --approved-v1`
  (K = 5, seed 42, stratum = source family × has Periapical Lesion × has Deep Caries × has Impacted; seeded order inside a stratum;
  each group goes to the fold with the fewest groups of that stratum). Summary: `reports/cv5_folds_v1_summary.md`. All findings of a
  radiograph are in one fold.

## 3. Training per fold (BASE recipe, unchanged)

* For held-out fold k, the training side is the other four folds.
* **Data rule = BASE (`data="dentex"`):** only `dentex_train_disease` findings are used for fitting and epoch selection. Official-val
  findings are never trained on (as in BASE).
* **Inner validation (epoch selection only):** the training-side `dentex_train_disease` groups are split by the same algorithm
  (`assign_folds`, Impacted-stratified) with K = 8 and seed 42 + k.
  Inner fold 0 (about 12.5 % of the training radiographs, group-disjoint) is used to choose the best epoch by macro-F1, exactly as BASE
  does. The rest is used for fitting. The held-out fold is never used for fitting, epoch selection, thresholds or calibration.
* **Recipe:** `EXPERIMENTS["BASE"]` in `kaggle/dentamind_kaggle.py`: ResNet-50 (ImageNet), 224 px crops with 10 % padding, CE with
  inverse-frequency class weights capped at 5 (computed from the fitting rows of that fold only), 15 epochs, batch 32, lr 3e-4,
  wd 1e-4, horizontal flip 0.5, contrast 0.1.
* **Seeds:** 42, 43, 44, 45, 46 for every fold: 25 runs. Run name `CV5_BASE_f<k>`, seed s.
* No temperature scaling or thresholds are fitted. Probabilities are raw softmax and the prediction is the argmax.

## 4. Evaluation

* Each run predicts its held-out fold once.
* **Primary population:** `dentex_train_disease` findings, so each of the 2,851 findings receives exactly one out-of-fold prediction per
  seed.
* **Secondary population:** official-val findings (159), reported separately.
* **Settings:** (a) **detector boxes**, the primary setting as in the BASE comparison: production tooth detector
  `dentex_teeth_detection_v1` (Faster R-CNN, score ≥ 0.3, grayscale replicated to 3 channels, mixed precision on GPU, as in
  `dentexmodel.inference.torch_models._run_detector`). Findings are matched to detector boxes one-to-one by IoU ≥ 0.5 (greedy, as
  `dentamind_kaggle.match`). (b) **GT boxes.** (c) **End-to-end recall**, where unmatched findings count as wrong.
* **Detector caveat (stated in advance):** the detector's training assignment (`dentex_splits.json`, fingerprint `7f66d59d…`) includes
  the 476 project-train radiographs of the pool. Detector-box metrics on those may be optimistic. They are therefore also reported for
  the 65 old-validation radiographs, which the detector never trained on.
* **Metrics** (`dentamind_kaggle.report`): macro-F1; per-class precision/recall/F1; confusion matrix; accuracy; ECE (10 bins); NLL;
  numbers of radiographs and findings; detector-matched/unmatched counts.

## 5. Aggregation and uncertainty

* **Primary estimate:** for each seed, macro-F1 of the pooled out-of-fold predictions (all 5 folds together). Reported per seed and as
  mean ± SD over the 5 seeds.
* **95 % interval:** cluster bootstrap over **radiographs** (2,000 resamples, seed 0). Each resample draws radiographs with
  replacement and takes all their findings. The statistic is the seed-mean pooled macro-F1. The interval reflects sampling of
  radiographs given the trained models. Seed-to-seed variation is reported separately. Training-set variation across folds is not
  fully captured; this is a stated limitation.
* **Per fold:** macro-F1 and per-class metrics per fold, mean ± SD over folds. These are descriptive. Folds share training data and
  are **not** independent replicates, so no fold-level confidence interval is computed.
* No claim is made that CV yields "N times more independent evidence" or a guaranteed narrower interval.

## 6. Caries vs Deep Caries analysis (exploratory)

For every `dentex_train_disease` finding labelled Caries or Deep Caries, the analysis records how many of the 5 seeds predicted the
other caries class (detector and GT settings), with the image, FDI tooth, box size and the original DENTEX label. Findings confused by
all 5 seeds are listed for **clinician review**. They are not called label errors: the analysis cannot separate model error from
annotation ambiguity. Confusion is summarised by tooth type and box-size quartile.

## 7. Integrity gates (pre-registered; the run stops or the result is invalid if any fails)

1. The fold-file SHA-256 equals section 2; every pool group appears exactly once; no group or image SHA-256 is in two folds; no pool
   group is in the calibration or test split.
2. Per fold: fitting, inner-validation and held-out groups are pairwise disjoint; the held-out fold is never in the training files.
3. **Detector reproduction:** on the 65 old-validation radiographs, the regenerated detector boxes give the **same matched set of
   findings** as the cached production boxes (`val_detector_boxes.json`), and the median IoU of corresponding boxes is ≥ 0.98.
   Otherwise detector-box results are not reported; GT-box results still are.
4. No failed run. Otherwise the notebook is resumed (`RESUME_FROM`) until all 25 runs exist. Folds are never silently dropped.
5. Every primary finding has exactly one out-of-fold prediction per seed.

## 8. Existing acceptance criteria (recorded, not applied here)

The project's acceptance rule for a candidate vs BASE (`ACCEPT` in `kaggle/dentamind_kaggle.py`) is: macro-F1 gain > 0.027 in ≥ 4/5
seed pairs and ≥ 20/25 cross pairs; Deep Caries and Periapical Lesion recall not lower; no class F1 drop > 0.05; GT-box macro-F1 drop
≤ 0.02; minority precision drop ≤ 0.10. **No candidate is evaluated in this experiment, so the rule is not applied.** A
cross-validated version for future candidates (paired by fold × seed on the same out-of-fold findings) will be written and approved
before any such comparison. It is not defined here, to avoid fixing thresholds before the CV variance is known. Everything in
section 6 is exploratory.

## 9. Relation to earlier test-split use

The test split (73 radiographs) is outside the pool and is not loaded. `Data/reports/test_set_ledger.json` already lists earlier final
evaluations, and a disclosure of the external-data run's BASE test evaluation is prepared but not yet recorded by the owner. CV5
results come from the training and validation radiographs only, so they are not test results. They are not comparable fold-by-fold
with the earlier single-split validation numbers, because the old validation radiographs are trained on in 4 of 5 folds.
