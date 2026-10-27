# Independent-reviewer checklist: approval-tooling patch

Date 2026-10-25. Companion to `reports/review/approval_tooling_review_packet_v1.md` (SHA-256
`93894ca403d4d8aa0682463affeb38096d2919162d7de1c21d7c2aff4d1ef92c`).
* This checklist is **blank**. It contains no verdict.
* Only the independent reviewer (IR) fills it in, on their own machine, and records the verdict themselves.
* The assistant does not act as the reviewer.

## A. Identity of what is reviewed (recompute every hash yourself)

| # | Check | Expected SHA-256 | Reviewer result |
|---|---|---|---|
| A1 | `patches/cv5_approvals_policy_tooling.patch` | `de92744b50c2d7f0c02add2f483bfdff5d2f514543bfcb9ba19cad1d0b0b6088` | ☐ match ☐ differs |
| A2 | Target before-state `kaggle/cv5_approvals.py` | `19d83c4251029ab937494f0c91a09e462611906452fa740cec75b435dd66d340` | ☐ match ☐ differs |
| A3 | Target after-state on a **temporary copy** (`git -c core.autocrlf=false apply` in a scratch folder) | `0221036c2ee640b84eb6cff53d0eea25bb53e103e2fe11c89bb1b624b5c21194` | ☐ match ☐ differs |
| A4 | Policy the patch encodes, `reports/cv5_approval_policy_DRAFT.md` | `1bd2a0cda953f52a70b9c61e27b31f307a2a69a1ce6f05f5a3ed2993d5e67e51` | ☐ match ☐ differs |
| A5 | Test files `tests/test_cv5_approval_tooling_patch.py` / `tests/test_cv5_approval_tooling_review_extra.py` | `ffa0693f367207c6f9e9d5f26f27426acfd67b764a1c13038ea073696a2871fc` / `f12d1fbe4e08f9bceaba8eed28e3a3c35347cd4147ab694be44423b1faf08dd3` | ☐ match ☐ differs |
| A6 | The diff touches only `kaggle/cv5_approvals.py` (one `diff --git` header; 224 lines added, 1 removed) | – | ☐ yes ☐ no |

On Windows, use `git -c core.autocrlf=false` for every apply and diff. The system git configuration converts line endings otherwise.

## B. Test evidence (re-run yourself; do not rely on the packet)

| # | Command / item | Packet states | Reviewer result |
|---|---|---|---|
| B1 | `python -m pytest tests/test_cv5_approval_tooling_patch.py tests/test_cv5_approval_tooling_review_extra.py -q` | 13 passed | ☐ ___ passed / ___ failed |
| B2 | After B1, the live `kaggle/cv5_approvals.py` is still the A2 hash (the tests patch a temporary copy only) | unchanged | ☐ yes ☐ no |
| B3 | The tests cover: no overwrite; self-countersignature (same record **and** same person under a second role); wrong scope / artifact / edited artifact; ordering (missing predecessor, before artifact, retrospective, advance); unauthorized and revoked roles; owner cannot decide clinically; superseded scope unapprovable; log tampering, duplicates and back-dating; register rules; signature claims; future dates | listed in packet §3 | ☐ adequate ☐ gaps: ______ |
| B4 | Full suite (optional) | 568 passed when the packet was prepared | ☐ ___ |

## C. Rollback procedure (packet §5)

| # | Check | Reviewer result |
|---|---|---|
| C1 | A backup of `kaggle/cv5_approvals.py` is taken **before** applying, and its hash is checked against A2 | ☐ procedure acceptable |
| C2 | Restoring the backup, or `git -c core.autocrlf=false apply -R`, returns the file to A2. **Rehearse on the scratch copy from A3.** | ☐ rehearsed, result: ______ |
| C3 | No other file needs restoring | ☐ confirmed |
| C4 | The repository has 1 commit and many uncommitted files. Rollback must not use `git checkout` / `git reset` on the working tree, because that would discard unrelated work | ☐ understood |

## D. The six documented limitations (packet §4): accept, or request changes

| # | Limitation | Reviewer judgement |
|---|---|---|
| D1 | Identity is self-asserted (signature level S0); the register limits *who may* approve, not *who did* | ☐ acceptable ☐ change needed |
| D2 | The predecessor check is shallow: the predecessor's own countersignature is not re-verified | ☐ acceptable ☐ change needed |
| D3 | `POLICY` mirrors the DRAFT policy; any policy change requires regenerating and re-reviewing the patch | ☐ acceptable ☐ change needed |
| D4 | **Unknown-scope behaviour (observation R1):** `make_approval_record` (live code, unchanged by the patch) accepts any scope string at creation. Such a record is refused at verification (`unknown approval scope`) by both `verify_approval` and `verify_approval_policy` (test `test_unknown_scope_and_future_dated_approval_are_refused`). **Explicit review item:** decide whether creation-time validation is required before adoption, or acceptable as a follow-up | ☐ acceptable as is ☐ follow-up patch ☐ blocking |
| D5 | Deleting the log file itself is not detectable without an external copy; deleting or replacing a record is detected via the log | ☐ acceptable ☐ change needed |
| D6 | `approved_at` is approver-supplied; ordering is checked against the log, not a trusted time-stamp | ☐ acceptable ☐ change needed |

## E. Policy fit

| # | Check | Reviewer result |
|---|---|---|
| E1 | The `POLICY` roles and countersigners per scope match the policy the project owner intends to adopt (policy §2 table) | ☐ yes ☐ no: ______ |
| E2 | Bootstrap: the policy-adoption and register-issue approvals cannot themselves be checked against a register that does not yet exist (policy §8); the procedure for those two records is acceptable | ☐ yes ☐ no |

## F. Verdict (completed and recorded by the reviewer only)
* Verdict: ☐ accept ☐ accept with changes ☐ reject
* Conditions / requested changes: ______
* The reviewer records their verdict with name, role, date and the A1 hash, by the means the project owner designates.
* The assistant does not create, store or sign this verdict.
