"""Dataset manifest: one row per radiograph."""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

from PIL import Image

from dentexmodel.config import Settings
from dentexmodel.data.coco import annotation_fdi, annotation_finding, has_polygon, load_coco
from dentexmodel.data.discovery import DatasetStatus

logger = logging.getLogger(__name__)


@dataclass
class ManifestRow:
    image_id: str
    file_path: str                 # POSIX path relative to DATA_ROOT
    dataset_source: str
    annotation_level: str          # none | detection | quadrant | quadrant_enumeration | quadrant_enumeration_disease
    width: int | None
    height: int | None
    tooth_ids: list = field(default_factory=list)       # FDI codes present
    labels: list = field(default_factory=list)          # finding names present
    has_masks: bool = False
    n_annotations: int = 0
    n_masks: int = 0
    split: str = "unassigned"
    annotation_status: str = "unlabeled"   # unlabeled | annotated
    is_test_data: bool = False
    patient_id: str | None = None
    file_exists: bool = True
    coco_image_id: int | None = None
    content_hash: str | None = None   # sha256 of the file bytes (identifies the same radiograph under different names)
    duplicate_of: str | None = None   # image_id of the first annotated row with identical pixels, if any


def _content_hashes(settings: Settings, rows: list) -> None:
    """Fill ``content_hash`` for every row, caching by (size, mtime) so reruns are fast."""
    import hashlib
    cache_path = settings.processed_dir / "content_hash_cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        cache = {}
    dirty = False
    for r in rows:
        p = settings.data_root / r.file_path
        if not p.is_file():
            continue
        st = p.stat()
        hit = cache.get(r.file_path)
        if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
            r.content_hash = hit[2]
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        r.content_hash = h.hexdigest()
        cache[r.file_path] = [st.st_size, st.st_mtime_ns, r.content_hash]
        dirty = True
    if dirty:
        settings.processed_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")


def _link_duplicates(rows: list) -> None:
    """Group identical pixels. Without a patient-id regex the content hash becomes the split group, so the same
    radiograph can never land in two splits just because it is stored under several file names."""
    first_annotated: dict = {}
    for r in rows:
        if r.content_hash and r.annotation_status == "annotated" and not r.is_test_data:
            first_annotated.setdefault(r.content_hash, r.image_id)
    for r in rows:
        if r.content_hash and r.patient_id is None:
            r.patient_id = "h_" + r.content_hash[:16]
        owner = first_annotated.get(r.content_hash) if r.content_hash else None
        if owner and owner != r.image_id and (r.annotation_status != "annotated" or r.is_test_data):
            r.duplicate_of = owner


def _dims(path: Path):
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001 - reported later by validation as corrupt
        return None, None


def _source_tag(source_name: str) -> str:
    """Short, stable tag for a source folder: ``quadrant-enumeration-disease`` -> ``qed``."""
    import re
    leaf = source_name.replace("\\", "/").rsplit("/", 1)[-1]
    parts = [t for t in re.split(r"[^A-Za-z0-9]+", leaf) if t]
    return "".join(t[0] for t in parts).lower() or "src"


def _disambiguate_ids(rows: list) -> None:
    """DENTEX subsets all contain files named ``train_<n>.png`` that are *different* radiographs. A bare file
    stem would therefore collide across sources and silently merge distinct images (ids, splits, labels).
    Stems that occur in more than one source get a source tag prefix; unique stems are left untouched."""
    from collections import defaultdict
    by_stem: dict = defaultdict(set)
    for r in rows:
        by_stem[r.image_id].add(r.dataset_source)
    for r in rows:
        if len(by_stem[r.image_id]) > 1:
            r.image_id = f"{_source_tag(r.dataset_source)}_{r.image_id}"
    ids = [r.image_id for r in rows]
    if len(ids) != len(set(ids)):  # tags themselves collided; fall back to the full folder name
        for r in rows:
            r.image_id = f"{r.dataset_source.replace('/', '_')}_{r.image_id.split('_', 1)[-1]}"


def build_manifest(settings: Settings, status: DatasetStatus, patient_regex: str | None = None) -> list:
    """Create manifest rows from a :class:`DatasetStatus`. Synthetic sources are labelled but never mixed in
    unless they were explicitly discovered with ``include_synthetic``."""
    import re
    rx = re.compile(patient_regex) if patient_regex else None
    rows: list = []
    root = settings.data_root
    for src in status.sources:
        images_dir = root / src["images_dir"]
        disk = {p.name.lower(): p for p in images_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"} and not p.name.startswith(".")}
        seen: set = set()
        coco = load_coco(root / src["annotation_file"]) if src["annotation_file"] else None

        def make(stem, path, level, ann_list, cats, cid, w, h, exists, status_s):
            teeth, labels, n_masks = [], [], 0
            for a in ann_list:
                f = annotation_fdi(a, cats)
                if f is not None and f not in teeth:
                    teeth.append(f)
                lab = annotation_finding(a, cats)
                if lab is not None and lab not in labels:
                    labels.append(lab)
                n_masks += 1 if has_polygon(a) else 0
            pid = None
            if rx:
                m = rx.search(Path(path).name)
                pid = m.group(1) if m and m.groups() else None
            rows.append(ManifestRow(
                image_id=stem, file_path=(Path(src["images_dir"]) / path).as_posix(), dataset_source=src["name"],
                annotation_level=level, width=w, height=h, tooth_ids=sorted(teeth), labels=sorted(labels),
                has_masks=n_masks > 0, n_annotations=len(ann_list), n_masks=n_masks, annotation_status=status_s,
                is_test_data=bool(src["is_test_data"]), patient_id=pid, file_exists=exists, coco_image_id=cid))

        if coco:
            for cid, info in coco.images.items():
                fname = Path(info["file_name"]).name
                p = disk.get(fname.lower())
                seen.add(fname.lower())
                w, h = _dims(p) if p else (info.get("width"), info.get("height"))
                make(Path(fname).stem, p.name if p else fname, coco.level, coco.by_image.get(cid, []), coco.categories,
                     cid, w, h, p is not None, "annotated" if coco.by_image.get(cid) else "unlabeled")
        for low, p in sorted(disk.items()):
            if low in seen:
                continue
            w, h = _dims(p)
            make(p.stem, p.name, "none", [], {}, None, w, h, True, "unlabeled")
    _disambiguate_ids(rows)
    _content_hashes(settings, rows)
    _link_duplicates(rows)
    return rows


def save_manifest(rows: list, out_dir: Path, stem: str = "manifest") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    jpath, cpath = out_dir / f"{stem}.json", out_dir / f"{stem}.csv"
    data = [asdict(r) for r in rows]
    jpath.write_text(json.dumps(data, indent=1), encoding="utf-8")
    with open(cpath, "w", newline="", encoding="utf-8") as fh:
        if data:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            for d in data:
                w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in d.items()})
    return {"json": jpath.name, "csv": cpath.name, "rows": len(rows)}


def load_manifest(path: Path) -> list:
    return [ManifestRow(**d) for d in json.loads(Path(path).read_text(encoding="utf-8"))]
