# Decision record: BASE-P2 failure policy (OPEN; nothing decided here)

Date 2026-10-25. **Responsible approving role: the accountable project owner.** Proposals are drafts until approved through a human
approval record (DRAFT Amendment 03, D-B2). No option below has been chosen.

## A. Existing requirements, approved protocol revision 3 (`reports/cv5_acceptance_protocol.md`, `0771b5f8…`)

These are in force and are quoted from the protocol, not reinterpreted:
* **§3.2:** BASE-P2 is a reference run, not a candidate. It is never ACCEPTED and does not count toward the budget. Order:
  1. candidate registration;
  2. BASE-P2 registration;
  3. BASE-P2 run;
  4. gate R on BASE-P2 in the candidate environment;
  5. candidate training.
* **§4.3:** stored reference predictions may be reused only if the fold file is byte-identical **and** gate R passes in the candidate
  environment. If either fails, it is "a validity failure before candidate training"; "training does not start until the cause is
  found, documented and resolved by a dated amendment"; "no budget slot is used".
* **§9:** run classes (infrastructure, divergence, incomplete) and retries (infrastructure only, up to 3 attempts in total) are
  defined for **candidate** runs. The protocol does **not** state how a failed **reference** (BASE-P2) run is handled.
* **§9, other events:** "Bug found after results are seen: fix it, write a dated amendment, rerun the whole candidate, and report both
  runs." This applies to candidates. BASE-P2 has no equivalent.

**Consequence without any amendment:** a BASE-P2 that is not complete leaves no valid comparator. §4.3 then prevents candidate training,
because stored reference predictions cannot be reused and gate R cannot pass for missing runs. What to do next is **unspecified**.

## B. Proposed amendment (DRAFT Amendment 03, D-B4; NOT IN FORCE)
* BASE-P2 serves as comparator only if all 25 runs are classified `ok` (`cv5_approvals.check_base_p2_complete`).
* Retries are exactly those of §9, as implemented in `cv5_accept.run_isolated`. No new retry behaviour.
* A failed BASE-P2 is not repaired in place, resumed into a different configuration, or partially reused.
* Proceeding needs:
  - an approval record of scope `base_p2_failure_resolution` bound to the failed `run_status.json`;
  - then a new BASE-P2 registration (`attempt = N + 1`) citing both hashes.

  Both attempts are reported.
* Implemented and tested on synthetic fixtures: `kaggle/cv5_approvals.py`, `kaggle/make_base_p2_notebook.py`;
  `tests/test_cv5_approvals.py` and `tests/test_cv5_base_p2.py`.

## C. Open decisions (owner to choose; the assistant does not choose)

| # | Question | Options (not ranked) | Considerations |
|---|---|---|---|
| F1 | How many BASE-P2 attempts are allowed before the import programme stops? | (a) one re-attempt; (b) a fixed maximum N; (c) no limit, each needing an approved resolution | every attempt runs on the same 541 evaluation radiographs; sealing (D-B3) limits what is learned from a failed attempt |
| F2 | What happens when the cap is reached? | (a) stop imports, and run candidates only against CV5-BASE run 1 without imports (§4.2 allows that comparator); (b) stop the CV5 candidate programme; (c) a new protocol revision | (a) changes the training data of every candidate (no imports) and needs Amendment 01 to name CV5-BASE run 1 as comparator |
| F3 | Is a **divergence** of BASE-P2 (the unchanged BASE recipe) treated differently from an infrastructure exhaustion? | (a) same handling; (b) divergence requires a root-cause report before any re-attempt | a divergence of the unchanged recipe after adding imports may point to the imported data |
| F4 | Do the sealed metrics of a failed attempt stay sealed permanently? | (a) yes; (b) released only together with the successful attempt's release | prevents a failed attempt informing later choices |
| F5 | Is a re-attempt allowed to change the imports manifest? | (a) no, same manifest; (b) yes, with a new Amendment 02 and V6 record | (b) turns the re-attempt into a different reference |
| F6 | Do registered candidates keep their reservations while BASE-P2 is being resolved? | (a) yes (current draft); (b) the owner may withdraw them; under §9 a withdrawal counts as a used slot | §9 says withdrawal counts as used "because reference results may be visible after registration" |

## D. Approval (to be completed only by the owner through an approval record; nothing entered)

| Field | Entry |
|---|---|
| Choices for F1 to F6 | |
| Approval record file and SHA-256 (scope `amendment_03_decisions`, bound to the amendment version that records the choices) | |
