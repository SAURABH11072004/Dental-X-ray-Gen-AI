# Annotation and evaluation plan for the next classifier / abstention experiment

Status: **proposal, not started.** Written 2026-10-16 after the abstention-rule experiment
(`docs/audit_evidence/ml_improvement/abstention/README.md`) found no rule that could be accepted with the current data.
All numeric targets below are proposals by the project team; they must be reviewed and confirmed by the supervising dental
experts before any data are collected, and then frozen (see §6).

## 1. Why new data are needed

The current classifier was trained on DENTEX, which labels only teeth that have one of four findings. Three gaps block any further
improvement of the abstention rule:

1. **No healthy / no-finding ground truth.** Most detected teeth carry no label. A looser rule names a class for more of them
   (43% → 59% on validation for the best candidate), and there is no way to know whether those extra predictions are right.
   Unlabelled teeth must not be treated as healthy, and extra predictions on them must not be counted as correct.
2. **Too few minority examples.** Periapical Lesion has 16 (calibration) and 7 (validation) detector-matched crops; Deep Caries 42 and
   41. One crop moves Periapical Lesion precision by 0.05–0.14.
3. **No patient identifiers and no untouched test set.** DENTEX has no patient IDs, so patient-level separation cannot be proven, and
   the DENTEX test split has already been used once per checkpoint.

## 2. What to collect

### 2.1 Label set (tooth level, every tooth in the image)

Every tooth visible on the radiograph gets a record; no tooth is left unlabelled.

| Field | Values |
|---|---|
| Tooth position | FDI number (11–48) and box/outline; "not assessable" if position cannot be determined |
| Status | **No finding** (examined, none of the listed findings present) · **Finding(s)** · **Other** · **Uncertain / not gradable** |
| Findings (multi-label) | Caries · Deep Caries · Impacted · Periapical Lesion — more than one allowed per tooth (the end-to-end evaluation found teeth carrying two findings) |
| Other | Free category for conditions outside the four classes (e.g. restorations, root-canal treatment, crowns, implants, other lesions), with a short code list defined by the experts |
| Uncertain / not gradable | Reason: image quality, overlap, artefact, insufficient expertise; a tooth in this state is never used as "no finding" |
| Annotator confidence | Low / medium / high |

"No finding" means *an expert looked and saw none of the listed findings on this radiograph*. It is a radiographic statement, not a
clinical diagnosis of health, and it is never inferred from a missing label.

The clinical definitions (in particular the boundary between Caries and Deep Caries, and the radiographic criteria for Periapical Lesion)
must be written by the dental experts in an annotation guideline with reference images before annotation starts.

### 2.2 How much (minimum per evaluation split)

Precision and recall are proportions; with *n* examples the 95% interval half-width is about 1.96·√(p(1−p)/n). For p ≈ 0.7:
n = 100 → ±0.09, n = 150 → ±0.07, n = 300 → ±0.05.

| Category | Training | Calibration | Validation | Test (untouched) |
|---|---:|---:|---:|---:|
| Caries | ≥ 1,000 | ≥ 150 | ≥ 150 | ≥ 150 |
| Deep Caries | ≥ 500 | ≥ 150 | ≥ 150 | ≥ 150 |
| Impacted | ≥ 400 | ≥ 100 | ≥ 100 | ≥ 100 |
| Periapical Lesion | ≥ 500 | ≥ 150 | ≥ 150 | ≥ 150 |
| No finding | ≥ 3,000 | ≥ 500 | ≥ 1,000 | ≥ 1,000 |
| Other | as available | ≥ 100 | ≥ 100 | ≥ 100 |
| Uncertain / not gradable | kept, not used as a class target | reported | reported | reported |

Periapical Lesion and Deep Caries are rare per radiograph, so collection should **enrich** for them (e.g. pre-screening by a clinician
or record search). Enrichment changes prevalence: every evaluation reports both the observed counts and prevalence-weighted estimates
using the source prevalence recorded at collection.

## 3. Annotation quality control and adjudication

1. **Annotators:** at least two qualified dental professionals per radiograph (dentists or oral and maxillofacial radiologists), each
   working independently and **blinded to model outputs and to each other**.
2. **Calibration round:** before production annotation, all annotators label the same set of ≥ 50 radiographs, discuss disagreements
   with the adjudicator, and update the guideline. These radiographs go to training only.
3. **Adjudication:** a senior oral and maxillofacial radiologist resolves every tooth where the two annotators disagree on status or on
   any finding. The adjudicated label is the reference; both original labels are kept.
4. **Agreement monitoring:** Cohen's κ per class and per batch (target κ ≥ 0.6 before adjudication; batches below that trigger a guideline
   review); intra-rater re-reads of 5% of radiographs after ≥ 2 weeks; a fixed gold set of 30 radiographs re-labelled each month.
5. **Uncertain cases:** if the adjudicator is also uncertain, the tooth stays "Uncertain" and is excluded from class-level targets
   (reported separately).
6. **Audit trail:** every label stores annotator ID (pseudonymous), qualification, timestamp, tool version, guideline version and
   revision history. The existing review store (revisions, second-person approval) is the model for this.
7. **Tooling:** the existing Label Studio export/import path can carry the extended label set; the label configuration must be
   versioned with the guideline.

## 4. Dataset provenance

Recorded per image in the dataset manifest (extending `Data/processed/manifest.json`):

* source institution / dataset and licence; ethics approval reference and consent or waiver basis;
* device manufacturer/model and acquisition date range; image format and any conversion;
* de-identification method (metadata stripping, burned-in text check) and who performed it;
* **pseudonymous patient ID** (salted hash issued by the data custodian; the salt never enters the project) and visit/study ID;
* pixel-content hash (already used by the audit) and near-duplicate group;
* annotation batch, annotators, adjudicator and guideline version.

DENTEX images keep their current provenance and are marked "no patient ID".

## 5. Evaluation protocol

### 5.1 Splits

| Split | Share | Used for | Never used for |
|---|---:|---|---|
| Training | ~60% | fitting models | any reported metric |
| Calibration | ~10% | abstention thresholds, temperature scaling | model selection, final metrics |
| Validation | ~10% | model / epoch selection, comparing candidate rules | thresholds, final claims |
| Test (untouched) | ~20% | one final evaluation per frozen candidate | anything before the candidate is frozen |
| External test (if a second site exists) | one whole site | generalisation check | training, tuning |

* Splits are assigned **per patient** (all radiographs and visits of a patient go to one split), stratified by site and by presence of
  Deep Caries / Periapical Lesion. Pixel-identical and near-duplicate images additionally share a split (existing duplicate-aware split).
* Images without patient IDs (DENTEX) may be used for training only, or reported as a separate stratum; they are never in the primary
  test set.
* The existing leakage checker is extended with patient-ID overlap and same-visit checks across all split pairs; it must pass before
  training starts.
* The test set is used through the existing hash-chained ledger (`Data/reports/test_set_ledger.json`): one evaluation per frozen
  candidate, authorised and recorded. At most five pre-registered candidates may be evaluated on test.

### 5.2 Metrics (all at tooth level, end to end through the detector, plus ground-truth-box results as secondary)

* Coverage (share of finding-labelled teeth that receive a named class) and abstention rate.
* Selective error rate (errors among accepted predictions) and the full coverage–risk curve.
* **No-finding false-alarm rate:** share of adjudicated "no finding" teeth given any finding class.
* Macro precision, recall and F1 over the four findings, end to end (abstentions and detector misses count as misses), plus per class.
* Per-class confusion matrix with columns for each finding, No finding, Other, ABSTAINED and MISSED.
* Behaviour on "Other" and "Uncertain" teeth (how often a finding is named).
* Calibration (ECE) of the reported scores.
* 95% confidence intervals by **patient-clustered bootstrap**; prevalence-weighted estimates where enrichment was used.

## 6. Predefined acceptance criteria (proposed — to be confirmed and frozen before data collection)

A candidate (new model and/or new abstention rule) is compared with the current production configuration evaluated on the **same new
labels**. It is accepted only if **all** hold on validation, and then again on the untouched test set:

| ID | Criterion | Proposed limit |
|---|---|---|
| A1 | Coverage on finding-labelled teeth | ≥ 0.70 and ≥ baseline + 0.10 |
| A2 | Selective error rate | ≤ 0.10, upper 95% CI ≤ 0.13, and not above baseline + 0.02 |
| A3 | No-finding false-alarm rate | ≤ 0.05, upper 95% CI ≤ 0.07 |
| A4 | End-to-end macro-F1 (four findings) | ≥ baseline + 0.05, lower 95% CI above baseline |
| A5 | Every finding class | precision ≥ 0.70 and recall ≥ 0.60 |
| A6 | **Deep Caries and Periapical Lesion** | recall lower 95% CI ≥ 0.50; precision lower 95% CI ≥ 0.60; neither precision nor recall below baseline by more than 0.02 |
| A7 | Other / Uncertain teeth | a finding is named for ≤ 20% of them |
| A8 | Calibration | ECE ≤ 0.05 on validation (temperature fitted on calibration) |
| A9 | Sites (if more than one) | no site with macro-F1 more than 0.10 below the pooled value |

Rules for using the criteria:

* The limits, the metric code and the list of candidates are frozen and hashed (stored next to the protocol) before validation or test
  results are viewed.
* A failure on test is final for that candidate: no re-tuning on test.
* Passing all criteria is necessary but not sufficient: promotion still requires review, written justification and explicit approval
  through the existing promotion workflow (validation report + justification + rollback record).
* No result on this research data set is a claim of clinical validity; clinical use would need a separate prospective study and
  regulatory review.

## 7. Next experiment, in order

1. Experts write the annotation guideline and confirm or revise the limits in §6; freeze them.
2. Obtain approvals and data-sharing agreements; collect and de-identify images with provenance and patient IDs.
3. Calibration round, then double annotation with adjudication; monitor κ.
4. Build patient-level splits; run the extended leakage checker.
5. Re-run the abstention experiment on the new calibration/validation labels (the current script structure can be reused, with
   "No finding" teeth now part of the evaluated population), and train a model with a no-finding class if the data allow.
6. Evaluate frozen candidates once on the untouched test set; decide with the predefined criteria.
