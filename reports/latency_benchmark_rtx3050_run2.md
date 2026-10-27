# Inference-latency benchmark (descriptive; one machine)

Script `scripts/benchmark_latency.py` (sha256 `4607be21cd31f4afb288d59cb5e3764a124bf2e3ea98d7f3665664750fa05bf2`), 2026-10-25T08:37:50Z. NVIDIA GeForce RTX 3050 Laptop GPU (NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB, 610.62, [N/A], 2100 MHz); torch 2.6.0+cu124, torchvision 0.21.0+cu124, CUDA 12.4, cuDNN 90100; CPU Intel64 Family 6 Model 154 Stepping 3, GenuineIntel; Windows-11-10.0.26300-SP0. Laptop power and thermal state were not controlled.

| Measurement | Batch | Median ms per crop (min–max over 5 reps) | Throughput (crops/s) | Peak GPU memory (MB) |
|---|---|---|---|---|
| Classifier only, GPU fp32 | 1 | 5.03 (4.71–5.26) | 199 | 109 |
| Classifier only, GPU fp32 | 64 | 2.92 (2.92–2.92) | 343 | 772 |
| Classifier only, CPU fp32 | 1 | 65.60 (63.88–66.90) | 15 | – |

End-to-end per radiograph (GPU; 20 radiographs x 5 repetitions; median detector boxes per image 29; peak GPU memory 698 MB):

| Stage | Median ms | p5–p95 ms |
|---|---|---|
| load | 49.7 | 45.9–58.6 |
| detector | 82.4 | 79.6–91.1 |
| crop | 18.0 | 12.6–22.1 |
| classify | 88.8 | 59.3–98.2 |
| total | 241.7 | 201.2–259.2 |

Excluded from end-to-end: image upload / HTTP, tooth numbering, segmentation, report generation, visualisation.

Checkpoints (SHA-256):

* `checkpoints/kaggle_candidates/dc9c505b/checkpoints/baseline__BASE_s45.pth` `3e0ab876885a1c3dd11eb45210876133cceb331a6662b718530a49af12833798`
* `Data/checkpoints/dentex_teeth_detection_v1.pth` `a68ce4884066ad80e9f6ea358d7ea56d101c6f7e65445b2f89cef9653e786921`
