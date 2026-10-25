#!/usr/bin/env python
"""Build the immutable CV5 import manifest (kaggle/cv5_imports.FORMAT) from clinician-verified labels. LOCAL step, run by the
project owner only after clinicians have reviewed; it never invents a label, reviewer, provenance field or count.

    .venv\\Scripts\\python.exe scripts\\dataset\\build_cv5_import_manifest.py --provenance <source_provenance.json> --out <manifest.json>

Inputs (all must exist; nothing is created if one is missing):
* data/annotation/verified_findings.csv     exported by clinical_review.export_verified (P1 route)
* data/annotation/clinical_reviews.jsonl    hash-chained review log (must verify)
* data/annotation/reviewers.csv             registered reviewers
* data/annotation/annotation_pool.csv       pool identities and split locks
* <source_provenance.json>                  one complete record per pool source_dataset (template: reports/templates/)
* <reviewer_authorization.json>             versioned authorization derived from reviewers.csv (build_reviewer_authorization.py);
                                            every finding must come from a listed, active reviewer inside the validity window

Every row goes through verified_to_manifest.verified_training_rows (chain, latest decision, accepted label, registered reviewer,
eligibility, image SHA-256, crop rule). Rows it skips, and rows from pool radiographs not locked 'unassigned', are listed under
"excluded" with the reason and are NOT imported. The manifest is written once; an existing file is never overwritten. Its SHA-256 is
printed for entry in Amendment 02.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (HERE, ROOT / "kaggle"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import clinical_review as CR  # noqa: E402
import cv5_imports as CI  # noqa: E402
from dsutil import read_csv  # noqa: E402
from verified_to_manifest import verified_training_rows  # noqa: E402


def build(verified_csv, log, reviewers_csv, pool_csv, splits_dir, data_root, provenance: dict, authorization_path,
          created_by_note: str = "") -> dict:
    for f in (verified_csv, log, reviewers_csv, pool_csv, authorization_path):
        if not Path(f).is_file():
            raise CI.ImportRefused(f"required input missing: {f}")
    auth_sha = hashlib.sha256(Path(authorization_path).read_bytes()).hexdigest()
    auth = CI.load_reviewer_authorization(authorization_path, auth_sha)
    if auth["registry_sha256"] != hashlib.sha256(Path(reviewers_csv).read_bytes()).hexdigest():
        raise CI.ImportRefused("reviewer authorization was not derived from this reviewers.csv (registry_sha256 mismatch: stale or foreign)")
    ok_chain, n_rec = CR.verify_chain(log)
    if not ok_chain:
        raise CI.ImportRefused(f"review log {log} fails its hash-chain check")
    rows, skipped = verified_training_rows(verified_csv, pool_csv, splits_dir, data_root, log=log, reviewers_csv=reviewers_csv)
    latest = {(r["pool_id"], r["region_id"]): r for r in CR.latest_decisions(log).values()}
    pool = {r["pool_id"]: r for r in read_csv(pool_csv)}
    findings, excluded = [], [{"row": k, "reason": why} for k, why in skipped]
    for r in rows:
        _, pool_id, region_id = r["sample_id"].split(":", 2)
        p, rec = pool[pool_id], latest[(pool_id, region_id)]
        if p["split_lock"] != CI.IMPORTABLE_SPLIT_LOCK:
            excluded.append({"row": r["sample_id"], "reason": f"pool split_lock {p['split_lock']!r}: twin of a project radiograph; "
                                                                "under CV every project radiograph is held out once"})
            continue
        src = p["source_dataset"]
        if src not in provenance:
            raise CI.ImportRefused(f"no provenance record for source {src!r} (needed by {r['sample_id']})")
        findings.append({
            "sample_id": r["sample_id"], "pool_id": pool_id, "region_id": region_id, "split_lock": p["split_lock"],
            "image_path": r["image_path"], "image_sha256": r["image_sha256"], "radiograph_group": r["radiograph_group"],
            "bbox_xywh": json.dumps(r["bbox_xywh"]), "target_class": r["target_class"], "class_index": int(r["class_index"]),
            "source_dataset": src, "source_id": src, "label_source": f"clinician review ({rec.get('decision')}), Label Studio",
            "fdi_tooth": r.get("fdi_tooth") or "",
            "verification": {"review_record_hash": rec["record_hash"], "reviewer_id": rec["reviewer_id"], "status": rec["status"],
                             "decision": rec["decision"], "reviewed_at": rec["reviewed_at"]}})
    if not findings:
        raise CI.ImportRefused("no eligible clinician-verified finding: nothing to import")
    for f in findings:
        f["binding_sha256"] = CI.binding_sha256(f, auth_sha)
    sources = {s: provenance[s] for s in sorted({f["source_id"] for f in findings})}
    sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()                     # noqa: E731
    m = {"format": CI.FORMAT, "created": datetime.now(timezone.utc).isoformat(), "note": created_by_note,
         "inputs": {"verified_findings_sha256": sha(verified_csv), "review_log_sha256": sha(log), "review_log_records": n_rec,
                    "reviewers_sha256": sha(reviewers_csv), "annotation_pool_sha256": sha(pool_csv)},
         "reviewer_authorization": {"sha256": auth_sha, "version": auth["version"]},
         "findings": findings, "sources": sources, "excluded": excluded, "content_sha256": CI.content_sha256(findings, sources)}
    CI.validate_manifest(m, reviewer_ids={r["reviewer_id"] for r in CR.load_reviewers(reviewers_csv).values()})
    CI.check_reviewer_bindings(m, auth)
    return m


def write_once(m: dict, out) -> str:
    out = Path(out)
    if out.exists():
        raise CI.ImportRefused(f"{out} exists: an import manifest is immutable; write a new file instead")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, ensure_ascii=False)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provenance", required=True)
    ap.add_argument("--authorization", required=True, help="reviewer_authorization_v<N>.json from build_reviewer_authorization.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-root", default=str(ROOT / "data"))
    a = ap.parse_args()
    ann = ROOT / "data" / "annotation"
    m = build(ann / "verified_findings.csv", ann / "clinical_reviews.jsonl", ann / "reviewers.csv", ann / "annotation_pool.csv",
              ROOT / "data" / "splits", a.data_root, json.loads(Path(a.provenance).read_text(encoding="utf-8")), a.authorization)
    h = write_once(m, a.out)
    print(f"wrote {a.out}: {len(m['findings'])} findings, {len(m['excluded'])} excluded; sha256 {h}")


if __name__ == "__main__":
    main()
