# Research integrity: test-set use, checkpoint provenance, patient-level leakage, model promotion

Last updated 2026-10-15. This page separates what the **code enforces** from what is only a **documented procedure**. Nothing
here makes the internal test images secret: anyone with write access to the files or the source code can read them, edit the
ledger or call the metric code directly. The protections make test use deliberate, recorded and detectable.

## 1. The internal DENTEX test split has already been used

All four current checkpoints were evaluated on the internal test split on 2026-10-14, before any authorization record existed
(the only gate was the `--final-test` flag). These results are kept unchanged as **historical results** and are entries 1-5
of `Data/reports/test_set_ledger.json`:

| # | Checkpoint | Task | Evaluated (UTC) | Test images | Checkpoint SHA-256 (prefix) | Report |
|---|---|---|---|---:|---|---|
| 1 | `dentex_fdi_numbering_v1` | numbering | 2026-10-14 07:11 | 63 | `83f97b2e1ce44b0c` | `eval_dentex_fdi_numbering_v1_test.json` |
| 2 | `dentex_findings_classification_v1` | classification | 2026-10-14 07:45 | 73 | `5aa878e1fc9ef097` | `eval_dentex_findings_classification_v1_test.json` |
| 3 | `dentex_teeth_detection_v1` | detection | 2026-10-14 05:50 | 63 | `a68ce4884066ad80` | `eval_dentex_teeth_detection_v1_test.json` |
| 4 | `dentex_teeth_segmentation_v1` | segmentation | 2026-10-14 07:51 | 63 | `dd13568c8de5c2cc` | `eval_dentex_teeth_segmentation_v1_test.json` |
| 5 | `dentex_findings_classification_v1` | classification (uncertainty / calibration error) | 2026-10-14 07:38 | (crops) | `5aa878e1fc9ef097` | `uncertainty_evaluation.json` |

Each checkpoint's current SHA-256 equals the prefix its sidecar recorded at training time. **Consequence:** any later number on
these test images is not an untouched estimate of generalisation. For an unbiased estimate of a new model, use the external
protocol in section 1.3.

### 1.1 Enforced in code (`src/dentexmodel/evaluation/test_ledger.py`, used by `scripts/evaluate_model.py` and `scripts/evaluate_uncertainty.py`)

* The API cannot evaluate on `test` (`EvaluateRequest.split` is `val` or `calibration` only).
* Training reads only `train` (fit) and `val` (epoch selection); `assert_not_test` refuses test ids. Calibration thresholds and
  temperature are fitted on `calibration` only.
* A test-split evaluation needs `--final-test`, `--authorized-by "<name>"` and `--reason "<at least 20 characters>"`.
  `--max-images` is refused for test runs (no partial peeks).
* The checkpoint must first have a **validation** report that records the same file SHA-256 (selection happens on validation).
* The same checkpoint cannot be test-evaluated twice for the same purpose.
* **One new candidate per task per test-split version.** Beyond the historical results, a second different candidate of the
  same task on the same split assignments is refused (`test_candidate_limit`). This blocks repeated candidate comparison on
  the test images.
* Legacy checkpoints (no training manifest) cannot get a new test result; `--reproduce --out-dir <folder>` re-runs their
  historical evaluation into a separate folder and is recorded as a reproduction.
* Every authorized test run is appended to the ledger: checkpoint SHA-256, time, split-assignment hash and manifest SHA-256,
  number of images, metrics, report path, authorizer, reason, and the earlier uses of the split for that task. The report
  itself carries a `test_set_status` block saying whether the split was used before.
* Ledger entries are hash-chained. `python scripts/test_set_ledger.py --verify` detects an edited, removed or reordered entry,
  and the gate refuses to add to a broken ledger.
* `scripts/evaluate_uncertainty.py` keeps the previous report as `uncertainty_evaluation.<timestamp>.json` before
  overwriting a report that contains a test block.

### 1.2 Procedural only (not enforced)

* The ledger file, the report files and the code can be edited or deleted by anyone with file access. The hash chain makes
  edits to *entries* detectable; deleting the whole file and the reports is not detectable by the application.
* Re-splitting the dataset changes the split-assignment hash and so resets the one-candidate-per-task rule. Re-splitting must
  not be used for that purpose.
* `scripts/audit_models.py` and `scripts/audit_live_api.py` run inference on 2-3 annotated test-split films to check software
  behaviour (finite boxes, box IoU against ground truth). They produce no selection metric and do not use the gate. Do not use
  them to compare candidates.
* The metric functions can be imported and called on test images directly, which bypasses the gate.
* Hyper-parameter tuning in `scripts/ml_cls_train.py` uses train/val only; there is no code that tunes on test, but nothing
  stops a person from writing such code.

### 1.3 Protocol for a genuinely untouched external test set (procedure; not implemented as a feature)

1. Before any model development on it, obtain a separately sourced, labelled panoramic set (different site or scanner if
   possible). Record its source, licence, acquisition period and the labelling protocol.
2. Compute SHA-256 for every file and check for pixel-identical and near-duplicate overlap with all of DENTEX (the methods in
   `scripts/check_leakage.py`). Remove overlaps and record them. If patient ids exist, also exclude any patient present in the
   development data.
3. Freeze a manifest (file name, SHA-256, labels) and store its SHA-256 together with a signed note by the data custodian.
   Keep the files with the custodian, not with the developers, until the final candidate is fixed.
4. Finish all model selection, threshold choice and calibration on DENTEX train/val/calibration. Fix one candidate per task
   and record its checkpoint SHA-256, its training manifest and its validation report.
5. Evaluate that single candidate once on the external set with the same metric code. Record the checkpoint SHA-256, the
   external manifest SHA-256, time, metrics and authorizer, in the same form as the ledger.
6. Report the result as the external estimate. Do not retrain or re-threshold based on it. A later candidate needs a new,
   untouched external set.

## 2. Checkpoint provenance

* **Future checkpoints (enforced):** `trainers._save_checkpoint` writes `<checkpoint>.training_manifest.json` with every image
  that actually contributed to training and to epoch selection (image id, file SHA-256, file path, source, number of crops or
  boxes), the manifest SHA-256, the split-file SHA-256, the split-assignment hash, the dataset fingerprint, the class mapping,
  preprocessing and augmentation, the seed, the full training configuration, and any approved review crops (review id + image
  SHA-256). The sidecar stores the manifest's SHA-256. If the manifest is later missing or edited, the registry rejects the
  checkpoint.
* **The four current checkpoints are legacy.** They were trained before manifests existed. Their sidecars record image *counts*
  (440 train / 69 val images for the detectors; 1550/438/412/120 crops per class for the classifier). These match what the
  current split produces, which is consistent with training on the current split but **does not prove image-level
  membership**. The registry and the UI label them `legacy: image-level training membership not recorded`; no manifest was
  reconstructed for them.

## 3. Patient-level leakage: unresolved

DENTEX as used here has no patient identifiers. Splits group files by pixel hash (`h_` + SHA-256 prefix), so identical copies of
a radiograph, including copies across the three DENTEX sub-sets, always share one split (verified: 0 groups across splits).
Near-duplicates are checked by perceptual hash plus pixel correlation (0 confirmed across splits). **This does not prove that
different films of the same patient are in the same split.** Patient-level leakage cannot be excluded and remains an open
limitation. If reliable patient ids become available, set `patient_id_regex` (configs) so they become the split groups, then
re-split. That retires the current test split and needs the external protocol above.

## 4. Model promotion

Enforced in code (`src/dentexmodel/inference/promotion.py`, `/api/models/promote`):

* Promotion needs a **validation-split evaluation report** for that checkpoint. Training-time metrics and calibration-split
  results are shown but are never sufficient. Test results are never required and are shown as context only.
* For a non-legacy checkpoint, the validation report must record the same file SHA-256. A legacy checkpoint's older report is
  accepted with a visible warning that it is tied by model id and version only.
* A checkpoint with a broken training manifest cannot be promoted.
* A named approver, `confirm=true` and a written justification (at least 20 characters) are required.
* Each promotion stores who, when, the model it replaced, and a snapshot of the evidence, warnings and limitations
  (`model_promotions` table; `GET /api/models/promotions`).
* **Rollback** (`POST /api/models/rollback`, name and reason required) re-activates the model the last promotion replaced, and is
  recorded too.
* "Use" (`/api/models/select`) switches without a new approval only for legacy checkpoints or checkpoints promoted before.
  A new checkpoint must go through promotion.

Procedural only: approver names are typed in and are not verified identities; one person can enter two names. The
`active_models.json` file, the `ACTIVE_<TASK>_CHECKPOINT` environment variables and `configs/models.yaml` can still select a
model without going through promotion.
