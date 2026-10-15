#!/usr/bin/env python
"""Build the TRAINING-split crop bank for the crop-robustness experiment (Candidate B). Training data only.

Pass 1: run the production detector on every training radiograph of the findings sub-set and collect, for each ground-truth
        finding box matched at IoU >= 0.5, the joint edge-offset vector (dx1/w, dy1/h, dx2/w, dy2/h).
Pass 2: for every training finding crop (same order as runtime/ml_cache/crops_train_224 used by ml_cls_train.py) write
        variant 0 = the exact ground-truth box crop (verified byte-identical to the cache) and variants 1..K = boxes jittered by a
        resampled offset vector scaled by U(0.75, 1.25), accepted only if IoU(jittered, original) >= 0.6 (else the exact box).
Crops use the production crop_region (pad 0.10, 224 px, bilinear). Labels are never changed.

    python scripts/ml_crop_bank.py            # -> runtime/ml_cache/cropbank_train_224_k8.npy (+ .json), visual grid in docs/
"""
import _bootstrap  # noqa: F401
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from dentexmodel.config import get_settings
from dentexmodel.data.coco import annotation_finding
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.preprocess import load_gray
from dentexmodel.data.splits import load_split_file
from dentexmodel.inference import torch_models as TM
from dentexmodel.training import trainers as T
from dentexmodel.utils.geometry import box_iou
from ml_common import CLASSES, load_split_crops

CACHE = Path("runtime/ml_cache")
EVID = Path("docs/audit_evidence/ml_improvement/crop_robustness")
SCALE = (0.75, 1.25)
MIN_IOU = 0.6
MAX_TRIES = 10


def train_items(s):
    """Identical selection and order to ml_common.load_split_crops('train')."""
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == T.TASK_LEVEL["classification"] and assign.get(r.image_id) == "train"]
    return T._annotations_for(s, svc, rows)


def finding_boxes(anns, cats):
    out = []
    for a in anns:
        lab = annotation_finding(a, cats) if "category_id_3" in a else None
        if lab is None or not a.get("bbox"):
            continue
        x, y, w, h = a["bbox"]
        out.append((lab, [float(x), float(y), float(x + w), float(y + h)]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    s = get_settings()
    out = CACHE / f"cropbank_train_224_k{a.k}.npy"
    if out.exists():
        print("crop bank exists, not overwriting:", out)
        return 2
    items = train_items(s)
    cached = load_split_crops("train")
    t0 = time.time()
    # ---------------- pass 1: detector-vs-ground-truth offsets on the TRAINING split
    offsets = []
    for row, anns, cats in items:
        gt = finding_boxes(anns, cats)
        if not gt:
            continue
        rgb01 = np.repeat(load_gray(s.data_root / row.file_path)[..., None], 3, axis=2)
        dets = [d.box for d in TM.detect_teeth(rgb01, row.image_id, s).detections]
        for _, g in gt:
            best = max(((box_iou(g, d), d) for d in dets), default=(0.0, None))
            if best[1] is not None and best[0] >= 0.5:
                d, w, h = best[1], g[2] - g[0], g[3] - g[1]
                offsets.append([(d[0] - g[0]) / w, (d[1] - g[1]) / h, (d[2] - g[2]) / w, (d[3] - g[3]) / h])
    offsets = np.asarray(offsets, dtype=np.float64)
    t1 = time.time()
    print(f"pass 1: {len(offsets)} offset vectors from training radiographs ({t1 - t0:.0f}s)", flush=True)
    # ---------------- pass 2: crop bank
    rng = np.random.default_rng(a.seed)
    N = len(cached["y"])
    bank = np.lib.format.open_memmap(out.with_suffix(".partial.npy"), mode="w+", dtype=np.uint8, shape=(N, a.k + 1, 224, 224, 3))
    boxes_rec, ious, fallbacks, n = [], [], 0, 0
    for row, anns, cats in items:
        img = np.asarray(Image.open(s.data_root / row.file_path).convert("RGB"))
        for lab, g in finding_boxes(anns, cats):
            c0 = T.crop_region(img, g, 224)
            if c0 is None:
                continue
            if not np.array_equal(c0, cached["X"][n]) or CLASSES[cached["y"][n]] != lab:
                raise SystemExit(f"order/content mismatch with the training crop cache at index {n} ({row.image_id})")
            bank[n, 0] = c0
            w, h = g[2] - g[0], g[3] - g[1]
            rec = [g]
            for v in range(1, a.k + 1):
                for _ in range(MAX_TRIES):
                    o = offsets[rng.integers(len(offsets))] * rng.uniform(*SCALE)
                    b = [g[0] + o[0] * w, g[1] + o[1] * h, g[2] + o[2] * w, g[3] + o[3] * h]
                    if b[2] - b[0] > 4 and b[3] - b[1] > 4 and box_iou(b, g) >= MIN_IOU:
                        break
                else:
                    b = g
                    fallbacks += 1
                c = T.crop_region(img, b, 224)
                if c is None:
                    c, b = c0, g
                    fallbacks += 1
                bank[n, v] = c
                ious.append(box_iou(b, g))
                rec.append([round(x, 1) for x in b])
            boxes_rec.append({"index": n, "image_id": row.image_id, "label": lab, "boxes": rec})
            n += 1
    if n != N:
        raise SystemExit(f"crop count {n} != cache {N}")
    bank.flush()
    del bank
    out.with_suffix(".partial.npy").replace(out)
    meta = {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "split": "train", "n_crops": N, "k_jittered": a.k, "seed": a.seed,
            "variant_0": "exact ground-truth box (byte-identical to crops_train_224.npz)",
            "jitter": {"source": "joint edge-offset vectors of production-detector boxes vs ground-truth finding boxes on TRAINING radiographs (IoU >= 0.5)",
                       "n_offset_vectors": len(offsets), "offsets_sha256": hashlib.sha256(offsets.tobytes()).hexdigest(),
                       "scale": SCALE, "min_iou_to_original": MIN_IOU, "max_tries": MAX_TRIES},
            "accepted_iou_to_original": {k: round(float(x), 4) for k, x in zip(("min", "p5", "p50", "p95"), np.percentile(ious, [0, 5, 50, 95]))},
            "fallbacks_to_exact_box": fallbacks, "crop": "trainers.crop_region pad 0.10, 224x224 bilinear", "duration_s": round(time.time() - t0, 1),
            "bank_file": out.name}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "cropbank_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (EVID / "cropbank_boxes.json").write_text(json.dumps(boxes_rec), encoding="utf-8")
    np.save(EVID / "train_offset_vectors.npy", offsets)
    # ---------------- visual grid: 3 Caries, 3 Impacted, 5 Deep Caries, 5 Periapical Lesion (seeded pick)
    bank = np.load(out, mmap_mode="r")
    y = cached["y"]
    pick = []
    for c, k in ((0, 3), (2, 3), (1, 5), (3, 5)):
        pick += sorted(np.random.default_rng(7).choice(np.where(y == c)[0], k, replace=False).tolist())
    S, L = 128, 14
    sheet = Image.new("RGB", (S * (a.k + 1), (S + L) * len(pick)), "white")
    d = ImageDraw.Draw(sheet)
    for r, i in enumerate(pick):
        for v in range(a.k + 1):
            sheet.paste(Image.fromarray(np.asarray(bank[i, v])).resize((S, S)), (v * S, r * (S + L)))
        d.text((2, r * (S + L) + S), f"{CLASSES[y[i]]} - {boxes_rec[i]['image_id']} #{i}  (col 1 = exact GT box, cols 2-{a.k + 1} jittered)", fill="black")
    sheet.save(EVID / "jitter_grid.png")
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
