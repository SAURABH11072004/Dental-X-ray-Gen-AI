"""Grouped 5-fold cross-validation of the BASE finding classifier. Protocol: reports/cv5_protocol.md (pre-registered 2026-10-24).

Reuses kaggle/dentamind_kaggle.py (crops, BASE recipe, isolated training, prediction, metrics) and scripts/dataset/make_cv_folds.py
(group assignment). This module only adds: fold/leakage gates, the per-fold plan (fit / inner-validation / held-out), a detector that
reproduces the production inference path, out-of-fold aggregation, a radiograph-level bootstrap and the Caries vs Deep Caries analysis.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for p in (HERE, HERE.parent / "scripts" / "dataset"):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))
import dentamind_kaggle as DK  # noqa: E402
import make_cv_folds as MCF  # noqa: E402
from dsutil import CLASSES  # noqa: E402

FOLD_FILE_SHA256 = "9b767a4822844ccf0c4bf33d299e6e37420d1458a38035af0c3a3cb9107b47a6"   # protocol section 2
K = 5
SEEDS = [42, 43, 44, 45, 46]
INNER_K = 8
PRIMARY = "dentex_train_disease"
SECONDARY = "dentex_official_val"
POOL_SPLITS = ("train", "validation")
EXCLUDED_SPLITS = ("calibration", "test")
BOOT_N, BOOT_SEED = 2000, 0
DET_IOU_MEDIAN_MIN = 0.98


class CVError(RuntimeError):
    pass


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run_name(fold: int) -> str:
    return f"CV5_BASE_f{fold}"


def fold_config(fold: int) -> DK.ExpConfig:
    """The BASE recipe, unchanged except for the run name (protocol section 3)."""
    return dataclasses.replace(DK.EXPERIMENTS["BASE"], name=run_name(fold),
                               note=f"CV5 fold {fold}: BASE recipe (C0r), fit on 4 folds minus inner validation; reports/cv5_protocol.md")


# ------------------------------------------------------------------------------------------------------------- folds (gate 1)
def load_folds(path, expected_sha=FOLD_FILE_SHA256) -> dict:
    """{radiograph_group: fold} from the approved fold file; refuses any other file."""
    got = sha256_file(path)
    if expected_sha and got != expected_sha:
        raise CVError(f"fold file sha256 {got[:16]}... is not the approved {expected_sha[:16]}...")
    fold_of = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            g, f = r["radiograph_group"], int(r["fold"])
            if g in fold_of:
                raise CVError(f"group {g} listed twice in the fold file")
            if not 0 <= f < K:
                raise CVError(f"group {g}: fold {f} outside 0..{K - 1}")
            fold_of[g] = f
    return fold_of


def check_folds(fold_of: dict, rows_by_split: dict) -> dict:
    """Gate 1: every pool group exactly once; no calibration/test group in the pool; no image (SHA-256) in two folds."""
    pool = [r for s in POOL_SPLITS for r in rows_by_split[s]]
    pool_groups = {r["radiograph_group"] for r in pool}
    excluded = {r["radiograph_group"] for s in EXCLUDED_SPLITS for r in rows_by_split.get(s, [])}
    excluded_sha = {r["image_sha256"] for s in EXCLUDED_SPLITS for r in rows_by_split.get(s, [])}
    problems = []
    if set(fold_of) != pool_groups:
        problems.append(f"fold file groups != pool groups (missing {len(pool_groups - set(fold_of))}, extra {len(set(fold_of) - pool_groups)})")
    if set(fold_of) & excluded:
        problems.append(f"{len(set(fold_of) & excluded)} calibration/test groups in the fold file")
    sha_folds = defaultdict(set)
    for r in pool:
        sha_folds[r["image_sha256"]].add(fold_of.get(r["radiograph_group"]))
        if r["image_sha256"] in excluded_sha:
            problems.append(f"pool image {r['image_path']} is byte-identical to a calibration/test image")
    multi = [s for s, f in sha_folds.items() if len(f) > 1]
    if multi:
        problems.append(f"{len(multi)} images in two folds")
    if problems:
        raise CVError("fold gate failed: " + "; ".join(problems[:5]))
    per_fold = defaultdict(Counter)
    for r in pool:
        per_fold[fold_of[r["radiograph_group"]]][(r["source_dataset"], r["target_class"])] += 1
    return {"pool_groups": len(pool_groups), "pool_findings": len(pool), "excluded_groups_checked": len(excluded),
            "radiographs_per_fold": dict(sorted(Counter(fold_of.values()).items())),
            "findings_per_fold": {f: {f"{s}:{c}": n for (s, c), n in sorted(cnt.items())} for f, cnt in sorted(per_fold.items())}}


# ------------------------------------------------------------------------------------------------------------- plan (gate 2)
def fold_plan(pool_rows: list, fold_of: dict, fold: int) -> dict:
    """Protocol section 3. Returns row lists: fit / inner (BASE data rule: primary source only), heldout (primary), heldout_secondary."""
    heldout = [r for r in pool_rows if fold_of[r["radiograph_group"]] == fold]
    train_side = [r for r in pool_rows if fold_of[r["radiograph_group"]] != fold and r["source_dataset"] == PRIMARY]
    inner_of = MCF.assign_folds(train_side, k=INNER_K, seed=42 + fold, with_impacted=True)
    inner = [r for r in train_side if inner_of[r["radiograph_group"]] == 0]
    fit = [r for r in train_side if inner_of[r["radiograph_group"]] != 0]
    return {"fold": fold, "fit": fit, "inner": inner,
            "heldout": [r for r in heldout if r["source_dataset"] == PRIMARY],
            "heldout_secondary": [r for r in heldout if r["source_dataset"] == SECONDARY]}


def check_plan(plan: dict, fold_of: dict) -> dict:
    """Gate 2: fit, inner and held-out are pairwise disjoint by group and by image; held-out = exactly fold k."""
    k = plan["fold"]
    parts = {n: plan[n] for n in ("fit", "inner", "heldout", "heldout_secondary")}
    g = {n: {r["radiograph_group"] for r in rs} for n, rs in parts.items()}
    s = {n: {r["image_sha256"] for r in rs} for n, rs in parts.items()}
    names = list(parts)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if g[a] & g[b] or s[a] & s[b]:
                raise CVError(f"fold {k}: {a} and {b} share {len(g[a] & g[b])} groups / {len(s[a] & s[b])} images")
    if any(fold_of[x] == k for x in g["fit"] | g["inner"]):
        raise CVError(f"fold {k}: a held-out radiograph is on the training side")
    if any(fold_of[x] != k for x in g["heldout"] | g["heldout_secondary"]):
        raise CVError(f"fold {k}: held-out set contains another fold")
    if {r["source_dataset"] for r in plan["fit"] + plan["inner"]} - {PRIMARY}:
        raise CVError(f"fold {k}: non-BASE source in the fitting data")
    if not plan["fit"] or not plan["inner"] or not plan["heldout"]:
        raise CVError(f"fold {k}: an empty part")
    return {n: {"radiographs": len(g[n]), "findings": len(parts[n]),
                "classes": dict(sorted(Counter(r["target_class"] for r in parts[n]).items()))} for n in names}


# ------------------------------------------------------------------------------------------------------------- detector
def load_gray01(path) -> np.ndarray:
    """Same as dentexmodel.data.preprocess.load_gray (production input of the detector)."""
    from PIL import Image
    with Image.open(path) as im:
        im.load()
        if im.mode in ("I;16", "I;16L", "I;16B", "I"):
            arr = np.asarray(im, dtype=np.float32)
            top = float(arr.max()) or 1.0
            return np.clip(arr / (65535.0 if top > 255 else 255.0), 0, 1).astype(np.float32)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA").convert("L") if im.mode != "LA" else im.convert("L")
        else:
            im = im.convert("L")
        return np.asarray(im, dtype=np.float32) / 255.0


class ProductionDetector:
    """dentexmodel.inference.torch_models._run_detector for dentex_teeth_detection_v1: grayscale replicated to 3 channels, float [0,1],
    autocast on CUDA (inference.mixed_precision default True), score >= DK.DET_SCORE (0.3)."""

    def __init__(self, ckpt, device=None):
        import torch
        import torchvision as tv
        self.torch = torch
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        m = tv.models.detection.fasterrcnn_resnet50_fpn(weights=None, weights_backbone=None, num_classes=2)
        m.load_state_dict(torch.load(ckpt, map_location="cpu", weights_only=True), strict=True)
        self.model = m.to(self.device).eval()

    def boxes(self, path) -> list:
        t = self.torch
        g = load_gray01(path)
        rgb01 = np.repeat(g[..., None], 3, axis=2)
        x = t.from_numpy(np.ascontiguousarray(rgb01.transpose(2, 0, 1))).float().to(self.device)
        with t.no_grad(), t.autocast(device_type=self.device.type, enabled=self.device.type == "cuda"):
            o = self.model([x])[0]
        return [[float(v) for v in b] + [float(s)] for b, s in zip(o["boxes"].float().cpu().tolist(), o["scores"].float().cpu().tolist())
                if s >= DK.DET_SCORE]


def gt_boxes(rows) -> list:
    out = []
    for r in rows:
        x, y, w, h = json.loads(r["bbox_xywh"])
        out.append([x, y, x + w, y + h])
    return out


def compare_detector(rows, new: dict, cached: dict, key=lambda r: r["project_image_id"]) -> dict:
    """Gate 3 statistic: per image, match GT findings to cached and to regenerated boxes (DK.match); the matched finding sets must be
    identical, and corresponding boxes must agree (median IoU)."""
    by_img = defaultdict(list)
    for r in rows:
        by_img[key(r)].append(r)
    same, diff, ious = 0, [], []
    for kk, rs in by_img.items():
        gts = gt_boxes(rs)
        cb = [d[:4] for d in cached.get(kk, []) if d[4] >= DK.DET_SCORE]
        nb = [d[:4] for d in new.get(kk, []) if d[4] >= DK.DET_SCORE]
        mc, mn = DK.match(gts, cb), DK.match(gts, nb)
        if set(mc) == set(mn):
            same += len(rs)
        else:
            diff.append({"image": kk, "only_cached": sorted(set(mc) - set(mn)), "only_new": sorted(set(mn) - set(mc))})
        for i in set(mc) & set(mn):
            ious.append(DK.box_iou(cb[mc[i][0]], nb[mn[i][0]]))
    med = float(np.median(ious)) if ious else 0.0
    return {"images": len(by_img), "findings": len(rows), "findings_same_match": same, "images_with_different_match": diff,
            "median_box_iou": med, "pass": (not diff) and med >= DET_IOU_MEDIAN_MIN}


# ------------------------------------------------------------------------------------------------------------- evaluation
def macro_f1(y, pred, n=len(CLASSES)) -> float:
    """Same definition as DK.report (vectorised for the bootstrap)."""
    cm = np.bincount(np.asarray(y) * n + np.asarray(pred), minlength=n * n).reshape(n, n)
    tp, pp, sup = np.diag(cm), cm.sum(0), cm.sum(1)
    prec = np.divide(tp, pp, out=np.zeros(n), where=pp > 0)
    rec = np.divide(tp, sup, out=np.zeros(n), where=sup > 0)
    return float(np.divide(2 * prec * rec, prec + rec, out=np.zeros(n), where=(prec + rec) > 0).mean())


def check_oof(oof: dict, n_findings: int, seeds=SEEDS) -> None:
    """Gate 5: oof[seed]['gt'] is (N, C) with every row filled exactly once (no NaN), for every seed."""
    for s in seeds:
        if s not in oof:
            raise CVError(f"seed {s}: no out-of-fold predictions")
        p = oof[s]["gt"]
        if p.shape != (n_findings, len(CLASSES)) or np.isnan(p).any():
            raise CVError(f"seed {s}: out-of-fold GT predictions incomplete ({int(np.isnan(p).any(1).sum())} findings missing)")
        if (oof[s]["filled"] != 1).any():
            raise CVError(f"seed {s}: {int((oof[s]['filled'] != 1).sum())} findings predicted 0 or >1 times")


def pooled_reports(y, oof: dict, matched: np.ndarray, seeds=SEEDS, subset=None) -> dict:
    """Per seed: DK.report on pooled out-of-fold predictions; detector setting on matched findings only; end-to-end recall."""
    idx = np.arange(len(y)) if subset is None else np.asarray(subset)
    out = {}
    for s in seeds:
        pg, pdet = oof[s]["gt"][idx], oof[s]["det"][idx]
        m = matched[idx]
        r = {"gt": DK.report(y[idx], pg.argmax(1), pg)}
        if m.any():
            r["det_matched"] = DK.report(y[idx][m], pdet[m].argmax(1), pdet[m])
        e2e = np.where(m, np.nan_to_num(pdet, nan=0).argmax(1), -1)
        r["end_to_end"] = {"accuracy": float((e2e == y[idx]).mean()), "unmatched_findings": int((~m).sum()),
                           "recall": {c: float(((e2e == k) & (y[idx] == k)).sum() / max(1, (y[idx] == k).sum())) for k, c in enumerate(CLASSES)}}
        out[s] = r
    return out


def cluster_bootstrap(y, preds_by_seed: list, groups, valid=None, n_boot=BOOT_N, seed=BOOT_SEED) -> dict:
    """95 % percentile interval of the seed-mean macro-F1, resampling RADIOGRAPHS (all their findings) with replacement.
    valid: boolean mask of findings that count (e.g. detector-matched); invalid findings are dropped after resampling."""
    y = np.asarray(y)
    groups = np.asarray(groups)
    valid = np.ones(len(y), bool) if valid is None else np.asarray(valid)
    uniq = np.unique(groups)
    members = {g: np.flatnonzero(groups == g) for g in uniq}
    rng = np.random.default_rng(seed)
    stats = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        i = np.concatenate([members[g] for g in pick])
        i = i[valid[i]]
        stats[b] = np.mean([macro_f1(y[i], np.asarray(p)[i]) for p in preds_by_seed])
    point = float(np.mean([macro_f1(y[valid], np.asarray(p)[valid]) for p in preds_by_seed]))
    return {"unit": "radiograph", "n_radiographs": int(len(uniq)), "n_boot": n_boot, "seed": seed, "point": point,
            "ci95": [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))], "boot_sd": float(stats.std(ddof=1))}


def mean_sd(values) -> dict:
    v = [float(x) for x in values]
    return {"values": v, "mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0}


def tooth_type(fdi) -> str:
    try:
        d = int(str(fdi)[-1])
    except (TypeError, ValueError):
        return "unknown"
    return {1: "incisor", 2: "incisor", 3: "canine", 4: "premolar", 5: "premolar"}.get(d, "molar" if d in (6, 7, 8) else "unknown")


def caries_confusion(rows, oof: dict, matched: np.ndarray, seeds=SEEDS) -> dict:
    """Exploratory (protocol section 6). For every Caries / Deep Caries finding: how many seeds predicted the other caries class,
    per setting. Returns per-finding records plus summaries by tooth type and box-area quartile. Labels are not judged."""
    C, DC = CLASSES.index("Caries"), CLASSES.index("Deep Caries")
    y = np.array([int(r["class_index"]) for r in rows])
    sel = np.flatnonzero((y == C) | (y == DC))
    other = np.where(y == C, DC, C)
    n_gt = np.zeros(len(y), int)
    n_det = np.zeros(len(y), int)
    for s in seeds:
        n_gt += oof[s]["gt"].argmax(1) == other
        n_det += np.where(matched, np.nan_to_num(oof[s]["det"], nan=0).argmax(1) == other, False)
    area = np.array([np.prod(json.loads(r["bbox_xywh"])[2:]) for r in rows], float)
    q = np.quantile(area[sel], [0.25, 0.5, 0.75])
    quart = np.searchsorted(q, area, side="right") + 1
    recs = []
    for i in sel:
        r = rows[i]
        recs.append({"sample_id": r["sample_id"], "image_path": r["image_path"], "radiograph_group": r["radiograph_group"],
                     "fdi_tooth": r["fdi_tooth"], "tooth_type": tooth_type(r["fdi_tooth"]), "label": r["target_class"],
                     "original_label": r["original_label"], "box_area_px": int(area[i]), "box_area_quartile": int(quart[i]),
                     "detector_matched": bool(matched[i]), "seeds_other_caries_gt": int(n_gt[i]),
                     "seeds_other_caries_det": int(n_det[i]) if matched[i] else ""})
    def summary(key):
        out = {}
        for lab in ("Caries", "Deep Caries"):
            for v in sorted({rr[key] for rr in recs}):
                grp = [rr for rr in recs if rr["label"] == lab and rr[key] == v]
                if grp:
                    out[f"{lab} | {key}={v}"] = {"n": len(grp), "mean_share_of_seeds_other_caries_gt":
                                                 float(np.mean([rr["seeds_other_caries_gt"] for rr in grp]) / len(seeds)),
                                                 "confused_by_all_seeds_gt": sum(rr["seeds_other_caries_gt"] == len(seeds) for rr in grp)}
        return out
    return {"records": recs, "box_area_quartile_edges_px": [float(v) for v in q],
            "by_tooth_type": summary("tooth_type"), "by_box_area_quartile": summary("box_area_quartile"),
            "confused_by_all_seeds_gt": {lab: sum(rr["label"] == lab and rr["seeds_other_caries_gt"] == len(seeds) for rr in recs)
                                         for lab in ("Caries", "Deep Caries")},
            "n": {lab: sum(rr["label"] == lab for rr in recs) for lab in ("Caries", "Deep Caries")}}
