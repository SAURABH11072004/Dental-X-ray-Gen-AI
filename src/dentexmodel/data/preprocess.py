"""Image validation and preprocessing. The original file is never modified.

Geometry is tracked by :class:`ResizeTransform` so boxes/masks follow the image. No horizontal flip is
provided on purpose: flipping a panoramic radiograph swaps patient-left/right and would corrupt FDI numbers.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, asdict, field
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from dentexmodel.errors import ImageValidationError

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_MAGIC = {b"\x89PNG\r\n\x1a\n": "PNG", b"\xff\xd8\xff": "JPEG"}


@dataclass
class ImageLimits:
    max_bytes: int = 25 * 1024 * 1024
    min_side: int = 256
    max_side: int = 12000
    max_pixels: int = 120_000_000

    @classmethod
    def from_settings(cls, settings) -> "ImageLimits":
        cfg = (settings.data_cfg or {}).get("image", {})
        return cls(max_bytes=int(settings.max_upload_mb) * 1024 * 1024, min_side=int(cfg.get("min_side_px", 256)),
                   max_side=int(cfg.get("max_side_px", 12000)), max_pixels=int(cfg.get("max_pixels", 120_000_000)))


@dataclass
class ResizeTransform:
    """Maps original pixel coords -> processed coords: ``p' = p * scale + (pad_x, pad_y)``."""
    orig_w: int
    orig_h: int
    scale: float = 1.0
    pad_x: int = 0
    pad_y: int = 0
    out_w: int = 0
    out_h: int = 0

    def boxes_to_processed(self, boxes_xyxy) -> np.ndarray:
        b = np.asarray(boxes_xyxy, dtype=np.float64).reshape(-1, 4)
        return b * self.scale + np.array([self.pad_x, self.pad_y, self.pad_x, self.pad_y])

    def boxes_to_original(self, boxes_xyxy) -> np.ndarray:
        b = np.asarray(boxes_xyxy, dtype=np.float64).reshape(-1, 4)
        return (b - np.array([self.pad_x, self.pad_y, self.pad_x, self.pad_y])) / self.scale

    def mask_to_processed(self, mask: np.ndarray) -> np.ndarray:
        """Nearest-neighbour resize of a binary mask (+ padding)."""
        h, w = mask.shape
        new_w, new_h = max(1, round(w * self.scale)), max(1, round(h * self.scale))
        m = np.array(Image.fromarray(mask.astype(np.uint8) * 255).resize((new_w, new_h), Image.NEAREST)) > 0
        out = np.zeros((self.out_h, self.out_w), dtype=bool)
        out[self.pad_y:self.pad_y + new_h, self.pad_x:self.pad_x + new_w] = m[: self.out_h - self.pad_y, : self.out_w - self.pad_x]
        return out


@dataclass
class PreprocessConfig:
    max_side: int = 1280
    pad_to_square: bool = False
    clahe: bool = False
    clahe_clip: float = 2.0
    clahe_grid: int = 8
    normalize: bool = True
    to_rgb: bool = False

    @classmethod
    def from_settings(cls, settings, **over) -> "PreprocessConfig":
        cfg = (settings.data_cfg or {}).get("image", {})
        cl = cfg.get("clahe", {}) or {}
        base = dict(max_side=int(cfg.get("processed_max_side", 1280)), clahe=bool(cl.get("enabled", False)),
                    clahe_clip=float(cl.get("clip_limit", 2.0)), clahe_grid=int(cl.get("tile_grid", 8)))
        base.update(over)
        return cls(**base)


@dataclass
class PreprocessResult:
    array: np.ndarray            # float32 HxW in [0,1] (or uint8 if normalize False); HxWx3 if to_rgb
    transform: ResizeTransform
    metadata: dict = field(default_factory=dict)


def sniff_format(head: bytes) -> str | None:
    for magic, name in _MAGIC.items():
        if head.startswith(magic):
            return name
    return None


def validate_upload(data: bytes, filename: str, limits: ImageLimits) -> dict:
    """Validate an uploaded byte string: extension, size, magic bytes, decodability, dimensions."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(f"Unsupported file type '{ext or 'unknown'}'.", code="unsupported_type",
                                   hint="Upload a PNG or JPEG panoramic radiograph.")
    if not data:
        raise ImageValidationError("The uploaded file is empty.", code="empty_file")
    if len(data) > limits.max_bytes:
        raise ImageValidationError(f"File is {len(data) / 1048576:.1f} MB; the limit is {limits.max_bytes / 1048576:.0f} MB.",
                                   code="file_too_large", hint="Increase MAX_UPLOAD_MB in .env or downscale the image.")
    fmt = sniff_format(data[:16])
    if fmt is None:
        raise ImageValidationError("File content is not a PNG or JPEG image (signature mismatch).", code="bad_signature")
    return inspect_image(io.BytesIO(data), limits, expected_format=fmt)


def inspect_image(source, limits: ImageLimits, expected_format: str | None = None) -> dict:
    """Decode fully (catches truncated/corrupt files) and validate dimensions. Returns metadata."""
    Image.MAX_IMAGE_PIXELS = limits.max_pixels
    try:
        with Image.open(source) as im:
            fmt, mode, (w, h) = im.format, im.mode, im.size
            if w * h > limits.max_pixels:
                raise ImageValidationError("Image has too many pixels.", code="too_many_pixels")
            im.load()
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, ValueError) as exc:
        raise ImageValidationError(f"Image is corrupt or unreadable: {exc}", code="corrupt_image")
    if min(w, h) < limits.min_side or max(w, h) > limits.max_side:
        raise ImageValidationError(f"Image size {w}x{h} is outside the supported range "
                                   f"({limits.min_side}-{limits.max_side} px per side).", code="bad_dimensions")
    return {"format": fmt, "mode": mode, "width": w, "height": h, "aspect_ratio": round(w / h, 4)}


def load_gray(path_or_file) -> np.ndarray:
    """Load any supported image as float32 grayscale in [0, 1], handling 8/16-bit and RGB(A)."""
    with Image.open(path_or_file) as im:
        im.load()
        if im.mode in ("I;16", "I;16L", "I;16B", "I"):
            arr = np.asarray(im, dtype=np.float32)
            top = float(arr.max()) or 1.0
            return np.clip(arr / (65535.0 if top > 255 else 255.0), 0, 1).astype(np.float32)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA").convert("L") if im.mode != "LA" else im.convert("L")
        else:
            im = im.convert("L")
        return (np.asarray(im, dtype=np.float32) / 255.0)


def _clahe(gray01: np.ndarray, clip: float, grid: int) -> tuple[np.ndarray, str | None]:
    try:
        import cv2  # type: ignore
        c = cv2.createCLAHE(clipLimit=float(clip), tileGridSize=(int(grid), int(grid)))
        return c.apply((gray01 * 255).astype(np.uint8)).astype(np.float32) / 255.0, "opencv"
    except Exception:  # noqa: BLE001 - cv2 missing or incompatible
        pass
    try:
        from skimage import exposure  # type: ignore
        return exposure.equalize_adapthist(gray01, clip_limit=min(0.03, float(clip) / 100.0)).astype(np.float32), "skimage"
    except Exception:  # noqa: BLE001
        return gray01, None


def percentile_normalize(gray01: np.ndarray, lo: float = 1.0, hi: float = 99.0) -> np.ndarray:
    a, b = np.percentile(gray01, [lo, hi])
    if b - a < 1e-6:
        return np.zeros_like(gray01)
    return np.clip((gray01 - a) / (b - a), 0, 1).astype(np.float32)


def resize_keep_aspect(gray01: np.ndarray, max_side: int, pad_to_square: bool = False) -> tuple[np.ndarray, ResizeTransform]:
    h, w = gray01.shape
    scale = min(1.0, max_side / max(h, w))
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    if (new_w, new_h) != (w, h):
        img = Image.fromarray(gray01, mode="F").resize((new_w, new_h), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.float32)
    else:
        arr = gray01
    pad_x = pad_y = 0
    out_w, out_h = new_w, new_h
    if pad_to_square:
        side = max(new_w, new_h)
        canvas = np.zeros((side, side), dtype=np.float32)
        pad_x, pad_y = (side - new_w) // 2, (side - new_h) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = arr
        arr, out_w, out_h = canvas, side, side
    return arr, ResizeTransform(orig_w=w, orig_h=h, scale=new_w / w, pad_x=pad_x, pad_y=pad_y, out_w=out_w, out_h=out_h)


def preprocess_image(path_or_file, cfg: PreprocessConfig | None = None) -> PreprocessResult:
    cfg = cfg or PreprocessConfig()
    gray = load_gray(path_or_file)
    meta = {"original_size": [int(gray.shape[1]), int(gray.shape[0])], "steps": ["grayscale"]}
    if cfg.normalize:
        gray = percentile_normalize(gray)
        meta["steps"].append("percentile_normalize(1,99)")
    if cfg.clahe:
        gray, backend = _clahe(gray, cfg.clahe_clip, cfg.clahe_grid)
        meta["clahe_applied"] = backend is not None
        meta["clahe_backend"] = backend
        if backend:
            meta["steps"].append(f"clahe({backend})")
    else:
        meta["clahe_applied"] = False
    arr, tf = resize_keep_aspect(gray, cfg.max_side, cfg.pad_to_square)
    meta["steps"].append(f"resize_keep_aspect(max_side={cfg.max_side}, pad_to_square={cfg.pad_to_square})")
    meta["processed_size"] = [tf.out_w, tf.out_h]
    meta["transform"] = asdict(tf)
    if cfg.to_rgb:
        arr = np.repeat(arr[..., None], 3, axis=2)
    return PreprocessResult(array=arr.astype(np.float32), transform=tf, metadata=meta)
