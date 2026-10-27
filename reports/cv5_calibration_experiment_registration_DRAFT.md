# Calibration experiment: registration DRAFT (NOT REGISTERED, NOT RUN)

Date 2026-10-25. It needs owner approval as a separate amendment. Until then, nothing in it may be run on CV5 data.

## 1. Background (verified)
* **Current calibration:** CV5-BASE run 1 reports ECE (10 equal-width bins, top-label) of 0.107 on detector boxes and 0.109 on GT
  boxes. Source: `kaggle/artifacts_cv5_run1/cv5_results.json` → `summary/*/ece_10bin`, definition in `kaggle/dentamind_kaggle.report`.
* **What it was computed on:** the pooled out-of-fold softmax outputs of each seed, then averaged over seeds. No calibration was
  fitted.
* **What is missing:** inner-validation predictions were **not archived**, so a temperature cannot be fitted from the archive without
  leakage. Fitting on held-out folds, the calibration split or the test split is excluded.

## 2. Why this cannot be a CV5 "candidate"
Temperature scaling divides the logits by a positive scalar, so the predicted class does not change. Macro-F1, and therefore the
CV5 primary checks P-A to P-D, are identical by construction (verified in `tests/test_temperature_scaling.py`).

The experiment therefore needs **its own endpoints**, below, and must not be reported as an accuracy improvement. It does not
consume the 15-candidate budget, which is defined for discrimination candidates. The owner must confirm this in the amendment.

## 3. Design (to be frozen at registration)
* **Models:** the 25 archived CV5-BASE checkpoints (5 folds × 5 seeds). Their hashes are in `checkpoint_manifest.json`; the files are
  in the Kaggle notebook output, and their availability must be checked. No retraining.
* **Fitting partition:**
  - each fold's inner-validation split, which is group-disjoint and already defined in `fold_plan.json`;
  - inference only: the inner-validation logits are re-predicted with the archived checkpoint;
  - one temperature per fold × seed, fitted with `src/dentexmodel/uncertainty/temperature.fit_per_fold`. This function refuses any
    other partition. The search runs over T in [0.05, 20] by NLL.
* **Evaluation:** the same held-out out-of-fold predictions as CV5-BASE, in the GT and detector-box settings.
* **Primary endpoint:** NLL (a proper scoring rule).
* **Secondary endpoints:** ECE (10 bins, identical definition), multiclass Brier score, reliability diagrams, and the fitted T per
  fold and seed.
* **Discrimination check:** macro-F1 and per-class metrics are reported to show they are unchanged.
* **Uncertainty:** the paired radiograph-level bootstrap of ΔNLL and ΔECE, using the CV5 resampling procedure (`default_rng(0)`,
  2,000 draws).
* **Decision rule** (proposed; the owner may change it **before** any run): calibration is called improved if the seed-mean ΔNLL < 0
  with a 95 % bootstrap upper bound < 0, **and** the seed-mean ΔECE < 0. Otherwise "not improved".
* **Reporting:** a calibration result, never "better classification".

## 4. Preconditions
1. The owner approves this registration with an approval record. The approval policy and tooling must be adopted first.
2. The archived CV5 checkpoints are confirmed to exist, by hash, in the Kaggle output.
3. A reviewed inference-only notebook is written. It loads the checkpoints, predicts the inner-validation and held-out crops, and
   archives the logits with SHA256SUMS. It must not modify the frozen generator; it is a separate notebook.
4. A Kaggle GPU session (inference only; well under 1 GPU-hour expected — **to be measured, not assumed**).

## 5. Prepared now
* `src/dentexmodel/uncertainty/temperature.py`: a deterministic fit, plus a guard that refuses fitting on non-inner partitions.
* `tests/test_temperature_scaling.py`: 4 tests on synthetic data. They check that a known T is recovered, that NLL and ECE decrease,
  that the arg-max is unchanged, and that held-out, test and calibration partitions are refused.
* Existing metric code is reused: `src/dentexmodel/uncertainty/calibration.py` (ECE, Brier, reliability bins).
