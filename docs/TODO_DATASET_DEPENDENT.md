# Open work (updated 2026-10-14)

Done and measured: dataset audit, grouped splits, three trained models with validation and locked-test evaluation, the
random-vs-entropy active-learning experiment, real-HTTP API checks, headless-browser UI checks. See `docs/MODEL_TRAINING.md`.

Still open:
- [ ] Tooth **numbering** model (`train_model.py --label-mode fdi`); currently only a rule-based consistency check exists
- [ ] Healthy-vs-diseased modelling: the DENTEX labels contain no healthy examples; needs additional labelled data
- [ ] Calibration of the classifier probabilities on the calibration split (ECE / Brier)
- [ ] Ensemble disagreement and mask-instability uncertainty signals, and an active-learning comparison that uses them
- [ ] Multiple seeds / confidence intervals for the final models
- [ ] Live Label Studio loop, live LLM report drafting, TensorBoard, Docker (none exercised)
- [ ] The `scripts/windows/*.ps1` wrappers on a machine where `-ExecutionPolicy Bypass` is permitted
- [ ] Patient-level grouping, if patient ids can be obtained for the radiographs
