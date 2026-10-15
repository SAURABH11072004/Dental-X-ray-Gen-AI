"""Does mask / detection instability (flip-pass signals) actually flag segmentation / detection errors?  Measured on the VALIDATION split only.

For each validation radiograph the live API runs the full pipeline (real models). Each region's ``mask_instability`` and ``detection_instability`` are compared with
the DENTEX ground truth: mask IoU against the matched ground-truth polygon, and whether the detected box has any ground-truth tooth at IoU >= 0.5 (else: false positive).
Reported: AUROC of the signal for "mask IoU < 0.8" and for "false-positive box", plus the error rate above/below the median signal. Nothing is tuned here.

    .\\.venv\\Scripts\\python.exe scripts\\evaluate_instability.py --images 30       # API on :8000; writes docs/audit_evidence/instability_validation.json
Calling the pipeline stores analysis records in the app database (remove with scripts\\audit_cleanup.py).
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _auth  # noqa: E402

_auth.install()
ROOT = Path(__file__).resolve().parents[1]


def auroc(scores, labels):
    """P(score of a positive > score of a negative), ties count half; None if one class is empty."""
    s, y = np.asarray(scores, float), np.asarray(labels, bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    cmp = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(cmp / (len(pos) * len(neg)))


def iou_box(a, b):
    iw, ih = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def main():
    from dentexmodel.config import get_settings
    from dentexmodel.data.coco import load_coco
    from dentexmodel.data.manifest import load_manifest
    from dentexmodel.utils.geometry import polygon_to_mask, rle_to_mask
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=int, default=30)
    ap.add_argument("--base", default="http://127.0.0.1:8000/api")
    a = ap.parse_args()
    s = get_settings()
    rows = [r for r in load_manifest(s.processed_dir / "manifest.json") if r.split == "val" and r.annotation_level.startswith("quadrant_enumeration")
            and r.annotation_status == "annotated" and r.duplicate_of is None and r.dataset_source.endswith("quadrant_enumeration")]
    rows.sort(key=lambda r: r.image_id)
    rows = rows[:a.images]
    src = s.data_root / "training_data" / "quadrant_enumeration" / "train_quadrant_enumeration.json"
    coco = load_coco(src)
    mask_rec, det_rec = [], []
    for r in rows:
        req = urllib.request.Request(a.base + "/analyze/full", json.dumps({"image_id": r.image_id}).encode(), {"content-type": "application/json"})
        full = json.load(urllib.request.urlopen(req, timeout=600))
        W, H = full["image_size"]
        gts = []
        for an in coco.by_image.get(r.coco_image_id, []):
            x, y, w, h = an["bbox"]
            seg = an.get("segmentation")
            gm = None
            if seg and isinstance(seg, list) and seg and isinstance(seg[0], list) and len(seg[0]) >= 6:
                pts = [(seg[0][i], seg[0][i + 1]) for i in range(0, len(seg[0]) - 1, 2)]
                gm = polygon_to_mask(pts, W, H)
            gts.append(([x, y, x + w, y + h], gm))
        used = set()
        for g in full["regions"]:
            u = g.get("uncertainty", {})
            best, bj = 0.0, None
            for j, (gb, _) in enumerate(gts):
                v = iou_box(g["box"], gb)
                if v > best:
                    best, bj = v, j
            if u.get("detection_instability") is not None:
                det_rec.append((u["detection_instability"], best < 0.5))
            if g.get("mask") and bj is not None and best >= 0.5 and gts[bj][1] is not None and u.get("mask_instability") is not None:
                pm = rle_to_mask(g["mask"]["mask_rle"])
                gm = gts[bj][1]
                inter = np.logical_and(pm, gm).sum()
                un = np.logical_or(pm, gm).sum()
                mask_rec.append((u["mask_instability"], 1.0 - (inter / un if un else 0.0)))
    out = {"generated": datetime.now(timezone.utc).isoformat(), "split": "val (test split never used)", "n_images": len(rows), "base": "live API, real models",
           "ground_truth": "DENTEX quadrant_enumeration boxes and polygons"}
    if mask_rec:
        sc = np.array([m[0] for m in mask_rec]); err = np.array([m[1] for m in mask_rec])
        bad = err > 0.2                                   # mask IoU < 0.8
        med = float(np.median(sc))
        out["mask_instability"] = {"n_regions": len(mask_rec), "mean_mask_iou": float(1 - err.mean()), "fraction_iou_below_0.8": float(bad.mean()), "auroc_for_iou_below_0.8": auroc(sc, bad),
                                   "spearman_like_corr_with_error": float(np.corrcoef(np.argsort(np.argsort(sc)), np.argsort(np.argsort(err)))[0, 1]),
                                   "error_rate_above_median_signal": float(bad[sc > med].mean()) if (sc > med).any() else None,
                                   "error_rate_at_or_below_median_signal": float(bad[sc <= med].mean()) if (sc <= med).any() else None, "median_signal": med}
    if det_rec:
        sc = np.array([d[0] for d in det_rec]); fp = np.array([d[1] for d in det_rec])
        med = float(np.median(sc))
        out["detection_instability"] = {"n_regions": len(det_rec), "false_positive_fraction": float(fp.mean()), "n_false_positives": int(fp.sum()), "auroc_for_false_positive": auroc(sc, fp),
                                        "error_rate_above_median_signal": float(fp[sc > med].mean()) if (sc > med).any() else None, "median_signal": med}
    out["reading"] = ("AUROC 0.5 = no information, 1.0 = perfect ranking. These are ranking signals on one split of one dataset; they are not calibrated probabilities of error. "
                      "If an AUROC is near 0.5 or None the signal must not be presented as validated.")
    dest = ROOT / "docs" / "audit_evidence" / "instability_validation.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
