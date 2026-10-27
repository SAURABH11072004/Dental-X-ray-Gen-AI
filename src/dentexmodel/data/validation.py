"""Dataset validation: missing/corrupt images, duplicate ids, invalid boxes, unsupported labels,
invalid FDI numbering, missing masks, and split leakage."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

from PIL import Image

from dentexmodel.config import Settings
from dentexmodel.data.coco import annotation_fdi, load_coco
from dentexmodel.data.fdi import is_valid_fdi
from dentexmodel.data.discovery import DatasetStatus
from dentexmodel.utils.geometry import validate_box_xyxy, xywh_to_xyxy

logger = logging.getLogger(__name__)
MAX_EXAMPLES = 25


@dataclass
class Issue:
    code: str
    severity: str        # error | warning | info
    message: str
    image_id: str | None = None


@dataclass
class ValidationReport:
    ok: bool = True
    n_images: int = 0
    counts: dict = field(default_factory=dict)       # code -> total occurrences
    severities: dict = field(default_factory=dict)   # code -> severity
    examples: dict = field(default_factory=dict)     # code -> first MAX_EXAMPLES issues
    checked: list = field(default_factory=list)

    def add(self, issue: Issue) -> None:
        self.counts[issue.code] = self.counts.get(issue.code, 0) + 1
        self.severities[issue.code] = issue.severity
        ex = self.examples.setdefault(issue.code, [])
        if len(ex) < MAX_EXAMPLES:
            ex.append(asdict(issue))
        if issue.severity == "error":
            self.ok = False

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_lines(self) -> list:
        return [f"[{self.severities[c]}] {c}: {n}" for c, n in sorted(self.counts.items())] or ["no issues"]


def validate_dataset(settings: Settings, status: DatasetStatus, rows: list, deep: bool = True) -> ValidationReport:
    cfg_labels = (settings.data_cfg or {}).get("labels", {})
    allow_dec = bool(cfg_labels.get("allow_deciduous_fdi", False))
    rep = ValidationReport(n_images=len(rows))
    rep.checked = ["missing_image", "corrupt_image", "duplicate_image_id", "invalid_box", "unsupported_label",
                   "invalid_fdi", "missing_masks", "dimension_mismatch", "split_leakage", "duplicate_of_labeled"]
    root = settings.data_root
    ids = Counter(r.image_id for r in rows)
    for iid, n in ids.items():
        if n > 1:
            rep.add(Issue("duplicate_image_id", "error", f"image id '{iid}' appears {n} times", iid))
    for r in rows:
        if r.duplicate_of:
            kind = "test-data image" if r.is_test_data else "unlabeled image"
            rep.add(Issue("duplicate_of_labeled", "warning",
                          f"{kind} has identical pixels to labeled image '{r.duplicate_of}'", r.image_id))
    for r in rows:
        p = root / r.file_path
        if not r.file_exists or not p.is_file():
            rep.add(Issue("missing_image", "error", f"file listed but not found: {r.file_path}", r.image_id))
            continue
        if deep:
            try:
                with Image.open(p) as im:
                    im.verify()
            except Exception as exc:  # noqa: BLE001
                rep.add(Issue("corrupt_image", "error", f"{r.file_path}: {exc}", r.image_id))
        if r.width is None or r.height is None:
            rep.add(Issue("corrupt_image", "error", f"cannot read image size: {r.file_path}", r.image_id))
    # annotation-level checks
    # keyed by (source, file name): different DENTEX subsets reuse names for different radiographs
    row_by_name = {(r.dataset_source, Path(r.file_path).name.lower()): r for r in rows}
    for src in status.sources:
        if not src["annotation_file"]:
            continue
        coco = load_coco(root / src["annotation_file"])
        for cid, info in coco.images.items():
            row = row_by_name.get((src["name"], Path(info["file_name"]).name.lower()))
            iid = row.image_id if row else str(cid)
            if row and info.get("width") and row.width and (info["width"], info["height"]) != (row.width, row.height):
                rep.add(Issue("dimension_mismatch", "warning",
                              f"annotation says {info['width']}x{info['height']}, file is {row.width}x{row.height}", iid))
            anns = coco.by_image.get(cid, [])
            if anns and not any(isinstance(a.get("segmentation"), list) and a["segmentation"] for a in anns):
                rep.add(Issue("missing_masks", "info", "no segmentation polygons for this image", iid))
            for a in anns:
                bbox = a.get("bbox")
                if bbox is None:
                    rep.add(Issue("invalid_box", "error", f"annotation {a.get('id')} has no bbox", iid))
                else:
                    probs = validate_box_xyxy(xywh_to_xyxy(bbox) if len(bbox) == 4 else bbox,
                                              info.get("width") or (row.width if row else None),
                                              info.get("height") or (row.height if row else None))
                    if probs:
                        rep.add(Issue("invalid_box", "error", f"annotation {a.get('id')}: {', '.join(probs)}", iid))
                for k in (1, 2, 3):
                    key = f"category_id_{k}"
                    if key in a and a[key] not in coco.categories.get(f"categories_{k}", {}):
                        rep.add(Issue("unsupported_label", "error", f"annotation {a.get('id')}: {key}={a[key]} not in categories_{k}", iid))
                if "category_id" in a and a["category_id"] not in coco.categories.get("categories", {}) and "categories" in coco.categories:
                    rep.add(Issue("unsupported_label", "error", f"annotation {a.get('id')}: category_id={a['category_id']}", iid))
                if "category_id_1" in a and "category_id_2" in a:
                    f = annotation_fdi(a, coco.categories)
                    if f is None or not is_valid_fdi(f, allow_dec):
                        rep.add(Issue("invalid_fdi", "error", f"annotation {a.get('id')}: invalid FDI combination", iid))
    rep.ok = not any(sev == "error" for sev in rep.severities.values())
    return rep


def check_split_leakage(rows: list, assignments: dict, report: ValidationReport | None = None) -> list:
    """Return leakage issues: the same image id or patient group in more than one split, or duplicate ids."""
    issues: list = []
    id_splits: dict = defaultdict(set)
    grp_splits: dict = defaultdict(set)
    for r in rows:
        s = assignments.get(r.image_id)
        if s is None:
            continue
        id_splits[r.image_id].add(s)
        grp_splits[r.patient_id or r.image_id].add(s)
    for iid, splits in id_splits.items():
        if len(splits) > 1:
            issues.append(Issue("split_leakage", "error", f"image '{iid}' present in splits {sorted(splits)}", iid))
    for g, splits in grp_splits.items():
        if len(splits) > 1:
            issues.append(Issue("split_leakage", "error", f"patient/group '{g}' present in splits {sorted(splits)}", g))
    if report is not None:
        for i in issues:
            report.add(i)
    return issues
