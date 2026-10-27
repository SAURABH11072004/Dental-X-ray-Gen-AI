# Consolidated patch-application plan v2: CV5 import wiring (NOT EXECUTED; decision NO-GO)

Date 2026-10-25. **This document supersedes `reports/cv5_patch_application_plan.md` (v1, `009c33ae…`) in full.** v1 and its addendum are kept
unchanged as history. Every step and hash here is self-contained; nothing in v1 applies anymore.

**Status:**
* No patch is applied and no approval exists. The decision is **NO-GO** until every item of §7 is met.
* Every hash in this plan was computed on 2026-10-25.
* Every "expected after" value was produced by a full dry run on a scratch copy outside the repository (§6).

## 1. The patch set (defects B and D resolved; one approval binds all three)

Patch-set manifest: `patches/cv5_patch_set_v1.json`, sha256 `55271334f1eaaf47a49b69c429c26ac83ba95ea499b2bbd6da809ed048bbcecd`.

| Order | Patch (SHA-256) | Target | Before | After |
|---|---|---|---|---|
| 1 | `patches/cv5_import_wiring.patch` `33ec47e60dae64a0845b49f10d6ac69b46afcd8b1661318e5e041e876ae3da46` | `kaggle/make_cv5_notebook.py` | `4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641` | `d15b1a55d959ff8e8079a8e7480c57b059f49cf866fee03ed7987f9e64ea969e` |
| 2 | `patches/cv5_test_pin_update.patch` `5e4062877f24f3943b37828c69e55b99c48d676d355fa14edc7f03573e0ec17e` | `tests/test_cv5_import_wiring.py` | `ac9fa89ee9b6472fd5cefaa6a21eea41cf577e6269de56b4fcbf96e4a88d93ee` | `20f6be2dfa622c3883995329e22512b1a1bbf4b8b0f67547b9414b6393fbf464` |
| 2 | (same patch) | `tests/test_cv5_base_p2.py` | `08ac428eb1570ae17f2e5e4b2f91e29bd92c25704dd5e9ab814baf0816101527` | `c8e10982e74fdf4984aac4bb8d130e48ad2777c2c326299faff8d5c4d6846035` |
| 3 | `patches/cv5_bundle_builder_imports.patch` `31a2ba15618ee41873bb2c457fc0887cbf60022027928bba2708f0b118925d45` | `kaggle/build_candidate_bundle.py` | `066b937b6e035dbd417268ae141f3eeaf6e19417a51af48764893512668c3aaf` | `14273a4c2099efc958182d406cc8e87eb39c8f7ad98751016671d8c120da7e54` |

* **Patch 1** is a byte-exact regeneration of the previously reviewed wiring patch (`ed26e064…`, now superseded). Its resulting
  generator content is identical (`d15b1a55…`). The earlier file lacked carriage returns in its content lines and applied only because
  the system git config sets `core.autocrlf=true`.
* **Patch 2 (defect B)** changes only the two tests that pin the generator hash:
  - `test_cv5_import_wiring.py` now asserts that the real generator is exactly `d15b1a55…` and that the reverse patch checks cleanly.
    It pins the imports-off output to the pre-patch baseline (§4).
  - `test_cv5_base_p2.py` pins `d15b1a55…`.

  No other test changes.
* **Patch 3 (defect D)** adds `kaggle/cv5_imports.py` to the candidate bundle's FILES. That module is the only file the patched generator
  needs that the bundle lacked; it depends only on `dsutil` (data bundle v3) and `cv5_accept` (already in the bundle).

**Git rule, every time:** `git -c core.autocrlf=false apply [--check | -R] <patch>`, run from the repository root.
* Never hand-merge.
* Never apply without the flag. With `autocrlf=true`, patch 3 rewrites the LF-only builder with CRLF endings, and its reverse no longer
  restores the original bytes (observed in the dry run).

## 2. Pre-change inventory and hash checkpoints

Recorded at step 1 into a new append-only execution log (`reports/cv5_patch_application_execution_log.md`, created only at execution),
and re-verified at steps 6, 8, 10 and 12.

| Group | File | Must equal (before) | After application |
|---|---|---|---|
| Affected | the 4 targets in §1 | "Before" column | "After" column |
| Affected (filled at step 9) | `reports/cv5_amendment_01c_DRAFT.md` (empty skeleton) | `36d43b0bad49d7229c0fa7623ec675856fa0d4c819934ce430129521d6154892` | filled draft, recorded in the log |
| Protected, never written | `kaggle/dentamind_5fold_cv.ipynb` | `dd65c7c7…` (raw); LF `31ffc3ef…` | unchanged |
| | `kaggle/dentamind_cv5_preflight.ipynb` | `6bf9ea18…` (raw); LF `7336f2cf…` | unchanged |
| | `reports/cv5_acceptance_protocol.md` / `reports/cv5_acceptance_protocol_proposal.md` | `0771b5f8…` / `98d6e223…` | unchanged |
| | `Data/reports/test_set_ledger.json` | `f117c1a3…` (5 entries, chain intact) | unchanged |
| | `kaggle/dentamind_5fold_cv_artifacts.zip` + `artifacts_cv5_run1/SHA256SUMS.txt` | `4ac56843…`; 88 / 88 entries | unchanged |
| | `kaggle/dist/dentamind_kaggle_bundle.zip` / `kaggle/dist/dentamind_cv5_candidate_code_v1.zip` | `9d070fc7…` / `8ce64d26…` | unchanged |
| | `kaggle/cv5_lib.py`, `kaggle/dentamind_kaggle.py`, `scripts/dataset/dsutil.py`, `kaggle/cv5_imports.py` | `72084f9b…`, `879faa93…`, `debeb7f0…`, `f9c061cb…` | unchanged |
| | Pre-audit set (8) and the other 01b files (`cv5_accept.py`, `cv5_interventions.py`, `make_cv5_preflight_notebook.py`, `cv5_preflight_trainer.py`, `tests/test_cv5_interventions.py`, `tests/test_cv5_candidate_runs.py`, `tests/test_cv5_accept.py`, `reports/cv5_candidate_bundle_v1_manifest.json`) | as recorded | unchanged |
| Created by the attempt | `kaggle/dist/dentamind_cv5_candidate_code_v2.zip`, `reports/cv5_candidate_bundle_v2_manifest.json`, the execution log, one status addendum | must not exist before | listed in the log with hashes |

## 3. Consolidated sequence (each step is a gate; any failure → §5 rollback)

1. **Inventory.** Hash every file in §2 and write the values to the execution log. Any mismatch with §2 → **STOP** (nothing has
   changed yet; no rollback needed).
2. **Patch and target hashes.** The three patch files and `patches/cv5_patch_set_v1.json` equal §1. Run
   `git -c core.autocrlf=false apply --check` for patches 1, 2 and 3. Any failure → STOP.
3. **Review the companion patches.** A human reviews patches 2 and 3 independently of patch 1, against their diffs in this
   repository. The reviewer confirms they touch only the files in §1. Not reviewed → STOP.
4. **Approval** under the approved approval policy (`reports/cv5_approval_policy_DRAFT.md`, once in force):
   - one record of scope `patch_set_application` bound to `patches/cv5_patch_set_v1.json`, by the role the policy names;
   - appended to the approval log;
   - verified with `cv5_approvals.verify_approval` and the policy checks.

   No approval, or policy not in force → STOP.
5. **Backup.** Copy the 4 patch targets and the 01c skeleton to a backup folder **outside** the repository. Record each backup's SHA-256 in the log; each
   must equal the "Before" column. Also record that the "created" files of §2 do not exist.
6. **Apply only the approved patches, in order 1 → 2 → 3,** with `git -c core.autocrlf=false apply`. After each one, its targets must
   equal the "After" column. Any mismatch or error → ROLLBACK.
7. **Full test suite** (before any bundle): `.venv\Scripts\python.exe -m pytest tests -q`. Required: 0 failures. Today 524 pass before
   the change; the scratch dry run gave 191 / 191 for the 10 CV5 suites after the change. Any failure → ROLLBACK.
8. **Scratch-only notebook regeneration (defect E):**
   - Write every regenerated notebook into a scratch folder outside the repository, never to `kaggle/`:
     - candidate notebooks for CROP384, PAD25 and CNXTT with imports off, and BASE: serialise
       `json.dumps(_notebook(cells), indent=1, ensure_ascii=False) + "\n"` to scratch files;
     - the pre-flight notebook: `make_cv5_preflight_notebook.main(<scratch path>)`. Never call `make_cv5_notebook.main()`, which writes
       the protected BASE notebook.
   - **One comparison method: the LF-normalised SHA-256** (file bytes with every CRLF replaced by LF), for every notebook. The values
     must equal `imports_off_baseline_lf_sha256` in the patch-set manifest:
     - CROP384 `d47727b6…`
     - PAD25 `5e52a6b0…`
     - CNXTT `e6e57c38…`
     - BASE `31ffc3ef…`
     - PREFLIGHT `7336f2cf…`
   - The protected BASE and pre-flight files must still equal their raw hashes in §2.
   - Any difference → ROLLBACK.
9. **Draft Amendment 01c** (`reports/cv5_amendment_01c_DRAFT.md`): fill in the evidence of steps 1–8 (§4). It stays **unsigned**.
10. **Candidate bundle v2:** `.venv\Scripts\python.exe kaggle\build_candidate_bundle.py --version 2 --manifest-out reports\cv5_candidate_bundle_v2_manifest.json`.
    - The builder refuses to overwrite.
    - Verify the manifest:
      - 15 files, including `kaggle/cv5_imports.py`;
      - every listed hash equals the working copy;
      - `relied_on_unchanged` is true for `dentamind_kaggle.py` / `dsutil.py`;
      - v1 is still `8ce64d26…`.
    - Record the zip's SHA-256. It is not predictable in advance, because the manifest embeds the build time.
    - Any failure → ROLLBACK (bundle v2 quarantined, see §5).
11. **Kaggle no-training pre-flight.**
    - The pre-flight notebook is byte-identical to the one that passed (LF `7336f2cf…`).
    - Re-run it on Kaggle with no input attached and Internet off. Require "PREFLIGHT RESULT: PASS (150 checks, 0 failed)".
    - Record the log hashes in the execution log.
    - Not PASS → ROLLBACK.
12. **Final integrity:**
    - every protected hash in §2;
    - the "After" hashes;
    - the bundle v2 manifest;
    - the pre-audit set;
    - ledger chain;
    - archive 88 / 88.

    All pass → Amendment 01c may be submitted for approval (§4). Any failure → ROLLBACK.

## 4. Amendment 01c (defect C)
* **Draft:** `reports/cv5_amendment_01c_DRAFT.md`. It is a draft from step 9 until approved. There is no advance and no retrospective
  approval.
* **It may be approved only after step 12 passes,** with an approval record of scope `amendment_01c_freeze` bound to the completed file.
* **Required evidence** (all in the execution log and copied into 01c):
  1. the pre-change inventory (step 1);
  2. the patch-set approval record and its approval-log entry (step 4);
  3. backup hashes (step 5);
  4. after-hashes of the 4 targets equal to §1 (step 6);
  5. the full test result with counts and 0 failures (step 7);
  6. the LF-normalised notebook hashes equal to the baseline, and the protected notebooks' raw hashes unchanged (step 8);
  7. the bundle v2 zip hash, manifest checks, and v1 unchanged (step 10);
  8. the Kaggle pre-flight notebook version, PASS line and log hashes (step 11);
  9. the final integrity results (step 12).
* **When approved,** 01c supersedes the 01b change-set table for these 4 files only.

## 5. Rollback (defect A)

Triggered by any failure at steps 6–12, or by a decision to abort.
1. **Restore** each of the 4 patch targets and the 01c skeleton from the backup folder (step 5). Do not reverse-patch.
2. **Verify** each restored file's SHA-256 equals the "Before" column (the skeleton: its §2 hash). A mismatch here → STOP all work and report. Do not attempt
   further repair.
3. **Quarantine created files.** Do not delete them, and do not overwrite anything. Move them to a quarantine folder outside the
   repository and record their names and hashes in the execution log:
   - bundle v2 zip and its manifest;
   - a copy of the filled 01c draft (the skeleton itself is restored in step 1);
   - scratch notebooks.

   Bundle v2 counts as published only after step 12 passes and 01c is approved. Before that, it may be quarantined.
4. **Never touched by rollback:**
   - bundle v1;
   - the data bundle v3;
   - protected notebooks;
   - protocols, ledger and archives.

   These are only verified (§2). If any differs, STOP and report: that is an integrity incident, not a rollback case.
5. **Logs are append-only.** Append a failure entry to the execution log and a status addendum. Never edit or delete earlier entries.
6. **Re-run the full test suite.** Require the pre-change result: 524 passed today, or the count recorded at step 1.
7. **Do not retry with modified patches.** A new attempt needs a new patch set, a new review and a new approval.

## 6. Dry-run evidence (2026-10-25, scratch copy outside the repository; repository unchanged)

| Check | Result |
|---|---|
| Scratch inventory equals the repository | true |
| All three patches `--check` with `core.autocrlf=false` | apply |
| After-hashes | exactly the §1 "After" column |
| CV5 test suites after the patch set (10 files) | 191 passed |
| Scratch notebooks (LF method) | CROP384 / PAD25 / CNXTT / BASE / PREFLIGHT equal the baseline |
| Scratch bundle v2 (discarded) | 15 files, includes `cv5_imports.py`, `relied_on_unchanged` true |
| Rollback by backup restore | all 4 files restored to "Before" |
| Reverse patch (with the flag) | also restores all 4. It is not used as the rollback method; restore from backup is |

## 7. GO / NO-GO

| # | Criterion | Now |
|---|---|---|
| 1 | Patch set, targets and manifest hashes verified; `--check` passes | GO |
| 2 | Dry run passes (tests, notebook identity, bundle, rollback) | GO |
| 3 | Companion patches 2 and 3 reviewed by a human | **NO-GO** |
| 4 | Approval policy approved and in force (`reports/cv5_approval_policy_DRAFT.md`) | **NO-GO** |
| 4a | Approval tooling accepts scopes `patch_set_application` / `amendment_01c_freeze` and checks the register and log (a reviewed patch to `kaggle/cv5_approvals.py`; not yet prepared) | **NO-GO** |
| 5 | Amendment 03 approved | **NO-GO** |
| 6 | Patch-set approval record of scope `patch_set_application`, logged | **NO-GO** |
| 7 | Kaggle session available for step 11 (owner) | not yet requested |
| 8 | Protected hashes re-verified immediately before step 1 | at execution |

**Decision: NO-GO.**

---

## Addendum 2026-10-25: approval tooling prepared (GO row 4a)
* The approval-tooling patch now exists, separate from the patch set: `patches/cv5_approvals_policy_tooling.patch` (`de92744b…`;
  target `kaggle/cv5_approvals.py` `19d83c42…`). It is **unapplied**.
* Tests: `tests/test_cv5_approval_tooling_patch.py`, 9 passed.
* Row 4a stays NO-GO until the patch is reviewed, approved and applied under the adopted policy.
