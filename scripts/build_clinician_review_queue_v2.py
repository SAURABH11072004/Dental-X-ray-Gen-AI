#!/usr/bin/env python
"""Clinician re-reading worksheet v2: v1 with OPAQUE image codes (no file name, no image hash, no exact box coordinates).

    .venv\\Scripts\\python.exe scripts\\build_clinician_review_queue_v2.py

Why: DENTEX annotations are public, so v1's `image_path` / `image_sha256` let a reviewer look up the original label of a box, which
breaks the blinding. v2 replaces them with random image codes (numpy default_rng(20261026)); the code -> file mapping goes into the
coordinator-only key. v1 files are verified against their manifest and left unchanged. Items, order and review IDs are identical to
v1. Shares no image. Writes reports/clinical_review/caries_rereading_*_v2.* (never overwritten).
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CR = ROOT / "reports" / "clinical_review"
SEED = 20261026


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    out = {"worksheet": CR / "caries_rereading_worksheet_v2_BLINDED.csv", "key": CR / "caries_rereading_key_v2_COORDINATOR_ONLY.csv",
           "manifest": CR / "caries_rereading_manifest_v2.json"}
    if any(p.exists() for p in out.values()):
        raise SystemExit("review queue v2 exists: build a new version instead of overwriting")
    man1 = json.loads((CR / "caries_rereading_manifest_v1.json").read_text(encoding="utf-8"))
    for e in man1["outputs"].values():
        if sha(ROOT / e["path"]) != e["sha256"]:
            raise SystemExit(f"{e['path']} does not match its v1 manifest")
    w1 = list(csv.DictReader(open(ROOT / man1["outputs"]["worksheet"]["path"], encoding="utf-8")))
    k1 = list(csv.DictReader(open(ROOT / man1["outputs"]["key"]["path"], encoding="utf-8")))
    paths = sorted({r["image_path"] for r in w1})
    codes = np.random.default_rng(SEED).permutation(len(paths))
    code_of = {p: f"IMG-{c + 1:03d}" for p, c in zip(paths, codes)}
    sha_of = {r["image_path"]: r["image_sha256"] for r in w1}
    answer = [c for c in w1[0] if c.startswith(("reviewer_", "image_quality", "comment", "review_date"))]
    w2 = [{"review_id": r["review_id"], "image_code": code_of[r["image_path"]], "fdi_tooth": r["fdi_tooth"],
           **{c: "" for c in answer}} for r in w1]
    k2 = [{**k, "image_code": code_of[w["image_path"]], "image_path": w["image_path"], "image_sha256": sha_of[w["image_path"]],
           "box_xyxy_px": w["box_xyxy_px"]} for k, w in zip(k1, w1)]
    assert [r["review_id"] for r in w1] == [r["review_id"] for r in k1]
    for p, rows in ((out["worksheet"], w2), (out["key"], k2)):
        with open(p, "x", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
    meta = {"format": "dentamind-clinician-rereading-queue-v2", "derived_from": "caries_rereading_manifest_v1.json",
            "v1_manifest_sha256": sha(CR / "caries_rereading_manifest_v1.json"), "image_code_seed": SEED, "images": len(paths),
            "items": len(w2), "script_sha256": sha(Path(__file__)),
            "change": "image_path, image_sha256 and the exact box coordinates removed from the reviewer worksheet (all three could be "
                      "matched against the public DENTEX annotations); opaque image codes added; mapping and box only in the "
                      "coordinator key, from which the coordinator configures the viewer that draws the box",
            "status": "PREPARED ONLY - no image shared, no review performed; blocked until a clinical lead and the governance decision exist",
            "outputs": {k: {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(p)} for k, p in out.items() if k != "manifest"}}
    with open(out["manifest"], "x", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)
    print(f"v2 worksheet: {len(w2)} items on {len(paths)} images (opaque codes); key; manifest")


if __name__ == "__main__":
    main()
