#!/usr/bin/env python
"""Preprocessing audit on TRAIN crops only: channel equality, intensity statistics, noise estimate, and a montage of
original vs stretch / CLAHE / denoise variants for every class (docs/audit_evidence/ml_improvement/visual/)."""
import _bootstrap  # noqa: F401
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ml_common import CLASSES, load_split_crops
from dentexmodel.data import crop_preprocess as CP

OUT = Path("docs/audit_evidence/ml_improvement/visual")
OUT.mkdir(parents=True, exist_ok=True)
VARIANTS = [("original", {"mode": "none"}), ("stretch 1-99", {"mode": "stretch"}),
            ("CLAHE c1.5 g4", {"mode": "clahe", "clip": 1.5, "grid": 4}), ("CLAHE c2.0 g4", {"mode": "clahe", "clip": 2.0, "grid": 4}),
            ("CLAHE c2.5 g8", {"mode": "clahe", "clip": 2.5, "grid": 8}), ("median3", {"mode": "median", "size": 3}),
            ("gauss 0.8", {"mode": "gaussian", "sigma": 0.8})]


def main():
    tr = load_split_crops("train")
    X, y = tr["X"], tr["y"]
    stats = {"n_train_crops": int(len(X)), "channels_identical_fraction": float((X[..., 0] == X[..., 1]).all(axis=(1, 2)).mean()
             * (X[..., 1] == X[..., 2]).all(axis=(1, 2)).mean()), "dtype": str(X.dtype)}
    g = X[..., 0].astype(np.float32)
    stats["mean_grey"] = float(g.mean())
    stats["std_grey"] = float(g.std())
    stats["blank_crops_std_lt3"] = int((g.std(axis=(1, 2)) < 3).sum())
    stats["saturated_fraction_mean"] = float(((g <= 1) | (g >= 254)).mean())
    rng = np.random.default_rng(0)
    idx = rng.choice(len(X), 400, replace=False)
    sig = np.array([CP.noise_sigma(X[i]) for i in idx])
    stats["noise_sigma_grey_levels"] = {"median": float(np.median(sig)), "p90": float(np.percentile(sig, 90)), "max": float(sig.max())}
    # does each variant change statistics / amplify noise?
    comp = {}
    for name, cfg in VARIANTS[1:]:
        out = [CP.apply_crop(X[i], cfg) for i in idx[:100]]
        comp[name] = {"noise_sigma_median": float(np.median([CP.noise_sigma(o) for o in out])),
                      "mean_abs_change": float(np.mean([np.abs(o.astype(np.float32) - X[i].astype(np.float32)).mean() for o, i in zip(out, idx[:100])])),
                      "grey_std_mean": float(np.mean([o[..., 0].std() for o in out]))}
    stats["variants"] = comp
    stats["original_grey_std_mean"] = float(np.mean([X[i][..., 0].std() for i in idx[:100]]))
    (OUT.parent / "preproc_audit.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    # montage: 2 examples per class (class 3 = Periapical Lesion shown with 3), rows=examples, cols=variants
    pick = []
    for c in range(4):
        ids = np.where(y == c)[0]
        pick += list(rng.choice(ids, 3 if c == 3 else 2, replace=False))
    cell = 160
    W = len(VARIANTS) * cell
    img = Image.new("RGB", (W, (len(pick)) * (cell + 14) + 18), "white")
    d = ImageDraw.Draw(img)
    for j, (name, _) in enumerate(VARIANTS):
        d.text((j * cell + 4, 2), name, fill="black")
    for r, i in enumerate(pick):
        for j, (name, cfg) in enumerate(VARIANTS):
            im = Image.fromarray(CP.apply_crop(X[i], cfg)).resize((cell, cell), Image.BILINEAR)
            img.paste(im, (j * cell, 18 + r * (cell + 14)))
        d.text((4, 18 + r * (cell + 14) + cell), CLASSES[y[i]], fill="black")
    img.save(OUT / "preprocessing_variants.png")
    print("montage saved", OUT / "preprocessing_variants.png")


if __name__ == "__main__":
    main()
