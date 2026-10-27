# Ensemble evaluation: 5 BASE seeds, mean softmax probability (DENTEX validation)

Protocol: `reports/ensemble_protocol.md` (written 2026-10-24, before any ensemble prediction). Code: `kaggle/ensemble_eval.py`
(sha256 `44a89511641a7c23ffe160eb30c20958191738407ff95f0ea283d932c3cee262`), tests `tests/test_ensemble_eval.py` (21 passed).
Result file: `reports/ensemble_evaluation_kaggle.json` (copied unchanged from the Kaggle notebook "DentaMind BASE ensemble eval" v1,
Tesla T4, torch 2.11.0+cu128, 2026-10-24 14:41 UTC). All numbers below come from that file. **The DENTEX test split was not loaded.**

## Verdict: FAIL (pre-registered acceptance). No improvement is claimed. No checkpoint, report or paper was changed.

| Criterion (detector boxes unless stated) | Result | Pass |
|---|---|---|
| 1. Macro-F1 gain over BASE mean > 0.027 and beats ≥ 4/5 members | +0.007; beats 2/5 (s42, s44) | no |
| 2. Deep Caries and Periapical Lesion recall not lower than BASE mean | DC −0.020, PL +0.029 | no |
| 3. No class F1 more than 0.05 below BASE mean | smallest Δ PL −0.004 | yes |
| 4. GT-box macro-F1 not more than 0.02 below BASE mean | +0.007 | yes |
| 5. Minority precision not more than 0.10 below BASE mean | DC +0.046, PL −0.020 | yes |

Bootstrap, reported but not used for acceptance (2,000 resamples, seed 0): ensemble − BASE-mean macro-F1 = +0.007, 95 % interval
[−0.032, +0.048] with detector boxes (positive in 62.5 % of resamples) and [−0.026, +0.040] with GT boxes. Both intervals include 0.

## Members and reproduction gate

The five registered checkpoints (SHA-256 verified) were re-evaluated in the Kaggle environment that produced the BASE numbers. All
reproduced their recorded macro-F1 **exactly** (difference 0.0 in both settings), so the gate passed.

The first attempt on the local PC (torch 2.6.0, Pillow 12.3.0, RTX 3050) failed the same gate: differences of up to 0.018 macro-F1.
No ensemble number was computed there. The exact Kaggle reproduction supports the explanation that the local differences came from
the software environment (crop resizing, convolution numerics), not from the checkpoints or data.

## Results (validation: 331 findings / 65 radiographs; detector-matched 323, 8 unmatched)

| Setting | Model | Macro-F1 | Accuracy | ECE (10 bins) | NLL |
|---|---|---|---|---|---|
| Detector boxes | BASE members s42-s46 | 0.701, 0.741, 0.700, 0.748, 0.759 | | | |
| Detector boxes | BASE mean ± SD | 0.730 ± 0.028 | 0.848 ± 0.024 | 0.096 ± 0.018 | 0.582 ± 0.046 |
| Detector boxes | **Ensemble** | **0.737** | **0.864** | **0.058** | **0.401** |
| GT boxes | BASE members s42-s46 | 0.744, 0.802, 0.746, 0.751, 0.743 | | | |
| GT boxes | BASE mean ± SD | 0.757 ± 0.025 | 0.852 ± 0.016 | 0.092 ± 0.014 | 0.530 ± 0.067 |
| GT boxes | **Ensemble** | **0.765** | **0.870** | **0.034** | **0.358** |

Per class, detector boxes (precision / recall / F1):

| Class (n) | BASE mean | Ensemble |
|---|---|---|
| Caries (203) | 0.888 / 0.891 / 0.889 | 0.899 / 0.916 / 0.907 |
| Deep Caries (41) | 0.579 / 0.507 / 0.535 | 0.625 / 0.488 / 0.548 |
| Impacted (72) | 0.934 / 0.939 / 0.936 | 0.932 / 0.944 / 0.938 |
| Periapical Lesion (7) | 0.474 / 0.686 / 0.560 | 0.455 / 0.714 / 0.556 |

Per class, GT boxes (precision / recall / F1):

| Class (n) | BASE mean | Ensemble |
|---|---|---|
| Caries (205) | 0.903 / 0.886 / 0.894 | 0.900 / 0.922 / 0.911 |
| Deep Caries (45) | 0.598 / 0.578 / 0.584 | 0.676 / 0.556 / 0.610 |
| Impacted (72) | 0.916 / 0.944 / 0.930 | 0.932 / 0.944 / 0.938 |
| Periapical Lesion (9) | 0.561 / 0.711 / 0.622 | 0.545 / 0.667 / 0.600 |

Ensemble confusion matrices (rows = truth, columns = prediction; order Caries, Deep Caries, Impacted, Periapical Lesion):

| Detector boxes | C | DC | Imp | PL |
|---|---|---|---|---|
| Caries | 186 | 10 | 4 | 3 |
| Deep Caries | 17 | 20 | 1 | 3 |
| Impacted | 3 | 1 | 68 | 0 |
| Periapical Lesion | 1 | 1 | 0 | 5 |

| GT boxes | C | DC | Imp | PL |
|---|---|---|---|---|
| Caries | 189 | 9 | 3 | 4 |
| Deep Caries | 17 | 25 | 2 | 1 |
| Impacted | 3 | 1 | 68 | 0 |
| Periapical Lesion | 1 | 2 | 0 | 6 |

The five individual confusion matrices and all per-member metrics are kept in `reports/ensemble_evaluation_kaggle.json`
(`member_results`).

## Calibration and abstention (secondary)

The clearest effect of averaging is on calibration: ECE 0.096 → 0.058 (detector boxes) and 0.092 → 0.034 (GT boxes); NLL 0.58 → 0.40
and 0.53 → 0.36. With the production abstention rule (normalised entropy ≥ 0.3966, fitted for the deployed model and not refitted),
the ensemble abstains on more findings (71 vs a BASE mean of 40 with detector boxes), with accuracy 0.952 on the accepted ones. That
threshold was not designed for an ensemble, so this abstention count is not a like-for-like comparison.

## Inference latency (Tesla T4, 5 repetitions after warm-up)

| | One member | Ensemble (5) | Ratio |
|---|---|---|---|
| Batch of 64, per crop | 2.9 ms | 14.4 ms | 5.0× |
| Single crop | 7.7 ms | 38.1 ms | 4.9× |

## Interpretation and limits

* On DENTEX validation the ensemble is slightly better than the average single model on macro-F1 (+0.007), but the gain is far
  below the pre-registered 0.027. It beats only 2 of the 5 members, and the bootstrap interval includes zero. Deep Caries recall is
  slightly lower. Under the protocol this is **not an improvement**.
* Calibration improves clearly (lower ECE and NLL). This was not an acceptance criterion and is reported as a secondary observation.
  It could justify a separate, pre-registered calibration study, for example on the calibration split.
* Every member's epoch was chosen on this same validation split, so all validation numbers here are optimistic.
* Periapical Lesion has 7-9 validation findings, so its per-class numbers move by about 0.1 per single case.
