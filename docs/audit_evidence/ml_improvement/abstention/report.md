# Abstention-rule experiment (finding classifier)

Generated 2026-10-15T19:33:18.097048+00:00. Offline only: production thresholds, checkpoints, API and UI are unchanged.

## Baseline (production, unchanged)

* Rule: abstain if normalised entropy `H(p) >= 0.39660`, `H(p) = -sum_k p_k ln p_k / ln K, K=4`; source: Data/reports/uncertainty_thresholds.json (calibration split, Youden's J).
* Only entropy causes an abstention. Flip disagreement (>= 0.0762), weak detection, unstable masks and numbering flags mark a region for review but never withhold the class.
* Models: detection `dentex_teeth_detection_v1` (a68ce4884066), classification `dentex_findings_classification_v1` (5aa878e1fc9e).

## Data and leakage control

| Split | Role | Radiographs | Findings | Matched to a detector box (population `det`) | Unlabelled tooth boxes |
|---|---|---:|---:|---:|---:|
| calibration | tuning (rule selection) | 64 | 324 | 318 (Caries 206, Deep Caries 42, Impacted 54, Periapical Lesion 16) | 534 |
| val | confirmation only | 65 | 331 | 323 (Caries 203, Deep Caries 41, Impacted 72, Periapical Lesion 7) | 584 |

The test split is never read. Validation also selected the classifier's best epoch, so its absolute values are slightly optimistic for every rule alike. Unlabelled tooth boxes have no finding label: they are not assumed healthy and are never counted as false positives; only the share that a rule names a class for is reported.

## Acceptance criteria (fixed before the run)

C1 coverage gain >= +0.10 (calibration) / +0.05 (validation); C2 risk increase <= +0.02; C3 Deep Caries and Periapical Lesion precision drop <= 0.05 and end-to-end recall not lower; C4 end-to-end macro-F1 >= baseline - 0.01; C5 (validation) bootstrap 95% upper bound of the risk increase <= 0.05. Candidate = highest calibration coverage among rules passing C1–C4 on calibration; recommended only if it also passes C1–C5 on validation.

Note on the analysis code: the first analysis run compared the limits without a floating-point tolerance, so a precision drop of exactly 0.05 (0.80 → 0.75, one crop) counted as a failure. The limits are inclusive by definition; the comparison was corrected (tolerance 1e-9) and the analysis re-run. The criteria values themselves were not changed.

## Results — calibration split, detector crops (`det`)

| Rule | Accepted | Abstained | Coverage | Risk | Macro P | Macro R (all) | Macro F1 (accepted) | Macro F1 (all) | DC P / R(all) / F1(all) | PL P / R(all) / F1(all) | Unlabelled named | C1–C4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|
| **abstain if H >= 0.3966** | 161 (51%) | 157 (49%) | 0.506 | 0.093 | 0.845 | 0.463 | 0.811 | 0.570 | 0.71 / 0.12 / 0.20 | 0.80 / 0.50 / 0.62 | 201/534 (38%) | **baseline** |
| abstain if H >= 0.3000 | 118 (37%) | 200 (63%) | 0.371 | 0.051 | 0.887 | 0.394 | 0.889 | 0.505 | 0.75 / 0.07 / 0.13 | 0.88 / 0.44 / 0.58 | 147/534 (28%) | fail: C1,C3,C4 |
| abstain if H >= 0.3500 | 135 (42%) | 183 (58%) | 0.425 | 0.067 | 0.870 | 0.420 | 0.852 | 0.527 | 0.80 / 0.10 / 0.17 | 0.78 / 0.44 / 0.56 | 176/534 (33%) | fail: C1,C3,C4 |
| abstain if H >= 0.4500 | 182 (57%) | 136 (43%) | 0.572 | 0.099 | 0.832 | 0.493 | 0.805 | 0.597 | 0.67 / 0.14 / 0.24 | 0.80 / 0.50 / 0.62 | 244/534 (46%) | fail: C1 |
| abstain if H >= 0.5000 | 206 (65%) | 112 (35%) | 0.648 | 0.112 | 0.777 | 0.534 | 0.776 | 0.615 | 0.55 / 0.14 / 0.23 | 0.69 / 0.56 / 0.62 | 284/534 (53%) | fail: C3 |
| abstain if H >= 0.5500 | 227 (71%) | 91 (29%) | 0.714 | 0.132 | 0.743 | 0.565 | 0.754 | 0.633 | 0.40 / 0.14 / 0.21 | 0.71 / 0.62 / 0.67 | 348/534 (65%) | fail: C2,C3 |
| abstain if H >= 0.6000 | 246 (77%) | 72 (23%) | 0.774 | 0.130 | 0.738 | 0.586 | 0.750 | 0.645 | 0.38 / 0.14 / 0.21 | 0.71 / 0.62 / 0.67 | 392/534 (73%) | fail: C2,C3 |
| abstain if H >= 0.6500 | 264 (83%) | 54 (17%) | 0.830 | 0.136 | 0.736 | 0.611 | 0.750 | 0.662 | 0.37 / 0.17 / 0.23 | 0.71 / 0.62 / 0.67 | 432/534 (81%) | fail: C2,C3 |
| abstain if H >= 0.7000 | 282 (89%) | 36 (11%) | 0.887 | 0.142 | 0.747 | 0.642 | 0.758 | 0.685 | 0.45 / 0.24 / 0.31 | 0.71 / 0.62 / 0.67 | 474/534 (89%) | fail: C2,C3 |
| abstain if H >= 0.7500 | 294 (92%) | 24 (8%) | 0.925 | 0.156 | 0.752 | 0.659 | 0.750 | 0.697 | 0.50 / 0.29 / 0.36 | 0.71 / 0.62 / 0.67 | 508/534 (95%) | fail: C2,C3 |
| abstain if H >= 0.8000 | 310 (97%) | 8 (3%) | 0.975 | 0.177 | 0.717 | 0.680 | 0.709 | 0.694 | 0.50 / 0.33 / 0.40 | 0.59 / 0.62 / 0.61 | 528/534 (99%) | fail: C2,C3 |
| abstain if H >= 0.9000 | 317 (100%) | 1 (0%) | 0.997 | 0.189 | 0.704 | 0.690 | 0.698 | 0.694 | 0.47 / 0.33 / 0.39 | 0.59 / 0.62 / 0.61 | 532/534 (100%) | fail: C2,C3 |
| abstain if H >= 1.0100 | 318 (100%) | 0 (0%) | 1.000 | 0.192 | 0.700 | 0.690 | 0.692 | 0.692 | 0.45 / 0.33 / 0.38 | 0.59 / 0.62 / 0.61 | 534/534 (100%) | fail: C2,C3 |
| abstain if max p < 0.4000 | 316 (99%) | 2 (1%) | 0.994 | 0.187 | 0.705 | 0.690 | 0.699 | 0.694 | 0.47 / 0.33 / 0.39 | 0.59 / 0.62 / 0.61 | 528/534 (99%) | fail: C2,C3 |
| abstain if max p < 0.4500 | 305 (96%) | 13 (4%) | 0.959 | 0.170 | 0.733 | 0.677 | 0.723 | 0.700 | 0.48 / 0.31 / 0.38 | 0.67 / 0.62 / 0.65 | 517/534 (97%) | fail: C2,C3 |
| abstain if max p < 0.5000 | 295 (93%) | 23 (7%) | 0.928 | 0.163 | 0.751 | 0.666 | 0.742 | 0.702 | 0.50 / 0.31 / 0.38 | 0.71 / 0.62 / 0.67 | 488/534 (91%) | fail: C2,C3 |
| abstain if max p < 0.5500 | 278 (87%) | 40 (13%) | 0.874 | 0.151 | 0.748 | 0.635 | 0.747 | 0.680 | 0.48 / 0.24 / 0.32 | 0.71 / 0.62 / 0.67 | 449/534 (84%) | fail: C2,C3 |
| abstain if max p < 0.6000 | 259 (81%) | 59 (19%) | 0.814 | 0.139 | 0.757 | 0.610 | 0.754 | 0.667 | 0.44 / 0.19 / 0.27 | 0.77 / 0.62 / 0.69 | 415/534 (78%) | fail: C2,C3 |
| abstain if max p < 0.6500 | 238 (75%) | 80 (25%) | 0.748 | 0.130 | 0.770 | 0.571 | 0.763 | 0.643 | 0.50 / 0.17 / 0.25 | 0.75 / 0.56 / 0.64 | 380/534 (71%) | fail: C2,C3 |
| abstain if max p < 0.7000 | 217 (68%) | 101 (32%) | 0.682 | 0.111 | 0.798 | 0.549 | 0.777 | 0.629 | 0.60 / 0.14 / 0.23 | 0.75 / 0.56 / 0.64 | 343/534 (64%) | fail: C3 |
| abstain if max p < 0.7500 | 198 (62%) | 120 (38%) | 0.623 | 0.096 | 0.841 | 0.529 | 0.801 | 0.620 | 0.75 / 0.14 / 0.24 | 0.75 / 0.56 / 0.64 | 283/534 (53%) | pass |
| abstain if max p < 0.8000 | 172 (54%) | 146 (46%) | 0.541 | 0.093 | 0.833 | 0.474 | 0.792 | 0.574 | 0.67 / 0.10 / 0.17 | 0.80 / 0.50 / 0.62 | 231/534 (43%) | fail: C1,C3 |
| abstain if max p < 0.8500 | 132 (42%) | 186 (58%) | 0.415 | 0.061 | 0.882 | 0.412 | 0.850 | 0.522 | 0.75 / 0.07 / 0.13 | 0.88 / 0.44 / 0.58 | 181/534 (34%) | fail: C1,C3,C4 |
| abstain if p1-p2 < 0.0500 | 309 (97%) | 9 (3%) | 0.972 | 0.188 | 0.703 | 0.674 | 0.694 | 0.684 | 0.46 / 0.31 / 0.37 | 0.59 / 0.62 / 0.61 | 518/534 (97%) | fail: C2,C3 |
| abstain if p1-p2 < 0.1000 | 300 (94%) | 18 (6%) | 0.943 | 0.177 | 0.722 | 0.669 | 0.711 | 0.691 | 0.48 / 0.31 / 0.38 | 0.62 / 0.62 / 0.62 | 498/534 (93%) | fail: C2,C3 |
| abstain if p1-p2 < 0.1500 | 290 (91%) | 28 (9%) | 0.912 | 0.169 | 0.733 | 0.654 | 0.719 | 0.687 | 0.48 / 0.29 / 0.36 | 0.67 / 0.62 / 0.65 | 474/534 (89%) | fail: C2,C3 |
| abstain if p1-p2 < 0.2000 | 285 (90%) | 33 (10%) | 0.896 | 0.158 | 0.752 | 0.653 | 0.739 | 0.694 | 0.50 / 0.29 / 0.36 | 0.71 / 0.62 / 0.67 | 452/534 (85%) | fail: C2,C3 |
| abstain if p1-p2 < 0.2500 | 271 (85%) | 47 (15%) | 0.852 | 0.151 | 0.771 | 0.636 | 0.760 | 0.690 | 0.52 / 0.26 / 0.35 | 0.77 / 0.62 / 0.69 | 428/534 (80%) | fail: C2,C3 |
| abstain if p1-p2 < 0.3000 | 253 (80%) | 65 (20%) | 0.796 | 0.142 | 0.776 | 0.598 | 0.762 | 0.666 | 0.56 / 0.24 / 0.33 | 0.75 / 0.56 / 0.64 | 416/534 (78%) | fail: C2,C3 |
| abstain if p1-p2 < 0.3500 | 245 (77%) | 73 (23%) | 0.770 | 0.143 | 0.763 | 0.580 | 0.751 | 0.648 | 0.50 / 0.19 / 0.28 | 0.75 / 0.56 / 0.64 | 401/534 (75%) | fail: C2,C3 |
| abstain if p1-p2 < 0.4000 | 235 (74%) | 83 (26%) | 0.739 | 0.132 | 0.782 | 0.572 | 0.762 | 0.646 | 0.57 / 0.19 / 0.29 | 0.75 / 0.56 / 0.64 | 375/534 (70%) | fail: C2,C3 |
| abstain if p1-p2 < 0.5000 | 212 (67%) | 106 (33%) | 0.667 | 0.113 | 0.832 | 0.543 | 0.777 | 0.626 | 0.75 / 0.14 / 0.24 | 0.75 / 0.56 / 0.64 | 323/534 (60%) | fail: C2 |
| abstain if p1-p2 < 0.6000 | 183 (58%) | 135 (42%) | 0.575 | 0.087 | 0.851 | 0.513 | 0.811 | 0.609 | 0.71 / 0.12 / 0.20 | 0.82 / 0.56 / 0.67 | 261/534 (49%) | fail: C1 |

## Results — val split, detector crops (`det`)

| Rule | Accepted | Abstained | Coverage | Risk | Macro P | Macro R (all) | Macro F1 (accepted) | Macro F1 (all) | DC P / R(all) / F1(all) | PL P / R(all) / F1(all) | Unlabelled named | C1–C4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|
| **abstain if H >= 0.3966** | 168 (52%) | 155 (48%) | 0.520 | 0.119 | 0.724 | 0.449 | 0.725 | 0.518 | 0.57 / 0.10 / 0.17 | 0.50 / 0.43 / 0.46 | 250/584 (43%) | **baseline** |
| abstain if H >= 0.3000 | 132 (41%) | 191 (59%) | 0.409 | 0.083 | 0.818 | 0.406 | 0.783 | 0.488 | 0.67 / 0.05 / 0.09 | 0.75 / 0.43 / 0.55 | 164/584 (28%) |  |
| abstain if H >= 0.3500 | 147 (46%) | 176 (54%) | 0.455 | 0.095 | 0.798 | 0.425 | 0.762 | 0.502 | 0.75 / 0.07 / 0.13 | 0.60 / 0.43 / 0.50 | 210/584 (36%) |  |
| abstain if H >= 0.4500 | 195 (60%) | 128 (40%) | 0.604 | 0.123 | 0.740 | 0.494 | 0.744 | 0.567 | 0.64 / 0.17 / 0.27 | 0.50 / 0.43 / 0.46 | 304/584 (52%) |  |
| abstain if H >= 0.5000 | 211 (65%) | 112 (35%) | 0.653 | 0.118 | 0.733 | 0.522 | 0.735 | 0.584 | 0.67 / 0.20 / 0.30 | 0.43 / 0.43 / 0.43 | 347/584 (59%) |  |
| abstain if H >= 0.5500 | 240 (74%) | 83 (26%) | 0.743 | 0.142 | 0.684 | 0.586 | 0.703 | 0.611 | 0.50 / 0.22 / 0.31 | 0.40 / 0.57 / 0.47 | 398/584 (68%) |  |
| abstain if H >= 0.6000 | 258 (80%) | 65 (20%) | 0.799 | 0.147 | 0.676 | 0.613 | 0.699 | 0.626 | 0.50 / 0.27 / 0.35 | 0.36 / 0.57 / 0.44 | 441/584 (76%) |  |
| abstain if H >= 0.6500 | 275 (85%) | 48 (15%) | 0.851 | 0.156 | 0.660 | 0.627 | 0.674 | 0.623 | 0.50 / 0.27 / 0.35 | 0.31 / 0.57 / 0.40 | 496/584 (85%) |  |
| abstain if H >= 0.7000 | 287 (89%) | 36 (11%) | 0.889 | 0.160 | 0.668 | 0.660 | 0.686 | 0.649 | 0.54 / 0.37 / 0.43 | 0.31 / 0.57 / 0.40 | 535/584 (92%) |  |
| abstain if H >= 0.7500 | 303 (94%) | 20 (6%) | 0.938 | 0.175 | 0.653 | 0.671 | 0.668 | 0.649 | 0.50 / 0.37 / 0.42 | 0.31 / 0.57 / 0.40 | 563/584 (96%) |  |
| abstain if H >= 0.8000 | 318 (98%) | 5 (2%) | 0.985 | 0.182 | 0.646 | 0.686 | 0.658 | 0.654 | 0.48 / 0.37 / 0.42 | 0.31 / 0.57 / 0.40 | 578/584 (99%) |  |
| abstain if H >= 0.9000 | 322 (100%) | 1 (0%) | 0.997 | 0.186 | 0.640 | 0.688 | 0.651 | 0.650 | 0.48 / 0.37 / 0.42 | 0.29 / 0.57 / 0.38 | 584/584 (100%) |  |
| abstain if H >= 1.0100 | 323 (100%) | 0 (0%) | 1.000 | 0.189 | 0.636 | 0.688 | 0.649 | 0.649 | 0.47 / 0.37 / 0.41 | 0.29 / 0.57 / 0.38 | 584/584 (100%) |  |
| abstain if max p < 0.4000 | 320 (99%) | 3 (1%) | 0.991 | 0.184 | 0.645 | 0.687 | 0.657 | 0.654 | 0.48 / 0.37 / 0.42 | 0.31 / 0.57 / 0.40 | 583/584 (100%) |  |
| abstain if max p < 0.4500 | 310 (96%) | 13 (4%) | 0.960 | 0.181 | 0.647 | 0.678 | 0.662 | 0.651 | 0.48 / 0.37 / 0.42 | 0.31 / 0.57 / 0.40 | 574/584 (98%) |  |
| abstain if max p < 0.5000 | 299 (93%) | 24 (7%) | 0.926 | 0.171 | 0.659 | 0.664 | 0.671 | 0.649 | 0.50 / 0.34 / 0.41 | 0.33 / 0.57 / 0.42 | 551/584 (94%) |  |
| abstain if max p < 0.5500 | 283 (88%) | 40 (12%) | 0.876 | 0.148 | 0.681 | 0.645 | 0.688 | 0.643 | 0.57 / 0.29 / 0.39 | 0.33 / 0.57 / 0.42 | 524/584 (90%) |  |
| abstain if max p < 0.6000 | 265 (82%) | 58 (18%) | 0.820 | 0.128 | 0.718 | 0.631 | 0.725 | 0.653 | 0.63 / 0.29 / 0.40 | 0.40 / 0.57 / 0.47 | 483/584 (83%) |  |
| abstain if max p < 0.6500 | 242 (75%) | 81 (25%) | 0.749 | 0.128 | 0.709 | 0.562 | 0.710 | 0.609 | 0.62 / 0.24 / 0.35 | 0.38 / 0.43 / 0.40 | 446/584 (76%) |  |
| abstain if max p < 0.7000 | 224 (69%) | 99 (31%) | 0.693 | 0.125 | 0.719 | 0.534 | 0.724 | 0.591 | 0.62 / 0.20 / 0.30 | 0.43 / 0.43 / 0.43 | 401/584 (69%) |  |
| abstain if max p < 0.7500 | 206 (64%) | 117 (36%) | 0.638 | 0.121 | 0.724 | 0.511 | 0.725 | 0.571 | 0.64 / 0.17 / 0.27 | 0.43 / 0.43 / 0.43 | 345/584 (59%) |  |
| abstain if max p < 0.8000 | 181 (56%) | 142 (44%) | 0.560 | 0.116 | 0.739 | 0.470 | 0.736 | 0.541 | 0.62 / 0.12 / 0.20 | 0.50 / 0.43 / 0.46 | 295/584 (51%) |  |
| abstain if max p < 0.8500 | 154 (48%) | 169 (52%) | 0.477 | 0.091 | 0.766 | 0.434 | 0.764 | 0.512 | 0.60 / 0.07 / 0.13 | 0.60 / 0.43 / 0.50 | 211/584 (36%) |  |
| abstain if p1-p2 < 0.0500 | 306 (95%) | 17 (5%) | 0.947 | 0.170 | 0.654 | 0.669 | 0.666 | 0.649 | 0.48 / 0.32 / 0.38 | 0.33 / 0.57 / 0.42 | 571/584 (98%) |  |
| abstain if p1-p2 < 0.1000 | 300 (93%) | 23 (7%) | 0.929 | 0.167 | 0.663 | 0.664 | 0.670 | 0.649 | 0.52 / 0.32 / 0.39 | 0.33 / 0.57 / 0.42 | 556/584 (95%) |  |
| abstain if p1-p2 < 0.1500 | 293 (91%) | 30 (9%) | 0.907 | 0.164 | 0.669 | 0.655 | 0.674 | 0.646 | 0.54 / 0.32 / 0.40 | 0.33 / 0.57 / 0.42 | 544/584 (93%) |  |
| abstain if p1-p2 < 0.2000 | 282 (87%) | 41 (13%) | 0.873 | 0.156 | 0.678 | 0.642 | 0.682 | 0.640 | 0.57 / 0.29 / 0.39 | 0.33 / 0.57 / 0.42 | 524/584 (90%) |  |
| abstain if p1-p2 < 0.2500 | 273 (85%) | 50 (15%) | 0.845 | 0.143 | 0.687 | 0.602 | 0.693 | 0.628 | 0.60 / 0.29 / 0.39 | 0.33 / 0.43 / 0.38 | 506/584 (87%) |  |
| abstain if p1-p2 < 0.3000 | 260 (80%) | 63 (20%) | 0.805 | 0.131 | 0.706 | 0.593 | 0.707 | 0.627 | 0.67 / 0.29 / 0.41 | 0.33 / 0.43 / 0.38 | 487/584 (83%) |  |
| abstain if p1-p2 < 0.3500 | 248 (77%) | 75 (23%) | 0.768 | 0.129 | 0.716 | 0.578 | 0.720 | 0.624 | 0.67 / 0.29 / 0.41 | 0.38 / 0.43 / 0.40 | 464/584 (79%) |  |
| abstain if p1-p2 < 0.4000 | 238 (74%) | 85 (26%) | 0.737 | 0.130 | 0.713 | 0.562 | 0.715 | 0.612 | 0.65 / 0.27 / 0.38 | 0.38 / 0.43 / 0.40 | 442/584 (76%) |  |
| abstain if p1-p2 < 0.5000 | 215 (67%) | 108 (33%) | 0.666 | 0.121 | 0.732 | 0.525 | 0.731 | 0.586 | 0.67 / 0.20 / 0.30 | 0.43 / 0.43 / 0.43 | 385/584 (66%) |  |
| abstain if p1-p2 < 0.6000 | 191 (59%) | 132 (41%) | 0.591 | 0.115 | 0.733 | 0.489 | 0.728 | 0.552 | 0.67 / 0.15 / 0.24 | 0.43 / 0.43 / 0.43 | 329/584 (56%) |  |

### calibration split, ground-truth crops (`gt`, secondary)

| Rule | Coverage | Risk | Macro F1 (all) | DC R(all) | PL R(all) |
|---|---:|---:|---:|---:|---:|
| abstain if H >= 0.3966 | 0.500 | 0.080 | 0.593 | 0.19 | 0.50 |
| abstain if H >= 0.3000 | 0.395 | 0.078 | 0.546 | 0.15 | 0.50 |
| abstain if H >= 0.3500 | 0.448 | 0.083 | 0.572 | 0.17 | 0.50 |
| abstain if H >= 0.4500 | 0.583 | 0.095 | 0.615 | 0.19 | 0.50 |
| abstain if H >= 0.5000 | 0.670 | 0.106 | 0.653 | 0.26 | 0.50 |
| abstain if H >= 0.5500 | 0.738 | 0.121 | 0.667 | 0.28 | 0.50 |
| abstain if H >= 0.6000 | 0.793 | 0.132 | 0.694 | 0.32 | 0.56 |
| abstain if H >= 0.6500 | 0.855 | 0.130 | 0.715 | 0.38 | 0.56 |
| abstain if H >= 0.7000 | 0.904 | 0.143 | 0.727 | 0.45 | 0.56 |
| abstain if H >= 0.7500 | 0.935 | 0.158 | 0.727 | 0.45 | 0.56 |
| abstain if H >= 0.8000 | 0.985 | 0.166 | 0.761 | 0.49 | 0.69 |
| abstain if H >= 0.9000 | 0.997 | 0.170 | 0.760 | 0.49 | 0.69 |
| abstain if H >= 1.0100 | 1.000 | 0.170 | 0.761 | 0.49 | 0.69 |
| abstain if max p < 0.4000 | 1.000 | 0.170 | 0.761 | 0.49 | 0.69 |
| abstain if max p < 0.4500 | 0.975 | 0.161 | 0.749 | 0.47 | 0.62 |
| abstain if max p < 0.5000 | 0.932 | 0.156 | 0.741 | 0.45 | 0.62 |
| abstain if max p < 0.5500 | 0.883 | 0.150 | 0.702 | 0.40 | 0.50 |
| abstain if max p < 0.6000 | 0.818 | 0.143 | 0.684 | 0.34 | 0.50 |
| abstain if max p < 0.6500 | 0.769 | 0.120 | 0.671 | 0.28 | 0.50 |
| abstain if max p < 0.7000 | 0.685 | 0.104 | 0.652 | 0.23 | 0.50 |
| abstain if max p < 0.7500 | 0.630 | 0.103 | 0.638 | 0.23 | 0.50 |
| abstain if max p < 0.8000 | 0.559 | 0.099 | 0.614 | 0.19 | 0.50 |
| abstain if max p < 0.8500 | 0.454 | 0.082 | 0.576 | 0.17 | 0.50 |
| abstain if p1-p2 < 0.0500 | 0.978 | 0.158 | 0.755 | 0.49 | 0.62 |
| abstain if p1-p2 < 0.1000 | 0.944 | 0.160 | 0.732 | 0.47 | 0.56 |
| abstain if p1-p2 < 0.1500 | 0.920 | 0.161 | 0.721 | 0.43 | 0.56 |
| abstain if p1-p2 < 0.2000 | 0.880 | 0.161 | 0.698 | 0.40 | 0.50 |
| abstain if p1-p2 < 0.2500 | 0.827 | 0.149 | 0.686 | 0.34 | 0.50 |
| abstain if p1-p2 < 0.3000 | 0.793 | 0.132 | 0.678 | 0.30 | 0.50 |
| abstain if p1-p2 < 0.3500 | 0.775 | 0.127 | 0.665 | 0.26 | 0.50 |
| abstain if p1-p2 < 0.4000 | 0.750 | 0.119 | 0.657 | 0.23 | 0.50 |
| abstain if p1-p2 < 0.5000 | 0.670 | 0.115 | 0.640 | 0.23 | 0.50 |
| abstain if p1-p2 < 0.6000 | 0.593 | 0.104 | 0.633 | 0.23 | 0.50 |

### val split, ground-truth crops (`gt`, secondary)

| Rule | Coverage | Risk | Macro F1 (all) | DC R(all) | PL R(all) |
|---|---:|---:|---:|---:|---:|
| abstain if H >= 0.3966 | 0.495 | 0.104 | 0.543 | 0.18 | 0.44 |
| abstain if H >= 0.3000 | 0.372 | 0.073 | 0.454 | 0.13 | 0.22 |
| abstain if H >= 0.3500 | 0.435 | 0.097 | 0.529 | 0.16 | 0.44 |
| abstain if H >= 0.4500 | 0.577 | 0.120 | 0.561 | 0.20 | 0.44 |
| abstain if H >= 0.5000 | 0.637 | 0.123 | 0.615 | 0.22 | 0.67 |
| abstain if H >= 0.5500 | 0.737 | 0.139 | 0.657 | 0.33 | 0.67 |
| abstain if H >= 0.6000 | 0.801 | 0.143 | 0.677 | 0.33 | 0.78 |
| abstain if H >= 0.6500 | 0.861 | 0.147 | 0.690 | 0.36 | 0.78 |
| abstain if H >= 0.7000 | 0.903 | 0.154 | 0.697 | 0.38 | 0.78 |
| abstain if H >= 0.7500 | 0.940 | 0.164 | 0.702 | 0.40 | 0.78 |
| abstain if H >= 0.8000 | 0.982 | 0.175 | 0.706 | 0.42 | 0.78 |
| abstain if H >= 0.9000 | 1.000 | 0.175 | 0.718 | 0.47 | 0.78 |
| abstain if H >= 1.0100 | 1.000 | 0.175 | 0.718 | 0.47 | 0.78 |
| abstain if max p < 0.4000 | 0.994 | 0.173 | 0.715 | 0.44 | 0.78 |
| abstain if max p < 0.4500 | 0.967 | 0.166 | 0.711 | 0.42 | 0.78 |
| abstain if max p < 0.5000 | 0.934 | 0.159 | 0.715 | 0.42 | 0.78 |
| abstain if max p < 0.5500 | 0.885 | 0.150 | 0.693 | 0.40 | 0.67 |
| abstain if max p < 0.6000 | 0.801 | 0.136 | 0.673 | 0.33 | 0.67 |
| abstain if max p < 0.6500 | 0.764 | 0.134 | 0.662 | 0.31 | 0.67 |
| abstain if max p < 0.7000 | 0.701 | 0.125 | 0.625 | 0.27 | 0.56 |
| abstain if max p < 0.7500 | 0.598 | 0.106 | 0.611 | 0.27 | 0.56 |
| abstain if max p < 0.8000 | 0.535 | 0.102 | 0.572 | 0.22 | 0.44 |
| abstain if max p < 0.8500 | 0.435 | 0.097 | 0.472 | 0.16 | 0.22 |
| abstain if p1-p2 < 0.0500 | 0.964 | 0.166 | 0.720 | 0.44 | 0.78 |
| abstain if p1-p2 < 0.1000 | 0.931 | 0.159 | 0.720 | 0.44 | 0.78 |
| abstain if p1-p2 < 0.1500 | 0.906 | 0.153 | 0.701 | 0.42 | 0.67 |
| abstain if p1-p2 < 0.2000 | 0.870 | 0.149 | 0.689 | 0.38 | 0.67 |
| abstain if p1-p2 < 0.2500 | 0.834 | 0.145 | 0.679 | 0.36 | 0.67 |
| abstain if p1-p2 < 0.3000 | 0.801 | 0.140 | 0.672 | 0.33 | 0.67 |
| abstain if p1-p2 < 0.3500 | 0.782 | 0.139 | 0.648 | 0.31 | 0.56 |
| abstain if p1-p2 < 0.4000 | 0.740 | 0.122 | 0.640 | 0.29 | 0.56 |
| abstain if p1-p2 < 0.5000 | 0.656 | 0.115 | 0.622 | 0.27 | 0.56 |
| abstain if p1-p2 < 0.6000 | 0.577 | 0.110 | 0.596 | 0.22 | 0.56 |

## Confusion matrices and per-class results (detector crops)

FP = accepted predictions of the class whose label differs; FN = crops of the class not correctly accepted (wrong class, abstained or missing).

**calibration — baseline** — abstain if H >= 0.3966

| true \ predicted | Caries | Deep Caries | Impacted | Periapical Lesion | ABSTAINED | MISSING |
|---|---:|---:|---:|---:|---:|---:|
| Caries | 90 | 2 | 2 | 2 | 110 | 0 |
| Deep Caries | 8 | 5 | 0 | 0 | 29 | 0 |
| Impacted | 0 | 0 | 43 | 0 | 11 | 0 |
| Periapical Lesion | 1 | 0 | 0 | 8 | 7 | 0 |

| Class | Support | TP | FP | FN | Precision | Recall (accepted) | Recall (all) | F1 (all) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Caries | 206 | 90 | 9 | 116 | 0.909 | 0.938 | 0.437 | 0.590 |
| Deep Caries | 42 | 5 | 2 | 37 | 0.714 | 0.385 | 0.119 | 0.204 |
| Impacted | 54 | 43 | 2 | 11 | 0.956 | 1.000 | 0.796 | 0.869 |
| Periapical Lesion | 16 | 8 | 2 | 8 | 0.800 | 0.889 | 0.500 | 0.615 |

**calibration — candidate** — abstain if max p < 0.7500

| true \ predicted | Caries | Deep Caries | Impacted | Periapical Lesion | ABSTAINED | MISSING |
|---|---:|---:|---:|---:|---:|---:|
| Caries | 119 | 2 | 2 | 3 | 80 | 0 |
| Deep Caries | 11 | 6 | 0 | 0 | 25 | 0 |
| Impacted | 0 | 0 | 45 | 0 | 9 | 0 |
| Periapical Lesion | 1 | 0 | 0 | 9 | 6 | 0 |

| Class | Support | TP | FP | FN | Precision | Recall (accepted) | Recall (all) | F1 (all) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Caries | 206 | 119 | 12 | 87 | 0.908 | 0.944 | 0.578 | 0.706 |
| Deep Caries | 42 | 6 | 2 | 36 | 0.750 | 0.353 | 0.143 | 0.240 |
| Impacted | 54 | 45 | 2 | 9 | 0.957 | 1.000 | 0.833 | 0.891 |
| Periapical Lesion | 16 | 9 | 3 | 7 | 0.750 | 0.900 | 0.562 | 0.643 |

**val — baseline** — abstain if H >= 0.3966

| true \ predicted | Caries | Deep Caries | Impacted | Periapical Lesion | ABSTAINED | MISSING |
|---|---:|---:|---:|---:|---:|---:|
| Caries | 77 | 2 | 4 | 3 | 117 | 0 |
| Deep Caries | 10 | 4 | 0 | 0 | 27 | 0 |
| Impacted | 0 | 1 | 64 | 0 | 7 | 0 |
| Periapical Lesion | 0 | 0 | 0 | 3 | 4 | 0 |

| Class | Support | TP | FP | FN | Precision | Recall (accepted) | Recall (all) | F1 (all) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Caries | 203 | 77 | 10 | 126 | 0.885 | 0.895 | 0.379 | 0.531 |
| Deep Caries | 41 | 4 | 3 | 37 | 0.571 | 0.286 | 0.098 | 0.167 |
| Impacted | 72 | 64 | 4 | 8 | 0.941 | 0.985 | 0.889 | 0.914 |
| Periapical Lesion | 7 | 3 | 3 | 4 | 0.500 | 1.000 | 0.429 | 0.462 |

**val — candidate** — abstain if max p < 0.7500

| true \ predicted | Caries | Deep Caries | Impacted | Periapical Lesion | ABSTAINED | MISSING |
|---|---:|---:|---:|---:|---:|---:|
| Caries | 104 | 3 | 4 | 3 | 89 | 0 |
| Deep Caries | 13 | 7 | 0 | 1 | 20 | 0 |
| Impacted | 0 | 1 | 67 | 0 | 4 | 0 |
| Periapical Lesion | 0 | 0 | 0 | 3 | 4 | 0 |

| Class | Support | TP | FP | FN | Precision | Recall (accepted) | Recall (all) | F1 (all) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Caries | 203 | 104 | 13 | 99 | 0.889 | 0.912 | 0.512 | 0.650 |
| Deep Caries | 41 | 7 | 4 | 34 | 0.636 | 0.333 | 0.171 | 0.269 |
| Impacted | 72 | 67 | 4 | 5 | 0.944 | 0.985 | 0.931 | 0.937 |
| Periapical Lesion | 7 | 3 | 4 | 4 | 0.429 | 1.000 | 0.429 | 0.429 |

## Selection

Rules passing C1–C4 on calibration: abstain if max p < 0.7500.

Candidate: **abstain if max p < 0.7500**. Validation checks: C1_coverage_gain pass, C2_risk_increase pass, C3_minority_classes FAIL, C4_macro_f1 pass, C5_bootstrap_risk_upper_bound pass.
Bootstrap (validation, 2000 resamples) risk difference candidate − baseline: mean +0.003, 95% CI [-0.018, +0.026].

## Recommendation

**keep the production baseline: the calibration candidate 'abstain if max p < 0.7500' failed on validation (C3_minority_classes).**

## Limitations

* Risk can only be measured on teeth that carry a DENTEX finding label. On teeth without a label (most teeth in a radiograph) the effect of a looser rule is unknown: the extra named classes there may be false alarms, and the ‘Unlabelled named’ column shows how many more teeth would get a class. The classifier has no healthy class, so this cannot be resolved without new labels.
* Deep Caries and Periapical Lesion have few examples per split; their precision and recall move by large steps with one crop.
* One model, one seed, one dataset; validation also selected the classifier's epoch. No test-split confirmation (by design).
* Nothing here is deployed. Changing the production threshold requires review and explicit approval, then an update of Data/reports/uncertainty_thresholds.json.

## Reproduce

```
.venv\Scripts\python.exe scripts\abstention_threshold_experiment.py collect   # GPU, ~1-2 min, caches probabilities
.venv\Scripts\python.exe scripts\abstention_threshold_experiment.py analyze   # CPU, writes report.json / report.md
.venv\Scripts\python.exe -m pytest tests\test_abstention_rules.py -q
```
