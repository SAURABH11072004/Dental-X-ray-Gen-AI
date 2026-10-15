#!/usr/bin/env python
"""Read-only audit: how the production detector's boxes differ from ground-truth finding boxes on the TRAINING split, and what
that does to the classifier input (crop window, per-axis scale, aspect ratio). Used only to size crop-jitter augmentation.
Writes docs/audit_evidence/ml_improvement/crop_robustness/geometry_audit_train.json. Never reads validation, calibration or test."""
import _bootstrap  # noqa: F401
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from dentexmodel.config import get_settings
from dentexmodel.data.coco import annotation_finding
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.preprocess import load_gray
from dentexmodel.data.splits import load_split_file
from dentexmodel.inference import torch_models as TM
from dentexmodel.training import trainers as T
from dentexmodel.utils.geometry import box_iou

OUT = Path("docs/audit_evidence/ml_improvement/crop_robustness")


def q(v):
    return {k: round(float(x), 4) for k, x in zip(("p5", "p25", "p50", "p75", "p95"), np.percentile(v, [5, 25, 50, 75, 95]))}


def main() -> int:
    s = get_settings()
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == T.TASK_LEVEL["classification"] and assign.get(r.image_id) == "train"]
    items = T._annotations_for(s, svc, rows)
    rec = []
    for row, anns, cats in items:
        gt = []
        for a in anns:
            lab = annotation_finding(a, cats) if "category_id_3" in a else None
            if lab and a.get("bbox"):
                x, y, w, h = a["bbox"]
                gt.append((lab, [x, y, x + w, y + h]))
        if not gt:
            continue
        path = s.data_root / row.file_path
        with Image.open(path) as im:
            W, H = im.size
        rgb01 = np.repeat(load_gray(path)[..., None], 3, axis=2)
        dets = [d.box for d in TM.detect_teeth(rgb01, row.image_id, s).detections]
        for lab, g in gt:
            best = max(((box_iou(g, d), d) for d in dets), default=(0.0, None))
            gw, gh = g[2] - g[0], g[3] - g[1]
            r = {"label": lab, "w": gw, "h": gh, "aspect_w_over_h": gw / gh, "iou": best[0],
                 "touches_border": g[0] - 0.1 * gw < 0 or g[1] - 0.1 * gh < 0 or g[2] + 0.1 * gw > W or g[3] + 0.1 * gh > H}
            if best[1] is not None and best[0] >= 0.5:
                d = best[1]
                r.update(dx1=(d[0] - g[0]) / gw, dy1=(d[1] - g[1]) / gh, dx2=(d[2] - g[2]) / gw, dy2=(d[3] - g[3]) / gh,
                         w_ratio=(d[2] - d[0]) / gw, h_ratio=(d[3] - d[1]) / gh)
            rec.append(r)
    m = [r for r in rec if "dx1" in r]
    out = {"split": "train", "n_findings": len(rec), "n_matched_iou_ge_0.5": len(m),
           "gt_box_px": {"w": q([r["w"] for r in rec]), "h": q([r["h"] for r in rec])},
           "aspect_w_over_h": q([r["aspect_w_over_h"] for r in rec]),
           "resize_scale_to_224": {"x": q([224 / (1.2 * r["w"]) for r in rec]), "y": q([224 / (1.2 * r["h"]) for r in rec])},
           "crop_clipped_at_image_border_fraction": round(float(np.mean([r["touches_border"] for r in rec])), 4),
           "detector_vs_gt": {"iou": q([r["iou"] for r in m]),
                              **{k: q([r[k] for r in m]) for k in ("dx1", "dy1", "dx2", "dy2", "w_ratio", "h_ratio")},
                              "abs_edge_shift_fraction": q([abs(r[k]) for r in m for k in ("dx1", "dy1", "dx2", "dy2")])},
           "note": "edge shifts are fractions of the GT box width (x) or height (y); positive = detector edge to the right/below. "
                   "The detector was trained on this split, so these errors understate what happens on unseen radiographs."}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "geometry_audit_train.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
