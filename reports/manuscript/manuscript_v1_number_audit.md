# Manuscript number and citation audit

* Manuscript: `reports/manuscript/DentaMind_CV5_manuscript_v1_submission_draft.md` (sha256 `fdc49f437eace3904b3eafc85bcd263f51dce0bfd11a9625a3c6565422312fac`)
* Audit script: `scripts/audit_manuscript_numbers.py` (sha256 `7482e743c3a0267d0e02b7476b476d6bfeb02f044eb42d3917827d41c8379b58`)
* Traceability: `reports/results_traceability.json` (`3b00bd88bb5a5c141343fbb85de4d5bdceeba7cdbcc12f5f732c374a173c6897`), `reports/negative_findings_traceability.json` (`a5810e133860910943c1f70a646b069af6884a784c63a297663f58cb26ac39ed`), `kaggle/artifacts_cv5_run1/cv5_results.json` (`52d94923bebad5596eeccfa26ead92a30237f289e6e4dd40963d13c78b29bd82`, checked against SHA256SUMS.txt)

**Result: PASS.** Numbers traced to a source: 134; declared constants: 62; untraced: 0; unknown tags: 0; distinct tags: 124; citation keys: 16, unknown: 0; reference list matches cited keys: True.

Limits: the audit proves that each number equals a tagged artifact value at its displayed precision, or is a declared constant. It does not prove that the surrounding sentence describes the value correctly; that remains a human check.

## Declared constants used

| Line | Number | Declared as |
|---|---|---|
| 8 | 1 | small count (design / structure; human check) |
| 26 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 31 | 95 | confidence level |
| 31 | 95 | confidence level |
| 57 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 76 | 4 | small count: classes, folds, Hamming distance (human check) |
| 76 | 0.97 | design: near-duplicate r |
| 85 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 93 | 4 | small count: classes, folds, Hamming distance (human check) |
| 95 | 224 | design: crop size |
| 95 | 0.10 | design: context padding |
| 96 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 98 | 15 | design: epochs; protocol lifetime budget k |
| 98 | 32 | design: batch size |
| 101 | 0.5 | design: IoU match threshold |
| 105 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 105 | 42 | design: first seed |
| 105 | 46 | design: last seed |
| 105 | 25 | design: 5 folds x 5 seeds |
| 111 | 2,000 | design: bootstrap resamples |
| 111 | 0 | design: bootstrap seed / zero |
| 112 | 10 | design: ECE bins |
| 119 | 3 | small count (design / structure; human check) |
| 125 | 0.027 | protocol threshold delta |
| 126 | 0 | design: bootstrap seed / zero |
| 126 | 1 | small count (design / structure; human check) |
| 126 | 0.05 | protocol alpha |
| 126 | 15 | design: epochs; protocol lifetime budget k |
| 126 | 20,000 | protocol: B |
| 126 | 15 | design: epochs; protocol lifetime budget k |
| 128 | 4 | small count: classes, folds, Hamming distance (human check) |
| 128 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 128 | 4 | small count: classes, folds, Hamming distance (human check) |
| 128 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 131 | 95 | confidence level |
| 145 | 1 | small count (design / structure; human check) |
| 149 | 1 | small count (design / structure; human check) |
| 149 | 95 | confidence level |
| 151 | 95 | confidence level |
| 158 | 2 | small count (design / structure; human check) |
| 203 | 9 | report-level: validation Periapical Lesion findings (reports/training_summary.md section 1) |
| 207 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 207 | 25 | design: 5 folds x 5 seeds |
| 210 | 3 | small count (design / structure; human check) |
| 212 | 25 | design: 5 folds x 5 seeds |
| 221 | 25 | design: 5 folds x 5 seeds |
| 228 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 228 | 95 | confidence level |
| 233 | 25 | design: 5 folds x 5 seeds |
| 239 | 384 | candidate C1 crop size (design, no result) |
| 239 | 0.25 | candidate C2 padding (design, no result) |
| 254 | 541 | population (also tagged where reported as a result) |
| 260 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 287 | 88 | integrity count verified this session |
| 287 | 88 | integrity count verified this session |
| 288 | 61 | integrity count verified this session |
| 288 | 61 | integrity count verified this session |
| 289 | 39 | integrity count verified this session |
| 289 | 39 | integrity count verified this session |
| 293 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 302 | 133 | row count of results_traceability.json |
| 303 | 49 | row count of negative_findings_traceability.json |

## Citation keys

ayhan, bittar, fpn, guo, hamamciArxiv, hamamciMiccai, imagenet, kapoor, naeini, peker, putra, raeisi, ren, resnet, szabo, tang
