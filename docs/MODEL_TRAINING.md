# Model training and evaluation

All numbers are from real runs on this machine (Windows 11, Python 3.13, PyTorch 2.6.0+cu124, RTX 3050 Laptop 4 GB) on
2026-10-14, against the grouped splits described in `docs/DATASET_GUIDE.md`. Each checkpoint has a sidecar
(`Data/checkpoints/<name>.json`) with its task, architecture, class mapping, input rule, dataset/manifest/split hashes,
training configuration, software versions and the validation metrics measured at its best epoch. Evaluation reports are in
`Data/reports/eval_<model>_<split>.json|md`.

## What was trained

| Model | Task and labels | Train data | Config |
|---|---|---|---|
| `dentex_teeth_detection_v1` | **Tooth detection**, one class "tooth" (Faster R-CNN R50-FPN, COCO-pretrained) | `quadrant_enumeration`, train split: 440 radiographs | 12 epochs, batch 2, AdamW 1e-4 cosine, AMP, ~97 s/epoch; best epoch 9 by validation box mAP |
| `dentex_findings_classification_v1` | **Finding classification** of a tooth crop: Caries / Deep Caries / Impacted / Periapical Lesion (ResNet-50, ImageNet-pretrained, 224 px, 10 % crop padding) | `quadrant-enumeration-disease`, train split: 476 radiographs, 2,520 crops (Caries 1550, Deep Caries 438, Impacted 412, Periapical Lesion 120) | 15 epochs, batch 32, AdamW 3e-4 cosine, inverse-frequency class weights, flip + contrast jitter; best epoch 5 by validation macro-F1 (later epochs overfit: train loss 0.04, validation F1 about 0.70) |
| `dentex_teeth_segmentation_v1` | **Tooth instance segmentation**, one class, real polygon masks (Mask R-CNN R50-FPN, COCO-pretrained) | `quadrant_enumeration`, train split: 440 radiographs | 8 epochs, batch 1, AdamW 1e-4 cosine, AMP, ~200-320 s/epoch; best epoch 8 |

Not trained: any disease *detector* or "healthy vs diseased" model (the labels do not support the latter - there are no healthy examples).

### Tooth numbering (`dentex_fdi_numbering_v1`) - added 2026-10-14

- **Labels:** valid FDI numbering exists in `quadrant_enumeration` (quadrant `category_id_1` + tooth `category_id_2` -> 32 distinct valid
  FDI codes, 341-630 examples each). Checked, not assumed: quadrants sit where FDI says (1 = image upper-left, 2 = upper-right, 3 = lower-right,
  4 = lower-left) and tooth number grows with distance from the midline (1: 0.015 ... 8: 0.227 of image width). 16 of 634 images repeat a code.
- **Model:** a separate `numbering` task (Faster R-CNN R50-FPN, 32 FDI classes, COCO-pretrained, no horizontal-flip augmentation because a flip
  swaps left/right numbers); 16 epochs, batch 2, AdamW 1e-4, best epoch 15 by validation mAP. Same train split as the tooth detector.
  The existing tooth detector/segmenter are untouched.
- **Post-processing (used identically in evaluation and the app):** class-agnostic NMS, then at most one box per tooth number; a detected
  tooth gets a number only if a numbering box overlaps it (IoU >= 0.5), otherwise it stays unnumbered.
- **Registration gate:** a numbering checkpoint is ignored by the registry until `evaluate_model.py` has evaluated it on the *validation*
  split and written `evaluated_on.passed = true` (gate: exact FDI accuracy among localised teeth >= 0.80). It passed (0.936), then the
  locked test split was evaluated once.

| Split | Radiographs | Teeth localised | Exact FDI correct (of localised) | Correct quadrant | Strict (all GT teeth) | mAP@[.5:.95] (32 classes) |
|---|---:|---:|---:|---:|---:|---:|
| val | 69 | 1957/2000 (0.979) | 0.936 | 0.997 | 0.915 | 0.524 |
| **test** | 63 | 1734/1790 (0.969) | **0.968** | **0.999** | **0.938** | 0.507 |

Weakest teeth on test: 47 (0.912), 27 (0.917), 16 (0.923), 26 (0.925); per-tooth tables are in `Data/reports/eval_dentex_fdi_numbering_v1_*.md`.
Caveats: accuracy is measured against ground-truth *localisation* (a tooth must first be found); at the app threshold the numbering model
also produces extra boxes (precision 0.88 on test), which only matter if they overlap a detected tooth; 16 images in the training labels repeat a
code, so a handful of "errors" may be label noise; one seed, one dataset.

## Results

Validation = the split used to pick each model's best epoch. **Test = the locked split, evaluated once after model selection
with `--final-test`.** Test numbers are the ones to quote; they are lower than validation, as expected from epoch selection
on validation.

### Detection (`dentex_teeth_detection_v1`), tooth boxes

| Split | Radiographs | Box mAP@[.5:.95] | AP@0.5 | At score >= 0.3, IoU >= 0.5 |
|---|---:|---:|---:|---|
| val | 69 | 0.560 | 0.978 | precision 0.962, recall 0.984 (TP 1968, FP 78, FN 32) |
| **test** | 63 | **0.515** | **0.966** | precision 0.960, recall 0.974 (TP 1743, FP 73, FN 47) |

### Segmentation (`dentex_teeth_segmentation_v1`)

| Split | Box mAP@[.5:.95] | Box AP@0.5 | Mask AP@0.5 | At score >= 0.3 |
|---|---:|---:|---:|---|
| val | 0.569 | 0.981 | 0.980 | precision 0.966, recall 0.986 |
| **test** | **0.530** | **0.974** | **0.974** | precision 0.962, recall 0.980 |

Mask IoU is computed on a 4x sub-sampled pixel grid (memory); the same grid is used for predictions and ground truth.

### Finding classification (`dentex_findings_classification_v1`), given ground-truth tooth boxes

| Split | Crops | Accuracy | Macro-F1 |
|---|---:|---:|---:|
| val | 331 | 0.825 | 0.718 |
| **test** | 354 | **0.785** | **0.646** |

Test per class: Caries P 0.866 / R 0.820 / F1 0.842 (n=228); Deep Caries 0.414 / 0.500 / 0.453 (n=48);
Impacted 0.887 / 0.969 / 0.926 (n=65); **Periapical Lesion 0.444 / 0.308 / 0.364 (n=13)**. Deep Caries and Periapical
Lesion are weak; with 13 test crops the Periapical Lesion figure is very noisy. The confusion matrices are in the reports.

### Additional metrics (added 2026-10-14, test split, measured)

- Segmentation: mean mask IoU **0.780**, mean Dice **0.873** over 1,753 teeth matched by box overlap (4x sub-sampled grid), mask AP@0.5 0.974.
- Classification (given ground-truth boxes): macro one-vs-rest ROC-AUC **0.910**; per class sensitivity / specificity / ROC-AUC: Caries 0.820 / 0.770 / 0.895,
  Deep Caries 0.500 / 0.889 / 0.834, Impacted 0.969 / 0.972 / 0.990, Periapical Lesion 0.308 / 0.985 / 0.921 (n = 13). Specificity is computed one-vs-rest among the four classes only: there is no healthy class.
- Uncertainty (see `Data/reports/uncertainty_evaluation.md`): AUROC of entropy for detecting the classifier's errors 0.768 (test), flip disagreement 0.745.
- Inference benchmark (`Data/reports/benchmark_inference.md`, RTX 3050 4 GB): detector about 9 images/s, segmenter about 3.5 images/s (1.7 GB peak), full app pipeline about 3-8 s per image.

### Active learning vs random (`Data/reports/active_learning_experiment.md`)

Finding classification, ResNet-18 at 160 px, 3 seeds, pool = 476 train radiographs, evaluation = validation crops (331),
identical data/budgets/seeds for both strategies. Macro-F1, mean ± std:

| Labeled radiographs | random | entropy |
|---:|---:|---:|
| 60 | 0.553 ± 0.053 | 0.553 ± 0.053 (same random start) |
| 120 | 0.626 ± 0.014 | 0.639 ± 0.011 |
| 180 | 0.680 ± 0.019 | 0.665 ± 0.035 |
| 240 | 0.712 ± 0.029 | 0.695 ± 0.010 |
| 300 | 0.706 ± 0.014 | 0.706 ± 0.029 |

**Entropy selection did not outperform random sampling in this experiment**: the differences are within seed noise and
change sign across budgets. Ensemble-disagreement and mask-instability strategies were not run (they need several trained
models / a segmentation ensemble).

## How to read these numbers

- mAP here is computed by this project's own implementation (`dentexmodel.evaluation.metrics`, all-point interpolation, per
  class), **not** pycocotools, and for *tooth* detection - not the DENTEX challenge's disease-detection task. Do not compare it
  with published DENTEX leaderboard values.
- Tooth detection is an easy task for these models (about 28 large, well-separated objects per image); an AP@0.5 near 0.97 says
  the boxes are in the right place, not that the system is clinically useful.
- The classifier has no "healthy" class and was evaluated on ground-truth boxes. Applied to detector boxes in the app it
  labels *every* tooth with its closest of four findings; the UI and overlay say so.
- One seed per final model, small validation/test sets, a single dataset: no confidence intervals. See
  `docs/KNOWN_LIMITATIONS.md`.

## Commands

```powershell
cd "D:\Dentex-Gen Ai"
# prerequisites are checked first; training refuses (with the reason) if labels, torch or GPU memory are insufficient
.\.venv\Scripts\python.exe scripts\train_model.py --task detection --name dentex_teeth --epochs 12 --batch-size 2 --lr 1e-4
.\.venv\Scripts\python.exe scripts\train_model.py --task classification --architecture resnet50 --name dentex_findings --epochs 15 --batch-size 32 --lr 3e-4
.\.venv\Scripts\python.exe scripts\train_model.py --task segmentation --name dentex_teeth --epochs 8 --batch-size 1 --lr 1e-4
#   options: --no-pretrained  --label-mode fdi  --device cpu  --num-workers N  (--max-train-images/--max-val-images = smoke tests ONLY)

.\.venv\Scripts\python.exe scripts\evaluate_model.py --checkpoint dentex_teeth_detection_v1.pth --split val
.\.venv\Scripts\python.exe scripts\evaluate_model.py --checkpoint dentex_teeth_detection_v1.pth --split test --final-test   # once
.\.venv\Scripts\python.exe scripts\predict.py --image <png>            # single image -> Data\results\predictions\<name>.json + _overlay.png
.\.venv\Scripts\python.exe scripts\predict.py --dir <folder> --limit 20   # batch
.\.venv\Scripts\python.exe scripts\run_al_experiment.py --seeds 0 1 2
Get-Content logs\job-*.log -Tail 20                                    # training logs; per-epoch metrics are also in the sidecar `history`
```

Run one training at a time: the 4 GB GPU cannot hold two (a second job stalls or fails with CUDA out-of-memory).
Training is deterministic for a given seed (a repeated classification run reproduced epoch 1 exactly).

A checkpoint is only used if its sidecar is consistent (task, supported architecture, `num_classes` matching the class
list); otherwise the registry lists it as `rejected: ...` and refuses to activate or load it. Weights are loaded with
`torch.load(..., weights_only=True)` and `strict=True`.

## Smoke tests vs experiments

A 2-epoch / 40-image classification run was used once to check the code path; its checkpoint was deleted and none of its
numbers are reported. Every number above comes from a full run on the whole train split.
