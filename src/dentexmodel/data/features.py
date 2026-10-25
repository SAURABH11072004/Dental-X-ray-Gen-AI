"""Feature processing. ``handcrafted_embedding`` is a cheap, model-free image descriptor used ONLY for
diversity-aware selection when no trained model can provide embeddings. It is not a learned representation and
reports itself as such (``backend='handcrafted'``)."""
from __future__ import annotations

import numpy as np
from PIL import Image


def handcrafted_embedding(gray01: np.ndarray, grid: int = 8, bins: int = 16) -> np.ndarray:
    """Spatial-intensity + gradient-orientation descriptor, L2-normalised. Length = grid*grid + bins + bins."""
    g = np.asarray(gray01, dtype=np.float32)
    small = np.asarray(Image.fromarray(g, mode="F").resize((grid * 8, grid * 4), Image.BILINEAR))
    h, w = small.shape
    pooled = small.reshape(grid, h // grid, grid, w // grid).mean(axis=(1, 3)).ravel()
    hist, _ = np.histogram(g, bins=bins, range=(0, 1), density=True)
    gy, gx = np.gradient(small)
    ang = np.arctan2(gy, gx)
    mag = np.hypot(gx, gy)
    ohist, _ = np.histogram(ang, bins=bins, range=(-np.pi, np.pi), weights=mag)
    ohist = ohist / (ohist.sum() + 1e-9)
    vec = np.concatenate([pooled - pooled.mean(), hist / (hist.sum() + 1e-9), ohist]).astype(np.float64)
    n = np.linalg.norm(vec)
    return (vec / n) if n > 0 else vec
