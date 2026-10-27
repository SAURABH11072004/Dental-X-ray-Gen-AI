# CV5 Amendment 01: first-round candidate registration (DRAFT, NOT IN EFFECT)

**Status: DRAFT prepared 2026-10-25. NOT REGISTERED. No budget slot is reserved.**

The amendment takes effect only when the project owner completes the signature block in §8 with their own name and the date. That
date and time is the registration timestamp used by the winner rule (protocol §10.2).

**Why the owner signs (protocol §4.5, §9, §10.1):**
* Registration reserves lifetime budget slots.
* A registered candidate cannot be withdrawn without using its slot.
* The choice of interventions is the owner's.

The candidates in §4 are therefore *proposed* and may be changed or replaced before signature. Nothing after signature may change them.

Governing protocol: `reports/cv5_acceptance_protocol.md` (revision 3, approved 2026-10-25, sha256 `0771b5f8…`). This amendment adds
no rule and changes no threshold.

---

## 1. Preconditions at signature (protocol §3, §3.2, §4.5)

| Precondition | State on 2026-10-25 | Effect |
|---|---|---|
| No candidate result exists (any family) | true: no candidate has been trained | registration allowed |
| BASE-P2 not yet run | true: BASE-P2 is not registered or run | registration allowed; it must precede BASE-P2 (§3.2) |
| No test data used for the choice | true (§5) | required |
| No held-out out-of-fold prediction of any candidate used | true: none exists | required |
| P2 met | **false**: PL 129 / 94 vs ≥ 300 / 200; DC 467 / 250 vs ≥ 750 / 400; 0 clinician-verified imports | registration may precede P2, but no confirmatory run may start until P2 is met |
| Candidate-path code frozen | true: `reports/cv5_candidate_path_freeze.md` | runs use the frozen path |
| Intervention code for F1 / F2 implemented and frozen | **false** (§6) | no candidate notebook may be generated until Amendment 01b freezes it |

The P2 version that applies is the one in force at signature (protocol §3): today, the provisional P2 of 2026-10-16.

## 2. Comparator and frozen comparison procedure

**Comparator: BASE-P2** (protocol §3.2).
* It uses the unchanged BASE recipe, with the P1 imports in every fold's fitting part, on `cv5_folds_v1.csv` (sha256 `9b767a48…`), seeds
  42–46.
* It is registered in its own amendment (Amendment 02) after this one and is run only after this one is signed.
* Every candidate below is trained on exactly the BASE-P2 training data: the same imports manifest, fixed in Amendment 02. It differs
  only in its own declared intervention.

**Comparison procedure (fixed, quoted from the protocol, not restated with new values):**
* **Frame:** v1 folds and their fitting / inner-validation split; seeds 42–46; the reference run's detector boxes; IoU ≥ 0.5
  one-to-one matching; epoch selection by best inner-validation macro-F1 (§4).
* **Reference reuse:** only after the fold-file check and gate R:
  - R1: exact argmax;
  - R2: maximum probability difference ≤ 1 × 10⁻⁴;
  - R3: identical argmax metrics.
* **Primary checks:**
  - P-A: Δ macro-F1 (detector boxes, seed mean) ≥ 0.027;
  - P-B: paired radiograph bootstrap, `default_rng(0)`, B = 20,000, two-sided level 1 − 0.05/15, lower bound > 0;
  - P-C: ≥ 4 of 5 seeds;
  - P-D: ≥ 4 of 5 folds.
* **Safeguards S1–S7:** margins 0.03 / 0.05 / 0.04 / 0.04 / 0.02, 0.03, 0.02, 0.03 / 0.02 / 0.03, 0.05.
* **Hard-harm rule H:** DC and PL recall and precision; unadjusted 95 %; fails if the upper bound is < 0.
* **Validity gates V1–V6.** The verdict precedence is unchanged:
  - an integrity-gate failure gives NO VERDICT;
  - otherwise any divergence gives FAIL;
  - infrastructure exhaustion, incomplete runs or missing runs give NO VERDICT;
  - only then are the criteria applied.
* **Run handling:** section-9 run classification and retry rules, as implemented in the frozen candidate path.
* **Winner and final artifact:** winner rule §10.2; final artifact §10.3 (V-a: the winner's fold 0 / seed 42 checkpoint); at most
  one ledger-recorded test evaluation §10.4.
* **Implementation:** `kaggle/cv5_accept.py`, sha256 `9e4dc067…`, as frozen.

## 3. Budget (protocol §10.1)

| Family | Lifetime cap | Registered before this amendment | Reserved by this amendment (if signed as proposed) |
|---|---:|---:|---:|
| F1 crop / input | 3 | 0 | 2 |
| F2 architecture | 3 | 0 | 1 |
| F3 training data | 3 | 0 | 0 |
| F4 loss / sampling / augmentation | 3 | 0 | 0 |
| F5 ensembling | 1 | 0 | 0 |
| Combinations | 2 | 0 | 0 |
| **Total** | **15** | **0** | **3** (12 remain) |

* Multiplicity: k = 15 for every candidate (fixed lifetime Bonferroni). It is unaffected by how many are registered.

## 4. Proposed candidates (owner may change before signature)

All three differ from `EXPERIMENTS["BASE"]` only in `extra`, which DK.train_run and the crop builders do not read today (§6). Each
candidate's config is otherwise the full BASE ExpConfig:
* loss `ce`; weights `inverse_cap5`; sampler `none`; data as BASE-P2;
* epochs 15, batch 32, lr 3e-4, wd 1e-4, hflip 0.5, contrast 0.1.

| ID | Family | Single intervention (config diff vs BASE) | Everything else |
|---|---|---|---|
| **C1 `CROP384`** | F1 | `extra = {"crop_size": 384}`: GT and detector crops resized to 384 px instead of 224 px; crop padding unchanged (0.10) | BASE |
| **C2 `PAD25`** | F1 | `extra = {"crop_pad": 0.25}`: context padding 0.25 instead of 0.10; size unchanged (224 px) | BASE |
| **C3 `CNXTT`** | F2 | `extra = {"backbone": "convnext_tiny"}`: torchvision ConvNeXt-Tiny, ImageNet-1k weights (`ConvNeXt_Tiny_Weights.IMAGENET1K_V1`), classifier replaced by a 4-class linear layer; native input 224 px (= BASE) | crop, data, loss, optimiser and lr as BASE |

**C3 notes:** the optimiser settings are deliberately left at BASE values so that the backbone is the only change. This may not be
the best setting for ConvNeXt; that is accepted as part of the registered intervention.

**C1 compute:** about 2.9× the pixels per crop. Batch 32 is kept. If it does not fit a T4 the run fails as out-of-memory
(infrastructure), and the candidate gets NO VERDICT. It is not silently changed.

## 5. How the candidates were chosen (protocol §3, §4.5)

**Sources used: only CV5-BASE run 1 (evidence category A1) and general literature knowledge.** From `reports/cv5_results.md`:
* **C1:** the Deep Caries → Caries confusion rises with box size (box-area quartiles 1–4: 0.33, 0.44, 0.51, 0.59). Large boxes are
  downsampled most at 224 px, so depth cues near the pulp may be lost. C1 tests whether higher input resolution helps.
* **C2:** Periapical Lesion is predicted as Caries in 229 of 645 GT-box predictions (36 %). A periapical lesion is judged from the
  apex region and its surroundings, so C2 tests whether more context helps.
* **C3:** a modern ImageNet-pretrained backbone of similar size (ConvNeXt-Tiny, about 28 M parameters vs ResNet-50 about 25 M) is a
  standard first architecture comparison.

**Disclosed prior knowledge (not used as evidence, but known when choosing):**
* The single-split imbalance strategies A1 sqrt weights, A2 effective-number weights, B sampler, C focal loss and D + official
  validation all FAILED the old acceptance rule on the project validation split (`reports/training_summary.md`). This is one reason
  no F4 candidate is proposed in this round. The choice is therefore informed by earlier failures.
* X2_hanoi: FAIL. The 5-seed BASE ensemble: FAIL.
* No candidate was chosen using test-split results. The BASE test evaluations exist but were not consulted for this choice.
* No candidate result, held-out out-of-fold candidate prediction or BASE-P2 result exists.

## 6. Implementation required before any candidate notebook is generated (Amendment 01b)

> **Update 2026-10-25:** implemented without registering anything. Candidate IDs are letters and digits only (`CROP384`, `PAD25`,
> `CNXTT`). Details are in the draft `reports/cv5_amendment_01b_implementation.md`.
> * `kaggle/cv5_interventions.py` implements the three keys (`crop_size`, `crop_pad`, `backbone`) and the V3 single-intervention check.
> * `dentamind_kaggle.py` and `dsutil.py` are **unchanged**, so no new data / code bundle was needed.
> * A separate versioned candidate-code bundle v1 was built.
> * The Kaggle no-training pre-flight was repeated (v2: PASS, 150 / 150).
> * Points 1–4 below are satisfied by that draft. It takes effect together with this amendment.

The interventions are not implemented. Before any candidate notebook is generated, a separate dated Amendment 01b must:
1. **Implement `extra["crop_size"]` and `extra["crop_pad"]`** in the crop builders used by the candidate path, for GT and detector
   crops. The defaults must reproduce today's crops byte for byte (test), so BASE / BASE-P2 and gate R are unaffected.
2. **Implement `extra["backbone"]`** in model construction, for training and for held-out prediction. The default must stay
   `resnet50`, unchanged (test).
3. **Update the V3 config-diff gate check** so it confirms that each candidate differs from BASE only in its declared key.
4. **Record new hashes for every changed file**, and repeat the no-training pre-flight on Kaggle.
   - `dentamind_kaggle.py` and `dsutil.py` are in the hashed Kaggle bundle. Changing them needs a new bundle version.
   - The change must be shown not to alter the BASE path.

## 7. What stays blocked after signature
* No candidate or BASE-P2 training until all of these hold:
  - P2 is met;
  - Amendment 01b (implementation freeze) exists;
  - Amendment 02 (BASE-P2 registration, with the frozen imports manifest and gate V6) exists.
* No test-set use of any kind (protocol §10.4).

## 8. Owner signature (registration takes effect only when completed)

| Field | Entry |
|---|---|
| Candidates registered (IDs as finally chosen) | |
| Registered by (owner's own full name) | |
| Date and time (UTC) | |
| Statement | "I register the candidates above under `reports/cv5_acceptance_protocol.md` revision 3, I understand that each reserves a lifetime budget slot that is used if it is withdrawn or once its training starts, and I confirm the selection statement in §5." |
