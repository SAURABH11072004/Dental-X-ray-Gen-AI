# Decision memo DRAFT: how matching rule M1 may be evaluated (Option A vs Option B)

Date 2026-10-25. For the project owner. **No decision is made here, and nothing has been executed.**

| Document | SHA-256 |
|---|---|
| Protocol `reports/cv5_acceptance_protocol.md` (revision 3; status line "APPROVED") | `0771b5f8…` |
| Registration draft `reports/cv5_matching_rule_registration_DRAFT.md` | `b2160a35…` |

## 1. Correction to the registration draft
The registration draft recommends Option A because it "uses no slot of the 15" and "leaves that frame untouched". **That reasoning is
incomplete.** Using no budget slot does not make an analysis permitted. The protocol provisions quoted below restrict any evaluation
on the CV5 population, whatever its budget status. A dated addendum to the registration draft points to this memo.

## 2. Protocol provisions that decide the question (quoted exactly)

| # | Section | Text | Bearing on M1 |
|---|---|---|---|
| Q1 | §2 scope | "**Applies to** any candidate finding classifier proposed to replace BASE, evaluated by grouped 5-fold CV of the DENTEX training/validation radiographs on `cv5_folds_v1.csv`." | M1 changes no classifier; whether it is a "candidate" under this protocol is not settled by the text |
| Q2 | §2 scope | "**Out of scope (each needs its own protocol):** * tooth-detector changes; …" | the closest listed category; a matching rule is a detection-stage change, so by analogy it needs **its own protocol**, not this protocol's verdicts |
| Q3 | §3 | "**No exploratory candidate runs on the CV5 evaluation population.** – No candidate configuration is trained or evaluated on the 541 primary radiographs of `cv5_folds_v1.csv` (or their folds) except as a registered confirmatory candidate." | **the decisive restriction.** If M1 is a "candidate configuration", evaluating it on the 541 radiographs is allowed **only** as a registered confirmatory candidate |
| Q4 | §3 | "**Confirmatory comparisons** are the only ones that can yield ACCEPT. They start only when P2 is met." and "**No confirmatory comparison can start today** (0 clinician-verified imports)." | Option B is **blocked by data** (P2) regardless of approvals |
| Q5 | §3 categories | "A3 Exploratory \| the §7.1 analyses, and the BASE-P2 vs CV5-BASE run 1 comparison \| hypotheses only; never ACCEPT, promotion or test use, and never input to first-round candidate selection" and "A result can never be relabelled into a stricter category." | an exploratory M1 result could never become evidence of improvement, and could not inform candidate choice |
| Q6 | §7.1 | "Exploratory analyses (never part of the verdict)", listing per-fold tables, confusion analyses, subsets, external evaluations, abstention counts, temperature scaling, "Any undeclared subgroup" and BASE-P2 vs run 1 | **matching rules are not listed**; adding M1 as exploratory needs an amendment |
| Q7 | §4.1 | "the candidate uses exactly the reference's evaluation frame: … the same detector boxes (`detector_boxes_pool.json` of the reference run) and the same matching (IoU ≥ 0.5, one-to-one)" | a confirmatory M1 candidate contradicts the frame; Option B must amend §4.1 for that family |
| Q8 | §6 | families F1 crop / input, F2 architecture, F3 training data, F4 loss / sampling / augmentation, F5 ensembling | no family covers matching; Option B needs a new family |
| Q9 | §10.1 | "**Lifetime budget: 15 candidate configurations.** … Only a recorded owner decision can enlarge it; an enlargement is disclosed in every later report and requires a new multiplicity amendment before any further candidate runs." | Option B: budget 15 → 16 and k = 16 for P-B, affecting every later candidate |
| Q10 | §3.2 | "All first-round candidates are registered, with frozen configurations, **before BASE-P2 is run**" | Option B M1 would have to be registered with the first round, before BASE-P2 |
| Q11 | §5.2 | "any later recalibration needs a new, prospectively registered protocol." | general principle: changes to the evaluation machinery are made prospectively, by protocol |

## 3. The options, re-stated against Q1–Q11

| | **A1 – own protocol** (matching evaluated as an out-of-scope pipeline change, by analogy with Q2) | **A2 – exploratory amendment** (add M1 to §7.1) | **B – confirmatory family F6** |
|---|---|---|---|
| Needs | a new, separately approved protocol for matching rules, plus an owner decision that M1 is **not** a "candidate configuration" under Q3 | a protocol amendment adding M1 to §7.1 (A3) | amendments to §4.1 (frame), §6 (family F6) and §10.1 (budget 16, k = 16); registration with the first round (Q10) |
| Can run when | after the new protocol and decision are approved; no P2 dependency **if** the owner's Q3 decision holds | after the amendment; no P2 dependency (A3 is not confirmatory) | only after P2 is met (Q4): **not possible today** |
| What it can show | a verdict under its own rules, about the **pipeline**, never "ACCEPT under the CV5 acceptance protocol" | **hypotheses only**; never an improvement claim; not usable to choose first-round candidates (Q5) | ACCEPT / FAIL / NO VERDICT under the CV5 protocol |
| Multiplicity | its own (the draft proposes one primary test at α = 0.05); disclosed as separate | none (no test for success) | Bonferroni over k = 16 for **all** later candidates |
| Main risk | Q3 conflict: a reviewer may read M1 as a "candidate configuration" evaluated outside the confirmatory route | low evidential value | delays; changes the multiplicity level of the whole programme |
| Fit with the registration draft | the draft's §4–§7 design can be reused as the new protocol; its "IMPROVED" wording is acceptable only under A1 | the draft's decision rule must be removed (exploratory, no verdict) | the draft's design must be replaced by the CV5 criteria (P-A to P-D, S1–S7, H) |

## 4. Questions only the owner can answer
1. **Q3 interpretation:** is a matching rule that changes no classifier a "candidate configuration" in the sense of §3? The text does
   not settle it. If yes, A1 is not available and the choice is A2 or B.
2. If A1: approve a separate protocol for pipeline (detection / matching) changes, as Q2 envisages for detector changes. Who reviews
   it?
3. If A2: accept that the result is a hypothesis only, and cannot be used to select first-round candidates.
4. If B: accept the budget and multiplicity change (Q9), the §4.1 amendment, and the P2 wait (Q4).

## 5. Assistant's assessment (non-binding)
* **A2 is the only option that is clearly compatible** with the current protocol text after one amendment. It yields no improvement
  claim.
* **A1 is the most informative**, but it depends on the owner's Q3 interpretation. It should be decided explicitly, in writing,
  **before** any M1 outcome is known.
* **B is blocked today** (P2) and is costly for the programme's multiplicity.
* Whatever is chosen, M1 must not be run until the chosen route's documents are approved. Its results must carry the matching
  category's label (Q5 for A2).
