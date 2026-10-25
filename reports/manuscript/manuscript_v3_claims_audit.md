# Manuscript claims audit

* Manuscript: `reports/manuscript/DentaMind_CV5_manuscript_v3_journal.md` (sha256 `ec96748ceb507408259c38831a67d31d1a53fb7af9a05c6b90b285bb71701270`)
* Script: `scripts/audit_manuscript_claims.py` (sha256 `5c24e69b78e98c6209c266768fbb892db07c92627f5a8e19562b0c5a676b3042`)

**Result: FAIL.** Mechanical evidence only; negated hits still need a human read.

| Kind | Rule | Result | Lines |
|---|---|---|---|
| REQUIRED | latency: classifier-only reported separately | present | 268, 269, 270 |
| REQUIRED | latency: full-pipeline reported separately | present | 271 |
| REQUIRED | latency: checkpoint is not a stored CV5 fold checkpoint | present | 154 |
| REQUIRED | latency: power / thermal state not controlled | present | 153, 329 |
| REQUIRED | latency: hardware-specific | present | 329 |
| REQUIRED | negative results labelled as validation split, not CV5 | present | 110, 247, 358 |
| REQUIRED | negative results not comparable with CV5 | present | 116 |
| REQUIRED | every earlier remedy failed its rule | present | 19 |
| REQUIRED | post-hoc analyses declared descriptive | present | 328 |
| REQUIRED | no improvement claim | present | 51 |
| REQUIRED | no clinical validation | present | 331 |
| REQUIRED | no external test set | present | 322 |
| REQUIRED | candidates not registered or trained | present | 327 |
| REQUIRED | confused findings not called label errors | present | 209 |
| REQUIRED | test split previously used, no test result reported | **MISSING** | - |
| FORBIDDEN | deployment / clinical readiness | absent | - |
| FORBIDDEN | clinical validation claimed | only in negated statements | 331 |
| FORBIDDEN | external validation claimed | absent | - |
| FORBIDDEN | superiority / state of the art | absent | - |
| FORBIDDEN | improvement achieved | absent | - |
| FORBIDDEN | candidates called registered | absent | - |
| FORBIDDEN | diagnostic claim | absent | - |
