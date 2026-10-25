# APPROVED grouped 5-fold assignment v1 (P4, option B: Impacted-stratified; owner approval 2026-10-24)

File `data/splits/cv5_folds_v1.csv`, SHA-256 `9b767a4822844ccf0c4bf33d299e6e37420d1458a38035af0c3a3cb9107b47a6`, seed 42. Units: radiograph groups of combined_train + combined_validation; test and calibration excluded (checked: no overlap).

| Fold | Radiographs | Findings | Caries | Deep Caries | Impacted | Periapical Lesion | PL radiographs | DC radiographs | from old val split |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 116 | 631 | 385 | 103 | 112 | 31 | 20 | 56 | 8 |
| 1 | 118 | 621 | 383 | 104 | 105 | 29 | 20 | 55 | 19 |
| 2 | 113 | 619 | 371 | 122 | 100 | 26 | 19 | 54 | 13 |
| 3 | 116 | 562 | 331 | 93 | 113 | 25 | 21 | 57 | 13 |
| 4 | 118 | 577 | 370 | 90 | 90 | 27 | 21 | 57 | 12 |

Radiographs per fold and source: fold 0: dentex_official_val 8, dentex_train_disease 108; fold 1: dentex_official_val 10, dentex_train_disease 108; fold 2: dentex_official_val 7, dentex_train_disease 106; fold 3: dentex_official_val 7, dentex_train_disease 109; fold 4: dentex_official_val 8, dentex_train_disease 110

Review points: (1) every fold has Periapical Lesion radiographs; (2) source mix per fold; (3) the old validation radiographs are spread over folds (they are trained on in 4 of 5 folds); (4) after clinician-verified labels are added, this draft is regenerated and needs a new review.
