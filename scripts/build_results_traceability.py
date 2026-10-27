#!/usr/bin/env python
"""Results traceability table for the verified CV5-BASE run 1 (no new computation of any metric).

    .venv\\Scripts\\python.exe scripts\\build_results_traceability.py

Every value is READ from an archived artifact of kaggle/artifacts_cv5_run1/ after checking that artifact against the run's
SHA256SUMS.txt, and is written with its exact JSON location and the artifact's SHA-256. The only derived quantities are sums / maxima of
archived per-run fields (training seconds, peak GPU memory, checkpoint bytes) and the parameter count of the BASE architecture, each
labelled as derived. Quantities the artifacts do not contain (e.g. inference latency) are listed as NOT AVAILABLE, never estimated.
Outputs: reports/results_traceability.json and reports/results_traceability.md (refuses to overwrite an existing file).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "kaggle" / "artifacts_cv5_run1"
CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verified(rel: str) -> tuple[dict | list, str]:
    sums = dict(reversed(line.split(maxsplit=1)) for line in (ART / "SHA256SUMS.txt").read_text().splitlines() if line.strip())
    sums = {k.lstrip("*").replace("\\", "/"): v for k, v in sums.items()}
    h = sha(ART / rel)
    if sums.get(rel) != h:
        raise SystemExit(f"{rel} does not match SHA256SUMS.txt - refusing to report it")
    return json.loads((ART / rel).read_text(encoding="utf-8")), h


def get(d, path: str):
    for k in path.split("/"):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def build() -> dict:
    res, h_res = verified("cv5_results.json")
    rows = []

    def add(qid, quantity, path, kind="read"):
        v = get(res, path)
        rows.append({"id": qid, "quantity": quantity, "value": v, "source": "kaggle/artifacts_cv5_run1/cv5_results.json",
                     "json_path": path, "source_sha256": h_res, "kind": kind})

    add("pop.findings", "primary out-of-fold findings", "population/primary_findings")
    add("pop.radiographs", "primary radiographs", "population/primary_radiographs")
    add("pop.det_matched", "detector-matched findings", "population/detector_matched")
    for st, name in (("det_matched", "detector boxes"), ("gt", "GT boxes")):
        add(f"{st}.macro_f1.mean", f"macro-F1, {name}, mean over seeds 42-46", f"summary/{st}/macro_f1/mean")
        add(f"{st}.macro_f1.sd", f"macro-F1, {name}, SD over seeds", f"summary/{st}/macro_f1/sd")
        add(f"{st}.boot.point", f"macro-F1, {name}, bootstrap point (seed-mean)", f"bootstrap/{st}/point")
        add(f"{st}.boot.ci95", f"macro-F1, {name}, radiograph bootstrap 95% CI (2,000 resamples)", f"bootstrap/{st}/ci95")
        add(f"{st}.accuracy.mean", f"accuracy, {name}, mean", f"summary/{st}/accuracy/mean")
        add(f"{st}.ece.mean", f"ECE (10 bins), {name}, mean", f"summary/{st}/ece_10bin/mean")
        add(f"{st}.ece.sd", f"ECE (10 bins), {name}, SD", f"summary/{st}/ece_10bin/sd")
        add(f"{st}.fold_level.mean", f"fold-level macro-F1, {name}, mean over folds (descriptive)", f"fold_level_macro_f1/{st}/mean")
        add(f"{st}.fold_level.sd", f"fold-level macro-F1, {name}, SD over folds", f"fold_level_macro_f1/{st}/sd")
        for c in CLASSES:
            for m in ("precision", "recall", "f1"):
                add(f"{st}.{c}.{m}.mean", f"{c} {m}, {name}, mean", f"summary/{st}/per_class/{c}/{m}/mean")
                add(f"{st}.{c}.{m}.sd", f"{c} {m}, {name}, SD", f"summary/{st}/per_class/{c}/{m}/sd")
        for s in res["seeds"]:
            add(f"{st}.seed{s}.macro_f1", f"macro-F1, {name}, seed {s} (pooled out-of-fold)", f"pooled_per_seed/{s}/{st}/macro_f1")
            add(f"{st}.seed{s}.nll", f"NLL, {name}, seed {s}", f"pooled_per_seed/{s}/{st}/nll")
        for k in res["folds"]:
            add(f"{st}.fold{k}.macro_f1.mean", f"macro-F1, {name}, held-out fold {k}, mean over seeds", f"per_fold/{k}/{st}/macro_f1/mean")
    for s in res["seeds"]:
        for c in CLASSES:
            add(f"e2e.seed{s}.{c}.recall", f"end-to-end recall (unmatched = wrong), {c}, seed {s}", f"pooled_per_seed/{s}/end_to_end/recall/{c}")
    add("unseen.findings", "detector-unseen subset findings", "detector_unseen_subset/findings")
    add("unseen.det.mean", "detector-unseen subset macro-F1, detector boxes, mean", "detector_unseen_subset/macro_f1_det_matched/mean")
    add("unseen.gt.mean", "detector-unseen subset macro-F1, GT boxes, mean", "detector_unseen_subset/macro_f1_gt/mean")
    add("secondary.findings", "DENTEX official-validation findings (secondary)", "secondary_official_val/findings")
    add("secondary.gt.mean", "official-validation macro-F1, GT boxes, mean", "secondary_official_val/gt_macro_f1/mean")
    add("secondary.gt.sd", "official-validation macro-F1, GT boxes, SD", "secondary_official_val/gt_macro_f1/sd")
    add("env.gpu", "GPU", "environment/gpu")
    add("env.torch", "torch", "environment/torch")

    # derived resource quantities (sums / maxima of archived per-run fields)
    secs, peaks, files = [], [], []
    for p in sorted((ART / "runs").glob("*__result.json")):
        d, h = verified(f"runs/{p.name}")
        secs.append(d["history"][-1]["sec"])
        peaks.append(d["gpu"]["peak_alloc_mb"])
        files.append({"file": f"runs/{p.name}", "sha256": h})
    ck, h_ck = verified("checkpoint_manifest.json")
    rows.append({"id": "cost.train_hours", "quantity": "training time, sum over the 25 runs (per-run cumulative epoch seconds; excludes "
                 "data download, crops, detector and prediction)", "value": sum(secs) / 3600, "source": "runs/*__result.json history[-1].sec",
                 "json_path": None, "source_sha256": [f["sha256"] for f in files], "kind": f"derived (sum of {len(secs)} runs)"})
    rows.append({"id": "cost.peak_gpu_mb", "quantity": "peak allocated GPU memory, max over runs (MB)", "value": max(peaks),
                 "source": "runs/*__result.json gpu.peak_alloc_mb", "json_path": None, "source_sha256": [f["sha256"] for f in files],
                 "kind": "derived (max)"})
    sizes = sorted({v["bytes"] for v in ck.values()})
    rows.append({"id": "cost.checkpoint_bytes", "quantity": "checkpoint size (bytes; identical for all 25)" if len(sizes) == 1 else
                 "checkpoint sizes (bytes)", "value": sizes[0] if len(sizes) == 1 else sizes, "source": "checkpoint_manifest.json",
                 "json_path": "*/bytes", "source_sha256": h_ck, "kind": "read"})
    try:
        sys.path[:0] = [str(ROOT / "kaggle"), str(ROOT / "scripts" / "dataset")]
        import torch
        import torchvision as tv
        import dentamind_kaggle as DK
        n = sum(p.numel() for p in DK.new_model(torch, tv, pretrained=False).parameters())
        rows.append({"id": "cost.parameters", "quantity": "trainable parameters of the BASE architecture (ResNet-50, 4-class head)",
                     "value": n, "source": "kaggle/dentamind_kaggle.py new_model()", "json_path": None,
                     "source_sha256": sha(ROOT / "kaggle" / "dentamind_kaggle.py"), "kind": "derived (architecture count, no weights)"})
    except Exception as e:                       # pragma: no cover - torch missing
        rows.append({"id": "cost.parameters", "quantity": "parameter count", "value": None, "kind": f"NOT AVAILABLE ({e})"})
    for qid, q in (("cost.latency", "inference latency per crop"), ("cost.notebook_runtime", "total notebook wall-clock runtime")):
        rows.append({"id": qid, "quantity": q, "value": None, "source": None, "json_path": None, "source_sha256": None,
                     "kind": "NOT AVAILABLE in the archived artifacts" + (" (the Kaggle log states 'Successfully ran in 4945.4s'; reported in "
                                                                          "reports/cv5_results.md, not an artifact field)" if qid == "cost.notebook_runtime" else "")})
    return {"format": "dentamind-results-traceability-v1", "run": "CV5-BASE run 1 (kaggle/artifacts_cv5_run1)",
            "archive_zip_sha256": sha(ROOT / "kaggle" / "dentamind_5fold_cv_artifacts.zip"),
            "sha256sums_txt": sha(ART / "SHA256SUMS.txt"), "script_sha256": sha(Path(__file__)),
            "notes": ["radiograph-level results only: DENTEX has no patient identifiers",
                      "not test-set results; not comparable with earlier single-split numbers (different populations and protocols)",
                      "no candidate results exist; BASE-P2 has not been run"], "rows": rows}


def fmt(v):
    if isinstance(v, float):
        return f"{v:.4f}"
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    return "n/a" if v is None else str(v)


def main():
    out_j, out_m = ROOT / "reports" / "results_traceability.json", ROOT / "reports" / "results_traceability.md"
    if out_j.exists() or out_m.exists():
        raise SystemExit("results_traceability.* exists: write a new version instead of overwriting")
    t = build()
    with open(out_j, "x", encoding="utf-8") as fh:
        json.dump(t, fh, indent=1)
    lines = [f"# Results traceability: {t['run']}", "",
             f"Generated by `scripts/build_results_traceability.py` (sha256 `{t['script_sha256']}`). Archive `{t['archive_zip_sha256']}`; "
             f"SHA256SUMS.txt `{t['sha256sums_txt']}` (every source verified against it).", "",
             *[f"* {n}" for n in t["notes"]], "", "| ID | Quantity | Value (4 d.p. display; full precision in the JSON) | Source | JSON path | Kind |",
             "|---|---|---|---|---|---|"]
    for r in t["rows"]:
        lines.append(f"| `{r['id']}` | {r['quantity']} | {fmt(r['value'])} | {r.get('source') or '-'} | {r.get('json_path') or '-'} | {r['kind']} |")
    with open(out_m, "x", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {out_j.name} and {out_m.name}: {len(t['rows'])} rows")


if __name__ == "__main__":
    main()
