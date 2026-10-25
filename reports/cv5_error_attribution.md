# CV5-BASE run 1: error attribution (post-hoc, descriptive)

Script `scripts/cv5_error_attribution.py` (sha256 `46120e638b09d57c0ea5653ec2207c2a1b344016405450b872b41d609e4791a7`). All gates passed: matched flags, end-to-end recall and the consistent-confusion count reproduce the archive exactly.

| Class | Findings | No overlapping box (U0) | Box IoU < 0.5 (U1) | Matching conflict (U2) | Matched | Unmatched share | End-to-end errors from detection / matching | from classification | Consistent confusion (GT, 5/5 seeds) |
|---|---|---|---|---|---|---|---|---|---|
| Caries | 1755 | 0 | 2 | 16 | 1737 | 0.010 | 0.081 | 0.919 | 17 |
| Deep Caries | 483 | 3 | 34 | 14 | 432 | 0.106 | 0.174 | 0.826 | 93 |
| Impacted | 484 | 0 | 5 | 3 | 476 | 0.017 | 0.233 | 0.767 | 0 |
| Periapical Lesion | 129 | 0 | 7 | 22 | 100 | 0.225 | 0.338 | 0.662 | 0 |

Classification errors on matched detector boxes (finding x seed), by predicted class:

* Caries: {"Impacted": 88, "Deep Caries": 682, "Periapical Lesion": 249}
* Deep Caries: {"Impacted": 57, "Caries": 1083, "Periapical Lesion": 70}
* Impacted: {"Caries": 83, "Deep Caries": 45, "Periapical Lesion": 4}
* Periapical Lesion: {"Deep Caries": 66, "Caries": 207, "Impacted": 11}

Inputs (SHA-256):

* `kaggle/artifacts_cv5_run1/oof_predictions.csv` `a90d16d8205acb7d3ea838149107535a4eef1a6114e5ea3633eb3c34138f1543`
* `kaggle/artifacts_cv5_run1/detector_boxes_pool.json` `a69d63cf2b4c677ef10476da2260cb4339d8e6c40904f4edbce37ef25d940e37`
* `kaggle/artifacts_cv5_run1/cv5_results.json` `52d94923bebad5596eeccfa26ead92a30237f289e6e4dd40963d13c78b29bd82`
* `kaggle/artifacts_cv5_run1/caries_confusion_findings.csv` `9998c9451e66e9224b030e7537628c06ebf943b4283657058fe8080e8d8b0ecf`
* `data/splits/combined_train.csv` `faf2902e473107138c6ce1111f6495f295ef46fffaa9cdbec9f54b0c5d8f4c98`
* `data/splits/combined_validation.csv` `3e29ffa00f8b9053de73ef0f89d2730ed842838394648a0c0816916754b76375`
