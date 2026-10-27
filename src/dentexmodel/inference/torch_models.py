"""PyTorch/torchvision inference wrappers (lazy imports). IMPLEMENTED BUT NOT VERIFIED in this repository's CI:
PyTorch and a dental checkpoint were unavailable. They never return synthetic predictions: if anything is
missing a :class:`ModelUnavailableError` explains what to install/provide."""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict

import numpy as np

from dentexmodel.config import Settings
from dentexmodel.errors import ImageValidationError, ModelUnavailableError
from dentexmodel.inference.registry import ModelInfo, active_model
from dentexmodel.utils.geometry import mask_to_rle

_CACHE: dict = {}


def require_torch():
    try:
        import torch  # type: ignore
        import torchvision  # type: ignore
        return torch, torchvision
    except ImportError as exc:
        raise ModelUnavailableError("PyTorch / torchvision are not installed.", hint="pip install torch torchvision (see requirements-ml.txt).",
                                    code="torch_missing") from exc


def _device(settings: Settings, torch):
    want = (settings.models_cfg.get("inference", {}) or {}).get("device", "auto")
    if want == "cpu" or (want == "auto" and not torch.cuda.is_available()):
        return torch.device("cpu")
    return torch.device("cuda")


@dataclass
class Detection:
    box: list            # xyxy original pixels
    score: float
    class_id: int
    label: str
    mask_rle: dict | None = None
    area: int | None = None
    fdi: int | None = None              # only set by a model trained with label_mode="fdi"
    fdi_confidence: float | None = None


@dataclass
class DetectionResult:
    image_id: str
    model_version: str
    model_id: str
    task: str
    detections: list = field(default_factory=list)
    duration_s: float = 0.0
    device: str = "cpu"
    image_size: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _load_state(torch, path, device):
    obj = torch.load(path, map_location=device, weights_only=True)
    if isinstance(obj, dict):
        for k in ("model", "model_state_dict", "state_dict"):
            if k in obj and isinstance(obj[k], dict):
                return obj[k]
    return obj


def _build(task: str, info: ModelInfo, settings: Settings):
    torch, tv = require_torch()
    device = _device(settings, torch)
    key = (info.path, task, str(device))
    mtime = __import__("os").path.getmtime(info.path)
    if key in _CACHE and _CACHE[key][0] == mtime:
        return _CACHE[key][1], device
    n_cls = int(info.metadata.get("num_classes") or (len(info.metadata.get("class_names", [])) + 1))
    arch = info.architecture or {"detection": "fasterrcnn_resnet50_fpn", "segmentation": "maskrcnn_resnet50_fpn", "classification": "resnet50",
                                       "numbering": "fasterrcnn_resnet50_fpn"}[task]
    try:
        if task == "classification":
            model = getattr(tv.models, arch)(weights=None)
            model.fc = torch.nn.Linear(model.fc.in_features, int(info.metadata.get("num_classes") or len(info.metadata["class_names"])))
        else:
            from dentexmodel.training.trainers import build_detector
            model = build_detector(torch, tv, arch, n_cls, pretrained=False)
        model.load_state_dict(_load_state(torch, info.path, device), strict=True)
    except Exception as exc:  # noqa: BLE001
        raise ModelUnavailableError(f"Could not load checkpoint '{info.model_id}': {exc}", hint="Check architecture/num_classes in the metadata sidecar.",
                                    code="checkpoint_load_failed") from exc
    model.to(device).eval()
    _CACHE[key] = (mtime, model)
    return model, device


def _run_detector(task: str, image_rgb01: np.ndarray, image_id: str, settings: Settings, model_version: str | None) -> DetectionResult:
    info = active_model(settings, task)  # checkpoint problems are reported first: they are what the user must fix
    torch, _ = require_torch()
    if model_version and model_version not in (info.version, info.model_id):
        raise ModelUnavailableError(f"Requested model '{model_version}' is not the active {task} model ('{info.version}').", code="model_mismatch")
    model, device = _build(task, info, settings)
    thr = float((settings.models_cfg.get("inference", {}) or {}).get("score_threshold", 0.3))
    names = info.metadata.get("class_names", [])
    t0 = time.time()
    x = torch.from_numpy(np.ascontiguousarray(image_rgb01.transpose(2, 0, 1))).float().to(device)
    use_amp = device.type == "cuda" and bool((settings.models_cfg.get("inference", {}) or {}).get("mixed_precision", True))
    with torch.no_grad(), torch.autocast(device_type=device.type, enabled=use_amp):
        out = model([x])[0]
    dets = []
    for i in range(len(out["boxes"])):
        s = float(out["scores"][i])
        if s < thr:
            continue
        cid = int(out["labels"][i])
        d = Detection(box=[float(v) for v in out["boxes"][i].tolist()], score=s, class_id=cid,
                      label=names[cid - 1] if 0 < cid <= len(names) else str(cid))
        if info.metadata.get("label_mode") == "fdi" and d.label.isdigit():
            d.fdi, d.fdi_confidence = int(d.label), s     # the tooth number is the model's class output, not inferred
        if "masks" in out:
            m = (out["masks"][i, 0] > 0.5).cpu().numpy()
            d.mask_rle, d.area = mask_to_rle(m), int(m.sum())
        dets.append(d)
    h, w = image_rgb01.shape[:2]
    return DetectionResult(image_id, info.version, info.model_id, task, dets, round(time.time() - t0, 4), str(device), [w, h])


def detect_teeth(image_rgb01: np.ndarray, image_id: str, settings: Settings, model_version: str | None = None) -> DetectionResult:
    """``image_rgb01``: HxWx3 float32 in [0,1]. Raises ModelUnavailableError when no dental detector is available."""
    return _run_detector("detection", image_rgb01, image_id, settings, model_version)


def segment_teeth(image_rgb01: np.ndarray, image_id: str, settings: Settings, detections=None, model_version: str | None = None) -> DetectionResult:
    """Instance segmentation with a trained Mask R-CNN. Masks are real network outputs - boxes are never filled in."""
    return _run_detector("segmentation", image_rgb01, image_id, settings, model_version)


def _prep_crops(image_rgb01: np.ndarray, boxes: list, info: ModelInfo, size: int):
    """Crop + normalise exactly as the classifier was trained (padding and mean/std come from the sidecar)."""
    from dentexmodel.inference.registry import classifier_preprocessing_problems
    from dentexmodel.training.trainers import crop_region
    problems = classifier_preprocessing_problems(info.metadata)
    if problems:      # never guess the preprocessing: a wrong crop or normalisation silently changes every prediction
        raise ModelUnavailableError(f"Classifier '{info.model_id}' does not state its training preprocessing: " + "; ".join(problems),
                                    hint="Add crop_pad, image_size and normalize (mean/std) to the checkpoint's .json sidecar, "
                                         "exactly as used in training.", code="sidecar_preprocessing_missing")
    pad = float(info.metadata["crop_pad"])
    img = (np.clip(image_rgb01, 0, 1) * 255).astype(np.uint8)
    crops = [crop_region(img, b, size, pad) for b in boxes]
    ok = [i for i, c in enumerate(crops) if c is not None]
    return ok, [crops[i] for i in ok]


def _normalize(torch, x_u8: np.ndarray, info: ModelInfo, device):
    n = info.metadata["normalize"]                  # presence and shape checked in _prep_crops / validate_sidecar
    mean = torch.tensor(n["mean"], device=device).view(1, 3, 1, 1)
    std = torch.tensor(n["std"], device=device).view(1, 3, 1, 1)
    x = torch.from_numpy(x_u8).to(device).permute(0, 3, 1, 2).float() / 255.0
    return (x - mean) / std


def number_teeth(image_rgb01: np.ndarray, detections: list, settings: Settings) -> dict:
    """Assign FDI tooth numbers to ``detections`` (dicts with ``box``/``score``; modified in place) using the registered
    numbering model. A detection gets a number only if a numbering-model box overlaps it (IoU >= 0.5); every number is
    used at most once per image; unmatched detections stay ``fdi=None``. Raises ModelUnavailableError without a registered
    numbering checkpoint - numbers are never guessed."""
    from dentexmodel.training.trainers import resolve_numbering
    from dentexmodel.utils.geometry import box_iou
    info = active_model(settings, "numbering")
    torch, _ = require_torch()
    model, device = _build("numbering", info, settings)
    codes = [int(c) for c in info.metadata["fdi_codes"]]
    thr = float((settings.models_cfg.get("inference", {}) or {}).get("score_threshold", 0.3))
    x = torch.from_numpy(np.ascontiguousarray(image_rgb01.transpose(2, 0, 1))).float().to(device)
    with torch.no_grad():
        out = model([x])[0]
    boxes, scores, labels = out["boxes"].cpu().tolist(), out["scores"].cpu().tolist(), out["labels"].cpu().tolist()
    keep = resolve_numbering(boxes, scores, labels, nms_iou=0.5, min_score=thr)
    used: set = set()
    assigned = 0
    for d in sorted(detections, key=lambda q: -q["score"]):
        best, bj = 0.0, None
        for j in keep:
            if j in used:
                continue
            v = box_iou(d["box"], boxes[j])
            if v > best:
                best, bj = v, j
        if bj is not None and best >= 0.5:
            used.add(bj)
            d["fdi"], d["fdi_confidence"] = codes[int(labels[bj]) - 1], float(scores[bj])
            assigned += 1
    return {"model_version": info.version, "n_assigned": assigned, "n_detections": len(detections),
            "note": "Tooth numbers come from the numbering model's class output for the overlapping box; unmatched regions stay unnumbered."}


def classify_regions(image_rgb01: np.ndarray, boxes: list, settings: Settings, size: int | None = None, flip: bool = False) -> dict:
    """Classify tooth crops with the active dental classifier. Returns class names and per-box softmax probabilities
    (``None`` for boxes too small to crop)."""
    info = active_model(settings, "classification")
    torch, _ = require_torch()
    model, device = _build("classification", info, settings)
    size = int(size or info.metadata.get("image_size") or 224)
    names = info.metadata.get("class_names", [])
    ok, crops = _prep_crops(image_rgb01, boxes, info, size)
    probs: list = [None] * len(boxes)
    if crops:
        if flip:                          # test-time augmentation: classify the horizontally flipped crops
            crops = [np.ascontiguousarray(c[:, ::-1]) for c in crops]
        x = _normalize(torch, np.stack(crops), info, device)
        with torch.no_grad():
            p = torch.softmax(model(x), dim=1).cpu().numpy()
        for i, row in zip(ok, p):
            probs[i] = row.tolist()
    return {"model_version": info.version, "class_names": names, "probabilities": probs, "flipped": flip,
            "limitations": info.metadata.get("limitations", [])}


def explain_region(image_rgb01: np.ndarray, box: list, settings: Settings, size: int = 224) -> dict:
    """Grad-CAM for the active classifier on one region (IMPLEMENTED BUT NOT VERIFIED - needs torch + a dental
    classification checkpoint). Returns a heatmap in the coordinates of the *crop* (``box`` in original pixels)."""
    import base64
    import io
    from PIL import Image
    info = active_model(settings, "classification")
    torch, _ = require_torch()
    model, device = _build("classification", info, settings)
    h, w = image_rgb01.shape[:2]
    size = int(info.metadata.get("image_size") or size)
    ok, crops = _prep_crops(image_rgb01, [box], info, size)
    if not ok:
        raise ImageValidationError("Region is too small to explain.", code="bad_region")
    x1, y1, x2, y2 = [int(round(v)) for v in box]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    x = _normalize(torch, np.stack(crops), info, device)
    store: dict = {}
    layer = model.layer4
    fh = layer.register_forward_hook(lambda m, i, o: store.__setitem__("act", o))
    bh = layer.register_full_backward_hook(lambda m, gi, go: store.__setitem__("grad", go[0]))
    try:
        model.zero_grad()
        logits = model(x)
        cls = int(logits.argmax(1))
        logits[0, cls].backward()
    finally:
        fh.remove()
        bh.remove()
    weights = store["grad"].mean(dim=(2, 3), keepdim=True)
    cam = torch.relu((weights * store["act"]).sum(1, keepdim=True))[0, 0].detach().cpu().numpy()
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-9)
    # colourise (blue -> red) with alpha proportional to influence, so it can be overlaid on the radiograph
    gray = np.asarray(Image.fromarray((cam * 255).astype(np.uint8)).resize((x2 - x1, y2 - y1), Image.BILINEAR), dtype=np.float32) / 255.0
    rgba = np.zeros(gray.shape + (4,), dtype=np.uint8)
    rgba[..., 0] = np.clip(255 * (2 * gray - 0.5), 0, 255)
    rgba[..., 1] = np.clip(255 * (1 - abs(2 * gray - 1)), 0, 255)
    rgba[..., 2] = np.clip(255 * (1.5 - 2 * gray), 0, 255)
    rgba[..., 3] = (255 * np.clip(gray * 1.2, 0, 1)).astype(np.uint8)
    png = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(png, "PNG")
    names = info.metadata.get("class_names", [])
    prob = float(torch.softmax(logits, 1)[0, cls])
    return {"model_version": info.version, "box": [x1, y1, x2, y2], "class_index": cls, "label": names[cls] if cls < len(names) else str(cls),
            "probability": prob, "heatmap_png_base64": base64.b64encode(png.getvalue()).decode(), "heatmap_format": "RGBA PNG, size of the box",
            "method": "Grad-CAM on the last convolutional block (ResNet layer4) for the top-scoring class of the crop", "target_class": names[cls] if cls < len(names) else str(cls),
            "model_architecture": info.architecture,
            "note": "Grad-CAM highlights regions that influenced this model's score; it is not evidence of pathology."}
