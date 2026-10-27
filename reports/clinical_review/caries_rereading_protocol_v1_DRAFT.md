# Clinician re-reading of consistently confused Caries / Deep Caries findings: protocol v1 (DRAFT, NOT IN FORCE)

Date 2026-10-25.

**Status: PREPARED ONLY. BLOCKED.**
* No image has been shown to anyone, and no review has been performed.
* It may start only after a **qualified clinical lead (CL)** completes `reports/templates/clinical_governance_decision_template.md`
  and the data-use conditions in §6 are confirmed.
* The assistant names no reviewer and makes no clinical judgement.

## 1. Purpose
For 110 findings, all five BASE seeds predicted the other caries class on ground-truth boxes. The question is whether these reflect
model error, a debatable depth boundary, or a labelling problem. **No finding is called a label error unless qualified reviewers say
so under this protocol.**

## 2. Material (built by `scripts/build_clinician_review_queue.py`; hashes in `caries_rereading_manifest_v1.json`)

| File | Content | Who sees it |
|---|---|---|
| `caries_rereading_worksheet_v1_BLINDED.csv` | 220 items in random order: review ID, image path and image SHA-256, box, FDI tooth, empty answer fields | reviewers |
| `caries_rereading_key_v1_COORDINATOR_ONLY.csv` | review ID → finding ID, radiograph group, CV5 fold, target/control, original label, annotation provenance, model-consistency counts | coordinator only |

* **Items:** 110 targets (17 Caries, 93 Deep Caries), confused by 5/5 seeds. There are also 110 controls with the same class mix that
  were never confused (0/5 seeds), drawn with a fixed seed.
* **Why controls:** they keep the reviewer from knowing which items are suspected, and they give a reference agreement rate. Without
  controls, a disagreement rate on targets cannot be interpreted.
* **Locked data:** every item belongs to the CV5 evaluation pool, whose labels are frozen (protocol §3).

## 3. Procedure (to be confirmed or changed by the CL)
1. **Phase A, independent blinded read.** Each reviewer sees the radiograph with the box and the tooth number only, with no original
   label and no model output.
   - They record a class (Caries / Deep Caries / Other finding / No finding / Uncertain), a confidence of 1–5, and image adequacy.
2. **Second reader.** Every item is read by two reviewers independently. This is a recommendation; the CL decides.
3. **Phase B, adjudication.** Where the two readers disagree, or both disagree with the original label, a third senior reader or a
   consensus meeting decides. This step is unblinded to the readers' answers, but not to the model.
4. **Record.**
   - Answers are stored as a new versioned file, `caries_rereading_results_v1.csv`, with reviewer IDs and dates.
   - The file is signed off by the CL with an approval record (scope `clinical_governance_decision`, or a scope the policy adds).
   - **Original labels and manifests are never edited.**
5. **Analysis** (fixed in advance):
   - agreement with the original label, for targets and controls separately;
   - inter-reader agreement (Cohen's κ);
   - the share of targets judged ambiguous, meaning "Uncertain" or reader disagreement;
   - all of it descriptive, with no model retraining.

## 4. Use of the results
* **Allowed:**
  - a descriptive paragraph in a later manuscript version (e.g. "on blinded re-reading, X of 110 consistently confused findings were
    judged ambiguous by two readers");
  - input to the clinical-governance labelling standard.
* **Not allowed without a separately approved label-revision protocol (CV5 protocol §3):**
  - changing any evaluation label;
  - re-scoring CV5;
  - importing revised labels for candidate training.

## 5. Governance checklist (all open)

| # | Item | Owner | Status |
|---|---|---|---|
| G1 | Clinical lead appointed and qualified | Project owner | open |
| G2 | Reviewer qualifications, calibration and conflicts defined | CL | open |
| G3 | Written Caries / Deep Caries depth definition given to readers | CL | open |
| G4 | Second reader and adjudication rule confirmed | CL | open |
| G5 | Data-use check: DENTEX licence permits showing the images to the readers; confidentiality agreement if required by the institution | Authors / institution | open |
| G6 | Ethics / institutional requirement for a reader study on public de-identified data | Institution | open |
| G7 | Result storage, sign-off and versioning (approval record) | Project owner + CL | open; needs the approval tooling |

## 6. Data handling
* Images stay on the project machine or an approved viewer (e.g. the project's Label Studio setup).
* The review files contain no patient data, because DENTEX has no identifiers. They do contain image paths and hashes; keep them
  in the project.
* Do not upload images to third-party services.
