# CV5-BASE run 1: per-class radiograph-bootstrap 95 % intervals (post-hoc, descriptive)

Script `scripts/per_class_bootstrap_cv5.py` (sha256 `344634a87e7d2c7c3fc8ebfdc11b6ea797a5d4613b5bb8321a5f26eeab6b15b5`). Inputs checked against SHA256SUMS.txt: `oof_predictions.csv` `a90d16d8205acb7d3ea838149107535a4eef1a6114e5ea3633eb3c34138f1543`, `cv5_results.json` `52d94923bebad5596eeccfa26ead92a30237f289e6e4dd40963d13c78b29bd82`. The recomputation reproduces the archived macro-F1 point estimates and intervals exactly, and the archived per-class seed means.

| Setting | Class | Precision (95 % CI) | Recall (95 % CI) | F1 (95 % CI) |
|---|---|---|---|---|
| gt | Caries | 0.847 (0.828–0.865) | 0.874 (0.860–0.888) | 0.860 (0.848–0.872) |
| gt | Deep Caries | 0.576 (0.529–0.619) | 0.496 (0.451–0.539) | 0.533 (0.494–0.570) |
| gt | Impacted | 0.913 (0.888–0.935) | 0.949 (0.929–0.966) | 0.931 (0.913–0.945) |
| gt | Periapical Lesion | 0.485 (0.403–0.564) | 0.451 (0.370–0.531) | 0.467 (0.393–0.534) |
| det_matched | Caries | 0.848 (0.830–0.866) | 0.883 (0.869–0.895) | 0.865 (0.853–0.877) |
| det_matched | Deep Caries | 0.546 (0.495–0.591) | 0.440 (0.397–0.485) | 0.487 (0.446–0.526) |
| det_matched | Impacted | 0.935 (0.913–0.954) | 0.945 (0.928–0.961) | 0.940 (0.925–0.953) |
| det_matched | Periapical Lesion | 0.401 (0.310–0.490) | 0.432 (0.341–0.528) | 0.416 (0.333–0.494) |
