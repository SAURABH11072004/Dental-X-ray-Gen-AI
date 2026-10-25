# CV5 acceptance protocol: owner decisions on B-1 – E-3 (record) and remaining open points

Date 2026-10-25. This file records the owner's decisions on the items in `reports/cv5_acceptance_decisions_needed.md` Part G and
drafts the follow-up wording that those decisions require.

**Status: the acceptance protocol remains NOT APPROVED.**
* E-2 was not approved.
* E-1, D-2 and D-3 were approved provisionally or with conditions that need further wording (below).
* U1–U9 have not been decided.

No proposal, protocol, result, fold file, ledger entry or artifact was changed. No training, data import or candidate run took place.
`reports/cv5_acceptance_protocol_proposal.md` (revision 2) is unchanged. These decisions are to be merged into a revision 3 only
after the open points in §3 are settled.

## 1. Decisions as given by the owner (verbatim)

| ID | Decision | Owner's reason | Recorded status |
|---|---|---|---|
| B-1 | Approve with an identity-level independence check | Preserve the existing fold file and original held-out labels. | **Approved**, condition: identity-level check (see §2.1) |
| B-2 | Approve: BASE-P2 is exploratory initially | Adding data changes the training regime, so it must not be presented as a direct confirmatory comparison against today's BASE. | **Approved** (exploratory) |
| B-3 | Approve | Make import independence a mandatory validity gate. | **Approved** |
| B-4 | Approve | Keep corrections to existing evaluation findings out of confirmatory work until a separate label-revision protocol is approved. | **Approved** |
| D-1 | Prefer the finite 15-candidate lifetime budget | Prevent indefinite experimentation and repeated selection against the same evaluation data. | **Approved**: 15 lifetime |
| D-2 | Approve with a restriction | Exploratory results may inform future hypotheses, but candidates selected using those results need a genuinely independent confirmatory evaluation. Count all candidates against the budget. | **Approved with restriction**: wording open (§3.2) |
| D-3 | Approve provisionally | Use the predeclared deterministic selection rule, provided all acceptance criteria pass and the comparisons are valid. | **Provisional** |
| E-1 | Approve provisionally | Define collapse as at least 99% of predictions assigned to one class; specify the exact prediction population and failure classification. | **Provisional**: 99 %; population and classification drafted in §3.3 |
| E-2 | Do not approve as written | A validation report on data the final model trained on is not an independent validation report. The ledger workflow needs a valid procedural solution before test evaluation. | **Not approved**: alternatives in §3.1 |
| E-3 | Approve the wording fixes | Keep comparisons unrounded, define latency and GPU-hours precisely, and explicitly state that future test results are not untouched estimates. | **Approved** for insertion |

## 2. What the approved decisions fix

### 2.1 B-1 / B-3: imports and the identity-level independence check (gate V6)
* The v1 fold file (`9b767a48…`) and the original DENTEX held-out and inner-validation labels are frozen.
* Imported, clinician-verified labels enter only the fitting part of each fold.
* **Gate V6 is mandatory** before any training that uses imports. Each imported radiograph must pass all three checks below; a single
  failure stops the run (NO VERDICT):
  - identity: not in the same radiograph group as any CV5 pool, calibration, test or eval-locked radiograph;
  - exact duplicate: no SHA-256 match with any of those images;
  - near duplicate: no match by perceptual hash (dHash Hamming distance ≤ 4 and correlation ≥ 0.97, as drafted in Part B).
* "Identity-level" is read here as radiograph and group identity. DENTEX has no patient IDs (cv5_results §7), so patient-level
  identity cannot be checked. That limitation stays stated.

### 2.2 B-2 / B-4
* **BASE-P2 is exploratory.** It is not a confirmatory test of "imports help".
* **Corrections to existing pool findings** (for example the 110-finding review list) stay out of confirmatory work until a separate
  label-revision protocol is approved.

### 2.3 D-1
The total lifetime budget is 15 candidate configurations:
* 3 for each of the families F1–F4;
* 1 F5 ensemble design;
* 2 combinations.

All candidates count, exploratory and confirmatory alike. Only a recorded owner decision can enlarge the budget.

### 2.4 E-3
The wording fixes are approved for insertion: N1–N6, G2, G4, G5, G8 and §5.2 (Part E of the decisions file). They add no new values.

## 3. Points that the decisions leave open (drafts only; need owner approval)

### 3.1 E-2 rejected: how the final model gets a genuine validation report

**Constraint (from code).** `authorize` in `src/dentexmodel/evaluation/test_ledger.py:182` requires
`reports/eval_<version>_val.json`, and `_val_report_for` (line 174) accepts it only if its `checkpoint_sha256` equals the model's.
So any final model needs a validation report for the exact checkpoint.

**Consequence.** A model retrained on the full CV5 pool has no radiographs left that are both labelled and unseen. The only labelled
data outside the pool are the calibration and test splits. Calibration is not part of this workflow, and test may not be used for
tuning. So, as you decided, the U9 recommendation (full-pool retrain) cannot meet the ledger requirement honestly.

**Options:**

| Option | Final model | Validation report | Cost / caveat |
|---|---|---|---|
| **V-a (recommended)** | One **pre-designated** CV5 fold model of the winning candidate, chosen by a fixed rule written now: **fold 0, seed 42**, the lowest indices, chosen without reference to any result | Its own held-out fold (fold 0, about 108 radiographs), which it never trained on | Trained on about 80 % of the pool. The held-out fold was also used for candidate comparison, so the report is independent of training but not of selection; this is stated. Needs no ledger code change. |
| V-b | Retrain on the pool minus a pre-declared subset (for example fold 0), fixed epoch count | That subset | Equivalent to V-a, plus one extra training run. Only useful if the recipe must change (for example no inner validation). |
| V-c | Full-pool retrain (as in U9) | Change the ledger to accept a CV out-of-fold report as validation evidence | Changes a protective gate in the ledger code; needs separate approval and a code review. The final checkpoint itself still has no independent report. |

**If V-a is chosen, U9 changes accordingly.** The final model is the fold 0 / seed 42 checkpoint of the winner. There is no retrain
and no new rounding rule; the "median epoch, rounded down" rule is dropped. Imports remain in its training part under B-1.

### 3.2 D-2 restriction: what counts as "genuinely independent confirmatory evaluation"

**Problem.** Under B-1, every confirmatory comparison uses the same 541 held-out radiographs (v1 folds) as every exploratory run.
A confirmatory run on those folds is therefore **not** independent of exploratory results on those folds. The restriction cannot be
met inside the frozen v1 population if exploratory candidate runs also use it.

**Options:**
* **(i) Recommended:** no exploratory candidate runs on the v1 CV population.
  - Candidates for confirmatory work are registered from information available now: literature, the BASE CV5 run, and earlier
    single-split results already disclosed.
  - BASE-P2 is a reference run, not a candidate. To keep it from selecting candidates, every confirmatory candidate for the first
    round is registered **before** BASE-P2 results are viewed.
  - The budget then counts confirmatory registrations; all 15 remain available.
* (ii) Exploratory runs are allowed on the v1 population, but candidates informed by them are confirmed only on a separate,
  pre-registered **confirmation population** of newly acquired, clinician-verified radiographs that never enter training.
  - This modifies B-1 for that subset: imports would be split, before any use, into training-only and confirmation-only parts.
  - With P2 not yet met even for training, such a population would be small, and its power low.
* (iii) The DENTEX test split is **not** an option: D7 allows one evaluation, it is not untouched (G8), and it may not be used for
  selection.

### 3.3 E-1: exact prediction population and failure classification (99 % threshold as approved provisionally)

Draft text:
> **Collapse check (per training run, i.e. per fold × seed).**
> * **Population:** the GT-box predictions on that run's **inner-validation** findings at the selected epoch. These are all
>   four-class primary findings in the inner-validation part of that fold's plan (`fold_plan.json`), and the numbers come from the
>   confusion matrix in `runs/<run>__result.json` → `val_gt.confusion`.
> * **Rule:** the run has **collapsed** if the predicted-class column sums of that confusion matrix give one class a share ≥ 0.99.
>   The comparison uses the unrounded value. Held-out and detector-box predictions are not used for this check, so that the
>   classification is made before any held-out result is read.
>
> **Failure classification (per run; recorded in the result JSON before any verdict and not changed afterwards):**
> 1. **Infrastructure failure:** the log ends in an exception outside the forward, backward or loss computation (CUDA runtime error,
>    out of memory, timeout, lost session).
>    - The run is retried with the identical config and seed, up to 3 attempts (`kaggle/dentamind_kaggle.py:535`).
>    - If all attempts fail, the candidate gets **NO VERDICT (infrastructure)**. It still counts against the D-1 budget, and it may
>      be re-run unchanged once, with owner approval.
> 2. **Divergence:** the training loss is NaN or ±inf at any logged step, **or** the run has collapsed (rule above).
>    - The run is not retried, and the candidate verdict is **FAIL (divergence)**. It counts against the budget.
> 3. **Incomplete:** integrity gate 4 or 5 fails for a reason not covered by 1 or 2.
>    - The verdict is **NO VERDICT (incomplete)**. It counts against the budget.

**BASE descriptive reference** (computed now from the archived result files; it does not change the threshold): over the 25 BASE
runs, the largest predicted-class share on inner validation was between 0.586 and 0.711, always Caries. Inner validation had 269–308
findings per run. BASE is therefore far from the 0.99 threshold.

### 3.4 D-3 provisional
The rule stays provisional until §3.1 and §3.2 are decided:
* Under option V-a it picks the candidate whose fold 0 / seed 42 model goes to D7.
* Under D-2 option (i), only confirmatory candidates that were registered without exploratory input on v1 are eligible.

### 3.5 U1–U9
Not decided. The recommendations in the decisions file Part F stand, except that **U9 depends on §3.1** (V-a would replace the
full-pool retrain) and **U3** remains tied to B-1 and B-2 as approved.

## 4. Remaining blockers (unchanged)
* P2 not met:
  - PL 129 findings / 94 radiographs, against a target of ≥ 300 / 200;
  - DC 467 / 250, against ≥ 750 / 400;
  - 0 clinician-verified imports.
* Two ledger disclosures (P5, external-data run) await the owner's name as authorizer.
* The acceptance function, the paired bootstrap, gate R and gate V6 are specified but not implemented.
