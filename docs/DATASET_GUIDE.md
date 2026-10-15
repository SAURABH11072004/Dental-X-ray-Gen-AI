# Dataset guide

Everything here was measured from the files in `Data/` on 2026-10-14 (`python scripts/audit_dataset.py`; full output in
`Data/reports/dataset_audit.md` / `.json`). Re-run the audit after any change to the data.

## Layout expected (and found)

```
Data/
  training_data/
    quadrant/                      xrays/*.png  + train_quadrant.json
    quadrant_enumeration/          xrays/*.png  + train_quadrant_enumeration.json
    quadrant-enumeration-disease/  xrays/*.png  + train_quadrant_enumeration_disease.json
    unlabelled/                    xrays/*.png  (no annotations)
  validation_data/quadrant_enumeration_disease/xrays/val_0..49.png   (50 unlabeled images = TEST DATA)
```

Folder names are discovered, not hard-coded (`quadrant-enumeration-disease` with hyphens works), and the root can be
moved with `DATA_ROOT` in `.env`. Source images and annotation files are never modified, renamed or deleted.

## What the data contains

| Sub-set | Image files | Annotations | Labels |
|---|---:|---:|---|
| `quadrant` | 693 | 2,772 (4 per image) | quadrant polygon + box, `category_id` 1-4 |
| `quadrant_enumeration` | 634 | 18,095 (28.5 per image) | tooth polygon + box, quadrant (`category_id_1`) + tooth number 1-8 (`category_id_2`) -> 32 FDI teeth |
| `quadrant-enumeration-disease` | 705 (27 have no annotation) | 3,529 | as above + `category_id_3`: Caries 2,189, Deep Caries 578, Impacted 604, Periapical Lesion 158 |
| `unlabelled` | 1,571 | none | - |
| `validation_data` | 50 | none | unlabeled test data |

All 3,653 files are readable PNGs (0 corrupt). Every image listed in an annotation file exists, and every recorded image
size matches the file. All boxes are valid, and every quadrant/tooth-number combination is a valid FDI tooth.
Every annotation has both a bounding box and a polygon mask.

## Things you must know before using it

1. **The sub-sets overlap.** The 3,653 files contain only **2,716 distinct radiographs** (by SHA-256 of the pixels).
   The same radiograph is often present in `quadrant`, `quadrant_enumeration` and `quadrant-enumeration-disease`
   under different names, and 40 "unlabelled" images and 20 of the 50 `validation_data` images are copies of labeled ones.
   Only **1,133** distinct radiographs carry annotations.
2. **File names are not identifiers.** `train_673.png` exists in several sub-sets and refers to *different* radiographs
   (705 names are reused with different pixels). The pipeline therefore gives every image an id that is unique across
   sub-sets: the bare file stem when unique, otherwise `<source tag>_<stem>` (`q_`, `qe_`, `qed_`).
3. **Splits are grouped by pixel content.** `patient_id` is not available in DENTEX, so the content hash is the group:
   identical radiographs always land in the same split. Measured: 0 distinct radiographs appear in more than one split
   and 0 test radiographs are also in train.
4. **Only annotated images are split.** Split sizes (distinct radiographs): train 794, val 113, calibration 113, test 113.
   Unlabeled images stay `unassigned` (active-learning pool); those identical to a labeled image are flagged
   `duplicate_of` and excluded from the pool. `validation_data` is held out as unlabeled test data and is never trained on.
5. **Each task uses the sub-set whose labels are complete for it:**
   - tooth detection / segmentation: `quadrant_enumeration` (every tooth is annotated);
   - finding classification: `quadrant-enumeration-disease` (only *diseased* teeth are annotated there, so it cannot be used
     as tooth ground truth, and it has no "healthy" class);
   - `quadrant` boxes are quadrants, not teeth, and are never used as tooth labels.

## Commands

```powershell
.\.venv\Scripts\python.exe scripts\run_pipeline.py --force     # discover -> validate -> manifest -> splits -> quality stats
.\.venv\Scripts\python.exe scripts\audit_dataset.py            # writes Data\reports\dataset_audit.json / .md (decodes every image)
.\.venv\Scripts\python.exe scripts\validate_dataset.py         # validation report only
```

Outputs: `Data/processed/manifest.json|csv` (one row per file, with `content_hash`, `duplicate_of`, `split`),
`Data/splits/dentex_splits.json` (append-only; the previous file, which used colliding ids, is kept as
`dentex_splits.legacy_colliding_ids.json`), `Data/results/validation_main.json`, `Data/processed/content_hash_cache.json`.
