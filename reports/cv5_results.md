# CV5-BASE results: grouped 5-fold cross-validation of the BASE finding classifier

Date 2026-10-24. Protocol: `reports/cv5_protocol.md` (pre-registered; no amendments). Readiness: `reports/cv5_readiness.md`.
Every number below is copied from `kaggle/artifacts_cv5_run1/cv5_results.json`. Nothing was estimated or filled in.

## 1. Run and provenance

* **Kaggle notebook:** "DentaMind 5-fold CV BASE" v1 (`btechgd10/dentamind-5-fold-cv-base`). It used Tesla T4 (torch 2.11.0+cu128,
  Pillow 13.0.0) and bundle dataset v3. Status: **"Successfully ran in 4945.4s"** (1.37 h).
* **Archive:** `kaggle/dentamind_5fold_cv_artifacts.zip`, 1,545,495 bytes. Its SHA-256 `4ac56843ebc370eb7f3913f6c6f2c92e78062033b7dae1727ec79b52ea220648`
  equals the hash printed in the Kaggle log. It was extracted to `kaggle/artifacts_cv5_run1/`, and all 88 entries of
  `SHA256SUMS.txt` verify.
* **Embedded inputs:** the archived fold file hash (`9b767a48…47a6`) equals the approved one. The archived `cv5_lib.py` is
  byte-identical to `kaggle/cv5_lib.py`.
* **Checkpoints:** the 25 checkpoints remain in the Kaggle notebook output. Their hashes are in `checkpoint_manifest.json`; they were
  not downloaded.
* **Unchanged:** no model was promoted, and production, the deployed checkpoint, earlier artifacts and the paper are unchanged. No test
  or calibration image was read.

## 2. Integrity gates (all passed)

| Gate | Result |
|---|---|
| 1 Folds | passed: 581 groups, 3,010 findings; 116/118/113/116/118 radiographs per fold |
| 2 Per-fold plans | passed for all 5 folds (fit / inner / held-out disjoint) |
| 3 Detector reproduction | passed: 65 images, 331/331 findings same match, median box IoU 0.99992 |
| 4 Runs complete | passed: 25/25, "failed runs: none" |
| 5 One out-of-fold prediction per primary finding per seed | passed: 2,851 findings × 5 seeds |

## 3. Primary estimate: pooled out-of-fold, 2,851 `dentex_train_disease` findings (541 radiographs)

Class counts: Caries 1,755; Deep Caries 483; Impacted 484; Periapical Lesion 129. Of these findings, 2,745 are matched to a detector
box, and 106 are unmatched for every seed.

| Setting | Macro-F1, mean ± SD over 5 seeds | Per seed (42…46) | Radiograph bootstrap 95 % CI (2,000 resamples) |
|---|---|---|---|
| **Detector boxes (matched findings)**, primary | **0.677 ± 0.008** | 0.668, 0.673, 0.681, 0.689, 0.673 | **0.652 – 0.701** |
| GT boxes | 0.698 ± 0.007 | 0.700, 0.698, 0.706, 0.697, 0.687 | 0.675 – 0.718 |

| Setting | Accuracy | Balanced acc. | ECE (10 bins) | NLL |
|---|---|---|---|---|
| Detector boxes | 0.807 ± 0.005 | 0.675 ± 0.010 | 0.107 ± 0.003 | 0.666 ± 0.022 |
| GT boxes | 0.804 ± 0.004 | 0.693 ± 0.009 | 0.109 ± 0.006 | 0.663 ± 0.028 |

The bootstrap interval covers resampling of radiographs given the trained models. It does not capture training-set variation across
folds (protocol §5).

### Per class (mean ± SD over seeds)

| Class | Det. precision | Det. recall | Det. F1 | GT precision | GT recall | GT F1 |
|---|---|---|---|---|---|---|
| Caries | 0.848 ± 0.003 | 0.883 ± 0.007 | 0.865 ± 0.003 | 0.847 ± 0.004 | 0.874 ± 0.005 | 0.860 ± 0.004 |
| **Deep Caries** | 0.546 ± 0.024 | **0.440 ± 0.018** | 0.487 ± 0.017 | 0.576 ± 0.018 | 0.496 ± 0.012 | 0.533 ± 0.012 |
| Impacted | 0.935 ± 0.011 | 0.945 ± 0.007 | 0.940 ± 0.007 | 0.913 ± 0.013 | 0.949 ± 0.009 | 0.931 ± 0.007 |
| **Periapical Lesion** | 0.401 ± 0.020 | **0.432 ± 0.033** | 0.416 ± 0.023 | 0.485 ± 0.019 | 0.451 ± 0.047 | 0.467 ± 0.033 |

### Confusion matrices, summed over the 5 seeds (rows = true class, columns = predicted; order Caries, Deep Caries, Impacted, PL)

| Detector boxes | Caries | Deep Caries | Impacted | PL |
|---|---:|---:|---:|---:|
| Caries | 7,666 | 682 | 88 | 249 |
| Deep Caries | 1,083 | 950 | 57 | 70 |
| Impacted | 83 | 45 | 2,248 | 4 |
| PL | 207 | 66 | 11 | 216 |

| GT boxes | Caries | Deep Caries | Impacted | PL |
|---|---:|---:|---:|---:|
| Caries | 7,673 | 722 | 132 | 248 |
| Deep Caries | 1,083 | 1,197 | 76 | 59 |
| Impacted | 76 | 47 | 2,296 | 1 |
| PL | 229 | 114 | 11 | 291 |

**Main errors:**
* Deep Caries is predicted as Caries in 1,083 of 2,415 GT-box predictions (45 %).
* Periapical Lesion is predicted as Caries in 229 of 645 (36 %).

### End-to-end (unmatched findings count as wrong; all 2,851 findings)

* Accuracy 0.777 ± 0.005.
* Recall: Caries 0.874 ± 0.007, Deep Caries 0.393 ± 0.016, Impacted 0.929 ± 0.007, Periapical Lesion 0.335 ± 0.025.

### Existing production abstention rule (not refitted; seed 42 shown, descriptive only)

* GT boxes: 514 of 2,851 abstained; accuracy on the accepted findings 0.861.
* Detector boxes: 486 of 2,745 abstained; accuracy on the accepted findings 0.853.

## 4. Per fold (descriptive; folds share training data and are not independent replicates)

| Held-out fold | Radiographs | Findings | Det.-matched | Det. macro-F1 | GT macro-F1 | GT DC recall | GT PL recall |
|---|---:|---:|---:|---|---|---:|---:|
| 0 | 108 | 592 | 564 | 0.725 ± 0.015 | 0.713 ± 0.022 | 0.511 | 0.510 |
| 1 | 108 | 592 | 566 | 0.652 ± 0.020 | 0.673 ± 0.031 | 0.537 | 0.400 |
| 2 | 106 | 591 | 572 | 0.662 ± 0.012 | 0.711 ± 0.013 | 0.455 | 0.496 |
| 3 | 109 | 530 | 513 | 0.647 ± 0.031 | 0.678 ± 0.018 | 0.514 | 0.330 |
| 4 | 110 | 546 | 530 | 0.689 ± 0.021 | 0.709 ± 0.011 | 0.466 | 0.504 |
| **Across folds** | | | | **0.675 ± 0.032** | 0.697 ± 0.020 | | |

(± within a row = SD over seeds. Recall values are seed means. Each fold has only 20-31 Periapical Lesion findings, so fold-level PL
recall is unstable.)

## 5. Subsets stated in advance

| Population | Findings | Det. macro-F1 | GT macro-F1 |
|---|---:|---|---|
| Detector-unseen subset: 65 old-validation radiographs, not in the detector's training assignment | 331 | 0.685 ± 0.023 | 0.710 ± 0.025 |
| Secondary: DENTEX official-validation findings, never trained on; 5 fold models each predict their own share | 159 | – | 0.706 ± 0.054 |

On the detector-unseen subset, detector-box macro-F1 (0.685) is not lower than the pooled value (0.677). So this run gives no
evidence that the detector's training overlap inflated the pooled detector-box estimate. With only 331 findings, it also cannot rule
that out. The official-validation result rests on 159 findings and varies widely by seed (0.623–0.764).

## 6. Caries vs Deep Caries (exploratory, protocol §6)

* Confused by **all 5 seeds** (GT boxes):
  - 93 of 483 Deep Caries findings (19 %) were predicted as Caries;
  - 17 of 1,755 Caries findings (1 %) were predicted as Deep Caries.
  - These 110 findings come from 88 radiographs. They are listed in `reports/cv5_caries_clinician_review_list.csv` **for clinician
    review**. They are not label errors: this analysis cannot separate model error from annotation ambiguity.
* Mean share of seeds predicting the other caries class, by tooth type:

  | Tooth type | Deep Caries findings | Share | Caries findings | Share |
  |---|---:|---:|---:|---:|
  | Molar | 357 | 0.42 | 1,159 | 0.08 |
  | Premolar | 104 | 0.50 | 432 | 0.09 |
  | Incisor | 16 | 0.66 | 104 | 0.10 |
  | Canine | 6 | 0.70 | 60 | 0.06 |

* By box-area quartile, Deep Caries confusion **rises with box size**: 0.33, 0.44, 0.51, 0.59 for quartiles 1 to 4 (edges 35,992 /
  46,845 / 62,195 px²). Caries confusion falls slightly with size (0.11 → 0.07).

## 7. Interpretation and limits

* **Baseline estimate:**
  - The cross-validated BASE estimate on the DENTEX training/validation radiographs is detector-box macro-F1 **0.677** (95 % CI
    0.652–0.701) and GT-box macro-F1 **0.698** (0.675–0.718).
  - Seed-to-seed SD is small (about 0.008). Fold-to-fold SD is larger (0.032 detector, 0.020 GT), so which radiographs are held out
    matters more than the seed.
* **Weak classes:** Deep Caries (detector recall 0.44) and Periapical Lesion (detector recall 0.43). The dominant failure is that both
  get absorbed into Caries.
* **Calibration:** raw softmax ECE is about 0.11 out of fold.
* **Comparability:** these are not test results. They are not directly comparable with the earlier single-split numbers (for example
  BASE test detector-box macro-F1 0.730 ± 0.028 in the ensemble run). The populations differ, and the CV estimate pools 5 models, each
  trained on about 380 radiographs.
* **Remaining limits:**
  - independence is at radiograph level only, since there are no patient IDs;
  - single-centre DENTEX data;
  - 129 Periapical Lesion findings, below the P2 target;
  - detector-box results partly use radiographs from the detector's training set (see §5).
* **Future candidates:** this run fixes the baseline distribution for future CV comparisons. Per protocol §8, the CV acceptance rule
  for candidates must be written and approved before any candidate is run.
