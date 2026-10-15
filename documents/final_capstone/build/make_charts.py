"""Capstone charts. Every number is read from the project's evaluation reports (read-only); nothing is typed in by hand
except dataset-audit counts that are also read from Data/reports/dataset_audit.json.
Output: documents/final_capstone/figures/*.png (black-and-white friendly, 300 dpi).
Run with the system Python (matplotlib):  python documents/final_capstone/build/make_charts.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "figures"
OUT.mkdir(parents=True, exist_ok=True)
J = lambda p: json.loads((ROOT / p).read_text(encoding="utf-8"))

plt.rcParams.update({"font.family": "Times New Roman", "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "hatch.linewidth": 0.6, "savefig.dpi": 300})
G = ["#1a1a1a", "#6e6e6e", "#b4b4b4", "#e6e6e6"]          # grey levels
H = ["", "///", "...", "xx"]                                # hatches so series never depend on shade alone
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def label_bars(ax, bars, fmt="{:.3f}", dy=0.01, size=8):
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + dy, fmt.format(h), ha="center", va="bottom", fontsize=size)


ev = {f"{m}_{s}": J(f"Data/reports/eval_dentex_{m}_v1_{s}.json")["metrics"]
      for m in ["teeth_detection", "teeth_segmentation", "fdi_numbering", "findings_classification"] for s in ["val", "test"]}
audit = J("Data/reports/dataset_audit.json")
e2e = J("Data/reports/end_to_end_validation_evaluation.json")
unc = J("Data/reports/uncertainty_evaluation.json")
imb = J("docs/audit_evidence/ml_improvement/imbalance/results.json")["methods"]
rec = J("Data/reports/training_recipe_comparison_results.json")
al = J("Data/reports/active_learning_experiment.json")["macro_f1_by_budget"]

# ---- 1. dataset composition ------------------------------------------------------------------------------------------
src = {s["name"]: s for s in audit["sources"]}
names = ["training_data/quadrant", "training_data/quadrant_enumeration", "training_data/quadrant-enumeration-disease",
         "training_data/unlabelled", "validation_data/quadrant_enumeration_disease"]
short = ["Quadrant", "Quadrant +\nenumeration", "Quadrant +\nenumeration +\ndisease", "Unlabelled\npool", "validation_data\n(no labels)"]
vals = [src[n]["n_images"] for n in names]
fig, ax = plt.subplots(figsize=(6.3, 3.0))
bars = ax.bar(short, vals, color=[G[1], G[1], G[0], G[2], G[3]], edgecolor="black", linewidth=0.6, hatch=None)
label_bars(ax, bars, "{:.0f}", dy=20)
ax.set_ylabel("Image files")
ax.set_ylim(0, max(vals) * 1.15)
t = audit["totals"]; d = audit["duplicates"]
ax.set_title(f"DENTEX files on disk: {t['images_on_disk']:,} files, {d['unique_radiographs']:,} unique radiographs, "
             f"{t['annotated_distinct_radiographs']:,} annotated unique", fontsize=9.5)
save(fig, "fig_dataset_sources.png")

# ---- 2. finding label distribution -----------------------------------------------------------------------------------
lab = src["training_data/quadrant-enumeration-disease"]["label_distribution"]["category_id_3"]
train_crops = [1550, 438, 412, 120]   # from the classifier checkpoint sidecar / MODEL_TRAINING.md (train split crops)
val_sup = [e2e["A2_production_gt_boxes"]["per_class"][c]["support"] for c in CLASSES]
test_sup = [ev["findings_classification_test"]["classification"]["per_class"][c]["support"] for c in CLASSES]
fig, ax = plt.subplots(figsize=(6.3, 3.0))
x = np.arange(4); w = 0.2
for i, (vv, nm) in enumerate([( [lab[c] for c in CLASSES], "All labelled findings (705 files)"), (train_crops, "Train crops"),
                               (val_sup, "Validation crops"), (test_sup, "Test crops")]):
    b = ax.bar(x + (i - 1.5) * w, vv, w, label=nm, color=G[i], edgecolor="black", linewidth=0.6, hatch=H[i])
    label_bars(ax, b, "{:.0f}", dy=15, size=7)
ax.set_xticks(x, CLASSES); ax.set_ylabel("Count"); ax.legend(frameon=False, fontsize=8, ncol=2)
ax.set_ylim(0, 2450)
ax.set_title("Finding classes are imbalanced: Periapical Lesion is about 7 % of findings", fontsize=10)
save(fig, "fig_class_distribution.png")

# ---- 3. split sizes --------------------------------------------------------------------------------------------------
sp = t["distinct_radiographs_per_split"]
fig, ax = plt.subplots(figsize=(4.6, 2.4))
order = ["train", "val", "calibration", "test"]
b = ax.barh(order[::-1], [sp[k] for k in order[::-1]], color=[G[3], G[2], G[1], G[0]], edgecolor="black", linewidth=0.6)
for bb in b:
    ax.text(bb.get_width() + 8, bb.get_y() + bb.get_height() / 2, f"{int(bb.get_width())}", va="center", fontsize=9)
ax.set_xlabel("Unique annotated radiographs"); ax.set_xlim(0, 900)
ax.set_title("Duplicate-aware split of 1,133 annotated radiographs", fontsize=10)
save(fig, "fig_splits.png")

# ---- 4. detection & segmentation: validation vs historical test ------------------------------------------------------
def dm(k, key):
    m = ev[k][key]; op = m["operating_point"]
    return [op["precision"], op["recall"], m["ap50"], m["map"]]
fig, axs = plt.subplots(1, 2, figsize=(6.5, 2.9), sharey=True)
labels = ["Precision", "Recall", "AP50", "mAP\n[.5:.95]"]
for ax, (task, key, ttl) in zip(axs, [("teeth_detection", "detection", "Tooth detection (Faster R-CNN)"),
                                      ("teeth_segmentation", "segmentation", "Tooth segmentation (Mask R-CNN), box metrics")]):
    x = np.arange(4)
    for i, (s, nm) in enumerate([("val", "Validation (69 images)"), ("test", "Historical test (63 images)")]):
        b = ax.bar(x + (i - 0.5) * 0.36, dm(f"{task}_{s}", key), 0.36, color=G[i * 2], edgecolor="black", linewidth=0.6, hatch=H[i], label=nm)
        label_bars(ax, b, "{:.3f}", dy=0.01, size=7)
    ax.set_xticks(x, labels); ax.set_ylim(0, 1.12); ax.set_title(ttl, fontsize=9.5)
axs[0].set_ylabel("Score")
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=8.5, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.06))
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(OUT / "fig_detection_segmentation.png", bbox_inches="tight", facecolor="white"); plt.close(fig); print("wrote fig_detection_segmentation.png")

# ---- 5. classifier per class, validation vs historical test ----------------------------------------------------------
cv = ev["findings_classification_val"]["classification"]["per_class"]; ct = ev["findings_classification_test"]["classification"]["per_class"]
fig, axs = plt.subplots(1, 3, figsize=(6.6, 2.8), sharey=True)
for ax, met in zip(axs, ["precision", "recall", "f1"]):
    x = np.arange(4)
    for i, (dd, nm) in enumerate([(cv, "Validation (331 crops)"), (ct, "Historical test (354 crops)")]):
        b = ax.bar(x + (i - 0.5) * 0.38, [dd[c][met] for c in CLASSES], 0.38, color=G[i * 2], edgecolor="black", linewidth=0.6, hatch=H[i], label=nm)
        label_bars(ax, b, "{:.2f}", dy=0.01, size=6.5)
    ax.set_xticks(x, ["Caries", "Deep\nCaries", "Impacted", "Periapical\nLesion"], fontsize=8)
    ax.set_title({"f1": "F1-score"}.get(met, met.capitalize()), fontsize=10); ax.set_ylim(0, 1.1)
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=8.5, ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(OUT / "fig_classifier_per_class.png", bbox_inches="tight", facecolor="white"); plt.close(fig); print("wrote fig_classifier_per_class.png")

# ---- 6. confusion matrix (validation, ground-truth boxes) ------------------------------------------------------------
cm = np.array(e2e["A2_production_gt_boxes"]["confusion_matrix"])
fig, ax = plt.subplots(figsize=(4.4, 3.6))
norm = cm / cm.sum(1, keepdims=True)
ax.imshow(norm, cmap="Greys", vmin=0, vmax=1)
for i in range(4):
    for j in range(4):
        ax.text(j, i, f"{cm[i, j]}\n({norm[i, j]:.0%})", ha="center", va="center", fontsize=8.5, color="white" if norm[i, j] > 0.55 else "black")
short4 = ["Caries", "Deep\nCaries", "Impacted", "Periapical\nLesion"]
ax.set_xticks(range(4), short4, fontsize=8.5); ax.set_yticks(range(4), short4, fontsize=8.5)
ax.set_xlabel("Predicted class"); ax.set_ylabel("Ground-truth class")
ax.spines[:].set_visible(True)
ax.set_title("Validation confusion matrix (ground-truth boxes, n = 331)", fontsize=9.5)
save(fig, "fig_confusion_val.png")

# ---- 7. ground-truth boxes vs detector boxes vs end-to-end (validation) ----------------------------------------------
m5 = e2e["matched@0.5"]; ee = e2e["end_to_end@0.5"]; a2 = e2e["A2_production_gt_boxes"]
groups = [("GT boxes,\nall 331 findings", a2["accuracy"], a2["macro_f1"]),
          ("GT boxes,\nsame 323 teeth", m5["A2_gt_boxes_same_teeth"]["accuracy"], m5["A2_gt_boxes_same_teeth"]["macro_f1"]),
          ("Detector boxes,\n323 matched teeth", m5["B_detector_boxes"]["accuracy"], m5["B_detector_boxes"]["macro_f1"]),
          ("End-to-end,\nall 331 (misses = wrong)", ee["accuracy"], ee["macro_f1"])]
fig, ax = plt.subplots(figsize=(6.4, 2.9))
x = np.arange(len(groups))
for i, nm in enumerate(["Accuracy", "Macro-F1"]):
    b = ax.bar(x + (i - 0.5) * 0.36, [g[1 + i] for g in groups], 0.36, color=G[i * 2], edgecolor="black", linewidth=0.6, hatch=H[i], label=nm)
    label_bars(ax, b, "{:.3f}", dy=0.01, size=7.5)
ax.set_xticks(x, [g[0] for g in groups], fontsize=8.5); ax.set_ylim(0, 1.0); ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper right")
ax.set_title("Finding classification on the validation split: effect of using detector crops", fontsize=10)
save(fig, "fig_gt_vs_detector.png")

# ---- 8. class-imbalance experiment -----------------------------------------------------------------------------------
keys = [("C0", "C0"), ("I_sampler", "A"), ("C3b_oversample_baselineaug", "B"),
        ("I_focal", "C"), ("I_weights_sqrt", "D"), ("I_minority_geom", "E"), ("C_unweighted", "Ref")]
fig, axs = plt.subplots(1, 2, figsize=(6.6, 3.0), gridspec_kw={"width_ratios": [1, 1.25]})
ag = lambda k, m: imb[k]["aggregate"][m]
x = np.arange(len(keys))
mu = [ag(k, "macro_f1")[0] for k, _ in keys]; sd = [ag(k, "macro_f1")[1] for k, _ in keys]
axs[0].errorbar(x, mu, yerr=sd, fmt="o", color="black", ecolor="black", capsize=3, markersize=5)
axs[0].axhline(mu[0], color="grey", lw=0.8, ls="--"); axs[0].axhline(mu[0] + 0.027, color="grey", lw=0.8, ls=":")
axs[0].text(len(keys) - 0.6, mu[0] + 0.029, "required gain +0.027", fontsize=7, ha="right")
for xi, m, s_ in zip(x, mu, sd):
    axs[0].text(xi, m + s_ + 0.003, f"{m:.3f}", fontsize=6.5, ha="center", rotation=90, va="bottom")
axs[0].set_xticks(x, [k[1] for k in keys], fontsize=8.5); axs[0].set_ylabel("Validation macro-F1\n(mean ± SD, 5 seeds)")
axs[0].set_ylim(0.68, 0.83); axs[0].set_title("Macro-F1", fontsize=10)
for i, (cls, nm) in enumerate([("Deep Caries", "Deep Caries recall"), ("Periapical Lesion", "Periapical Lesion recall")]):
    b = axs[1].bar(x + (i - 0.5) * 0.38, [ag(k, f"{cls}|recall")[0] for k, _ in keys], 0.38, color=G[i * 2], edgecolor="black", linewidth=0.6, hatch=H[i], label=nm)
    label_bars(axs[1], b, "{:.2f}", dy=0.01, size=6)
axs[1].set_xticks(x, [k[1] for k in keys], fontsize=8.5); axs[1].set_ylim(0, 1.0); axs[1].legend(frameon=False, fontsize=7.5, loc="upper left", ncol=2)
axs[1].set_title("Minority-class recall (mean of 5 seeds)", fontsize=10)
save(fig, "fig_imbalance.png")

# ---- 9. recipe comparison: per-seed detector-box macro-F1 ------------------------------------------------------------
P = rec["models"]["P_production_recipe"]; E = rec["models"]["E_C0r_recipe"]
seeds = ["42", "43", "44", "45", "46"]
def detf1(d): return d["det_all"]["macro_f1"] if "det_all" in d else d["det_matched"]["macro_f1"]
try:
    pv = [detf1(P[s]) for s in seeds]; evv = [detf1(E[s]) for s in seeds]
except KeyError:
    pv = evv = None
if pv is not None:
    fig, ax = plt.subplots(figsize=(5.4, 2.8))
    x = np.arange(5)
    b1 = ax.bar(x - 0.19, pv, 0.38, color=G[0], edgecolor="black", linewidth=0.6, label="P: production trainer recipe")
    b2 = ax.bar(x + 0.19, evv, 0.38, color=G[2], edgecolor="black", linewidth=0.6, hatch="///", label="E: experiment (C0r) recipe")
    label_bars(ax, b1, "{:.3f}", dy=0.004, size=7); label_bars(ax, b2, "{:.3f}", dy=0.005, size=7)
    ax.set_xticks(x, [f"seed {s}" for s in seeds]); ax.set_ylim(0.6, 0.83); ax.set_ylabel("Macro-F1 on detector crops")
    ax.text(-0.19, pv[0] + 0.024, "(deployed)", ha="center", fontsize=7, style="italic")
    ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
    ax.set_title("Training-recipe comparison on the validation split (323 matched teeth)", fontsize=10)
    save(fig, "fig_recipe.png")
    print("recipe P", [round(v, 3) for v in pv], "E", [round(v, 3) for v in evv])

# ---- 10. uncertainty / abstention -----------------------------------------------------------------------------------
ts = unc["test_split"]; cs = unc["calibration_split"]
fig, axs = plt.subplots(1, 2, figsize=(6.4, 2.7))
b = axs[0].bar(["Flagged for\nreview", "Not flagged"], [ts["error_rate_flagged"], ts["error_rate_not_flagged"]], color=[G[0], G[2]], edgecolor="black", linewidth=0.6)
label_bars(axs[0], b, "{:.1%}", dy=0.008, size=8)
axs[0].set_ylabel("Classifier error rate"); axs[0].set_ylim(0, 0.45)
axs[0].set_title(f"Historical test: {ts['flagged_for_review_fraction']:.0%} flagged,\n{ts['errors_caught_fraction']:.0%} of errors caught", fontsize=9.5)
x = np.arange(2)
for i, (vv, nm) in enumerate([([cs["ece"], ts["ece"]], "Before temperature scaling"),
                              ([cs["ece_after_temperature"], ts["ece_after_temperature_fitted_on_calibration"]], "After (T fitted on calibration)")]):
    b = axs[1].bar(x + (i - 0.5) * 0.36, vv, 0.36, color=G[i * 2], edgecolor="black", linewidth=0.6, hatch=H[i], label=nm)
    label_bars(axs[1], b, "{:.3f}", dy=0.002, size=7.5)
axs[1].set_xticks(x, ["Calibration split", "Historical test"]); axs[1].set_ylabel("Expected calibration error")
axs[1].set_ylim(0, 0.11); axs[1].legend(frameon=False, fontsize=7.5, loc="upper right"); axs[1].set_title("Calibration (ECE)", fontsize=9.5)
save(fig, "fig_uncertainty.png")

# ---- 11. active learning ---------------------------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(5.2, 2.8))
for i, (k, nm, mk) in enumerate([("random", "Random", "o"), ("entropy", "Entropy", "s"), ("combined", "Combined", "^")]):
    bud = sorted(al[k], key=int); m = [al[k][b]["mean"] for b in bud]; s = [al[k][b]["std"] for b in bud]
    ax.errorbar([int(b) + (i - 1) * 3 for b in bud], m, yerr=s, marker=mk, color=G[i], mfc="white" if i == 1 else G[i], capsize=2, lw=1, label=nm)
ax.set_xlabel("Labelled training radiographs (budget)"); ax.set_ylabel("Validation macro-F1")
ax.legend(frameon=False, fontsize=8); ax.set_title("Active learning vs random selection (ResNet-18, 3 seeds)", fontsize=10)
save(fig, "fig_active_learning.png")

# ---- 12. numbering per-tooth exact accuracy (validation) -------------------------------------------------------------
pt = ev["fdi_numbering_val"]["numbering"]["numbering"]["per_tooth"]
teeth = sorted(pt, key=lambda t_: (int(t_[0]), int(t_[1])))
fig, ax = plt.subplots(figsize=(6.6, 2.5))
acc = [pt[t_]["exact_accuracy"] for t_ in teeth]
ax.bar(range(len(teeth)), acc, color=[G[(int(t_[0]) - 1) % 4] for t_ in teeth], edgecolor="black", linewidth=0.4)
ax.set_xticks(range(len(teeth)), teeth, fontsize=7, rotation=90); ax.set_ylim(0.6, 1.02); ax.set_ylabel("Exact FDI accuracy")
ax.set_title("Tooth numbering, validation split: exact FDI accuracy per tooth (matched teeth); shade = quadrant", fontsize=9.5)
save(fig, "fig_numbering_per_tooth.png")
print("min tooth", min(zip(acc, teeth)))
