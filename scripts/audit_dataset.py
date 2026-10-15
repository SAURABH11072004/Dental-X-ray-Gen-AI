#!/usr/bin/env python
"""Dataset audit: writes Data/reports/dataset_audit.json and dataset_audit.md from the real files.

Everything reported is measured from the files on disk; nothing is assumed. Reads images (never modifies them).
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from dentexmodel.config import get_settings
from dentexmodel.data.coco import load_coco
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.fdi import is_valid_fdi
from dentexmodel.data.coco import annotation_fdi


def audit(settings, decode: bool) -> dict:
    svc = DatasetService(settings)
    status = svc.status()
    svc.process()
    rows = svc.manifest("main")
    test_rows = [r for r in svc.manifest("test_data")] if (settings.processed_dir / "manifest_test_data.json").is_file() else []
    root = settings.data_root
    out: dict = {"generated": datetime.now(timezone.utc).isoformat(), "data_root": str(root), "state": status.state,
                 "sources": [], "totals": {}, "duplicates": {}, "leakage": {}, "validation": {}}

    all_rows = rows + test_rows
    out["totals"] = {"images_on_disk": len(all_rows), "formats": dict(Counter(Path(r.file_path).suffix.lower() for r in all_rows)),
                     "annotated_images": sum(1 for r in rows if r.annotation_status == "annotated"),
                     "unlabeled_images": sum(1 for r in rows if r.annotation_status != "annotated"),
                     "test_data_images": len(test_rows)}

    corrupt = []
    if decode:
        for r in all_rows:
            try:
                with Image.open(root / r.file_path) as im:
                    im.verify()
            except Exception as exc:  # noqa: BLE001
                corrupt.append({"file": r.file_path, "error": str(exc)})
    out["totals"]["corrupt_images"] = corrupt if decode else "not checked (--no-decode)"

    for src in status.sources:
        srows = [r for r in all_rows if r.dataset_source == src["name"]]
        dims = Counter(f"{r.width}x{r.height}" for r in srows)
        info = {"name": src["name"], "role": src["role"], "is_test_data": src["is_test_data"], "n_images": len(srows),
                "annotation_file": src["annotation_file"], "annotation_level": src["annotation_level"],
                "top_dimensions": dims.most_common(5), "n_distinct_dimensions": len(dims),
                "splits": dict(Counter(r.split for r in srows))}
        if src["annotation_file"]:
            coco = load_coco(root / src["annotation_file"])
            anns = coco.annotations
            info["n_annotations"] = len(anns)
            info["images_in_json"] = len(coco.images)
            info["images_without_annotations"] = sum(1 for cid in coco.images if not coco.by_image.get(cid))
            info["with_bbox"] = sum(1 for a in anns if a.get("bbox"))
            info["with_polygon_mask"] = sum(1 for a in anns if isinstance(a.get("segmentation"), list) and a["segmentation"])
            info["annotations_per_image_mean"] = round(len(anns) / max(1, len(coco.images)), 2)
            files_ok = sum(1 for r in srows if r.file_exists)
            info["json_images_found_on_disk"] = f"{files_ok}/{len(srows)}"
            dist = {}
            for k, label in ((None, "category_id"), (1, "category_id_1"), (2, "category_id_2"), (3, "category_id_3")):
                catkey = "categories" if k is None else f"categories_{k}"
                if catkey in coco.categories and any(label in a for a in anns):
                    c = Counter(coco.categories[catkey].get(a[label], f"?{a[label]}") for a in anns if label in a)
                    dist[label] = dict(sorted(c.items(), key=lambda kv: str(kv[0])))
            info["label_distribution"] = dist
            if "category_id_1" in anns[0] and "category_id_2" in anns[0]:
                bad = sum(1 for a in anns if not is_valid_fdi(annotation_fdi(a, coco.categories) or 0, False))
                info["invalid_fdi_combinations"] = bad
                info["distinct_fdi_teeth"] = len({annotation_fdi(a, coco.categories) for a in anns})
        out["sources"].append(info)

    # duplicates by identical pixels
    by_hash = defaultdict(list)
    for r in all_rows:
        if r.content_hash:
            by_hash[r.content_hash].append(r)
    groups = [g for g in by_hash.values() if len(g) > 1]
    pair_counter = Counter(tuple(sorted({r.dataset_source for r in g})) for g in groups)
    out["duplicates"] = {
        "unique_radiographs": len(by_hash), "files": len(all_rows), "groups_with_multiple_files": len(groups),
        "groups_by_sources": [{"sources": list(k), "groups": v} for k, v in pair_counter.most_common()],
        "same_file_name_different_pixels": sum(1 for n, hs in _name_hashes(all_rows).items() if len(hs) > 1),
        "note": "The DENTEX subsets re-use file names such as train_1.png for different radiographs, and the same "
                "radiograph often appears in several subsets under different names. Image ids are source-prefixed and "
                "split groups are defined by pixel hash so identical radiographs always share a split."}

    # leakage checks over the persisted assignments
    split_of_hash = defaultdict(set)
    for r in rows:
        if r.annotation_status == "annotated" and r.split in ("train", "val", "calibration", "test"):
            split_of_hash[r.content_hash].add(r.split)
    distinct = defaultdict(set)
    for r in rows:
        if r.annotation_status == "annotated" and r.split in ("train", "val", "calibration", "test"):
            distinct[r.split].add(r.content_hash)
    out["totals"]["annotated_distinct_radiographs"] = len(set().union(*distinct.values())) if distinct else 0
    out["totals"]["distinct_radiographs_per_split"] = {k: len(v) for k, v in sorted(distinct.items())}
    out["leakage"] = {
        "annotated_radiographs_in_more_than_one_split": sum(1 for s in split_of_hash.values() if len(s) > 1),
        "unlabeled_images_identical_to_labeled": sum(1 for r in rows if r.duplicate_of and not r.is_test_data),
        "validation_data_images_identical_to_training_images": sum(1 for r in test_rows if r.duplicate_of),
        "test_split_images_identical_to_train_split_images": _test_vs_train(rows),
        "policy": "validation_data/ is unlabeled TEST DATA: never used for training or metrics. Unlabeled images that "
                  "duplicate labeled ones (duplicate_of) are excluded from the active-learning pool."}
    out["validation"] = json.loads((settings.results_dir / "validation_main.json").read_text(encoding="utf-8")).get("counts", {})

    # what can be trained
    ann = [s for s in out["sources"] if s["annotation_file"]]
    out["trainable_tasks"] = {
        "tooth_quadrant_detection": any(s["with_bbox"] for s in ann),
        "tooth_detection_with_fdi_number": any(s["annotation_level"] in ("quadrant_enumeration", "quadrant_enumeration_disease") for s in ann),
        "disease_detection_and_classification": any(s["annotation_level"] == "quadrant_enumeration_disease" for s in ann),
        "instance_segmentation": any(s["with_polygon_mask"] for s in ann),
        "note": "Availability of labels only; 'trained' status is reported separately by the model registry."}
    return out


def _name_hashes(rows):
    d = defaultdict(set)
    for r in rows:
        d[Path(r.file_path).name].add(r.content_hash)
    return d


def _test_vs_train(rows):
    t = {r.content_hash for r in rows if r.split == "test"}
    tr = {r.content_hash for r in rows if r.split == "train"}
    return len(t & tr)


def to_markdown(a: dict) -> str:
    L = ["# Dataset audit", "", f"Generated {a['generated']} from `{a['data_root']}` (state: **{a['state']}**). All values are measured from the files.", "",
         "## Totals", ""]
    t = a["totals"]
    L += [f"- Images on disk: **{t['images_on_disk']}** ({t['formats']})",
          f"- Annotated images: **{t['annotated_images']}**; unlabeled: **{t['unlabeled_images']}**; unlabeled test data: **{t['test_data_images']}**",
          f"- Distinct annotated radiographs (by pixels): **{t['annotated_distinct_radiographs']}**; per split: {t['distinct_radiographs_per_split']}",
          f"- Corrupt images: **{len(t['corrupt_images']) if isinstance(t['corrupt_images'], list) else t['corrupt_images']}**", "", "## Sources", ""]
    for s in a["sources"]:
        L += [f"### {s['name']}", "", f"- Role: {s['role']}{' (TEST DATA)' if s['is_test_data'] else ''}; images: {s['n_images']}; level: {s['annotation_level']}",
              f"- Annotation file: `{s['annotation_file']}`" if s["annotation_file"] else "- No annotation file (unlabeled)",
              f"- Dimensions: {s['top_dimensions']} ({s['n_distinct_dimensions']} distinct)", f"- Splits: {s['splits']}"]
        if s["annotation_file"]:
            L += [f"- Annotations: {s['n_annotations']} (mean {s['annotations_per_image_mean']}/image); bbox: {s['with_bbox']}; polygon masks: {s['with_polygon_mask']}",
                  f"- Images in JSON found on disk: {s['json_images_found_on_disk']}; JSON images with no annotations: {s['images_without_annotations']}"]
            for k, v in s["label_distribution"].items():
                L.append(f"- `{k}`: {v}")
            if "invalid_fdi_combinations" in s:
                L.append(f"- Invalid FDI combinations: {s['invalid_fdi_combinations']}; distinct teeth: {s['distinct_fdi_teeth']}")
        L.append("")
    d = a["duplicates"]
    L += ["## Duplicates and leakage", "",
          f"- {d['files']} files contain only **{d['unique_radiographs']}** distinct radiographs; {d['groups_with_multiple_files']} pixel-identical groups span several files.",
          f"- File names that refer to different pixels in different folders: {d['same_file_name_different_pixels']}.", f"- {d['note']}"]
    for g in d["groups_by_sources"]:
        L.append(f"  - {g['groups']} × {', '.join(g['sources'])}")
    lk = a["leakage"]
    L += ["", *(f"- {k.replace('_', ' ')}: **{v}**" for k, v in lk.items() if k != "policy"), f"- Policy: {lk['policy']}", "",
          "## Validation issue counts", "", f"`{a['validation'] or 'no issues'}`", "", "## Tasks the labels support", ""]
    L += [f"- {k.replace('_', ' ')}: {'yes' if v else 'no'}" for k, v in a["trainable_tasks"].items() if k != "note"]
    L += ["", a["trainable_tasks"]["note"], ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-decode", action="store_true", help="skip full image verification (faster)")
    ns = ap.parse_args()
    s = get_settings()
    rep = audit(s, decode=not ns.no_decode)
    outdir = s.data_root / "reports"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "dataset_audit.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    (outdir / "dataset_audit.md").write_text(to_markdown(rep), encoding="utf-8")
    print("wrote", outdir / "dataset_audit.json", "and dataset_audit.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
