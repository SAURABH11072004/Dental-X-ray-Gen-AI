# Demonstration script (about 12 minutes)

**Before you start** (once): open two PowerShell windows in `D:\Dentex-Gen Ai`.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000     # window 1 (API; first analysis loads the models)
cd frontend; npm.cmd run dev                                                           # window 2 -> http://localhost:5173
```

Do not run a training or the AL experiment at the same time: the 4 GB GPU holds the four models (about 3 GB) or one training, not both.

## Storyline (say this first)
"DentaMind is a research prototype for uncertainty-guided active learning on dental panoramic X-rays. It is **not** a diagnostic system: it
shows what the models output, how unsure they are, and routes the uncertain cases to a human reviewer."

## Steps

1. **Home** (`/`) - point at *Dataset*: 3,653 files = 2,716 distinct films; open "How these numbers are defined" (duplicates, grouped splits, leakage check: all pass, 0 confirmed near-duplicates).
   Mention models and GPU, review tasks, recent experiments (all real records).
2. **X-ray Analysis** - choose *Test data (unlabeled)* -> any image -> **Analyze Image (full pipeline)**. Show the step list (preprocess, detect, number, segment, match, classify, flip passes), the region table
   (ids, FDI number, candidate class or *no reliable candidate - manual review*, entropy, flags) and the overlays. Toggle masks, change opacity, zoom with the mouse wheel.
   Say: "the class column is a *candidate*; the classifier has no healthy class, so it is never called a finding".
3. **Inspect one region** (click a row): tooth number + confidence, candidate/abstain wording, four uncertainty values, flags. Press **Explain Prediction** on a region with a candidate class: real Grad-CAM, adjustable opacity,
   method note ("does not prove disease").
4. **Calculate Uncertainty** -> "saved" message -> **Uncertainty** page: the image appears with real values; select it to see reasons for any unavailable signal, provisional thresholds and the regions needing review. Sort by combined score.
   Say: "flip disagreement and instability are test-time augmentation of one network, not an ensemble; thresholds were chosen on the calibration split (`Data/reports/uncertainty_evaluation.md`: AUROC 0.77 for entropy vs errors on the test split)".
5. **Active Learning** - *Dataset & pool*: show "scored x of N"; **Score pool images** (n = 5, about a minute) -> strategy *combined* -> run selection: each pick lists the real signal values behind its score. Mention duplicates and the locked test split are excluded.
   Show `Data/reports/active_learning_experiment.md` (random vs entropy vs combined, 3 seeds, same data/budgets) and state the measured result honestly (see `docs/UNCERTAINTY_AND_ACTIVE_LEARNING.md`).
6. **Annotations -> Region review** - the analysed image is in the queue. Open it, click a region, **Save review** (confirm), press it again (refused as duplicate), change to *Correct class* (revision 2, history kept).
   Try approving as the same name (refused), then as another name (approved). Say: "names are self-declared; nothing is expert-verified; reviews on test/validation images are never exported as training data".
6b. Optional: `Approved JSON/CSV` export; explicit training use only via `use_approved_annotations` in a training run.
7. **Reports** - back on Analysis press **Generate Draft Report**. Show the banner (unconfirmed research draft), counts, model versions, abstained regions, the "regions requiring manual review" list. Switch **Language** to हिन्दी, then मराठी: ids, numbers and model versions are identical
   (green "values match English report"); press HTML / TXT / JSON to download. Say: "Hindi/Marathi wording awaits native dental review".
8. **Experiments / Model Registry / Model Training** - real runs and checkpoints with evaluation reports; nothing simulated. Registry shows the four checkpoints, sidecar metrics, and the evaluation reports.
9. **Evidence on disk**: `Data/reports/` (dataset audit, leakage check, per-model evaluation incl. per-class tables, uncertainty evaluation, benchmark, AL experiment).

## If something goes wrong
- *"Dental model setup required"*: a checkpoint is missing or the registry rejected it (Model Registry shows why).
- *Out of memory*: stop any training / experiment process, restart the API.
- *Analysis is slow the first time*: the four models load once (about 10 s), later runs take 3-8 s.
