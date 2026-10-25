"""Crop-level preprocessing shared by classifier training, evaluation and inference.

One implementation, selected by a small config dict that is stored in the checkpoint sidecar (``crop_preprocess``). A checkpoint
without that key is treated as ``{"mode": "none"}``, i.e. exactly the pre-existing behaviour, so older models keep working.

Modes (all operate on uint8 RGB crops, return uint8 RGB crops of the same shape; no new dependencies):

* ``none``     - unchanged.
* ``stretch``  - per-crop percentile contrast stretch (``low``/``high`` percentiles of the grey values -> 0..255).
* ``clahe``    - contrast-limited adaptive histogram equalisation on the grey channel (``clip`` ~1.5-2.5, ``grid`` tiles per side).
* ``median`` / ``gaussian`` - mild denoising (``size`` / ``sigma``); only meaningful when a noise measurement justifies it.

The radiographs are single-channel images stored as RGB; the grey value is the channel mean and is written back to all channels.
"""
from __future__ import annotations

import numpy as np

DEFAULT = {"mode": "none"}


def normalise_config(cfg: dict | None) -> dict:
    cfg = dict(cfg or DEFAULT)
    cfg.setdefault("mode", "none")
    return cfg


def _grey(rgb: np.ndarray) -> np.ndarray:
    return rgb.astype(np.float32).mean(axis=2)


def _to_rgb(g: np.ndarray) -> np.ndarray:
    g8 = np.clip(np.rint(g), 0, 255).astype(np.uint8)
    return np.repeat(g8[:, :, None], 3, axis=2)


def stretch(rgb: np.ndarray, low: float = 1.0, high: float = 99.0) -> np.ndarray:
    g = _grey(rgb)
    lo, hi = np.percentile(g, [low, high])
    if hi - lo < 4:                       # nearly flat crop: nothing meaningful to stretch
        return rgb
    return _to_rgb((g - lo) * (255.0 / (hi - lo)))


def clahe(rgb: np.ndarray, clip: float = 2.0, grid: int = 4) -> np.ndarray:
    """Standard CLAHE: per-tile clipped histogram -> equalisation LUT, bilinear blending between neighbouring tiles."""
    g = np.clip(np.rint(_grey(rgb)), 0, 255).astype(np.uint8)
    H, W = g.shape
    th, tw = -(-H // grid), -(-W // grid)
    ph, pw = th * grid - H, tw * grid - W
    gp = np.pad(g, ((0, ph), (0, pw)), mode="reflect") if (ph or pw) else g
    luts = np.zeros((grid, grid, 256), np.float32)
    area = th * tw
    clip_n = max(1, int(round(clip * area / 256.0)))
    for i in range(grid):
        for j in range(grid):
            t = gp[i * th:(i + 1) * th, j * tw:(j + 1) * tw]
            h = np.bincount(t.ravel(), minlength=256).astype(np.float64)
            excess = np.maximum(h - clip_n, 0).sum()
            h = np.minimum(h, clip_n) + excess / 256.0
            cdf = np.cumsum(h)
            luts[i, j] = np.clip(cdf / cdf[-1] * 255.0, 0, 255)
    ys = (np.arange(H) + 0.5) / th - 0.5
    xs = (np.arange(W) + 0.5) / tw - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, grid - 1)
    y1 = np.clip(y0 + 1, 0, grid - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, grid - 1)
    x1 = np.clip(x0 + 1, 0, grid - 1)
    wy = np.clip(ys - np.floor(ys), 0, 1)[:, None].astype(np.float32)
    wx = np.clip(xs - np.floor(xs), 0, 1)[None, :].astype(np.float32)
    wy = np.where((ys < 0)[:, None], 0.0, wy)
    wx = np.where((xs < 0)[None, :], 0.0, wx)
    v = g.astype(np.intp)
    a = luts[y0[:, None], x0[None, :], v]
    b = luts[y0[:, None], x1[None, :], v]
    c = luts[y1[:, None], x0[None, :], v]
    d = luts[y1[:, None], x1[None, :], v]
    out = (a * (1 - wx) + b * wx) * (1 - wy) + (c * (1 - wx) + d * wx) * wy
    return _to_rgb(out)


def denoise(rgb: np.ndarray, mode: str, size: int = 3, sigma: float = 0.8) -> np.ndarray:
    from PIL import Image, ImageFilter
    im = Image.fromarray(rgb[:, :, 0])
    im = im.filter(ImageFilter.MedianFilter(int(size))) if mode == "median" else im.filter(ImageFilter.GaussianBlur(float(sigma)))
    return np.repeat(np.asarray(im)[:, :, None], 3, axis=2)


def apply_crop(rgb: np.ndarray, cfg: dict | None) -> np.ndarray:
    cfg = normalise_config(cfg)
    m = cfg["mode"]
    if m == "none":
        return rgb
    if m == "stretch":
        return stretch(rgb, cfg.get("low", 1.0), cfg.get("high", 99.0))
    if m == "clahe":
        return clahe(rgb, cfg.get("clip", 2.0), int(cfg.get("grid", 4)))
    if m in ("median", "gaussian"):
        return denoise(rgb, m, cfg.get("size", 3), cfg.get("sigma", 0.8))
    raise ValueError(f"unknown crop preprocessing mode: {m!r}")


def apply_crops(crops, cfg: dict | None) -> list:
    cfg = normalise_config(cfg)
    if cfg["mode"] == "none":
        return list(crops)
    return [apply_crop(c, cfg) for c in crops]


def noise_sigma(rgb: np.ndarray) -> float:
    """Immerkaer fast noise-sigma estimate on the grey channel (robust to edges; units = grey levels)."""
    g = _grey(rgb)
    H, W = g.shape
    if H < 3 or W < 3:
        return 0.0
    k = (g[:-2, :-2] - 2 * g[:-2, 1:-1] + g[:-2, 2:] - 2 * g[1:-1, :-2] + 4 * g[1:-1, 1:-1] - 2 * g[1:-1, 2:]
         + g[2:, :-2] - 2 * g[2:, 1:-1] + g[2:, 2:])
    return float(np.sqrt(np.pi / 2) * np.abs(k).sum() / (6.0 * (W - 2) * (H - 2)))
