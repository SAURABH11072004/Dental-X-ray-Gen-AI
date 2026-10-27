# Clinical-governance decision (TEMPLATE; to be completed by the clinical lead)

**This template contains no decision.** Every field must be filled by the accountable clinical lead, and countersigned by the project
owner through approval records (DRAFT Amendment 03, D-B2). The assistant has not entered any name, credential, threshold or clinical
judgement, and must not.

**What it unblocks:** issuing reviewer authorization version 1 (`scripts/dataset/build_reviewer_authorization.py`; approval scope
`reviewer_authorization_issue`). Without it, no import manifest can be built and P2 cannot be met through imports.

## 1. Clinical lead
| Field | Entry |
|---|---|
| Full name | |
| Professional qualification(s) | |
| Registration body and registration number (kept local; never placed in Kaggle artifacts) | |
| Institution / affiliation | |
| Relationship to the project (conflict-of-interest statement) | |
| Date accepted the role | |

## 2. Eligible reviewer qualifications
| Field | Entry |
|---|---|
| Minimum qualification(s) to review dental panoramic radiographs for Caries / Deep Caries / Impacted / Periapical Lesion | |
| Minimum experience (years / case volume), if any | |
| Required registration or licence, and how it is verified | |
| Calibration or training required before reviewing (e.g. a reference set, written guidance) | |
| Who attests each reviewer (`attested_by` in `reviewers.csv`) | |
| Conflicts that exclude a reviewer | |

## 3. Labelling standard
| Field | Entry |
|---|---|
| Written definitions for each class, especially Caries vs Deep Caries (depth criterion) and Periapical Lesion | |
| Use of the model suggestions shown in Label Studio (allowed as hints only / hidden) | |
| Coverage rule (all target findings on a radiograph must be marked: yes / no; mandatory for Hanoi under P3) | |
| Handling of uncertain findings (`uncertain` decision; never counted) | |

## 4. Second reader
| Field | Entry |
|---|---|
| Required? (yes / no) | |
| If yes: all findings or a subset; subset size and how it is selected (fixed before review) | |
| Blinding of the second reader to the first reader's decision | |
| Agreement statistic to report (e.g. per-class agreement); is there an action threshold? | |

## 5. Adjudication
| Field | Entry |
|---|---|
| What counts as a disagreement (label, box, presence) | |
| Who adjudicates (role; the name in §1 or another named adjudicator) | |
| Is the adjudicated decision final? Are both original decisions kept in the hash-chained log? | |
| How the final decision is recorded (a new review-log record with decision `corrected` / `confirmed` by the adjudicator) | |
| Findings left unresolved are excluded (yes / no) | |

## 6. Documentation and authorization
| Field | Entry |
|---|---|
| Records kept locally (`reviewers.csv`, attestations, calibration results, intake sheets) and where they are stored | |
| Records allowed in Kaggle artifacts (only internal reviewer IDs and dates, per the authorization format) | |
| Validity period of each reviewer authorization; review interval | |
| Revocation procedure and who may revoke (D-B1: a revoked reviewer's labels are refused in new manifests) | |
| Who approves each authorization version (approval scope `reviewer_authorization_issue`) | |
| Ethics / data-use approvals that cover the reviewed images (reference and date) | |

## 7. Sign-off (approval records, not entries in this file)
* **Open gap G7** (`reports/cv5_approval_checklist_amendment03_and_patch.md`): the approval-record scopes include none for a clinical
  governance document. `reviewer_authorization_issue` binds to the *authorization file* when it is issued, not to this document.
  Before sign-off, the owner decides whether to add a scope (e.g. `clinical_governance_decision`; a code and amendment change). Until
  then this document cannot be approved through a record.
* Then:
  - the clinical lead approves the completed copy of this document;
  - the project owner approves it for D-B5;
  - the clinical lead (or the role named in §6) approves each issued authorization version with scope `reviewer_authorization_issue`.

---

## Addendum 2026-10-25: sign-off under the DRAFT approval policy
* `reports/cv5_approval_policy_DRAFT.md` (not in force) proposes the scope `clinical_governance_decision` for this document:
  - the clinical lead approves;
  - the project owner countersigns.
* Each reviewer-authorization version is approved by the clinical lead (`reviewer_authorization_issue`) and countersigned by the owner.
* Both need the approval-tooling patch named in the policy (§2) before records for the new scope can be verified.
* Until a real, qualified clinical lead is appointed and approves, every field above stays empty and pending.
