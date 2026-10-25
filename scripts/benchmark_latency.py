#!/usr/bin/env python
"""Inference-latency benchmark of the BASE classifier and of the end-to-end pipeline (measurement only; no metric, no candidate).

    .venv\\Scripts\\python.exe scripts\\benchmark_latency.py [--out-stem reports/latency_benchmark_rtx3050]

Procedure (follows the latency definition of reports/cv5_acceptance_protocol.md section 7: batch 64 and batch 1, 5 repetitions
after warm-up, median; this measurement is descriptive and decides nothing):
* Classifier: ResNet-50 4-class BASE recipe, checkpoint checkpoints/kaggle_candidates/dc9c505b/checkpoints/baseline__BASE_s45.pth
  (verified against that run's SHA256SUMS.txt; same architecture and input as CV5-BASE, whose fold checkpoints are not stored
  locally). fp32, eval mode, torch.no_grad, input 224 x 224 crops normalised with ImageNet statistics, softmax included.
* Model-only: inputs already on the device; per timed iteration forward + softmax; torch.cuda.synchronize around every timing.
  Warm-up 20 iterations; 5 repetitions x 50 iterations (batch 1) or x 10 iterations (batch 64). Latency per crop = time / batch.
* End-to-end (per radiograph): PNG decode from disk, tooth detector (Faster R-CNN, autocast as in production, score >= 0.3), crop of
  every detector box (production crop rule), classification of all crops in one batch, results copied to the CPU. 20 fixed pool
  radiographs (first 20 primary DENTEX disease images by file name; no labels are used), 2 warm-up images, 5 repetitions.
* Environment recorded: GPU, VRAM, driver, CUDA, cuDNN, torch / torchvision, CPU, OS. Laptop power and thermal state are NOT
  controlled; results apply to this machine only.
Writes <out-stem>.json and .md (never overwritten).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kaggle"))
sys.path.insert(0, str(ROOT / "scripts" / "dataset"))
import dentamind_kaggle as DK  # noqa: E402
from dsutil import CROP_PAD, CROP_SIZE, crop_region  # noqa: E402

CLS_RUN = ROOT / "checkpoints" / "kaggle_candidates" / "dc9c505b"
CLS_REL = "checkpoints/baseline__BASE_s45.pth"
DET = ROOT / "Data" / "checkpoints" / "dentex_teeth_detection_v1.pth"
BUNDLE = ROOT / "kaggle" / "dist" / "dentamind_kaggle_bundle.zip"
DATA = ROOT / "Data"
REPS, WARM = 5, 20
ITERS = {1: 50, 64: 10}


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify() -> dict:
    sums = {}
    for line in (CLS_RUN / "SHA256SUMS.txt").read_text().splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*").replace("\\", "/")] = h
    h_cls = sha(CLS_RUN / CLS_REL)
    if sums.get(CLS_REL) != h_cls:
        raise SystemExit("classifier checkpoint does not match its run's SHA256SUMS.txt")
    hb = hashlib.sha256()
    with zipfile.ZipFile(BUNDLE).open("data/checkpoints/dentex_teeth_detection_v1.pth") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            hb.update(b)
    h_det = sha(DET)
    if hb.hexdigest() != h_det:
        raise SystemExit("detector checkpoint differs from the CV5 bundle copy")
    return {f"checkpoints/kaggle_candidates/dc9c505b/{CLS_REL}": h_cls, "Data/checkpoints/dentex_teeth_detection_v1.pth": h_det}


def environment(torch, tv) -> dict:
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version,power.limit,clocks.max.sm",
                          "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    return {"gpu": torch.cuda.get_device_name(0), "nvidia_smi": smi,
            "vram_bytes": torch.cuda.get_device_properties(0).total_memory, "cuda_runtime": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(), "cudnn_benchmark": torch.backends.cudnn.benchmark, "torch": torch.__version__,
            "torchvision": tv.__version__, "python": platform.python_version(), "cpu": platform.processor(),
            "os": platform.platform(), "power_thermal_control": "none (laptop; not controlled)"}


def stats(xs) -> dict:
    a = np.asarray(xs, float)
    return {"n": int(a.size), "median": float(np.median(a)), "min": float(a.min()), "max": float(a.max()),
            "p5": float(np.percentile(a, 5)), "p95": float(np.percentile(a, 95))}


def model_only(torch, model, dev, batch) -> dict:
    x = DK.norm(torch, torch.rand(batch, 3, CROP_SIZE, CROP_SIZE, device=dev), dev)
    sync = torch.cuda.synchronize if dev.type == "cuda" else (lambda: None)
    with torch.no_grad():
        for _ in range(WARM):
            torch.softmax(model(x), 1)
        sync()
        if dev.type == "cuda":
            torch.cuda.reset_peak_memory_stats()
        reps, per_iter = [], []
        for _ in range(REPS):
            t0 = time.perf_counter()
            for _ in range(ITERS[batch]):
                t1 = time.perf_counter()
                torch.softmax(model(x), 1)
                sync()
                per_iter.append((time.perf_counter() - t1) * 1000)
            reps.append((time.perf_counter() - t0) * 1000 / (ITERS[batch] * batch))
    return {"batch": batch, "iterations_per_repetition": ITERS[batch], "repetitions": REPS, "warmup_iterations": WARM,
            "ms_per_crop_by_repetition": reps, "ms_per_crop": stats(reps), "ms_per_iteration": stats(per_iter),
            "throughput_crops_per_s_median": 1000 / float(np.median(reps)),
            "peak_allocated_mb": torch.cuda.max_memory_allocated() / 2**20 if dev.type == "cuda" else None}


def images() -> list[Path]:
    paths = set()
    for r in csv.DictReader(open(ROOT / "data" / "splits" / "combined_train.csv", encoding="utf-8")):
        if r["image_path"].startswith("training_data/quadrant-enumeration-disease/"):
            paths.add(r["image_path"])
    chosen = sorted(paths, key=lambda p: int(Path(p).stem.split("_")[1]))[:22]
    return [DATA / p for p in chosen]


def end_to_end(torch, tv, cls, dev) -> dict:
    from PIL import Image
    det = tv.models.detection.fasterrcnn_resnet50_fpn(weights=None, weights_backbone=None, num_classes=2)
    det.load_state_dict(torch.load(DET, map_location="cpu", weights_only=True), strict=True)
    det = det.to(dev).eval()
    imgs = images()
    sync = torch.cuda.synchronize

    def one(path):
        t = {}
        t0 = time.perf_counter()
        img = np.asarray(Image.open(path).convert("RGB"))
        t["load"] = time.perf_counter() - t0
        t1 = time.perf_counter()
        x = torch.from_numpy(np.ascontiguousarray(img.transpose(2, 0, 1))).float().div(255).to(dev)
        with torch.no_grad(), torch.autocast(device_type="cuda"):
            o = det([x])[0]
        boxes = [b for b, s in zip(o["boxes"].float().cpu().tolist(), o["scores"].float().cpu().tolist()) if s >= DK.DET_SCORE]
        sync()
        t["detector"] = time.perf_counter() - t1
        t2 = time.perf_counter()
        crops = [c for c in (crop_region(img, b, CROP_SIZE, CROP_PAD) for b in boxes) if c is not None]
        t["crop"] = time.perf_counter() - t2
        t3 = time.perf_counter()
        probs = DK.predict(torch, cls, np.stack(crops), dev, bs=64) if crops else np.zeros((0, 4))
        sync()
        t["classify"] = time.perf_counter() - t3
        t["total"] = time.perf_counter() - t0
        return {k: v * 1000 for k, v in t.items()}, len(boxes), probs.shape[0]

    for p in imgs[:2]:
        one(p)
    torch.cuda.reset_peak_memory_stats()
    rec, n_boxes = [], []
    for _ in range(REPS):
        for p in imgs[2:]:
            t, nb, _ = one(p)
            rec.append(t)
            n_boxes.append(nb)
    return {"images": [str(p.relative_to(ROOT)).replace("\\", "/") for p in imgs[2:]], "warmup_images": 2, "repetitions": REPS,
            "detector_boxes_per_image": stats(n_boxes),
            "ms_per_radiograph": {k: stats([r[k] for r in rec]) for k in ("load", "detector", "crop", "classify", "total")},
            "peak_allocated_mb": torch.cuda.max_memory_allocated() / 2**20,
            "excluded": "image upload / HTTP, tooth numbering, segmentation, report generation, visualisation"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-stem", default=str(ROOT / "reports" / "latency_benchmark_rtx3050"))
    a = ap.parse_args()
    out_j, out_m = Path(a.out_stem + ".json"), Path(a.out_stem + ".md")
    if out_j.exists() or out_m.exists():
        raise SystemExit(f"{out_j.name} exists: write a new benchmark to a new file")
    import torch
    import torchvision as tv
    if not torch.cuda.is_available():
        raise SystemExit("no CUDA device: the GPU benchmark is PENDING (run on the target GPU); nothing written")
    hashes = verify()
    dev = torch.device("cuda")
    model = DK.new_model(torch, tv, pretrained=False)
    model.load_state_dict(torch.load(CLS_RUN / CLS_REL, map_location="cpu", weights_only=True), strict=True)
    model = model.to(dev).eval()
    n_params = sum(p.numel() for p in model.parameters())
    res = {"format": "dentamind-latency-benchmark-v1", "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "status": "descriptive measurement on one machine; not a CV5 metric and not an acceptance criterion",
           "script_sha256": sha(Path(__file__)), "checkpoints": hashes, "classifier_parameters": n_params,
           "environment": environment(torch, tv),
           "model_only_gpu_fp32": [model_only(torch, model, dev, b) for b in (1, 64)]}
    cpu_model = model.to("cpu")
    res["model_only_cpu_fp32"] = [model_only(torch, cpu_model, torch.device("cpu"), 1)]
    model = cpu_model.to(dev)
    res["end_to_end_gpu"] = end_to_end(torch, tv, model, dev)
    with open(out_j, "x", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    e = res["environment"]
    L = ["# Inference-latency benchmark (descriptive; one machine)", "",
         f"Script `scripts/benchmark_latency.py` (sha256 `{res['script_sha256']}`), {res['date_utc']}. {e['gpu']} ({e['nvidia_smi']}); "
         f"torch {e['torch']}, torchvision {e['torchvision']}, CUDA {e['cuda_runtime']}, cuDNN {e['cudnn']}; CPU {e['cpu']}; {e['os']}. "
         "Laptop power and thermal state were not controlled.", "",
         "| Measurement | Batch | Median ms per crop (min–max over 5 reps) | Throughput (crops/s) | Peak GPU memory (MB) |", "|---|---|---|---|---|"]
    for name, rows in (("Classifier only, GPU fp32", res["model_only_gpu_fp32"]), ("Classifier only, CPU fp32", res["model_only_cpu_fp32"])):
        for r in rows:
            s = r["ms_per_crop"]
            pk = f"{r['peak_allocated_mb']:.0f}" if r["peak_allocated_mb"] is not None else "–"
            L.append(f"| {name} | {r['batch']} | {s['median']:.2f} ({s['min']:.2f}–{s['max']:.2f}) | {r['throughput_crops_per_s_median']:.0f} | {pk} |")
    E = res["end_to_end_gpu"]
    L += ["", f"End-to-end per radiograph (GPU; {len(E['images'])} radiographs x {E['repetitions']} repetitions; median detector boxes "
          f"per image {E['detector_boxes_per_image']['median']:.0f}; peak GPU memory {E['peak_allocated_mb']:.0f} MB):", "",
          "| Stage | Median ms | p5–p95 ms |", "|---|---|---|"]
    for k, s in E["ms_per_radiograph"].items():
        L.append(f"| {k} | {s['median']:.1f} | {s['p5']:.1f}–{s['p95']:.1f} |")
    L += ["", f"Excluded from end-to-end: {E['excluded']}.", "", "Checkpoints (SHA-256):", ""] + [f"* `{k}` `{v}`" for k, v in hashes.items()]
    with open(out_m, "x", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L[4:]))


if __name__ == "__main__":
    main()
