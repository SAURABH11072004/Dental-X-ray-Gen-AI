# Data expansion audit: finding classifier (before any further model experiments)

Date 2026-10-16. Scope: Steps 1-5 of the data-first plan. **No model was trained.** Production checkpoints, thresholds, the persisted
split file (fingerprint `7f66d59d9cbad925`) and the combined train / validation / calibration / test manifests are unchanged (hashes
re-verified). **No new label has been verified yet**: every number for new data below is a count of radiographs awaiting review.

## 1. Current verified data (unique radiographs, duplicates counted once)

Training split (`data/splits/combined_train.csv` = DENTEX disease subset + DENTEX official-validation labels):

| Class | Findings (= crops) | Unique radiographs with class | of which DENTEX train | of which DENTEX official val |
|---|---:|---:|---:|---:|
| Caries | 1,635 | 467 | 1,550 | 85 |
| Deep Caries | 467 | 250 | 438 | 29 |
| Impacted | 448 | 186 | 412 | 36 |
| **Periapical Lesion** | **129** | **94** | 120 | 9 |

Evaluation splits (unchanged): validation 205 / 45 / 72 / **9**; calibration 206 / 47 / 55 / 16; test 228 / 48 / 65 / 13
(Caries / Deep Caries / Impacted / Periapical Lesion findings). Per-class detail: `reports/expanded_class_distribution.csv`.
Patient identifiers do not exist in any source; all separation is per radiograph.

## 2. Status of every data source

| Source | Status | Unique radiographs | Target labels usable now |
|---|---|---:|---|
| DENTEX disease subset (train/val/cal/test) | **ACQUIRED, labelled** | 678 with findings | yes (in use) |
| DENTEX official validation labels | **ACQUIRED, labelled** | 40 contributing (training only) | yes (in use) |
| DENTEX unlabelled subset | **ACCESSIBLE, UNLABELLED** | 1,537 | no - needs clinician review |
| DENTEX enumeration subset (tooth boxes + FDI, no diagnoses) | **ACCESSIBLE, UNLABELLED** | 251 train-locked + 105 eval-locked | no - needs clinician review |
| DENTEX quadrant subset (no diagnoses) | **ACCESSIBLE, UNLABELLED** | 55 train-locked + 24 eval-locked | no - needs clinician review |
| DENTEX disease-subset images without annotations | **ACCESSIBLE, UNLABELLED** | 16 | no |
| DENTEX official test (Turkish taxonomy) | **ACCESSIBLE, UNLABELLED** (Turkish marks used as hints) | 155 new | no |
| Hanoi periapical dataset (Mendeley, CC BY 4.0) | **ACQUIRED, expert lesion boxes, mapping unverified** | 3,863 | no - tooth assignment + equivalence must be confirmed |
| DENTEX English test labels | **AWAITING AUTHORIZATION** (organizers) | up to 155 new + clean test set | - |
| InReDD-PAN924 (PhysioNet) | **AWAITING AUTHORIZATION** (credentialing + DUA + author approval) | 924 | possibly Impacted / PL after review |
| Tufts Dental Database | **AWAITING AUTHORIZATION** (inquiry to Dr. Panetta) | 1,000 | unknown |
| Dental OPG XRAY, Four-diseases (Mendeley), Children's panoramic, OdontoAI, DenPAR, BRAR | **REJECTED** | - | incompatible taxonomy / modality / domain |

Details, licences and evidence: `reports/additional_dataset_candidates.md` (sections 1-5). Request drafts (not sent):
`reports/data_requests/dentex_organizers_email.md`, `reports/data_requests/tufts_access_request.md`.

## 3. Annotation pool (validated)

`data/annotation/annotation_pool.csv`, audit `reports/annotation_pool_audit.json`:
* 7,827 image files considered, in 6,734 radiograph groups (exact SHA-256 + confirmed near duplicate). 728 groups already carry
  diagnosis labels and are excluded, leaving **6,006 unique unlabelled radiographs**.
* Near duplicates: 51,545 hash candidates, **2 confirmed** (both inside Hanoi). Exact duplicates inside Hanoi: 57 pairs. No pool
  radiograph duplicates a labelled one; no Hanoi image duplicates DENTEX.
* `split_lock`: `train` (306: twin of a project training radiograph), `eval_locked` (129: twin of a val / calibration / test
  radiograph, never trained on), `unassigned` (5,571: new radiographs; split decided by the protocol in section 6).
* Image integrity: every pool image was decoded during scoring or dHash computation; Hanoi XML sizes equal image sizes (3,924 / 3,924).

## 4. Clinician-verified annotation workflow (built, tested, not yet used)

* `scripts/dataset/clinical_review.py`, `data/annotation/README.md`, Label Studio add-on `docker-compose.annotation-review.yml`.
* Model output and external marks appear only as Label Studio **predictions** labelled "SUGGESTION ONLY". Each region needs an
  explicit decision (`confirmed` / `corrected` / `rejected`) plus FDI. "No target finding" / "Not assessable" are recorded but are never
  exported as labels, so there is no healthy class and unlabelled teeth are never negatives.
* Labels are accepted only from accounts listed in `data/annotation/reviewers.csv` with qualification and owner attestation.
  **The registry is empty**: no reviewer has been registered.
* Every import is appended to `clinical_reviews.jsonl` (append-only SHA-256 hash chain; later decisions supersede but never delete
  earlier ones). Original dataset files are never modified; corrections of existing labels are separate records referencing the original id.
* Tests: `tests/test_clinical_review.py` (8 tests): registered-reviewer gate, explicit decision, non-findings never become labels,
  hash-chain tamper detection, suggestion caps, expert-hint precedence.

### Model shortlisting: what it can and cannot do
Production models were run read-only on 4,928 pool radiographs (all 2,014 DENTEX train/unassigned + 2,914 of 3,863 Hanoi; the run was
stopped by the session's low-memory safeguard and can be resumed). The classifier has **no healthy class**: on unlabelled radiographs it
gives P(Periapical Lesion) >= 0.5 for 7,614 of 54,645 DENTEX-pool teeth (14 %), so its probabilities only order the review.
Suggestions are therefore capped (at most 2 PL teeth with p >= 0.9 and 2 DC teeth with p >= 0.8 per radiograph), and expert marks
from other taxonomies take precedence.

### Review batch 1 (`reports/annotation_review_queue.csv`, `data/annotation/review_batch_01_tasks.json`)
| Tier | Radiographs | Basis |
|---|---:|---|
| A: expert hint, periapical | 36 DENTEX-test + 99 Hanoi | DENTEX-test "7-lezyon" tooth marks; Hanoi PAI >= 3 lesion boxes matched to the overlapping model tooth box |
| B: model priority | 135 (124 DENTEX, 9 Hanoi without a matching tooth) | interleaved highest P(PL) / P(DC) |
| C: random audit | 30 (DENTEX only) | seeded random, full review, no suggestions: unbiased yield estimate for the DENTEX pool |
| **Total** | **300** | 495 suggested teeth (1.83 per suggested radiograph) |

## 5. Measurable target (proposal for your approval)

Goal: substantially more **independent** Periapical Lesion and Deep Caries examples before cross-validation / context-resolution work;
no duplication or oversampling to force balance.

| Class | Now (train) | Target before experiments | Gap |
|---|---|---|---|
| Periapical Lesion | 129 findings / 94 radiographs | >= 300 findings from >= 200 radiographs | 171 / 106 |
| Deep Caries | 467 findings / 250 radiographs | >= 750 findings from >= 400 radiographs | 283 / 150 |
| Caries, Impacted | 1,635 / 448 | no target; keep verified labels from reviewed radiographs | - |

Why these numbers: they roughly double (PL) or add +60 % (DC) independent radiographs, which with 5-fold cross-validation gives
about 60 PL and 150 DC evaluation cases per fold instead of 9 and 45 on today's validation split.

Expected yield and capacity: **estimates, not results.**
* Tier A Hanoi (99 radiographs; 172 lesion hints matched to a tooth) could add up to about 170 PL findings *if* the dentist confirms equivalence and
  tooth assignment; the confirmation rate is unknown.
* Tier A DENTEX-test (36 radiographs, 50 "lezyon" tooth marks): up to 50 PL; overlap with "Periapical Lesion" is unverified.
* Tier B and the audit slice: unknown; tier C measures the true rate in the DENTEX pool.
* Review time assumption (to be replaced by measured times): 2-4 min per suggested radiograph, 5-8 min per full review, so batch 1
  takes about **12-20 dentist hours**. Reaching the targets will likely need batch 1 plus part of a batch 2.

## 6. Split protocol for new labels (proposal; nothing is applied yet)

1. Existing validation / calibration / test manifests stay frozen.
2. Verified labels on `train`-locked and `unassigned` radiographs go to **training only**; `eval_locked` radiographs are never trained on.
3. For the planned grouped 5-fold cross-validation, folds are built over radiograph groups (all crops of one radiograph in one fold),
   stratified by source, with the frozen test split excluded; metrics are reported per source (DENTEX vs Hanoi), and Hanoi radiographs
   enter only after full-radiograph review (all four classes marked), so the model cannot learn "Hanoi → Periapical Lesion".
4. No patient-level separation is claimed.

## 7. Gate for Step 6 (model experiments)

Step 6 (grouped 5-fold CV; 224 px / 10 % vs 320 px / 25 % crops) starts only when (a) the targets in section 5 are met with verified
labels, or you explicitly accept a smaller verified set, and (b) the split protocol in section 6 is approved. The existing acceptance
criteria stay unchanged. Kaggle: about 27-28 of the weekly 30 GPU hours were used by the two training runs this week; check the quota
after the weekly reset before scheduling.

## 8. Exact next actions for you

1. **Register the reviewing dentist(s)** in `data/annotation/reviewers.csv` (qualification + your attestation + Label Studio email).
2. Start Label Studio as described in `data/annotation/README.md`, import `review_batch_01_tasks.json` with `review_config.xml`, and
   have the dentist review batch 1 (start with tier A DENTEX-test and the 30 audit radiographs).
3. Approve or amend the targets (section 5) and the split protocol (section 6).
4. Send the two drafted requests (DENTEX organizers, Tufts) and, if you want InReDD, complete PhysioNet credentialing and the DUA.
5. Optional: let me resume scoring of the remaining 949 Hanoi radiographs (stopped by the low-memory safeguard) when the machine has
   free memory: `.venv\Scripts\python.exe scripts\dataset\build_annotation_queue.py score` (resumable).

## 9. Verification pass (2026-10-16, second session)

* Protected state re-checked: split fingerprint `7f66d59d9cbad925` (split file SHA-256 equals the value recorded in
  `combined_split_audit.json`), all combined manifests unchanged, production checkpoints match their sidecars, thresholds file
  `5e03ace1…`, test-set ledger `f117c1a3…` (unchanged since 2026-10-15).
* Reviewer registry: header only, **0 reviewers**.
* Batch 1: 300 radiographs = 300 Label Studio tasks (same pool ids); 36 DENTEX-test radiographs with 50 "7-lezyon" hints; 30 audit
  radiographs (all DENTEX, 0 suggestions, 0 pre-filled predictions); every image exists and matches its recorded SHA-256; none is a
  labelled, eval-locked or duplicate-group radiograph; all 525 rows `pending` with empty reviewer / label fields.
* Fixed: 108 Hanoi task URLs contained unencoded spaces (`Original JPG Images`); image paths are now URL-encoded. The selection and the
  queue CSV are byte-identical; only the task image URLs changed.
* Scoring state: 4,928 records, all unique and matching the pool; **949 Hanoi radiographs remain**; no scorer process is running.
* Pending decisions are listed in `reports/protocol_change_proposals.md` (P1-P5).
