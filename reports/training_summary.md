# Class-imbalance correction: dataset expansion, integration and Kaggle training. Status report

Date 2026-10-16. **Production changed: NO.** Production checkpoints, `configs/models.yaml` and the abstention threshold are untouched;
all four production checkpoints still match the SHA-256 recorded in their sidecars.

**Kaggle run: completed.** Notebook https://www.kaggle.com/code/btechgd10/dentamind-ai-balanced-training (Version 2, private), Tesla T4
(GPU T4 x2 session, one GPU used), torch 2.11.0+cu128, Internet on, 2.13 h. Input: private dataset
https://www.kaggle.com/datasets/btechgd10/dentamind-ai-training-bundle (v2). 35/35 runs finished, 0 failed. Version 1 crashed on the
first training batch with a CUDA "illegal memory access" that did not reproduce in isolation; Version 2 trains every run in its own
process with retry/resume (no retry was needed). **Result: no strategy passed the acceptance rule; no candidate checkpoint exists.**

## 1. Current data and imbalance (measured; `reports/class_imbalance_before.csv`, `reports/dataset_inventory.json`)

DENTEX quadrant-enumeration-disease subset: 705 panoramic radiographs (678 with findings, 27 without annotations), persisted seed-42
project splits.

| Split | Radiographs | Caries | Deep Caries | Impacted | Periapical Lesion |
|---|---:|---:|---:|---:|---:|
| train | 476 | 1550 | 438 | 412 | 120 |
| val | 65 | 205 | 45 | 72 | 9 |
| calibration | 64 | 206 | 47 | 55 | 16 |
| test (previously used) | 73 | 228 | 48 | 65 | 13 |

* Imbalance in train is 12.9 : 1 (Caries : Periapical Lesion). Periapical Lesion occurs on only 87 training radiographs (116 overall,
  at most 4 per radiograph). Deep Caries occurs on 232 training radiographs.
* Every finding passes the production crop rule; counts before and after cropping are identical and match the cached crops the
  earlier experiments trained on.
* Duplicates: 11 exact duplicates inside the disease subset (manifest `duplicate_of`); 542 disease images also exist byte-identical in
  other DENTEX subsets (same split by construction); 0 confirmed near duplicates (78 hash candidates, all below the r >= 0.97 rule).
* Patient ids: **not available.** Separation is per radiograph only; whether a minority class comes from few patients cannot be checked.

## 2. Additional datasets (`reports/additional_dataset_candidates.md`, `reports/dataset_source_inventory.csv`)

| Source | Downloaded? | Used? | Verified samples contributed |
|---|---|---|---|
| DENTEX official validation labels (`validation_triple.json`, HF) | yes, SHA-256 recorded | **yes, training only** | **159 findings / 40 radiographs** (Caries 85, Deep Caries 29, Impacted 36, PL 9) |
| DENTEX official validation images (`validation_data.zip`) | not needed locally (50/50 local files CRC-identical to the archive); downloaded on Kaggle | yes | (same images) |
| DENTEX official test (`test_data.zip`, 765 MB) | yes, SHA-256 = HF LFS id | **no**: Turkish treatment taxonomy, contradicted by the English labels on the one shared radiograph | 0 |
| Dental OPG XRAY, Four-diseases (Mendeley), Children's panoramic (figshare) | no | no: incompatible taxonomies / domain | 0 |
| Tufts Dental Database | **could not access**: request form (your registration needed) | no | 0 |
| OdontoAI (+ BMC 2024 labels) | no; data statement not retrievable | no | 0 |

Notable finding: 95 of the 250 official DENTEX test images are byte-identical to radiographs in DENTEX's own training subsets.

## 3. Combined manifests (`data/splits/combined_*.csv`, `reports/combined_split_audit.json`)

| Split | Findings | Radiographs | Caries | Deep Caries | Impacted | PL |
|---|---:|---:|---:|---:|---:|---:|
| combined_train | 2679 | 516 | 1635 (+85) | 467 (+29, +6.6 %) | 448 (+36) | 129 (+9, +7.5 %) |
| combined_validation | 331 | 65 | 205 | 45 | 72 | 9 |
| combined_calibration | 324 | 64 | 206 | 47 | 55 | 16 |
| combined_test | 354 | 73 | 228 | 48 | 65 | 13 |

* Validation, calibration and test are **identical** to the project splits (checked); external data enters training only.
* Radiograph groups (exact SHA-256 + confirmed near duplicates over 2,305 images) never cross splits: overlap 0 for every split pair.
  23 official-validation findings were excluded because their radiographs are twins of project val / calibration / test images.
* No new random split was drawn (seed 42 assignment kept); manifest SHA-256s are in the audit file.
* All images are DENTEX panoramic radiographs; no bitewing or periapical images were mixed in.

## 4. Imbalance strategies: what is already measured (local, DENTEX-only, 5 seeds, validation GT boxes)

These numbers come from the project's earlier controlled study (`docs/audit_evidence/ml_improvement/imbalance/report.md`), reproduced
in `reports/imbalance_experiment_results.csv`. Same split, same protocol, one factor changed per row.

| Method | Macro-F1 | DC recall | PL recall | DC precision | PL precision |
|---|---|---|---|---|---|
| C0 baseline (inverse-frequency weights, cap 5) | 0.764 ± 0.027 | 0.587 | 0.711 | 0.577 | 0.615 |
| A: sqrt class weights | 0.742 ± 0.024 | 0.533 | 0.622 | 0.614 | 0.554 |
| B: weighted sampler | 0.766 ± 0.009 | 0.489 | 0.600 | 0.687 | 0.714 |
| C: focal loss (gamma 2) | 0.750 ± 0.022 | 0.476 | 0.600 | 0.605 | 0.702 |
| oversampling | 0.774 ± 0.016 | 0.516 | 0.689 | 0.727 | 0.670 |
| minority-only geometric augmentation | 0.751 ± 0.020 | 0.462 | 0.756 | 0.598 | 0.590 |
| no rebalancing (reference) | 0.751 ± 0.017 | 0.524 | 0.644 | 0.583 | 0.624 |

**None beat the baseline under the pre-registered rule.** Every alternative traded minority recall for minority precision (fewer
false positives, more missed Deep Caries / Periapical Lesions). The Kaggle notebook repeats A, B and C in one codebase next to the
new runs (A2 effective-number weights and D official-validation data), so all are compared on identical terms.

## 5. Kaggle experiment design

`kaggle/denta_mind_training.ipynb`: BASE, REF_unweighted, A1 sqrt weights, A2 effective-number weights, B sampler, C focal, D
+official-validation data, and E (the combination, only if more than one component passes), each with seeds 42-46.

* Mixed precision, batch 32, per-epoch resumable checkpoints, GPU memory and disk logged after every run, 11 h budget guard.
* Validation is evaluated on GT boxes and on cached production-detector boxes (323 matched findings, as in earlier studies), with
  per-class P/R/F1, false positives, confusion matrices, ECE/NLL, and accepted/abstained counts at the production entropy threshold.
* **Acceptance rule (existing, pre-registered; applied unchanged, vs BASE):** (1) detector-box macro-F1 gain > 0 in >= 4/5 seed
  pairs, mean gain > 0.027 and >= 20/25 cross pairs; (2) mean Deep Caries and Periapical Lesion recall not lower; (3) no class F1
  lower by > 0.05; (4) GT-box macro-F1 not lower by > 0.02; (5) Deep Caries / Periapical Lesion precision not lower by > 0.10.
  Sources: `data/reports/training_recipe_comparison_protocol.md` section 5 and the earlier imbalance study's side condition.
  **If you want a different promotion threshold, say so before the run.**
* The test split is read only for BASE and passing candidates, after selection on validation.
* Expected effect of D is small: +29 Deep Caries and +9 Periapical Lesion crops.


## 5b. Kaggle results (validation, 5 seeds, mean +- SD; source: checkpoints/kaggle_candidates/dc9c505b/validation_eval.json)

| Experiment | Det-box macro-F1 | GT-box macro-F1 | Accuracy (GT) | DC P / R (det) | PL P / R (det) | Abstained (GT, of 331) | Acceptance |
|---|---|---|---|---|---|---|---|
| BASE | 0.726 +- 0.026 | 0.741 +- 0.016 | 0.846 | 0.58 / 0.42 | 0.51 / 0.74 | 45 | baseline |
| REF_unweighted | 0.730 +- 0.040 | 0.741 +- 0.032 | 0.850 | 0.61 / 0.41 | 0.58 / 0.66 | 42 | fail (gain +0.004; PL recall -0.086) |
| A1 sqrt weights | 0.718 +- 0.017 | 0.748 +- 0.013 | 0.859 | 0.60 / 0.42 | 0.46 / 0.71 | 40 | fail (gain -0.009; class-F1 drop) |
| A2 effective-number weights | 0.727 +- 0.037 | 0.762 +- 0.024 | 0.853 | 0.54 / 0.44 | 0.53 / 0.74 | 52 | fail (gain +0.001) |
| B weighted sampler | 0.722 +- 0.032 | 0.751 +- 0.019 | 0.860 | 0.62 / 0.40 | 0.52 / 0.63 | 34 | fail (gain -0.004; PL recall -0.114) |
| C focal loss | 0.712 +- 0.022 | 0.747 +- 0.012 | 0.847 | 0.55 / 0.37 | 0.57 / 0.63 | 96 | fail (gain -0.014; DC/PL recall down) |
| D + official val data | 0.722 +- 0.030 | 0.756 +- 0.016 | 0.854 | 0.61 / 0.42 | 0.44 / 0.77 | 50 | fail (gain -0.004; PL precision -0.073) |

* Criterion 1 (mean det-box gain > 0.027 in >= 4/5 seeds and >= 20/25 cross pairs) failed for every experiment; the largest mean gain
  was +0.004. Differences are well inside the seed SD (0.017-0.040). Experiment E was therefore not run.
* Trade-offs match the earlier local study: sampler / focal / unweighted raise minority precision but lose Periapical Lesion recall;
  D slightly raises PL recall (+0.029, i.e. about 0.26 of one of 9 cases on average) but lowers PL precision.
* Test split (previously used; BASE only, selection on validation): GT-box macro-F1 0.693 +- 0.030; recall Caries 0.912,
  Deep Caries 0.463, Impacted 0.938, Periapical Lesion 0.369. The test use should be added to data/reports/test_set_ledger.json.
* Packaged checkpoint: baseline record only (BASE seed 45, the median seed). Staged to checkpoints/kaggle_candidates/dc9c505b/;
  local re-inference macro-F1 0.7509 vs 0.7534 on Kaggle (T4 vs RTX 3050). Not promoted.

## 6. Tests

| Check | Result |
|---|---|
| Full project suite `pytest tests` | **307 passed, 0 failed** (21 subtests) |
| New `tests/test_dataset_integration.py` (label mapping, parsers, crop rule identical to production, near-duplicate rule, dHash, remote-ZIP reader incl. CRC failure, split isolation, fixed eval sets, manifest hashes, no official-test labels / no healthy class) | 23 passed |
| New `tests/test_kaggle_training_lib.py` (weights equal existing code + training-only, sampler bounds / rebalancing, focal loss, metrics + abstention, IoU matching, acceptance rule incl. recall- and false-positive guards, **interrupted-then-resumed training bit-identical to uninterrupted**, candidate loads with production construction, deployed checkpoint loads, notebook syntax) | 16 passed |
| Kaggle evaluation path on real data reproduces project numbers | deployed model: GT macro-F1 **0.7179** (sidecar 0.7179), detector-box **0.6507** (published 0.651), 323 / 8 matched / unmatched; validation crops byte-identical to the experiment cache |
| **Full notebook executed locally** (smoke: 1 epoch, seeds 42-43, BASE / B / D) | completed all 13 code cells: bundle hash check, 541 + 65 + 73 radiographs SHA-verified, leakage asserts, training-only weights, crops, 6 training runs (peak GPU 2.3 GB), evaluation, acceptance (correctly refused with 2 seeds), E skipped, test gating (BASE only), 84 MB archive with SHA256SUMS |
| Staging script on the smoke archive | 32/32 members verified, strict load OK, local re-inference = reported value (0.5036), production snapshot unchanged; tampered archive rejected |
| Kaggle GPU run (Version 2) | completed: 35/35 runs, 0 failures, archive SHA-256 dc9c505b... verified after download |
| Staging of the downloaded archive | exit 0: 61/61 members verified, strict production load OK, production unchanged |
| Full suite after the run | **309 passed, 0 failed** |

Smoke-run metrics come from 1-epoch runs and are pipeline checks only, not results.

## 7. Limitations

* Only one compatible external source exists, and it adds about 7 % to the minority classes; no new independent test set exists.
* Periapical Lesion has 9 validation and 13 test findings; per-class metrics for it are fragile whatever the method.
* The project test split was used before; validation is used both for epoch selection and acceptance (equally optimistic for all).
* No patient-level separation can be claimed (DENTEX has no patient ids).
* The production abstention threshold was fitted for the deployed model; counts for candidates are indicative only.
