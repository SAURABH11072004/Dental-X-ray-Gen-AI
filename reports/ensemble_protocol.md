# Pre-registered protocol: 5-seed BASE ensemble (mean probability averaging)

Status: **written 2026-10-24, before any ensemble prediction was computed.** Changes after results are seen are recorded as dated
amendments with their reason.

## 1. Members (fixed)

The five BASE classifiers from the Kaggle run "DentaMind external data training" v1 (`reports/external_data_results.md`),
identified by full SHA-256 from `kaggle/artifacts_external_run1/checkpoint_manifest.json`:

| Member | SHA-256 | best epoch |
|---|---|---|
| BASE_s42 | `0846c7595f9e567960d223988a284e8aab552b7a53be172f719e02508117c6ad` | 10 |
| BASE_s43 | `48c2b6718afdef0e273598e60b8feb51f3129db3d11da4d9f9c790cc2eb779cf` | 12 |
| BASE_s44 | `270cb3f190b99a9d56bc3c086a56223264e69bdc9ad989e77fe765d3ceb75a4b` | 12 |
| BASE_s45 | `05ed85068fec18102e5686d619488c50aef0fda69f4046a842dfe26cd62e22f8` | 15 |
| BASE_s46 | `653eaab4cfea1efa0b1bc3de683c707f28128aed97f9eee50619baa9ec59a30e` | 11 |

All five are used. No member is dropped, re-weighted or selected by any score. If a file is missing or its hash differs, the
evaluation stops.

## 2. Method

* Each member: ResNet-50, 4 outputs, class order `Caries, Deep Caries, Impacted, Periapical Lesion`, 224 px crops with 10 % padding,
  ImageNet normalisation, softmax in fp32 (`kaggle/dentamind_kaggle.py: predict`).
* Ensemble probability = arithmetic mean of the five members' softmax probabilities. Prediction = argmax. No temperature, no
  thresholds, no class weights, no tuning of any kind.

## 3. Data and metrics (identical to the BASE comparison)

* DENTEX validation split `data/splits/combined_validation.csv` (331 findings), images verified by SHA-256.
* Two settings, exactly as in the Kaggle notebook: ground-truth-box crops (`gt`), and production-detector-box crops matched to the
  ground truth (IoU ≥ 0.5, detector score ≥ 0.3, cached boxes `val_detector_boxes.json`; `det_matched`).
* Metrics from `dentamind_kaggle.report`: macro-F1, per-class precision/recall/F1, confusion matrix, accuracy, ECE (10 bins), NLL.
* Inference latency on the local GPU (RTX 3050 Laptop), and on CPU if feasible: batch of 64 and single crop, after warm-up,
  ensemble vs one member.
* **The DENTEX test split is not loaded.** Calibration split not used.

## 4. Reproduction check (gate before any comparison)

Each member is re-evaluated locally. Its `det_matched` and `gt` macro-F1 must match the Kaggle values in
`kaggle/artifacts_external_run1/validation_eval.json` to within 0.005. If any member fails, the comparison is not made and the
discrepancy is reported.

## 5. Acceptance (ensemble vs BASE; reference = the five individual members, `det_matched` unless stated)

The project's criteria (`ACCEPT` in `kaggle/dentamind_kaggle.py`) are applied with the closest valid analogue for a single
ensemble model compared with five single models. Thresholds are unchanged.

1. Macro-F1 gain over the BASE mean > 0.027, **and** the ensemble beats at least 4 of the 5 individual members.
   (Cross pairs do not apply to a single ensemble.)
2. Deep Caries and Periapical Lesion recall not lower than the BASE mean.
3. No class F1 more than 0.05 below the BASE mean.
4. GT-box macro-F1 not more than 0.02 below the BASE mean.
5. Deep Caries and Periapical Lesion precision not more than 0.10 below the BASE mean.

The ensemble **passes** only if all five hold.

**Reported, not used for acceptance:** a 95 % bootstrap interval (2,000 resamples of validation findings, seed 0) for the macro-F1
difference ensemble − BASE mean; ECE/NLL difference; latency ratio.

## 6. Known bias (stated in advance)

Each member's epoch was chosen on this same validation split, so every validation number here, members and ensemble alike, is
optimistic. A pass is a reason for a future, untouched evaluation; it is not a clinical result. No checkpoint, report or paper is
changed by this protocol.
