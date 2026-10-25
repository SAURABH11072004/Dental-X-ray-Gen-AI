"""Parser for DENTEX-style COCO annotations (``categories_1/2/3`` hierarchy) and plain COCO files."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from dentexmodel.data.fdi import fdi_from_parts
from dentexmodel.errors import DentaMindError

logger = logging.getLogger(__name__)

LEVELS = ("none", "detection", "quadrant", "quadrant_enumeration", "quadrant_enumeration_disease")


@dataclass
class CocoData:
    path: str
    images: dict            # image id -> {"file_name", "width", "height"}
    annotations: list       # raw annotation dicts
    categories: dict        # "categories_1" | "categories_2" | "categories_3" | "categories" -> {id: name}
    level: str = "none"
    by_image: dict = field(default_factory=dict)  # image id -> [annotation, ...]

    def image_by_filename(self) -> dict:
        return {Path(v["file_name"]).name.lower(): k for k, v in self.images.items()}


def is_coco_like(obj) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("images"), list) and isinstance(obj.get("annotations"), list)


_cache: dict = {}


def load_coco(path: Path) -> CocoData:
    path = Path(path)
    key = (str(path), path.stat().st_mtime_ns, path.stat().st_size)
    if key in _cache:
        return _cache[key]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise DentaMindError(f"Cannot read annotation file {path.name}: {exc}", code="annotation_unreadable",
                             hint="Re-download the file; it must be valid JSON.")
    if not is_coco_like(raw):
        raise DentaMindError(f"{path.name} is not a COCO-style annotation file (needs 'images' and 'annotations').",
                             code="annotation_format")
    images = {}
    for im in raw["images"]:
        if "id" not in im or "file_name" not in im:
            continue
        images[im["id"]] = {"file_name": im["file_name"], "width": im.get("width"), "height": im.get("height")}
    categories: dict = {}
    for k, v in raw.items():
        if k.startswith("categories") and isinstance(v, list):
            categories[k] = {c.get("id"): c.get("name") for c in v if isinstance(c, dict)}
    anns = [a for a in raw["annotations"] if isinstance(a, dict)]
    level = "none"
    if any("category_id_3" in a for a in anns):
        level = "quadrant_enumeration_disease"
    elif any("category_id_2" in a for a in anns):
        level = "quadrant_enumeration"
    elif any("category_id_1" in a for a in anns):
        level = "quadrant"
    elif anns:
        level = "detection"
    by_image: dict = {}
    for a in anns:
        by_image.setdefault(a.get("image_id"), []).append(a)
    data = CocoData(str(path), images, anns, categories, level, by_image)
    _cache.clear()
    _cache[key] = data
    return data


def annotation_fdi(ann: dict, categories: dict) -> int | None:
    q = categories.get("categories_1", {}).get(ann.get("category_id_1"))
    p = categories.get("categories_2", {}).get(ann.get("category_id_2"))
    if q is None or p is None:
        return None
    return fdi_from_parts(q, p)


def annotation_finding(ann: dict, categories: dict) -> str | None:
    if "category_id_3" in ann:
        return categories.get("categories_3", {}).get(ann["category_id_3"])
    if "category_id" in ann:
        return categories.get("categories", {}).get(ann["category_id"])
    return None


def has_polygon(ann: dict) -> bool:
    seg = ann.get("segmentation")
    if not isinstance(seg, list) or not seg:
        return False
    return any(isinstance(poly, list) and len(poly) >= 6 for poly in seg)
