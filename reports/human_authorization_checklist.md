# Human authorization checklist (prepared; nothing signed or recorded)

Date 2026-10-25.

**Who completes it:** these actions can only be taken by the accountable project owner, in their own name. The assistant has not
signed, recorded or reserved anything, and will not use a guessed or borrowed identity.

**Before any action:** check that the ledger is unchanged:
`.venv\Scripts\python.exe -c "import hashlib;print(hashlib.sha256(open('Data/reports/test_set_ledger.json','rb').read()).hexdigest())"`
→ `f117c1a32cc0cb76b82b…` (5 entries).

## 1. Ledger disclosure: P5 (BASE test evaluation of 2026-10-16)
- [ ] Read `reports/p5_disclosure_entry.json`. Confirm it describes what happened: task classification, 73 images
      / 354 findings, evaluated 2026-10-16T11:53:27Z. `--record-disclosure` records it with kind `retrospective_disclosure`
      (`test_ledger.DISCLOSURE_KIND`).
- [ ] Confirm that you are the accountable person for test-set use in this project.
- [ ] Write a reason of at least 20 characters, in your own words. It should state that this records an evaluation that already
      happened and that no selection used it.
- [ ] Run:
  `.venv\Scripts\python.exe scripts\test_set_ledger.py --record-disclosure reports\p5_disclosure_entry.json --authorized-by "<your full name>" --reason "<your reason>"`
- [ ] Check that the ledger now has 6 entries and that `verify_chain` reports no problems.
- [ ] Note the new ledger SHA-256 in `reports/project_completion_status.md` (dated addendum).

## 2. Ledger disclosure: external-data run (BASE test evaluation of 2026-10-24)
- [ ] Read `kaggle/artifacts_external_run1/ledger_disclosure_entry.json` and confirm it.
- [ ] Run the same command with that file, your name and your reason.
- [ ] Check 7 entries and an intact chain. Neither disclosure uses the one-new-candidate test slot (kind `retrospective_disclosure`).

## 3. Amendment 01: candidate registration (with 01b: implementation freeze)
- [ ] Read `reports/cv5_amendment_01_candidate_registration.md` (§1–§7) and `reports/cv5_amendment_01b_implementation.md`.
- [ ] Decide the candidates: keep, change or drop C1 `CROP384`, C2 `PAD25`, C3 `CNXTT`. Any change before signature is free. After
      signature each registered candidate reserves a lifetime slot: 3 of 15 as proposed. Withdrawing one later still uses its slot.
- [ ] Confirm the selection statement in §5: no candidate result, no BASE-P2 result and no test data were used.
- [ ] Confirm that BASE-P2 has **not** been run. Amendment 01 must be signed before it is.
- [ ] Re-verify the 01b hashes (the §2 table) against the working copies. Do not sign if any differ.
- [ ] Fill in §8: candidate IDs, your full name, date and time (UTC) and the statement. The signature date is the registration
      timestamp used by the winner rule.
- [ ] Record the signature as a dated line in the amendment.
- [ ] No budget registry file exists yet. One is created, in the `cv5_accept.budget` format, only on your instruction after
      signature.

## 4. Later (blocked by data): Amendment 02
- [ ] Only after P2 is met by `expansion_report.py` and a manifest has been built by `build_cv5_import_manifest.py`.
- [ ] Enter the manifest SHA-256, the counts and gate V6 result in `reports/cv5_amendment_02_base_p2.md`. Authorize the notebook
      wiring change (new hashes). Sign §9.

## What signing does not do
* It does not start training. Training also needs P2 and Amendment 02.
* It does not authorize any test-set evaluation. That is allowed at most once, only after a confirmatory ACCEPT.
* It does not establish that any candidate is better. Only the complete confirmatory protocol can.
