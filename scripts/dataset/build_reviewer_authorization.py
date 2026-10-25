#!/usr/bin/env python
"""Issue a versioned reviewer-authorization artifact from the LOCAL registry data/annotation/reviewers.csv. Run by the project owner.

    .venv\\Scripts\\python.exe scripts\\dataset\\build_reviewer_authorization.py --version 1 --issued-by "<owner's name or role>" \\
        --out data/annotation/reviewer_authorization_v1.json [--previous <v(N-1).json>] [--revoke R2=2026-11-30] [--valid-to R1=2027-12-31]

The artifact lists, for every reviewer that clinical_review.load_reviewers accepts (reviewer_id, qualification, attested_by and
ls_user all present): reviewer_id, qualification_attested, attested_on, valid_from (= attested_on), valid_to, status, revoked_on.
It deliberately contains NO display name, registration number, login or other personal field, so it can be attached to Kaggle; the
full registry stays local and is bound by registry_sha256. Each new version references the previous one by SHA-256; files are
written once and never overwritten. Nothing here creates or attests a reviewer: reviewers.csv is maintained by the owner.
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


def _pairs(items) -> dict:
    out = {}
    for it in items or []:
        rid, _, d = it.partition("=")
        if not rid or not d:
            raise CI.ImportRefused(f"expected REVIEWER_ID=YYYY-MM-DD, got {it!r}")
        CI._date(d)
        out[rid] = d
    return out


def build(reviewers_csv, version: int, issued_by: str, previous=None, revoke=None, valid_to=None) -> dict:
    reviewers_csv = Path(reviewers_csv)
    if not reviewers_csv.is_file():
        raise CI.ImportRefused(f"{reviewers_csv} does not exist")
    if not issued_by or not issued_by.strip():
        raise CI.ImportRefused("--issued-by is required (the accountable issuer, as the owner chooses to state it)")
    regs = list(CR.load_reviewers(reviewers_csv).values())
    if not regs:
        raise CI.ImportRefused("no attested reviewer in the registry: nothing to authorize")
    revoke, valid_to = _pairs(revoke), _pairs(valid_to)
    unknown = (set(revoke) | set(valid_to)) - {r["reviewer_id"] for r in regs}
    if unknown:
        raise CI.ImportRefused(f"revocation / validity given for reviewers not in the registry: {sorted(unknown)}")
    prev_sha = None
    if version > 1:
        if not previous or not Path(previous).is_file():
            raise CI.ImportRefused("a version > 1 needs --previous (the version it supersedes)")
        prev = json.loads(Path(previous).read_text(encoding="utf-8"))
        CI.validate_authorization(prev)
        if prev["version"] != version - 1:
            raise CI.ImportRefused(f"--previous is version {prev['version']}, expected {version - 1}")
        prev_sha = hashlib.sha256(Path(previous).read_bytes()).hexdigest()
        was_revoked = {r["reviewer_id"] for r in prev["reviewers"] if r["status"] == "revoked"}
        still = was_revoked - set(revoke)
        if still:
            raise CI.ImportRefused(f"previously revoked reviewers must stay revoked (repeat --revoke): {sorted(still)}")
    revs = []
    for r in sorted(regs, key=lambda r: r["reviewer_id"]):
        rid = r["reviewer_id"]
        revs.append({"reviewer_id": rid, "qualification_attested": True, "attested_on": r["attested_on"],
                     "valid_from": r["attested_on"], "valid_to": valid_to.get(rid),
                     "status": "revoked" if rid in revoke else "active", "revoked_on": revoke.get(rid)})
    a = {"format": CI.AUTH_FORMAT, "version": version, "issued_at": datetime.now(timezone.utc).isoformat(),
         "issued_by": issued_by.strip(), "registry_sha256": hashlib.sha256(reviewers_csv.read_bytes()).hexdigest(),
         "previous_version_sha256": prev_sha, "reviewers": revs}
    a["content_sha256"] = CI.authorization_content_sha256(a)
    CI.validate_authorization(a)
    return a


def write_once(a: dict, out) -> str:
    out = Path(out)
    if out.exists():
        raise CI.ImportRefused(f"{out} exists: authorization versions are written once")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(a, fh, indent=1)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--issued-by", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous")
    ap.add_argument("--revoke", action="append")
    ap.add_argument("--valid-to", action="append")
    a = ap.parse_args()
    auth = build(ROOT / "data" / "annotation" / "reviewers.csv", a.version, a.issued_by, a.previous, a.revoke, a.valid_to)
    print(f"wrote {a.out}: version {auth['version']}, {len(auth['reviewers'])} reviewers; sha256 {write_once(auth, a.out)}")


if __name__ == "__main__":
    main()
