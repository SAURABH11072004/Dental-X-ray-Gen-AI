# Approval checklist: Amendment 03 and the import-wiring patch (prepared; NO approval recorded)

Date 2026-10-25.
* **No approval record exists in the repository** (searched: no `*approval*.json`).
* The patch is not applied; Amendment 03 is not in force.
* Only the named human roles can complete the steps below.

## 1. Artifacts to approve (hashes recomputed 2026-10-25)

| Artifact | SHA-256 | Approval scope |
|---|---|---|
| `reports/cv5_amendment_03_decisions_DB1_DB6.md` | `d80654d18e4ac28ce1e0b5f59181fef4869332696e0d48d56089af2b19407b89` | `amendment_03_decisions` |
| `patches/cv5_import_wiring.patch` (unapplied) | `ed26e064e86d9136f6026515937b9ba26c123bfeeb94d9b843957e749e639d5d` | `import_wiring_patch_application` |
| Target `kaggle/make_cv5_notebook.py` (frozen) | `4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641` | — (must equal this before applying) |
| `kaggle/cv5_approvals.py` (verifier) | `19d83c4251029ab937494f0c91a09e462611906452fa740cec75b435dd66d340` | — |

Approving Amendment 03 as written also records the open decisions as open. The choices in
`reports/cv5_decision_base_p2_failure_policy.md` (F1–F6) and the clinical template (D-B5) are separate approvals of later versions.

## 2. Gaps in the approval mechanism (found by inspection and an executed probe; not fixed here)

| # | Gap | Effect | Needs |
|---|---|---|---|
| G1 | Approver name and role are **self-asserted**; there is no approver register or role-to-scope rule | a record by anyone in any role verifies (probe: role "intern" accepted for `reviewer_authorization_issue`) | owner decision: who may approve which scope (table §3), then a versioned approver register and a code check |
| G2 | **Authenticity:** `content_sha256` is tamper-evident only; anyone can create, or re-hash, a record in someone's name | not proof of who approved | owner decision: accept procedural records kept under version control / a write-once log, or adopt real digital signatures (verification not available today) |
| G3 | **No time ordering:** `approved_at` is checked only for not being in the future | a record dated before the artifact existed verifies (probe: 1999 accepted) | rule: approval after artifact creation, and sequencing (01 before BASE-P2 registration, etc.) |
| G4 | Binding is by **content hash**, not path | identical bytes at another path verify | acceptable by design; stated |
| G5 | **No register / supersession / revocation** of approval records | conflicting records for one artifact cannot be resolved | an append-only approval log (decision) |
| G6 | Ledger disclosures use the ledger's own authorizer field, not approval records | two mechanisms | intentional; unchanged |
| G7 | No scope for approving the clinical-governance document | it cannot be approved by record | add a scope (code + amendment) or a different mechanism (decision) |

Until G1–G3 are decided, an approval record is evidence of a statement, not proof of authority or identity.

## 3. Remaining decisions and responsible approving role

| Decision | Responsible role | Document |
|---|---|---|
| Accept / modify Amendment 03 (D-B1 … D-B6) | Project owner | `reports/cv5_amendment_03_decisions_DB1_DB6.md` |
| BASE-P2 failure policy F1–F6 | Project owner | `reports/cv5_decision_base_p2_failure_policy.md` |
| Reviewer qualifications, labelling standard, second reader, adjudication, documentation (D-B5) | Clinical lead (named by the owner), countersigned by the owner | `reports/templates/clinical_governance_decision_template.md` |
| Who may approve which scope (G1), signature policy (G2), ordering rules (G3), approval log (G5), governance scope (G7) | Project owner | this checklist |
| Apply the wiring patch (D-B6) | Project owner | `reports/cv5_patch_application_plan.md` |
| Ledger disclosures (two) | Accountable person, own name | `reports/human_authorization_checklist.md` |
| Amendment 01 (candidates) / Amendment 02 (BASE-P2) signatures | Project owner | amendment drafts |
| Data requests, reviewer registration | Project owner / clinical lead | `reports/data_request_checklist.md` |
| Whether the academic guide must also approve any of the above | Project owner / institution | institutional rules (not known to the assistant) |

## 4. Approval steps (performed by the approver; the assistant does not run step 2 with a real identity)
1. **Verify the artifact** is the reviewed version: `sha256sum <artifact>` must equal §1. If it differs, stop.
2. **The approver creates their own record:**
   ```
   .venv\Scripts\python.exe -c "import sys,json; sys.path.insert(0,'kaggle'); import cv5_approvals as A; r=A.make_approval_record('<scope>', '<artifact path>', '<your full name>', '<your role>', '<your statement, at least 20 characters>'); open('<record path>','x',encoding='utf-8').write(json.dumps(r, indent=1))"
   ```
   Opening with `'x'` refuses to overwrite an existing record.
3. **Verify:**
   ```
   .venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'kaggle'); import cv5_approvals as A; print(A.verify_approval('<record path>', '<artifact path>', '<scope>'))"
   ```
4. **Record** the record path and its SHA-256 in the dated approval section of the artifact's companion document, as an addendum.
   Never edit the approved artifact itself; that would change its hash and invalidate the record.

## 5. Stop conditions
* The artifact hash differs from §1, or the patch target is not `4a5efda8…`.
* `verify_approval` raises anything.
* Any protected-file check fails:
  - pre-audit set 8 / 8;
  - protocol `0771b5f8…`;
  - ledger `f117c1a3…`, 5 entries, chain intact;
  - archive 88 / 88;
  - bundles `9d070fc7…` / `8ce64d26…`;
  - BASE notebook `dd65c7c7…`.
* The full test suite does not pass (currently 524).
* An approval would be made by someone other than the responsible role in §3. Until G1 is decided, this is a human check.

## 6. Verification of the patch application plan (dry run on a scratch copy; real generator untouched)

Executed 2026-10-25 outside the repository (`GIT_CEILING_DIRECTORIES` set, so git never touched the enclosing repository):

| Plan condition | Result |
|---|---|
| Patch applies to the frozen generator | yes; patched generator would hash `d15b1a55d959ff8e8079a8e7480c57b059f49cf866fee03ed7987f9e64ea969e` |
| Imports-off notebooks byte-identical (CROP384, PAD25, CNXTT, BASE) | **identical** before and after. LF-serialised SHA-256: CROP384 `d47727b6…`, PAD25 `5e52a6b0…`, CNXTT `e6e57c38…`, BASE `31ffc3ef…` |
| Rollback `git apply -R` restores the frozen file | yes, `4a5efda8…` restored exactly |

**Corrections the plan needs** (recorded as an addendum to the plan; not yet applied to anything):
1. **Byte-identity method.** The generator's writer produces CRLF files on Windows: the BASE notebook file `dd65c7c7…` equals the CRLF
   form of the LF serialisation `31ffc3ef…`. Compare either files written by the same writer on the same OS, or LF-normalised
   serialisations. Never mix the two.
2. **Order.** Run the full test suite (plan step 10) **before** building candidate bundle v2 (step 9), so a failed test never leaves a
   bundle behind.
3. **Backup.** Before step 6, copy the frozen generator to a scratch backup and record its hash. Rollback is `git apply -R` **or**
   restoring the backup, followed by the `4a5efda8…` check.
4. **Tests that pin the frozen hash** must be updated in the same dated change:
   - `tests/test_cv5_base_p2.py::test_frozen_files_and_base_notebook_unchanged`;
   - `tests/test_cv5_import_wiring.py` (`FROZEN_SHA`; its fixture applies the patch to a copy, which cannot apply to an
     already-patched file);
   - the Amendment 01b change-set table, superseded by Amendment 01c.
5. **BASE-P2 registrations** list the generator's hash in `code_sha256`. Any BASE-P2 registration must be made **after** the patch
   decision, with the hash then current.
