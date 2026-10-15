#!/usr/bin/env python
"""Single-image or batch inference with the active dental checkpoints; writes JSON + an overlay PNG per image.

    python scripts/predict.py --image Data/validation_data/quadrant_enumeration_disease/xrays/val_0.png
    python scripts/predict.py --dir Data/validation_data/quadrant_enumeration_disease/xrays --limit 10

Output goes to Data/results/predictions/. Refuses (with the reason) when no dental detector is available;
it never fabricates detections. Everything is model output for research use, not a diagnosis.
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from dentexmodel.config import get_settings
from dentexmodel.errors import DentaMindError
from dentexmodel.inference.torch_models import classify_regions, detect_teeth
from dentexmodel.inference.visualize import draw_detections
from dentexmodel.utils.logging_utils import setup_logging


def predict_one(path: Path, settings, outdir: Path, classify: bool, min_score: float) -> dict:
    img = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    res = detect_teeth(img, path.stem, settings)
    dets = [d.__dict__ for d in res.detections]
    cls = None
    if classify and dets:
        try:
            cls = classify_regions(img, [d["box"] for d in dets], settings)
        except DentaMindError as exc:
            cls = {"unavailable": exc.message}
    out = {"image": path.name, "image_size": [img.shape[1], img.shape[0]], "detector": res.model_version, "device": res.device,
           "n_detections": len(dets), "detections": dets, "classification": cls,
           "warnings": ["Research model output; not a diagnosis.", *((cls or {}).get("limitations", []))]}
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{path.stem}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    draw_detections(img, dets, cls if cls and "probabilities" in cls else None, min_score).save(outdir / f"{path.stem}_overlay.png")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--image", type=Path)
    g.add_argument("--dir", type=Path)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-classify", action="store_true")
    ap.add_argument("--min-score", type=float, default=0.3, help="boxes below this score are not drawn")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    s = get_settings()
    setup_logging(s.logs_dir, s.log_level)
    outdir = a.out or (s.results_dir / "predictions")
    files = [a.image] if a.image else sorted(p for p in a.dir.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})[:a.limit]
    try:
        for f in files:
            r = predict_one(f, s, outdir, not a.no_classify, a.min_score)
            print(f"{f.name}: {r['n_detections']} detections ({r['detector']}, {r['device']})")
    except DentaMindError as exc:
        print("Cannot run inference:", exc.message, exc.hint or "")
        return 2
    print("wrote", outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
