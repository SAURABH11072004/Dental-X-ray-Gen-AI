# Candidate-run readiness (C1 384 px crops, C2 0.25 padding, C3 ConvNeXt-Tiny): v1

Date 2026-10-25. Every row was checked against files in this session.

**Verdict: NOT READY. No training is permitted.**

| Gate (protocol / plan v2) | Required evidence | Found | Status |
|---|---|---|---|
| Approval policy adopted; approver register v1 | approval records + `reports/approvals/` | no `reports/approvals/` directory; no record files | **missing** |
| Approval-tooling patch reviewed and applied | IR review + PO approval; `kaggle/cv5_approvals.py` changed | `cv5_approvals.py` unchanged (`19d83c42…`); patch `de92744b…` unapplied | **missing** |
| Amendment 01 (candidate registration) | approved, frozen configurations | file status "DRAFT … NOT REGISTERED" | **missing** |
| Amendment 01b (implementation freeze) | approved | file status "DRAFT"; change set 12 / 12 hashes intact | **missing (approval)** |
| Amendment 03 (decisions D-B1 to D-B6) | approved | "DRAFT … NOT IN FORCE" | **missing** |
| Patch set applied + post-application checks | approval; plan v2 steps 5–12 executed | `make_cv5_notebook.py` still `4a5efda8…` (before-state); manifest `55271334…` | **not applied** |
| Amendment 01c (post-application freeze) | approved after execution | empty skeleton | **missing** |
| Amendment 02 / BASE-P2 registration | approved | "DRAFT skeleton … NOT REGISTERED. BASE-P2 must not be run" | **missing** |
| BASE-P2 run completed (gate R) | archived run | none | **missing** |
| Clinician-verified imports (P2) / reviewer authorization | reviewer authorization v1, import manifest | none; 0 verified labels | **missing** |
| Ledger disclosures (two pending) | ledger entries by the ATA | ledger `f117c1a3…`, 5 entries, unchanged | **pending** |
| Candidate budget | registered count ≤ 15 | 0 registered | n/a until Amendment 01 |
| Infrastructure | Kaggle GPU sessions | available to the owner; not used | owner action |

**Order of unblocking:**
1. IR review of the tooling patch.
2. PO adopts the policy and issues register v1.
3. The tooling patch is applied.
4. Amendment 03.
5. Patch-set approval, then plan v2 steps 5–12, then Amendment 01c.
6. Amendment 01, the BASE-P2 failure policy and Amendment 02.
7. The BASE-P2 run, then gate R.
8. The candidate runs.
