# Clinical-governance readiness: blinded re-reading of 110 + 110 Caries / Deep Caries findings (v1)

Date 2026-10-25.

**Readiness: NOT READY TO START.**
* Materials are prepared and blinded.
* No clinical lead exists, no governance decision exists, and no image has been shared.
* The assistant names no person, credential or decision.

## 1. Material status

| Item | Status | Evidence |
|---|---|---|
| Item selection: 110 targets (5/5 seeds confused, GT boxes) + 110 class-matched controls (0/5) | done; target count reproduces the archive | `caries_rereading_manifest_v1.json` |
| **Reviewer worksheet to use: v2** | done. Columns: review ID, opaque image code, FDI tooth, empty answer fields. No file name, image hash, box coordinates, label, model output or target / control flag | `caries_rereading_worksheet_v2_BLINDED.csv` |
| v1 worksheet | **do not give to reviewers.** It contains the DENTEX file name, image hash and exact box, which can be matched against the public DENTEX annotations to reveal the label. Kept unchanged as a record | `caries_rereading_worksheet_v1_BLINDED.csv` |
| Coordinator key (v2) | done. It maps review ID to finding, label, fold, target / control, image file and box (for the viewer). **Coordinator only** | `caries_rereading_key_v2_COORDINATOR_ONLY.csv` |
| Item order | random (seed recorded); targets not clustered (mean position 109 of 220) | build scripts |
| Protocol draft | done | `caries_rereading_protocol_v1_DRAFT.md` |

**Separation of files.** All files currently sit in `reports/clinical_review/`. Before any review, the coordinator must:
* move both coordinator keys (v1 and v2) and the v1 worksheet to a location reviewers cannot open;
* give reviewers only the v2 worksheet and a viewer that shows the coded image with the box drawn.

This is a manual step for the coordinator. The assistant moved nothing.

## 2. Licence and data sharing

| Question | Finding | Open action |
|---|---|---|
| Licence of the DENTEX copy used | the official Hugging Face dataset page (checked 2026-10-25) states **CC BY-NC-SA 4.0** for all elements of DENTEX, and asks that both DENTEX papers be cited. The project's inventory records the same URLs. This resolves the conflict noted in `external_validation_eligibility_v1.md` for this copy; the HierarchicalDet README's "CC BY-SA 4.0" is a different statement | authors confirm |
| May images be shown to reviewers? | showing images to reviewers for **non-commercial research**, with attribution, is within CC BY-NC-SA 4.0. The licence does not cover institutional, ethics or confidentiality rules | institution / ethics committee confirm (G5, G6) |
| Patient data | DENTEX has no patient identifiers; the worksheet contains none | – |
| Third-party services | images must not be uploaded to external services; use the project machine or the local Label Studio setup | coordinator |

## 3. Clinical-lead decision checklist
Every item is to be completed by the clinical lead (CL) in `reports/templates/clinical_governance_decision_template.md`, and recorded
with an approval record (scope `clinical_governance_decision`, countersigned by the project owner) **after** the approval tooling is in
force.

| # | Decision | Options / notes | Decided? |
|---|---|---|---|
| C1 | Accept the CL role; qualifications; conflict-of-interest statement | a real, qualified dental clinician | no |
| C2 | Reviewer qualifications and how they are verified | e.g. a dental degree plus radiograph-reading experience | no |
| C3 | Written depth definition for Caries vs Deep Caries, given to readers before reading | e.g. enamel / dentine depth or pulp proximity, in the CL's words | no |
| C4 | Reviewer calibration before reading | e.g. a short practice set *not* drawn from the 220 items | no |
| C5 | Keep the controls (recommended) or drop them | without controls, target disagreement cannot be interpreted | no |
| C6 | Second reader for every item; adjudication method (third reader or consensus) | the protocol draft recommends two independent readers plus adjudication | no |
| C7 | Answer categories and confidence scale | the draft uses Caries / Deep Caries / Other / No finding / Uncertain, and 1–5 | no |
| C8 | Viewer and display conditions | coded image, box drawn, no other annotations, no model hints | no |
| C9 | Confidentiality and data-handling rules for readers | institutional | no |
| C10 | How results are stored and signed | a new versioned results file and an approval record; original labels never edited | no |
| C11 | Permitted use of results | descriptive reporting only; label changes or training use need a separate, approved label-revision process (CV5 protocol §3) | no |

## 4. Blockers, in order
1. The project owner appoints a CL.
2. The approval policy and tooling are in force, so the CL's decision can be recorded.
3. The CL completes C1–C11.
4. The institution or ethics committee confirms the reader-study requirements.
5. The coordinator separates the files and sets up the viewer.
6. Then reading starts.
