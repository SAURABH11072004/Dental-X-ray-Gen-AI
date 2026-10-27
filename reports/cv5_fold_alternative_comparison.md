# P4 fold assignment: current draft vs. proposed Impacted-stratified alternative (FOR APPROVAL; nothing applied)

Date 2026-10-16. The current draft `data/splits/cv5_folds_DRAFT.csv` (SHA-256 `b001df15…`) is unchanged and is still the draft under
review. The alternative exists only as a definition below; no alternative fold file was written. **No cross-validation will run until
one assignment is approved, and any approved assignment is regenerated and re-reviewed after verified labels are added.**

Owner decisions on record (2026-10-16): P4 assumptions 1-4 accepted (groups = radiographs, not patients; duplicate merging limited to
SHA-256 + dHash/correlation; old validation radiographs are trained on in 4 of 5 folds; draft covers today's data only); K = 5 and
seed = 42 unchanged.

## Definitions (only the stratum differs)
* **Current:** stratum = (source family, has Periapical Lesion, has Deep Caries): 8 strata.
* **Alternative:** stratum = (source family, has Periapical Lesion, has Deep Caries, **has Impacted**): 16 strata.
* Both use the same algorithm (`make_cv_folds.assign_folds`): seeded order within a stratum, each group to the fold with the fewest
  groups of that stratum (ties: fewest findings, then lowest fold). 581 radiograph groups of combined_train + combined_validation;
  calibration and test excluded. The alternative passes the same integrity checks (every group once, 0 calibration/test groups,
  no image hash in two folds). 454 of 581 groups would change fold.

## Comparison (min-max per fold, max/min ratio, coefficient of variation; f = findings, r = radiographs with the class)

| Metric | Current draft | Alternative (+Impacted) | Better |
|---|---|---|---|
| Radiographs | 114-118 (x1.04, CV 0.011) | 113-118 (x1.04, CV 0.016) | ≈ |
| Findings | 579-627 (x1.08, CV 0.026) | 562-631 (x1.12, CV 0.045) | current |
| Caries f | 352-396 (x1.12, CV 0.047) | 331-385 (x1.16, CV 0.053) | ≈ current |
| Caries r | 104-109 (x1.05, CV 0.018) | 99-110 (x1.11, CV 0.035) | current |
| Deep Caries f | 88-117 (x1.33, CV 0.116) | 90-122 (x1.36, CV 0.110) | ≈ |
| Deep Caries r | 55-57 (x1.04, CV 0.013) | 54-57 (x1.06, CV 0.021) | ≈ |
| **Impacted f** | **82-125 (x1.52, CV 0.179)** | **90-113 (x1.26, CV 0.081)** | **alternative** |
| **Impacted r** | **36-51 (x1.42, CV 0.129)** | **41-45 (x1.10, CV 0.031)** | **alternative** |
| Periapical Lesion f | 22-31 (x1.41, CV 0.120) | 25-31 (x1.24, CV 0.078) | alternative |
| Periapical Lesion r | 19-21 (x1.11, CV 0.037) | 19-21 (x1.11, CV 0.037) | = |
| Official-val radiographs | 7-9 | 7-10 | ≈ |
| Old project-val radiographs | 12-16 (CV 0.119) | 8-19 (CV 0.271) | current |

Per fold (current): Impacted findings 124 / 125 / 82 / 84 / 105; PL findings 22 / 27 / 31 / 27 / 31.
Per fold (alternative): Impacted findings 112 / 105 / 100 / 113 / 90; PL findings 31 / 29 / 26 / 25 / 27.

Seed sensitivity (informational; the seed stays 42): over seeds 40-49 the Impacted max/min ratio is median 1.41 (range 1.14-1.77) for the
current stratification and median 1.26 (1.09-1.38) for the alternative, so the improvement is systematic, not a lucky seed.

## Assessment
* The alternative **materially improves** Impacted (radiograph spread x1.42 → x1.10) and Periapical Lesion findings (x1.41 → x1.24), with
  no change to PL or DC radiograph balance.
* Costs: slightly larger spread of total findings and Caries, and a less even spread of the old project-validation radiographs
  (8-19 per fold). Under accepted assumption 3, CV results are not compared fold-by-fold with old validation numbers, so this cost is small.
* Remaining concern in both versions: about 19-21 Periapical Lesion radiographs per fold is still small for per-fold metrics. Report
  fold-pooled (out-of-fold) predictions as the primary result, as P4 already specifies; treat per-fold minority metrics as descriptive.

## Decision needed
Choose one: **(A)** keep the current draft as the assignment to approve, or **(B)** replace the draft with the Impacted-stratified
alternative (I would add the fourth stratum flag to `make_cv_folds.py`, regenerate `cv5_folds_DRAFT.csv` + summary, re-run all integrity
checks and present it for final approval). Either way: no CV run before final approval, and regeneration + re-review after verified
labels are added.
