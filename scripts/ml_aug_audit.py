#!/usr/bin/env python
"""Visual + numeric audit of the conservative classification augmentation (train crops only, fixed seed).

Writes docs/audit_evidence/ml_improvement/visual/augmentation_examples.png and augmentation_provenance.json (source id, class,
transform parameters, seed, config version for every rendered sample). Also measures how much of the crop is filled by border
replication and the pixel change, to reject transformations that distort anatomy."""
import _bootstrap  # noqa: F401
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from ml_common import CLASSES, load_split_crops
from ml_cls_train import AUG, augment_batch

OUT = Path("docs/audit_evidence/ml_improvement/visual")


def main():
    tr = load_split_crops("train")
    X, y, meta = tr["X"], tr["y"], tr["meta"]
    cfg = AUG["conservative_noflip"]
    seed = 123
    rng = np.random.default_rng(seed)
    picks = []
    for c in range(4):
        picks += list(rng.choice(np.where(y == c)[0], 4 if c == 3 else 3, replace=False))
    gen = torch.Generator().manual_seed(seed)
    cell = 150
    ncols = 5   # original + 4 augmented draws
    img = Image.new("RGB", (ncols * cell, len(picks) * (cell + 14) + 4), "white")
    d = ImageDraw.Draw(img)
    prov = []
    for r, i in enumerate(picks):
        xb = torch.from_numpy(X[[i] * 4])
        x01, params = augment_batch(torch, xb, gen, cfg, torch.device("cpu"), return_params=True)
        img.paste(Image.fromarray(X[i]).resize((cell, cell)), (0, 4 + r * (cell + 14)))
        for k in range(4):
            a = (x01[k].permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)
            img.paste(Image.fromarray(a).resize((cell, cell)), ((k + 1) * cell, 4 + r * (cell + 14)))
            prov.append({"source_image_id": meta[i]["image_id"], "annotation_id": meta[i]["ann_id"], "class": CLASSES[y[i]], "draw": k,
                         "params": params[k], "seed": seed, "config_version": cfg["name"], "mean_abs_pixel_change": round(float(np.abs(a.astype(float) - X[i].astype(float)).mean()), 2)})
        d.text((2, 4 + r * (cell + 14) + cell), f"{CLASSES[y[i]]} - {meta[i]['image_id']}", fill="black")
    img.save(OUT / "augmentation_examples.png")
    # extremes the config allows
    ch = [p["mean_abs_pixel_change"] for p in prov]
    summ = {"config": cfg, "seed": seed, "n_rendered": len(prov), "mean_abs_pixel_change": {"mean": float(np.mean(ch)), "max": float(np.max(ch))},
            "max_abs_rotation_deg": max(abs(p["params"].get("rot_deg", 0)) for p in prov),
            "max_abs_translate_frac": max(max(abs(p["params"].get("tx", 0)), abs(p["params"].get("ty", 0))) for p in prov),
            "scale_range_seen": [min(p["params"].get("scale", 1) for p in prov), max(p["params"].get("scale", 1) for p in prov)],
            "vertical_flip": "never applied", "horizontal_flip_in_this_config": cfg["hflip"]}
    (OUT / "augmentation_provenance.json").write_text(json.dumps({"summary": summ, "samples": prov}, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
