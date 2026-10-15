"""Image upload, registry lookup, safe file resolution and thumbnails."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image

from dentexmodel.data.preprocess import ImageLimits, load_gray, validate_upload
from dentexmodel.errors import NotFoundError
from dentexmodel.storage import jdump, jload, now
from dentexmodel.uncertainty.quality import image_quality
from dentexmodel.utils.paths import safe_join

EXT_BY_FORMAT = {"PNG": ".png", "JPEG": ".jpg"}


class ImageService:
    def __init__(self, ctx):
        self.ctx = ctx

    def upload(self, filename: str, data: bytes) -> dict:
        s = self.ctx.settings
        info = validate_upload(data, filename, ImageLimits.from_settings(s))
        digest = hashlib.sha256(data).hexdigest()
        image_id = f"up_{digest[:12]}"
        existing = self.ctx.db.get("images", image_id)
        if existing:
            return self._public(existing, duplicate=True)
        s.upload_dir.mkdir(parents=True, exist_ok=True)
        rel = f"{image_id}{EXT_BY_FORMAT[info['format']]}"
        (s.upload_dir / rel).write_bytes(data)
        gray = load_gray(io.BytesIO(data))
        from dentexmodel.data.preprocess import resize_keep_aspect
        small, _ = resize_keep_aspect(gray, 1024)
        q = image_quality(small, (s.data_cfg or {}).get("quality"))
        row = {"id": image_id, "filename": Path(filename).name[:120], "rel_path": rel, "width": info["width"], "height": info["height"],
               "sha256": digest, "source": "upload", "quality_json": jdump(q), "created": now()}
        self.ctx.db.insert("images", row)
        return self._public(row)

    def _public(self, row: dict, duplicate: bool = False) -> dict:
        try:
            size = (self.ctx.settings.upload_dir / row["rel_path"]).stat().st_size
        except OSError:
            size = None
        return {"id": row["id"], "filename": row["filename"], "width": row["width"], "height": row["height"], "source": row["source"], "size_bytes": size,
                "quality": jload(row.get("quality_json")), "created": row["created"], "duplicate": duplicate,
                "url": f"/api/images/{row['id']}/file", "thumbnail_url": f"/api/images/{row['id']}/thumbnail"}

    def _manifest_rows(self) -> dict:
        out = {}
        for which in ("main", "test_data"):
            p = self.ctx.settings.processed_dir / ("manifest.json" if which == "main" else "manifest_test_data.json")
            if p.is_file():
                from dentexmodel.data.manifest import load_manifest
                for r in load_manifest(p):
                    out.setdefault(r.image_id, r)
        return out

    def resolve_path(self, image_id: str) -> Path:
        s = self.ctx.settings
        row = self.ctx.db.get("images", image_id)
        if row:
            return safe_join(s.upload_dir, row["rel_path"])
        m = self._manifest_rows().get(image_id)
        if m is not None:
            p = safe_join(s.data_root, m.file_path)
            if p.is_file():
                return p
        raise NotFoundError(f"Image '{image_id}' was not found.", hint="Upload an image or process the dataset first.")

    def get(self, image_id: str) -> dict:
        row = self.ctx.db.get("images", image_id)
        if row:
            return self._public(row)
        rows = self._manifest_rows()
        m = rows.get(image_id)
        if m is None:
            raise NotFoundError(f"Image '{image_id}' was not found.")
        try:
            size = safe_join(self.ctx.settings.data_root, m.file_path).stat().st_size
        except OSError:
            size = None
        return {"id": m.image_id, "filename": Path(m.file_path).name, "width": m.width, "height": m.height, "size_bytes": size,
                "source": "test_data" if m.is_test_data else "dataset", "split": m.split, "annotation_status": m.annotation_status,
                "quality": None, "url": f"/api/images/{m.image_id}/file", "thumbnail_url": f"/api/images/{m.image_id}/thumbnail",
                "is_test_data": m.is_test_data, **self._twin(m, rows)}

    @staticmethod
    def _twin(m, rows: dict) -> dict:
        """For a copy of a labeled radiograph: which film it is and that film's split (e.g. a validation_data file that is a test film)."""
        owner = rows.get(m.duplicate_of) if m.duplicate_of else None
        return {"duplicate_of": m.duplicate_of, "duplicate_split": owner.split if owner else None}

    def list(self, source: str = "all", limit: int = 100, offset: int = 0) -> dict:
        items = []
        if source in ("all", "uploads"):
            items += [self._public(r) for r in self.ctx.db.list("images", limit=1000)]
        if source in ("all", "dataset", "test_data"):
            rows = self._manifest_rows()
            for iid, m in rows.items():
                if source == "dataset" and m.is_test_data:
                    continue
                if source == "test_data" and not m.is_test_data:
                    continue
                items.append({"id": iid, "filename": Path(m.file_path).name, "width": m.width, "height": m.height,
                              "source": "test_data" if m.is_test_data else "dataset", "split": m.split,
                              "annotation_status": m.annotation_status, "is_test_data": m.is_test_data, **self._twin(m, rows),
                              "url": f"/api/images/{iid}/file", "thumbnail_url": f"/api/images/{iid}/thumbnail"})
        total = len(items)
        return {"total": total, "items": items[offset:offset + limit]}

    def thumbnail(self, image_id: str, max_side: int = 320) -> bytes:
        path = self.resolve_path(image_id)
        cache = self.ctx.settings.processed_dir / "thumbs"
        cache.mkdir(parents=True, exist_ok=True)
        st = path.stat()
        cpath = cache / f"{image_id}_{max_side}_{st.st_mtime_ns}.jpg"
        if cpath.is_file():
            return cpath.read_bytes()
        gray = load_gray(path)
        from dentexmodel.data.preprocess import percentile_normalize, resize_keep_aspect
        small, _ = resize_keep_aspect(percentile_normalize(gray), max_side)
        buf = io.BytesIO()
        Image.fromarray((small * 255).astype("uint8"), mode="L").save(buf, "JPEG", quality=85)
        cpath.write_bytes(buf.getvalue())
        return buf.getvalue()

    def load_rgb01(self, image_id: str):
        import numpy as np
        g = load_gray(self.resolve_path(image_id))
        return np.repeat(g[..., None], 3, axis=2)
