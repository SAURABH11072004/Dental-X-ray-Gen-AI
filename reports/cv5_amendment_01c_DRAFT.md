# CV5 Amendment 01c: import-wiring implementation change (DRAFT, NOT IN FORCE, UNSIGNED)

**Status: empty draft skeleton, created 2026-10-25.**
* It is filled in only at step 9 of `reports/cv5_patch_application_plan_v2.md`.
* It may be approved only after step 12 passes, with an approval record of scope `amendment_01c_freeze` bound to the completed file.
* There is no advance and no retrospective approval.
* Nothing below has been executed, and no field may be filled with an expected or estimated value.

**Scope:** supersedes the Amendment 01b change-set entries for exactly these files:
* `kaggle/make_cv5_notebook.py`
* `tests/test_cv5_import_wiring.py`
* `tests/test_cv5_base_p2.py`
* `kaggle/build_candidate_bundle.py`

It adds candidate bundle v2. All other 01b entries stay in force.

## Required evidence (to be filled from the execution log; every field empty now)

| # | Evidence | Value |
|---|---|---|
| 1 | Pre-change inventory (execution-log entry and hash) | |
| 2 | Patch-set approval record (scope `patch_set_application`, bound to `patches/cv5_patch_set_v1.json` `55271334…`) and approval-log entry | |
| 3 | Backup hashes of the 4 files (must equal the plan's "Before" column) | |
| 4 | After-hashes of the 4 files (must equal the plan's "After" column) | |
| 5 | Full test suite result (counts; 0 failures required) | |
| 6 | LF-normalised notebook hashes (CROP384, PAD25, CNXTT, BASE, PREFLIGHT) and protected notebook raw hashes | |
| 7 | Bundle v2 zip SHA-256; manifest checks (15 files incl. `cv5_imports.py`, hashes equal, `relied_on_unchanged`); bundle v1 `8ce64d26…` unchanged | |
| 8 | Kaggle pre-flight: notebook version, "PREFLIGHT RESULT" line, log hashes | |
| 9 | Final integrity (protected hashes, pre-audit set, ledger chain, archive 88 / 88) | |

## New frozen hashes (filled only from evidence row 4 and row 7)

| File | SHA-256 |
|---|---|
| `kaggle/make_cv5_notebook.py` | |
| `tests/test_cv5_import_wiring.py` | |
| `tests/test_cv5_base_p2.py` | |
| `kaggle/build_candidate_bundle.py` | |
| `kaggle/dist/dentamind_cv5_candidate_code_v2.zip` | |
| `reports/cv5_candidate_bundle_v2_manifest.json` | |

## Approval
By approval record only (scope `amendment_01c_freeze`), after evidence rows 1–9 are complete. Nothing is entered here.
