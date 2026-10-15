"""Bounding-box / mask helpers. Pixel boxes are ``xyxy`` unless the name says ``xywh``;
Label Studio percentages are relative to the *original* image size."""
from __future__ import annotations

import numpy as np

Box = tuple[float, float, float, float]


def xywh_to_xyxy(b) -> Box:
    x, y, w, h = (float(v) for v in b)
    return (x, y, x + w, y + h)


def xyxy_to_xywh(b) -> Box:
    x1, y1, x2, y2 = (float(v) for v in b)
    return (x1, y1, x2 - x1, y2 - y1)


def box_area(b) -> float:
    return max(0.0, float(b[2]) - float(b[0])) * max(0.0, float(b[3]) - float(b[1]))


def clip_box(b, width: float, height: float) -> Box:
    x1, y1, x2, y2 = (float(v) for v in b)
    return (min(max(x1, 0.0), width), min(max(y1, 0.0), height), min(max(x2, 0.0), width), min(max(y2, 0.0), height))


def box_iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = box_area(a) + box_area(b) - inter
    return float(inter / union) if union > 0 else 0.0


def validate_box_xyxy(b, width: float | None = None, height: float | None = None, min_size: float = 1.0) -> list[str]:
    """Return a list of problems (empty if the box is valid)."""
    problems: list[str] = []
    try:
        x1, y1, x2, y2 = (float(v) for v in b)
    except (TypeError, ValueError):
        return ["box must be 4 numbers"]
    if not all(np.isfinite([x1, y1, x2, y2])):
        return ["box contains NaN/inf"]
    if x2 <= x1 or y2 <= y1:
        problems.append("non-positive width or height")
    elif (x2 - x1) < min_size or (y2 - y1) < min_size:
        problems.append("box smaller than minimum size")
    if width is not None and height is not None:
        if x1 < -0.5 or y1 < -0.5 or x2 > width + 0.5 or y2 > height + 0.5:
            problems.append("box outside image bounds")
    return problems


def pixel_to_percent_xywh(box_xyxy, width: float, height: float) -> dict:
    """Pixel xyxy -> Label Studio rectangle value (percent of original size)."""
    x1, y1, x2, y2 = box_xyxy
    return {"x": 100.0 * x1 / width, "y": 100.0 * y1 / height, "width": 100.0 * (x2 - x1) / width, "height": 100.0 * (y2 - y1) / height}


def percent_to_pixel_xyxy(value: dict, width: float, height: float) -> Box:
    """Label Studio rectangle value (percent) -> pixel xyxy. Rotation is not supported."""
    x1 = value["x"] / 100.0 * width
    y1 = value["y"] / 100.0 * height
    return (x1, y1, x1 + value["width"] / 100.0 * width, y1 + value["height"] / 100.0 * height)


def polygon_percent_to_pixel(points, width: float, height: float) -> list[tuple[float, float]]:
    return [(p[0] / 100.0 * width, p[1] / 100.0 * height) for p in points]


def polygon_pixel_to_percent(points, width: float, height: float) -> list[list[float]]:
    return [[100.0 * p[0] / width, 100.0 * p[1] / height] for p in points]


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    if a.shape != b.shape:
        raise ValueError(f"mask shapes differ: {a.shape} vs {b.shape}")
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union > 0 else 0.0


# ---- mask serialisation (uncompressed run-length encoding, row-major, JSON friendly) ----
def mask_to_rle(mask: np.ndarray) -> dict:
    m = np.asarray(mask, dtype=bool)
    flat = m.ravel(order="C")
    if flat.size == 0:
        return {"size": list(m.shape), "counts": [], "order": "C"}
    change = np.flatnonzero(flat[1:] != flat[:-1]) + 1
    bounds = np.concatenate(([0], change, [flat.size]))
    runs = np.diff(bounds).tolist()
    if flat[0]:  # RLE always starts with a run of zeros
        runs = [0] + runs
    return {"size": list(m.shape), "counts": runs, "order": "C"}


def rle_to_mask(rle: dict) -> np.ndarray:
    h, w = rle["size"]
    out = np.zeros(h * w, dtype=bool)
    pos, val = 0, False
    for run in rle["counts"]:
        if val:
            out[pos:pos + run] = True
        pos += run
        val = not val
    if pos != h * w:
        raise ValueError("RLE counts do not sum to mask size")
    return out.reshape((h, w), order="C")


def polygon_to_mask(points, width: int, height: int) -> np.ndarray:
    """Rasterise a polygon (pixel coords) with Pillow - real polygon fill, never a box."""
    from PIL import Image, ImageDraw

    img = Image.new("L", (int(width), int(height)), 0)
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) >= 3:
        ImageDraw.Draw(img).polygon(pts, outline=1, fill=1)
    return np.array(img, dtype=bool)
