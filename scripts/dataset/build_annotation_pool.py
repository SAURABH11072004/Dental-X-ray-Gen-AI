#!/usr/bin/env python
"""Annotation pool: every UNIQUE radiograph that has no diagnosis label yet, deduplicated against all labelled radiographs.

    .venv\\Scripts\\python.exe scripts\\dataset\\build_annotation_pool.py

Sources (only images already obtained from official releases):
  * DENTEX quadrant_enumeration subset (tooth boxes + FDI, no diagnoses)
  * DENTEX quadrant subset (quadrant boxes only)
  * DENTEX unlabelled subset (no annotations)
  * DENTEX official test images whose radiograph is not already in the project (Turkish taxonomy -> review hints only)
  * Hanoi periapical dataset originals, if downloaded and extracted (PAI 3-5 lesion boxes -> review hints only)

Rules: one row per radiograph group (exact SHA-256 + confirmed near duplicate, same rule as the leakage check). A group that
contains any diagnosis-labelled radiograph is NOT in the pool. ``split_lock``:
  train       - twin of a project TRAIN radiograph: new labels may join training
  eval_locked - twin of a project val / calibration / test radiograph: must not enter training (kept for a later, approved
                evaluation protocol)
  unassigned  - new radiograph: split decided by a documented protocol before any use (default proposal: training)
Writes data/annotation/annotation_pool.csv and reports/annotation_pool_audit.json. Never writes labels.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_combined_manifest import UF  # noqa: E402
from dsutil import dhash, near_duplicate_pairs, read_csv, sha256_file, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = DATA / "annotation"
TEST_LABELS = DATA / "raw/external/dentex_hf/test_data/disease/label"
HANOI = DATA / "raw/external/hanoi_periapical"
FIELDS = ["pool_id", "source_dataset", "image_id", "image_path", "image_sha256", "width", "height", "radiograph_group",
          "split_lock", "tooth_boxes_available", "external_hint", "duplicate_members", "notes"]


def turkish_hint(stem):
    f = TEST_LABELS / f"{stem}.json"
    if not f.is_file():
        return ""
    shapes = json.loads(f.read_text(encoding="utf-8"))["shapes"]
    keep = [s["label"] for s in shapes if s["label"].split("-")[1:2] and s["label"].split("-")[1] in ("lezyon", "küretaj", "çürük", "gömülü")]
    return "DENTEX-test Turkish labels (different taxonomy, unverified): " + ", ".join(sorted(keep)) if keep else ""


def hanoi_items():
    """Hanoi originals that have an annotation file. Returns [] until images are extracted."""
    img_dir = next((p for p in HANOI.glob("**/Original JPG Images") if p.is_dir()), None)
    ann_dir = next((p for p in HANOI.glob("annots/**/Image Annots") if p.is_dir()), None)
    if not img_dir or not ann_dir:
        return []
    out = []
    for img in sorted(img_dir.glob("*.jpg")):
        xml = ann_dir / f"{img.stem}.xml"
        hint = ""
        if xml.is_file():
            objs = ET.parse(xml).getroot().findall("object")
            hint = f"Hanoi PAI lesion boxes (unverified mapping): {len(objs)} x PAI " + ",".join(o.findtext("name") for o in objs)
        out.append({"source_dataset": "hanoi_periapical", "image_id": f"hanoi_{img.stem}",
                    "image_path": img.relative_to(DATA).as_posix(), "tooth_boxes_available": "no (model suggestion)",
                    "external_hint": hint, "has_annotation": xml.is_file()})
    return out


def main():
    man = read_csv(DATA / "processed/manifest.csv")
    vman = read_csv(DATA / "processed/manifest_test_data.csv")
    assign = json.loads((DATA / "splits/dentex_splits.json").read_text(encoding="utf-8"))["assignments"]
    dh = json.loads((DATA / "processed/dhash_cache.json").read_text(encoding="utf-8"))

    items = {}   # path -> info
    for r in man:
        sp = assign.get(r["image_id"])
        items[r["file_path"]] = {"sha": r["content_hash"], "image_id": r["image_id"], "source": r["dataset_source"],
                                 "level": r["annotation_level"], "split": sp if sp in ("train", "val", "calibration", "test") else None,
                                 "labelled_dx": r["annotation_level"] == "quadrant_enumeration_disease" and r["annotation_status"] == "annotated",
                                 "w": r["width"], "h": r["height"], "dhash": dh.get(r["file_path"])}
    for r in vman:   # official DENTEX validation: diagnosis-labelled (validation_triple.json)
        items[r["file_path"]] = {"sha": r["content_hash"], "image_id": r["image_id"], "source": "dentex_official_val",
                                 "level": "quadrant_enumeration_disease", "split": None, "labelled_dx": True,
                                 "w": r["width"], "h": r["height"], "dhash": None}
    tdir = DATA / "raw/external/dentex_hf/test_data/disease/input"
    for p in sorted(tdir.glob("*.png")):
        items[p.relative_to(DATA).as_posix()] = {"sha": sha256_file(p), "image_id": f"dxtest_{p.stem}", "source": "dentex_official_test",
                                                 "level": "none", "split": None, "labelled_dx": False, "w": "", "h": "", "dhash": None,
                                                 "hint": turkish_hint(p.stem)}
    for h in hanoi_items():
        p = DATA / h["image_path"]
        items[h["image_path"]] = {"sha": sha256_file(p), "image_id": h["image_id"], "source": "hanoi_periapical", "level": "none",
                                  "split": None, "labelled_dx": False, "w": "", "h": "", "dhash": None, "hint": h["external_hint"]}
    for k, v in items.items():
        if v["dhash"] is None:
            v["dhash"] = dhash(DATA / k)

    uf = UF()
    by_sha = defaultdict(list)
    for k, v in items.items():
        uf.find(k)
        by_sha[v["sha"]].append(k)
    for ks in by_sha.values():
        for k in ks[1:]:
            uf.union(ks[0], k)
    near, n_cand, max_corr = near_duplicate_pairs([(k, v["sha"], v["dhash"], DATA / k) for k, v in items.items()])
    for a, b, _d, _r in near:
        uf.union(a, b)
    groups = defaultdict(list)
    for k in items:
        groups[uf.find(k)].append(k)

    pref = {"training_data/quadrant_enumeration": 0, "training_data/quadrant": 1, "dentex_official_test": 2, "training_data/unlabelled": 3,
            "hanoi_periapical": 4}
    rows, excluded = [], Counter()
    for root, ks in sorted(groups.items()):
        if any(items[k]["labelled_dx"] for k in ks):
            excluded["group already has diagnosis labels"] += 1
            continue
        splits = {items[k]["split"] for k in ks} - {None}
        if len(splits) > 1:
            excluded["group spans several project splits"] += 1
            continue
        lock = "unassigned" if not splits else ("train" if splits == {"train"} else "eval_locked")
        rep = min(ks, key=lambda k: (pref.get(items[k]["source"], 9), k))   # representative: richest annotation level
        v = items[rep]
        has_boxes = any(items[k]["level"] == "quadrant_enumeration" for k in ks)
        rows.append({"source_dataset": v["source"].replace("training_data/", "dentex_"), "image_id": v["image_id"], "image_path": rep,
                     "image_sha256": v["sha"], "width": v["w"], "height": v["h"], "radiograph_group": "",
                     "split_lock": lock, "tooth_boxes_available": "yes (DENTEX enumeration GT, tooth + FDI)" if has_boxes else "no (model suggestion)",
                     "external_hint": next((items[k].get("hint") for k in ks if items[k].get("hint")), ""),
                     "duplicate_members": ";".join(items[k]["image_id"] for k in ks if k != rep), "notes": ""})
    rows.sort(key=lambda r: (r["source_dataset"], r["image_id"]))
    for i, r in enumerate(rows):
        r["pool_id"] = f"P{i:05d}"
        r["radiograph_group"] = f"pool_g{i:05d}"
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "annotation_pool.csv", rows, FIELDS)
    summary = Counter((r["source_dataset"], r["split_lock"], r["tooth_boxes_available"][:3]) for r in rows)
    audit = {"generated": datetime.now(timezone.utc).isoformat(), "script": "scripts/dataset/build_annotation_pool.py",
             "images_considered": len(items), "radiograph_groups": len(groups), "pool_radiographs": len(rows),
             "excluded_groups": dict(excluded),
             "pool_by_source_lock_boxes": {" | ".join(k): v for k, v in sorted(summary.items())},
             "near_duplicates": {"rule": "dHash Hamming <= 4 and different SHA-256, confirmed by thumbnail correlation >= 0.97",
                                 "hash_candidates": n_cand, "confirmed": len(near), "max_candidate_correlation": max_corr, "pairs": near},
             "hanoi_included": any(r["source_dataset"] == "hanoi_periapical" for r in rows),
             "policy": "pool radiographs carry NO labels; teeth without a clinician-confirmed finding are never treated as healthy",
             "pool_sha256": sha256_file(OUT / "annotation_pool.csv")}
    (ROOT / "reports/annotation_pool_audit.json").write_text(json.dumps(audit, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: audit[k] for k in ("images_considered", "radiograph_groups", "pool_radiographs", "excluded_groups",
                                            "pool_by_source_lock_boxes", "hanoi_included")}, indent=1))
    print("near duplicates confirmed:", len(near), "of", n_cand, "hash candidates")


if __name__ == "__main__":
    main()
