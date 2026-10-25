# CV5 Amendment 02: BASE-P2 reference registration (DRAFT, NOT IN EFFECT)

**Status: DRAFT skeleton prepared 2026-10-25. NOT REGISTERED. BASE-P2 must not be run.**

This amendment can only be completed and signed when all of these hold:
1. P2 is met;
2. a frozen imports manifest of clinician-verified labels exists, and its hash is entered in §2;
3. Amendment 01 (candidate registration) is signed, because candidates are registered before BASE-P2 is run (protocol §3.2).

Every field marked **[PENDING]** is unknown today. None may be filled with an estimate.

Governing protocol: `reports/cv5_acceptance_protocol.md` (revision 3, sha256 `0771b5f8…`). Nothing here changes a rule or threshold.

---

## 1. Role and status of BASE-P2 (protocol §3.2)

* **What it is:** the unchanged BASE recipe plus the P1 imports, in every fold's fitting part only. It is a **reference run, not a
  candidate**: never ACCEPTED, and it uses no budget slot.
* **Role:** the predeclared comparator for confirmatory candidates.
* **Comparison with CV5-BASE run 1** (the effect of the imported data) is **EXPLORATORY** (evidence category A3). It is reported, never
  used to select candidates, and BASE-P2 is never described as the same baseline as CV5-BASE run 1.
* **Order:**
  1. Amendment 01 signed;
  2. this amendment signed;
  3. BASE-P2 run;
  4. gate R on BASE-P2 in the candidate environment;
  5. candidate training.

## 2. Training data and split identity

| Item | Value |
|---|---|
| Fold file | `data/splits/cv5_folds_v1.csv`, sha256 `9b767a4822844ccf0c4bf33d299e6e37420d1458a38035af0c3a3cb9107b47a6` (unchanged; not regenerated, protocol §3.1) |
| Evaluation population | 541 primary radiographs / 2,851 primary findings; held-out and inner-validation labels are original DENTEX labels only |
| Base manifests | `data/splits/combined_{train,validation}.csv` as in Kaggle bundle v3 (`kaggle/dist/dentamind_kaggle_bundle.zip`, sha256 `9d070fc7…`) |
| Verified-label source | `data/annotation/verified_findings.csv`: **does not exist today**; sha256 **[PENDING]** |
| Review log | `data/annotation/clinical_reviews.jsonl` (hash-chained); chain head **[PENDING]** |
| Reviewer registry | `data/annotation/reviewers.csv`; sha256 at freeze **[PENDING]** |
| Frozen imports manifest | produced by `verified_to_manifest.verified_training_rows` (via `build_combined_manifest.py --include-verified`), written as a separate file; path and sha256 **[PENDING]** |
| Imported counts | findings and radiographs per class and per source **[PENDING]**. They must come from `scripts/dataset/expansion_report.py` showing a P2 gap of 0 for PL and DC |
| P2 version applied | provisional P2 of 2026-10-16 (PL ≥ 300 findings / ≥ 200 radiographs; DC ≥ 750 / ≥ 400), unless revised beforehand by a dated owner decision |

**Placement:** imported rows are added to the **fitting part of every fold**. They are never placed in inner-validation or held-out, and
they never contribute to an out-of-fold metric (protocol §3.1 item 2).

**Implementation status (updated 2026-10-25; not authorized for use):**
* `kaggle/cv5_imports.py` implements the import logic. It is not yet wired into any notebook. **Imports are off by default.**
  - `load_import_manifest`: refuses a missing file, a manifest whose SHA-256 is not the registered one, a manifest edited after it was
    built, and any validation problem.
  - `validate_manifest`: per finding, requires the accepted clinician-verification record (review-log record hash, registered
    reviewer, decision, date), the label source, the pool identity and split lock, and a source with complete licence / provenance
    fields. It refuses duplicates.
  - `check_independence`, `gate_v6_for_manifest`.
  - `augment_plans`: appends imported rows to the fitting part of every fold only; inner validation and held-out lists are passed
    through untouched; refuses imports whose group is in the fold file.
  - `p2_status`: a consistency check; the binding count stays `expansion_report.py`.
* `scripts/dataset/build_cv5_import_manifest.py` builds the manifest locally from the P1 route and writes it once (never overwritten).
* Tests: `tests/test_cv5_imports.py`, 22 passed (synthetic fixtures only).
* **Not done, needs separate authorization:** wiring the imports into the candidate / BASE-P2 notebook. This changes the frozen
  `kaggle/make_cv5_notebook.py` (Amendment 01b change set) and so needs its own dated change with new hashes. The imported images
  must also be made available on Kaggle (a separate private dataset), with their SHA-256 values checked against the manifest.

## 3. Independence checks (gate V6, protocol §3.1 item 4)

Implemented in `kaggle/cv5_accept.gate_v6`. It runs before any training that uses imports. Each imported radiograph is checked against
every image of:
* the 581-group CV pool;
* the calibration split;
* the test split;
* the `eval_locked` groups of `data/annotation/annotation_pool.csv`.

The checks:

| Check | Rule | Hit means |
|---|---|---|
| Radiograph-group identity | import group ∉ protected groups | refused |
| Exact duplicate | import SHA-256 ∉ protected SHA-256s | refused |
| Near duplicate | dHash Hamming ≤ 4 **and** 256 × 128 thumbnail correlation ≥ 0.97 (the project leakage rule) | refused |
| Pool split lock | only annotation-pool radiographs locked `unassigned` may be imported. `train`-locked rows are twins of project radiographs, and under CV every project radiograph is held out once | refused; recorded as excluded in the manifest |

* Any hit gives NO VERDICT until the hit is removed.
* The P1 route already re-checks eligibility at import (`clinical_review.training_eligibility`: evaluation radiographs, eval_locked
  twins and Hanoi without full review are excluded). V6 is an independent second check.
* Patient-level identity cannot be checked, because DENTEX has no patient IDs. This is stated as a limitation.
* The V6 result JSON (all hits, rule, counts) is archived with BASE-P2. Its sha256 is **[PENDING]**.

## 4. Exclusions
* **Calibration and test splits:** never read by training (`excluded_by_design` in every training manifest). They are listed in V6
  only as protected references.
* **`eval_locked` radiographs and their twins:** never imported.
* **`train`-locked pool radiographs (twins of project-train radiographs):** never imported under CV.
  - P1's `training_eligibility` allows them, because it was written for a single split.
  - The CV import path refuses them, as protocol §3.1 item 3 requires: only radiographs outside the evaluation population, and under
    CV that population includes every train / validation radiograph.
* **Corrections to existing pool findings** (e.g. `reports/cv5_caries_clinician_review_list.csv`): excluded until a separate
  label-revision protocol is approved (owner B-4).
* **Unverified pool radiographs:** the 6,006 annotation-pool groups and the 525-row review queue count toward nothing until they are
  clinician-accepted through the P1 route.

## 5. BASE-P2 configuration and provenance

| Item | Value |
|---|---|
| Recipe | `EXPERIMENTS["BASE"]` unchanged: CE, inverse-frequency weights cap 5, no sampler, 15 epochs, batch 32, AdamW lr 3e-4, wd 1e-4, hflip 0.5, contrast 0.1, ResNet-50 IMAGENET1K_V2, 224 px crops, pad 0.10 |
| `extra` | `{}`: trainer `dentamind_kaggle:train_run` (`cv5_accept.trainer_for`) |
| Data option | BASE data + frozen imports manifest **[PENDING: implementation of the data option]** |
| Folds / seeds | v1 folds 0–4 × seeds 42–46 = 25 runs; inner validation as `cv5_lib.fold_plan` |
| Detector boxes | regenerated with the production detector; gate 3 as in `cv5_protocol.md` |
| Run handling | `cv5_accept.run_isolated`: protocol §9 classes and retries, per-run training manifest written by the run itself |
| Code | candidate-path freeze `reports/cv5_candidate_path_freeze.md` plus Amendment 01b hashes; Kaggle data bundle v3 unchanged (`dentamind_kaggle.py` `879faa93…`, `dsutil.py` `debeb7f0…`) |

## 6. Comparator prediction reproduction (gate R, protocol §4.3)

Before any candidate trains, the 25 stored BASE-P2 checkpoints are re-evaluated in the candidate environment.
* **Matching:** each checkpoint is matched by SHA-256 to the BASE-P2 `checkpoint_manifest.json` and to its own training manifest.
* **Re-evaluation:** each checkpoint is evaluated on its own held-out fold, in both settings, with BASE-P2's stored detector boxes.
* **R1:** identical argmax for every finding.
* **R2:** maximum probability difference ≤ 1 × 10⁻⁴.
* **R3:** identical accuracy, macro-F1 and per-class precision / recall / F1. ECE and NLL differences are reported only.
* **Implementation:** `cv5_accept.gate_r`.
* **Fold-file check:** the fold file must be byte-identical (sha256 above).
* **On failure:** a validity failure before candidate training. No budget slot is used, and the cause is resolved by a dated amendment.

## 7. Required manifests and evidence (archived with BASE-P2, all hashed in SHA256SUMS.txt)
* Frozen imports manifest and V6 result JSON.
* `expansion_report.py` output showing P2 met.
* Per run:
  - `result.json`;
  - `cv_run.json`;
  - training manifest (`best.training_manifest.json`, written by the run);
  - attempt records (`run_attempts.json`, `attempt_<n>.json`);
  - any failure records;
  - held-out predictions.
* `run_status.json` covering all 25 runs.
* The run-evidence archive, which is produced even if runs fail.
* `checkpoint_manifest.json` (the 25 checkpoint hashes), `oof_predictions.csv`, `detector_boxes_pool.json`, `fold_plan.json`,
  `environment.json`, `training_log.txt`.
* Embedded-code hashes, and the Kaggle notebook name and version.

## 8. Reporting
* The BASE-P2 vs CV5-BASE run 1 comparison is labelled **"EXPLORATORY: not a confirmatory result"**. It states the change in training
  data (number and source of imported findings).
* No candidate is selected, ranked or changed on the basis of BASE-P2 results. In the first round, candidates are frozen before
  BASE-P2 runs.

## 9. Owner signature (registration takes effect only when completed)

| Field | Entry |
|---|---|
| Frozen imports manifest path and sha256 | |
| `expansion_report.py` output sha256 showing P2 met | |
| Amendment 01 signature date | |
| Registered by (owner's own full name) | |
| Date and time (UTC) | |

---

## Addendum 2026-10-25: proposed notebook wiring (UNAPPLIED) and local V6 record

* **Proposed change:** `patches/cv5_import_wiring.patch` (sha256 `1dfc288cab7e76658dde5f1a30a5e2ed7ddfbd5ad70a7d5101f9c0526eb7b462`), against the frozen `kaggle/make_cv5_notebook.py` (`4a5efda8…`).
  - **Status:** not applied. The frozen file is unchanged. Applying it needs a separately authorized, dated change with new hashes.
  - **With `imports=None`:** the generated notebooks are byte-identical to today's (tested).
  - **With a registered manifest:** one cell after the detector cell, which in order:
    1. loads the manifest (registered SHA-256, content, verification);
    2. loads the registered **local V6 record**;
    3. verifies every imported image file;
    4. checks identities against train / validation / calibration / test using IDs only (no calibration or test image is read);
    5. runs the near-duplicate V6 check against the CV-pool images;
    6. adds imports to every fold's fitting part, and asserts that no inner-validation or held-out assignment changed;
    7. builds import crops with the candidate's crop rule.
* **Local V6 record:** `scripts/dataset/run_cv5_import_v6.py`. The full near-duplicate check against calibration, test and
  `eval_locked` images runs locally, because the notebook never reads those images. It writes a record once and only if V6 passes.
* **Extra registration field:** the V6 record's SHA-256 is needed in addition to the manifest SHA-256.
  `write_candidate_notebook(..., imports=...)` refuses unless this amendment names both hashes.
* **Tests:** `tests/test_cv5_import_wiring.py` (14), on a temporary patched copy of the generator; `tests/test_cv5_imports.py` (22).
  All fixtures are synthetic.
