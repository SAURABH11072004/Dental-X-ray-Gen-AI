# Data acquisition and verification checklist (P2)

Date 2026-10-25. Operational checklist for meeting P2 (the provisional targets of 2026-10-16):

| Class | Target | Today | Gap |
|---|---|---|---|
| Periapical Lesion | ≥ 300 findings from ≥ 200 radiographs | 129 / 94 | +171 findings, +106 radiographs |
| Deep Caries | ≥ 750 findings from ≥ 400 radiographs | 467 / 250 | +283 findings, +150 radiographs |

**Nothing here has been done.** No request was sent, no data was obtained, and no label was verified. `data/annotation/verified_findings.csv`
does not exist, so 0 clinician-verified labels count toward P2.

## A. What already exists (reviewed)

| Item | State |
|---|---|
| `reports/data_requests/dentex_organizers_email.md`, `tufts_access_request.md` | Drafts only; **not sent**. Sending is the owner's action. |
| `data/annotation/annotation_pool.csv` | 6,006 radiograph groups (Hanoi 3,863; DENTEX unlabelled 1,537; DENTEX official test 155; DENTEX quadrant(-enumeration) 306 train-locked / 129 eval_locked; quadrant-enumeration-disease 16). Groups containing any diagnosis-labelled radiograph are excluded by construction. **No class labels.** |
| `reports/annotation_review_queue.csv` | 525 prioritised review tasks (batch 01). `model_suggestion` and `p_*` columns are model scores. **They are not labels and never count toward P2.** |
| `data/annotation/reviewers.csv`, `review_config.xml`, `review_batch_01_*` | Reviewer registry and Label Studio configuration / batch for clinician review |
| P1 route | `scripts/dataset/clinical_review.py` (hash-chained review log) → `verified_findings.csv` → `scripts/dataset/verified_to_manifest.py` → `build_combined_manifest.py --include-verified` (training only). `verified_to_manifest` re-checks the chain, the latest decision, `accepted_label`, the reviewer in the registry, eligibility, image SHA-256 and the crop rule. |
| Independence gate | `kaggle/cv5_accept.gate_v6`: group identity, exact SHA-256, dHash ≤ 4 + correlation ≥ 0.97, against the CV pool, calibration, test and eval_locked |
| Counting | `scripts/dataset/expansion_report.py` → `reports/expanded_class_distribution.csv` (verified findings only; pool rows are counts awaiting review) |

## B. Per new data source (before any image is used)
- [ ] **Licence** read and recorded. It must permit research use, derivative annotations and, if intended, publication. Record the
      redistribution terms. No source is used under an unclear licence.
- [ ] **Provenance** recorded:
  - [ ] official URL / DOI and version;
  - [ ] download date;
  - [ ] archive SHA-256;
  - [ ] the institution and country of acquisition;
  - [ ] the original label taxonomy.
- [ ] **Ethics / de-identification:** confirm the images contain no patient identifiers, and record the source's own ethics statement.
- [ ] **Label taxonomy:** map the source's labels to the four target classes with an explicit, documented mapping
      (`dsutil.canonical_finding` refuses unknown taxonomies).
  - [ ] Unmappable labels are not used.
  - [ ] Owner decisions on mapping are recorded (see the 2026-10-24 definition-mapping decision for Cluj / Hanoi).
- [ ] **Per-source reporting (P3):** counts and results are always reported per source; sources are not pooled silently.
- [ ] **Hanoi:** rows need a complete four-class clinician review before any training use (P3; enforced by `training_eligibility`).

## C. Image integrity and leakage (before review, and again before training)
- [ ] SHA-256 of every image recorded in the pool. Exact duplicates within the source are collapsed into one radiograph group.
- [ ] Near-duplicate grouping with the project rule (dHash Hamming ≤ 4 confirmed by thumbnail correlation ≥ 0.97), via
      `build_annotation_pool.py` / `build_combined_manifest.py`.
- [ ] Twins of validation, calibration or test radiographs are marked `eval_locked` and never reviewed for training.
- [ ] **Gate V6** run on the final import set: 0 hits against the CV pool, calibration, test and eval_locked. The result JSON is archived.
- [ ] DENTEX official-test images in the pool: 95 of 250 official test images are byte-identical to DENTEX training radiographs
      (`reports/training_summary.md`). Confirm via V6 that no such twin is imported.

## D. Clinician verification (the only route to a P2 count)
- [ ] Reviewers are registered in `reviewers.csv`, with a qualification statement. Reviews are only accepted from registered reviewers.
- [ ] Every decision is written to the hash-chained review log. The chain verifies before export.
- [ ] Only the **latest** decision with status `accepted_label` counts.
- [ ] **Model suggestions are shown as suggestions only.** A finding counts only when the clinician draws or confirms the box and label.
- [ ] Recommended: a second-reader check on a predefined subset (e.g. 10 %), with agreement reported. The subset size is an owner
      decision. It is not a P2 rule unless adopted by amendment.
- [ ] Corrections to existing DENTEX labels are **not** imports (B-4). They are recorded separately for a future label-revision protocol.

## E. Counting toward P2
- [ ] Run `verified_to_manifest` and inspect every skipped row and its reason. Nothing is repaired by hand.
- [ ] Run `expansion_report.py`. P2 is met only when it reports a gap of 0 findings **and** 0 radiographs for both PL and DC.
- [ ] Freeze the imports manifest (file and SHA-256), the review-log chain head and the reviewer-registry SHA-256, for Amendment 02.
- [ ] Unverified, model-suggested, partially reviewed or eval_locked rows count toward nothing.

## F. Owner actions required (not performed by the assistant)
1. Decide which sources to pursue, and send the access requests yourself.
2. Recruit and register clinician reviewers, then run review batches in Label Studio.
3. Approve any taxonomy mapping and the second-reader subset.
4. After E is complete, sign Amendment 01 (if not already) and complete Amendment 02.
