# DentaMind AI: research improvement, round 2 (2026-10-25)

**Scope.** Inspection, a defect fix in production inference, consistency tests, leakage verification, a security audit, and the
research-direction ranking.
* No candidate was trained.
* No locked CV5 evaluation was run, and the matching rule was not applied to real data.
* No test data was used, and no evaluation rule was changed.
* No approval was created.
* No ACL, file location, Git history, remote or repository setting was changed.

## 1. Verified starting state

| Item | Verified value |
|---|---|
| Pre-audit set; Amendment 01b change set; CV5 archive | 8 / 8; 12 / 12; 88 / 88 entries |
| Protocol / ledger / approvals module / Kaggle training lib / CV5 lib / frozen generator | `0771b5f8` / `f117c1a3` (5 entries) / `19d83c42` / `879faa93` / `72084f9b` / `4a5efda8`, all unchanged |
| Manuscript v3.1 md / docx | `99c5d218` / `ed1e518b`, unchanged; number, claims and citation audits re-run: PASS (222 traced, 0 untraced); 16 / 16 keys; 9 author placeholders open |
| Approvals | no `reports/approvals/`; amendments DRAFT; P2 not met; M1 has no real-data result |
| Repository | 1 commit (`6340f09` = `origin/main`) |
| Baseline | 0.677 ± 0.008, DC recall 0.440, PL recall 0.432, ECE ≈ 0.11: **previously reported** values from the checksum-verified archive. They were not re-measured, and no new metric was computed in this round |

## 2. Ranked technical opportunities (observed evidence vs hypothesis)

| Rank | Direction | Observed failure mode (source) | Proposed intervention | Benefits / harms | Data / compute | Metrics and safeguards | Authorization needed |
|---|---|---|---|---|---|---|---|
| **1** | **Caries ↔ Deep Caries boundary** | Largest error mass. GT boxes: 1,083 / 2,415 Deep Caries predictions are Caries (45 %). Detector boxes: DC F1 0.487. 93 DC findings are confused by all 5 seeds. Confusion varies with box size (`cv5_results.json`; `cv5_error_attribution.md`) | **(a) blinded clinician re-reading first** (prepared, 220 items). **(b)** registered candidates C1 (384 px crops) and C2 (0.25 padding), which give more detail and pulp context | (a) separates label ambiguity from model error and bounds what any model can gain. (b) may raise DC recall; possible harm: Caries precision, compute ×3 for 384 px | (a) a qualified CL, 2 readers, no compute; (b) Kaggle GPU, 25 runs each | protocol P-A to P-D, S1–S7, H | (a) CL plus governance (C1–C11); (b) Amendment 01 and **P2 met** (confirmatory only) |
| 2 | Periapical Lesion | 29 / 129 PL unmatched, 22 of them through matching conflicts. PL → Caries in 36 % of GT-box predictions. Only 129 PL findings | M1 matching (no retraining); C2 apical context; more PL data via P1 imports | M1: end-to-end recall cannot fall, but precision can; data: needs verified labels | M1: CPU only; data: clinician time | M1 registration (decision memo); protocol S2 / S4 / S7 | M1: route decision (A1 / A2 / B, memo); data: P2 route |
| 3 | Calibration | ECE 0.107 / 0.109 (10-bin, CV5) | temperature scaling fitted on inner-validation predictions only | better probability scores for abstention; **cannot change macro-F1** | inference-only re-prediction with archived checkpoints (Kaggle) | NLL primary, ECE and Brier (registration draft) | separate calibration amendment (protocol §2 lists post-hoc calibration studies as out of scope) |
| 4 | Detector localisation for Deep Caries | 34 / 483 DC overlap a tooth box only with IoU < 0.5 | finding-level box rule or detector retraining | uncertain | detector training | own protocol | protocol §2: "tooth-detector changes" are out of scope; own protocol needed |

**What is hypothesis, not evidence:**
* that larger crops or more padding help;
* that M1 improves end-to-end macro-F1;
* that the 93 consistent DC confusions are label ambiguity rather than model error;
* that calibration would improve abstention.

None of these has been measured.

## 3. Recommended research direction
**Caries / Deep Caries boundary, label quality first.**
* It is the largest observed error mass (rank 1).
* The 93 consistent confusions are exactly where label ambiguity is plausible. If many are ambiguous to clinicians, no model change can
  be judged without that knowledge.
* The re-reading needs **no compute and no protocol budget**: only a clinical lead and governance, with materials already prepared
  and blinded.
* Its outcome directly informs the registered C1 / C2 candidates and the P2 labelling standard, which is the bottleneck for all
  confirmatory work.

## 4. Safe implementation changes made

**Defect fixed in production inference (latent; current behaviour unchanged).**
* **What was wrong:** `torch_models._prep_crops` / `_normalize` silently used `crop_pad = 0.0` and identity normalisation when a
  classifier sidecar omitted them.
* **Why it matters:** a hand-written sidecar for a new checkpoint (e.g. a Kaggle BASE model) would load without error and feed the
  network uncropped, unnormalised inputs it was never trained on.
* **Fix:** inference now refuses with `ModelUnavailableError(code="sidecar_preprocessing_missing")`. A new helper,
  `registry.classifier_preprocessing_problems`, states the requirement.
* **Scope:**
  - first tried also at checkpoint scanning; that changed listing and promotion of 13 fixture-based tests, so it was narrowed to the
    point of use;
  - checkpoint listing, provenance and promotion are unchanged;
  - all three sidecar writers (production trainer, Kaggle trainer, deployed sidecar) already state these keys.

**Verified consistency, now pinned by tests** (`tests/test_inference_consistency.py`, 22 tests, synthetic images only):
* **Inputs:** inference crops are byte-identical to training crops for DENTEX-style images.
  - All 755 local DENTEX images were checked: every one is RGB with three equal channels, so the grayscale inference loader and the
    RGB training loader give identical input.
  - The float round-trip is exact for all 256 values.
* **Crop rules and normalisation:** the production and training crop rules are identical, and production normalisation equals the
  training normalisation.
* **Deployed sidecar:** it states exactly the CV5 training constants (pad 0.10, 224 px, ImageNet mean / std, class order).
* **ECE:** the CV5 ECE equals the app's ECE function, including confidences on bin edges.
* **Matching and cropping edge cases:** empty inputs, IoU exactly 0.5, zero-area boxes, one-to-one assignment, tiny or out-of-image
  boxes.
* **Documented limitation:** colour uploads are reduced to grayscale at inference, and training never saw colour images.

**Leakage verified on artifacts (read-only):**
* **Archived fold plan:** 0 violations; 541 / 541 groups held out exactly once.
* **Split audit** (identical to the bundle copy): 0 group and 0 image-hash overlaps between train, validation, calibration and test;
  0 confirmed near-duplicates among 2,305 images.
* **DENTEX official test release:** 95 of its images overlap other DENTEX training subsets. This confirms it is not an independent
  external set.
* **Training determinism:** seeds, deterministic cuDNN and saved RNG state for resume were inspected. GPU non-determinism remains, as
  already disclosed.

## 5. Files changed

| File | Change |
|---|---|
| `src/dentexmodel/inference/registry.py` | + `classifier_preprocessing_problems()`; `validate_sidecar` unchanged. Pre-change copy: `scratchpad/bak_round2/registry.py` (`f099bcea…`) |
| `src/dentexmodel/inference/torch_models.py` | `_prep_crops` refuses missing preprocessing; `_normalize` has no silent defaults. Pre-change copy: `scratchpad/bak_round2/torch_models.py` (`91471a5f…`) |
| `tests/test_inference_consistency.py` | new, 22 tests |
| `reports/research_improvement_round2.md` | this report |
| `reports/action_register_v1.md` | dated addendum only |

**Rollback:** restore the two pre-change copies. No other file is affected.

## 6. Tests executed

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_inference_consistency.py -q -p no:cacheprovider -o addopts=""` | 21 passed, 1 failed → the failure was a wrong expected IoU in my test (100/199 is > 0.5), corrected → **22 passed** |
| full suite with stricter scan-time validation (rejected design) | 13 failed, 555 passed → design narrowed |
| `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (final) | **590 passed, 0 failed** |
| manuscript v3.1 number / claims / citation audits (to scratch files) | PASS / PASS / 16 of 16 keys found (6 known flags) |

## 7. Performance results
**None.** No model was trained or evaluated, and no new metric was computed in this round. The latency benchmark from round 1 is
unchanged (RTX 3050 laptop; descriptive).

## 8. Remain hypotheses
Every intervention in §2. The consistency tests establish correct inputs, not better accuracy.

## 9. Security findings and human decisions

| Item | Finding (read-only) | Proposed remediation (needs approval) |
|---|---|---|
| `.gitignore` | restricted files F1–F6 not ignored | add the 5 lines in `reports/security/clinical_files_access_control_plan_PROPOSED.md` §4 Step 1 **before any commit** |
| Tracked / staged / history | none of F1–F6 tracked, staged or in any commit; remote `main` = local `6340f09` | none needed; re-audit before every push |
| GitHub | repository **public**; restricted folder absent remotely | owner decides visibility (repository setting) |
| Kaggle | the project's 4 notebooks (including `dentamind-5-fold-cv-base`, whose output contains F5 / F6) and the dataset return HTTP 404 anonymously, while known public Kaggle pages return 200 → **not publicly visible** (indicative; sharing with specific users cannot be seen) | owner confirms in Kaggle settings that they are private and unshared |
| External copies | file-name search of the user profile and D: found restricted copies **only in this assistant's session scratchpad** (ACL: owner, SYSTEM, Administrators, 3 app-specific identities; no general Users access): byte-identical copies of F4 (`011dfb19`), F5 (`9998c945`) and F6 (`4ac56843`) in `scratchpad/dry_tree/`; F5-format files from a smoke run in `scratchpad/cv5_smoke/` (different hash, same size; treat as restricted) | **owner approves deleting** `scratchpad/dry_tree/` and `scratchpad/cv5_smoke/`. Not deleted. Other machines, backups and cloud sync were not searched |
| Least privilege / verification | all local accounts can read F1–F6; access test FAIL (baseline) | plan Steps 2–5; access is not fixed until a non-administrator test passes |

## 10. Exact next steps to authorize a valid experiment
1. **Clinical re-reading (recommended first; no compute):**
   - the PO appoints a CL;
   - the CL completes C1–C11;
   - the institution confirms the reader-study requirements;
   - the coordinator executes the access plan, and the non-administrator test passes;
   - reading with worksheet v2.

   The approval tooling (R1 → R2 → R4) is needed to record the CL decision formally.
2. **M1 matching:** the PO settles the protocol §3 interpretation, then chooses A1, A2 or B (decision memo), in writing, before any
   outcome. It needs R4 for the record. B also needs P2.
3. **C1 / C2 candidates:** R1 → R2 → R3 → R4 → Amendment 03 → patch set → 01c → Amendment 01 → BASE-P2 registration and run → gate R.
   **P2 must be met first**, which needs clinician-verified imports.
4. **Calibration:** a separate amendment (protocol §2: post-hoc calibration studies are out of scope), plus Kaggle re-prediction.

## Matching-rule decision brief (summary of `reports/cv5_matching_rule_decision_memo_DRAFT.md`)
* **A1, separate protocol:** needs a written owner determination that M1 is not a "candidate configuration" under protocol §3. It
  yields a pipeline verdict, never "ACCEPT".
* **A2, exploratory amendment:** adds M1 to §7.1. Hypotheses only; it cannot be used for candidate selection.
* **B, candidate family F6:** amendments to §4.1, §6 and §10.1 (budget 16, k = 16). **Blocked until P2 is met.**

That M1 needs no new inference does **not** settle whether it is a candidate; the owner must decide.
