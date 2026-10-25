#!/usr/bin/env python
"""Figures for manuscript v2, drawn only from checksum-verified archived results (plotting; no new metric except row-normalising
archived confusion counts).

    .venv\\Scripts\\python.exe scripts\\make_manuscript_figures.py

Writes reports/manuscript/figures_v2/fig{1..5}_*.png (300 dpi) and .pdf, plus figures_manifest.json with every source SHA-256.
Refuses to run if the output folder exists.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "kaggle" / "artifacts_cv5_run1"
OUT = ROOT / "reports" / "manuscript" / "figures_v2"
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
SHORT = ["Caries", "Deep\nCaries", "Impacted", "Periapical\nLesion"]
SEEDS = ["42", "43", "44", "45", "46"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verified_cv5() -> tuple[dict, str]:
    sums = {}
    for line in (ART / "SHA256SUMS.txt").read_text().splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*").replace("\\", "/")] = h
    h = sha(ART / "cv5_results.json")
    if sums.get("cv5_results.json") != h:
        raise SystemExit("cv5_results.json does not match SHA256SUMS.txt")
    return json.loads((ART / "cv5_results.json").read_text(encoding="utf-8")), h


def save(fig, name, manifest, sources):
    for ext in ("png", "pdf"):
        p = OUT / f"{name}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight", metadata={"CreationDate": None} if ext == "pdf" else None)
        manifest["figures"][p.name] = {"sha256": sha(p), "sources": sources}
    plt.close(fig)


def fig1(manifest):
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.set_xlim(0, 100), ax.set_ylim(0, 40), ax.axis("off")
    boxes = [
        (1, 22, 16, 14, "DENTEX\ndisease subset\n541 radiographs\n2,851 findings"),
        (21, 22, 16, 14, "Radiograph\ngroups (exact +\nnear-duplicate\nmerge)"),
        (41, 22, 16, 14, "Grouped\n5-fold CV ×\nseeds 42–46\n(25 runs)"),
        (61, 22, 16, 14, "Inner\nvalidation split\n(epoch selection\nonly)"),
        (81, 22, 18, 14, "Out-of-fold\npredictions:\nGT boxes, detector\nboxes, end-to-end"),
        (41, 2, 16, 13, "Radiograph\nbootstrap\n(2,000 draws)"),
        (61, 2, 38, 13, "Frozen acceptance protocol\nfor future candidates (P-A–P-D,\nS1–S7, hard harm H; budget 15)"),
        (1, 2, 36, 13, "Held out from all CV runs:\ncalibration and test splits\n(test use only via ledger)"),
    ]
    for x, y, w, h, t in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4", fc="#eef3f8", ec="#33557a", lw=0.8))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=6.5)
    for x0, x1 in ((17.6, 20.4), (37.6, 40.4), (57.6, 60.4), (77.6, 80.4)):
        ax.annotate("", (x1, 29), (x0, 29), arrowprops={"arrowstyle": "->", "lw": 0.8})
    ax.annotate("", (52, 15.9), (85, 21.3), arrowprops={"arrowstyle": "->", "lw": 0.8})
    save(fig, "fig1_study_design", manifest, ["schematic of the methods text; no data"])


def fig2(res, h, manifest):
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4), constrained_layout=True)
    for ax, st, title in zip(axes, ("gt", "det_matched"), ("GT boxes", "Detector boxes (matched)")):
        cm = np.array(res["summary"][st]["confusion_sum_over_seeds"], float)
        norm = cm / cm.sum(1, keepdims=True)
        im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{norm[i, j]:.2f}\n({int(cm[i, j])})", ha="center", va="center", fontsize=6.5,
                        color="white" if norm[i, j] > 0.6 else "black")
        ax.set_xticks(range(4), SHORT, fontsize=7), ax.set_yticks(range(4), SHORT, fontsize=7)
        ax.set_xlabel("Predicted"), ax.set_title(title, fontsize=9)
        if st == "gt":
            ax.set_ylabel("Reference label")
    fig.colorbar(im, ax=axes, shrink=0.8, label="Row proportion")
    save(fig, "fig2_confusion", manifest, [f"kaggle/artifacts_cv5_run1/cv5_results.json {h}: summary/*/confusion_sum_over_seeds"])


def fig3(res, h, boot, h_boot, manifest):
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    x = np.arange(4)
    for k, (st, lab, col) in enumerate((("gt", "GT boxes", "#33557a"), ("det_matched", "Detector boxes (matched)", "#7aa6c2"))):
        pts = [boot["results"][st]["per_class"][c]["recall"]["point"] for c in CLASSES]
        lo = [boot["results"][st]["per_class"][c]["recall"]["ci95"][0] for c in CLASSES]
        hi = [boot["results"][st]["per_class"][c]["recall"]["ci95"][1] for c in CLASSES]
        ax.bar(x + (k - 1) * 0.27, pts, 0.27, color=col, label=lab,
               yerr=[np.subtract(pts, lo), np.subtract(hi, pts)], capsize=2, error_kw={"lw": 0.7})
    e2e = [[res["pooled_per_seed"][s]["end_to_end"]["recall"][c] for s in SEEDS] for c in CLASSES]
    ax.bar(x + 0.27, [np.mean(v) for v in e2e], 0.27, color="#d9a441", label="End-to-end (unmatched = error)")
    for i, v in enumerate(e2e):
        ax.scatter([x[i] + 0.27] * len(v), v, s=5, color="black", zorder=3)
    ax.set_xticks(x, SHORT), ax.set_ylim(0, 1), ax.set_ylabel("Recall")
    ax.legend(fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3)
    save(fig, "fig3_recall_settings", manifest, [f"reports/cv5_per_class_bootstrap.json {h_boot}",
                                                 f"kaggle/artifacts_cv5_run1/cv5_results.json {h}: pooled_per_seed/*/end_to_end/recall"])


def fig4(res, h, manifest):
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    for k in range(5):
        v = res["per_fold"][str(k)]["det_matched"]["macro_f1"]["values"]
        ax.scatter([k] * len(v), v, s=10, color="#7aa6c2", zorder=2)
        ax.plot([k - 0.25, k + 0.25], [np.mean(v)] * 2, color="#33557a", lw=1.5)
    m = res["summary"]["det_matched"]["macro_f1"]["mean"]
    ax.axhline(m, ls="--", lw=0.8, color="grey")
    ax.text(-0.45, m, "pooled", fontsize=7, va="bottom", ha="left", color="grey")
    ax.set_xticks(range(5), [f"Fold {k}" for k in range(5)], fontsize=7), ax.set_ylabel("Macro-F1 (detector boxes)")
    save(fig, "fig4_fold_variation", manifest, [f"kaggle/artifacts_cv5_run1/cv5_results.json {h}: per_fold/*/det_matched/macro_f1/values"])


def fig5(neg, h_neg, manifest):
    r = {x["id"]: x["value"] for x in neg["rows"]}
    names = [("REF_unweighted", "Unweighted"), ("A1_sqrt_weights", "Sqrt weights"), ("A2_effnum_weights", "Effective-number\nweights"),
             ("B_sampler", "Balanced sampler"), ("C_focal", "Focal loss"), ("D_official_val", "+ Official val. data")]
    labels = [n for _, n in names] + ["+ External data", "5-seed ensemble"]
    gains = [r[f"neg.imbalance.{k}.gain"] for k, _ in names] + [r["neg.external.gain"], r["neg.ensemble.gain"]]
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    y = np.arange(len(labels))[::-1]
    ax.barh(y, gains, color=["#7aa6c2"] * 6 + ["#d9a441", "#8c6bb1"])
    lo, hi = r["neg.ensemble.boot.ci95"]
    ax.errorbar(gains[-1], y[-1], xerr=[[gains[-1] - lo], [hi - gains[-1]]], fmt="none", color="black", capsize=2, lw=0.7)
    ax.axvline(0, color="black", lw=0.6)
    ax.axvline(0.027, color="#b2182b", ls="--", lw=0.9)
    ax.text(0.0275, y[0] + 0.3, "pre-registered\nminimum gain 0.027", fontsize=7, color="#b2182b", va="top")
    ax.set_yticks(y, labels, fontsize=7), ax.set_xlabel("Macro-F1 gain over BASE (validation split, detector boxes)")
    save(fig, "fig5_negative_results", manifest, [f"reports/negative_findings_traceability.json {h_neg}"])


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: write figures of a new version to a new folder")
    res, h = verified_cv5()
    bp, np_ = ROOT / "reports" / "cv5_per_class_bootstrap.json", ROOT / "reports" / "negative_findings_traceability.json"
    boot, neg = json.loads(bp.read_text(encoding="utf-8")), json.loads(np_.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True)
    manifest = {"format": "dentamind-manuscript-figures-v2", "script_sha256": sha(Path(__file__)), "figures": {}}
    fig1(manifest)
    fig2(res, h, manifest)
    fig3(res, h, boot, sha(bp), manifest)
    fig4(res, h, manifest)
    fig5(neg, sha(np_), manifest)
    (OUT / "figures_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"wrote {len(manifest['figures'])} files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
