# DentaMind AI: publication readiness, dependency graph and approval-tooling review (2026-10-25)

All values below were verified in this execution unless marked "reported".

## 1. Integrity (verified)
* **Pre-audit set and Amendment 01b change set:** pre-audit 8 / 8 OK; 01b 12 / 12 OK.
* **Protocol, ledger and archive:**
  - protocol `0771b5f8…`;
  - ledger `f117c1a3…`, 5 entries, chain intact;
  - CV5 archive `4ac56843…`, 88 / 88 entries OK.
* **Bundles and protected notebooks:**
  - bundles v3 `9d070fc7…` and v1 `8ce64d26…`; no v2;
  - protected notebooks `dd65c7c7…` / `6bf9ea18…`.
* **Patch set and approvals:**
  - `patches/cv5_patch_set_v1.json` `55271334…` is consistent with all three patches and their "before" target hashes;
  - `git -c core.autocrlf=false apply --check` passes; **not applied**;
  - no approval record, register, log, reviewer authorization or import manifest exists.
* **Repository:** 1 commit; the same 21 pre-existing modified tracked files (preserved; never reset or stashed).
* **Tests:** **533 passed, 0 failed** (524 before this execution, plus 9 new tooling-patch tests).

## 2. Work completed in this execution
| Deliverable | File (SHA-256) |
|---|---|
| Approval-tooling patch (unapplied; separate artifact from the patch set) | `patches/cv5_approvals_policy_tooling.patch` (`de92744b…`, +224 / −1 on `kaggle/cv5_approvals.py` `19d83c42…`) |
| Its tests (on a temporary patched copy; live module untouched) | `tests/test_cv5_approval_tooling_patch.py` (`ffa0693f…`), 9 passed |
| Results traceability builder and table (133 rows, every source checked against SHA256SUMS) | `scripts/build_results_traceability.py` (`49aa00fd…`); `reports/results_traceability.json` (`3b00bd88…`), `.md` (`6b4ae2ec…`) |
| Manuscript draft (verified numbers only; candidate sections BLOCKED) | `reports/manuscript/DentaMind_CV5_manuscript_DRAFT.md` (`be57fcee…`). All 29 cited row IDs exist, the displayed values round exactly from the sources, and all citation keys are in the bibliography |

## 3. Approval-tooling patch: review report

**What it adds:**
* scopes `patch_set_application`, `amendment_01c_freeze` and `clinical_governance_decision`, plus the bootstrap scopes
  `approval_policy_adoption` and `approver_register_issue`;
* `POLICY`: approving role(s), countersigning role(s) and required predecessor scopes for every scope. The superseded
  `import_wiring_patch_application` can no longer be approved;
* a versioned approver register (`validate_register`, `load_register`): content-hashed, version chain, revocation;
* an append-only, hash-chained approval log (`append_log`, `read_log`) that rejects edits, reordering, back-dating and duplicate
  records;
* `write_approval_record`, which never overwrites;
* `verify_approval_policy`, which requires all of:
  - the role authorized for the scope;
  - the approver active in the register at `approved_at`;
  - the record logged and not revoked;
  - the artifact registered in the log no later than the approval;
  - required earlier approvals present;
  - no `execution_started` on the artifact before approval (no retrospective approval);
  - `amendment_01c_freeze` only after a logged `execution_completed` (no advance approval);
  - signature level S0 only;
* `approval_complete`, which requires a countersignature by a different person where the policy demands one.

The existing `verify_approval` API is unchanged.

**Limitations to review (not hidden):**
1. Approvers are matched in the register by exact name and role. Identity is still self-asserted at signature level S0; the register
   limits **who may** approve, not **who did**.
2. "Required predecessor" means a logged, non-revoked approval of that scope. It does not re-verify the predecessor's own countersignature.
3. `POLICY` encodes the DRAFT policy's role table. If the owner changes the policy, the patch must be regenerated and reviewed again.
4. S1 / S2 signatures are not implemented. Any signature claim other than `none` is refused.

**Test coverage (9):** the patch targets the live module and stays unapplied; existing API; a full valid flow (bootstrap → Amendment 03
→ patch set → execution → Amendment 01c → clinical governance) with countersignatures; unauthorized role / person / revoked approver;
self-countersignature; missing predecessor, approval before the artifact existed, retrospective and advance approvals; log duplicate,
overwrite, back-dating, unlogged record, revocation and tampering; register rules; signature claims.

## 4. Dependency graph of the remaining work

```
[PO] adopt approval policy ──► [PO] approver register v1 ──► [IR] review tooling patch ──► [PO] approve & apply tooling patch (+01b-style record)
        │                                     │
        │                                     ├──► [PO+CL] Amendment 03 ──► [IR] review patches 2,3 ──► [PO+IR] patch-set approval
        │                                     │                                                      └─► execute plan v2 steps 5-12
        │                                     │                                                            (incl. Kaggle pre-flight [owner session])
        │                                     │                                                            └─► [PO+IR] Amendment 01c
        │                                     └──► [PO] name clinical lead ──► [CL+PO] clinical governance decision
        │                                                                          └─► [CL+PO] reviewer authorization v1
[ATA] two ledger disclosures (independent)                                               └─► [DATA] clinician review of real data → P2 met
                                                                                                 └─► local manifest + V6 record
[PO] BASE-P2 failure policy F1–F6 ─────────────────────────────────────────────────────────┐        └─► [PO+CL] Amendment 02
[PO] Amendment 01 (candidates) ─────────────────────────────────────────────────────────────┴─► BASE-P2 registration → BASE-P2 run [INFRA]
                                                                                                       → gate R → sealed-metric release → candidate CV runs [INFRA]
                                                                                                       → verdicts → (at most one) ledger test evaluation [ATA]
                                                                                                       → final analysis → manuscript results
```

| Category | Items |
|---|---|
| Executable engineering (no authorization needed) | none outstanding beyond keeping drafts current; all preparable patches, tests, plans and the manuscript draft are done |
| Project owner (PO) | adopt the approval policy; approver register v1; apply the tooling patch; Amendment 03; BASE-P2 failure policy F1–F6; Amendment 01; name the clinical lead; patch-set approval; Amendment 01c; Amendment 02; BASE-P2 registration; metric release |
| Independent reviewer (IR) | review the tooling patch and patches 2 / 3; countersign the patch set and Amendment 01c |
| Accountable test-set authorizer (ATA) | two ledger disclosures (P5 `c8f9b186…`, external run `91083588…`); any future test evaluation |
| Qualified clinical lead (CL) | clinical-governance decision (qualifications, second reader, adjudication, documentation); reviewer authorization v1; countersign Amendments 02 / 03 |
| Blocked by data | P2: Periapical Lesion +171 findings / +106 radiographs, Deep Caries +283 / +150; 0 clinician-verified labels; licensed sources not yet obtained |
| Blocked by infrastructure | Kaggle GPU sessions for the pre-flight, BASE-P2 and 3 × 25 candidate runs; private Kaggle dataset for the imports |

## 5. Publication-readiness assessment

**Highest justified level: "baseline methods-and-protocol report with verified cross-validated results; not ready for an
improvement claim".**

| Gate | Evidence | Status |
|---|---|---|
| Baseline results verified and traceable | `reports/results_traceability.*` | met |
| Pre-registered protocol frozen | protocol `0771b5f8…` | met |
| Candidate improvement evaluated under the protocol | none | **not met: BLOCKED (data, approvals, infrastructure)** |
| Additional clinically verified data (P2) | none | **not met** |
| Test-history disclosures recorded | pending ATA | **not met** |
| Clinical governance | pending CL | **not met** |
| Bibliography verified against DOIs | not done in this session | **not met (author task)** |
| Declarations (ethics, funding, COI, contributions) | placeholders | **not met (authors)** |
| Venue selected and formatted | none | **not met** |

**What could honestly be submitted today,** if the authors choose and after the declarations and bibliography are completed: a paper
reporting the cross-validated BASE baseline, its error analysis, negative results and the pre-registered acceptance protocol. It would
make no improvement claim. The candidate sections would have to be removed, not filled.

## 6. Single next action
The **project owner adopts (or amends) `reports/cv5_approval_policy_DRAFT.md` and issues approver register v1**, after the independent
reviewer reviews `patches/cv5_approvals_policy_tooling.patch`. Every other approval in the graph, including the patch set and the
clinical track, depends on that policy and register.

Recording the two ledger disclosures (ATA) is independent and can happen at any time.
