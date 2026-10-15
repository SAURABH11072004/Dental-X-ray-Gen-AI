# Known limitations

This is a research prototype. Nothing it outputs is a diagnosis and it has not been clinically validated.

## Data

- **Overlapping sub-sets.** DENTEX's three annotated folders contain 2,005 annotated image entries but only **1,133 distinct
  radiographs**; unlabeled and validation folders also repeat some of them (see `docs/DATASET_GUIDE.md`). Dataset sizes quoted
  by the original download (for example "705 images") count entries, not independent patients.
- **No patient ids.** DENTEX file names carry none, so patient-level leakage cannot be excluded. The pipeline groups splits by
  identical pixels, which prevents the *same radiograph* from crossing splits, but two different radiographs of one patient
  would not be detected.
- **Small validation/test sets.** Per task the validation split is small (detection 69 radiographs, findings 65 radiographs /
  331 crops; rare classes have few crops, e.g. Periapical Lesion). Metrics for those classes are noisy.
- The 50 images in `validation_data/` are **unlabeled**: they are used only to demonstrate inference and are never evaluated.
  20 of them are pixel-identical to labelled radiographs (12 train, 2 val, 3 calibration, 3 test split); the image pickers label
  each one with the split of its twin. Predictions on the train-split copies are optimistic.
- **The internal test split has already been used** for final evaluation of all four current checkpoints (2026-10-14). Those
  numbers are historical; a later result on the same images is not an untouched estimate. Test use is gated and recorded in
  `Data/reports/test_set_ledger.json`; see `docs/RESEARCH_INTEGRITY.md` for what is enforced and what is procedure only.
- **The current checkpoints are legacy for provenance:** their image-level training membership was not recorded (counts
  match the current split, which does not prove membership). New checkpoints get an image-level training manifest.

## Models (what each one can and cannot say)

- **Tooth detector** (Faster R-CNN R50-FPN, one class "tooth"): finds teeth, it does **not** number them. Numbers come from the
  separate `dentex_fdi_numbering_v1` model (test exact accuracy 0.968 among localised teeth, 0.938 strict). A tooth the numbering
  model does not overlap stays "unassigned"; wisdom teeth (18/28/38/48) and absent/impacted teeth are the least reliable. Numbers are
  model output, not confirmed.
- **Reports in Hindi/Marathi** are fixed templates whose wording has not been reviewed by a native-speaking dental professional.
- **Finding classifier** (ResNet): trained *only on teeth that DENTEX marks with one of four findings* (Caries, Deep Caries,
  Impacted, Periapical Lesion). There is **no healthy class**, so it answers "which of these four does this crop most resemble",
  never "is this tooth diseased". Its softmax probabilities are not calibrated clinical probabilities. It classifies given boxes
  (ground-truth boxes in evaluation, detector boxes in the app); it is not a disease *detector*.
- **Instance segmentation** is trained from the dataset's real polygon masks; it is only available if a segmentation checkpoint
  exists (check the Model Registry). Boxes are never converted into masks.
- Pretrained starting weights are general-domain (ImageNet / COCO) from the official torchvision URLs; they are recorded in each
  checkpoint's sidecar.
- Training used one seed and a single hold-out split; no confidence intervals over seeds are reported for the final models.
- Models were trained and evaluated on one dataset (three institutions, varying equipment). Performance on other scanners,
  paediatric patients or unusual scans (for example images with stitching artefacts) is unknown.

## Uncertainty and review

- **Flip disagreement, mask instability and detection instability are test-time augmentation of ONE network (horizontal flip), not an ensemble and not Bayesian.**
  True model disagreement needs several independently trained models; the interface reports it as unavailable (with the reason) rather than inventing it.
- Review thresholds (entropy >= 0.397, flip disagreement >= 0.076) were chosen on the calibration split of one dataset and one seed: **provisional**. On the test
  split the entropy flag marks 54 % of crops (error rate 34 % flagged vs 6 % unflagged; 87 % of errors caught), so many regions are routed to manual review by design.
- Class scores are **uncalibrated** model scores (test ECE 0.048; temperature scaling gives 0.036 but is not applied in the app).
- Reviewer names are self-declared; there is no authentication or role enforcement in this architecture. The second-person approval rule compares names only.
- Approved reviews can enter a training run only through an explicit option and only for pool/upload images; that path has unit tests but **no retraining with approved reviews has been run**, so its effect is unmeasured.

## Active learning

- The measured comparison covers **random vs entropy** selection with a ResNet-18 classifier. Ensemble disagreement needs
  several independently trained models and mask instability needs a segmentation model, so those signals are reported as
  unavailable and are not part of the measured comparison.
- "Annotation" in that experiment reveals labels that already exist; it measures label efficiency, not annotator effort.
- The Label Studio loop is implemented but was **not** exercised against a live Label Studio server in this environment.

## Reports

- Reports are template-based unless an OpenAI-compatible LLM is configured (`LLM_API_KEY`); the LLM path was **not** tested
  live. Every report is an unconfirmed research draft until a named reviewer signs it off, and the validator refuses text that
  cites teeth, labels or numbers that are not in the structured findings.

## Platform

- Developed and run on Windows 11, Python 3.13, PyTorch 2.6 + CUDA 12.4, RTX 3050 Laptop GPU (4 GB). Training both detectors
  at full resolution needs about 3 GB of GPU memory; do not run two trainings at once on this card.
- Detectron2 is **not** used (the existing code base is torchvision based); it is not installed and not required.
- The PowerShell setup scripts in `scripts/windows/` were not executed by the automated session that wrote this (the
  execution-policy bypass they need was blocked); the equivalent manual steps in `docs/WINDOWS_SETUP.md` were run and work.
- Docker and a live LLM / Label Studio / TensorBoard were not exercised.
