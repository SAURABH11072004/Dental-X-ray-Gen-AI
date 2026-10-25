# Abstention-rule experiment — decision record

**Decision (2026-10-16): no candidate promoted. Production keeps `abstain if normalised entropy >= 0.3965956833419285`.**
Nothing in this folder is used by the application. The production threshold, the four checkpoints, the inference logic and the UI
were not changed by this experiment (verification below).

## Files

| File | Content |
|---|---|
| `report.md` | Full results: baseline, 33 rules × 2 splits × 2 crop populations, coverage / risk / macro and per-class P-R-F1, confusion matrices, FP/FN, unlabelled-tooth naming rate, selection, limitations, reproduction commands |
| `report.json` | Same results, machine-readable (every configuration, both splits, both populations) |
| `probs_calibration.json`, `probs_val.json` | Cached per-crop softmax outputs of the production models (calibration: 64 radiographs, 324 findings, 534 unlabelled tooth boxes; validation: 65 radiographs, 331 findings, 584 unlabelled tooth boxes), with model and split hashes |
| `MANIFEST.sha256` | SHA-256 of every artefact in this folder plus the experiment script, the rule module and the regression tests |
| `README.md` | This decision record |

Code: `scripts/abstention_threshold_experiment.py` (experiment), `src/dentexmodel/uncertainty/abstention.py` (offline rules),
`tests/test_abstention_rules.py` (15 regression tests). Follow-up plan: [`docs/ANNOTATION_AND_EVALUATION_PLAN.md`](../../../ANNOTATION_AND_EVALUATION_PLAN.md).

## Why no candidate was promoted

1. **Fixed criteria, no exception.** The acceptance criteria (C1 coverage gain, C2 selective-risk limit, C3 Deep Caries and Periapical
   Lesion protection, C4 macro-F1, C5 bootstrap bound) were written into the script before the run. A rule is recommended only if it
   passes C1–C4 on the calibration split **and** C1–C5 on the validation split.
2. **Only one rule passed on calibration:** `abstain if max p < 0.75` (coverage 0.506 → 0.623, risk 0.093 → 0.096 on detector crops).
3. **It failed confirmation on validation (C3).** Periapical Lesion precision fell from 0.50 to 0.43 (one additional wrong Periapical
   Lesion prediction among 7 validation crops) while Periapical Lesion recall did not improve (0.43 → 0.43). C1, C2, C4 and C5 passed
   (risk difference +0.003, bootstrap 95% CI −0.018 to +0.026).
4. **Simpler relaxations fail on the minority classes.** Raising the entropy threshold to 0.50 raises calibration coverage by 0.14 but
   drops Deep Caries precision from 0.71 to 0.55; at 0.65 (which would accept the example region 25, H = 0.648) selective risk rises by
   0.043 and Deep Caries precision falls to 0.37.
5. **The cost on unlabelled teeth cannot be measured.** The candidate would name a class for 59% instead of 43% of validation teeth that
   carry no DENTEX finding label. Those teeth are not known to be healthy (DENTEX never labels healthy teeth) and are not counted as
   errors or as correct; the extra predictions there are unverified. The production rule already names a class for about 40% of them.
6. **Too little minority data to decide.** Periapical Lesion has 16 (calibration) and 7 (validation) detector-matched crops; one crop
   moves its precision by 0.05–0.14. No threshold can be tuned reliably for that class with the current data.

One analysis-code correction is recorded in `report.md`: the first run compared the inclusive limits without a floating-point tolerance
(a precision drop of exactly 0.05 counted as a failure). The comparison was fixed and the analysis re-run; the criteria values were not
changed. The final recommendation was the same before and after the fix.

## Verification that production is unchanged (2026-10-16)

* `Data/reports/uncertainty_thresholds.json`: `normalised_entropy_ge = 0.3965956833419285`, generated 2026-10-14 (unchanged; equals the
  experiment baseline).
* Checkpoint SHA-256 prefixes match their sidecars: detection a68ce4884066, segmentation dd13568c8de5, numbering 83f97b2e1ce4,
  classification 5aa878e1fc9e; the probability caches were produced with the same detection and classification files.
* The 10 most recent stored production analyses (275 classified regions) were re-checked: every abstain/accept decision equals the baseline
  rule (0 differences).
* `backend/services/pipeline.py` differs from the committed version only by the two lines that add the image-level `final_result`
  (an earlier, separate change); the abstention logic (`h >= thr["normalised_entropy_ge"]`) is unchanged.

## What would change the decision

New ground truth, not more tuning: healthy / no-finding labels for every tooth, more Deep Caries and Periapical Lesion examples, and an
untouched test set — see the annotation and evaluation plan.
