#!/usr/bin/env python
"""Error attribution for CV5-BASE run 1: where are end-to-end errors lost - detection, matching or classification?

    .venv\\Scripts\\python.exe scripts\\cv5_error_attribution.py

Post-hoc DESCRIPTIVE analysis of the BASE reference from ARCHIVED outputs only (no training, no new predictions, no candidate):
* kaggle/artifacts_cv5_run1/{oof_predictions.csv, detector_boxes_pool.json, cv5_results.json, caries_confusion_findings.csv},
  each checked against the run's SHA256SUMS.txt;
* finding boxes from data/splits/combined_train.csv and combined_validation.csv (the manifests of the CV5 bundle; their SHA-256
  must equal the bundle's copies). The calibration and test manifests are never opened.
Matching is the production rule (kaggle/dentamind_kaggle.match: score >= 0.3, greedy one-to-one, IoU >= 0.5).

Categories per primary finding (counts of findings; classification errors are counted per finding x seed):
  U0 no detector box overlaps the finding (max IoU = 0)
  U1 a detector box overlaps but with IoU < 0.5 (localisation / box-definition mismatch)
  U2 a box with IoU >= 0.5 exists but was assigned one-to-one to another finding (matching conflict)
  M  matched; then per seed: correct, or misclassified (C = classification error)
  Among misclassified Caries / Deep Caries findings, those confused by all 5 seeds on GT boxes are flagged "consistent confusion
  (candidate for clinician review)". This is NOT a label error.
Gates (nothing is written unless all pass): matched flags equal the archived `detector_matched` for every finding; recomputed
end-to-end recall equals the archived per-seed values; the consistent-confusion count equals the archived count.
Outputs reports/cv5_error_attribution.json and .md (never overwritten).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "kaggle" / "artifacts_cv5_run1"
BUNDLE = ROOT / "kaggle" / "dist" / "dentamind_kaggle_bundle.zip"
MANIFESTS = ["data/splits/combined_train.csv", "data/splits/combined_validation.csv"]
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
SEEDS = [42, 43, 44, 45, 46]
sys.path.insert(0, str(ROOT / "kaggle"))
sys.path.insert(0, str(ROOT / "scripts" / "dataset"))
import dentamind_kaggle as DK  # noqa: E402  (match, box_iou, DET_SCORE, IOU_THR)


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def checked(rel: str) -> str:
    sums = {}
    for line in (ART / "SHA256SUMS.txt").read_text().splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*").replace("\\", "/")] = h
    h = sha(ART / rel)
    if sums.get(rel) != h:
        raise SystemExit(f"{rel} does not match SHA256SUMS.txt")
    return h


def analyse() -> dict:
    hashes = {f"kaggle/artifacts_cv5_run1/{r}": checked(r) for r in
              ("oof_predictions.csv", "detector_boxes_pool.json", "cv5_results.json", "caries_confusion_findings.csv")}
    z = zipfile.ZipFile(BUNDLE)
    for m in MANIFESTS:
        if hashlib.sha256(z.read(m)).hexdigest() != sha(ROOT / m):
            raise SystemExit(f"{m} differs from the CV5 bundle copy")
        hashes[m] = sha(ROOT / m)
    oof = list(csv.DictReader(open(ART / "oof_predictions.csv", encoding="utf-8")))
    ids = {r["sample_id"] for r in oof}
    man = {}
    for m in MANIFESTS:
        for r in csv.DictReader(open(ROOT / m, encoding="utf-8")):
            if r["sample_id"] in ids:
                man[r["sample_id"]] = r
    if len(man) != len(oof):
        raise SystemExit(f"{len(oof) - len(man)} primary findings missing from the manifests")
    det = json.loads((ART / "detector_boxes_pool.json").read_text(encoding="utf-8"))
    res = json.loads((ART / "cv5_results.json").read_text(encoding="utf-8"))

    by_img = defaultdict(list)
    for r in oof:
        by_img[man[r["sample_id"]]["image_path"]].append(r["sample_id"])
    cat, max_iou = {}, {}
    for path, sids in by_img.items():
        key = man[sids[0]]["project_image_id"]
        boxes = [d[:4] for d in det.get(key, []) if d[4] >= DK.DET_SCORE]
        gts = []
        for s in sids:
            x, y, w, h = json.loads(man[s]["bbox_xywh"])
            gts.append([x, y, x + w, y + h])
        m = DK.match(gts, boxes)
        for k, s in enumerate(sids):
            ious = [DK.box_iou(gts[k], b) for b in boxes]
            mx = max(ious, default=0.0)
            max_iou[s] = mx
            cat[s] = "M" if k in m else ("U0" if mx == 0 else "U1" if mx < DK.IOU_THR else "U2")

    # gate 1: matched flags
    bad = [r["sample_id"] for r in oof if (cat[r["sample_id"]] == "M") != (r["detector_matched"] == "True")]
    if bad:
        raise SystemExit(f"gate 1 failed: {len(bad)} findings' matched flag differs from the archive, e.g. {bad[:3]}")

    def argmax(r, s, setting):
        v = [r[f"s{s}_{setting}_{c}"] for c in CLASSES]
        return None if any(x in ("", "nan", "NaN") for x in v) else int(np.argmax([float(x) for x in v]))

    conf = {r["sample_id"]: int(r["seeds_other_caries_gt"]) for r in
            csv.DictReader(open(ART / "caries_confusion_findings.csv", encoding="utf-8"))}
    per = {c: {"findings": 0, "U0": 0, "U1": 0, "U2": 0, "M": 0, "pred_total": 0, "pred_correct": 0, "pred_misclassified": 0,
               "pred_unmatched": 0, "misclassified_as": defaultdict(int), "consistent_confusion_findings": 0,
               "max_iou_unmatched": []} for c in CLASSES}
    e2e_hits = {s: defaultdict(int) for s in SEEDS}
    for r in oof:
        sid, c = r["sample_id"], r["true_class"]
        t = CLASSES.index(c)
        p = per[c]
        p["findings"] += 1
        p[cat[sid]] += 1
        if cat[sid] != "M":
            p["max_iou_unmatched"].append(max_iou[sid])
        if conf.get(sid) == 5:
            p["consistent_confusion_findings"] += 1
        for s in SEEDS:
            p["pred_total"] += 1
            if cat[sid] != "M":
                p["pred_unmatched"] += 1
                continue
            k = argmax(r, s, "det")
            if k == t:
                p["pred_correct"] += 1
                e2e_hits[s][c] += 1
            else:
                p["pred_misclassified"] += 1
                p["misclassified_as"][CLASSES[k]] += 1

    # gate 2: end-to-end recall reproduces the archive
    for s in SEEDS:
        for c in CLASSES:
            got = e2e_hits[s][c] / per[c]["findings"]
            arch = res["pooled_per_seed"][str(s)]["end_to_end"]["recall"][c]
            if abs(got - arch) > 1e-12:
                raise SystemExit(f"gate 2 failed: seed {s} {c} end-to-end recall {got} != archived {arch}")
    # gate 3: consistent-confusion count
    n110 = sum(p["consistent_confusion_findings"] for p in per.values())
    if n110 != sum(res["caries_confusion"]["confused_by_all_seeds_gt"].values()):
        raise SystemExit(f"gate 3 failed: {n110} consistent confusions vs archived {res['caries_confusion']['confused_by_all_seeds_gt']}")

    out = {}
    for c, p in per.items():
        n, tot = p["findings"], p["pred_total"]
        e2e_err = p["pred_unmatched"] + p["pred_misclassified"]
        mi = p.pop("max_iou_unmatched")
        out[c] = {**{k: v for k, v in p.items() if k != "misclassified_as"},
                  "misclassified_as": dict(p["misclassified_as"]),
                  "share_findings_unmatched": (p["U0"] + p["U1"] + p["U2"]) / n,
                  "share_of_end_to_end_errors_from_detection_or_matching": p["pred_unmatched"] / e2e_err if e2e_err else None,
                  "share_of_end_to_end_errors_from_classification": p["pred_misclassified"] / e2e_err if e2e_err else None,
                  "end_to_end_recall_mean": p["pred_correct"] / tot,
                  "median_max_iou_of_unmatched": float(np.median(mi)) if mi else None}
    return {"format": "dentamind-cv5-error-attribution-v1",
            "status": "post-hoc descriptive analysis of the BASE reference from archived outputs; not an acceptance criterion; no "
                      "candidate, calibration or test data involved; 'consistent confusion' is not a label error",
            "script_sha256": sha(Path(__file__)), "inputs": hashes,
            "rule": {"detector_score_min": DK.DET_SCORE, "iou_min": DK.IOU_THR, "matching": "greedy one-to-one by IoU (production)"},
            "gates": {"matched_flags_reproduce_archive": True, "end_to_end_recall_reproduces_archive": True,
                      "consistent_confusion_count_reproduces_archive": n110},
            "per_class": out}


def main():
    out_j, out_m = ROOT / "reports" / "cv5_error_attribution.json", ROOT / "reports" / "cv5_error_attribution.md"
    if out_j.exists() or out_m.exists():
        raise SystemExit("cv5_error_attribution.* exists: write a new version instead of overwriting")
    t = analyse()
    with open(out_j, "x", encoding="utf-8") as fh:
        json.dump(t, fh, indent=1)
    L = ["# CV5-BASE run 1: error attribution (post-hoc, descriptive)", "",
         f"Script `scripts/cv5_error_attribution.py` (sha256 `{t['script_sha256']}`). All gates passed: matched flags, end-to-end "
         "recall and the consistent-confusion count reproduce the archive exactly.", "",
         "| Class | Findings | No overlapping box (U0) | Box IoU < 0.5 (U1) | Matching conflict (U2) | Matched | Unmatched share | "
         "End-to-end errors from detection / matching | from classification | Consistent confusion (GT, 5/5 seeds) |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for c, p in t["per_class"].items():
        L.append(f"| {c} | {p['findings']} | {p['U0']} | {p['U1']} | {p['U2']} | {p['M']} | {p['share_findings_unmatched']:.3f} | "
                 f"{p['share_of_end_to_end_errors_from_detection_or_matching']:.3f} | {p['share_of_end_to_end_errors_from_classification']:.3f} | "
                 f"{p['consistent_confusion_findings']} |")
    L += ["", "Classification errors on matched detector boxes (finding x seed), by predicted class:", ""]
    L += [f"* {c}: {json.dumps(p['misclassified_as'])}" for c, p in t["per_class"].items()]
    L += ["", "Inputs (SHA-256):", ""] + [f"* `{k}` `{v}`" for k, v in t["inputs"].items()]
    with open(out_m, "x", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L[4:10]))


if __name__ == "__main__":
    main()
