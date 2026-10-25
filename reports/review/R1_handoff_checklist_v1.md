# R1 handoff checklist: independent review of the approval-tooling patch

Date 2026-10-25.
* **Prepared for:** the project owner (sender) and the independent reviewer (IR, recipient).
* **Nothing has been sent.** The owner chooses the reviewer and the transfer method.
* **No verdict exists.** The assistant does not create one and does not act as the reviewer.

## 1. Handoff package: send these files only

| # | File | SHA-256 |
|---|---|---|
| H1 | `patches/cv5_approvals_policy_tooling.patch` | `de92744b50c2d7f0c02add2f483bfdff5d2f514543bfcb9ba19cad1d0b0b6088` |
| H2 | `kaggle/cv5_approvals.py` (before-state) | `19d83c4251029ab937494f0c91a09e462611906452fa740cec75b435dd66d340` |
| H3 | `tests/test_cv5_approval_tooling_patch.py` | `ffa0693f367207c6f9e9d5f26f27426acfd67b764a1c13038ea073696a2871fc` |
| H4 | `tests/test_cv5_approval_tooling_review_extra.py` | `f12d1fbe4e08f9bceaba8eed28e3a3c35347cd4147ab694be44423b1faf08dd3` |
| H5 | `reports/cv5_approval_policy_DRAFT.md` | `1bd2a0cda953f52a70b9c61e27b31f307a2a69a1ce6f05f5a3ed2993d5e67e51` |
| H6 | `reports/review/approval_tooling_review_packet_v1.md` | `93894ca403d4d8aa0682463affeb38096d2919162d7de1c21d7c2aff4d1ef92c` |
| H7 | `reports/review/independent_reviewer_checklist_v1.md` (blank) | `1a8acf39962ff1b4573d8a0d1ff9cb242e989d2b46804b0f439a1b3d32ae1c27` |

* **Keep the folder layout:** `kaggle/`, `patches/`, `tests/` and `reports/`.
* **Verified minimal:** on 2026-10-25, H1–H4 alone, copied to an empty folder, gave **13 passed**, and the copied H2 stayed unchanged.
  The run used `python -m pytest tests -q -o addopts=""`, with Python and pytest, plus git on PATH.
* **Do not send** a copy of the repository or working tree. It contains the restricted clinical-review files
  (`reports/security/clinical_files_access_control_plan_PROPOSED.md` §1), and the reviewer does not need them.
* H1–H7 contain no clinical data.
* The patch is **not** on the public GitHub repository (it is untracked), so it must be transferred directly.

## 2. Sender steps (project owner)
- [ ] Choose the IR: a person other than the patch author, with no conflict of interest. Record the choice yourself.
- [ ] Recompute H1–H7 hashes immediately before sending, and include this table in the message.
- [ ] Send the files by a channel the institution accepts. The assistant does not send them.
- [ ] Ask the IR to report the verdict bound to H1's hash (§4).

## 3. Reviewer steps (IR; summary of the blank checklist H7)
- [ ] **Independent hash verification:** recompute H1–H7. Any mismatch means stop and report it.
- [ ] **Clean-room apply:** in an empty folder, apply H1 to H2 with `git -c core.autocrlf=false apply`. The after-hash must be
  `0221036c2ee640b84eb6cff53d0eea25bb53e103e2fe11c89bb1b624b5c21194`.
- [ ] **Test re-run:** `python -m pytest tests -q -o addopts=""`. Expect 13 passed. Record the counts you actually observe.
- [ ] **Rollback rehearsal:** `git -c core.autocrlf=false apply -R` on the clean-room copy must restore H2's hash.
- [ ] **Read the diff in full:** one file only; 224 lines added and 1 removed.
- [ ] **Known limitations:** judge all six (H7 §D). For D4, the unknown-scope behaviour, explicitly choose accept, follow-up or
  blocking:
  - `make_approval_record` accepts any scope string at creation;
  - verification then refuses it (`unknown approval scope`).
- [ ] **Policy fit:** `POLICY` roles and countersigners match the policy the owner intends to adopt (H5 §2), including the bootstrap
  (H5 §8).

## 4. Hash-bound verdict record (fields only; filled in by the IR, never by the assistant)

| Field | Content |
|---|---|
| Artifact reviewed | `patches/cv5_approvals_policy_tooling.patch` |
| Artifact SHA-256 | (IR copies the hash they computed; it must equal H1) |
| Target before / after SHA-256 | (IR's own computed values) |
| Tests observed | (IR: passed / failed counts and environment) |
| Limitations D1–D6 | (IR's judgement per item; D4 explicit) |
| Verdict | accept / accept with changes / reject |
| Conditions | |
| Reviewer name and role | |
| Date | |
| Signature or record method | as designated by the project owner. Until the approval tooling is in force, this is an S0 statement: it records what was said, not who said it |

**After the verdict:**
* the owner decides on R2 (policy adoption) and R4 (apply the patch);
* nothing is applied on the basis of an unrecorded or unbound verdict.
