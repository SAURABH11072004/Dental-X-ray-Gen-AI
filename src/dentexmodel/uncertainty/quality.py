"""Image-quality signals. These are *independent* of model uncertainty: a blurry image is not the same thing
as an uncertain prediction, and the UI presents them separately."""
from __future__ import annotations

import numpy as np

DEFAULT_THRESHOLDS = {"blur_laplacian_var_min": 20.0, "contrast_std_min": 0.08, "brightness_range": [0.15, 0.85],
                      "saturation_fraction_max": 0.05}


def laplacian_variance(gray01: np.ndarray) -> float:
    """Variance of a 4-neighbour Laplacian on a 0-255 scale (sharpness proxy)."""
    g = np.asarray(gray01, dtype=np.float64) * 255.0
    if g.shape[0] < 3 or g.shape[1] < 3:
        return 0.0
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def image_quality(gray01: np.ndarray, thresholds: dict | None = None) -> dict:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    g = np.asarray(gray01, dtype=np.float32)
    lo, hi = t["brightness_range"]
    metrics = {
        "sharpness_laplacian_var": round(laplacian_variance(g), 3),
        "contrast_std": round(float(g.std()), 4),
        "brightness_mean": round(float(g.mean()), 4),
        "saturated_fraction": round(float(((g <= 0.002) | (g >= 0.998)).mean()), 4),
    }
    flags = []
    if metrics["sharpness_laplacian_var"] < t["blur_laplacian_var_min"]:
        flags.append("low_sharpness")
    if metrics["contrast_std"] < t["contrast_std_min"]:
        flags.append("low_contrast")
    if metrics["brightness_mean"] < lo:
        flags.append("too_dark")
    if metrics["brightness_mean"] > hi:
        flags.append("too_bright")
    if metrics["saturated_fraction"] > t["saturation_fraction_max"]:
        flags.append("saturation_clipping")
    return {"metrics": metrics, "flags": flags, "status": "ok" if not flags else "warning"}
