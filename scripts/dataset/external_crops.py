"""Build tooth crops from external panoramic datasets, following reports/external_data_protocol.md (pre-registered 2026-10-24).

    .venv\\Scripts\\python.exe scripts\\dataset\\external_crops.py hanoi
    .venv\\Scripts\\python.exe scripts\\dataset\\external_crops.py cluj

Lesion boxes (Hanoi PAI 3-5, Cluj API / CAR) are assigned to the production tooth detector's box with the highest
coverage = area(L ∩ T+) / area(L), T+ = tooth box padded 10 % per side; kept only if coverage >= 0.5. Cluj IMT boxes are tooth
boxes and are cropped directly. Crops use the production crop rule (pad 10 %, 224 px). Detections are cached (resumable).

Outputs (Data/external_crops/<source>/): crops.npz (X uint8 N x 224 x 224 x 3, y int64; y = 4 means partial label
{Caries, Deep Caries}), manifest.csv (one row per crop, with provenance and the mapping evidence), mapping_stats.json,
check_grid_<class>.png (visual check: 48 random crops per class).
"""
from __future__ import annotations

import json
import random
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import os

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from dsutil import CLASSES, CROP_PAD, CROP_SIZE, crop_region, read_csv, sha256_file, write_csv  # noqa: E402

PARTIAL_CARIES = 4                       # label index for {Caries, Deep Caries}
LABEL_NAMES = CLASSES + ["Caries|Deep Caries"]
# paths can be overridden so the same code runs on Kaggle (no repository there)
DET_CKPT = Path(os.environ.get("DM_DET_CKPT", ROOT / "Data/checkpoints/dentex_teeth_detection_v1.pth"))
DET_SCORE, COVER_MIN, TOOTH_PAD = 0.3, 0.5, 0.10
OUT_ROOT = Path(os.environ.get("DM_EXT_OUT", ROOT / "Data/external_crops"))
CLUJ_DIR = Path(os.environ.get("DM_CLUJ_DIR", ROOT / "Data/raw/external/zenodo_cluj_15487430/extracted"))
DATA_DIR = Path(os.environ.get("DM_DATA_DIR", ROOT / "Data"))
CLUJ_MAP = {7: ("lesion", 3), 6: ("tooth", 2), 4: ("lesion", PARTIAL_CARIES)}   # API -> PL, IMT -> Impacted, CAR -> partial


# ------------------------------------------------------------------------------------------------------------- detector
class Detector:
    def __init__(self, cache: Path):
        import torch
        import torchvision as tv
        self.torch = torch
        self.dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # identical to dentexmodel.training.trainers.build_detector(..., "fasterrcnn_resnet50_fpn", 2, pretrained=False)
        m = tv.models.detection.fasterrcnn_resnet50_fpn(weights=None, weights_backbone=None, num_classes=2)
        m.load_state_dict(torch.load(DET_CKPT, map_location="cpu", weights_only=True), strict=True)
        self.model = m.to(self.dev).eval()
        self.cache_path = cache
        self.cache = {}
        if cache.is_file():
            for line in cache.read_text(encoding="utf-8").splitlines():
                d = json.loads(line)
                self.cache[d["key"]] = d["boxes"]

    def boxes(self, key: str, img_u8: np.ndarray) -> list:
        if key in self.cache:
            return self.cache[key]
        t = self.torch
        x = t.from_numpy(np.ascontiguousarray(img_u8.transpose(2, 0, 1))).float().div(255).to(self.dev)
        with t.no_grad(), t.autocast(device_type=self.dev.type, enabled=self.dev.type == "cuda"):      # as production
            o = self.model([x])[0]
        b = [[round(float(v), 1) for v in bb] + [round(float(s), 4)]
             for bb, s in zip(o["boxes"].float().cpu().tolist(), o["scores"].float().cpu().tolist()) if s >= DET_SCORE]
        self.cache[key] = b
        with self.cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "boxes": b}) + "\n")
        return b


def coverage(lesion, tooth):
    w, h = tooth[2] - tooth[0], tooth[3] - tooth[1]
    tp = [tooth[0] - TOOTH_PAD * w, tooth[1] - TOOTH_PAD * h, tooth[2] + TOOTH_PAD * w, tooth[3] + TOOTH_PAD * h]
    ix = max(0.0, min(lesion[2], tp[2]) - max(lesion[0], tp[0]))
    iy = max(0.0, min(lesion[3], tp[3]) - max(lesion[1], tp[1]))
    la = max(1e-6, (lesion[2] - lesion[0]) * (lesion[3] - lesion[1]))
    return ix * iy / la


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


# ------------------------------------------------------------------------------------------------------------- sources
def hanoi_items():
    """One item per unique Hanoi radiograph (duplicates already grouped in the annotation pool)."""
    ann = ROOT / "Data/raw/external/hanoi_periapical/annots/Image Annots"
    for r in read_csv(ROOT / "Data/annotation/annotation_pool.csv"):
        if r["source_dataset"] != "hanoi_periapical":
            continue
        stem = Path(r["image_path"]).stem
        f = ann / f"{stem}.xml"
        if not f.is_file():
            continue
        labels = []
        for o in ET.parse(f).getroot().findall("object"):
            b = o.find("bndbox")
            labels.append(("lesion", 3, [float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax")], f"PAI {o.findtext('name')}"))
        yield {"key": r["image_id"], "path": ROOT / "Data" / r["image_path"], "rel": r["image_path"], "sha": r["image_sha256"],
               "group": r["radiograph_group"], "role": "train", "subset": "hanoi", "labels": labels}


def cluj_items():
    """Cluj YOLO folders. Folder role is decided by the folder name (protocol section 3): test / external -> eval only."""
    from PIL import Image
    imgs = [p for p in CLUJ_DIR.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    for p in sorted(imgs):
        rel_parts = [s.lower() for s in p.relative_to(CLUJ_DIR).parts[:-1]]
        known = [s for s in rel_parts if s in ("train", "valid", "val", "test")]
        # only folders clearly named train/valid/val are trained on; anything else (test, external, unrecognised) is
        # evaluation-only, so an unexpected archive layout can never leak evaluation images into training
        subset = known[0] if known else "/".join(s for s in rel_parts if s not in ("images", "labels")) or "root"
        role = "train" if subset in ("train", "valid", "val") else "eval"
        lab = p.parent.parent / "labels" / (p.stem + ".txt")
        if not lab.is_file():
            continue
        with Image.open(p) as im:
            W, H = im.size
        labels = []
        for row in lab.read_text().split("\n"):
            v = row.split()
            if len(v) < 5 or int(float(v[0])) not in CLUJ_MAP:
                continue
            c, (cx, cy, w, h) = int(float(v[0])), map(float, v[1:5])
            kind, target = CLUJ_MAP[c]
            labels.append((kind, target, [(cx - w / 2) * W, (cy - h / 2) * H, (cx + w / 2) * W, (cy + h / 2) * H], ["API", "IMT", "CAR"][[7, 6, 4].index(c)]))
        yield {"key": "cluj_" + "_".join(p.relative_to(CLUJ_DIR).with_suffix("").parts), "path": p,
               "rel": "cluj/" + p.relative_to(CLUJ_DIR).as_posix(), "sha": None, "group": None, "role": role,
               "subset": subset, "labels": labels}


# ------------------------------------------------------------------------------------------------------------- main
def build(source: str):
    from PIL import Image
    out = OUT_ROOT / source
    out.mkdir(parents=True, exist_ok=True)
    det = Detector(out / "detections.jsonl")
    items = list(hanoi_items() if source == "hanoi" else cluj_items())
    X, rows, stats = [], [], Counter()
    for n, it in enumerate(items, 1):
        if not it["labels"]:
            stats["images_without_target_labels"] += 1
            continue
        img = np.asarray(Image.open(it["path"]).convert("RGB"))
        sha = it["sha"] or sha256_file(it["path"])
        teeth = None
        done = set()
        for kind, target, box, src_label in it["labels"]:
            stats[f"labels_{LABEL_NAMES[target]}"] += 1
            if kind == "tooth":
                crop_box, cov, tooth_i = box, None, None
            else:
                teeth = teeth if teeth is not None else det.boxes(it["key"], img)
                scored = sorted(((coverage(box, t[:4]), iou(box, t[:4]), i) for i, t in enumerate(teeth)), reverse=True)
                if not scored or scored[0][0] < COVER_MIN:
                    stats[f"dropped_no_tooth_{LABEL_NAMES[target]}"] += 1
                    continue
                cov, _, tooth_i = scored[0]
                crop_box = teeth[tooth_i][:4]
                if (tooth_i, target) in done:          # several lesions of one class on one tooth -> one sample
                    stats[f"merged_same_tooth_{LABEL_NAMES[target]}"] += 1
                    continue
                done.add((tooth_i, target))
            c = crop_region(img, crop_box, CROP_SIZE, CROP_PAD)
            if c is None:
                stats["dropped_degenerate_crop"] += 1
                continue
            X.append(c)
            rows.append({"sample_id": f"{it['key']}#{len(rows)}", "source_dataset": source, "subset": it["subset"], "role": it["role"],
                         "image_path": it["rel"], "image_sha256": sha, "radiograph_group": it["group"] or f"{source}:{sha[:16]}",
                         "source_label": src_label, "class_index": target, "class_name": LABEL_NAMES[target],
                         "crop_box_xyxy": json.dumps([round(v, 1) for v in crop_box]), "lesion_box_xyxy": json.dumps([round(v, 1) for v in box]),
                         "coverage": round(cov, 3) if cov is not None else "", "box_rule": "tooth label box" if kind == "tooth" else "detector tooth box"})
        if n % 200 == 0:
            print(f"{source}: {n}/{len(items)} radiographs, {len(rows)} crops", flush=True)
    X = np.stack(X) if X else np.zeros((0, CROP_SIZE, CROP_SIZE, 3), np.uint8)
    y = np.array([r["class_index"] for r in rows], np.int64)
    np.savez_compressed(out / "crops.npz", X=X, y=y)
    write_csv(out / "manifest.csv", rows)
    stats.update({f"crops_{LABEL_NAMES[k]}_{role}": v for (k, role), v in Counter((r["class_index"], r["role"]) for r in rows).items()})
    stats["radiographs"] = len(items)
    (out / "mapping_stats.json").write_text(json.dumps(dict(sorted(stats.items())), indent=1), encoding="utf-8")
    check_grids(out, X, rows)
    print(json.dumps(dict(sorted(stats.items())), indent=1))


def check_grids(out, X, rows, n=48, seed=42):
    """Visual check (protocol section 2): 48 random crops per class, with the lesion box drawn in crop coordinates."""
    from PIL import Image, ImageDraw
    by = defaultdict(list)
    for i, r in enumerate(rows):
        by[r["class_name"]].append(i)
    rng = random.Random(seed)
    for cname, idx in by.items():
        pick = rng.sample(idx, min(n, len(idx)))
        cols = 8
        grid = Image.new("RGB", (cols * 228, ((len(pick) + cols - 1) // cols) * 228), "white")
        for k, i in enumerate(pick):
            im = Image.fromarray(X[i])
            r = rows[i]
            cb, lb = json.loads(r["crop_box_xyxy"]), json.loads(r["lesion_box_xyxy"])
            w, h = cb[2] - cb[0], cb[3] - cb[1]
            x0, y0, sx, sy = cb[0] - CROP_PAD * w, cb[1] - CROP_PAD * h, CROP_SIZE / ((1 + 2 * CROP_PAD) * w), CROP_SIZE / ((1 + 2 * CROP_PAD) * h)
            if r["box_rule"] != "tooth label box":
                ImageDraw.Draw(im).rectangle([(lb[0] - x0) * sx, (lb[1] - y0) * sy, (lb[2] - x0) * sx, (lb[3] - y0) * sy], outline=(255, 0, 0), width=2)
            grid.paste(im, ((k % cols) * 228, (k // cols) * 228))
        grid.save(out / f"check_grid_{cname.replace('|', '_or_').replace(' ', '_')}.png")


if __name__ == "__main__":
    build(sys.argv[1])
