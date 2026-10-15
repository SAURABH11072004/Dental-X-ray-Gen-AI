#!/usr/bin/env python
"""Alignment audit of the synchronised segmentation augmentation (CPU only, train images only, fixed seed).

Checks per augmented sample: image/mask shapes equal, every box inside the image and equal to the mask's bounding box, no empty
mask, instance count (dropped instances counted), and that the mean grey level INSIDE each transformed mask correlates with the
level inside the original mask (a shifted/shuffled mask would break this). Writes overlay PNGs for visual inspection."""
import _bootstrap  # noqa: F401
import json
from pathlib import Path

import numpy as np
from PIL import Image

from ml_seg_train import AUGS, PRE, SegDS, make_items

OUT = Path("docs/audit_evidence/ml_improvement/visual")


def contour(m):
    k = m.astype(bool)
    e = k.copy()
    e[1:-1, 1:-1] = k[1:-1, 1:-1] & k[:-2, 1:-1] & k[2:, 1:-1] & k[1:-1, :-2] & k[1:-1, 2:]
    return k & ~e


def main():
    s, items = make_items("train")
    ds = SegDS(s.data_root, items, True, dict(AUGS["sync"], hflip=0.0, intensity=False), PRE["none"], 7)
    ref = SegDS(s.data_root, items, False, AUGS["baseline"], PRE["none"], 7)
    rng_pick = np.random.default_rng(5)
    idxs = rng_pick.choice(len(items), 40, replace=False)
    rep = {"n_checked": 0, "shape_mismatch": 0, "box_outside_image": 0, "box_ne_mask_bbox": 0, "empty_mask": 0, "dropped_instances": 0,
           "instances_total": 0, "corr_inside_mask_min": 1.0, "corr_inside_mask_mean": [], "identity_equals_baseline_masks": None}
    # identity check: geom_p = 0 must reproduce the baseline masks exactly
    ident = SegDS(s.data_root, items, True, dict(AUGS["sync"], geom_p=0.0, hflip=0.0, intensity=False), PRE["none"], 7)
    a = ident.load(int(idxs[0]), np.random.default_rng(1))
    b = ref.load(int(idxs[0]))
    rep["identity_equals_baseline_masks"] = bool(len(a[2]) == len(b[2]) and all((x == y).all() for x, y in zip(a[2], b[2])))
    shown = 0
    for k, i in enumerate(idxs):
        rng = np.random.default_rng(100 + k)
        img0, _, masks0, _ = ref.load(int(i))
        img, boxes, masks, info = ds.load(int(i), rng)
        H, W = img.shape[:2]
        rep["n_checked"] += 1
        rep["instances_total"] += len(masks0)
        rep["dropped_instances"] += info["dropped"]
        if img.shape != img0.shape or any(m.shape != (H, W) for m in masks):
            rep["shape_mismatch"] += 1
        for bx, m in zip(boxes, masks):
            ys, xs = np.where(m)
            if len(xs) == 0:
                rep["empty_mask"] += 1
                continue
            if bx[0] < 0 or bx[1] < 0 or bx[2] > W or bx[3] > H:
                rep["box_outside_image"] += 1
            if [bx[0], bx[1], bx[2], bx[3]] != [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)]:
                rep["box_ne_mask_bbox"] += 1
        if info["geom"]:
            # keep original-order correspondence: surviving instances are in the original order, minus dropped ones
            g0 = [float(img0[m, 0].mean()) for m in masks0]
            g1 = [float(img[m, 0].mean()) for m in masks]
            if info["dropped"] == 0 and len(g0) == len(g1) and len(g0) > 5:
                c = float(np.corrcoef(g0, g1)[0, 1])
                rep["corr_inside_mask_mean"].append(c)
                rep["corr_inside_mask_min"] = min(rep["corr_inside_mask_min"], c)
        if shown < 4 and info["geom"]:
            ov = np.stack([img] * 3, -1) if img.ndim == 2 else img.copy()
            for m in masks:
                ov[contour(m)] = (255, 40, 40)
            Image.fromarray(ov).resize((W // 2, H // 2)).save(OUT / f"seg_aug_overlay_{shown}.png")
            json.dump(info, open(OUT / f"seg_aug_overlay_{shown}.json", "w"), indent=1)
            shown += 1
    rep["corr_inside_mask_mean"] = float(np.mean(rep["corr_inside_mask_mean"])) if rep["corr_inside_mask_mean"] else None
    (OUT.parent / "seg_aug_audit.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
