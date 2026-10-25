#!/usr/bin/env python
"""Supplementary traceability table for the NEGATIVE findings cited in the manuscript (no new computation of any metric).

    .venv\\Scripts\\python.exe scripts\\build_negative_findings_traceability.py

Three earlier experiments, all evaluated on the seed-42 project VALIDATION split (not CV5, not the test split), under the rules
pre-registered for each of them:
  * imbalance strategies (Kaggle run, checkpoints/kaggle_candidates/dc9c505b, checked against its SHA256SUMS.txt);
  * external training data (Kaggle run, kaggle/artifacts_external_run1, checked against its SHA256SUMS.txt);
  * 5-seed BASE ensemble (reports/ensemble_evaluation_kaggle.json; NOT part of a checksum-archived run, so only its own SHA-256 is
    recorded and the row kind says so).
Every value is READ from those files with its JSON path. Outputs reports/negative_findings_traceability.json and .md (never overwritten).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMB = ROOT / "checkpoints" / "kaggle_candidates" / "dc9c505b"
EXT = ROOT / "kaggle" / "artifacts_external_run1"
ENS = ROOT / "reports" / "ensemble_evaluation_kaggle.json"


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verified(run: Path, rel: str) -> tuple[dict, str]:
    sums = {}
    for line in (run / "SHA256SUMS.txt").read_text().splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*").replace("\\", "/")] = h
    h = sha(run / rel)
    if sums.get(rel) != h:
        raise SystemExit(f"{run.name}/{rel} does not match SHA256SUMS.txt - refusing to report it")
    return json.loads((run / rel).read_text(encoding="utf-8")), h


def get(d, path: str):
    for k in path.split("/"):
        d = d[k]
    return d


def build() -> dict:
    rows = []

    def add(qid, quantity, data, path, source, h, kind):
        rows.append({"id": qid, "quantity": quantity, "value": get(data, path), "source": source, "json_path": path,
                     "source_sha256": h, "kind": kind})

    imb, h_imb = verified(IMB, "validation_eval.json")
    src = "checkpoints/kaggle_candidates/dc9c505b/validation_eval.json"
    for name in imb["acceptance"]:
        base = f"acceptance/{name}"
        tag = f"neg.imbalance.{name}"
        add(f"{tag}.gain", f"imbalance strategy {name}: mean macro-F1 gain vs BASE (detector boxes)", imb, f"{base}/mean_gain_macro_f1",
            src, h_imb, "read (checksum-archived)")
        add(f"{tag}.seed_pairs", f"imbalance strategy {name}: seed pairs better (of 5)", imb, f"{base}/seed_pairs_better", src, h_imb,
            "read (checksum-archived)")
        add(f"{tag}.cross_pairs", f"imbalance strategy {name}: cross pairs better (of 25)", imb, f"{base}/cross_pairs_better", src,
            h_imb, "read (checksum-archived)")
        for c in ("Deep Caries", "Periapical Lesion"):
            add(f"{tag}.{c}.recall_delta", f"imbalance strategy {name}: {c} recall delta", imb, f"{base}/minority_recall_delta/{c}",
                src, h_imb, "read (checksum-archived)")
        add(f"{tag}.pass", f"imbalance strategy {name}: passed its acceptance rule", imb, f"{base}/pass", src, h_imb,
            "read (checksum-archived)")
    add("neg.imbalance.rule", "imbalance experiment acceptance rule", imb, "rule", src, h_imb, "read (checksum-archived)")

    ext, h_ext = verified(EXT, "validation_eval.json")
    src = "kaggle/artifacts_external_run1/validation_eval.json"
    base = "acceptance/X2_hanoi"
    for qid, q, p in (("gain", "mean macro-F1 gain vs BASE (detector boxes)", "mean_gain_macro_f1"),
                      ("seed_pairs", "seed pairs better (of 5)", "seed_pairs_better"),
                      ("cross_pairs", "cross pairs better (of 25)", "cross_pairs_better"),
                      ("Deep Caries.recall_delta", "Deep Caries recall delta", "minority_recall_delta/Deep Caries"),
                      ("Periapical Lesion.recall_delta", "Periapical Lesion recall delta", "minority_recall_delta/Periapical Lesion"),
                      ("gt_delta", "GT-box macro-F1 delta", "gt_macro_f1_delta"),
                      ("pass", "passed its acceptance rule", "pass")):
        add(f"neg.external.{qid}", f"external data (X2_hanoi): {q}", ext, f"{base}/{p}", src, h_ext, "read (checksum-archived)")

    ens, h_ens = json.loads(ENS.read_text(encoding="utf-8")), sha(ENS)
    src, kind = "reports/ensemble_evaluation_kaggle.json", "read (report-level file; not in a checksum-archived run)"
    for qid, q, p in (("gain", "5-seed ensemble: macro-F1 gain vs BASE mean (detector boxes)", "acceptance/macro_f1_gain_vs_base_mean"),
                      ("members_beaten", "5-seed ensemble: members beaten (of 5)", "acceptance/members_beaten"),
                      ("Deep Caries.recall_delta", "5-seed ensemble: Deep Caries recall delta", "acceptance/minority_recall_delta/Deep Caries"),
                      ("boot.ci95", "5-seed ensemble: bootstrap 95% CI of the gain (2,000 resamples)", "bootstrap_det_matched/ci95"),
                      ("pass", "5-seed ensemble: passed its acceptance rule", "acceptance/pass")):
        add(f"neg.ensemble.{qid}", q, ens, p, src, h_ens, kind)

    return {"format": "dentamind-negative-findings-traceability-v1", "script_sha256": sha(Path(__file__)),
            "notes": ["all three experiments were evaluated on the seed-42 project validation split, not on CV5 folds and not on the "
                      "test split; their criteria are the rules pre-registered for each experiment, not the CV5 acceptance protocol",
                      "Periapical Lesion has 9 validation findings: minority deltas are fragile",
                      "the ensemble file carries a 'latency' field from a separate single-split experiment; it is not reported here"],
            "rows": rows}


def fmt(v):
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return f"{v:.4f}"
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return json.dumps(v)
    return str(v)


def main():
    out_j, out_m = ROOT / "reports" / "negative_findings_traceability.json", ROOT / "reports" / "negative_findings_traceability.md"
    if out_j.exists() or out_m.exists():
        raise SystemExit("negative_findings_traceability.* exists: write a new version instead of overwriting")
    t = build()
    with open(out_j, "x", encoding="utf-8") as fh:
        json.dump(t, fh, indent=1)
    lines = ["# Negative-findings traceability (supplementary)", "",
             f"Generated by `scripts/build_negative_findings_traceability.py` (sha256 `{t['script_sha256']}`).", "",
             *[f"* {n}" for n in t["notes"]], "", "| ID | Quantity | Value | Source | JSON path | Kind |", "|---|---|---|---|---|---|"]
    for r in t["rows"]:
        lines.append(f"| `{r['id']}` | {r['quantity']} | {fmt(r['value'])} | {r['source']} | {r['json_path']} | {r['kind']} |")
    with open(out_m, "x", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {out_j.name} and {out_m.name}: {len(t['rows'])} rows")


if __name__ == "__main__":
    main()
