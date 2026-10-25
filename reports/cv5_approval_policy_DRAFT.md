# CV5 approval policy (DRAFT, NOT IN FORCE)

Date 2026-10-25. Resolves the approval-mechanism gaps G1–G7 of `reports/cv5_approval_checklist_amendment03_and_patch.md` as a
**proposal**.
* It takes effect only when the project owner approves it.
* That approval is the bootstrap step and cannot use this policy itself; see §8.
* No person is named, no credential is assumed, and no approval record, register or log has been created.
* Items marked **[INSTITUTION]** depend on rules of the institution that the assistant does not know. Items marked **[CLINICAL]** are
  for a real, qualified clinical lead.

## 1. Roles (functions, not people)

| Role | Holds | Appointed by |
|---|---|---|
| **Project owner (PO)** | accountability for the CV5 programme, amendments, patches, BASE-P2 | [INSTITUTION] |
| **Accountable test-set authorizer (ATA)** | ledger entries (test-set use and disclosures) | PO, unless the institution says otherwise; may be the PO |
| **Clinical lead (CL)** | clinical governance: reviewer qualifications, labelling standard, second reader, adjudication | PO; must be a qualified clinician [CLINICAL] |
| **Independent reviewer (IR)** | technical review of patches (a person other than the author of the change, where available) | PO |
| **Academic supervisor / institution** | any approval the institution requires in addition | [INSTITUTION] |

The assistant holds no role and never approves, signs, countersigns or records on anyone's behalf.

## 2. Artifact-bound scopes and who approves them (G1)

Every approval binds **one artifact by SHA-256** (`cv5_approvals.verify_approval`).

| Scope | Artifact bound | Approver | Countersignature |
|---|---|---|---|
| `approval_policy_adoption` *(new)* | this policy file | PO | [INSTITUTION] |
| `approver_register_issue` *(new)* | each approver-register version (§4) | PO | [INSTITUTION] |
| `amendment_01_registration` | Amendment 01 | PO | — |
| `amendment_01b_freeze` | Amendment 01b | PO | — |
| `amendment_01c_freeze` *(new)* | the completed Amendment 01c (only after plan v2 step 12) | PO | IR (technical evidence reviewed) |
| `amendment_02_registration` | Amendment 02 | PO | CL (the imported labels follow the approved clinical governance) |
| `amendment_03_decisions` | Amendment 03 | PO | CL for the D-B5 part |
| `patch_set_application` *(new)* | `patches/cv5_patch_set_v1.json` (binds the three patches) | PO | IR (patches 2 and 3 reviewed independently) |
| `import_wiring_patch_application` | (superseded by `patch_set_application`; not used) | — | — |
| `base_p2_registration` | the BASE-P2 registration file | PO | — |
| `base_p2_metrics_release` | the sealed metrics archive | PO | — |
| `base_p2_failure_resolution` | a failed BASE-P2 `run_status.json` | PO | — |
| `clinical_governance_decision` *(new; closes G7)* | the completed clinical-governance decision document | CL | PO |
| `reviewer_authorization_issue` | each reviewer-authorization version | CL | PO |
| Ledger disclosures / test-set use | the ledger's own CLI (`--authorized-by`) | ATA | — (unchanged mechanism, G6) |

**Tooling dependency.** The scopes marked *(new)* are not yet accepted by `kaggle/cv5_approvals.py`, whose fixed scope list refuses
unknown scopes. Adding them, plus register and log checks, is a code change that needs its own reviewed patch before this policy can be
enforced. Until then, records for these scopes cannot be verified, and the GO criteria that need them stay NO-GO.

## 3. Signature strength (G2)

| Level | Meaning | Status |
|---|---|---|
| S0 procedural record | a `dentamind-human-approval-v1` JSON (`signature: {"type": "none"}`), hash-bound, in the append-only log | available now; proves a statement was recorded, not who made it |
| S1 institutional e-signature | the approval record (or its SHA-256) signed with the institution's e-signature system, with the signed file kept beside the record | [INSTITUTION]: tooling and verifier not available here |
| S2 cryptographic signature | the record signed with a key registered in the approver register (e.g. GPG / SSH signing), verified against that key | [INSTITUTION]: not implemented; `verify_approval` currently refuses any signature claim it cannot verify |

**Proposal.** The required level per scope is set by the institution.
* Until set, S0 records are accepted as evidence of a statement only, and every human role confirms their own records in person or by
  institutional e-mail to the PO.
* Nothing is described as "digitally signed" unless an S1 or S2 verification actually ran.

## 4. Approver register (G1)

A versioned JSON, written once per version, chained like the reviewer authorization (`previous_version_sha256`). Proposed path:
`reports/approvals/approver_register_v<N>.json`. Not created.
* **Entries:** person ID (internal), role(s), allowed scopes, valid from / to, status (active / revoked), and the public-key fingerprint
  if S2 is adopted.
* **Personal data:** names may appear, because these are accountable approvers. Registration numbers stay with the institution.
* **Each version** is approved with scope `approver_register_issue` by the PO.
* **Check:** an approval is valid only if its approver is active in the register version current at `approved_at`, in a role allowed
  for that scope.

## 5. Time ordering (G3)

* `approved_at` must be later than the artifact's creation, evidenced by the artifact's first appearance in the approval log or the
  execution log. It must also be later than the approval of every artifact it depends on, and not in the future.
* **Required order:**
  1. approval policy;
  2. approver register v1;
  3. Amendment 03;
  4. patch set;
  5. (execution of plan v2, steps 5–12);
  6. Amendment 01c.

  Separately:
  - Amendment 01 comes before Amendment 02, which comes before the BASE-P2 registration, then the BASE-P2 run, then gate R, then the
    metrics release;
  - the clinical-governance decision comes before reviewer authorization v1, which comes before any import manifest.
* **No retrospective approval:** an approval may not cover work already performed. Plan v2 steps 5–12 run only after step 4's approval
  is logged.
* **No advance approval:** Amendment 01c is approved only after its evidence exists.

## 6. Append-only approval log (G5)

Proposed `reports/approvals/approval_log.jsonl` (not created).
* **Entries:** one JSON line per event, hash-chained (`prev_hash`, `entry_hash`), in the same pattern as the clinical review log.
* **Events:** `approval_recorded` (record path and SHA-256, scope, artifact SHA-256), `approval_superseded`, `approval_revoked`,
  `register_issued`.
* **Rules:**
  - lines are never edited or deleted;
  - a correction is a new event;
  - conflicting approvals for one artifact are resolved by the latest non-revoked event of an authorized approver.
* **Verification** checks the chain, the record hashes, the register (§4) and the order (§5). This needs the tooling patch in §2.

## 7. Clinical governance and countersignature (G7)

* **CL decides:** the clinical-governance decision (`reports/templates/clinical_governance_decision_template.md`) is completed and
  approved by the CL (`clinical_governance_decision`) and countersigned by the PO.
* **Reviewer authorization:** each version is approved by the CL and countersigned by the PO.
* **Amendment 02:** countersigned by the CL.
* **Until a real, qualified CL is appointed and approves:**
  - qualifications, second reader, adjudication and documentation stay **pending**;
  - no reviewer authorization is issued;
  - no import manifest is built.
* **Not invented here:** no clinical lead, credential or clinical decision.

## 8. Adoption (bootstrap)

The PO adopts this policy with an S0 record of scope `approval_policy_adoption` bound to this file. The PO then issues approver
register v1, which needs the tooling patch first. Both records are the first two lines of the approval log. [INSTITUTION] may require
a further confirmation.

## 9. Open decisions

| Decision | Responsible |
|---|---|
| Who holds PO, ATA, IR; whether institutional approval is also required | PO / [INSTITUTION] |
| Signature level per scope (S0 / S1 / S2) | [INSTITUTION] |
| Appointment of the clinical lead | PO; the CL must be qualified [CLINICAL] |
| Tooling patch for new scopes, register and log checks | PO approves; to be prepared as a reviewed patch |

---

## Addendum 2026-10-25: enforcement tooling prepared (unapplied)
* `patches/cv5_approvals_policy_tooling.patch` (`de92744b…`) implements §2 (role table as `POLICY`), §4 (register), §5 (ordering) and
  §6 (log) at signature level S0.
* Review report: `reports/publication_readiness_and_dependencies.md` §3.
* It is applied only after this policy is adopted and the patch is reviewed and approved.
