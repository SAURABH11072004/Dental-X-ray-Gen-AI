"""Draw real model output on the original radiograph. Pure PIL; nothing is drawn that the model did not output."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PALETTE = {"tooth": (15, 139, 141), "Caries": (230, 160, 20), "Deep Caries": (200, 50, 50),
           "Impacted": (110, 70, 200), "Periapical Lesion": (30, 110, 220)}


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_detections(image_rgb01: np.ndarray, detections: list, classification: dict | None = None, min_score: float = 0.0) -> Image.Image:
    """Overlay boxes (and, when present, the top finding per box with its softmax probability).

    ``detections``: list of dicts with ``box`` (xyxy pixels) and ``score``. ``classification``: output of
    ``classify_regions`` for the *same ordered boxes*.
    """
    img = Image.fromarray((np.clip(image_rgb01, 0, 1) * 255).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    H, W = image_rgb01.shape[:2]
    lw = max(2, int(round(max(W, H) / 700)))
    font = _font(max(12, int(round(max(W, H) / 110))))
    names = (classification or {}).get("class_names", [])
    probs = (classification or {}).get("probabilities", [])
    for i, d in enumerate(detections):
        if d["score"] < min_score:
            continue
        x1, y1, x2, y2 = d["box"]
        label, colour = d.get("label") or f"tooth {d['score']:.3f}", PALETTE["tooth"]   # "label": caller-supplied text (full-pipeline regions)
        p = probs[i] if i < len(probs) else None
        if p is not None and names:
            k = int(np.argmax(p))
            label = f"~{names[k]} {p[k]:.2f} | tooth {d['score']:.3f}"      # "~": closest of the trained findings, not a diagnosis
            colour = PALETTE.get(names[k], colour)
        draw.rectangle([x1, y1, x2, y2], outline=colour + (255,), width=lw)
        tw = draw.textlength(label, font=font)
        draw.rectangle([x1, max(0, y1 - font.size - 4), x1 + tw + 6, y1], fill=colour + (200,))
        draw.text((x1 + 3, max(0, y1 - font.size - 3)), label, fill=(255, 255, 255, 255), font=font)
    if probs and names:
        note = "Findings are the closest of 4 trained classes (no 'healthy' class). Research output, not a diagnosis."
        bh = font.size + 10
        draw.rectangle([0, H - bh, W, H], fill=(0, 0, 0, 170))
        draw.text((8, H - bh + 5), note, fill=(255, 255, 255, 255), font=font)
    return img
