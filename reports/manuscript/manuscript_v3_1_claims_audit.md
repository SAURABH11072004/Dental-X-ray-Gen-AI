# Manuscript claims audit

* Manuscript: `reports/manuscript/DentaMind_CV5_manuscript_v3_1_journal.md` (sha256 `99c5d21868596a9796e4f1211cb9ca9e166d33ab2d6e5d5f5d53df797874ee4c`)
* Script: `scripts/audit_manuscript_claims.py` (sha256 `5c24e69b78e98c6209c266768fbb892db07c92627f5a8e19562b0c5a676b3042`)

**Result: PASS.** Mechanical evidence only; negated hits still need a human read.

| Kind | Rule | Result | Lines |
|---|---|---|---|
| REQUIRED | latency: classifier-only reported separately | present | 270, 271, 272 |
| REQUIRED | latency: full-pipeline reported separately | present | 273 |
| REQUIRED | latency: checkpoint is not a stored CV5 fold checkpoint | present | 156 |
| REQUIRED | latency: power / thermal state not controlled | present | 155, 331 |
| REQUIRED | latency: hardware-specific | present | 331 |
| REQUIRED | negative results labelled as validation split, not CV5 | present | 112, 249, 360 |
| REQUIRED | negative results not comparable with CV5 | present | 118 |
| REQUIRED | every earlier remedy failed its rule | present | 19 |
| REQUIRED | post-hoc analyses declared descriptive | present | 330 |
| REQUIRED | no improvement claim | present | 51 |
| REQUIRED | no clinical validation | present | 333 |
| REQUIRED | no external test set | present | 324 |
| REQUIRED | candidates not registered or trained | present | 329 |
| REQUIRED | confused findings not called label errors | present | 211 |
| REQUIRED | test split previously used, no test result reported | present | 65 |
| FORBIDDEN | deployment / clinical readiness | absent | - |
| FORBIDDEN | clinical validation claimed | only in negated statements | 333 |
| FORBIDDEN | external validation claimed | absent | - |
| FORBIDDEN | superiority / state of the art | absent | - |
| FORBIDDEN | improvement achieved | absent | - |
| FORBIDDEN | candidates called registered | absent | - |
| FORBIDDEN | diagnostic claim | absent | - |
