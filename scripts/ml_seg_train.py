#!/usr/bin/env python
"""Controlled Mask R-CNN (ResNet-50-FPN, COCO-pretrained, one class 'tooth') experiments with synchronised augmentation.

Protocol identical to the deployed trainer: fit on the train split, choose the epoch by validation box mAP@[.5:.95], then measure
box mAP, mask AP@0.5, mean mask IoU and Dice on the VALIDATION split. Calibration and test splits are not loaded here.

Synchronised geometry: one random similarity transform (rotation, scale, translation about the image centre) is applied to the
image (bilinear) and to every polygon vertex with the same matrix; masks are then rasterised from the transformed polygons
(nearest-style, exact), boxes are recomputed from the masks, clipped to the image, and an instance is dropped only if less
than 50 % of its transformed area is still inside the image or it has fewer than 64 mask pixels (documented rule).
Intensity changes touch the image only.

    .venv\\Scripts\\python.exe scripts\\ml_seg_train.py --exp S0r --aug baseline
    .venv\\Scripts\\python.exe scripts\\ml_seg_train.py --exp S3 --aug sync
"""
import _bootstrap  # noqa: F401
import argparse
import copy
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
import torchvision as tv
from PIL import Image
from torch.utils.data import DataLoader, WeightedRandomSampler

from ml_common import free_gpu_mb
from dentexmodel.config import get_settings
from dentexmodel.data import crop_preprocess as CP
from dentexmodel.data.coco import annotation_fdi
from dentexmodel.data.dataset import DatasetService
from dentexmodel.training import trainers as T
from dentexmodel.utils.geometry import polygon_to_mask

OUT = Path("docs/audit_evidence/ml_improvement/seg")
CAND = Path("runtime/candidates")
AUGS = {"baseline": {"name": "baseline", "hflip": 0.5, "geom_p": 0.0, "intensity": False},
        "sync": {"name": "sync_v1", "hflip": 0.5, "geom_p": 0.6, "rot_deg": 5.0, "scale": [0.95, 1.05], "translate": 0.03, "intensity": True,
                 "contrast": [0.9, 1.1], "brightness": 0.05, "min_visible_fraction": 0.5, "min_mask_px": 64}}
PRE = {"none": {"mode": "none"}, "clahe": {"mode": "clahe", "clip": 2.0, "grid": 8}}


def shoelace(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


class SegDS(T.DetDataset):
    def __init__(self, root, items, train, aug, pre, seed=0):
        super().__init__(root, items, True, None, train)
        self.aug, self.pre, self.seed = aug, pre, seed
        self.epoch = 0

    def sample_params(self, rng, W, H):
        a = self.aug
        if not (self.train and a.get("geom_p", 0) and rng.random() < a["geom_p"]):
            return None
        ang = math.radians(rng.uniform(-a["rot_deg"], a["rot_deg"]))
        sc = rng.uniform(*a["scale"])
        return {"rot_deg": math.degrees(ang), "scale": sc, "tx": rng.uniform(-1, 1) * a["translate"] * W, "ty": rng.uniform(-1, 1) * a["translate"] * H}

    @staticmethod
    def affine(par, W, H):
        ang, s = math.radians(par["rot_deg"]), par["scale"]
        R = s * np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        c = np.array([W / 2.0, H / 2.0])
        t = c + np.array([par["tx"], par["ty"]])
        return R, c, t                    # p' = R (p - c) + t

    def load(self, i, rng=None, return_params=False):
        row, anns, cats = self.items[i]
        img = np.asarray(Image.open(self.root / row.file_path).convert("RGB"))
        H, W = img.shape[:2]
        if self.pre["mode"] != "none":
            img = CP.apply_crop(img, self.pre)
        polys = [np.asarray(a["segmentation"][0], float).reshape(-1, 2) for a in anns]
        boxes0 = [[a["bbox"][0], a["bbox"][1], a["bbox"][0] + a["bbox"][2], a["bbox"][1] + a["bbox"][3]] for a in anns]
        rng = rng or np.random.default_rng()
        par = self.sample_params(rng, W, H)
        flip = self.train and rng.random() < self.aug.get("hflip", 0)
        info = {"image_id": row.image_id, "seed": self.seed, "config_version": self.aug["name"], "geom": par, "hflip": bool(flip), "dropped": 0}
        if par:
            R, c, t = self.affine(par, W, H)
            Rinv = np.linalg.inv(R)
            # PIL maps OUTPUT (x,y) -> INPUT:  p = Rinv (p' - t) + c
            a_, b_ = Rinv[0]
            c_, d_ = Rinv[1]
            off = c - Rinv @ t
            fill = tuple(int(v) for v in np.median(img.reshape(-1, 3), axis=0))
            im = Image.fromarray(img).transform((W, H), Image.AFFINE, (a_, b_, off[0], c_, d_, off[1]), resample=Image.BILINEAR, fillcolor=fill)
            img = np.asarray(im)
            polys2, keep = [], []
            for k, p in enumerate(polys):
                p2 = (R @ (p - c).T).T + t
                full = shoelace(p2)
                m = polygon_to_mask(p2, W, H)
                px = int(m.sum())
                if full <= 0 or px < self.aug["min_mask_px"] or px / max(1.0, full) < self.aug["min_visible_fraction"]:
                    info["dropped"] += 1
                    continue
                polys2.append((p2, m))
            masks = [m for _, m in polys2]
            polys = [p for p, _ in polys2]
        else:
            masks = [polygon_to_mask(p, W, H) for p in polys]
        boxes = []
        for m in masks:
            ys, xs = np.where(m)
            boxes.append([float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)])
        if par is None:
            boxes = [[float(v) for v in b] for b in boxes0] if len(boxes0) == len(masks) else boxes
        if flip:
            img = img[:, ::-1]
            masks = [m[:, ::-1] for m in masks]
            boxes = [[W - b[2], b[1], W - b[0], b[3]] for b in boxes]
        if self.train and self.aug.get("intensity"):
            c0, b0 = rng.uniform(*self.aug["contrast"]), rng.uniform(-1, 1) * self.aug["brightness"]
            f = img.astype(np.float32) / 255.0
            f = np.clip((f - f.mean()) * c0 + f.mean() + b0, 0, 1)
            img = np.rint(f * 255).astype(np.uint8)
            info["contrast"], info["brightness"] = round(float(c0), 4), round(float(b0), 4)
        return np.ascontiguousarray(img), boxes, masks, info

    def __getitem__(self, i):
        rng = np.random.default_rng([self.seed, self.epoch, i, torch.initial_seed() % 100000]) if self.train else None
        img, boxes, masks, _ = self.load(i, rng)
        x = torch.from_numpy(img).permute(2, 0, 1).contiguous()
        bt = torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4)
        mt = torch.from_numpy(np.stack(masks).astype(np.uint8)) if masks else torch.zeros((0, *img.shape[:2]), dtype=torch.uint8)
        return x, {"boxes": bt, "labels": torch.ones(len(boxes), dtype=torch.int64), "masks": mt}, self.items[i][0].image_id


def make_items(split):
    s = get_settings()
    svc = DatasetService(s)
    from dentexmodel.data.splits import load_split_file
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == T.TASK_LEVEL["segmentation"] and assign.get(r.image_id) == split]
    return s, T._annotations_for(s, svc, rows)


def image_weights(ds, cap=2.0):
    """Limited instance-aware sampling: images that contain under-represented FDI teeth are drawn up to ``cap`` times more often."""
    from collections import Counter
    f = Counter()
    for row, anns, cats in ds.items:
        for a in anns:
            f[annotation_fdi(a, cats)] += 1
    med = float(np.median(list(f.values())))
    w = []
    for row, anns, cats in ds.items:
        r = [min(cap, max(1.0, med / f[annotation_fdi(a, cats)])) for a in anns]
        w.append(float(np.mean(r)))
    w = np.asarray(w)
    return w / w.mean(), {"fdi_instance_counts": {str(k): v for k, v in sorted(f.items(), key=lambda kv: (kv[0] is None, kv[0]))}, "weight_min": float(w.min() / w.mean()), "weight_max": float(w.max() / w.mean())}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", required=True)
    ap.add_argument("--aug", default="baseline", choices=list(AUGS))
    ap.add_argument("--preproc", default="none", choices=list(PRE))
    ap.add_argument("--sampling", default="uniform", choices=["uniform", "instance_aware"])
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--min-size", type=int, default=800)
    ap.add_argument("--max-size", type=int, default=1333)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--max-train", type=int, default=None, help="smoke test only")
    args = ap.parse_args()
    if free_gpu_mb() < 2500:
        raise SystemExit(f"only {free_gpu_mb()} MB GPU memory free; stopping instead of risking an OOM")
    s, tr_items = make_items("train")
    _, va_items = make_items("val")
    if args.max_train:
        tr_items, va_items = tr_items[:args.max_train], va_items[:args.max_train]
    ds_tr = SegDS(s.data_root, tr_items, True, AUGS[args.aug], PRE[args.preproc], args.seed)
    ds_va = SegDS(s.data_root, va_items, False, AUGS["baseline"], PRE[args.preproc], args.seed)
    dev = torch.device("cuda")
    torch.manual_seed(args.seed)
    model = T.build_detector(torch, tv, "maskrcnn_resnet50_fpn", 2, True).to(dev)
    model.transform.min_size, model.transform.max_size = (args.min_size,), args.max_size
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, weight_decay=args.wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs))
    scaler = torch.amp.GradScaler("cuda")
    samp_info = None
    sampler = None
    if args.sampling == "instance_aware":
        w, samp_info = image_weights(ds_tr)
        sampler = WeightedRandomSampler(torch.tensor(w, dtype=torch.double), num_samples=len(ds_tr), replacement=True, generator=torch.Generator().manual_seed(args.seed))
    loader = DataLoader(ds_tr, batch_size=1, shuffle=sampler is None, sampler=sampler, collate_fn=T._collate, num_workers=args.workers,
                        generator=torch.Generator().manual_seed(args.seed), persistent_workers=args.workers > 0)
    torch.cuda.reset_peak_memory_stats()
    best, best_state, best_ev, hist = -1.0, None, None, []
    t0 = time.time()
    for ep in range(1, args.epochs + 1):
        ds_tr.epoch = ep
        model.train()
        tot, n, comp, t_ep = 0.0, 0, {}, time.time()
        for imgs, tgts, _ in loader:
            imgs = [i.to(dev).float() / 255.0 for i in imgs]
            tg = [{k: v.to(dev) for k, v in d.items()} for d in tgts]
            if any(len(d["boxes"]) == 0 for d in tg):
                continue
            with torch.autocast("cuda"):
                losses = model(imgs, tg)
                loss = sum(losses.values())
            if not torch.isfinite(loss):
                raise SystemExit(f"loss became {float(loss)}; stopping")
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(params, 10.0)
            scaler.step(opt)
            scaler.update()
            tot, n = tot + float(loss), n + 1
            for k, v in losses.items():
                comp[k] = comp.get(k, 0.0) + float(v)
        sched.step()
        ev = T.evaluate_detector(model, ds_va, dev, with_masks=False)
        m = {"epoch": ep, "train_loss": tot / max(1, n), "loss_components": {k: v / max(1, n) for k, v in comp.items()},
             "val_box_map": ev["map"], "val_box_ap50": ev["ap50"], "epoch_seconds": round(time.time() - t_ep, 1)}
        hist.append(m)
        if (ev["map"] or 0) > best:
            best, best_state, best_ep = ev["map"] or 0, copy.deepcopy(model.state_dict()), ep
        print(f"  [{args.exp}] ep{ep} loss {m['train_loss']:.3f} val box mAP {ev['map']:.4f} AP50 {ev['ap50']:.4f} ({m['epoch_seconds']}s)", flush=True)
    dur = time.time() - t0
    model.load_state_dict(best_state)
    full = T.evaluate_detector(model, ds_va, dev, with_masks=True)
    res = {"exp": args.exp, "config": vars(args), "aug_cfg": AUGS[args.aug], "preproc_cfg": PRE[args.preproc], "sampling_info": samp_info,
           "n_train": len(ds_tr), "n_val": len(ds_va), "best_epoch": best_ep, "val": full, "history": hist, "duration_s": round(dur, 1),
           "gpu_peak_mb": round(torch.cuda.max_memory_allocated() / 2**20),
           "split_note": "fit on train; epoch chosen on validation box mAP; calibration/test not used"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{args.exp}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    if args.save:
        CAND.mkdir(parents=True, exist_ok=True)
        torch.save(best_state, CAND / f"{args.exp}.pth")
    print(f"{args.exp}: best ep {best_ep} val box mAP {full['map']:.4f} AP50 {full['ap50']:.4f} mask AP50 {full.get('mask_ap50')} IoU {full.get('mean_mask_iou_matched')} Dice {full.get('mean_dice_matched')} ({dur:.0f}s, peak {res['gpu_peak_mb']} MB)")


if __name__ == "__main__":
    main()
