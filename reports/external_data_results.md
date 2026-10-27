# External-data experiment: results (protocol `reports/external_data_protocol.md`)

Run: Kaggle notebook "DentaMind external data training", version 1, Tesla T4, 2026-10-24, 1.09 h, no failed runs.
Artifacts: `kaggle/dentamind_external_data_artifacts.zip` (sha256 `c62591ac5bc1de39ce8c87cc8e1c5d66586817b1b79a232ba8dba78593a2b9ed`),
extracted to `kaggle/artifacts_external_run1/`, every file verified against its `SHA256SUMS.txt`. All numbers below are copied from
those files; nothing was re-run or adjusted.

## Experiments

| Experiment | Status |
|---|---|
| BASE (DENTEX train) | run, seeds 42-46 |
| X2_hanoi (+1,500 Hanoi Periapical Lesion crops from 977 radiographs) | run, seeds 42-46 |
| X1_cluj, X3_both | **withdrawn before training**: Cluj failed the protocol's visual label check (amendment of 2026-10-24) |

## Acceptance (DENTEX validation, production-detector boxes, pre-registered criteria)

**X2_hanoi: FAIL.**

| Criterion | Result | Pass |
|---|---|---|
| 1. macro-F1 gain > 0.027, ≥ 4/5 seed pairs, ≥ 20/25 cross pairs | gain −0.0005; 2/5 seed pairs; 11/25 cross pairs | no |
| 2. Deep Caries and Periapical Lesion recall not lower | DC −0.049, PL −0.057 | no |
| 3. no class F1 drop > 0.05 | largest drop DC −0.022 | yes |
| 4. GT-box macro-F1 drop ≤ 0.02 | −0.006 | yes |
| 5. minority precision drop ≤ 0.10 | DC +0.008, PL +0.051 | yes |

## DENTEX validation (331 findings; mean ± SD over 5 seeds)

| Setting | Experiment | macro-F1 (per seed 42-46) | mean | accuracy | ECE (10 bins) |
|---|---|---|---|---|---|
| GT boxes | BASE | 0.744, 0.802, 0.746, 0.751, 0.743 | 0.757 ± 0.025 | 0.852 ± 0.016 | 0.092 ± 0.014 |
| GT boxes | X2_hanoi | 0.749, 0.748, 0.748, 0.780, 0.731 | 0.751 ± 0.018 | 0.862 ± 0.004 | 0.098 ± 0.010 |
| Detector boxes | BASE | 0.701, 0.742, 0.700, 0.748, 0.759 | 0.730 ± 0.028 | 0.848 ± 0.024 | 0.096 ± 0.018 |
| Detector boxes | X2_hanoi | 0.699, 0.729, 0.756, 0.767, 0.697 | 0.729 ± 0.032 | 0.853 ± 0.009 | 0.107 ± 0.009 |

Per class, detector boxes (mean ± SD):

| Class | BASE P / R / F1 | X2_hanoi P / R / F1 |
|---|---|---|
| Caries | 0.888 / 0.891 / 0.889 | 0.874 / 0.910 / 0.892 |
| Deep Caries | 0.579 / 0.507 / 0.535 | 0.586 / 0.459 / 0.513 |
| Impacted | 0.934 / 0.939 / 0.936 | 0.947 / 0.936 / 0.941 |
| Periapical Lesion (n = 9) | 0.474 / 0.686 / 0.560 | 0.525 / 0.629 / 0.572 |

## Secondary: Cluj external evaluation (never trained on; recall only)

Recall of the labelled class among Cluj evaluation crops, mean ± SD over 5 seeds. "Caries-any" = predicted Caries or Deep Caries for a
Cluj CAR tooth. Precision cannot be computed from these crops, so a recall gain may come with more false positives.

| Set | Metric (n) | BASE | X2_hanoi |
|---|---|---|---|
| Cluj `test` | Impacted (58) | 0.962 ± 0.026 | 0.948 ± 0.024 |
| Cluj `test` | Periapical Lesion (69) | 0.206 ± 0.062 | 0.394 ± 0.081 |
| Cluj `test` | Caries-any (132) | 0.936 ± 0.013 | 0.888 ± 0.034 |
| Cluj multi-center (180 images) | Impacted (111) | 0.932 ± 0.005 | 0.926 ± 0.021 |
| Cluj multi-center | Periapical Lesion (91) | 0.207 ± 0.046 | 0.360 ± 0.036 |
| Cluj multi-center | Caries-any (278) | 0.937 ± 0.012 | 0.847 ± 0.049 |

Reading: on outside data, Hanoi roughly doubles Periapical Lesion recall (about 0.21 → 0.36-0.39) but lowers caries-any recall by
5-9 points, i.e. more teeth are called Periapical Lesion overall. On DENTEX validation (9 PL findings) the same models show no gain.
Caveats: Cluj labels are definition-mapped, not dentist-confirmed; 2 Cluj evaluation images were flagged for the label-numbering fault.

## DENTEX test split (BASE only, as the ledger rule requires)

| | per seed 42-46 | mean |
|---|---|---|
| BASE test macro-F1 (GT boxes) | 0.667, 0.736, 0.737, 0.696, 0.691 | 0.705 ± 0.031 |

Deployed classifier re-evaluated as a reference in the same run: validation macro-F1 0.714 (GT) / 0.650 (detector), test 0.651 (GT).
This test use still has to be recorded in `Data/reports/test_set_ledger.json` (entry prepared:
`kaggle/artifacts_external_run1/ledger_disclosure_entry.json`; needs the owner's name as authorizer).

## Conclusion

Under the pre-registered rule, adding Hanoi Periapical Lesion crops does **not** improve the DENTEX classifier, and no checkpoint is
promoted. The Cluj external evaluation suggests a trade-off (higher lesion recall, lower caries recall) rather than a clean gain.
Cluj itself could not be used for training because of a label-numbering fault in the published dataset. Production is unchanged.
