# Evaluation: dentex_teeth_segmentation_v1 on the **val** split

Generated 2026-10-14T18:06:10.144806+00:00. Images: 69. Dataset version: `{'fingerprint': '7f66d59d9cbad925', 'manifest_sha': '932b0b941f54643e', 'splits_sha': 'ee88dc6835eb9a20', 'assignments_sha': '1c350480eed2ae96'}`.

All numbers below were computed by running this checkpoint over that split. Research use only; not a diagnosis.

## segmentation

- Box mAP@[.5:.95]: **0.5689**; AP@0.5: **0.9808**; ground-truth boxes: 2000
- Mask AP@0.5: 0.9796; mean mask IoU 0.794 and Dice 0.883 over 1972 matched teeth
- At score >= 0.3 (app default), IoU >= 0.5: TP 1972, FP 70, FN 28; precision 0.966, recall 0.986
