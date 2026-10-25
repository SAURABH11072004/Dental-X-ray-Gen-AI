# CV5 candidate path: review and code freeze

> **Superseded change set pending (2026-10-25):** the candidate interventions changed `cv5_accept.py`, `make_cv5_notebook.py`,
> `make_cv5_preflight_notebook.py`, `dentamind_cv5_preflight.ipynb` and `tests/test_cv5_candidate_runs.py`, and added new files.
> * The new hashes are recorded in the DRAFT `reports/cv5_amendment_01b_implementation.md` and `reports/cv5_candidate_bundle_v1_manifest.json`.
> * The table below is kept as the record of the first freeze.
> * Until Amendment 01b is in force, no candidate notebook may be run.

Date: 2026-10-25. Protocol: `reports/cv5_acceptance_protocol.md` (revision 3, approved). The protocol is unchanged.

**What this freeze means:**
* The files below are the candidate-run code that every candidate notebook embeds or relies on.
* From this date, a change to any of them is a dated amendment, with new hashes recorded here.
* A candidate notebook generated after a change must not be run before that amendment exists.
* `kaggle/cv5_lib.py`, `kaggle/dentamind_kaggle.py` and the BASE notebook are not part of this change set and are unchanged.

## Frozen files (SHA-256)

| File | SHA-256 |
|---|---|
| `kaggle/cv5_accept.py` | `9e4dc06761af8a599b04afc027b9003b04ad807ac650a908cb523fad1d752cea` |
| `kaggle/make_cv5_notebook.py` | `89ce67b66dc4cb0523b96208d10f4ea958d1bb199a2c4c972c7e43439b4ff1db` |
| `kaggle/cv5_preflight_trainer.py` | `d511da4bd07b597ef80a9d09fa88dd192e25e3c604f28ffc012254e7e15b7a33` |
| `kaggle/make_cv5_preflight_notebook.py` | `2f234cea87d2b84a7c08d7b9aae254f60d52a8e98f86f48e48630bd12748295a` |
| `kaggle/dentamind_cv5_preflight.ipynb` | `af9a4aa27f32164ed9f8ab2a2d75ecae149a032fe73d9e17eb534fac043a8873` |
| `tests/test_cv5_candidate_runs.py` | `c14f31f0c2230f1ccb7ad071b12211b04e15e9441ea90a6620b3d7f362cb0268` |
| `tests/test_cv5_accept.py` | `5fe1ba218f249c1d036fc959fb74e953e1dfcfd892747a09e6043d14ed0581e6` |

**`make_cv5_notebook.py` is a seventh file.** It changed in this review, after the pre-flight run, by one line in the candidate definition cell. That line refuses to start a candidate notebook when the pre-flight trainer switch is set. It sits before the block the pre-flight reuses, so the pre-flight notebook and its hash are unaffected (checked by test). The BASE notebook output is still byte-identical (`dd65c7c7…`).

**Unchanged references:**
* `kaggle/dentamind_kaggle.py` `879faa93…`
* `kaggle/cv5_lib.py` `72084f9b…`
* `kaggle/dentamind_5fold_cv.ipynb` `dd65c7c7…`
* approved protocol `0771b5f8…`
* revision 2 proposal `98d6e223…`
* ledger `f117c1a3…`

## Review confirmations

**1. Manifest timing**
* The manifest is written by the run's own worker process, immediately after `DK.train_run` returns. By then `train_run` has saved and hashed `best.pth` and written `result.json` and the sidecar.
* Before writing, the worker checks:
  - that the checkpoint on disk matches the hash the trainer recorded;
  - that the trainer's config and seed match the run.
* The manifest records:
  - checkpoint file, size and hash;
  - run, fold, seed and selected epoch;
  - training config;
  - fold-file hash and fit / inner array hashes;
  - trainer.
* The checkpoint sidecar references the manifest.
* **No late manifest.** If an attempt ends after `best.pth` or `result.json` exists but before completion is recorded, the run is final-incomplete. The parent refuses any retry, and the worker refuses to write a manifest when either file is present at start. Tests: `test_interruption_after_checkpoint_before_manifest_is_incomplete_without_late_manifest`, `test_worker_refuses_a_late_manifest_even_if_called_directly`. The Kaggle pre-flight confirmed the same.
* **Manifest-write failure** makes the run final-incomplete. It is not retried and is never eligible.

**2. Conservative exception classification**
* **Retried as infrastructure** (at most 3 attempts per run, counted across sessions):
  - out-of-memory: `torch.cuda.OutOfMemoryError`, "CUDA out of memory", host `MemoryError`, cuDNN / cuBLAS allocation failures;
  - CUDA illegal memory access or unspecified launch failure;
  - missing or broken driver, no GPU, uncorrectable ECC error, kernel launch timeout;
  - process timeout;
  - process killed by SIGKILL (return code −9 / 137).
* **Never retried:**
  - computation errors, and all other CUDA or cuDNN errors, including device-side asserts and `CUDNN_STATUS_INTERNAL_ERROR`;
  - silent exits without a record ("ambiguous").

  These make the run final-incomplete.
* **Divergence** (non-finite training loss, including one recorded before a crash, or a collapse ≥ 0.99) is FAIL. It takes precedence as approved.

**3. Pre-flight trainer isolation**
* A fake trainer can only be selected through `DENTAMIND_PREFLIGHT_TRAINER`. It is recorded in every attempt record and in the manifest (`cv.trainer`).
* Pre-flight runs are never eligible for final-model selection, and `heldout_report` refuses their manifests.
* The fake trainer module is embedded only in the pre-flight notebook, never in candidate notebooks.
* A candidate notebook now refuses to start if the switch is set.

## Verification evidence
* **Full test suite:** 423 passed. The two CV5 candidate test files: 47 passed.
* **Kaggle pre-flight:** "DentaMind CV5 candidate preflight" (`btechgd10/dentamind-cv5-candidate-preflight`), version 1.
  - Status: "Successfully ran in 159.1s", Tesla T4, torch 2.11.0+cu128.
  - Inputs: none attached, Internet off.
  - Result: PREFLIGHT RESULT: PASS (150 checks, 0 failed).
  - Run-evidence archive sha256 `bfb65370…`; output archive sha256 `87840fa5…`.
  - These values are read from the Kaggle log. The output archive was not downloaded.

## Not covered by this freeze
These need a registered candidate and real data, and remain untested:
* the data cells of a candidate notebook;
* aggregation with all 25 runs complete;
* a real `train_run` writing a manifest on Kaggle;
* gate R, gate V6, BASE-P2.
