# Manuscript number and citation audit

* Manuscript: `reports/manuscript/DentaMind_CV5_manuscript_v2_journal.md` (sha256 `993c7b668e166216b5ad07dbf34036ae17417a1e7b28d761d9d0fed736235443`)
* Audit script: `scripts/audit_manuscript_numbers.py` (sha256 `ef676b468c79118cf363bb69c9753512fd9a789c5d943518a0f954b277c689ab`)
* Traceability: `reports/results_traceability.json` (`3b00bd88bb5a5c141343fbb85de4d5bdceeba7cdbcc12f5f732c374a173c6897`), `reports/negative_findings_traceability.json` (`a5810e133860910943c1f70a646b069af6884a784c63a297663f58cb26ac39ed`), `kaggle/artifacts_cv5_run1/cv5_results.json` (`52d94923bebad5596eeccfa26ead92a30237f289e6e4dd40963d13c78b29bd82`, checked against SHA256SUMS.txt)

**Result: PASS.** Numbers traced to a source: 170; declared constants: 64; untraced: 0; unknown tags: 0; distinct tags: 99; citation keys: 16, unknown: 0; reference list matches cited keys: no reference list found.

Limits: the audit proves that each number equals a tagged artifact value at its displayed precision, or is a declared constant. It does not prove that the surrounding sentence describes the value correctly; that remains a human check.

## Declared constants used

| Line | Number | Declared as |
|---|---|---|
| 17 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 19 | 95 | confidence level |
| 45 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 68 | 4 | small count: classes, folds, Hamming distance (human check) |
| 68 | 0.97 | design: near-duplicate r |
| 72 | 224 | design: crop size |
| 72 | 0.10 | design: context padding |
| 74 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 76 | 15 | design: epochs; protocol lifetime budget k |
| 76 | 32 | design: batch size |
| 79 | 0.5 | design: IoU match threshold |
| 83 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 83 | 42 | design: first seed |
| 83 | 46 | design: last seed |
| 83 | 25 | design: 5 folds x 5 seeds |
| 83 | 1 | small count (design / structure; human check) |
| 101 | 2,000 | design: bootstrap resamples |
| 101 | 0 | design: bootstrap seed / zero |
| 103 | 10 | design: ECE bins |
| 115 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 115 | 25 | design: 5 folds x 5 seeds |
| 122 | 0.027 | protocol threshold delta |
| 123 | 20,000 | protocol: B |
| 123 | 1 | small count (design / structure; human check) |
| 123 | 0.05 | protocol alpha |
| 123 | 15 | design: epochs; protocol lifetime budget k |
| 123 | 15 | design: epochs; protocol lifetime budget k |
| 124 | 4 | small count: classes, folds, Hamming distance (human check) |
| 124 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 124 | 4 | small count: classes, folds, Hamming distance (human check) |
| 124 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 128 | 95 | confidence level |
| 143 | 1 | small count (design / structure; human check) |
| 143 | 95 | confidence level |
| 145 | 95 | confidence level |
| 152 | 2 | small count (design / structure; human check) |
| 158 | 2 | small count (design / structure; human check) |
| 158 | 95 | confidence level |
| 173 | 3 | small count (design / structure; human check) |
| 182 | 2 | small count (design / structure; human check) |
| 191 | 4 | small count: classes, folds, Hamming distance (human check) |
| 203 | 3 | small count (design / structure; human check) |
| 203 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 207 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 207 | 95 | confidence level |
| 209 | 3 | small count (design / structure; human check) |
| 211 | 25 | design: 5 folds x 5 seeds |
| 224 | 25 | design: 5 folds x 5 seeds |
| 285 | 1 | small count (design / structure; human check) |
| 285 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 287 | 2 | small count (design / structure; human check) |
| 289 | 3 | small count (design / structure; human check) |
| 289 | 95 | confidence level |
| 291 | 4 | small count: classes, folds, Hamming distance (human check) |
| 293 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 301 | 88 | integrity count verified this session |
| 301 | 88 | integrity count verified this session |
| 302 | 61 | integrity count verified this session |
| 302 | 61 | integrity count verified this session |
| 303 | 39 | integrity count verified this session |
| 303 | 39 | integrity count verified this session |
| 306 | 3 | small count (design / structure; human check) |
| 308 | 133 | row count of results_traceability.json |
| 308 | 49 | row count of negative_findings_traceability.json |

## Citation keys

ayhan, bittar, fpn, guo, hamamciArxiv, hamamciMiccai, imagenet, kapoor, naeini, peker, putra, raeisi, ren, resnet, szabo, tang
