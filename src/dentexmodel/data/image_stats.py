"""Per-image quality metrics + handcrafted embeddings with an mtime/size keyed on-disk cache."""
from __future__ import annotations

import json
import logging

from dentexmodel.config import Settings
from dentexmodel.data.features import handcrafted_embedding
from dentexmodel.data.preprocess import load_gray, resize_keep_aspect
from dentexmodel.uncertainty.quality import image_quality

logger = logging.getLogger(__name__)
CACHE_NAME = "image_stats_cache.json"


def _load_cache(settings: Settings) -> dict:
    p = settings.processed_dir / CACHE_NAME
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def compute_image_stats(settings: Settings, rows: list, limit: int | None = None) -> dict:
    """Return ``{image_id: {quality, flags, embedding, embedding_backend, size, error}}`` for manifest rows."""
    cache = _load_cache(settings)
    qcfg = (settings.data_cfg or {}).get("quality", {})
    max_side = int((settings.data_cfg or {}).get("image", {}).get("processed_max_side", 1280))
    out: dict = {}
    dirty = False
    for r in rows[:limit] if limit else rows:
        path = settings.data_root / r.file_path
        try:
            st = path.stat()
        except OSError:
            out[r.image_id] = {"error": "file missing"}
            continue
        key = f"{r.file_path}|{st.st_size}|{st.st_mtime_ns}"
        hit = cache.get(r.image_id)
        if hit and hit.get("key") == key:
            out[r.image_id] = hit
            continue
        try:
            gray = load_gray(path)
            small, _ = resize_keep_aspect(gray, min(max_side, 768))
            q = image_quality(small, qcfg)
            entry = {"key": key, "quality": q["metrics"], "flags": q["flags"], "embedding": handcrafted_embedding(small).round(5).tolist(),
                     "embedding_backend": "handcrafted", "size": [int(gray.shape[1]), int(gray.shape[0])]}
        except Exception as exc:  # noqa: BLE001 - corrupt image must not stop the batch
            logger.warning("stats failed for %s: %s", r.image_id, exc)
            entry = {"key": key, "error": f"{type(exc).__name__}: {exc}"}
        cache[r.image_id] = entry
        out[r.image_id] = entry
        dirty = True
    if dirty:
        settings.processed_dir.mkdir(parents=True, exist_ok=True)
        (settings.processed_dir / CACHE_NAME).write_text(json.dumps(cache), encoding="utf-8")
    return out
