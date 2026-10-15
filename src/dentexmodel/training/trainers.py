"""PyTorch trainers: tooth-crop finding classifier, and torchvision Faster/Mask R-CNN tooth detector/segmenter.

Design rules (all enforced in code, not only documented):

* Each task reads only the DENTEX sub-set whose labels are *complete* for it:
    - classification (finding per tooth)  <- ``quadrant_enumeration_disease`` (category_id_3)
    - detection / segmentation (teeth)    <- ``quadrant_enumeration`` (every tooth is annotated)
  The ``quadrant`` subset holds four huge quadrant polygons per image, which are not teeth, and the disease subset only
  annotates diseased teeth, so neither may be used as tooth ground truth.
* Only the ``train`` split is trained on; ``val`` selects the best epoch. The ``test`` split is refused here
  (``assert_not_test``) and only touched by ``scripts/evaluate_model.py --final-test``.
* Images enter the detectors at full resolution; torchvision's own transform resizes them. Inference does the same
  thing, so train and inference geometry match.
* Every number written to a sidecar was measured in this run on the validation split. Nothing is estimated.
"""
from __future__ import annotations

import copy
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np

from dentexmodel.data.coco import annotation_fdi, annotation_finding, has_polygon, load_coco
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.splits import assert_not_test, load_split_file
from dentexmodel.errors import DatasetUnavailableError, ModelUnavailableError
from dentexmodel.evaluation.metrics import classification_report, detection_map
from dentexmodel.training.config import TrainConfig

try:  # torch is optional for importing this module (tests/inspection), required for training
    import torch
    from torch.utils.data import DataLoader, Dataset as _Dataset
except ImportError:  # pragma: no cover
    torch = None
    DataLoader = None
    _Dataset = object

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
CROP_PAD = 0.10
MASK_STRIDE = 4   # mask IoU is computed on every 4th pixel in each direction (memory); same grid for predictions and ground truth
TASK_LEVEL = {"classification": "quadrant_enumeration_disease", "detection": "quadrant_enumeration",
              "segmentation": "quadrant_enumeration", "numbering": "quadrant_enumeration"}


# --------------------------------------------------------------------------------------------- shared helpers
def _require_torch():
    try:
        import torch as t, torchvision as tv  # type: ignore  # noqa: F401
        return t, tv
    except ImportError as exc:
        raise ModelUnavailableError("PyTorch is not installed.", hint="pip install -r requirements-ml.txt") from exc


def crop_region(img_u8: np.ndarray, box_xyxy, size: int, pad: float = CROP_PAD) -> np.ndarray | None:
    """Square-resized RGB uint8 crop around ``box_xyxy`` with proportional padding. Shared by training and inference."""
    from PIL import Image
    H, W = img_u8.shape[:2]
    x1, y1, x2, y2 = (float(v) for v in box_xyxy)
    w, h = x2 - x1, y2 - y1
    x1, y1, x2, y2 = max(0, x1 - pad * w), max(0, y1 - pad * h), min(W, x2 + pad * w), min(H, y2 + pad * h)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return np.asarray(Image.fromarray(img_u8[int(y1):int(y2), int(x1):int(x2)]).resize((size, size), Image.BILINEAR))


def _collect(settings, cfg: TrainConfig):
    svc = DatasetService(settings)
    if not svc.status().main_available:
        raise DatasetUnavailableError("Main dataset is not available.", hint="Place the dataset in the data directory.")
    level = TASK_LEVEL[cfg.task]
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data and r.annotation_level == level]
    splits = load_split_file(settings.splits_dir / "dentex_splits.json").get("assignments", {})
    train = [r for r in rows if splits.get(r.image_id) == "train"]
    val = [r for r in rows if splits.get(r.image_id) == "val"]
    assert_not_test([r.image_id for r in train + val], splits, "model training")
    if cfg.max_train_images:
        train = train[:cfg.max_train_images]
    if cfg.max_val_images:
        val = val[:cfg.max_val_images]
    if not train:
        raise DatasetUnavailableError(f"No training images with '{level}' annotations were found.", hint="Run scripts/run_pipeline.py --force.")
    return svc, train, val


def _annotations_for(settings, svc, rows):
    """``[(row, [annotation dicts], categories)]`` using the COCO file of the row's own source."""
    out = []
    by_file = {}
    for src in svc.status().sources:
        if src["annotation_file"]:
            c = load_coco(settings.data_root / src["annotation_file"])
            for cid, info in c.images.items():
                by_file[(src["name"], Path(info["file_name"]).name.lower())] = (c, cid)
    for r in rows:
        hit = by_file.get((r.dataset_source, Path(r.file_path).name.lower()))
        if hit:
            c, cid = hit
            out.append((r, c.by_image.get(cid, []), c.categories))
    return out


def dataset_version(settings) -> dict:
    """Identify exactly which manifest and split file a run used."""
    def sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).is_file() else None
    state = {}
    sp = settings.results_dir / "dataset_state.json"
    if sp.is_file():
        state = json.loads(sp.read_text(encoding="utf-8"))
    return {"fingerprint": state.get("fingerprint"), "manifest_sha": sha(settings.processed_dir / "manifest.json"),
            "splits_sha": sha(settings.splits_dir / "dentex_splits.json"), "assignments_sha": assignments_sha(settings.splits_dir / "dentex_splits.json")}


def assignments_sha(path) -> str | None:
    """Hash of the split ASSIGNMENTS only (image id -> split), so re-processing the dataset (which rewrites the file with a new
    'updated' timestamp) does not change it unless an image really moved between splits."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        a = json.loads(p.read_text(encoding="utf-8")).get("assignments", {})
    except (OSError, json.JSONDecodeError):
        return None
    return hashlib.sha256(json.dumps(sorted(a.items())).encode("utf-8")).hexdigest()[:16]


def software_versions(torch_mod=None) -> dict:
    t, tv = _require_torch()
    v = {"python": platform.python_version(), "torch": t.__version__, "torchvision": tv.__version__, "numpy": np.__version__,
         "cuda": t.version.cuda, "platform": platform.platform()}
    if t.cuda.is_available():
        v["gpu"] = t.cuda.get_device_name(0)
    return v


def _check_gpu_memory(torch_mod, device, need_mb: int, cfg: TrainConfig) -> None:
    if device.type != "cuda":
        return
    free, total = torch_mod.cuda.mem_get_info()
    need = cfg.min_free_gpu_mb or need_mb
    if free / 2**20 < need:
        raise ModelUnavailableError(
            f"Only {free / 2**20:.0f} MB of GPU memory is free (about {need} MB needed for {cfg.task}).",
            hint="Close other GPU programs, lower batch_size, or train with device=cpu.", code="gpu_memory")


def _save_checkpoint(ctx, cfg, state_dict, meta_extra: dict, provenance: dict | None = None) -> str | None:
    if ctx.cancelled:       # a cancelled run is incomplete: it must not appear in the registry as a verified dental model
        ctx.log("cancelled: no checkpoint written")
        return None
    t, _ = _require_torch()
    d = ctx.settings.checkpoint_dir
    d.mkdir(parents=True, exist_ok=True)
    stem, i = f"{cfg.experiment_name}_{cfg.task}", 1
    while (d / f"{stem}_v{i}.pth").exists():  # never overwrite an earlier checkpoint
        i += 1
    path = d / f"{stem}_v{i}.pth"
    t.save(state_dict, path)
    meta = {"task": cfg.task, "architecture": cfg.architecture, "version": f"{stem}_v{i}", "dental_specific": True,
            "dataset_version": dataset_version(ctx.settings), "training_config": cfg.to_dict(),
            "software": software_versions(), "trained_by": "dentamind run_training",
            "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16], **meta_extra}
    if provenance is not None:          # image-level record of exactly what was trained on (dentexmodel.training.provenance)
        from dentexmodel.training import provenance as P
        meta["training_manifest"] = P.write(path, provenance)
    path.with_suffix(".json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    return path.relative_to(ctx.settings.checkpoint_dir).as_posix()


def run_training(cfg: TrainConfig, ctx) -> dict:
    t, tv = _require_torch()
    s = ctx.settings
    t.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    device = t.device("cuda" if (cfg.device in ("auto", "cuda") and t.cuda.is_available()) else "cpu")
    if cfg.device == "cuda" and device.type != "cuda":
        raise ModelUnavailableError("device=cuda was requested but CUDA is not available.", hint="Use device=cpu or install a CUDA build of PyTorch.")
    if cfg.task == "numbering":
        cfg.label_mode = "fdi"          # a numbering model predicts the 32 FDI tooth numbers; ordinary tooth boxes are not FDI labels
    ctx.log(f"device={device} task={cfg.task} arch={cfg.architecture} pretrained={cfg.pretrained} label_mode={cfg.label_mode}")
    svc, train_rows, val_rows = _collect(s, cfg)
    train_ann, val_ann = _annotations_for(s, svc, train_rows), _annotations_for(s, svc, val_rows)
    ctx.log(f"train images={len(train_ann)} val images={len(val_ann)} source level={TASK_LEVEL[cfg.task]}")
    try:
        from torch.utils.tensorboard import SummaryWriter  # type: ignore
        writer = SummaryWriter(str(ctx.tb_dir))
        writer.add_text("config", json.dumps(cfg.to_dict()))
    except Exception:  # noqa: BLE001 - tensorboard is optional
        writer = None
    t0 = time.time()
    if cfg.task == "classification":
        _check_gpu_memory(t, device, 1200, cfg)
        result = _train_classifier(cfg, ctx, t, tv, device, writer, train_ann, val_ann)
    else:
        _check_gpu_memory(t, device, 3000, cfg)
        result = _train_detector(cfg, ctx, t, tv, device, writer, train_ann, val_ann)
    result["duration_s"] = round(time.time() - t0, 2)
    if writer:
        writer.close()
    return result


# ------------------------------------------------------------------------------------------------ classification
def _crops(settings, items, size, with_ids: bool = False):
    """uint8 crops (N,size,size,3) and finding names from annotations that carry a finding label (+ the source image id per crop)."""
    from PIL import Image
    X, y, ids = [], [], []
    for row, anns, cats in items:
        try:
            img = np.asarray(Image.open(settings.data_root / row.file_path).convert("RGB"))
        except OSError:
            continue
        for a in anns:
            lab = annotation_finding(a, cats) if "category_id_3" in a else None
            if lab is None or not a.get("bbox"):
                continue
            x, yy, w, h = a["bbox"]
            c = crop_region(img, (x, yy, x + w, yy + h), size)
            if c is not None:
                X.append(c)
                y.append(lab)
                ids.append(row.image_id)
    return (X, y, ids) if with_ids else (X, y)


def _used(items, ids_per_item) -> list:
    """[(row, n_items)] for the rows that contributed at least one training item, in input order."""
    from collections import Counter
    n = Counter(ids_per_item)
    return [(row, n[row.image_id]) for row, _a, _c in items if n[row.image_id]]


def _norm(batch_u8, device, torch_mod):
    x = batch_u8.to(device).permute(0, 3, 1, 2).float() / 255.0
    m = torch_mod.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)
    sd = torch_mod.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
    return (x - m) / sd


def _train_classifier(cfg, ctx, t, tv, device, writer, train_ann, val_ann) -> dict:
    s = ctx.settings
    Xtr, ytr, ids_tr = _crops(s, train_ann, cfg.image_size, with_ids=True)
    Xva, yva, ids_va = _crops(s, val_ann, cfg.image_size, with_ids=True)
    review_prov = []
    extra_info = {"requested": bool(cfg.use_approved_annotations), "added": 0, "skipped": {}}
    if cfg.use_approved_annotations:
        # explicit opt-in only: approved, second-person-reviewed region labels on pool/upload images (never val/test/calibration/labelled-train)
        from PIL import Image
        from dentexmodel.annotation.reviews import ReviewStore
        from dentexmodel.storage import Database
        items, skipped = ReviewStore(Database(s.db_path)).training_items(s)
        known = set(ytr)
        for it in items:
            if it["label"] not in known:
                skipped["unknown_class"] = skipped.get("unknown_class", 0) + 1
                continue
            x1, y1, x2, y2 = it["box"]
            c = crop_region(np.asarray(Image.open(it["path"]).convert("RGB")), (x1, y1, x2, y2), cfg.image_size)
            if c is None:
                skipped["tiny_box"] = skipped.get("tiny_box", 0) + 1
                continue
            Xtr.append(c)
            ytr.append(it["label"])
            extra_info["added"] += 1
            review_prov.append({"review_id": it["review_id"], "label": it["label"], "box": it["box"],
                                "image_sha256": hashlib.sha256(Path(it["path"]).read_bytes()).hexdigest()})
        extra_info["skipped"] = skipped
        ctx.log(f"approved reviews: added {extra_info['added']} crops, skipped {skipped}")
    classes = sorted(set(ytr))
    if not Xtr or len(classes) < 2:
        raise DatasetUnavailableError("Need labelled tooth crops of at least two classes in the training split.")
    idx = {c: i for i, c in enumerate(classes)}
    counts = np.array([ytr.count(c) for c in classes], dtype=float)
    weights = counts.sum() / (len(classes) * counts)   # inverse-frequency class weights (class imbalance)
    ctx.log(f"crops train={len(Xtr)} val={len(Xva)} classes={dict(zip(classes, counts.astype(int).tolist()))}")
    weights_enum = tv.models.ResNet18_Weights.IMAGENET1K_V1 if cfg.architecture == "resnet18" else tv.models.ResNet50_Weights.IMAGENET1K_V2
    model = getattr(tv.models, cfg.architecture)(weights=weights_enum if cfg.pretrained else None)
    model.fc = t.nn.Linear(model.fc.in_features, len(classes))
    model.to(device)
    opt = t.optim.AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=1e-4)
    sched = t.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, cfg.epochs))
    scaler = t.amp.GradScaler("cuda", enabled=device.type == "cuda")
    Xt = t.from_numpy(np.stack(Xtr))
    yt = t.tensor([idx[c] for c in ytr])
    Xv = t.from_numpy(np.stack(Xva)) if Xva else None
    yv = [idx[c] for c in yva if c in idx]
    cw = t.tensor(weights, dtype=t.float32, device=device)
    best, best_state, history = -1.0, None, []
    g = t.Generator().manual_seed(cfg.seed)
    for epoch in range(1, cfg.epochs + 1):
        if ctx.cancelled:
            ctx.log("cancelled")
            break
        model.train()
        perm = t.randperm(len(Xt), generator=g)
        total = 0.0
        for i in range(0, len(perm), cfg.batch_size):
            b = perm[i:i + cfg.batch_size]
            xb = Xt[b]
            flip = t.rand(len(b), generator=g) < 0.5          # horizontal flip is label-preserving for findings
            xb = t.where(flip.view(-1, 1, 1, 1), xb.flip(2), xb)
            xin = _norm(xb, device, t)
            xin = xin * (1 + 0.1 * (t.rand(len(b), 1, 1, 1, device=device) - 0.5))   # mild contrast jitter
            opt.zero_grad(set_to_none=True)
            with t.autocast(device_type=device.type, enabled=device.type == "cuda"):
                loss = t.nn.functional.cross_entropy(model(xin), yt[b].to(device), weight=cw)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            total += float(loss) * len(b)
        sched.step()
        m = {"train_loss": total / len(Xt)}
        if Xv is not None and yv:
            model.eval()
            pred = []
            with t.no_grad():
                for i in range(0, len(Xv), 64):
                    pred += model(_norm(Xv[i:i + 64], device, t)).argmax(1).cpu().tolist()
            known = [(idx[tt], p) for tt, p in zip(yva, pred) if tt in idx]
            rep = classification_report([k[0] for k in known], [k[1] for k in known], len(classes), classes)
            m.update(val_macro_f1=rep["macro_f1"], val_accuracy=rep["accuracy"])
            if (rep["macro_f1"] or 0) > best:
                best, best_state, best_rep = rep["macro_f1"] or 0, copy.deepcopy(model.state_dict()), rep
        history.append({"epoch": epoch, **m})
        ctx.progress(epoch, cfg.epochs, m)
        if writer:
            for k, v in m.items():
                if v is not None:
                    writer.add_scalar(k, v, epoch)
        ctx.log(f"epoch {epoch}/{cfg.epochs} " + " ".join(f"{k}={v:.4f}" for k, v in m.items() if v is not None))
    if best_state is None:
        best_state, best_rep = model.state_dict(), None
    from dentexmodel.training import provenance as P
    prov = P.build(s, cfg, TASK_LEVEL[cfg.task], {"train": _used(train_ann, ids_tr), "val": _used(val_ann, ids_va)}, idx,
                   {"input": "RGB uint8 tooth crop around the annotated box", "crop_pad": CROP_PAD, "image_size": cfg.image_size,
                    "normalize": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD, "fitted_on_data": False},
                    "train_augmentation": "horizontal flip p=0.5; multiplicative contrast jitter +-5% after normalisation",
                    "class_weights": "inverse frequency of train-split crops (+ approved review crops if enabled)"}, review_prov)
    ck = _save_checkpoint(ctx, cfg, best_state, {
        "class_names": classes, "num_classes": len(classes), "image_size": cfg.image_size, "crop_pad": CROP_PAD,
        "normalize": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD}, "label_source": "category_id_3 (DENTEX disease)",
        "class_counts_train": dict(zip(classes, counts.astype(int).tolist())), "class_weights": dict(zip(classes, weights.round(4).tolist())),
        "pretrained": "torchvision ImageNet weights" if cfg.pretrained else None, "history": history, "approved_reviews_used": extra_info,
        "limitations": ["Trained only on teeth that DENTEX labelled with one of these findings; there is no 'healthy' class. "
                        "Output says which finding a crop most resembles, NOT whether the tooth is diseased.",
                        "Probabilities come from a closed-set softmax and are not calibrated clinical probabilities.",
                        "Research use only; not a diagnosis."],
        "measured_on": "validation split (best epoch by macro-F1)",
        "metrics": {"classification": {"macro_f1": best_rep["macro_f1"], "accuracy": best_rep["accuracy"],
                                       "per_class": best_rep["per_class"]}} if best_rep else {}}, provenance=prov)
    metrics = {"classification": {"macro_f1": best_rep["macro_f1"], "accuracy": best_rep["accuracy"]}} if best_rep else {}
    return {"checkpoint": ck, "metrics": metrics}


# ------------------------------------------------------------------------------------------------ detection
class DetDataset(_Dataset):
    """Full-resolution RGB uint8 image + COCO boxes (+ polygon masks). Resizing is done by torchvision's transform."""

    def __init__(self, data_root, items, seg: bool, label_index: dict | None, train: bool):
        self.root, self.seg, self.label_index, self.train = Path(data_root), seg, label_index, train
        self.items = [(r, [a for a in anns if a.get("bbox") and (not seg or has_polygon(a))], cats) for r, anns, cats in items]
        self.items = [it for it in self.items if it[1]]

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        from PIL import Image
        from dentexmodel.utils.geometry import polygon_to_mask, xywh_to_xyxy
        row, anns, cats = self.items[i]
        img = np.asarray(Image.open(self.root / row.file_path).convert("RGB"))
        H, W = img.shape[:2]
        boxes, labels, masks = [], [], []
        for a in anns:
            b = xywh_to_xyxy(a["bbox"])
            if b[2] - b[0] < 2 or b[3] - b[1] < 2:
                continue
            boxes.append(b)
            labels.append(1 if self.label_index is None else self.label_index[annotation_fdi(a, cats)])
            if self.seg:
                masks.append(polygon_to_mask(np.asarray(a["segmentation"][0]).reshape(-1, 2), W, H))
        x = torch.from_numpy(img).permute(2, 0, 1).contiguous()          # uint8 CHW
        boxes_t = torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4)
        if self.train and torch.rand(1).item() < 0.5 and self.label_index is None:   # hflip only for the one-class mode
            x = x.flip(2)
            boxes_t = torch.stack([W - boxes_t[:, 2], boxes_t[:, 1], W - boxes_t[:, 0], boxes_t[:, 3]], 1) if len(boxes_t) else boxes_t
            masks = [m[:, ::-1].copy() for m in masks]
        tgt = {"boxes": boxes_t, "labels": torch.tensor(labels, dtype=torch.int64)}
        if self.seg:
            tgt["masks"] = torch.from_numpy(np.stack(masks).astype(np.uint8)) if masks else torch.zeros((0, H, W), dtype=torch.uint8)
        return x, tgt, row.image_id


def _collate(batch):
    return tuple(zip(*batch))


def build_detector(torch_mod, tv, architecture: str, num_classes: int, pretrained: bool):
    """Model constructor shared by training and inference: same structure either way, so state dicts always load."""
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
    from torchvision.models.detection.mask_rcnn import MaskRCNNPredictor
    builder = getattr(tv.models.detection, architecture)
    if pretrained:
        model = builder(weights="DEFAULT")
    else:
        model = builder(weights=None, weights_backbone=None, num_classes=num_classes)
        if architecture.startswith("maskrcnn"):
            model.roi_heads.detections_per_img = 40
        return model
    model.roi_heads.box_predictor = FastRCNNPredictor(model.roi_heads.box_predictor.cls_score.in_features, num_classes)
    if architecture.startswith("maskrcnn"):
        in_ch = model.roi_heads.mask_predictor.conv5_mask.in_channels
        model.roi_heads.mask_predictor = MaskRCNNPredictor(in_ch, 256, num_classes)
    if architecture.startswith("maskrcnn"):
        # A mouth has at most 32 teeth. torchvision's default of 100 full-resolution masks per image exhausts a 4 GB GPU.
        model.roi_heads.detections_per_img = 40
    return model


def resolve_numbering(boxes, scores, labels, nms_iou: float = 0.5, min_score: float = 0.3):
    """Turn raw per-class detections of a numbering model into at most one box per FDI code.

    Faster R-CNN suppresses overlaps only within a class, so one tooth can come back with several numbers. Apply
    class-agnostic NMS, then keep the highest-scoring box for each tooth number. Used by evaluation and inference alike.
    Returns indices into the inputs."""
    import torchvision
    keep_score = [i for i in range(len(scores)) if float(scores[i]) >= min_score]
    if not keep_score:
        return []
    b = torch.as_tensor([boxes[i] for i in keep_score], dtype=torch.float32)
    s = torch.as_tensor([float(scores[i]) for i in keep_score])
    kept = torchvision.ops.nms(b, s, nms_iou).tolist()
    best: dict = {}
    for k in kept:
        i = keep_score[k]
        lab = int(labels[i])
        if lab not in best or float(scores[i]) > float(scores[best[lab]]):
            best[lab] = i
    return sorted(best.values(), key=lambda i: -float(scores[i]))


@torch.no_grad() if torch is not None else (lambda f: f)
def evaluate_detector(model, dataset, device, batch_size: int = 2, score_floor: float = 0.05, with_masks: bool = False) -> dict:
    """COCO-style box mAP (and optionally mask AP@0.5) of ``model`` over ``dataset`` - computed, never estimated."""
    from dentexmodel.evaluation.metrics import mask_ap
    model.eval()
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, collate_fn=_collate)
    preds, gts, mpreds, mgts = [], [], [], []
    n_pred = 0
    ious, dices = [], []            # mask IoU / Dice over teeth matched by box overlap (IoU >= 0.5), same sub-sampled grid
    for imgs, tgts, ids in loader:
        out = model([i.to(device).float() / 255.0 for i in imgs])
        for o, tg, iid in zip(out, tgts, ids):
            keep = o["scores"] >= score_floor
            for j, (b, sc, lb) in enumerate(zip(o["boxes"][keep].cpu().tolist(), o["scores"][keep].cpu().tolist(), o["labels"][keep].cpu().tolist())):
                preds.append((iid, lb, sc, tuple(b)))
                if with_masks and "masks" in o:
                    mpreds.append((iid, lb, sc, (o["masks"][keep][j, 0, ::MASK_STRIDE, ::MASK_STRIDE] > 0.5).cpu().numpy()))
            n_pred += int(keep.sum())
            for b, lb in zip(tg["boxes"].tolist(), tg["labels"].tolist()):
                gts.append((iid, lb, tuple(b)))
            if with_masks and "masks" in tg:
                gsmall = tg["masks"][:, ::MASK_STRIDE, ::MASK_STRIDE].numpy().astype(bool)      # sub-sample BEFORE converting (memory)
                for m, lb in zip(gsmall, tg["labels"].tolist()):
                    mgts.append((iid, lb, m))
                from dentexmodel.utils.geometry import box_iou as _biou
                pb = [b for b, s_ in zip(o["boxes"][keep].cpu().tolist(), o["scores"][keep].cpu().tolist()) if s_ >= 0.3]
                pm = [o["masks"][keep][j, 0, ::MASK_STRIDE, ::MASK_STRIDE].cpu().numpy() > 0.5 for j, s_ in enumerate(o["scores"][keep].cpu().tolist()) if s_ >= 0.3]
                used = set()
                for gbox, g in zip(tg["boxes"].tolist(), gsmall):
                    best, bj = 0.0, None
                    for j, b in enumerate(pb):
                        v = _biou(b, gbox)
                        if j not in used and v > best:
                            best, bj = v, j
                    if bj is not None and best >= 0.5:
                        used.add(bj)
                        inter = float((pm[bj] & g).sum())
                        uni = float((pm[bj] | g).sum())
                        ious.append(inter / uni if uni else 0.0)
                        dices.append(2 * inter / (pm[bj].sum() + g.sum()) if (pm[bj].sum() + g.sum()) else 0.0)
    ev = detection_map(preds, gts)
    res = {"map": ev["map"], "ap50": ev["ap50"], "per_class_ap50": ev["per_class_ap50"], "n_images": len(dataset),
           "n_ground_truth": len(gts), "n_predictions": n_pred, "score_floor": score_floor}
    if with_masks and mgts:
        res["mask_ap50"] = mask_ap(mpreds, mgts)["map"]
        res["mask_eval_note"] = f"mask IoU on a {MASK_STRIDE}x subsampled grid"
        res["mean_mask_iou_matched"] = float(np.mean(ious)) if ious else None
        res["mean_dice_matched"] = float(np.mean(dices)) if dices else None
        res["n_matched_for_iou"] = len(ious)
    return res


def _train_detector(cfg, ctx, t, tv, device, writer, train_ann, val_ann) -> dict:
    s = ctx.settings
    seg = cfg.task == "segmentation"
    label_index, class_names = None, ["tooth"]
    if cfg.label_mode == "fdi":
        fdis = sorted({annotation_fdi(a, c) for _r, anns, c in train_ann for a in anns} - {None})
        label_index = {f: i + 1 for i, f in enumerate(fdis)}
        class_names = [str(f) for f in fdis]
    ds_tr = DetDataset(s.data_root, train_ann, seg, label_index, train=True)
    ds_va = DetDataset(s.data_root, val_ann, seg, label_index, train=False)
    if not len(ds_tr):
        raise DatasetUnavailableError("No annotated training images available for detection.")
    num_classes = len(class_names) + 1
    model = build_detector(t, tv, cfg.architecture, num_classes, cfg.pretrained).to(device)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = t.optim.AdamW(params, lr=cfg.learning_rate, weight_decay=1e-4)
    sched = t.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, cfg.epochs))
    scaler = t.amp.GradScaler("cuda", enabled=device.type == "cuda")
    loader = DataLoader(ds_tr, batch_size=cfg.batch_size, shuffle=True, collate_fn=_collate, num_workers=cfg.num_workers,
                        generator=t.Generator().manual_seed(cfg.seed), persistent_workers=cfg.num_workers > 0)
    best, best_state, best_ev, history = -1.0, None, None, []
    ctx.log(f"detector train={len(ds_tr)} val={len(ds_va)} classes={num_classes - 1} ({cfg.label_mode})")
    for epoch in range(1, cfg.epochs + 1):
        if ctx.cancelled:
            ctx.log("cancelled")
            break
        model.train()
        total, n, t_ep = 0.0, 0, time.time()
        for step, (imgs, tgts, _ids) in enumerate(loader, 1):
            imgs = [i.to(device).float() / 255.0 for i in imgs]
            tg = [{k: v.to(device) for k, v in d.items()} for d in tgts]
            with t.autocast(device_type=device.type, enabled=device.type == "cuda"):
                losses = model(imgs, tg)
                loss = sum(losses.values())
            if not t.isfinite(loss):
                raise RuntimeError(f"Loss became {float(loss)} at epoch {epoch} step {step}; lower the learning rate.")
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            t.nn.utils.clip_grad_norm_(params, 10.0)
            scaler.step(opt)
            scaler.update()
            total, n = total + float(loss), n + 1
            if step % 25 == 0:
                ctx.log(f"epoch {epoch} step {step}/{len(loader)} loss={total / n:.4f}")
        sched.step()
        m = {"train_loss": total / max(n, 1), "epoch_seconds": round(time.time() - t_ep, 1)}
        if len(ds_va):
            ev = evaluate_detector(model, ds_va, device, with_masks=False)
            m.update(val_map=ev["map"], val_ap50=ev["ap50"])
            if (ev["map"] or 0) > best:
                best, best_state, best_ev = ev["map"] or 0, copy.deepcopy(model.state_dict()), ev
        history.append({"epoch": epoch, **m})
        ctx.progress(epoch, cfg.epochs, m)
        if writer:
            for k, v in m.items():
                if v is not None:
                    writer.add_scalar(k, v, epoch)
        ctx.log(f"epoch {epoch}/{cfg.epochs} " + " ".join(f"{k}={v:.4f}" for k, v in m.items() if v is not None))
    if best_state is None:
        best_state = model.state_dict()
    metrics = {"detection": {"map": best_ev["map"], "ap50": best_ev["ap50"]}} if best_ev else {}
    from dentexmodel.training import provenance as P
    prov = P.build(s, cfg, TASK_LEVEL[cfg.task], {"train": [(r, len(a)) for r, a, _c in ds_tr.items], "val": [(r, len(a)) for r, a, _c in ds_va.items]},
                   label_index or {"tooth": 1},
                   {"input": "full-resolution RGB scaled to 0-1; torchvision GeneralizedRCNNTransform resizes (min_size=800, max_size=1333) "
                             "and normalises with its built-in ImageNet constants (not fitted on data)",
                    "train_augmentation": "horizontal flip p=0.5 (one-class tooth mode only)" if label_index is None else "none",
                    "masks": "DENTEX polygons rasterised per tooth" if seg else None})
    ck = _save_checkpoint(ctx, cfg, best_state, {
        "class_names": class_names, "num_classes": num_classes, "label_mode": cfg.label_mode,
        "fdi_codes": [int(c) for c in class_names] if cfg.label_mode == "fdi" else None,
        "input": "full-resolution RGB, 0-1 float; torchvision GeneralizedRCNNTransform resizes (min_size=800, max_size=1333)",
        "label_source": "category_id_1/2 of DENTEX quadrant_enumeration (all teeth annotated)",
        "pretrained": "torchvision COCO weights (general-domain; not dental)" if cfg.pretrained else None,
        "n_train_images": len(ds_tr), "n_val_images": len(ds_va), "history": history,
        "measured_on": "validation split (best epoch by box mAP@[.5:.95])", "metrics": metrics,
        "val_detail": best_ev}, provenance=prov)
    return {"checkpoint": ck, "metrics": metrics}
