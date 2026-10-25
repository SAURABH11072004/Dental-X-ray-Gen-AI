#!/usr/bin/env python
"""Build deterministic combined train / validation / calibration / test manifests for the finding classifier.

    .venv\\Scripts\\python.exe scripts\\dataset\\build_combined_manifest.py [--official-val-role train|exclude]

Sources (scripts/dataset/sources.py):
  * dentex_train_disease  - DENTEX disease subset; every image keeps its persisted project split (data/splits/dentex_splits.json).
  * dentex_official_val   - DENTEX official validation labels (same taxonomy). Default role: TRAINING ONLY (Experiment D). The
                            project validation / calibration / test sets are left exactly as they were, so results stay comparable.
  * dentex_official_test  - inventoried, never mapped (different taxonomy); its images still take part in duplicate grouping.

Leakage rules:
  * radiograph groups = connected components of "same SHA-256" and "confirmed near-duplicate" (dHash <= 4 + thumbnail r >= 0.97)
    over every annotated DENTEX image (all subsets), the official validation images and the official test images;
  * a group inherits the persisted project split of any member; a group whose members carry different splits is excluded;
  * an external image whose group is already in validation / calibration / test is EXCLUDED (adding its labels would change a fixed
    evaluation set); one whose group is in train joins train;
  * every crop of one radiograph is in the same split (by construction: split is a property of the group).
No patient ids exist, so patient-level separation is not claimed.

Writes data/splits/combined_{train,validation,calibration,test}.csv, data/splits/combined_excluded.csv,
reports/combined_split_audit.json, reports/class_imbalance_after.csv, reports/class_distribution_after.png.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import parse_dentex_coco, parse_labelme_tr  # noqa: E402
from audit_class_imbalance import class_table, plot  # noqa: E402
from dsutil import CLASSES, crop_box_xyxy, dhash, near_duplicate_pairs, read_csv, sha256_file, write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SEED = 42                     # the persisted DENTEX split seed; no new random draw is made by this script
OUT_SPLIT = {"train": "train", "val": "validation", "calibration": "calibration", "test": "test"}
EVAL_SUBSET = {"train": "train",
               "val": "dentex_project_val (fixed 2026-10-14; used for epoch selection in every earlier experiment)",
               "calibration": "dentex_project_calibration (abstention / calibration fitting only)",
               "test": "dentex_project_test (previously used; see data/reports/test_set_ledger.json)"}
FIELDS = ["sample_id", "split", "eval_subset", "source_dataset", "source_split", "project_image_id", "original_image_id", "original_file_name",
          "annotation_id", "fdi_tooth", "target_class", "class_index", "original_label", "annotation_type", "image_type",
          "image_path", "image_sha256", "image_width", "image_height", "bbox_xywh", "crop_xyxy", "radiograph_group", "conversion"]


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--official-val-role", choices=["train", "exclude"], default="train")
    ap.add_argument("--include-verified", action="store_true",
                    help="P1 (approved 2026-10-16): add clinician-verified labels from data/annotation/verified_findings.csv to TRAINING only")
    a = ap.parse_args()

    man = read_csv(DATA / "processed/manifest.csv")
    vman = read_csv(DATA / "processed/manifest_test_data.csv")
    split_file = json.loads((DATA / "splits/dentex_splits.json").read_text(encoding="utf-8"))
    assign = split_file["assignments"]
    dh_cache = json.loads((DATA / "processed/dhash_cache.json").read_text(encoding="utf-8"))

    # ---- image table: path (relative to DATA) -> sha, project split, dhash
    images = {}
    for r in man:
        if r["annotation_status"] != "annotated":
            continue
        sp = assign.get(r["image_id"])
        images[r["file_path"]] = {"sha": r["content_hash"], "split": sp if sp in OUT_SPLIT else None, "source": r["dataset_source"],
                                  "dhash": dh_cache.get(r["file_path"]), "image_id": r["image_id"]}
    for r in vman:
        images[r["file_path"]] = {"sha": r["content_hash"], "split": None, "source": "dentex_official_val", "dhash": None,
                                  "image_id": r["image_id"]}
    test_dir = "raw/external/dentex_hf/test_data/disease/input"
    for p in sorted((DATA / test_dir).glob("*.png")):
        images[f"{test_dir}/{p.name}"] = {"sha": sha256_file(p), "split": None, "source": "dentex_official_test", "dhash": None,
                                                 "image_id": None}
    for k, v in images.items():
        if v["dhash"] is None:
            v["dhash"] = dhash(DATA / k)

    # ---- groups
    uf = UF()
    by_sha = defaultdict(list)
    for k, v in images.items():
        uf.find(k)
        by_sha[v["sha"]].append(k)
    for ks in by_sha.values():
        for k in ks[1:]:
            uf.union(ks[0], k)
    near, n_cand, max_corr = near_duplicate_pairs([(k, v["sha"], v["dhash"], DATA / k) for k, v in images.items()])
    for x, y, _d, _r in near:
        uf.union(x, y)
    groups = defaultdict(list)
    for k in images:
        groups[uf.find(k)].append(k)
    gid = {root: f"g{n:05d}" for n, root in enumerate(sorted(groups))}
    g_split, conflicts = {}, []
    for root, ks in groups.items():
        s = {images[k]["split"] for k in ks} - {None}
        if len(s) > 1:
            conflicts.append({"group": gid[root], "members": ks, "splits": sorted(s)})
        g_split[root] = s.pop() if len(s) == 1 else ("CONFLICT" if s else None)

    # ---- annotations
    dis_dir = "training_data/quadrant-enumeration-disease"
    _, rec_tr = parse_dentex_coco(DATA / dis_dir / "train_quadrant_enumeration_disease.json", f"{dis_dir}/xrays", "dentex_train_disease")
    _, rec_va = parse_dentex_coco(DATA / "raw/external/dentex_hf/validation_triple.json",
                                  "validation_data/quadrant_enumeration_disease/xrays", "dentex_official_val")
    _, rec_te = parse_labelme_tr(DATA / "raw/external/dentex_hf/test_data/disease/label", test_dir, "dentex_official_test")

    kept, excluded = [], []
    for r in rec_tr + rec_va + rec_te:
        r = dict(r)
        r["sample_id"] = f"{r['source_dataset']}:{r['original_image_id']}:{r['annotation_id']}"
        r["source_split"] = {"dentex_train_disease": "official train", "dentex_official_val": "official validation",
                             "dentex_official_test": "official test"}[r["source_dataset"]]
        img = images.get(r["image_path"])
        if img is None:
            excluded.append({**r, "reason": "image not in the verified image table (missing or not annotated)"})
            continue
        root = uf.find(r["image_path"])
        r["radiograph_group"], r["image_sha256"], r["image_type"] = gid[root], img["sha"], "panoramic"
        r["project_image_id"] = img["image_id"]
        if not r["target_class"]:
            excluded.append({**r, "reason": r["mapping_note"]})
            continue
        x1, y1, x2, y2 = crop_box_xyxy(r["bbox_xywh"], r["image_width"], r["image_height"])
        if x2 - x1 < 4 or y2 - y1 < 4:
            excluded.append({**r, "reason": "padded crop smaller than 4 px (production crop rule)"})
            continue
        r["crop_xyxy"] = [round(v, 2) for v in (x1, y1, x2, y2)]
        gs = g_split[root]
        if gs == "CONFLICT":
            excluded.append({**r, "reason": "radiograph group spans several project splits"})
            continue
        if r["source_dataset"] == "dentex_train_disease":
            split = gs
            if split is None:
                excluded.append({**r, "reason": "disease image without a persisted split"})
                continue
            conv = "none (original DENTEX label and box)"
        else:
            if gs in ("val", "calibration", "test"):
                excluded.append({**r, "reason": f"byte-identical / near-duplicate of a project {gs} radiograph; adding its labels would "
                                                f"change a fixed evaluation set"})
                continue
            if a.official_val_role == "exclude":
                excluded.append({**r, "reason": "--official-val-role exclude"})
                continue
            split = "train"
            conv = ("official validation label, same taxonomy and category ids as training; "
                    + ("radiograph also in a DENTEX training subset (train split)" if gs == "train" else "new radiograph"))
        r["split"], r["eval_subset"], r["class_index"] = OUT_SPLIT[split], EVAL_SUBSET[split], CLASSES.index(r["target_class"])
        r["conversion"] = conv
        kept.append(r)

    verified_info = {"included": False}
    if a.include_verified:
        from verified_to_manifest import verified_training_rows
        vrows, vskipped = verified_training_rows(DATA / "annotation/verified_findings.csv", DATA / "annotation/annotation_pool.csv",
                                                 DATA / "splits", DATA)
        eval_shas = {r["image_sha256"] for r in kept if r["split"] != "train"}
        assert not ({r["image_sha256"] for r in vrows} & eval_shas), "verified row on an evaluation radiograph"
        kept.extend(vrows)
        vf = DATA / "annotation/verified_findings.csv"
        verified_info = {"included": True, "rows": len(vrows), "radiographs": len({r["image_sha256"] for r in vrows}),
                         "skipped": [{"region": k, "reason": w} for k, w in vskipped],
                         "verified_findings_sha256": sha256_file(vf) if vf.is_file() else None}
    kept.sort(key=lambda r: (r["split"], r["source_dataset"], r["image_path"], str(r["annotation_id"])))
    out_paths = {}
    for sp in OUT_SPLIT.values():
        p = DATA / f"splits/combined_{sp}.csv"
        write_csv(p, [r for r in kept if r["split"] == sp], FIELDS)
        out_paths[sp] = p
    write_csv(DATA / "splits/combined_excluded.csv", excluded, FIELDS + ["reason"])

    # ---- audit
    by_split_groups = defaultdict(set)
    by_split_sha = defaultdict(set)
    for r in kept:
        by_split_groups[r["split"]].add(r["radiograph_group"])
        by_split_sha[r["split"]].add(r["image_sha256"])
    names = list(OUT_SPLIT.values())
    overlaps = {f"{x} vs {y}": {"groups": len(by_split_groups[x] & by_split_groups[y]), "sha256": len(by_split_sha[x] & by_split_sha[y])}
                for i, x in enumerate(names) for y in names[i + 1:]}
    before = read_csv(ROOT / "reports/class_imbalance_before.csv")
    legacy_val = {(r["original_file_name"], r["annotation_id"]) for r in rec_tr if r["target_class"]
                  and g_split[uf.find(r["image_path"])] == "val"}
    new_val = {(r["original_file_name"], r["annotation_id"]) for r in kept if r["split"] == "validation"}
    legacy_test = {(r["original_file_name"], r["annotation_id"]) for r in rec_tr if r["target_class"]
                   and g_split[uf.find(r["image_path"])] == "test"}
    new_test = {(r["original_file_name"], r["annotation_id"]) for r in kept if r["split"] == "test"}
    dist = defaultdict(lambda: defaultdict(Counter))
    for r in kept:
        dist[r["split"]][r["source_dataset"]][r["target_class"]] += 1
    ext_imgs = {r["image_path"] for r in kept if r["source_dataset"] == "dentex_official_val"}
    audit = {
        "generated": datetime.now(timezone.utc).isoformat(), "script": "scripts/dataset/build_combined_manifest.py",
        "seed": SEED, "seed_note": "no new random split: DENTEX images keep their persisted seed-42 assignment; external data is "
                                   "assigned by rule (deterministic)",
        "official_val_role": a.official_val_role,
        "clinician_verified": verified_info,
        "inputs_sha256": {"manifest.csv": sha256_file(DATA / "processed/manifest.csv"),
                          "manifest_test_data.csv": sha256_file(DATA / "processed/manifest_test_data.csv"),
                          "dentex_splits.json": sha256_file(DATA / "splits/dentex_splits.json"),
                          "split_assignments_fingerprint": split_file.get("fingerprint"),
                          "train_quadrant_enumeration_disease.json": sha256_file(DATA / dis_dir / "train_quadrant_enumeration_disease.json"),
                          "validation_triple.json": sha256_file(DATA / "raw/external/dentex_hf/validation_triple.json"),
                          "test_data.zip": "ed396d6daa133264ddb0ecdbed3f963868d2a31344ba0fab929a6a1773d82ce2"},
        "outputs_sha256": {f"combined_{k}.csv": sha256_file(v) for k, v in out_paths.items()}
                          | {"combined_excluded.csv": sha256_file(DATA / "splits/combined_excluded.csv")},
        "samples_per_split": {k: len([r for r in kept if r["split"] == k]) for k in names},
        "radiographs_per_split": {k: len(by_split_groups[k]) for k in names},
        "class_distribution_by_split_and_source": {k: {s: dict(c) for s, c in v.items()} for k, v in dist.items()},
        "leakage_checks": {"split_overlaps": overlaps,
                           "all_zero": all(v["groups"] == 0 and v["sha256"] == 0 for v in overlaps.values()),
                           "group_split_conflicts": conflicts,
                           "near_duplicates": {"method": "dHash Hamming <= 4 and different SHA-256, confirmed by 256x128 thumbnail "
                                                         "correlation >= 0.97", "images_checked": len(images), "hash_candidates": n_cand,
                                               "confirmed": len(near), "max_candidate_correlation": max_corr, "pairs": near},
                           "patient_level": "not possible: no patient ids in DENTEX; groups are radiograph-level"},
        "fixed_evaluation_sets": {"validation_identical_to_project_val": new_val == legacy_val, "validation_findings": len(new_val),
                                  "test_identical_to_project_test": new_test == legacy_test, "test_findings": len(new_test),
                                  "test_status": "previously used project test split; the official DENTEX test set is NOT a usable "
                                                 "test set for this taxonomy (labels not mapped) - no new independent test set exists"},
        "external_contribution": {"dentex_official_val": {"images_contributing": len(ext_imgs),
                                                          "findings": dict(dist["train"]["dentex_official_val"])},
                                  "dentex_official_test": {"findings": 0, "reason": "taxonomy not equivalent (see candidates report)"}},
        "excluded": {"count": len(excluded), "by_reason": dict(Counter(e["reason"][:90] for e in excluded))},
        "official_test_overlap_with_dentex_training_subsets": sum(
            1 for k, v in images.items() if v["source"] == "dentex_official_test"
            and any(images[m]["source"].startswith("training_data") for m in groups[uf.find(k)])),
        "domain": "all included images are DENTEX panoramic radiographs from the same release; no bitewing / periapical images mixed",
    }
    (ROOT / "reports/combined_split_audit.json").write_text(json.dumps(audit, indent=1, default=str), encoding="utf-8")

    # ---- after-tables (same layout as the before-table, plus per-source rows for train)
    rows = class_table([{**r, "image_path": r["image_path"]} for r in kept],
                       lambda rec: {"train": "train", "validation": "val", "calibration": "calibration", "test": "test"}[rec["split"]])
    b = {(r["split"], r["class"]): int(r["crops_after_crop_rule"]) for r in before}
    for r in rows:
        r["crops_before"] = b.get((r["split"], r["class"]), "")
        r["change"] = r["crops_after_crop_rule"] - int(r["crops_before"]) if r["crops_before"] != "" else ""
    for src in ("dentex_train_disease", "dentex_official_val"):
        for c in CLASSES:
            rows.append({"split": f"train[{src}]", "class": c, "findings": dist["train"][src][c], "crops_after_crop_rule": dist["train"][src][c],
                         "radiographs_with_class": len({r["image_path"] for r in kept if r["split"] == "train" and r["source_dataset"] == src
                                                        and r["target_class"] == c})})
    write_csv(ROOT / "reports/class_imbalance_after.csv", rows,
              ["split", "class", "findings", "crops_after_crop_rule", "crops_before", "change", "radiographs_with_class",
               "share_of_split_crops", "radiographs_in_split_with_any_finding"])
    plot([r for r in rows if not r["split"].startswith("train[")], ROOT / "reports/class_distribution_after.png",
         f"AFTER integration (official DENTEX validation labels -> {a.official_val_role}); validation/calibration/test unchanged")
    print(json.dumps({k: audit[k] for k in ("samples_per_split", "radiographs_per_split", "external_contribution", "excluded",
                                            "fixed_evaluation_sets", "official_test_overlap_with_dentex_training_subsets")}, indent=1))
    print("overlaps all zero:", audit["leakage_checks"]["all_zero"], "| near-dups confirmed:", len(near), "| conflicts:", len(conflicts))


if __name__ == "__main__":
    main()
