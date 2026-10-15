# Uncertainty, review and active learning - methods and measured results

Everything numeric below was measured on this machine on 2026-10-14 from the files named; nothing is simulated.

## 1. What is computed (`backend/services/pipeline.py`)

For each detected tooth region the pipeline links the numbering box, the segmentation mask and the classifier crop **by IoU matching and a content-derived
region id** (`image:hash(box rounded to 8 px, model version)`), never by list position, and computes:

| Signal | Definition | Needs | Range |
|---|---|---|---|
| entropy | normalised Shannon entropy of the classifier softmax over the 4 trained classes (divide by log 4) | classifier | 0 certain .. 1 uniform |
| flip disagreement | Jensen-Shannon divergence between the classifier on the crop and on its horizontal flip, divided by log 2 (**2 passes of ONE network; not an ensemble**) | classifier | 0..1 |
| mask instability | 1 - IoU between each mask and the mask predicted on the flipped image (flipped back); no counterpart = 1 | segmenter | 0..1 |
| detection instability | 1 - IoU of each box against its best match on the flipped image | detector | 0..1 |

Image-level values are means over regions. **Combined score** = weighted mean of the *available* signals among entropy (0.4), flip disagreement (0.4) and mask
instability (0.2), weights renormalised; detection instability is shown but excluded. A signal that cannot be computed is `unavailable` with a reason and is
never counted as 0 (unit-tested). Image-quality flags (blur, contrast, brightness, saturation) are stored separately and never mixed into the score.
Normalisation note: all four signals are scaled to 0-1 so they are comparable, but they are *not* on a common probabilistic scale.

Region flags: `high_entropy`, `unstable_under_flip`, `mask_unstable`, `no_matching_mask`, `low_detection_score`, `unassigned_tooth_number`,
`tooth_number_needs_review`, `not_found_on_flipped_image`. A region with `high_entropy` is **abstained** (no candidate class is named).

## 2. Do the signals flag errors? (`scripts/evaluate_uncertainty.py`, `Data/reports/uncertainty_evaluation.md`)

Classifier on ground-truth tooth crops; thresholds chosen on the **calibration** split, evaluated once on **test**.

| Split | n | Accuracy | ECE | Brier | AUROC entropy -> error | AUROC flip disagreement -> error |
|---|---:|---:|---:|---:|---:|---:|
| calibration | 324 | 0.830 | 0.071 | 0.277 | 0.721 | 0.709 |
| test | 354 | 0.785 | 0.048 | 0.291 | 0.768 | 0.745 |

Provisional thresholds: review if entropy >= 0.397; "unstable under flip" if flip disagreement >= 0.076 (90th percentile of calibration crops). On test the entropy flag
marks 54.2 % of crops; error rate 34.4 % among flagged vs 6.2 % among unflagged; 86.8 % of all errors are flagged. Flip-unstable crops (9.3 %) have an error rate of 48.5 % vs 18.7 %.
So the signals carry real information about the classifier's mistakes (AUROC about 0.75), but the thresholds are coarse, **provisional** and send many regions to review.
Temperature scaling (T = 0.95, fitted on calibration) changes test ECE 0.048 -> 0.036; it is **not applied**: displayed scores remain uncalibrated model scores.

## 3. Review workflow (`src/dentexmodel/annotation/reviews.py`)

Actions per region (confirm, correct class, reject, set tooth number, mark number unassigned) or per image (specialist review, unusable). Each record stores the image id,
region id, the **model output the reviewer saw** (class, score, uncertainty, flags, numbering status), model versions, reviewer, timestamp, notes and a revision number.
Identical resubmission is refused; a changed decision becomes a new revision and the old one stays in the history. Approval needs a named approver different from the reviewer.
Reviewer names are self-declared (stored as such); nothing is labelled expert-verified. Reviews on test/calibration/validation/labelled-train images are saved but flagged
`usable_for_training = false`; only approved reviews on pool/upload images can be exported or, via `use_approved_annotations`, enter a training run.

## 4. Active-learning experiment (`scripts/run_al_experiment.py`, `Data/reports/active_learning_experiment.md|json`)

Protocol: finding classification (ResNet-18, 160 px, 8 epochs, ImageNet init); pool = 476 train-split radiographs of the disease sub-set (labels hidden until selected); evaluation =
the fixed validation split (331 crops, 65 radiographs); the test split is never touched. Round 0 = 60 random radiographs (identical for all strategies per seed); then +60 per round
up to 300. Same data, model configuration, budgets and seeds (0, 1, 2) for every strategy. Strategies: `random`; `entropy` (mean normalised entropy of the radiograph's crops);
`combined` (0.5 x entropy + 0.5 x flip disagreement, the pipeline's two classifier signals equally weighted). Macro-F1, mean ± std over 3 seeds:

| Labeled radiographs | random | entropy | combined |
|---:|---:|---:|---:|
| 60 | 0.553 ± 0.053 | 0.553 ± 0.053 | 0.553 ± 0.053 |
| 120 | 0.626 ± 0.014 | 0.639 ± 0.011 | 0.618 ± 0.013 |
| 180 | 0.680 ± 0.019 | 0.665 ± 0.035 | 0.640 ± 0.013 |
| 240 | 0.712 ± 0.029 | 0.695 ± 0.010 | 0.702 ± 0.026 |
| 300 | 0.706 ± 0.014 | 0.706 ± 0.029 | 0.720 ± 0.027 |

**Result: uncertainty-guided selection did not improve learning efficiency over random sampling here.** Paired differences to random (3 seeds x budgets 120-300, n = 12 each):
entropy mean -0.005 (better in 7 of 12), combined mean -0.011 (better in 4 of 12); ranges about ±0.06. Differences are within seed noise. Plausible reasons (not tested): the pool is small
(476) and already class-imbalanced; the classifier is trained on crops with ground-truth boxes so image-level entropy mostly tracks the number of hard classes; 8-epoch fine-tuning from ImageNet
saturates quickly. The earlier two-strategy run (`..._random_vs_entropy_first_run.*`) gave identical random/entropy numbers, confirming determinism.
Not evaluated: ensemble disagreement and mask instability as acquisition signals; detection/segmentation active learning (needs retraining those detectors per round, not run); effect of
human corrections on a later training run.

## 5. Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_uncertainty.py --final-test       # thresholds + calibration + error-detection AUROC (writes uncertainty_thresholds.json)
.\.venv\Scripts\python.exe scripts\run_al_experiment.py --seeds 0 1 2          # ~30 min on the RTX 3050; stop the API first (GPU memory)
.\.venv\Scripts\python.exe scripts\benchmark_inference.py --images 10
```
