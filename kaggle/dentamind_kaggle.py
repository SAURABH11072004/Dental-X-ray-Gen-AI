"""DentaMind finding-classifier imbalance experiments: data, training (resumable), evaluation, acceptance rule.

Used by kaggle/denta_mind_training.ipynb; importable locally too (tests/test_kaggle_training_lib.py). Depends on torch, torchvision,
numpy, Pillow and scripts/dataset/dsutil.py (crop rule identical to production ``trainers.crop_region``).

The baseline reproduces the project's same-code baseline C0r (= scripts/ml_cls_train.py --exp C0r): ResNet-50 IMAGENET1K_V2,
224 px ground-truth crops (pad 0.10), AdamW lr 3e-4 wd 1e-4, cosine T_max 15, batch 32, 15 epochs, horizontal flip p=0.5 +
+-5 % contrast, inverse-frequency class weights capped at 5, best epoch by validation macro-F1. Exactly one factor changes per
experiment. The test split is evaluated only for the baseline and for candidates that pass the acceptance rule on validation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for p in (HERE.parent / "scripts" / "dataset", HERE / "scripts" / "dataset"):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
from dsutil import CLASSES, CROP_PAD, CROP_SIZE, crop_region, read_csv, sha256_file  # noqa: E402

MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
IOU_THR, DET_SCORE = 0.5, 0.3                      # same as scripts/ml_recipe_eval.py
ABSTAIN_ENTROPY = 0.3965956833419285               # production rule (data/reports/uncertainty_thresholds.json), NOT refitted
# Pre-registered acceptance criteria of this project (data/reports/training_recipe_comparison_protocol.md section 5, and the
# precision side-condition of docs/audit_evidence/ml_improvement/imbalance/report.md). Applied unchanged; candidate vs BASE.
ACCEPT = {"gain_min": 0.027, "seed_pairs_min": 4, "cross_pairs_min": 20, "class_f1_drop_max": 0.05, "gt_macro_f1_drop_max": 0.02,
          "minority_precision_drop_max": 0.10}
MINORITY = ("Deep Caries", "Periapical Lesion")


# ----------------------------------------------------------------------------------------------------------------- config
@dataclass
class ExpConfig:
    name: str
    loss: str = "ce"                    # ce | focal
    weights: str = "inverse_cap5"       # none | inverse_cap5 | sqrt | effective_number
    sampler: str = "none"               # none | sqrt_inverse (p ~ n_c^-0.5, epoch length unchanged)
    data: str = "dentex"                # dentex | dentex+official_val
    gamma: float = 2.0
    beta: float = 0.999                 # effective-number weights
    epochs: int = 15
    batch_size: int = 32
    lr: float = 3e-4
    wd: float = 1e-4
    hflip: float = 0.5
    contrast: float = 0.1               # multiplicative +-contrast/2 around the per-image mean, clamped to [0,1]
    note: str = ""
    extra: dict = field(default_factory=dict)


EXPERIMENTS = {
    "REF_unweighted": ExpConfig("REF_unweighted", weights="none", note="reference: plain cross-entropy"),
    "BASE": ExpConfig("BASE", note="current recipe (C0r): inverse-frequency weights capped at 5"),
    "A1_sqrt_weights": ExpConfig("A1_sqrt_weights", weights="sqrt", note="Strategy A: sqrt(inverse frequency) weights"),
    "A2_effnum_weights": ExpConfig("A2_effnum_weights", weights="effective_number", note="Strategy A: effective-number weights (Cui 2019, beta 0.999)"),
    "B_sampler": ExpConfig("B_sampler", weights="none", sampler="sqrt_inverse", note="Strategy B: weighted sampler p~n_c^-0.5, plain CE"),
    "C_focal": ExpConfig("C_focal", loss="focal", weights="none", note="Strategy C: focal loss gamma 2, no class weights"),
    "D_official_val": ExpConfig("D_official_val", data="dentex+official_val", note="Strategy D: BASE + DENTEX official-validation findings in train"),
    # external panoramic data (reports/external_data_protocol.md, pre-registered 2026-10-24); BASE recipe, only the data changes
    "X1_cluj": ExpConfig("X1_cluj", data="dentex+cluj", note="BASE + Cluj (Zenodo 15487430) Impacted, Periapical Lesion, partial caries crops"),
    "X2_hanoi": ExpConfig("X2_hanoi", data="dentex+hanoi", note="BASE + Hanoi (Mendeley kx52tk2ddj) Periapical Lesion crops, cap 1,500"),
    "X3_both": ExpConfig("X3_both", data="dentex+cluj+hanoi", note="BASE + Cluj + Hanoi (cap 1,500)"),
}
PARTIAL_CARIES = 4          # label index: {Caries, Deep Caries} (caries of unrecorded depth); never a prediction target


def class_counts(y):
    """Counts of the four fully labelled classes (partial labels excluded, so BASE weights are unchanged)."""
    y = np.asarray(y)
    return np.bincount(y[y < len(CLASSES)], minlength=len(CLASSES))


def ce_partial(torch, logits, target, weight=None):
    """Weighted mean cross-entropy that also accepts the partial label PARTIAL_CARIES: loss = -log(p_Caries + p_DeepCaries).
    With no partial label in the batch it is exactly F.cross_entropy(logits, target, weight=weight). Partial samples get the
    Caries class weight (protocol section 1)."""
    F = torch.nn.functional
    part = target == PARTIAL_CARIES
    if not bool(part.any()):
        return F.cross_entropy(logits, target, weight=weight)
    logp = F.log_softmax(logits, 1)
    full = ~part
    tgt = torch.where(full, target, torch.zeros_like(target))
    nll = -logp.gather(1, tgt.view(-1, 1)).squeeze(1)
    nll = torch.where(part, -torch.logsumexp(logp[:, :2], 1), nll)
    w = weight[tgt] if weight is not None else torch.ones_like(nll)
    return (w * nll).sum() / w.sum()


# ------------------------------------------------------------------------------------------------------------------ data
def load_split(split_dir, split):
    p = Path(split_dir) / f"combined_{split}.csv"
    return read_csv(p) if p.is_file() else []


def verify_images(rows, data_root, max_report=10):
    """SHA-256 of every distinct image against the manifest. Returns (n_ok, problems)."""
    seen, bad = {}, []
    for r in rows:
        if r["image_path"] in seen:
            continue
        p = Path(data_root) / r["image_path"]
        if not p.is_file():
            bad.append(f"missing {r['image_path']}")
            seen[r["image_path"]] = False
            continue
        ok = sha256_file(p) == r["image_sha256"]
        seen[r["image_path"]] = ok
        if not ok:
            bad.append(f"sha256 mismatch {r['image_path']}")
    return sum(seen.values()), bad[:max_report] + ([f"... {len(bad) - max_report} more"] if len(bad) > max_report else [])


def build_crops(rows, data_root, cache_file=None):
    """GT-box crops exactly as the production trainer makes them. -> X uint8 (N,224,224,3), y (N,), meta list."""
    from PIL import Image
    if cache_file and Path(cache_file).is_file():
        z = np.load(cache_file, allow_pickle=False)
        meta = json.loads(Path(str(cache_file) + ".json").read_text(encoding="utf-8"))
        if [m["sample_id"] for m in meta] == [r["sample_id"] for r in rows]:
            return z["X"], z["y"], meta
    by_img = {}
    for i, r in enumerate(rows):
        by_img.setdefault(r["image_path"], []).append(i)
    X = np.zeros((len(rows), CROP_SIZE, CROP_SIZE, 3), np.uint8)
    keep = np.zeros(len(rows), bool)
    for path, idx in by_img.items():
        img = np.asarray(Image.open(Path(data_root) / path).convert("RGB"))
        for i in idx:
            x, y_, w, h = json.loads(rows[i]["bbox_xywh"])
            c = crop_region(img, (x, y_, x + w, y_ + h), CROP_SIZE, CROP_PAD)
            if c is not None:
                X[i], keep[i] = c, True
    if not keep.all():
        raise ValueError(f"{(~keep).sum()} manifest rows produced no crop - manifest and crop rule disagree")
    y = np.array([int(r["class_index"]) for r in rows], np.int64)
    meta = [{"sample_id": r["sample_id"], "source_dataset": r["source_dataset"], "image_path": r["image_path"],
             "radiograph_group": r["radiograph_group"]} for r in rows]
    if cache_file:
        np.savez(cache_file, X=X, y=y)
        Path(str(cache_file) + ".json").write_text(json.dumps(meta), encoding="utf-8")
    return X, y, meta


def box_iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return float(inter / union) if union > 0 else 0.0


def match(gt, pred, thr=IOU_THR):
    """Greedy one-to-one matching by IoU (identical to scripts/ml_recipe_eval.py)."""
    pairs = sorted(((box_iou(g, p), i, j) for i, g in enumerate(gt) for j, p in enumerate(pred)), reverse=True)
    ug, up, m = set(), set(), {}
    for v, i, j in pairs:
        if v < thr:
            break
        if i in ug or j in up:
            continue
        ug.add(i)
        up.add(j)
        m[i] = (j, v)
    return m


def build_detector_crops(rows, data_root, det_cache_path, image_id_of):
    """Crops from cached production-detector boxes (score >= 0.3) matched to GT findings. -> Xd, matched index array, n_missed.
    ``image_id_of(row)`` maps a manifest row to the key used in the detector cache (project image_id)."""
    from PIL import Image
    det = json.loads(Path(det_cache_path).read_text(encoding="utf-8"))
    by_img = {}
    for i, r in enumerate(rows):
        by_img.setdefault(r["image_path"], []).append(i)
    Xd, mi, missed = [], [], 0
    for path, idx in by_img.items():
        key = image_id_of(rows[idx[0]])
        boxes = [d[:4] for d in det.get(key, []) if d[4] >= DET_SCORE]
        gts = []
        for i in idx:
            x, y_, w, h = json.loads(rows[i]["bbox_xywh"])
            gts.append([x, y_, x + w, y_ + h])
        m = match(gts, boxes)
        img = None
        for k, i in enumerate(idx):
            hit = m.get(k)
            if hit is None:
                missed += 1
                continue
            img = img if img is not None else np.asarray(Image.open(Path(data_root) / path).convert("RGB"))
            c = crop_region(img, boxes[hit[0]], CROP_SIZE, CROP_PAD)
            if c is None:
                missed += 1
                continue
            Xd.append(c)
            mi.append(i)
    order = np.argsort(mi, kind="stable")
    return np.stack(Xd)[order], np.asarray(mi)[order], missed


# ------------------------------------------------------------------------------------------------- imbalance components
def class_weights(counts, scheme, cap=5.0, beta=0.999):
    """Training-split class weights normalised so the average SAMPLE weight is 1. scheme: none | inverse_cap5 | sqrt | effective_number.
    ``inverse_cap5`` equals scripts/ml_cls_train.class_weights(counts, 'weights')."""
    counts = np.asarray(counts, float)
    if (counts <= 0).any():
        raise ValueError(f"every class needs training samples, got {counts.tolist()}")
    if scheme == "none":
        return None
    if scheme in ("inverse_cap5", "sqrt"):
        w = counts.sum() / (len(counts) * counts)               # inverse frequency (already average sample weight 1)
        if scheme == "sqrt":
            w = np.sqrt(w)
    elif scheme == "effective_number":
        w = (1 - beta) / (1 - np.power(beta, counts))
        w = w / (w * counts).sum() * counts.sum()               # put on the same scale before the cap
    else:
        raise ValueError(scheme)
    w = np.minimum(w, cap)
    return w / (w * counts).sum() * counts.sum()


def sampler_indices(y, rng, power=0.5):
    """One epoch of indices drawn with replacement, p(sample) ~ n_class^-power; epoch length = len(y)."""
    n = np.bincount(y, minlength=len(CLASSES)).astype(float)
    p = (1.0 / n ** power)[y]
    return rng.choice(len(y), size=len(y), replace=True, p=p / p.sum())


def sampler_exposure(y, power=0.5):
    """Expected draws per epoch of one sample of each class (1.0 = as often as without a sampler)."""
    n = np.bincount(y, minlength=len(CLASSES)).astype(float)
    p_class = n ** (1 - power) / (n ** (1 - power)).sum()
    return {c: round(float(len(y) * p_class[k] / n[k]), 3) for k, c in enumerate(CLASSES)}


def focal_loss(torch, logits, target, gamma=2.0, weight=None):
    ce = torch.nn.functional.cross_entropy(logits, target, reduction="none", weight=weight)
    pt = torch.exp(-torch.nn.functional.cross_entropy(logits, target, reduction="none"))
    return ((1 - pt) ** gamma * ce).mean()


def augment(torch, xb_u8, gen, cfg: ExpConfig, device):
    """Baseline augmentation of scripts/ml_cls_train.py ('baseline'): hflip p, multiplicative contrast 1+c*(u-0.5) around the
    per-image mean, clamp [0,1]. Crop-level only (finding class is invariant to a mirror of the crop; no FDI task involved)."""
    B = xb_u8.shape[0]
    x = xb_u8.permute(0, 3, 1, 2).contiguous().float() / 255.0
    r = lambda *s: torch.rand(*s, generator=gen)  # noqa: E731
    if cfg.hflip:
        f = (r(B) < cfg.hflip)
        x = torch.where(f.view(-1, 1, 1, 1).to(device), x.flip(3), x)
    if cfg.contrast:
        cm = 1 + cfg.contrast * (r(B) - 0.5)
        m = x.mean(dim=(1, 2, 3), keepdim=True)
        r(B)    # brightness draw (amplitude 0 in the baseline); kept so the random stream matches scripts/ml_cls_train.py
        x = ((x - m) * cm.view(-1, 1, 1, 1).to(device) + m).clamp(0, 1)
    return x


def norm(torch, x01, device):
    return (x01 - torch.tensor(MEAN, device=device).view(1, 3, 1, 1)) / torch.tensor(STD, device=device).view(1, 3, 1, 1)


# ------------------------------------------------------------------------------------------------------------- metrics
def report(y_true, y_pred, prob=None):
    n = len(CLASSES)
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    cm = np.zeros((n, n), int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    sup, tp = cm.sum(1), np.diag(cm)
    prec = np.divide(tp, cm.sum(0), out=np.zeros(n), where=cm.sum(0) > 0)
    rec = np.divide(tp, sup, out=np.zeros(n), where=sup > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros(n), where=(prec + rec) > 0)
    out = {"n": int(len(y_true)), "accuracy": float(tp.sum() / max(1, cm.sum())), "macro_precision": float(prec.mean()),
           "macro_recall": float(rec.mean()), "macro_f1": float(f1.mean()), "balanced_accuracy": float(rec.mean()),
           "per_class": {CLASSES[i]: {"precision": float(prec[i]), "recall": float(rec[i]), "f1": float(f1[i]), "support": int(sup[i]),
                                      "false_positives": int(cm[:, i].sum() - cm[i, i])} for i in range(n)},
           "confusion": cm.tolist()}
    if prob is not None:
        prob = np.asarray(prob, float)
        conf, pred = prob.max(1), prob.argmax(1)
        ece = 0.0
        for b in range(10):
            m = (conf > b / 10) & (conf <= (b + 1) / 10)
            if m.any():
                ece += m.mean() * abs((pred[m] == y_true[m]).mean() - conf[m].mean())
        out["nll"] = float(-np.log(np.clip(prob[np.arange(len(y_true)), y_true], 1e-9, 1)).mean())
        out["ece_10bin"] = float(ece)
        H = -(np.clip(prob, 1e-12, 1) * np.log(np.clip(prob, 1e-12, 1))).sum(1) / math.log(n)
        acc = H < ABSTAIN_ENTROPY
        out["abstention_production_rule"] = {
            "rule": f"abstain if normalised entropy >= {ABSTAIN_ENTROPY:.4f} (fitted for the deployed model; not refitted)",
            "accepted": int(acc.sum()), "abstained": int((~acc).sum()),
            "accuracy_on_accepted": float((pred[acc] == y_true[acc]).mean()) if acc.any() else None}
    return out


# ------------------------------------------------------------------------------------------------------------- training
def software():
    import platform
    import torch
    import torchvision
    return {"python": platform.python_version(), "torch": torch.__version__, "torchvision": torchvision.__version__,
            "numpy": np.__version__, "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "platform": platform.platform()}


def new_model(torch, tv, pretrained=True):
    m = tv.models.resnet50(weights=tv.models.ResNet50_Weights.IMAGENET1K_V2 if pretrained else None)
    m.fc = torch.nn.Linear(m.fc.in_features, len(CLASSES))
    return m


def predict(torch, model, X, device, bs=64):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(X), bs):
            xb = torch.from_numpy(np.ascontiguousarray(X[i:i + bs])).to(device).permute(0, 3, 1, 2).float() / 255.0
            out.append(torch.softmax(model(norm(torch, xb, device)).float(), 1).cpu().numpy())   # fp32 inference
    return np.concatenate(out)


def free_disk_gb(path="/kaggle/working"):
    p = path if os.path.exists(path) else "."
    return round(shutil.disk_usage(p).free / 1e9, 1)


def gpu_status(torch):
    if not torch.cuda.is_available():
        return {"gpu": None}
    free, total = torch.cuda.mem_get_info()
    return {"gpu": torch.cuda.get_device_name(0), "mem_free_mb": free // 2**20, "mem_total_mb": total // 2**20,
            "peak_alloc_mb": torch.cuda.max_memory_allocated() // 2**20}


def train_run(cfg: ExpConfig, seed: int, train, val, out_dir, log=print):
    """Train one (experiment, seed). Resumable: per-epoch state in <out>/state.pt; a finished run (result.json) is skipped.
    train/val: dicts with X, y (val also meta). Returns the result dict (validation only)."""
    import torch
    import torchvision as tv
    out = Path(out_dir) / f"{cfg.name}_s{seed}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "result.json").is_file():
        log(f"[{cfg.name} s{seed}] already finished - skipped")
        return json.loads((out / "result.json").read_text(encoding="utf-8"))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    Xtr, ytr, Xva, yva = train["X"], train["y"], val["X"], val["y"]
    counts = class_counts(ytr)
    if (ytr == PARTIAL_CARIES).any() and (cfg.loss != "ce" or cfg.sampler != "none"):
        raise ValueError("partial caries labels are only supported with plain (weighted) cross-entropy and no sampler")
    w = class_weights(counts, cfg.weights, beta=cfg.beta)
    cw = torch.tensor(w, dtype=torch.float32, device=device) if w is not None else None
    torch.manual_seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)
    gen = torch.Generator().manual_seed(seed)
    model = new_model(torch, tv).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, cfg.epochs))
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    start, best, best_ep, best_state, hist = 1, -1.0, 0, None, []
    st = out / "state.pt"
    if st.is_file():
        s = torch.load(st, map_location=device, weights_only=False)
        model.load_state_dict(s["model"])
        opt.load_state_dict(s["opt"])
        sched.load_state_dict(s["sched"])
        scaler.load_state_dict(s["scaler"])
        rng.bit_generator.state = s["rng"]
        gen.set_state(s["gen"])
        torch.set_rng_state(s["torch_rng"])
        start, best, best_ep, best_state, hist = s["epoch"] + 1, s["best"], s["best_ep"], s["best_state"], s["hist"]
        log(f"[{cfg.name} s{seed}] resumed after epoch {s['epoch']}")
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    for ep in range(start, cfg.epochs + 1):
        model.train()
        idx = sampler_indices(ytr, rng) if cfg.sampler == "sqrt_inverse" else rng.permutation(len(ytr))
        tot, seen = 0.0, 0
        for i in range(0, len(idx), cfg.batch_size):
            b = idx[i:i + cfg.batch_size]
            if len(b) < 2:
                continue
            xb = augment(torch, torch.from_numpy(Xtr[b]).to(device), gen, cfg, device)
            yb = torch.from_numpy(ytr[b]).to(device)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                lo = model(norm(torch, xb, device))
            lo = lo.float()
            loss = focal_loss(torch, lo, yb, cfg.gamma, cw) if cfg.loss == "focal" else ce_partial(torch, lo, yb, cw)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            tot += float(loss.detach()) * len(b)
            seen += len(b)
        sched.step()
        prob = predict(torch, model, Xva, device)
        rep = report(yva, prob.argmax(1), prob)
        h = {"epoch": ep, "train_loss": tot / max(1, seen), "val_nll": rep["nll"], "val_macro_f1": rep["macro_f1"],
             "val_acc": rep["accuracy"], "val_dc_recall": rep["per_class"]["Deep Caries"]["recall"],
             "val_pl_recall": rep["per_class"]["Periapical Lesion"]["recall"], "sec": round(time.time() - t0, 1)}
        hist.append(h)
        if rep["macro_f1"] > best:
            best, best_ep, best_state = rep["macro_f1"], ep, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(), "scaler": scaler.state_dict(),
                    "rng": rng.bit_generator.state, "gen": gen.get_state(), "torch_rng": torch.get_rng_state(), "epoch": ep,
                    "best": best, "best_ep": best_ep, "best_state": best_state, "hist": hist}, st.with_suffix(".tmp"))
        os.replace(st.with_suffix(".tmp"), st)
        log(f"  [{cfg.name} s{seed}] ep{ep:02d} loss {h['train_loss']:.3f} valF1 {h['val_macro_f1']:.3f} DCrec {h['val_dc_recall']:.2f} "
            f"PLrec {h['val_pl_recall']:.2f} ({h['sec']}s)")
    model.load_state_dict(best_state)
    prob = predict(torch, model, Xva, device)
    ck = out / "best.pth"
    torch.save(best_state, ck)
    sha = sha256_file(ck)
    res = {"experiment": cfg.name, "seed": seed, "config": asdict(cfg), "train_counts": dict(zip(CLASSES, counts.tolist())),
           "train_partial_caries": int((ytr == PARTIAL_CARIES).sum()),
           "class_weights": dict(zip(CLASSES, [round(float(v), 4) for v in w])) if w is not None else None,
           "sampler_exposure": sampler_exposure(ytr) if cfg.sampler != "none" else None,
           "best_epoch": best_ep, "val_gt": report(yva, prob.argmax(1), prob), "history": hist,
           "checkpoint": str(ck), "checkpoint_sha256": sha, "gpu": gpu_status(torch), "software": software(),
           "split_note": "fit on combined_train; epoch selection on combined_validation (= project val); test not used"}
    np.save(out / "val_prob.npy", prob)
    sidecar = {"task": "classification", "architecture": "resnet50", "version": f"kaggle_{cfg.name}_s{seed}", "dental_specific": True,
               "candidate": True, "promoted": False, "class_names": CLASSES, "num_classes": len(CLASSES), "image_size": CROP_SIZE,
               "crop_pad": CROP_PAD, "normalize": {"mean": list(MEAN), "std": list(STD)}, "label_source": "category_id_3 (DENTEX disease)",
               "class_counts_train": res["train_counts"], "class_weights": res["class_weights"], "pretrained": "torchvision IMAGENET1K_V2",
               "training_config": asdict(cfg), "seed": seed, "software": res["software"], "checkpoint_sha256": sha[:16],
               "checkpoint_sha256_full": sha, "measured_on": "validation split (best epoch by macro-F1)",
               "metrics": {"classification": {k: res["val_gt"][k] for k in ("macro_f1", "accuracy", "per_class")}},
               "trained_by": "kaggle/denta_mind_training.ipynb",
               "limitations": ["Candidate only: not validated for clinical use and not promoted.",
                               "Trained only on teeth DENTEX labelled with one of four findings; there is no healthy class."]}
    ck.with_suffix(".json").write_text(json.dumps(sidecar, indent=1), encoding="utf-8")
    (out / "result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    st.unlink(missing_ok=True)
    del model, opt
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return res


def evaluate_checkpoint(ck_path, Xg, y, Xd=None, mi=None, sources=None):
    """GT-box metrics, detector-box metrics on matched findings, end-to-end recall (missed = wrong), per-source metrics."""
    import torch
    import torchvision as tv
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = new_model(torch, tv, pretrained=False)
    model.load_state_dict(torch.load(ck_path, map_location="cpu", weights_only=True), strict=True)
    model.to(device)
    pg = predict(torch, model, Xg, device)
    out = {"gt": report(y, pg.argmax(1), pg)}
    if Xd is not None and len(Xd):
        pd = predict(torch, model, Xd, device)
        out["det_matched"] = report(y[mi], pd.argmax(1), pd)
        e2e = np.full(len(y), -1)
        e2e[mi] = pd.argmax(1)
        out["end_to_end"] = {"accuracy": float((e2e == y).mean()),
                             "recall": {c: float(((e2e == k) & (y == k)).sum() / max(1, (y == k).sum())) for k, c in enumerate(CLASSES)},
                             "unmatched_findings": int(len(y) - len(mi))}
    if sources is not None:
        src = np.asarray(sources)
        out["by_source"] = {s: report(y[src == s], pg.argmax(1)[src == s]) for s in sorted(set(sources))}
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return out


# --------------------------------------------------------------------------------------------------------- acceptance
def _mean(xs):
    return float(np.mean(xs)) if xs else float("nan")


def acceptance(cand: dict, base: dict, setting="det_matched"):
    """cand/base: {seed: evaluate_checkpoint(...) on validation}. Applies ACCEPT (pre-registered). Returns dict with pass flags."""
    seeds = sorted(set(cand) & set(base))
    if len(seeds) < ACCEPT["seed_pairs_min"]:
        return {"pass": False, "reason": f"only {len(seeds)} paired seeds"}
    s = setting if all(setting in cand[k] for k in seeds) else "gt"
    f = lambda d, k: d[k][s]["macro_f1"]  # noqa: E731
    diffs = [f(cand, k) - f(base, k) for k in seeds]
    cross = sum(f(cand, a) > f(base, b) for a in cand for b in base)
    pc = lambda d, c, m: _mean([d[k][s]["per_class"][c][m] for k in seeds])  # noqa: E731
    c1 = sum(d > 0 for d in diffs) >= ACCEPT["seed_pairs_min"] and _mean(diffs) > ACCEPT["gain_min"] and cross >= ACCEPT["cross_pairs_min"]
    c2 = all(pc(cand, c, "recall") >= pc(base, c, "recall") for c in MINORITY)
    c3 = all(pc(cand, c, "f1") >= pc(base, c, "f1") - ACCEPT["class_f1_drop_max"] for c in CLASSES)
    gt = lambda d: _mean([d[k]["gt"]["macro_f1"] for k in seeds])  # noqa: E731
    c4 = gt(cand) >= gt(base) - ACCEPT["gt_macro_f1_drop_max"]
    c5 = all(pc(cand, c, "precision") >= pc(base, c, "precision") - ACCEPT["minority_precision_drop_max"] for c in MINORITY)
    return {"setting": s, "seeds": seeds, "mean_gain_macro_f1": _mean(diffs), "seed_pairs_better": int(sum(d > 0 for d in diffs)),
            "cross_pairs_better": int(cross), "cross_pairs_total": len(cand) * len(base),
            "minority_recall_delta": {c: pc(cand, c, "recall") - pc(base, c, "recall") for c in MINORITY},
            "minority_precision_delta": {c: pc(cand, c, "precision") - pc(base, c, "precision") for c in MINORITY},
            "class_f1_delta": {c: pc(cand, c, "f1") - pc(base, c, "f1") for c in CLASSES},
            "gt_macro_f1_delta": gt(cand) - gt(base),
            "criteria": {"1_macro_f1_gain": bool(c1), "2_minority_recall_not_lower": bool(c2), "3_no_class_f1_drop_gt_0.05": bool(c3),
                         "4_gt_macro_f1_drop_le_0.02": bool(c4), "5_minority_precision_drop_le_0.10": bool(c5)},
            "pass": bool(c1 and c2 and c3 and c4 and c5)}


def file_hashes(paths):
    return {str(p): sha256_file(p) for p in paths if Path(p).is_file()}


def short_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]



# -------------------------------------------------------------------------------------------- process-isolated training
def save_arrays(path, data):
    """Write a {"X", "y"} split once, for the training subprocesses (np.savez, uncompressed)."""
    if not Path(path).is_file():
        np.savez(path, X=data["X"], y=data["y"])
    return str(path)


def train_run_isolated(cfg: ExpConfig, seed: int, train_npz, val_npz, out_dir, log=print, attempts=3, timeout_s=3 * 3600):
    """Run ``train_run`` in a fresh Python process. A CUDA fault (e.g. 'illegal memory access') poisons the whole process's GPU
    context, so isolating every run keeps one fault from killing the remaining experiments. A failed attempt is retried and
    resumes from its last completed epoch (state.pt). Returns the result dict, or {"failed": True, ...} after ``attempts``."""
    import subprocess
    out = Path(out_dir) / f"{cfg.name}_s{seed}"
    if (out / "result.json").is_file():
        log(f"[{cfg.name} s{seed}] already finished - skipped")
        return json.loads((out / "result.json").read_text(encoding="utf-8"))
    spec = json.dumps({"cfg": asdict(cfg), "seed": seed, "train": str(train_npz), "val": str(val_npz), "out": str(out_dir)})
    errors = []
    for attempt in range(1, attempts + 1):
        p = subprocess.Popen([sys.executable, "-u", str(Path(__file__).resolve()), "--worker", spec],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        tail = []
        try:
            for line in p.stdout:
                line = line.rstrip()
                tail = (tail + [line])[-40:]
                if line.startswith("  [") or "resumed" in line or "Error" in line:
                    log(line)
            rc = p.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            p.kill()
            rc = "timeout"
        if rc == 0 and (out / "result.json").is_file():
            if attempt > 1:
                log(f"[{cfg.name} s{seed}] succeeded on attempt {attempt}")
            return json.loads((out / "result.json").read_text(encoding="utf-8"))
        errors.append({"attempt": attempt, "returncode": rc, "tail": tail[-15:]})
        log(f"[{cfg.name} s{seed}] attempt {attempt} FAILED (rc={rc}): " + " | ".join(tail[-4:]))
    out.mkdir(parents=True, exist_ok=True)
    (out / "failure.json").write_text(json.dumps(errors, indent=1), encoding="utf-8")
    return {"failed": True, "experiment": cfg.name, "seed": seed, "errors": errors}


def _worker(spec_json):
    spec = json.loads(spec_json)
    cfg = ExpConfig(**spec["cfg"])
    load = lambda f: (lambda z: {"X": z["X"], "y": z["y"]})(np.load(f))  # noqa: E731
    train_run(cfg, spec["seed"], load(spec["train"]), load(spec["val"]), spec["out"], log=print)


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--worker":
    _worker(sys.argv[2])
