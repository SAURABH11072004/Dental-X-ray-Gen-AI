# Manuscript number and citation audit

* Manuscript: `reports/manuscript/DentaMind_CV5_manuscript_v3_1_journal.md` (sha256 `99c5d21868596a9796e4f1211cb9ca9e166d33ab2d6e5d5f5d53df797874ee4c`)
* Audit script: `scripts/audit_manuscript_numbers.py` (sha256 `83b3d29271ca1447dfa8da4e1ccb9129e53be17a91caa180bfb0639a0107f0a5`)
* Traceability: `reports/results_traceability.json` (`3b00bd88bb5a5c141343fbb85de4d5bdceeba7cdbcc12f5f732c374a173c6897`), `reports/negative_findings_traceability.json` (`a5810e133860910943c1f70a646b069af6884a784c63a297663f58cb26ac39ed`), `kaggle/artifacts_cv5_run1/cv5_results.json` (`52d94923bebad5596eeccfa26ead92a30237f289e6e4dd40963d13c78b29bd82`, checked against SHA256SUMS.txt)

**Result: PASS.** Numbers traced to a source: 222; declared constants: 95; untraced: 0; unknown tags: 0; distinct tags: 115; citation keys: 16, unknown: 0; reference list matches cited keys: no reference list found.

Limits: the audit proves that each number equals a tagged artifact value at its displayed precision, or is a declared constant. It does not prove that the surrounding sentence describes the value correctly; that remains a human check.

## Declared constants used

| Line | Number | Declared as |
|---|---|---|
| 3 | 3 | small count (design / structure; human check) |
| 3 | 6 | figure / table / contribution number |
| 3 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 17 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 19 | 95 | confidence level |
| 19 | 3050 | hardware model name (RTX 3050) |
| 45 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 65 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 71 | 4 | small count: classes, folds, Hamming distance (human check) |
| 71 | 0.97 | design: near-duplicate r |
| 75 | 224 | design: crop size |
| 75 | 0.10 | design: context padding |
| 77 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 79 | 15 | design: epochs; protocol lifetime budget k |
| 79 | 32 | design: batch size |
| 82 | 0.5 | design: IoU match threshold |
| 86 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 86 | 42 | design: first seed |
| 86 | 46 | design: last seed |
| 86 | 25 | design: 5 folds x 5 seeds |
| 86 | 1 | small count (design / structure; human check) |
| 104 | 2,000 | design: bootstrap resamples |
| 104 | 0 | design: bootstrap seed / zero |
| 106 | 10 | design: ECE bins |
| 118 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 118 | 25 | design: 5 folds x 5 seeds |
| 125 | 0.027 | protocol threshold delta |
| 126 | 20,000 | protocol: B |
| 126 | 1 | small count (design / structure; human check) |
| 126 | 0.05 | protocol alpha |
| 126 | 15 | design: epochs; protocol lifetime budget k |
| 126 | 15 | design: epochs; protocol lifetime budget k |
| 127 | 4 | small count: classes, folds, Hamming distance (human check) |
| 127 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 127 | 4 | small count: classes, folds, Hamming distance (human check) |
| 127 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 131 | 95 | confidence level |
| 144 | 0.3 | design: detector score threshold (kaggle/dentamind_kaggle.DET_SCORE) |
| 145 | 0.5 | design: IoU match threshold |
| 146 | 0.5 | design: IoU match threshold |
| 155 | 3050 | hardware model name (RTX 3050) |
| 155 | 4 | small count: classes, folds, Hamming distance (human check) |
| 155 | 2.6 | software version (torch 2.6; latency_benchmark environment) |
| 155 | 12.4 | software version (CUDA 12.4; latency_benchmark environment) |
| 157 | 1 | small count (design / structure; human check) |
| 157 | 64 | protocol section 7: latency batch size |
| 157 | 32 | design: batch size |
| 158 | 20 | protocol/rule: cross pairs minimum |
| 167 | 1 | small count (design / structure; human check) |
| 167 | 95 | confidence level |
| 169 | 95 | confidence level |
| 176 | 2 | small count (design / structure; human check) |
| 182 | 2 | small count (design / structure; human check) |
| 182 | 95 | confidence level |
| 197 | 3 | small count (design / structure; human check) |
| 206 | 2 | small count (design / structure; human check) |
| 213 | 3 | small count (design / structure; human check) |
| 213 | 6 | figure / table / contribution number |
| 217 | 0.5 | design: IoU match threshold |
| 220 | 3 | small count (design / structure; human check) |
| 222 | 0.5 | design: IoU match threshold |
| 231 | 4 | small count: classes, folds, Hamming distance (human check) |
| 243 | 4 | small count: classes, folds, Hamming distance (human check) |
| 243 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 247 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 247 | 95 | confidence level |
| 249 | 4 | small count: classes, folds, Hamming distance (human check) |
| 251 | 25 | design: 5 folds x 5 seeds |
| 264 | 25 | design: 5 folds x 5 seeds |
| 264 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 266 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 266 | 3050 | hardware model name (RTX 3050) |
| 266 | 4 | small count: classes, folds, Hamming distance (human check) |
| 266 | 1 | small count (design / structure; human check) |
| 270 | 1 | small count (design / structure; human check) |
| 271 | 64 | protocol section 7: latency batch size |
| 272 | 1 | small count (design / structure; human check) |
| 352 | 1 | small count (design / structure; human check) |
| 352 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 354 | 2 | small count (design / structure; human check) |
| 356 | 3 | small count (design / structure; human check) |
| 356 | 95 | confidence level |
| 358 | 4 | small count: classes, folds, Hamming distance (human check) |
| 360 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 362 | 6 | figure / table / contribution number |
| 362 | 0.5 | design: IoU match threshold |
| 370 | 88 | integrity count verified this session |
| 370 | 88 | integrity count verified this session |
| 371 | 61 | integrity count verified this session |
| 371 | 61 | integrity count verified this session |
| 372 | 39 | integrity count verified this session |
| 372 | 39 | integrity count verified this session |
| 375 | 3 | small count (design / structure; human check) |
| 377 | 133 | row count of results_traceability.json |
| 377 | 49 | row count of negative_findings_traceability.json |

## Citation keys

ayhan, bittar, fpn, guo, hamamciArxiv, hamamciMiccai, imagenet, kapoor, naeini, peker, putra, raeisi, ren, resnet, szabo, tang
