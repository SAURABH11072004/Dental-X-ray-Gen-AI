# Inference-latency benchmark (descriptive; one machine)

Script `scripts/benchmark_latency.py` (sha256 `4607be21cd31f4afb288d59cb5e3764a124bf2e3ea98d7f3665664750fa05bf2`), 2026-10-25T08:36:40Z. NVIDIA GeForce RTX 3050 Laptop GPU (NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB, 610.62, [N/A], 2100 MHz); torch 2.6.0+cu124, torchvision 0.21.0+cu124, CUDA 12.4, cuDNN 90100; CPU Intel64 Family 6 Model 154 Stepping 3, GenuineIntel; Windows-11-10.0.26300-SP0. Laptop power and thermal state were not controlled.

| Measurement | Batch | Median ms per crop (min–max over 5 reps) | Throughput (crops/s) | Peak GPU memory (MB) |
|---|---|---|---|---|
| Classifier only, GPU fp32 | 1 | 4.96 (4.69–5.43) | 202 | 109 |
| Classifier only, GPU fp32 | 64 | 2.91 (2.91–2.91) | 344 | 772 |
| Classifier only, CPU fp32 | 1 | 65.38 (64.71–66.16) | 15 | – |

End-to-end per radiograph (GPU; 20 radiographs x 5 repetitions; median detector boxes per image 29; peak GPU memory 698 MB):

| Stage | Median ms | p5–p95 ms |
|---|---|---|
| load | 55.0 | 49.9–79.9 |
| detector | 84.5 | 81.0–93.4 |
| crop | 18.4 | 13.1–22.5 |
| classify | 89.1 | 59.5–98.6 |
| total | 251.3 | 209.0–282.5 |

Excluded from end-to-end: image upload / HTTP, tooth numbering, segmentation, report generation, visualisation.

Checkpoints (SHA-256):

* `checkpoints/kaggle_candidates/dc9c505b/checkpoints/baseline__BASE_s45.pth` `3e0ab876885a1c3dd11eb45210876133cceb331a6662b718530a49af12833798`
* `Data/checkpoints/dentex_teeth_detection_v1.pth` `a68ce4884066ad80e9f6ea358d7ea56d101c6f7e65445b2f89cef9653e786921`
