# Pre-registered protocol: adding external panoramic datasets to the finding classifier

Status: **written 2026-10-24, before any crop was extracted or any model was trained on external data.** Nothing below may be
changed after results are seen; any change is recorded as a dated amendment with its reason.

## 1. Owner decision on labels (2026-10-24)

The project owner chose **definition mapping**. This replaces, for training purposes only, the earlier rule that a dentist must confirm
each external label first (reports/additional_dataset_candidates.md). The mapping is an assumption and must be disclosed in any
publication.

| Source | Source label | Target |
|---|---|---|
| Hanoi (Mendeley kx52tk2ddj v3, CC BY 4.0) | PAI 3, 4, 5 (apical periodontitis) | Periapical Lesion |
| Cluj (Zenodo 10.5281/zenodo.15487430, CC BY 4.0) | API (apical periodontitis) | Periapical Lesion |
| Cluj | IMT (impacted tooth) | Impacted |
| Cluj | CAR (carious lesion, depth not recorded) | **partial label** {Caries, Deep Caries} |
| Cluj | all other 11 classes (implants, restorations, bone loss, ...) | not used |

**Partial label.** For a sample whose label is {Caries, Deep Caries}, the loss is −w·log(p_Caries + p_DeepCaries), so the model
is told "some caries" and decides the depth itself. The weight w is the Caries class weight. Class weights are computed from
fully labelled samples only, so BASE weights are unchanged.

## 2. From lesion boxes to tooth crops

The classifier works on tooth crops (pad 10 %, 224 px; production `crop_region`). Hanoi API/PAI and Cluj CAR boxes outline the
**lesion**, not the tooth. For each such box L:

1. Run the production tooth detector `dentex_teeth_detection_v1` (score ≥ 0.3) on the radiograph.
2. Coverage(L, T) = area(L ∩ T⁺) / area(L), where T⁺ is the tooth box T padded by 10 % on each side. The padding matches the crop
   padding and reaches the root apex for periapical lesions.
3. Assign L to the tooth with the highest coverage, and only if that coverage is ≥ 0.5. Ties are broken by IoU(L, T). If no tooth
   qualifies, the lesion is dropped and counted.
4. The crop is taken from the detector tooth box T, exactly as in the application. Several lesions of the same class on the same
   tooth give one sample.

Cluj IMT boxes outline the impacted tooth itself, like DENTEX finding boxes, so they are cropped directly from the label box.

Before training, a visual check grid of 48 random crops per source and class is produced. If more than 10 % of those crops do not
show the labelled finding on the cropped tooth, the source is withdrawn.

## 3. Data roles (fixed)

- **DENTEX** train / validation / calibration / test: unchanged (`data/splits/combined_*.csv`). Validation is used for epoch
  selection and the acceptance rule. The test split is used only for BASE and for candidates that pass (ledger rule).
- **Hanoi:** training only. It contains positives only (every radiograph has a lesion), so it carries a source-shortcut risk.
  At most **1,500** Hanoi Periapical Lesion crops are used. They are chosen by a seeded draw (seed 42) over radiograph groups,
  taking whole radiographs until the cap is reached, so that Periapical Lesion does not grow from 120 to about 6,000 crops.
- **Cluj:** the published `train` and `valid` folders are used for training. The published `test` folder and the 180-image
  multi-center external set are **external evaluation only** and are never trained on.
- **Leakage checks:** exact (SHA-256) and near duplicates (dHash + pixel correlation ≥ 0.97) between every external image and all
  DENTEX images, and between Cluj train and Cluj test/external. Any match is removed from training.

## 4. Experiments (5 seeds each, 42–46; recipe = BASE / C0r; exactly one data factor changes)

| Name | Training data |
|---|---|
| BASE | DENTEX train (identical to the earlier Kaggle BASE) |
| X1_cluj | + Cluj train/valid crops (Impacted, Periapical Lesion, partial caries) |
| X2_hanoi | + Hanoi Periapical Lesion crops (cap 1,500) |
| X3_both | + Cluj + Hanoi (cap 1,500) |

## 5. Acceptance (unchanged, pre-registered; candidate vs BASE on DENTEX validation, detector boxes)

These are the project's existing criteria 1–5 (`kaggle/dentamind_kaggle.py`, `ACCEPT`):

1. Macro-F1 gain > 0.027, better in ≥ 4/5 seed pairs and ≥ 20/25 cross pairs.
2. Deep Caries and Periapical Lesion recall not lower.
3. No class F1 drop > 0.05.
4. Ground-truth-box macro-F1 drop ≤ 0.02.
5. Minority precision drop ≤ 0.10.

**Secondary (reported, not used for acceptance):**

- Cluj external set and Cluj test folder:
  - Impacted recall;
  - Periapical Lesion recall;
  - caries-any recall (prediction ∈ {Caries, Deep Caries} for CAR teeth).
- The same metrics per source, to make shortcuts visible.

## 6. Reporting

All runs, including failures and negative results, are reported. The DENTEX test split is touched once per passing candidate and
once for BASE, and each use is appended to `Data/reports/test_set_ledger.json`. No production checkpoint is changed by this protocol.

## Amendments

- **2026-10-24, before any Cluj data was seen.** The local Zenodo download ran at about 2–7 MB/min, so Cluj is downloaded and
  cropped on Kaggle with the same script (`scripts/dataset/external_crops.py`) and the same detector checkpoint. The folder rule was
  made stricter: only folders named `train`, `valid` or `val` are trained on. Every other folder (`test`, an external set, or any
  unrecognised name) is evaluation-only, so an unexpected archive layout cannot leak evaluation images into training. The notebook
  logs the actual layout.
- **2026-10-24, local audit of the full archive (before any training on Cluj; no rule changed).** The archive (1,397,393,531 bytes,
  MD5 verified) holds 1,808 images in `train` (1,375), `valid` (153), `test` (100) and `test_alte_cabinete/Ext-validation` (180),
  each with a matching YOLO label file; none is undecodable. By the folder rule, `train` and `valid` are trained on; `test` and
  `test_alte_cabinete/Ext-validation` are evaluation only. Exact duplicates: 197, all inside one role (150 train–train,
  43 train–valid, 1 valid–valid, 2 test–test, 1 external–external); 0 against DENTEX or Hanoi. Near duplicates: 20, all inside
  one role (19 train–train, 1 external–external); 0 against DENTEX or Hanoi. So no training image duplicates an evaluation image.
  Duplicates inside the training role are kept, as section 3 requires removal only across roles; this is disclosed here.
  Full counts: `reports/cluj_dataset_audit.json`.
- **2026-10-24, Cluj withdrawn from training (before any training; owner decision).** Section 2's visual check was run on the real
  Cluj crops (48 random crops per class, `scripts/dataset/external_crops.py`). Periapical Lesion and caries crops showed the
  lesion box on the cropped tooth. About 15 of the 48 Impacted crops (~30 %, limit 10 %) showed no impacted tooth. Cause, found by
  drawing the raw YOLO labels on full radiographs: a block of Cluj images (mostly train ids 101-199, plus a few in valid, test and
  the external set; 42 images flagged by a size/count heuristic) uses a different class numbering from `legend.txt`, e.g. image
  `train/107.jpg` has class 6 ("impacted tooth") boxes at the alveolar crest of every remaining tooth. The crop code reproduces the
  labels exactly; the fault is in the published labels. As section 2 requires, **Cluj is withdrawn from training**: X1_cluj and
  X3_both are not run and are reported as withdrawn. BASE and X2_hanoi run unchanged. The Cluj `test` and external folders remain
  a secondary evaluation only, with the caveat that some of their labels may share the numbering fault (2 images flagged).
