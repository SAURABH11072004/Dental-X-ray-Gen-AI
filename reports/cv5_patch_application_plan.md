# Import-wiring patch: approval-ready application plan (D-B6; NOT EXECUTED)

Date 2026-10-25. **The patch is not applied.** This plan is executed only after an approval record of scope
`import_wiring_patch_application`, bound to the patch file, has been made by the accountable owner (DRAFT Amendment 03, D-B2).

| Item | Value now |
|---|---|
| Patch | `patches/cv5_import_wiring.patch`, sha256 `ed26e064e86d9136f6026515937b9ba26c123bfeeb94d9b843957e749e639d5d`, 1 file, 4 hunks (+57 / −7) |
| Target (frozen, Amendment 01b) | `kaggle/make_cv5_notebook.py`, sha256 `4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641` |
| Depends on | `kaggle/cv5_imports.py` `f9c061cb…` (shared import cell, `check_import_params`) |
| Historical candidate bundle | `kaggle/dist/dentamind_cv5_candidate_code_v1.zip` `8ce64d26…` (must stay unchanged) |

## Preconditions (all, or stop)
1. **Approval verifies:**
   `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'kaggle'); import cv5_approvals as A; print(A.verify_approval('<record.json>', 'patches/cv5_import_wiring.patch', 'import_wiring_patch_application'))"`
2. **Patch and target are the reviewed versions:** `sha256sum patches/cv5_import_wiring.patch kaggle/make_cv5_notebook.py` equals
   the table above.
3. **Patch applies cleanly:** `git apply --check patches/cv5_import_wiring.patch`. If anything is out of place, stop; never hand-merge.
4. **Clean baseline:**
   - full suite passes (currently 524);
   - record the hashes of every candidate notebook generated today for `CROP384`, `PAD25` and `CNXTT`, with imports off. Step 5 needs
     them.

## Application
5. **Capture the baseline:** generate the three candidate notebooks with imports off **before** applying, into a scratch folder, and
   record their SHA-256 values. Also record the BASE notebook hash (`dd65c7c7…`).
6. **Apply exactly the reviewed patch:** `git apply patches/cv5_import_wiring.patch`. No other edit to the frozen file.
7. **Recalculate hashes:**
   - `kaggle/make_cv5_notebook.py` (new hash);
   - every other 01b change-set file, which must be unchanged except the generator.

   Record them in a dated Amendment 01c (implementation change), which takes effect through its own approval record.
8. **Byte-identical imports-off output:**
   - regenerate the three candidate notebooks with imports off, and require their SHA-256 to equal step 5;
   - regenerate the BASE notebook (`dd65c7c7…`) and the pre-flight notebook. The pre-flight notebook embeds files and candidate cell
     hashes, so its hash changes only if its inputs changed; check and record.
9. **New candidate bundle version:** `.venv\Scripts\python.exe kaggle\build_candidate_bundle.py --version 2 --manifest-out reports\cv5_candidate_bundle_v2_manifest.json`.
   - The builder refuses to overwrite.
   - It checks `dentamind_kaggle.py` / `dsutil.py` against bundle v3.
   - v1 stays byte-identical.
10. **Full test suite:**
    - In `tests/test_cv5_import_wiring.py`, the tests that apply the patch to a temporary copy must be replaced by tests on the real
      generator. They assert the frozen hash `4a5efda8…`, so they will fail by design until updated in the same dated change.
    - Everything else must pass.
11. **Kaggle no-training pre-flight:**
    - repeat it with the regenerated pre-flight notebook, no input attached and Internet off;
    - require PASS (150 / 150 or the updated count);
    - record the log hashes.
12. **Integrity re-check:**
    - pre-audit set 8 / 8;
    - protocol `0771b5f8…`;
    - ledger `f117c1a3…`;
    - archive 88 / 88;
    - historical bundles `9d070fc7…` / `8ce64d26…`;
    - BASE notebook / code unchanged.

## Rollback
* If any check in steps 7–12 fails, revert the generator to the reviewed hash (`git apply -R patches/cv5_import_wiring.patch`, then
  confirm `4a5efda8…`) and stop.
* Delete only files created in this attempt. Bundle v2 is created only after every check before it has passed.
* Record the failure; do not retry with modifications.

## What this does not do
It does not:
* make imports available;
* register BASE-P2;
* train anything;
* touch the test set.

Imports still need P2 data, reviewer authorization v1 (blocked by D-B5), a manifest, a V6 record and signed Amendments 01 / 02.

---

## Addendum 2026-10-25: verification review of this plan (dry run; nothing applied)

* **Dry run.** Done on a scratch copy outside the repository, with git confined by `GIT_CEILING_DIRECTORIES`:
  - the patch applies;
  - the patched generator would hash `d15b1a55d959ff8e8079a8e7480c57b059f49cf866fee03ed7987f9e64ea969e`;
  - the imports-off notebooks for CROP384, PAD25, CNXTT and BASE are byte-identical before and after;
  - `git apply -R` restores `4a5efda8…`.

  The real generator was not touched.
* **Corrections to the steps above.** They supersede the earlier wording where it differs; details are in
  `reports/cv5_approval_checklist_amendment03_and_patch.md` §6.
  1. Byte-identity is checked either on files written by the generator's own writer on the same OS (CRLF on Windows), or on
     LF-normalised serialisations. The two methods are never mixed.
  2. Step 10 (full test suite) runs before step 9 (candidate bundle v2).
  3. Before step 6, back up the frozen generator to scratch and record its hash. Rollback is `git apply -R` or a restore from the
     backup, verified by `4a5efda8…`.
  4. In the same dated change, update the tests that pin the frozen hash: `test_cv5_base_p2.py` and `test_cv5_import_wiring.py`.
     Supersede the 01b change-set table with Amendment 01c.
  5. BASE-P2 registrations are made only after the patch decision, with the generator hash then current.

---

## Addendum 2026-10-25 (2): SUPERSEDED
This plan and its first addendum are superseded in full by `reports/cv5_patch_application_plan_v2.md`. Kept unchanged as history.
