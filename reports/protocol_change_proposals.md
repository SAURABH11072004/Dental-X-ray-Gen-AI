# Protocol change proposals: owner decisions recorded 2026-10-16

Decisions were given by the project owner on 2026-10-16 (table B). Unless stated in section D, the current protocol still applies: split fingerprint
`7f66d59d9cbad925`, frozen validation / calibration / test manifests, existing acceptance criteria, production checkpoints and abstention
threshold, and the test-set ledger (`data/reports/test_set_ledger.json`, 5 entries, SHA-256 prefix `f117c1a32cc0cb76`, chain intact,
last modified 2026-10-15).

## A. What code already enforces (no decision needed; these safeguards stay whatever you decide)

* Only labels from reviewers in `data/annotation/reviewers.csv` with an explicit decision are accepted (`clinical_review.py`).
* Training eligibility at export is re-derived from `annotation_pool.csv` and the frozen evaluation manifests: evaluation radiographs
  and `eval_locked` twins are always excluded, whatever the task metadata says.
* Hanoi labels are excluded unless coverage = "all target findings on this radiograph are marked".
* Verified labels are written to `data/annotation/verified_findings.csv` but are **not** read by any training or manifest code.

## B. Decisions required from you

| ID | Proposal | What approval would change | Recommendation | Your decision (approve / amend / reject, name, date) |
|---|---|---|---|---|
| **P1** | New clinician-verified labels may enter **training only**; validation / calibration / test stay frozen. | Allows writing the opt-in step that adds `verified_findings.csv` to the training manifest (code not written yet). Rejecting keeps verified labels out of training. | Approve | **APPROVED** (owner, 2026-10-16) |
| **P2** | **Provisional** targets before further experiments: Periapical Lesion >= 300 findings from >= 200 unique radiographs; Deep Caries >= 750 findings from >= 400 unique radiographs (training split, verified labels, no duplication). | Sets the gate for the cross-validation and context/resolution experiments. Today: PL 129 / 94, DC 467 / 250. | Approve as provisional; revisit after batch 1 | **APPROVED PROVISIONALLY** (owner, 2026-10-16) |
| **P3** | Hanoi radiographs require a **complete four-class review**; all results are reported separately by source. | Makes the already-coded exclusion official, and adds per-source reporting to future experiment reports. Rejecting keeps all Hanoi labels out of training. | Approve | **APPROVED** (owner, 2026-10-16) |
| **P4** | **Grouped 5-fold cross-validation for future experiments only**; all crops of a radiograph stay in one fold; the exact fold assignment is reviewed and approved before any run; the frozen test split is excluded; acceptance criteria unchanged. | Allows preparing a fold-assignment file for your review. No experiment runs without a second approval of that file. | Approve in principle | **APPROVED WITH REVIEW GATE** (owner, 2026-10-16) |
| **P5** | **Record the 2026-10-16 Kaggle Version 2 baseline test-set evaluation** in `data/reports/test_set_ledger.json`. | Appends one hash-chained disclosure entry using the implementation in section C (not applied). | Approve, including a named authorizer (see C.4) | **APPROVED; authorizer NOT PROVIDED. Ledger edit BLOCKED until the authorizer is confirmed** |

## C. P5: proposed ledger implementation (investigated; not applied)

### C.1 Why the existing API cannot be used as-is
`dentexmodel.evaluation.test_ledger` exposes `authorize()` + `record()`, a **gate for future** test evaluations. For this retrospective
record it is unsuitable:
1. `authorize()` needs a registered checkpoint (`ModelInfo`) with a training manifest and an `eval_<version>_val.json` validation report
   for the same file. The Kaggle checkpoints have neither, so they are refused as legacy, and only seed 45's file is on disk.
2. **Side effect:** a non-historical `final_metrics` entry for task `classification` occupies the one candidate slot per task on the
   current split version (`test_candidate_limit`). Recording the Kaggle baseline that way would **block** the final test evaluation of a
   future improved classifier. That must not happen.
3. `scripts/test_set_ledger.py` only has status / `--init` / `--verify`; there is no append command.

### C.2 Proposed minimal implementation
* Add one public function to `src/dentexmodel/evaluation/test_ledger.py`:
  `record_retrospective_disclosure(settings, entry_fields, authorized_by, reason)`. It
  1. calls `ensure_ledger()` and refuses if `verify_chain()` reports any problem;
  2. refuses a duplicate (same `kind` and same set of checkpoint SHA-256s already present);
  3. requires a named `authorized_by` (same name rule) and a reason of at least 20 characters, as `authorize()` does;
  4. appends via the existing `_append()` / `_write()` (same hash chain and atomic write), with
     `kind = "retrospective_disclosure"`, a **new kind** used only for disclosures. It is not `final_metrics`, so it does not consume the
     candidate slot, but it is listed in `prior_uses_for_task`, so every future test report states that the split was used again.
* Add `--record-disclosure <entry.json> --authorized-by "<name>" --reason "<text>"` to `scripts/test_set_ledger.py`, followed by
  automatic `--verify`.
* Tests on a temporary ledger: the chain stays valid; a duplicate is refused; a tampered ledger is refused; `authorize()` for a future
  candidate is **not** blocked by the disclosure entry; `status()` lists the disclosure.
* No change to inference, training, thresholds or any other ledger entry.

### C.3 Entry content (every value from files on disk, with its source)
| Field | Value | Source |
|---|---|---|
| kind | `retrospective_disclosure` | new kind (C.2) |
| task | `classification` | |
| what | BASE recipe (C0r), seeds 42-46, test split evaluated **once**, GT-box crops, after selection on validation | `test_eval.json`, notebook |
| evaluated_at | `2026-10-16T11:53:27` (Kaggle container clock, UTC; run started `2026-10-16T09:45:49Z`) | `training_log.txt` line 679, `environment.json` |
| checkpoint_sha256 (5) | s42 `6c610485…`, s43 `aa5e7f9b…`, s44 `9e948343…`, s45 `3e0ab876…`, s46 `f098a7b2…` (full hashes in the run files) | `runs/BASE_s*.json` |
| split_version | assignments `1c350480eed2ae96`, manifest `932b0b94…` (unchanged today); combined_test.csv `749af264…` (identical to the frozen local file) | `split_version()`, package copy |
| n | 354 findings on 73 radiographs | `test_eval.json` |
| metrics | GT-box macro-F1 per seed 0.734 / 0.668 / 0.693 / 0.711 / 0.661, mean 0.693 +- 0.030; mean recall Caries 0.912, Deep Caries 0.463, Impacted 0.938, PL 0.369 | `test_eval.json` |
| report | `checkpoints/kaggle_candidates/dc9c505b/test_eval.json` (SHA-256 `95f386b5…`); archive `dc9c505b…b2f9` | staged archive |
| script | Kaggle notebook `btechgd10/dentamind-ai-balanced-training`, Version 2 | |
| selection | none on test: candidate selection used validation only; no candidate passed, so only BASE was evaluated | `selection.json` |
| authorized_by | **not recorded at run time; must be supplied by you** (the person who authorized the run). It will not be invented. | |

### C.4 What I need from you for P5
1. Approval of C.2 (new function + CLI flag + tests).
2. The **name** to record as `authorized_by` (the person who approved the 2026-10-16 run), and whether the entry should also state that
   the authorization was given in the session instructions rather than through `authorize()`.

## D. Implementation status after the decisions (2026-10-16)

| ID | Done | Not done (and why) |
|---|---|---|
| P1 | Opt-in step written: `scripts/dataset/verified_to_manifest.py` + `build_combined_manifest.py --include-verified`. It re-checks every verified label (target class, eligibility from the pool and frozen manifests, image SHA-256 on disk, crop rule) and adds rows to **training only**; tests in `tests/test_clinical_review.py`. | Not run: there are 0 verified labels, and running the builder rewrites the audit timestamps. Run it only after reviews are imported. |
| P2 | Targets recorded as provisional in `scripts/dataset/expansion_report.py` / `reports/expanded_class_distribution.csv`. | To be revisited after batch 1 (audit-slice yield). |
| P3 | Already enforced at export and again in `verified_to_manifest.py`. | Per-source reporting is a requirement for future experiment reports (no experiment is planned yet). |
| P4 | **Draft** fold assignment for review: `data/splits/cv5_folds_DRAFT.csv` (SHA-256 `b001df15…`), summary `reports/cv5_fold_draft_summary.md`, generator `scripts/dataset/make_cv_folds.py` (+ test). | **Review gate:** the draft is neither approved nor used. It must be regenerated and re-reviewed after verified labels are added. |
| P5 | Code ready and tested on temporary ledgers: `test_ledger.record_retrospective_disclosure()` + `scripts/test_set_ledger.py --record-disclosure` (`tests/test_ledger_disclosure.py`). Entry prepared from archive files: `reports/p5_disclosure_entry.json`. | **The ledger is NOT edited** (5 entries, SHA-256 prefix `f117c1a3…`, chain intact). It is blocked until you confirm the `authorized_by` name. |

## E. Verification pass (2026-10-16, after the decisions)

**P4 draft review (draft NOT approved, nothing run).** `data/splits/cv5_folds_DRAFT.csv` (SHA-256 `b001df15…`, matches the summary):
* Integrity checks pass: 581 radiograph groups (= every group of combined_train + combined_validation), each in exactly one fold; all
  crops of a radiograph share its fold; 0 calibration / test groups or image hashes in any fold; no image hash in two groups or two
  folds; per-fold class counts equal a recount from the manifest labels; re-running the assignment (also with shuffled input)
  reproduces it exactly (seed 42).
* Balance: Periapical Lesion radiographs 19-21 per fold (findings 22-31); Deep Caries radiographs 55-57 (findings 88-117);
  **Impacted is not a stratification variable: 82-125 findings (36-51 radiographs) per fold, 1.5x spread.** Fold sizes 114-118 radiographs.
* Assumptions to accept or change before approval:
  1. Groups are **radiographs, not patients** (no patient ids); two different radiographs of one patient can fall in different folds.
  2. Duplicate merging relies on exact SHA-256 plus the dHash + correlation rule (1,456 candidates, 0 confirmed); re-processed or
     cropped copies below that rule's sensitivity would not be merged.
  3. The old validation radiographs are trained on in 4 of 5 folds, so CV numbers are not comparable to earlier single-split numbers.
  4. The draft covers today's data only; it must be regenerated and re-reviewed after verified labels are added.
* Options: approve as is; or ask me to add Impacted to the stratification (likely narrows the 82-125 spread); or change K / seed.

**P1 hardening (defect fixed).** `verified_to_manifest.py` trusted the rows of `verified_findings.csv`. It now refuses any row whose
`record_hash` is not the latest decision for that region in the hash-chained review log (forged / superseded / edited rows), whose label /
box / image differ from the logged record, or whose reviewer is not in the current registry; a log that fails its chain check stops the
build. The default build without `--include-verified` was run in an isolated sandbox: all five combined manifests were **byte-identical**
to the frozen ones; the only difference is one new audit key `clinician_verified: {"included": false}`.

**P5 readiness.** All facts in `reports/p5_disclosure_entry.json` were re-checked against their source files (seeds, five checkpoint
hashes, BASE configuration, per-seed metrics and mean / SD, 354 findings / 73 radiographs from the frozen test manifest, test-manifest
and split hashes, the log line at 11:53:27; the container clock is UTC, since the log's first line equals the recorded UTC start
09:45:49Z). Dry run on a temporary **copy**: the entry appends as #6 with an intact chain, a duplicate is refused (`already_recorded`), and no
`final_metrics` slot is used. The live ledger is unchanged. **Missing: the `authorized_by` name.**

## F. Owner decisions, second round (2026-10-16)

* **P1: approved**, including the hardening (review-log verification, current-registry check, evaluation exclusions, unchanged default build).
* **P4:** assumptions 1-4 **accepted**; K = 5 and seed = 42 kept; current draft kept for review. Impacted-stratified alternative presented
  for approval in `reports/cv5_fold_alternative_comparison.md` (not applied). **No cross-validation run before final approval;**
  regenerate and re-review after verified labels are added.
* **P5:** live-ledger write **not authorized** until the actual authorizer and the circumstances of the authorization are established.
  The dry run is not authorization.
