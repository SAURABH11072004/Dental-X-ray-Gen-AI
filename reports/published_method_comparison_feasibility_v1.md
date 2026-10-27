# Published-method comparison: feasibility (v1)

Date 2026-10-25. Repository facts were checked online in this session; see the sources at the end.

## 1. Candidate method
**HierarchicalDet** (Hamamci et al., MICCAI 2023 [hamamciMiccai]) is the DENTEX authors' baseline.
* **Repository:** github.com/ibrahimethemhamamci/HierarchicalDet, public.
* **Licence:** code under MIT; the README states CC BY-SA 4.0 for the data.
* **Contents:** training and evaluation code built on detectron2 (`train_net.py`, `evaluator.py`, configs).
* **Weights:** no released weights or releases were visible on the repository page.

The challenge repository (github.com/ibrahimethemhamamci/DENTEX) provides evaluation and baseline Docker containers. It states
CC BY-NC-SA 4.0 for the data and MIT for the rest, and links no participants' code.

## 2. Task mismatch
| Aspect | HierarchicalDet / DENTEX challenge | This study |
|---|---|---|
| Task | detection of abnormal teeth with quadrant, enumeration and diagnosis labels | 4-way classification of each annotated finding, from GT boxes or matched tooth-detector boxes |
| Metric | box AP / AR family (challenge ranking over 12 metrics) | per-finding macro-F1, precision, recall; end-to-end recall |
| Split | official train / validation / test | radiograph-grouped 5-fold CV on 541 radiographs |

**Published AP values cannot be compared with our macro-F1.** The manuscript must not place them side by side as if comparable.

## 3. A fair same-fold comparison (feasible, but expensive)
1. Train HierarchicalDet on each CV5 training fold (5 folds; 5 seeds if the budget allows), using our fold file.
2. Convert its diagnosis boxes into per-finding predictions. Match predicted diagnosis boxes to GT findings at IoU ≥ 0.5; a finding
   without a matched box is end-to-end wrong. The matching and conversion rule must be frozen before any run.
3. Evaluate with the CV5 metrics and bootstrap. The CV5 acceptance protocol applies only if it is registered as a candidate.

**Cost and risk:**
* Diffusion-based detection on detectron2 is heavy; a 4 GB RTX 3050 is unlikely to suffice, so Kaggle T4 sessions are needed.
* The cost is unknown and must be measured in a pilot, not assumed.
* Its training uses the hierarchical (quadrant, enumeration) annotations, so the comparison also changes the supervision.

**Budget:** it would be a new candidate family, so it needs a new amendment and counts toward the lifetime budget of 15.
Amendment 01 currently drafts 3 candidates.

## 4. Recommendation
1. In manuscript v3, give a **qualitative literature comparison only**, stating why the numbers are not comparable. This is done.
2. If reviewers require a same-fold comparison, register HierarchicalDet as a candidate after Amendment 01 is in force, with a frozen
   conversion rule and a pilot cost measurement first.

## Sources
* https://github.com/ibrahimethemhamamci/HierarchicalDet
* https://github.com/ibrahimethemhamamci/DENTEX
* https://arxiv.org/abs/2305.19112
