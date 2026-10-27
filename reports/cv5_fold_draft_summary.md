# DRAFT grouped 5-fold assignment (P4): FOR REVIEW, NOT APPROVED, NOT USED

File `data/splits/cv5_folds_DRAFT.csv`, SHA-256 `b001df151740f4ba3dd67550b4e6aac2b00cc2105b61cdb937331f121eb4c162`, seed 42. Units: radiograph groups of combined_train + combined_validation; test and calibration excluded (checked: no overlap).

| Fold | Radiographs | Findings | Caries | Deep Caries | Impacted | Periapical Lesion | PL radiographs | DC radiographs | from old val split |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 114 | 594 | 354 | 94 | 124 | 22 | 20 | 55 | 13 |
| 1 | 116 | 627 | 358 | 117 | 125 | 27 | 19 | 56 | 12 |
| 2 | 116 | 606 | 396 | 97 | 82 | 31 | 20 | 55 | 16 |
| 3 | 117 | 579 | 380 | 88 | 84 | 27 | 21 | 56 | 12 |
| 4 | 118 | 604 | 352 | 116 | 105 | 31 | 21 | 57 | 12 |

Radiographs per fold and source: fold 0: dentex_official_val 7, dentex_train_disease 107; fold 1: dentex_official_val 8, dentex_train_disease 108; fold 2: dentex_official_val 9, dentex_train_disease 107; fold 3: dentex_official_val 7, dentex_train_disease 110; fold 4: dentex_official_val 9, dentex_train_disease 109

Review points: (1) every fold has Periapical Lesion radiographs; (2) source mix per fold; (3) the old validation radiographs are spread over folds (they are trained on in 4 of 5 folds); (4) after clinician-verified labels are added, this draft is regenerated and needs a new review.
