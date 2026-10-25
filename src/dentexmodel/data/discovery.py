"""Locate the DENTEX dataset (or unlabeled test images) below DATA_ROOT.

The *main dataset* is declared present only when radiographs AND a COCO annotation file that references them
are found. Unlabeled radiographs (for example the 50 ``validation_data`` images) are reported as TEST DATA and
are never promoted to "main dataset".
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from dentexmodel.config import Settings
from dentexmodel.data.coco import load_coco
from dentexmodel.errors import DentaMindError

DEFAULT_DATA_CFG = {
    "dataset": {
        "name": "DENTEX",
        "image_dir_names": ["xrays"],
        "annotation_file_names": ["train_quadrant_enumeration_disease.json", "train_quadrant_enumeration.json"],
        "image_extensions": [".png", ".jpg", ".jpeg"],
        "max_search_depth": 6,
        "ignore_dirs": [".ipynb_checkpoints", "__pycache__", "checkpoints", "runs", "results", "uploads", "processed",
                        "splits", "reports", "annotations", "logs"],
        "test_data_dir_hints": ["validation_data", "test_data", "sample_data"],
        "download_help": "Place the DENTEX dataset (xrays/ + COCO annotation JSON) inside the data directory.",
    }
}
SYNTHETIC_DIR = "_synthetic_test"
MAIN_EXPECTED_HINT = "<data>/training_data/quadrant_enumeration_disease/xrays/*.png + train_quadrant_enumeration_disease.json"


@dataclass
class DatasetSource:
    name: str                     # POSIX path of the parent of the images dir, relative to DATA_ROOT
    images_dir: str               # relative POSIX path
    n_images: int
    annotation_file: str | None   # relative POSIX path or None
    role: str                     # "annotated" | "unlabeled"
    is_test_data: bool            # unlabeled images that live in a test/validation hint dir
    annotation_level: str = "none"
    n_annotated_images: int = 0
    n_annotations: int = 0
    synthetic: bool = False


@dataclass
class DatasetStatus:
    state: str                    # "main_available" | "test_data_only" | "missing"
    main_available: bool
    data_root: str
    data_root_exists: bool
    sources: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    expected_location: str = MAIN_EXPECTED_HINT
    fingerprint: str = ""
    test_image_count: int = 0
    main_image_count: int = 0
    download_help: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _cfg(settings: Settings | None) -> dict:
    base = dict(DEFAULT_DATA_CFG["dataset"])
    if settings is not None:
        base.update((settings.data_cfg or {}).get("dataset", {}))
    return base


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _walk_dirs(root: Path, max_depth: int, ignore: set):
    root = root.resolve()
    base_depth = len(root.parts)
    for dirpath, dirnames, _files in os.walk(root, followlinks=False):
        depth = len(Path(dirpath).parts) - base_depth
        dirnames[:] = sorted(d for d in dirnames if d.lower() not in ignore and d != SYNTHETIC_DIR and not d.startswith("."))
        if depth >= max_depth:
            dirnames[:] = []
        yield Path(dirpath)


def _list_images(d: Path, exts: set) -> list:
    try:
        return sorted(p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts and not p.name.startswith("."))
    except OSError:
        return []


_NAME_RX = re.compile(r"(train|val|valid|test|dentex|quadrant|annotation).*\.json$", re.I)


def _candidate_jsons(start: Path, root: Path, expected: set) -> list:
    out: list = []
    cur = start
    root = root.resolve()
    while True:
        try:
            for p in sorted(cur.iterdir()):
                if p.is_file() and p.suffix.lower() == ".json" and (p.name.lower() in expected or _NAME_RX.search(p.name)):
                    out.append(p)
        except OSError:
            pass
        if cur.resolve() == root or cur.parent == cur:
            break
        cur = cur.parent
    return out


def discover(settings: Settings, include_synthetic: bool = False) -> DatasetStatus:
    cfg = _cfg(settings)
    root = settings.data_root
    status = DatasetStatus(state="missing", main_available=False, data_root=str(root), data_root_exists=root.is_dir(),
                           download_help=str(cfg.get("download_help", "")).strip())
    if not root.is_dir():
        status.messages.append("Main dataset is not available. Please place the dataset in "
                               f"{MAIN_EXPECTED_HINT}. (The data directory '{root.name}' does not exist yet - create it first.)")
        return status
    exts = {e.lower() for e in cfg["image_extensions"]}
    dir_names = {n.lower() for n in cfg["image_dir_names"]}
    expected = {n.lower() for n in cfg["annotation_file_names"]}
    hints = [h.lower() for h in cfg["test_data_dir_hints"]]
    ignore = {d.lower() for d in cfg["ignore_dirs"]}
    fp = hashlib.sha256()
    sources: list = []
    scan_roots = [root]
    if include_synthetic and (root / SYNTHETIC_DIR).is_dir():
        scan_roots.append(root / SYNTHETIC_DIR)
    for scan_root in scan_roots:
        for d in _walk_dirs(scan_root, int(cfg["max_search_depth"]), ignore if scan_root == root else set()):
            if d.name.lower() not in dir_names:
                continue
            images = _list_images(d, exts)
            if not images:
                continue
            parent = d.parent
            names = {p.name.lower() for p in images}
            ann_path, coco = None, None
            for cand in _candidate_jsons(parent, scan_root, expected):
                try:
                    c = load_coco(cand)
                except DentaMindError as exc:
                    status.messages.append(f"Ignoring {cand.name}: {exc.message}")
                    continue
                overlap = len(names & {Path(v["file_name"]).name.lower() for v in c.images.values()})
                if overlap > 0:
                    ann_path, coco = cand, c
                    break
            synthetic = scan_root != root
            rel_parent = _rel(parent, root) if parent.resolve() != root.resolve() else "."
            low = rel_parent.lower()
            src = DatasetSource(
                name=rel_parent, images_dir=_rel(d, root), n_images=len(images),
                annotation_file=_rel(ann_path, root) if ann_path else None,
                role="annotated" if ann_path else "unlabeled",
                is_test_data=(ann_path is None and any(h in low for h in hints)) or synthetic,
                annotation_level=coco.level if coco else "none",
                n_annotated_images=len([i for i in coco.images.values() if Path(i["file_name"]).name.lower() in names]) if coco else 0,
                n_annotations=len(coco.annotations) if coco else 0, synthetic=synthetic)
            sources.append(src)
            fp.update(f"{src.images_dir}|{src.n_images}|{src.annotation_file}".encode())
            if ann_path:
                st = ann_path.stat()
                fp.update(f"{st.st_size}|{st.st_mtime_ns}".encode())
    status.sources = [asdict(s) for s in sources]
    status.fingerprint = fp.hexdigest()[:16]
    main = [s for s in sources if s.role == "annotated" and not s.synthetic and s.n_annotated_images > 0]
    tests = [s for s in sources if s.role == "unlabeled" and s.is_test_data]
    status.main_image_count = sum(s.n_images for s in sources if not s.is_test_data and not s.synthetic)
    status.test_image_count = sum(s.n_images for s in tests)
    if main:
        status.state, status.main_available = "main_available", True
        status.messages.append(f"Main dataset detected: {len(main)} annotated source(s), "
                               f"{sum(s.n_annotated_images for s in main)} image entries with annotations. The DENTEX sub-sets overlap "
                               "(the same radiograph appears in several), so this is not a count of distinct radiographs.")
    elif tests or any(s.role == "unlabeled" for s in sources):
        status.state = "test_data_only"
        status.messages.append("Main dataset is not available. Please place the dataset in "
                               f"{MAIN_EXPECTED_HINT}. Only unlabeled TEST DATA was found; it is used for pipeline smoke tests only.")
    else:
        status.messages.append("Main dataset is not available. Please place the dataset in "
                               f"{MAIN_EXPECTED_HINT}. No radiographs were found in the data directory.")
    return status
