# Drafted final wording for revision 3 of `reports/cv5_acceptance_protocol_proposal.md`

**Superseded 2026-10-25:** the owner approved all open items. The merged, approved text is `reports/cv5_acceptance_protocol.md` (revision 3). This file is kept unchanged below as the drafting record.

**Status: DRAFT WORDING. The proposal remains NOT APPROVED.**
* Update 2026-10-25 (second owner round):
  - The owner approved the **direction** of revision 3, not the final document.
  - V-a is approved conditionally, and D-3 provisionally.
  - U1–U8 now have owner recommendations, incorporated below.
  - Items that still need a value or a choice are listed in §R.
* Date: 2026-10-25.
* This file holds the replacement and insertion text for revision 3. It has **not** been merged.
* `reports/cv5_acceptance_protocol_proposal.md` stays at revision 2, SHA-256 `98d6e223…`, unchanged. This keeps the existing proposal
  and its hash intact, as instructed.
* When the owner approves the open items in §R (end of this file), these sections replace the named sections of the proposal one for
  one. The header of the merged document still reads "NOT APPROVED" until the owner gives final approval.

**Sources for the decisions:**
* owner decisions of 2026-10-25 on B-1 – E-3 (`reports/cv5_acceptance_owner_decisions.md`);
* the owner's follow-up decisions of 2026-10-25 (items 1–6 of that message);
* bootstrap specification: `reports/cv5_acceptance_decisions_needed.md` Part C, inserted verbatim as Appendix C (not repeated here).

**Unchanged in revision 3:** δ = 0.027, P-A to P-D, the S1–S6 margins, the D8 flags and the bootstrap settings.
**New values introduced:** only the 99 % collapse threshold (E-1, approved provisionally) and the fold 0 / seed 42 designation (V-a).

---

## Header (replaces lines 1–10)

> # PROPOSAL (not approved): acceptance protocol for candidate models compared with BASE under grouped 5-fold CV
>
> **Status: DRAFT PROPOSAL, revision 3 (2026-10-25). NOT APPROVED. Not in force.**
> * Revision 2 incorporated the owner's recommended decisions D1–D10.
> * Revision 3 incorporates the owner's decisions of 2026-10-25: B-1 to B-4, D-1, D-2 (option i), E-1, E-3, the E-2
>   replacement (V-a), and the U9 change. These are recorded in §13.
> * Final approval is still required before any candidate or reference run is registered or run.
> * No candidate has been trained or evaluated. Every threshold is a **proposed future criterion**, not an observed result.

## §2 Scope: replace the bullet "any change to a fold file without P4 approval"

> * any change to the fold file `cv5_folds_v1.csv` (SHA-256 `9b767a48…`). Under §3.1 it is not regenerated for this protocol; a
>   new evaluation population needs its own protocol.

## §3 Data readiness and evidence categories (replaces §3)

> ## 3. Data readiness and evidence categories
>
> * **Confirmatory comparisons** are the only ones that can yield ACCEPT. They start only when P2 is met.
>   - **P2 counting basis:** P2 is met when `scripts/dataset/expansion_report.py`, run on the current manifests and verified labels,
>     reports a gap of 0 findings and 0 radiographs for both Periapical Lesion and Deep Caries. It is a pool-level condition, not a
>     per-fold one. Per-fold fitting counts are reported, descriptively.
>   - **P2 version:** the P2 version in force on the date a confirmatory candidate, or BASE-P2, is registered applies to it. P2 may be
>     revised only before any confirmatory result exists, and only by a dated owner decision. Today it is the provisional P2 of
>     2026-10-16:
>     - PL ≥ 300 findings from ≥ 200 radiographs (now 129 / 94);
>     - DC ≥ 750 from ≥ 400 (now 467 / 250).
>   - **What counts toward P2:** only labels admitted through the P1 route (`verified_to_manifest.py`, review-log chain verified,
>     current reviewer registry) that also pass gate V6. Original DENTEX labels count as `expansion_report.py` already counts them.
>   - **No confirmatory comparison can start today.**
> * **No exploratory candidate runs on the CV5 evaluation population** (owner D-2, option i).
>   - No candidate configuration is trained or evaluated on the 541 primary radiographs of `cv5_folds_v1.csv` (or their folds)
>     except as a registered confirmatory candidate.
>   - Candidates are chosen from information available before registration: the literature, CV5-BASE run 1 (A1), and earlier
>     single-split results already disclosed.
>   - The DENTEX test split is never used to choose, rank or tune candidates.
>   - Pre-P2 "exploratory exception" candidate runs (revision 2) are withdrawn.
> * **Evidence categories:**
>
>   | Category | Content | Supports | Report label |
>   |---|---|---|---|
>   | A1 Completed baseline | CV5-BASE run 1 (`reports/cv5_results.md`, `kaggle/artifacts_cv5_run1/`) | reference values and noise margins | "Observed BASE (CV5 run 1)" |
>   | A2 Test-set history | 5 historical ledger entries, plus 2 pending retrospective disclosures of BASE test evaluations (2026-10-16; 2026-10-24) | context only; shows the test split is already used | "Historical test result (test split previously used)" |
>   | A3 Exploratory | the §7.1 analyses, and the BASE-P2 vs BASE comparison (B-2) | hypotheses only; never ACCEPT, promotion or test use, and **never input to first-round candidate selection** (§4.5) | "EXPLORATORY: not a confirmatory result" |
>   | A4 Confirmatory | a candidate registered under §4.5 after P2 is met, with all validity gates passed | the only route to ACCEPT / FAIL / NO VERDICT | "Confirmatory (CV5 acceptance protocol)" |
>   | A5 Future ledger test | at most one, after a confirmatory ACCEPT and the winner rule (§10.2) | descriptive only; **not** an untouched estimate | "Final test evaluation (ledger entry #…, test split previously used)" |
>
>   A result can never be relabelled into a stricter category. It can only be produced again under that category's rules.
>
> ### 3.1 Imported labels and evaluation independence (owner B-1, B-3, B-4)
>
> 1. **Evaluation labels are frozen.** Every held-out and inner-validation label is an original DENTEX expert label of
>    `cv5_folds_v1.csv` (581 groups). Imports never add, remove or change an evaluation label, and the fold file is not regenerated.
>    P4's note on regenerating the folds is superseded for this protocol.
> 2. **Imports are training-only, in every fold.** P1 rows enter the **fitting** part of every fold. They never enter
>    inner-validation or a held-out fold, and never contribute to an out-of-fold metric.
> 3. **Only radiographs outside the evaluation population can be imported.** `build_annotation_pool.py` excludes every group that
>    contains a diagnosis-labelled radiograph. `eval_locked` twins and evaluation hashes are refused at export and again in
>    `verified_to_manifest.py`.
> 4. **Gate V6 (identity-level import independence; mandatory).** It runs before any training that uses imports. Every imported
>    image must lie outside the 581-group CV pool, the calibration split, the test split and the eval_locked groups, on each of
>    three checks:
>    - radiograph group identity;
>    - exact SHA-256;
>    - the confirmed near-duplicate rule (dHash Hamming ≤ 4 and correlation ≥ 0.97).
>
>    Any hit is refused, and the run gets NO VERDICT until the hit is removed. DENTEX has no patient IDs, so patient-level identity
>    cannot be checked. This is stated as a limitation (§8).
> 5. **Corrections to existing pool labels are excluded.** Clinician opinions on findings already in the CV pool (for example the 110
>    findings in `reports/cv5_caries_clinician_review_list.csv`) are used in no confirmatory comparison. They need an owner-approved
>    label-revision protocol first.
> 6. **Per-source reporting (P3)** applies to imported rows.
>
> ### 3.2 BASE reference after imports: BASE-P2 (owner B-2)
>
> * **BASE-P2 recipe:** the unchanged BASE recipe, with the imports in every fold's fitting part, on the v1 folds, seeds 42–46, the
>   same inner-validation and the same detector boxes.
> * **Registration:** by its own dated amendment.
> * **Role:** BASE-P2 is a **reference run, not a candidate.** It is never ACCEPTED, and it does not count toward the candidate budget
>   (§10.1).
> * **Its comparison with CV5-BASE run 1** (the effect of imported data) is **exploratory** (A3). It is not a confirmatory test of the
>   imports.
> * **Sequencing (D-2 option i; owner U3, 2026-10-25):** every first-round confirmatory candidate is registered, and its configuration
>   frozen, **before BASE-P2 is run**, not merely before its results are viewed, because training logs print metrics. Order:
>   1. candidate registration amendment;
>   2. BASE-P2 registration amendment;
>   3. BASE-P2 run;
>   4. gate R on BASE-P2 in the candidate environment;
>   5. candidate training.
> * **Role as comparator (owner U3):** BASE-P2 is the predeclared comparator for confirmatory candidates.
>   - Its training data differ from CV5-BASE run 1, because it adds the imports. Every report states this, and BASE-P2 is never
>     described as the same baseline as CV5-BASE run 1.
>   - Its comparison with CV5-BASE run 1 remains exploratory.

## §4 Experiment design: replace items 1, 3 and 5

> 1. **Frame:** add one bullet: "imports, if any, only in each fold's fitting part (§3.1)".
>
> 3. **BASE reference: reuse only after exact reproduction and an unchanged fold file (D3, confirmed 2026-10-25).**
>    - Stored BASE-reference predictions may be reused only if **both** of these hold:
>      - (a) the fold file is byte-identical to the one they were produced on (`cv5_folds_v1.csv`, SHA-256 `9b767a48…`, checked
>        before use); and
>      - (b) gate R passes in the candidate's notebook and environment.
>    - The reference is CV5-BASE run 1 where no imports are used, and BASE-P2 for confirmatory work after imports (§3.2).
>    - **Gate R:** before the candidate trains, the stored reference checkpoints are re-evaluated on their held-out folds. It passes
>      only if:
>      - the predicted class equals the stored out-of-fold argmax for **every** finding, in both settings; and
>      - every recomputed pooled metric equals the stored value.
>
>    - **Gate R specification (owner U4, 2026-10-25; tolerance values are [NEW VALUES: need approval]):**
>      - **Scope:** every stored checkpoint of the reference run used as the comparator (all 25 BASE-P2 checkpoints, matched by
>        SHA-256 to its checkpoint manifest), each on its own held-out fold, in both settings, with the stored reference detector
>        boxes.
>      - **R1, deterministic prediction output (exact):** for every finding, the recomputed predicted class equals the stored
>        out-of-fold argmax. Zero mismatches are allowed.
>      - **R2, probability output (tolerance):** the maximum absolute difference between the recomputed and the stored class
>        probability, over all findings, classes, settings and checkpoints, is ≤ **1 × 10⁻⁴**. This is the same atol already used
>        for the probability-sum check in `kaggle/ensemble_eval.py:102`.
>      - **R3, aggregate metrics:**
>        - Accuracy, macro-F1 and per-class precision / recall / F1 are deterministic functions of the argmax. Once R1 passes they are
>          recomputed and must be equal; a difference indicates a computation fault, not numerical noise, and fails the gate.
>        - The probability-based metrics (ECE, NLL) are not gated. Their differences are reported.
>      - **Recorded:** the number of argmax mismatches, the maximum probability difference, and the R3 comparison, in the result JSON.
>    - **If gate R fails (owner U5):** it is a **validity failure** before candidate training. The candidate gets no verdict, and
>      training does not start until the cause is found, documented and resolved by a dated amendment. It does **not** use a budget
>      slot (§10.1).
>    - If (a) or (b) fails, the stored predictions are not used.
>
> 5. **Pre-registration (D9, D-1, D-2).** Before any training, a dated amendment fixes:
>    * the candidates;
>    * each candidate's exact config diff against `EXPERIMENTS["BASE"]`;
>    * how each was chosen. The choice used no held-out out-of-fold prediction of any candidate, no BASE-P2 result (first round), and
>      no test data;
>    * the family's running candidate count against the budget (§10.1);
>    * k for the multiplicity correction (U6).
>
>    Hyperparameter search, if any, runs inside inner-validation only. No candidate may be added after any result of its round is seen.

## §5 Acceptance criteria: insertions

> **Unrounded comparisons (N1).**
> * All criteria are evaluated on unrounded IEEE-754 double-precision values exactly as computed. Rounding is for display only
>   (3 decimals). The criteria are:
>   - P-A: Δ ≥ 0.027;
>   - P-B: lower bound > 0;
>   - P-C and P-D: per-seed or per-fold Δ > 0;
>   - S1–S6: Δ ≥ −margin.
> * The P-A operator is **≥** (owner D1/D2). The earlier single-split `ACCEPT` rule (`kaggle/dentamind_kaggle.py:501`) used **>**.
>   The value is unchanged; the operator difference is disclosed.
>
> **P-B row, "Proposed value" column:** "as specified in Appendix C (paired radiograph bootstrap, `default_rng(0)`, B = 2,000,
> percentile CI at two-sided level 1 − 0.05/k)".
>
> **P-C row, "Proposed value" column (N5):** "For each seed s: pooled out-of-fold macro-F1 of candidate seed s minus BASE-reference
> seed s, detector boxes, matched primary findings. Passes if > 0 for ≥ 4 of 5 seeds."
>
> **§5.2, last sentence of the margin-rule paragraph:** "none was chosen after seeing any candidate's CV5 results (the earlier
> single-split X2_hanoi and ensemble results were known; see the disclosure)."
>
> **§5.3: add**
> * **V6:** gate V6 passes (§3.1 item 4), for every candidate or reference run that uses imports.
>
> **§5.4: replace the EXPLORATORY bullet**
> * **EXPLORATORY** applies only to A3 analyses. No candidate receives an exploratory verdict.

## §6.1 Ensembles: replace the E1/E2 bullet (N6, updated for D-2)

> * E1 = seeds 42–46 of the **BASE reference run for the training data in force**: BASE-P2 for confirmatory work, and CV5-BASE run 1
>   only if a confirmatory ensemble is registered without imports.
> * E2 = seeds 47–51, trained with the same recipe and data.
> * E1 shares its members with the BASE comparator, so only E2 is an independent replication. Both must pass (U8).
> * The F5 design is one candidate configuration in the budget (§10.1).

## §7 Secondary criteria: latency and compute rows (N2, N3)

> **Inference latency:**
> * Measured in the candidate's notebook session, on the same GPU and with the same script.
> * The candidate and one BASE-reference checkpoint are each timed at batch 64 (time per crop) and at batch 1, with 5 repetitions after
>   warm-up; the median is reported.
> * Flag (D8): either ratio (candidate / BASE) > 2.
> * Earlier measurements (ensemble report: 2.9 / 7.7 ms) are not the reference.
>
> **Compute cost:**
> * Report (i) the total notebook wall-clock runtime and (ii) the sum of per-run training times from `runs/*__result.json`, for the
>   candidate and the BASE-reference run, with GPU type and count, plus peak GPU memory.
> * CV5-BASE run 1: 1.37 h total notebook runtime, which includes downloads. Its training-time sum is computed from its result files
>   when the first candidate report is written.

## §8 Statistical units: add

> * **Identity checks are radiograph-level (V6).** No patient-level independence between imports and the evaluation population is
>   claimed.
> * **No independent confirmation of the winner exists inside this design.**
>   - Every confirmatory candidate is evaluated on the same 541 primary radiographs.
>   - The winner's Δ is optimistically biased by selection (winner's curse).
>   - The fold 0 report of §10.3 comes from the same radiographs.

## §9 Failure handling (replaces §9; owner E-1)

> ## 9. Failure handling and run classification
>
> Each training run (fold × seed) is classified from its log. The classification is recorded in the result JSON **before** any
> verdict and is not changed afterwards.
>
> | Class | Definition | Handling | Candidate outcome |
> |---|---|---|---|
> | **Infrastructure failure** | the log ends in an exception raised outside the forward, backward or loss computation: CUDA runtime error, out of memory, process timeout, lost session | retried with the identical config and seed, up to **3 attempts** in total per run (`train_run_isolated(attempts=3)`, `kaggle/dentamind_kaggle.py:535`; `RESUME_FROM`); every attempt logged | if any run still fails after 3 attempts: **NO VERDICT** |
> | **Divergence** | (i) training loss NaN or ±inf at any logged step; or (ii) **collapse**: at the selected epoch, ≥ **0.99** of the run's inner-validation GT-box predictions fall in one class | **not retried** | **FAIL** |
> | **Incomplete** | integrity gate 4 or 5 fails for a reason not covered above | none; folds and seeds are never dropped or substituted | **NO VERDICT** |
>
> **Collapse population:**
> * all four-class primary findings in that run's inner-validation part (`fold_plan.json`), predicted with GT boxes, at the epoch
>   selected by the inner-validation rule;
> * computed from the predicted-class column sums of `runs/<run>__result.json` → `val_gt.confusion`;
> * compared unrounded;
> * held-out and detector-box predictions are not used for this check.
>
> For reference (descriptive, CV5-BASE run 1): the largest predicted-class share was 0.586–0.711 across the 25 runs, always Caries,
> with 269–308 inner-validation findings per run.
>
> **Budget (owner E-1 and U5):**
> * **A candidate counts toward the 15-candidate lifetime budget (§10.1) once its training starts.** Training starts at the first
>   training step of any of its fold × seed runs.
> * From then on every outcome counts: ACCEPT, FAIL, or NO VERDICT (infrastructure, incomplete, or a validity gate after training
>   started).
> * A validity failure **before** candidate training (gate R, gate V6 or the fold-file check) uses no slot. Its cause must be
>   resolved before proceeding.
> * A registered candidate cannot be withdrawn before it starts for any other reason. A withdrawal anyway counts as a used slot
>   [needs approval, §R item 6].
>
> **Other events:**
> * Validity-gate failure: NO VERDICT, with the cause documented.
> * Bug found after results are seen: fix it, write a dated amendment, rerun the whole candidate, and report both runs. Thresholds
>   stay unchanged.
>
> Every registered candidate is reported.

## §10 Test set and ledger (replaces §10)

> ## 10. Budget, winner, test set and ledger
>
> ### 10.1 Candidate budget (owner D-1)
> * **Lifetime budget: 15 candidate configurations.**
>   - 3 for each of the families F1–F4;
>   - 1 F5 ensemble design;
>   - 2 combinations, each combining only individually ACCEPTED components.
> * A candidate counts from the start of its training, whatever its outcome. Pre-training validity failures use no slot (§9).
> * The budget is not reset by rounds or amendments. Only a recorded owner decision can enlarge it, and any enlargement is disclosed
>   in every later report.
> * BASE-P2 and gate-R reproductions are reference runs and do not count.
>
> ### 10.2 Winner rule (owner D-3: approved provisionally, 2026-10-25)
> * **Eligible:** confirmatory candidates that pass **every** criterion (verdict ACCEPT, with all validity gates, primary checks and
>   safeguards passed).
> * **Order:** each step breaks only exact ties of the previous step, on unrounded values:
>   1. highest unrounded seed-mean Δ macro-F1 (detector boxes; the P-A quantity);
>   2. larger P-B lower bound;
>   3. fewer trainable parameters;
>   4. earlier registration timestamp.
> * **Scope:** within a family the rule picks the family winner. Across all eligible candidates, including ACCEPTED combinations, it
>   picks the single candidate that may proceed to §10.3.
> * **Reporting:** the winner's Δ is reported as optimistically biased by selection, and the other ACCEPTED candidates are reported in
>   full.
> * Selection is never re-run after test results exist.
>
> ### 10.3 Final artifact and its validation report (owner E-2 replacement: V-a; approved conditionally 2026-10-25)
>
> **Conditions.** All must hold before the test evaluation. If any fails, there is no test evaluation.
> 1. **Genuine training manifest.** The checkpoint has a `training_manifest` written **by its own training run** at training time.
>    It is never reconstructed afterwards. This requires the CV pipeline to write manifests **before** the first candidate is run
>    (implementation item, not done).
> 2. **Verified checkpoint hash.** The downloaded checkpoint's SHA-256 equals the entry in that run's `checkpoint_manifest.json`, in
>    `runs/<run>__cv_run.json` (`checkpoint_sha256`), and in the training manifest.
> 3. **Held-out report from stored predictions only.**
>    - The report is computed from `runs/<run>__heldout_pred.npz` (verified against the run's `SHA256SUMS.txt`), with the
>      `checkpoint_sha256` taken from `cv_run.json`.
>    - **No new inference is run.**
>    - The report is written as `eval_<version>_val.json` and labelled "held-out CV fold 0 (stored predictions)", not "validation
>      split".
> 4. **Disclosure** (wording below) in that report and in every test report.
>
> * **Final artifact:** the winner's **fold 0, seed 42** checkpoint, from its confirmatory CV5 run.
>   - The designation was fixed on 2026-10-25, before any candidate exists, by the rule "lowest fold index, lowest seed".
>   - There is **no retraining**: no full-pool retrain and no fixed-epoch rule.
> * **Validation report:** the `eval_<version>_val.json` required by `test_ledger.authorize` (`_val_report_for`, which checks
>   `checkpoint_sha256`) is that checkpoint's **existing held-out fold 0 report**.
>   - It is computed from the run's stored held-out predictions (`runs/<run>__heldout_pred.npz`) for the same checkpoint hash.
>   - That fold was never used to train that checkpoint or to select its epoch.
>   - The ledger's validation-first requirement and its code are **not changed or weakened**.
> * **Mandatory disclosure**, in that report and in any test report:
>   > "Held-out fold 0 was part of the population on which all confirmatory candidates were compared and the winner was selected.
>   > This report is independent of the checkpoint's training data but **not** independent confirmation of the selected winner."
> * **Ledger prerequisites, to be met before the test evaluation:**
>   - `authorize` refuses a checkpoint without a training manifest, treating it as `legacy_checkpoint`. CV5 Kaggle runs currently
>     record checkpoint hashes (`checkpoint_manifest.json`) but no `training_manifest` sidecar. The final checkpoint therefore needs a
>     genuine training manifest from its run, verified against `checkpoint_manifest.json`.
>   - The checkpoint must be downloaded and its SHA-256 matched to the manifest.
>   - Neither may be fabricated after the fact.
>
> ### 10.4 Test-set use (D7, G8)
> * The DENTEX internal test split (73 radiographs) and the calibration split are never used for training, epoch selection, candidate
>   selection, ranking, thresholds, calibration or tuning.
> * **At most one** final test evaluation, of the §10.3 artifact only, after a confirmatory ACCEPT. It:
>   - goes through `test_ledger.authorize` with a named authorizer and written reason;
>   - respects the one-new-candidate-per-split-version rule;
>   - is appended to the hash-chained ledger;
>   - is reported as it is.
> * **The test result is not an untouched or unbiased estimate.** The split has 5 historical ledger entries and two BASE test
>   evaluations (2026-10-16, 2026-10-24) with pending disclosures. Every report of the test result carries the
>   `test_status_for_report` block.
> * No tuning follows the test evaluation.
> * **Precondition:** both pending disclosures (P5; `kaggle/artifacts_external_run1/ledger_disclosure_entry.json`) are recorded with
>   the owner's named authorization.

## §13 Decision record: append rows

> | # | Owner decision (2026-10-25) | Where | Status |
> |---|---|---|---|
> | B-1 | Imports training-only, frozen v1 evaluation population, identity-level independence check | §3.1 | decided |
> | B-2 | BASE-P2 is a reference; its comparison with BASE is exploratory | §3.2 | decided |
> | B-3 | Gate V6 mandatory | §3.1, §5.3 | decided |
> | B-4 | Corrections to existing pool findings excluded until a label-revision protocol | §3.1 | decided |
> | D-1 | 15-candidate lifetime budget, all outcomes counted | §10.1, §9 | decided |
> | D-2 | Option (i): no exploratory candidates on the CV5 population; register first round before viewing BASE-P2; no test-set selection | §3, §3.2, §4.5 | decided |
> | D3 | Reuse stored BASE predictions only after exact reproduction and with an unchanged fold file | §4.3 | decided (confirmation of D3) |
> | D-3 | Winner rule | §10.2 | provisional |
> | E-1 | Collapse ≥ 99 % of inner-validation GT-box predictions at the selected epoch; failure classes and outcomes | §9 | decided (owner's 2026-10-25 wording) |
> | E-2 | Procedural validation report on training data: **rejected**; replaced by V-a | §10.3 | V-a recommended by owner; approval of §10.3 text pending |
> | E-3 | Wording fixes N1–N6, G2, G4, G5, G8, §5.2 | §3, §5, §6.1, §7, §10.4 | decided |
> | U9 | Full-pool retraining and median-epoch rule removed (V-a) | §10.3, §14 | decided |
> | V-a | Final artifact fold 0 / seed 42; conditions: genuine manifest, verified hash, report from stored predictions without new inference, selection disclosure | §10.3 | approved conditionally |
> | U1–U8 | Owner recommendations of 2026-10-25 (second round) | §3.2, §4.3, §9, §14, App. C | see §14; open values in §R |

## §14 Unresolved points: replace the table

> | # | Original question (revision 2, verbatim) | Recommended resolution (unchanged unless noted) | Status |
> |---|---|---|---|
> | U1 | "When P2 is met and the pool grows, are the **numeric margins** kept as frozen here, or re-derived by the same rule from the new BASE CV run?" | **owner 2026-10-25:** margins are **not** re-derived from BASE-P2. The registered CV5-BASE-run-1 margins (S1–S6) stay fixed for the first confirmatory round. Any later recalibration needs a new, prospectively registered protocol. BASE-P2-derived values are not computed for decision use | decided |
> | U2 | "Are δ = 0.027 and the D8 flags also kept unchanged for the new pool?" | **owner:** kept fixed, as for U1 (first round; later changes only by a new protocol) | decided |
> | U3 | "After P2, BASE must be re-run under CV5 on the regenerated, re-approved fold file (P4). Should that BASE re-run be pre-registered as part of this protocol or as a separate amendment?" | **owner:** premise superseded by B-1 (no regeneration). BASE-P2 is a separate dated amendment on the unchanged v1 folds. Candidates are registered and frozen **before BASE-P2 is run**. BASE-P2 is the predeclared comparator; its comparison with CV5-BASE run 1 stays exploratory, and the change in training data is documented (§3.2) | decided |
> | U4 | "Gate R scope: how many stored BASE checkpoints are re-evaluated (1 or all 25), and is any probability tolerance allowed besides identical predicted classes and identical metrics?" | **owner:** the exact stored BASE-P2 comparator checkpoints. Exact prediction-level check where deterministic; no exact float equality required for metrics affected by harmless numerical variation; tolerances defined in advance. Drafted in §4.3: R1 exact argmax, R2 probability ≤ 1 × 10⁻⁴, R3 | direction decided; R2 value needs approval (§R 2) |
> | U5 | "If gate R fails: retrain BASE concurrently in the candidate environment (about 1.4 GPU-h, then use it as the comparator), or stop until the environment is fixed?" | **owner:** a pre-training failure is a validity failure. It uses no budget slot, and its cause is resolved before proceeding. Once a candidate's training starts, every outcome counts (§9) | decided; withdrawal rule needs approval (§R 6) |
> | U6 | "Multiplicity method for k > 1 candidates in a round" | **owner:** a cumulative lifetime count across all registered candidates, not a fresh count per round. The adjustment is specified before the first candidate runs | direction decided; method needs approval (§R 3) |
> | U7 | "Keep S7 (end-to-end DC/PL recall) and the hard-harm rule from revision 1?" | **owner (hard-harm):** level, direction, multiplicity and interval method frozen in advance. It flags a material decrease in a protected class's recall or precision, and is never a post-hoc selection device. S7 not yet decided | needs approval (§R 4, 5) |
> | U8 | "Ensemble substitute for P-C (no per-seed replicates)" | **owner:** E1 and E2 must each pass P-A, P-B, P-D and **every applicable safeguard**. S1–S6 are mandatory; S7 is mandatory if adopted under U7, and otherwise not applicable. Per-fold results (P-D) are compared against the predeclared BASE comparator (BASE-P2 seed-mean per fold) on the same held-out radiographs. E2 is trained with the same imports as BASE-P2 | decided, subject to S7 (§R 5) |
> | U9 | "Which single model goes to the test set after an ACCEPT, and how it is trained" | **decided:** §10.3 (V-a). No full-pool retrain, no median-epoch rule | decided |

## Appendix C (new): paired radiograph bootstrap

> Inserted verbatim from `reports/cv5_acceptance_decisions_needed.md` Part C.1–C.3 (inputs, point estimates, bootstrap). The
> following changes apply.
>
> **Step 5, multiplicity (owner U6):** k is a **cumulative lifetime count across all registered candidates, in all families**, not a
> per-round or per-family count. This replaces Part D.1's "no adjustment across families". The exact adjustment is fixed before the
> first candidate runs; the options are in §R item 3.
>
> **Hard-harm interval (owner U7):** it uses the same B draws as P-B, the same percentile method and the same Δ definition. Its level,
> direction and adjustment are in §R item 4.

---

## §R Items still open after the owner's 2026-10-25 recommendations

The ambiguities A-U1 to A-U8 of the previous draft are resolved by the owner's recommendations (§14), except those below.

1. **Revision 3 as a whole.**
   - Direction approved; the final document is not.
   - It is merged into the proposal only after items 2–7 are decided. Even then it stays NOT APPROVED until final approval.
2. **U4, gate R tolerance R2 = 1 × 10⁻⁴** (maximum absolute class-probability difference) [NEW VALUE].
   - **Basis:** the existing probability-sum atol (`kaggle/ensemble_eval.py:102`).
   - **Observed history:** the earlier ensemble reproduction gate in the Kaggle environment reproduced macro-F1 exactly. The local PC
     (other torch/Pillow) did not, with differences up to 0.018 (`reports/ensemble_evaluation.md`), so gate R must run in the
     candidate's Kaggle environment.
   - **Alternatives:** a looser value (e.g. 1 × 10⁻³), or R2 reported only, with R1 alone gating.
   - The earlier ensemble protocol's macro-F1 tolerance (0.005, `REPRO_TOL`) is **not** proposed here. Under R1 the
     classification metrics must match exactly.
3. **U6, adjustment method** (cumulative lifetime count, fixed before the first candidate runs). Options:
   - **(a) Recommended: fixed k = 15**, the lifetime budget, for every candidate. P-B uses the two-sided level 1 − 0.05/15, i.e.
     percentiles 0.1667 and 99.8333.
     - This is the only Bonferroni form that is fixed in advance, identical for every candidate regardless of order, and still valid
       if the full budget is used.
     - **Consequence 1:** with B = 2,000 the lower bound rests on about 3 resamples in the tail, which is unstable. The registered B
       would need to rise, e.g. to B = 20,000 (about 33 tail resamples) [NEW VALUE]. Changing B before any candidate exists is a
       prospective amendment, not a change after results.
     - **Consequence 2:** the requirement becomes stricter than the revision-2 per-family k ≤ 3, so P-B will be harder to pass.
   - (b) Growing k = the number of candidates registered so far, including this one.
     - Order-dependent: earlier candidates face a laxer level.
     - It does **not** control the lifetime error rate (Σ 0.05/j over j = 1…15 > 0.05).
     - Not recommended.
   - (c) Bonferroni α-spending with a declared per-candidate α_j that sums to 0.05 over 15 slots, e.g. a larger share for the first
     round. This is valid, but needs owner-chosen α_j values before the first run.
4. **U7, hard-harm rule.**
   - **Scope (owner):** protected classes Deep Caries and Periapical Lesion, recall **and precision**. Revision 1 covered recall only;
     adding precision follows the owner's wording and needs confirmation.
   - **Interval:** the paired percentile bootstrap of Appendix C, on the same draws as P-B, detector boxes, Δ of seed means.
   - **Direction** (needs a choice):
     - **H1, as worded in revision 1:** FAIL if the CI **upper** bound < −margin, with the S1–S4 margins.
       - Because the point estimate almost always lies inside its percentile interval, H1 fails essentially only when the point
         estimate is already below −margin, which S1–S4 already catch.
       - H1 is therefore close to redundant.
     - **H2:** FAIL if the CI upper bound < 0, i.e. a statistically clear decrease in a protected class, even when the point estimate
       is within the S margin.
       - It adds information beyond S1–S4.
       - It flags clear decreases of any size, which is stricter than "material".
     - **H3:** FAIL if the CI **lower** bound < −margin, i.e. the candidate must exclude a material decrease.
       - The strictest option. With PL's small support (100 detector-matched findings), BASE-vs-BASE intervals for PL recall are
         already wide (bootstrap SD of a single-seed difference about 0.05; `reports/cv5_base_noise.json`), so H3 would fail most
         candidates.
   - **Level** (needs a choice):
     - unadjusted two-sided 95 %, recommended because a multiplicity-adjusted, wider interval makes harm **harder** to detect and so
       favours candidates; or
     - the same k-adjusted level as P-B.
   - **Recommendation:** H2 at unadjusted 95 %, which is the only option that both adds a check and is not near-certain to fail.
     H1 if the owner wants "material" read strictly, accepting that it adds almost nothing to S1–S4.
   - Whichever is chosen is frozen before the first candidate.
5. **S7 (end-to-end DC/PL recall, unmatched findings counted wrong, S1/S2 margins).** Not decided. Recommendation: adopt it as
   **mandatory**; under U8 it would then apply to E1 and E2 as well.
6. **Withdrawal before training** (§9). A registered candidate is withdrawn before its training starts, for a reason other than a
   pre-training validity failure. Recommended: it counts as a used slot, because BASE-P2 results become visible after registration
   and a withdrawal could otherwise act as selection.
7. **Implementation items** (specified, **not** implemented, and not authorized yet):
   - the acceptance function;
   - the paired bootstrap;
   - gate R (R1–R3);
   - gate V6;
   - the training-manifest writing in the CV pipeline (V-a condition 1);
   - the stored-prediction held-out report generator (V-a condition 3).

## Decisions still requiring explicit approval

1. Final revision 3 text, after items 2–6.
2. R2 tolerance value (§R 2).
3. U6 method, and with option (a) the bootstrap size B (§R 3).
4. U7: precision added to the scope, direction H1/H2/H3, level (§R 4).
5. S7 (§R 5).
6. The withdrawal rule (§R 6).
7. Final approval of the protocol (it stays NOT APPROVED).
