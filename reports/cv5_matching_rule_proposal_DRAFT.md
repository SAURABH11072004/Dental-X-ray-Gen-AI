# Detector-matching improvement: candidate proposal (DRAFT, NOT REGISTERED, NOT EVALUATED)

Date 2026-10-25. It follows from `reports/cv5_error_attribution.md`, a descriptive analysis of the archived BASE outputs that passed
all three reproduction gates.

## 1. Observation (verified counts of primary findings)

| Class | Findings | Unmatched | of which: no overlapping box (U0) | box IoU < 0.5 (U1) | box exists but assigned to another finding (U2) |
|---|---|---|---|---|---|
| Caries | 1,755 | 18 | 0 | 2 | 16 |
| Deep Caries | 483 | 51 | 3 | 34 | 14 |
| Impacted | 484 | 8 | 0 | 5 | 3 |
| Periapical Lesion | 129 | 29 | 0 | 7 | 22 |

* **The detector rarely misses the tooth.** U0 = 3 findings in total.
* **Periapical lesions are lost mainly at matching.** The detector boxes *teeth*; one tooth can carry several findings (e.g. caries
  and a periapical lesion), and greedy one-to-one matching gives the tooth box to only one of them. 22 of the 29 unmatched periapical
  lesions are of this kind (U2).
* **Deep caries is lost mainly at localisation.** 34 of its 51 unmatched findings overlap a tooth box with IoU < 0.5, i.e. the finding
  box and the tooth box differ in extent.
* **Classification still dominates.** Across classes, 66–92 % of end-to-end errors (finding × seed) come from misclassification on
  matched boxes, not from detection or matching.

## 2. Proposed candidates (for registration under Amendment 01-style rules; NOT run)
* **M1, many-to-one matching:** a tooth box may serve every finding with IoU ≥ 0.5. Structural upper bound: 55 more findings become
  classifiable (U2). This does **not** say how many would be classified correctly. Note that two findings on one tooth then share one
  crop and receive the same class.
* **M2, finding-level box expansion for periapical findings:** a crop rule that extends the tooth box apically. This needs a frozen
  geometric rule defined without looking at CV5 results.
* **M3, multi-label output per tooth:** this changes the task definition, so it needs its own protocol.

## 3. Why the effect is not computed now
The M1 effect could be computed from archived predictions, because the shared crops were already classified. Doing so would
evaluate an unregistered candidate on the held-out CV5 data, and the result would then shape the registration. That is post-hoc
selection, which the protocol forbids (§3, §10).

The correct order is:
1. register M1 with a frozen rule;
2. count it against the budget;
3. evaluate it under the protocol.

M1 needs no retraining, only re-scoring, so its compute cost is negligible once it is authorised.

## 4. Protocol interaction (to be settled in the amendment)
* Changing the matching rule changes the detector-box denominator. The protocol's comparison must therefore use the end-to-end
  setting, S7, over all primary findings, or define the matched set by the reference rule.
* The owner decides this in the amendment, **before** any evaluation.
