# Quality audit (2026-10-14)

Performed against the running application with the three trained checkpoints. Everything below was executed, not assumed.

## Checkpoints (`D:\Dentex-Gen Ai\Data\checkpoints\`)

| File | Task / architecture | Classes | Size | SHA-256 matches sidecar |
|---|---|---|---:|---|
| `dentex_teeth_detection_v1.pth` (+ `.json`) | detection, Faster R-CNN R50-FPN | `tooth` (num_classes 2) | 158 MB | yes |
| `dentex_teeth_segmentation_v1.pth` (+ `.json`) | segmentation, Mask R-CNN R50-FPN, `detections_per_img` 40 | `tooth` (num_classes 2) | 168 MB | yes |
| `dentex_findings_classification_v1.pth` (+ `.json`) | classification, ResNet-50 | Caries, Deep Caries, Impacted, Periapical Lesion | 90 MB | yes |

All sidecars record the dataset fingerprint / manifest hash / split hash, training config and software versions
(torch 2.6.0+cu124). No `active_models.json` override exists: each task auto-selects its only checkpoint. Known quirk: the
segmentation sidecar stores its *box* mAP under `metrics.detection`; mask AP is in `Data/reports/eval_*_segmentation_*`.

## Are displayed values real? (item 2)

Every box, mask, class name and score on screen is taken from the API response of a real forward pass; searched the frontend
and backend for default/fallback scores (`?? 1`, `score: 1`, constants) and found none. The classifier's probabilities,
the detector score and the Mask R-CNN score are read from the model output tensors (`torch_models._run_detector`,
`classify_regions`). Fixed in this audit: the Segmentation page showed "Mask AP: N/A" although a measured value existed; it now
shows the measured val/test values from `/api/evaluations`.

## Why many scores showed 1.00 (item 3)

Raw outputs (3 test images, through the HTTP API): detector scores 0.985-0.9995 (median 0.997-0.998), Mask R-CNN scores
0.982-0.9995; **none was exactly 1.0**. The "1.00" was display rounding (two decimals) of genuine, saturated softmax scores.
Saturation is expected: a one-class "tooth" problem is easy and the models were trained to low loss; these scores say
"this is a tooth", not "this box is accurate" (box accuracy is IoU, mean 0.80 vs ground truth in the alignment check) and
are not calibrated. Fix: scores now display with 3-4 decimals (segmentation list, overlay PNG, report) and the UI says that
per-instance scores are not accuracy. Per-pixel mask probabilities range 0-1 and are thresholded at 0.5 for the displayed mask.

## Alignment (item 4)

Five test-split radiographs through the real API: image size identical in the PNG file, `/api/images/{id}`, `/api/predict` and
`/api/segment`; every decoded mask has the image's exact height/width; 100 % of mask pixels lie inside their own box; boxes
(score >= 0.5) match ground truth in original pixel coordinates with mean best-IoU 0.795 (detector) / 0.796 (segmenter).
The viewer draws boxes/masks in an SVG whose viewBox is the image's natural size and which shares the image's transform, so
alignment holds at every zoom; the viewer keeps the image's aspect ratio (1.9176 drawn = 1.9176 natural).

## Tooth numbering (item 5) - superseded: a numbering model was added afterwards, see `docs/MODEL_TRAINING.md`

At the time of the audit:

**Not implemented as a model.** All `fdi` fields in real outputs are `null`; `numbering` is only a rule-based consistency
check that reports "no tooth number predicted". The "Tooth identifiers" layer is disabled in the UI and tooth numbers are
shown as "unassigned". The trainer supports `--label-mode fdi`, which was not run. Therefore no FDI numbers appear anywhere.

## Report generator (item 6) - defects found and fixed

1. It listed **every detected tooth as a finding** with the classifier's forced closest class ("predicted 'Periapical Lesion'"),
   although that classifier has no healthy class. Now such entries are `kind: closest_class` and are worded "closest trained
   class X (score s); not evidence that the finding is present"; detections are described as "detected region".
2. Its validator **rejected its own text** (finding ids "F11"-"F15" and "located 15 tooth region(s)" were read as FDI teeth), so
   reports with >= 11 regions could never pass validation or be signed off. Fixed; it still rejects an invented tooth number.
3. Only the detector's version was recorded. Reports now carry `model_versions` (detection + classification) shown in the UI/HTML.
Still true: status `unconfirmed_research_draft`, template text (no LLM call), disclaimer + limitations (including the
no-healthy-class limitation), forbidden-phrase scan ("diagnos", "recommend", "confirmed", ...). A report generated through the
UI passes all four validation checks. 3 new tests cover these cases.

## Held-out test evaluation (item 7)

`scripts/check_leakage.py` -> `Data/reports/leakage_check.md`: 0 pixel-identical radiographs between train/val/calibration/test
across all annotated sub-sets, and 0 between each model's exact training/validation set and the test set (detection,
segmentation, classification); the unlabeled pool excludes duplicates of labeled images. Informational: 3 unlabeled
`validation_data` demo images are copies of test radiographs (never used in training or any metric). **Limitation:** DENTEX has no
patient ids, so two different radiographs of one patient cannot be detected. Per-class metrics are in
`Data/reports/eval_dentex_findings_classification_v1_test.md` (Caries F1 0.842, Deep Caries 0.453, Impacted 0.926, Periapical
Lesion 0.364 with only 13 test crops); detection/segmentation are single-class ("tooth"), so per-class = overall.

## Browser-to-backend (item 8) and viewer (item 9)

Headless Edge, real servers: detection (13 boxes) and segmentation (13 masks) from the Analysis page, report generated from the
UI, Segmentation evaluation panel, 0 console errors, 0 HTTP >= 400. Viewer: the container height now follows the image aspect
ratio; the radiograph fills 99.9 % of an 810x422 viewer on desktop (previously 430x224 inside a fixed tall box) and 340x177 on a
390 px phone (previously 136x71 because the 256 px sidebar never collapsed). The sidebar is now hidden below 1024 px with a
page selector in the top bar; the inspector drops below the viewer under 1536 px.

## Tests (item 10)

`python -m unittest discover -s tests`: 139 tests, all pass.

## Remaining defects / limits

- No tooth-numbering model; no healthy-vs-diseased model (labels do not allow it).
- Test numbers are single-seed; Deep Caries and Periapical Lesion are weak; no confidence intervals.
- Grad-CAM (`/api/explain`) was verified over HTTP (real heatmap, size equals the box) but not clicked in the browser; Label Studio, live LLM and TensorBoard are untested.
- Detector/segmenter scores are saturated and uninformative for ranking; calibration was not done.

## Addendum (2026-10-14, later): full pipeline, uncertainty, review

Latest verification: `python -m unittest discover -s tests` -> **161 tests, all pass**; `npm run build` OK; headless-Edge workflow (full analysis, uncertainty, Grad-CAM, region review incl. duplicate and
self-approval refusals, English/Hindi report, other pages) -> all checks pass, 0 unexpected console/HTTP errors (the only 400s are the intended refusals). Details and measured results:
`docs/PROJECT_AUDIT.md`, `docs/UNCERTAINTY_AND_ACTIVE_LEARNING.md`, `docs/MODEL_TRAINING.md`.
