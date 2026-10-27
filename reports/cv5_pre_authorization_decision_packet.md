# Pre-authorization audit and decision packet: CV5 import wiring (NO approval recorded; patch NOT applied)

Date 2026-10-25. Every value in §1 was **recomputed in this audit**. Values quoted from earlier reports are marked "reported".

## 1. Integrity findings (verified now)

| Check | Result |
|---|---|
| Frozen generator `kaggle/make_cv5_notebook.py` | `4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641` (unchanged) |
| Patch `patches/cv5_import_wiring.patch` | `ed26e064e86d9136f6026515937b9ba26c123bfeeb94d9b843957e749e639d5d`; `git apply --check` passes; 1 file, +57 / −7; **not applied** |
| Amendment 01b change set (12 files) / pre-audit set (8 files) | 12 / 12 OK / 8 / 8 OK |
| Approved protocol / revision 2 proposal | `0771b5f8…` / `98d6e223…` |
| Ledger | `f117c1a3…`, 5 entries, `verify_chain` → no problems |
| CV5 archive / SHA256SUMS | zip `4ac56843…`, 88 / 88 entries OK |
| Bundles | data bundle v3 `9d070fc7…`; candidate code v1 `8ce64d26…`; no v2 exists |
| BASE notebook / `cv5_lib.py` / `dentamind_kaggle.py` / `dsutil.py` | `dd65c7c7…` / `72084f9b…` / `879faa93…` / `debeb7f0…` |
| Repository | 1 commit; 21 modified tracked files (the pre-existing set); 44 untracked entries; no approval record, reviewer authorization, import manifest or BASE-P2 registration file exists |
| Tests | **524 passed, 0 failed**. Approvals 12, BASE-P2 24, reviewer authorization 12, import wiring 14, imports 22, interventions 17, candidate runs 26, acceptance 21, CV5 22, ensemble 21 |
| Scratch dry run (reported, previous step; not re-run) | patch applies; imports-off notebooks byte-identical; `git apply -R` restores the frozen hash |

## 2. Consistency audit of `reports/cv5_patch_application_plan.md` (`009c33ae…`)

| Point | Status in the plan | Finding |
|---|---|---|
| Windows line endings | addendum item 1 | covered by the addendum; the main steps 5 / 8 still do not name a method (superseded, not consolidated) |
| Original generator backup | addendum item 3 | covered; the main Rollback section still names only `git apply -R` |
| Reverse-patch rollback | Rollback + addendum | covered for the generator. **Gap A:** rollback does not say that test edits and any Amendment 01c draft made in the attempt are also reverted |
| Pinned-hash test updates | step 10 + addendum item 4 | **Gap B:** these test edits (`tests/test_cv5_import_wiring.py`, whose fixture can no longer apply the patch, and `tests/test_cv5_base_p2.py`) are **not part of the reviewed patch**. Applying them would be an unreviewed change. They need their own reviewed patch, approved with the generator patch |
| Amendment 01c | step 7 | **Gap C:** the plan drafts 01c at step 7 but does not say it is approved only **after** steps 8–12 pass |
| Test ordering | addendum item 2 | covered (tests before bundle v2); the main list still shows 9 before 10 |
| Candidate bundle v2 | step 9 | **Gap D:** `kaggle/build_candidate_bundle.py` FILES does not include `kaggle/cv5_imports.py`, which the patched generator embeds in import mode. Bundle v2 would be incomplete unless that list changes (a frozen-file change, to be reviewed in the same package) |
| Regeneration in step 8 | step 8 | **Gap E:** `make_cv5_notebook.main()` writes to `kaggle/dentamind_5fold_cv.ipynb`, and the pre-flight generator writes to `kaggle/dentamind_cv5_preflight.ipynb` by default. Both are protected / frozen files. Regeneration must go to a scratch path (`_notebook(...)` serialisation, or the pre-flight generator's `out` argument) and be compared, never written over the originals |
| Delayed BASE-P2 registration | addendum item 5 | covered |

**Conclusion:** the plan is not yet internally consistent. Gaps A–E must be resolved in a consolidated revision of the plan (and, for B and D,
reviewed patches) before it can be approved.

## 3. Remaining approvals

| # | Approval | Responsible role | Artifact to check (exact SHA-256 now) | Stop condition if verification fails |
|---|---|---|---|---|
| 1 | Ledger disclosure P5 | accountable person, own name | `reports/p5_disclosure_entry.json` `c8f9b186fe7c6acbdf28f0c69905336385437ab4bb0f554a84c913b2725e65c1`; ledger `f117c1a3…` | hash differs, or ledger chain not intact → do not record |
| 2 | Ledger disclosure, external-data run | accountable person, own name | `kaggle/artifacts_external_run1/ledger_disclosure_entry.json` `910835882c223b67fe253aabafdcb9064166a38c330fae022b99f6f788ead6be` | same |
| 3 | Approval-mechanism policy G1 (who may approve which scope), G2 (signature policy), G3 (time ordering), G5 (approval log), G7 (governance scope) | project owner | `reports/cv5_approval_checklist_amendment03_and_patch.md` `9346fce28165dac5bf19b29051c007f0cae6960577cad071c35aa4da426d13c9` | until decided, no approval record proves authority → no record is relied on |
| 4 | Amendment 03 (D-B1 … D-B6) | project owner | `reports/cv5_amendment_03_decisions_DB1_DB6.md` `d80654d18e4ac28ce1e0b5f59181fef4869332696e0d48d56089af2b19407b89` | hash differs → re-review the changed text |
| 5 | BASE-P2 failure policy F1–F6 | project owner | `reports/cv5_decision_base_p2_failure_policy.md` `3591c0b3c1cd40b5e92d2baf95f3df512e3559f4e6e16fb886f8202c6876dbfe` | **pending**; no choice made by the assistant |
| 6 | Clinical governance (qualifications, labelling standard, second reader, adjudication, documentation / authorization) | named clinical lead, countersigned by the owner | template `reports/templates/clinical_governance_decision_template.md` `baa284b8cde48df6626e589d91cd81f8b4de0d721a1c11f98ca454bcb1d84ab7` (completed copy to be hashed) | **pending**; blocked by G7 (no approval scope yet). No reviewer authorization may be issued until then |
| 7 | Consolidated patch plan + test-update patch + bundle file-list change (gaps A–E) | project owner | not yet written: **unverified** | no revision exists → no patch application |
| 8 | Apply the import-wiring patch (D-B6) | project owner | patch `ed26e064…`; target `4a5efda8…` | either hash differs, `git apply --check` fails, or items 4 / 7 not approved → stop |
| 9 | Amendment 01 (candidate registration) | project owner | `reports/cv5_amendment_01_candidate_registration.md` `ce9d0c9c944a69e2c17680dce9ac77d569bb79870f4e7815937a8b3003b36687` | hash differs → re-review |
| 10 | Amendment 01b (implementation freeze) | project owner | `reports/cv5_amendment_01b_implementation.md` `2fb847e15a27533a1c980d4a8b05f55c225febe25a92156f8fd65c70bc9b6b44` and its 12-file set (12 / 12 OK now) | any file differs → stop |
| 11 | Amendment 02 / BASE-P2 registration | project owner | `reports/cv5_amendment_02_base_p2.md` `bf8b7e5515e93d0ca08418adc5baa693366d0001125819ef950717c63e53d8e8` | blocked by data (P2) and by items 6, 8 |

## 4. Go / no-go for the patch

| Criterion | Now |
|---|---|
| Patch and target are the reviewed hashes; `git apply --check` passes | **GO** |
| Full suite passes before application | **GO** (524 / 524) |
| Imports-off byte-identity demonstrated (scratch dry run) | **GO** (reported; repeat at execution) |
| Plan internally consistent (gaps A–E resolved) | **NO-GO** |
| Test-update patch and bundle file-list change reviewed | **NO-GO** (not written) |
| Approval mechanism policy decided (G1–G3) | **NO-GO** |
| Amendment 03 approved | **NO-GO** |
| Patch application approved by the owner, by record | **NO-GO** |
| Protected files verified immediately before applying | to be repeated at execution |

**Decision: NO-GO.** The patch must not be applied now.

## 5. Exact next human action
The **project owner** decides the approval-mechanism policy (G1, G2, G3, G5, G7 in
`reports/cv5_approval_checklist_amendment03_and_patch.md` §2–§3) and names the clinical lead.

Independently, the accountable person can record the two ledger disclosures in their own name
(`reports/human_authorization_checklist.md` §1–§2), after checking the two hashes in §3 rows 1–2. Nothing else unblocks safely
before these.

## 6. Confirmation
* `kaggle/make_cv5_notebook.py` is unchanged (`4a5efda8…`). The patch is not applied.
* No approval record, reviewer authorization, import manifest, registration or signature was created.
* No ledger disclosure was recorded and no candidate slot reserved.
* No data request was sent, no model trained, BASE-P2 not run, and the test set not touched. No commit.
* Real-data validity is unverified.

---

## Addendum 2026-10-25: defects A–E addressed in plan v2 (NO-GO unchanged)
* **Plan:** `reports/cv5_patch_application_plan_v2.md`, with the patch set `patches/cv5_patch_set_v1.json`.
* **Patch regenerated:** the wiring patch was regenerated byte-exact, `33ec47e6…`. It supersedes `ed26e064…` and gives the identical
  resulting generator, `d15b1a55…`.
* **New patches:**
  - `patches/cv5_test_pin_update.patch` `5e406287…`;
  - `patches/cv5_bundle_builder_imports.patch` `31a2ba15…`.
* **New finding:** the system git config sets `core.autocrlf=true`. Every apply, check and reverse must therefore use
  `git -c core.autocrlf=false`.
* **Draft approval policy:** `reports/cv5_approval_policy_DRAFT.md`.
