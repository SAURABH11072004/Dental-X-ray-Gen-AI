#!/usr/bin/env python
"""Inference latency / throughput / peak GPU memory of each registered model on real radiographs (measured, not estimated).

    python scripts/benchmark_inference.py --images 12
Writes Data/reports/benchmark_inference.json and .md. Uses test-data images only for timing; no accuracy is computed here.
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
import time
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from dentexmodel.config import get_settings
from dentexmodel.errors import DentaMindError
from dentexmodel.inference.torch_models import classify_regions, detect_teeth, number_teeth, segment_teeth


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=int, default=12)
    ap.add_argument("--warmup", type=int, default=2)
    a = ap.parse_args()
    s = get_settings()
    import torch
    files = sorted((s.data_root / "validation_data").rglob("*.png"))[: a.images + a.warmup]
    imgs = [np.asarray(Image.open(f).convert("RGB"), dtype=np.float32) / 255.0 for f in files]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    out = {"generated": datetime.now(timezone.utc).isoformat(), "device": dev, "gpu": torch.cuda.get_device_name(0) if dev == "cuda" else None,
           "n_images": a.images, "image_sizes": sorted({f"{i.shape[1]}x{i.shape[0]}" for i in imgs}), "stages": {}, "failures": 0}
    state = {}

    def stage(name, fn):
        times, fails = [], 0
        if dev == "cuda":
            torch.cuda.reset_peak_memory_stats()
        for k, im in enumerate(imgs):
            try:
                t = time.perf_counter()
                r = fn(im)
                if dev == "cuda":
                    torch.cuda.synchronize()
                dt = time.perf_counter() - t
                if k >= a.warmup:
                    times.append(dt)
                state[name] = r
            except DentaMindError as exc:
                fails += 1
                out["stages"][name] = {"unavailable": exc.message}
                return
        out["stages"][name] = {"mean_s": float(np.mean(times)), "median_s": float(np.median(times)), "p95_s": float(np.percentile(times, 95)),
                               "images_per_s": float(1 / np.mean(times)), "peak_gpu_mb": round(torch.cuda.max_memory_allocated() / 2**20, 1) if dev == "cuda" else None,
                               "failures": fails}
        out["failures"] += fails

    stage("detection", lambda im: detect_teeth(im, "bench", s))
    stage("segmentation", lambda im: segment_teeth(im, "bench", s))
    def det_number(im):
        d = detect_teeth(im, "b", s)
        return number_teeth(im, [dict(x.__dict__) for x in d.detections], s)
    stage("detection+numbering (total)", det_number)

    def classify(im):
        d = detect_teeth(im, "b", s)
        return classify_regions(im, [x.box for x in d.detections], s)
    stage("detection+classification (total)", classify)
    rep = s.data_root / "reports"
    (rep / "benchmark_inference.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    lines = ["# Inference benchmark", "", f"{out['generated']} - device {dev} ({out['gpu']}), {a.images} images ({', '.join(out['image_sizes'])}), {a.warmup} warm-up runs excluded.", "",
             "| Stage | mean s | median s | p95 s | images/s | peak GPU MB | failures |", "|---|---:|---:|---:|---:|---:|---:|"]
    for k, v in out["stages"].items():
        lines.append(f"| {k} | " + (" | ".join(f"{v[c]:.3f}" if isinstance(v[c], float) else str(v[c]) for c in ("mean_s", "median_s", "p95_s", "images_per_s", "peak_gpu_mb", "failures")) if "mean_s" in v else f"unavailable: {v['unavailable']} | | | | |"))
    lines += ["", "'(total)' rows include the detector pass. The full app pipeline (all models + flip-TTA passes) reports its own time in /api/analyze/full (`summary.seconds`, about 8 s on the first call incl. model loading).", ""]
    (rep / "benchmark_inference.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
