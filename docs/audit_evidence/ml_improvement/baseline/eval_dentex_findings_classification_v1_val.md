# Evaluation: dentex_findings_classification_v1 on the **val** split

Generated 2026-10-14T18:01:24.782106+00:00. Images: 65. Dataset version: `{'fingerprint': '7f66d59d9cbad925', 'manifest_sha': '932b0b941f54643e', 'splits_sha': 'ee88dc6835eb9a20', 'assignments_sha': '1c350480eed2ae96'}`.

All numbers below were computed by running this checkpoint over that split. Research use only; not a diagnosis.

## classification

- Accuracy: 0.8248; macro-F1: 0.7179; macro one-vs-rest ROC-AUC: 0.916; crops: 331

| Class | Precision | Recall (sensitivity) | Specificity | F1 | ROC-AUC (OvR) | Support |
|---|---:|---:|---:|---:|---:|---:|
| Caries | 0.885 | 0.863 | 0.817 | 0.874 | 0.904 | 205 |
| Deep Caries | 0.500 | 0.467 | 0.927 | 0.483 | 0.794 | 45 |
| Impacted | 0.919 | 0.944 | 0.977 | 0.932 | 0.995 | 72 |
| Periapical Lesion | 0.467 | 0.778 | 0.975 | 0.583 | 0.968 | 9 |

Confusion matrix (rows = true, columns = predicted), class order: Caries, Deep Caries, Impacted, Periapical Lesion

```
  177    18     5     5
   20    21     1     3
    2     2    68     0
    1     1     0     7
```
