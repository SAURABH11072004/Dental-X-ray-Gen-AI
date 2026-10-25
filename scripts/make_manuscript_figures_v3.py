#!/usr/bin/env python
"""Figures for manuscript v3: the five v2 figures (copied after checking reports/manuscript/figures_v2/figures_manifest.json) plus
fig6, the error attribution, drawn from reports/cv5_error_attribution.json. Plotting only. Refuses to overwrite figures_v3/.

    .venv\\Scripts\\python.exe scripts\\make_manuscript_figures_v3.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "reports" / "manuscript" / "figures_v2"
OUT = ROOT / "reports" / "manuscript" / "figures_v3"
ATTR = ROOT / "reports" / "cv5_error_attribution.json"
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} exists: write a new version instead of overwriting")
    man2 = json.loads((V2 / "figures_manifest.json").read_text(encoding="utf-8"))
    for name, e in man2["figures"].items():
        if sha(V2 / name) != e["sha256"]:
            raise SystemExit(f"figures_v2/{name} does not match its manifest")
    a = json.loads(ATTR.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True)
    manifest = {"format": "dentamind-manuscript-figures-v3", "script_sha256": sha(Path(__file__)), "figures": {}}
    for name, e in man2["figures"].items():
        shutil.copy2(V2 / name, OUT / name)
        manifest["figures"][name] = {"sha256": sha(OUT / name), "sources": e["sources"] + ["copied from figures_v2 (hash-checked)"]}

    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    parts = [("No overlapping detector box", "#b2182b"), ("Box with IoU < 0.5", "#ef8a62"), ("Matching conflict", "#fddbc7"),
             ("Misclassified on matched box", "#67a9cf"), ("Correct", "#d1e5f0")]
    y = np.arange(len(CLASSES))[::-1]
    for i, c in enumerate(CLASSES):
        p = a["per_class"][c]
        tot = p["pred_total"]
        seeds = tot / p["findings"]
        vals = [p["U0"] * seeds / tot, p["U1"] * seeds / tot, p["U2"] * seeds / tot, p["pred_misclassified"] / tot, p["pred_correct"] / tot]
        left = 0.0
        for (lab, col), v in zip(parts, vals):
            ax.barh(y[i], v, left=left, color=col, edgecolor="white", lw=0.4, label=lab if i == 0 else None)
            left += v
    ax.set_yticks(y, CLASSES), ax.set_xlim(0, 1), ax.set_xlabel("Share of finding × seed predictions (end-to-end)")
    ax.legend(fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3)
    for ext in ("png", "pdf"):
        p = OUT / f"fig6_error_attribution.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight", metadata={"CreationDate": None} if ext == "pdf" else None)
        manifest["figures"][p.name] = {"sha256": sha(p), "sources": [f"reports/cv5_error_attribution.json {sha(ATTR)}"]}
    plt.close(fig)
    (OUT / "figures_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"wrote {len(manifest['figures'])} files to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
