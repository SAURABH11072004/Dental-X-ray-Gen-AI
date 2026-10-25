# Manuscript number and citation audit

* Manuscript: `reports/manuscript/DentaMind_CV5_manuscript_v3_journal.md` (sha256 `ec96748ceb507408259c38831a67d31d1a53fb7af9a05c6b90b285bb71701270`)
* Audit script: `scripts/audit_manuscript_numbers.py` (sha256 `83b3d29271ca1447dfa8da4e1ccb9129e53be17a91caa180bfb0639a0107f0a5`)
* Traceability: `reports/results_traceability.json` (`3b00bd88bb5a5c141343fbb85de4d5bdceeba7cdbcc12f5f732c374a173c6897`), `reports/negative_findings_traceability.json` (`a5810e133860910943c1f70a646b069af6884a784c63a297663f58cb26ac39ed`), `kaggle/artifacts_cv5_run1/cv5_results.json` (`52d94923bebad5596eeccfa26ead92a30237f289e6e4dd40963d13c78b29bd82`, checked against SHA256SUMS.txt)

**Result: PASS.** Numbers traced to a source: 222; declared constants: 95; untraced: 0; unknown tags: 0; distinct tags: 115; citation keys: 16, unknown: 0; reference list matches cited keys: no reference list found.

Limits: the audit proves that each number equals a tagged artifact value at its displayed precision, or is a declared constant. It does not prove that the surrounding sentence describes the value correctly; that remains a human check.

## Declared constants used

| Line | Number | Declared as |
|---|---|---|
| 3 | 3 | small count (design / structure; human check) |
| 3 | 3 | small count (design / structure; human check) |
| 3 | 6 | figure / table / contribution number |
| 3 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 17 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 19 | 95 | confidence level |
| 19 | 3050 | hardware model name (RTX 3050) |
| 45 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 69 | 4 | small count: classes, folds, Hamming distance (human check) |
| 69 | 0.97 | design: near-duplicate r |
| 73 | 224 | design: crop size |
| 73 | 0.10 | design: context padding |
| 75 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 77 | 15 | design: epochs; protocol lifetime budget k |
| 77 | 32 | design: batch size |
| 80 | 0.5 | design: IoU match threshold |
| 84 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 84 | 42 | design: first seed |
| 84 | 46 | design: last seed |
| 84 | 25 | design: 5 folds x 5 seeds |
| 84 | 1 | small count (design / structure; human check) |
| 102 | 2,000 | design: bootstrap resamples |
| 102 | 0 | design: bootstrap seed / zero |
| 104 | 10 | design: ECE bins |
| 116 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 116 | 25 | design: 5 folds x 5 seeds |
| 123 | 0.027 | protocol threshold delta |
| 124 | 20,000 | protocol: B |
| 124 | 1 | small count (design / structure; human check) |
| 124 | 0.05 | protocol alpha |
| 124 | 15 | design: epochs; protocol lifetime budget k |
| 124 | 15 | design: epochs; protocol lifetime budget k |
| 125 | 4 | small count: classes, folds, Hamming distance (human check) |
| 125 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 125 | 4 | small count: classes, folds, Hamming distance (human check) |
| 125 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 129 | 95 | confidence level |
| 142 | 0.3 | design: detector score threshold (kaggle/dentamind_kaggle.DET_SCORE) |
| 143 | 0.5 | design: IoU match threshold |
| 144 | 0.5 | design: IoU match threshold |
| 153 | 3050 | hardware model name (RTX 3050) |
| 153 | 4 | small count: classes, folds, Hamming distance (human check) |
| 153 | 2.6 | software version (torch 2.6; latency_benchmark environment) |
| 153 | 12.4 | software version (CUDA 12.4; latency_benchmark environment) |
| 155 | 1 | small count (design / structure; human check) |
| 155 | 64 | protocol section 7: latency batch size |
| 155 | 32 | design: batch size |
| 156 | 20 | protocol/rule: cross pairs minimum |
| 165 | 1 | small count (design / structure; human check) |
| 165 | 95 | confidence level |
| 167 | 95 | confidence level |
| 174 | 2 | small count (design / structure; human check) |
| 180 | 2 | small count (design / structure; human check) |
| 180 | 95 | confidence level |
| 195 | 3 | small count (design / structure; human check) |
| 204 | 2 | small count (design / structure; human check) |
| 211 | 3 | small count (design / structure; human check) |
| 211 | 6 | figure / table / contribution number |
| 215 | 0.5 | design: IoU match threshold |
| 218 | 3 | small count (design / structure; human check) |
| 220 | 0.5 | design: IoU match threshold |
| 229 | 4 | small count: classes, folds, Hamming distance (human check) |
| 241 | 4 | small count: classes, folds, Hamming distance (human check) |
| 241 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 245 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 245 | 95 | confidence level |
| 247 | 4 | small count: classes, folds, Hamming distance (human check) |
| 249 | 25 | design: 5 folds x 5 seeds |
| 262 | 25 | design: 5 folds x 5 seeds |
| 262 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 264 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 264 | 3050 | hardware model name (RTX 3050) |
| 264 | 4 | small count: classes, folds, Hamming distance (human check) |
| 264 | 1 | small count (design / structure; human check) |
| 268 | 1 | small count (design / structure; human check) |
| 269 | 64 | protocol section 7: latency batch size |
| 270 | 1 | small count (design / structure; human check) |
| 350 | 1 | small count (design / structure; human check) |
| 350 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 352 | 2 | small count (design / structure; human check) |
| 354 | 3 | small count (design / structure; human check) |
| 354 | 95 | confidence level |
| 356 | 4 | small count: classes, folds, Hamming distance (human check) |
| 358 | 5 | small count: folds, seeds, weight cap, ledger entries (human check) |
| 360 | 6 | figure / table / contribution number |
| 360 | 0.5 | design: IoU match threshold |
| 368 | 88 | integrity count verified this session |
| 368 | 88 | integrity count verified this session |
| 369 | 61 | integrity count verified this session |
| 369 | 61 | integrity count verified this session |
| 370 | 39 | integrity count verified this session |
| 370 | 39 | integrity count verified this session |
| 373 | 3 | small count (design / structure; human check) |
| 375 | 133 | row count of results_traceability.json |
| 375 | 49 | row count of negative_findings_traceability.json |

## Citation keys

ayhan, bittar, fpn, guo, hamamciArxiv, hamamciMiccai, imagenet, kapoor, naeini, peker, putra, raeisi, ren, resnet, szabo, tang
