# CV5 Amendment 01b: candidate intervention implementation and code freeze (DRAFT, NOT IN EFFECT)

**Status: DRAFT 2026-10-25.**
* It takes effect only together with Amendment 01, once that is signed by the owner.
* It registers nothing, reserves no budget slot and changes no protocol rule or threshold.
* No candidate was trained. Only a synthetic engineering smoke test ran, described in §4.

Governing protocol: `reports/cv5_acceptance_protocol.md` revision 3 (`0771b5f8…`), unchanged.

## 1. What was implemented

| Intervention | Selected by | Implementation | BASE path |
|---|---|---|---|
| C1 `CROP384` (F1) | `ExpConfig.extra = {"crop_size": 384}` | `cv5_interventions.build_crops` / `build_detector_crops` call the unchanged DK crop builders with `DK.CROP_SIZE` rebound inside `crop_rule()` (restored on exit and on error); `dsutil.crop_region` already takes size and pad | unchanged: default crops byte-identical (test) |
| C2 `PAD25` (F1) | `extra = {"crop_pad": 0.25}` | same, with `DK.CROP_PAD` rebound; region = box ± 0.25 × width / height, clipped to the image | unchanged |
| C3 `CNXTT` (F2) | `extra = {"backbone": "convnext_tiny"}` | `cv5_interventions.new_model`: torchvision ConvNeXt-Tiny (IMAGENET1K_V1), last classifier layer → 4-way linear (BASE class order). `DK.train_run` builds it through `model_rule()`, which rebinds `DK.new_model` in the run's own worker process | `resnet50` default is the BASE constructor itself (`BASE_NEW_MODEL`, bound at import) |

**Shared mechanics:**
* **Trainer selection:** `cv5_accept.trainer_for(cfg)` gives `dentamind_kaggle:train_run` for BASE (empty `extra`) and
  `cv5_interventions:train_run` otherwise. `REAL_TRAINERS` contains exactly these two. The pre-flight trainer is not a real trainer;
  runs that use it are recorded as pre-flight, are never eligible, and are refused by the final-model report.
* **Candidate notebook** (`make_cv5_notebook.candidate_cells`):
  - V3 single-intervention check, at generation time and in the notebook;
  - crops and detector crops built with the candidate's crop rule, with crop-tagged cache names;
  - held-out prediction uses the candidate's backbone;
  - `cv5_interventions.py` embedded and archived;
  - the candidate notebook refuses to start if the pre-flight switch is set.
* **Provenance:**
  - The per-run training manifest records the full config, including `extra`, and the trainer.
  - The checkpoint sidecar written by `DK.train_run` is corrected to the actual architecture, image size and crop padding, and an
    `intervention` field is added.
* `kaggle/dentamind_kaggle.py` (`879faa93…`) and `scripts/dataset/dsutil.py` (`debeb7f0…`) are **unchanged** and equal to the Kaggle
  data bundle v3. That bundle (`kaggle/dist/dentamind_kaggle_bundle.zip`, `9d070fc7…`) is not rebuilt.

**Defects found and fixed during implementation:**
1. **Infinite recursion for ResNet-backed candidates (C1, C2).** `model_rule` routed `DK.new_model` → `CI.new_model` → `DK.new_model`. Fixed
   by binding the BASE constructor once at import; a regression test was added.
2. **Pre-flight import gap.** The pre-flight notebook lacked the `cv5_interventions` import used by the copied V3 line. Fixed and
   regenerated.

## 2. Frozen change set (SHA-256)

| File | SHA-256 | Change |
|---|---|---|
| `kaggle/cv5_interventions.py` | `752b0da88d18ba67c2d807e68e01afced8baf2db6dcdacc9004492fded463c62` | new |
| `kaggle/cv5_accept.py` | `f55a44ed57b0232a9be2d49255c107f40dfeaf8e695aa9488d22cf5c18ff7798` | trainer selection, `REAL_TRAINERS` |
| `kaggle/make_cv5_notebook.py` | `4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641` | candidate crop / model / V3 / embed |
| `kaggle/make_cv5_preflight_notebook.py` | `63fd98fa8d4aef683b9410b19bdab0d3a32c46068ec1375af36b05a6f8facfd8` | embeds interventions; PAD25 config |
| `kaggle/dentamind_cv5_preflight.ipynb` | `6bf9ea1851fe8b63fe01760f5320023f2df142b58f283a35def6643c2b1eb3bb` | regenerated |
| `kaggle/build_candidate_bundle.py` | `066b937b6e035dbd417268ae141f3eeaf6e19417a51af48764893512668c3aaf` | new |
| `kaggle/cv5_preflight_trainer.py` | `d511da4bd07b597ef80a9d09fa88dd192e25e3c604f28ffc012254e7e15b7a33` | unchanged |
| `tests/test_cv5_interventions.py` | `e4f90b75937a1a1d4e18af89a017692f53b3943a597700700d4d2e4d184b458c` | new (17 tests) |
| `tests/test_cv5_candidate_runs.py` | `89b5b7f226a84f5849e64c7239b7c96b97f9fca3fdf9a2dbc3a99f6c66608f0a` | candidate configs are now real single interventions |
| `tests/test_cv5_accept.py` | `5fe1ba218f249c1d036fc959fb74e953e1dfcfd892747a09e6043d14ed0581e6` | unchanged |
| `kaggle/dist/dentamind_cv5_candidate_code_v1.zip` | `8ce64d2607be9c1fa8176f4abeb6e7db2f4428cfbf9298c479337f141e119544` | new versioned bundle (14 files) |
| `reports/cv5_candidate_bundle_v1_manifest.json` | `65984508db64054d8e978d2ddc779f840d22e141ebe2edcffe5c89a4461f4dab` | bundle manifest |

`kaggle/cv5_lib.py` (`72084f9b…`), the BASE notebook (`dd65c7c7…`) and the fold file (`9b767a48…`) are unchanged.

## 3. Test evidence
* **Full suite:** 440 passed.
* **Intervention tests** (`tests/test_cv5_interventions.py`, 17), covering:
  - BASE code and recipe pinned to bundle v3;
  - V3 gate;
  - default crops byte-identical to BASE;
  - C1 384 px crops (region identical to `crop_region`, alignment with the 224 px crop);
  - C2 padding geometry, corner clipping and exact region bounds on a gradient image;
  - no cross-radiograph pixels in any crop;
  - crop-cache tags;
  - constants restored after errors;
  - detector crops;
  - BASE model weights and predictions identical;
  - ConvNeXt-Tiny shapes (224 and 384 input, 4 classes, about 28 M parameters), checkpoint save / load round trip, and refusal to load
    into BASE;
  - no recursion with a ResNet backbone;
  - trainer delegation and sidecar provenance;
  - pre-flight trainer never real;
  - versioned bundle never overwritten, and drift refused.
* **Other test files:** `test_cv5_candidate_runs.py` 26 passed; `test_cv5_accept.py` 21; `test_cv5.py` 22; `test_ensemble_eval.py` 21.

## 4. Engineering smoke and pre-flight (no training on data)
* **Local synthetic smoke.** This was a code-path check, not a result. Setup: the real `DK.train_run` via `cv5_accept.run_isolated`;
  1 epoch; 12 random synthetic crops; local RTX 3050; temp folder deleted afterwards. For each of `CROP384`, `PAD25` and `CNXTT`:
  - status completed, with trainer `cv5_interventions:train_run`;
  - not pre-flight;
  - the manifest recorded the actual `extra` and verified;
  - the checkpoint hash matched the manifest;
  - the sidecar showed the true architecture, image size and padding.
* **Kaggle pre-flight v2.** "DentaMind CV5 candidate preflight" (`btechgd10/dentamind-cv5-candidate-preflight`), version 2:
  - "Successfully ran in 175.4s", Tesla T4, no input attached, Internet off;
  - embedded `cv5_accept.py` `f55a44ed…` and `cv5_interventions.py` `752b0da8…` (equal to §2);
  - V3 log: `{'key': 'crop_pad', 'family': 'F1', 'value': 0.25}`;
  - **PREFLIGHT RESULT: PASS (150 checks, 0 failed)**;
  - run-evidence archive `92a88c58…`; output archive `dc02ad05…`.

  Values are read from the Kaggle log; the output archive was not downloaded.
* **Local pre-flight** of the same notebook: PASS (150 / 150).

## 5. Not verified (needs real data or a registered candidate)
* Real DENTEX crops at 384 px / pad 0.25 on Kaggle, including runtime and memory of C1 at batch 32 on a T4.
* ConvNeXt-Tiny ImageNet weights on Kaggle. The download needs Internet on in the real run, as BASE does for ResNet-50.
* Aggregation with all 25 runs complete. Gate R and gate V6 on real data. Imports in the fitting part (Amendment 02).

## 6. Owner signature
Takes effect with Amendment 01. Name and date are entered there; nothing is entered here.
