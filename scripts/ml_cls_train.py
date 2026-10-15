#!/usr/bin/env python
"""Controlled classification experiments (ResNet-50 on ground-truth tooth crops) with a fixed protocol.

Each run: train split only for fitting, validation split only for epoch selection (best validation macro-F1, as in the deployed
trainer). Calibration and test splits are never loaded here unless --final-test is given for a SAVED candidate (ml_cls_final.py).

    .venv\\Scripts\\python.exe scripts\\ml_cls_train.py --exp C0 --seeds 42 43 44
    .venv\\Scripts\\python.exe scripts\\ml_cls_train.py --exp C4 --preproc clahe15 --aug conservative --imbalance weights --seeds 42 43 44

Options map to the experiment matrix; every run writes docs/audit_evidence/ml_improvement/cls/<exp>_s<seed>.json.
"""
import _bootstrap  # noqa: F401
import argparse
import copy
import json
import math
import time
from pathlib import Path

import numpy as np

from ml_common import CLASSES, free_gpu_mb, load_split_crops, report
from dentexmodel.data import crop_preprocess as CP

OUT = Path("docs/audit_evidence/ml_improvement/cls")
CAND = Path("runtime/candidates")
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
PREPROC = {"none": {"mode": "none"}, "stretch": {"mode": "stretch", "low": 1.0, "high": 99.0},
           "clahe15": {"mode": "clahe", "clip": 1.5, "grid": 4}, "clahe20": {"mode": "clahe", "clip": 2.0, "grid": 4}}
AUG = {"baseline": {"name": "baseline", "hflip": 0.5, "contrast": 0.1, "geom_p": 0.0},
       "none": {"name": "none", "hflip": 0.0, "contrast": 0.0, "geom_p": 0.0},
       "conservative": {"name": "conservative", "hflip": 0.5, "geom_p": 0.7, "rot_deg": 5.0, "translate": 0.03, "scale": [0.95, 1.05],
                        "contrast": [0.9, 1.1], "brightness": 0.05},
       "conservative_noflip": {"name": "conservative_noflip", "hflip": 0.0, "geom_p": 0.7, "rot_deg": 5.0, "translate": 0.03,
                               "scale": [0.95, 1.05], "contrast": [0.9, 1.1], "brightness": 0.05},
       # baseline augmentation for every class (identical to "baseline") PLUS the conservative geometric transform, applied ONLY to
       # Deep Caries (1) and Periapical Lesion (3) crops: a single-factor minority-class augmentation variant
       "minority_geom": {"name": "minority_geom", "hflip": 0.5, "contrast": 0.1, "geom_p": 0.7, "rot_deg": 5.0, "translate": 0.03,
                         "scale": [0.95, 1.05], "geom_classes": [1, 3]}}


def augment_batch(torch, xb_u8, gen, cfg, device, return_params=False, labels=None):
    """xb_u8 (B,H,W,3) uint8 on device -> float (B,3,H,W) in 0..1. All randomness from ``gen`` (CPU generator, seeded).
    ``labels`` (class indices) is only used by configs with ``geom_classes`` (class-restricted geometric augmentation)."""
    B = xb_u8.shape[0]
    x = xb_u8.permute(0, 3, 1, 2).contiguous().float() / 255.0
    params = [{} for _ in range(B)]
    r = lambda *shape: torch.rand(*shape, generator=gen)  # noqa: E731
    if cfg.get("hflip", 0):
        f = (r(B) < cfg["hflip"])
        x = torch.where(f.view(-1, 1, 1, 1).to(device), x.flip(3), x)
        for i in range(B):
            params[i]["hflip"] = bool(f[i])
    if cfg.get("geom_p", 0):
        on = (r(B) < cfg["geom_p"])
        if cfg.get("geom_classes") is not None:
            if labels is None:
                raise ValueError("class-restricted augmentation needs labels")
            on = on & torch.as_tensor(np.isin(np.asarray(labels), cfg["geom_classes"]))
        ang = (r(B) * 2 - 1) * cfg["rot_deg"] * math.pi / 180
        sc = cfg["scale"][0] + r(B) * (cfg["scale"][1] - cfg["scale"][0])
        tx, ty = (r(B) * 2 - 1) * cfg["translate"] * 2, (r(B) * 2 - 1) * cfg["translate"] * 2   # normalised coords span 2
        ang, sc, tx, ty = (torch.where(on, v, d) for v, d in ((ang, torch.zeros(B)), (sc, torch.ones(B)), (tx, torch.zeros(B)), (ty, torch.zeros(B))))
        th = torch.zeros(B, 2, 3)
        th[:, 0, 0], th[:, 0, 1], th[:, 0, 2] = torch.cos(ang) / sc, -torch.sin(ang) / sc, tx
        th[:, 1, 0], th[:, 1, 1], th[:, 1, 2] = torch.sin(ang) / sc, torch.cos(ang) / sc, ty
        grid = torch.nn.functional.affine_grid(th.to(device), list(x.shape), align_corners=False)
        x = torch.nn.functional.grid_sample(x, grid, mode="bilinear", padding_mode="border", align_corners=False)
        for i in range(B):
            if bool(on[i]):
                params[i].update(rot_deg=round(float(ang[i]) * 180 / math.pi, 3), scale=round(float(sc[i]), 4),
                                 tx=round(float(tx[i]) / 2, 4), ty=round(float(ty[i]) / 2, 4))
    c = cfg.get("contrast", 0)
    if c:
        if isinstance(c, (int, float)):       # legacy: +-c/2 multiplicative jitter applied after normalisation in the baseline trainer
            cm = 1 + c * (r(B) - 0.5)
        else:
            cm = c[0] + r(B) * (c[1] - c[0])
        m = x.mean(dim=(1, 2, 3), keepdim=True)
        x = ((x - m) * cm.view(-1, 1, 1, 1).to(device) + m)
        b = (r(B) * 2 - 1) * cfg.get("brightness", 0.0)
        x = (x + b.view(-1, 1, 1, 1).to(device)).clamp(0, 1)
        for i in range(B):
            params[i]["contrast"], params[i]["brightness"] = round(float(cm[i]), 4), round(float(b[i]), 4)
    return (x, params) if return_params else x


def thermal_wait(limit, resume_margin=8, poll_s=15):
    """Pause between epochs while the GPU is at/above ``limit`` deg C; resume at limit - margin. No-op if nvidia-smi is unavailable."""
    if not limit:
        return
    import subprocess
    def temp():
        try:
            return int(subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader"], capture_output=True, text=True, timeout=10).stdout.split()[0])
        except Exception:  # noqa: BLE001
            return None
    t = temp()
    if t is None or t < limit:
        return
    print(f"  THERMAL PAUSE: GPU {t} C >= {limit} C", flush=True)
    while t is not None and t > limit - resume_margin:
        time.sleep(poll_s)
        t = temp()
    print(f"  THERMAL RESUME: GPU {t} C", flush=True)


def norm(torch, x01, device):
    m = torch.tensor(MEAN, device=device).view(1, 3, 1, 1)
    s = torch.tensor(STD, device=device).view(1, 3, 1, 1)
    return (x01 - m) / s


def class_weights(counts, mode, cap=5.0):
    counts = np.asarray(counts, float)
    w = counts.sum() / (len(counts) * counts)                # inverse frequency
    if mode == "weights_sqrt":
        w = np.sqrt(w)
    w = np.minimum(w, cap)
    return w / (w * counts).sum() * counts.sum()             # normalised so the average sample weight is 1


def build_indices(y, imbalance, rng):
    """Index list for one epoch. 'oversample': partial balancing, target_c = min(3*n_c, sqrt(n_max*n_c)); 'sampler': draws with
    probability proportional to n_c^-0.5 (same epoch length). Originals are always all present in 'oversample'."""
    n = np.bincount(y, minlength=len(CLASSES))
    if imbalance in ("none", "weights", "weights_sqrt", "focal"):
        return rng.permutation(len(y))
    if imbalance == "sampler":
        p = (1.0 / np.sqrt(n))[y]
        return rng.choice(len(y), size=len(y), replace=True, p=p / p.sum())
    if imbalance == "oversample":
        idx = [np.arange(len(y))]
        for c in range(len(CLASSES)):
            tgt = int(min(3 * n[c], math.sqrt(n.max() * n[c])))
            extra = tgt - n[c]
            if extra > 0:
                idx.append(rng.choice(np.where(y == c)[0], size=extra, replace=True))
        return rng.permutation(np.concatenate(idx))
    raise ValueError(imbalance)


def evaluate(torch, model, Xv, yv, device, bs=64):
    model.eval()
    prob = []
    with torch.no_grad():
        for i in range(0, len(Xv), bs):
            xb = torch.from_numpy(Xv[i:i + bs]).to(device).permute(0, 3, 1, 2).contiguous().float() / 255.0
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                lo = model(norm(torch, xb, device))
            prob.append(torch.softmax(lo.float(), 1).cpu().numpy())
    prob = np.concatenate(prob)
    return prob, report(yv, prob.argmax(1), prob)


def run(args, seed, tr, va, inputs=None):
    import torch
    import torchvision as tv
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pre = PREPROC[args.preproc]
    Xtr = np.stack(CP.apply_crops(list(tr["X"]), pre)) if pre["mode"] != "none" else tr["X"]
    Xva = np.stack(CP.apply_crops(list(va["X"]), pre)) if pre["mode"] != "none" else va["X"]
    ytr, yva = tr["y"], va["y"]
    counts = np.bincount(ytr, minlength=len(CLASSES))
    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)
    gen = torch.Generator().manual_seed(seed)
    model = tv.models.resnet50(weights=tv.models.ResNet50_Weights.IMAGENET1K_V2)
    model.fc = torch.nn.Linear(model.fc.in_features, len(CLASSES))
    model.to(device)
    cfg_aug = AUG[args.aug]
    if args.freeze_epochs:
        for n_, p in model.named_parameters():
            if not n_.startswith("fc."):
                p.requires_grad = False
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=args.wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs))
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    bank = np.load(args.crop_bank, mmap_mode="r") if args.crop_bank else None
    if bank is not None and (bank.shape[0] != len(ytr) or not np.array_equal(np.asarray(bank[:16, 0]), Xtr[:16])):
        raise SystemExit("crop bank does not match the training crop cache (order/content)")
    jrng = np.random.default_rng(seed + 10_000)      # separate stream: the jitter draw does not change the other random streams
    use_w = args.imbalance in ("weights", "weights_sqrt")
    cw = torch.tensor(class_weights(counts, args.imbalance), dtype=torch.float32, device=device) if use_w else None
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    best, best_state, best_ep, hist = -1.0, None, 0, []
    for ep in range(1, args.epochs + 1):
        if args.freeze_epochs and ep == args.freeze_epochs + 1:
            for p in model.parameters():
                p.requires_grad = True
            opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, args.epochs - args.freeze_epochs))
        thermal_wait(args.thermal_limit)
        model.train()
        idx = build_indices(ytr, args.imbalance, rng)
        tot, nseen = 0.0, 0
        for i in range(0, len(idx), args.batch_size):
            b = idx[i:i + args.batch_size]
            if len(b) < 2:
                continue
            if bank is not None:      # crop-robustness: exact GT crop with p=1-jitter_p, else a random jittered variant (training only)
                var = np.where(jrng.random(len(b)) < args.jitter_p, jrng.integers(1, bank.shape[1], len(b)), 0)
                xb = torch.from_numpy(np.stack([bank[k, v] for k, v in zip(b, var)])).to(device)
            else:
                xb = torch.from_numpy(Xtr[b]).to(device)
            x01 = augment_batch(torch, xb, gen, cfg_aug, device, labels=ytr[b])
            yb = torch.from_numpy(ytr[b]).to(device)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                lo = model(norm(torch, x01, device))
            lo = lo.float()
            if args.imbalance == "focal":
                ce = torch.nn.functional.cross_entropy(lo, yb, reduction="none")
                loss = ((1 - torch.exp(-ce)) ** args.gamma * ce).mean()
            else:
                loss = torch.nn.functional.cross_entropy(lo, yb, weight=cw)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tot += float(loss) * len(b)
            nseen += len(b)
        sched.step()
        prob, rep = evaluate(torch, model, Xva, yva, device)
        vloss = float(rep["nll"])
        m = {"epoch": ep, "train_loss": tot / max(1, nseen), "val_loss": vloss, "val_macro_f1": rep["macro_f1"], "val_acc": rep["accuracy"],
             "val_pl_recall": rep["minority_recall_periapical"], "val_balanced_acc": rep["balanced_accuracy"]}
        hist.append(m)
        if rep["macro_f1"] > best:
            best, best_state, best_ep, best_rep, best_prob = rep["macro_f1"], copy.deepcopy(model.state_dict()), ep, rep, prob
        print(f"  [{args.exp} s{seed}] ep{ep:02d} train {m['train_loss']:.3f} val_loss {vloss:.3f} F1 {rep['macro_f1']:.3f} acc {rep['accuracy']:.3f} PLrec {rep['minority_recall_periapical']:.2f}", flush=True)
    dur = time.time() - t0
    res = {"exp": args.exp, "seed": seed, "config": {k: v for k, v in vars(args).items() if k not in ("seeds",)},
           "preproc_cfg": pre, "aug_cfg": cfg_aug, "train_counts": counts.tolist(), "n_val": int(len(yva)),
           "best_epoch": best_ep, "best_val": best_rep, "last_val": {k: hist[-1][k] for k in ("val_macro_f1", "val_acc", "val_pl_recall", "val_loss")},
           "history": hist, "duration_s": round(dur, 1),
           "gpu_peak_mb": round(torch.cuda.max_memory_allocated() / 2**20) if device.type == "cuda" else None,
           "split_note": "fit on train split; epoch selection on validation split; calibration and test not used",
           "inputs": inputs}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{args.exp}_s{seed}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    # best-epoch validation probabilities (for post-hoc threshold analysis; training is not affected)
    np.savez(OUT / f"{args.exp}_s{seed}_valprob.npz", prob=best_prob, y=yva, image_id=np.array([m["image_id"] for m in va["meta"]]))
    if args.save:
        CAND.mkdir(parents=True, exist_ok=True)
        p = CAND / f"{args.exp}_s{seed}.pth"
        torch.save(best_state, p)
        res["checkpoint"] = str(p)
    del model, opt
    torch.cuda.empty_cache()
    return res


def _inputs() -> dict:
    """Exact inputs of a run: crop caches, split assignments, manifest and this script (SHA-256)."""
    import hashlib
    from dentexmodel.config import get_settings
    from dentexmodel.training.trainers import assignments_sha
    s = get_settings()
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else None  # noqa: E731
    return {"crops_train_sha256": sha("runtime/ml_cache/crops_train_224.npz"), "crops_val_sha256": sha("runtime/ml_cache/crops_val_224.npz"),
            "split_assignments_sha": assignments_sha(s.splits_dir / "dentex_splits.json"), "manifest_sha256": sha(s.processed_dir / "manifest.json"),
            "script_sha256": sha(__file__)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", required=True)
    ap.add_argument("--preproc", default="none", choices=list(PREPROC))
    ap.add_argument("--aug", default="baseline", choices=list(AUG))
    ap.add_argument("--only-new", action="store_true", help="skip seeds whose result JSON already exists (resume after a failure)")
    ap.add_argument("--crop-bank", default=None, help="TRAINING crop bank (scripts/ml_crop_bank.py): variant 0 = exact box, 1..K = jittered boxes")
    ap.add_argument("--jitter-p", type=float, default=0.8, help="with --crop-bank: probability of using a jittered variant for a training sample")
    ap.add_argument("--thermal-limit", type=int, default=0, help="pause between epochs while the GPU is at or above this temperature (deg C); 0 = off")
    ap.add_argument("--imbalance", default="weights", choices=["none", "weights", "weights_sqrt", "sampler", "oversample", "focal"])
    ap.add_argument("--gamma", type=float, default=2.0)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--wd", type=float, default=1e-4)
    ap.add_argument("--freeze-epochs", type=int, default=0, help="train only the new head for N epochs first")
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--save", action="store_true", help="keep the best-validation state under runtime/candidates/ (never Data/checkpoints)")
    args = ap.parse_args()
    if free_gpu_mb() < 2200:
        raise SystemExit(f"only {free_gpu_mb()} MB GPU memory free; need ~2200 MB - stopping instead of risking an OOM")
    tr, va = load_split_crops("train"), load_split_crops("val")
    inputs = _inputs()
    rows = []
    for sd in args.seeds:
        if args.only_new and (OUT / f"{args.exp}_s{sd}.json").is_file():
            print(f"{args.exp} seed {sd}: result exists, skipped", flush=True)
            rows.append(json.loads((OUT / f"{args.exp}_s{sd}.json").read_text(encoding="utf-8")))
            continue
        r = run(args, sd, tr, va, inputs)
        rows.append(r)
        print(f"{args.exp} seed {sd}: best ep {r['best_epoch']} val macro-F1 {r['best_val']['macro_f1']:.4f} acc {r['best_val']['accuracy']:.4f} "
              f"PL recall {r['best_val']['minority_recall_periapical']:.3f}  ({r['duration_s']}s, peak {r['gpu_peak_mb']} MB)", flush=True)
    f1 = [r["best_val"]["macro_f1"] for r in rows]
    print(f"{args.exp}: macro-F1 mean {np.mean(f1):.4f} sd {np.std(f1):.4f} over seeds {args.seeds}")


if __name__ == "__main__":
    main()
