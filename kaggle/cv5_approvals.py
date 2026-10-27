"""Human approval records, BASE-P2 metric sealing and the BASE-P2 completeness gate (DRAFT Amendment 03, decisions D-B2 - D-B4; NOT
IN FORCE). Verification only: nothing here creates an approval, signs, releases metrics or runs anything on its own.

* Approval record (D-B2): an auditable JSON bound to ONE artifact by its SHA-256, with the approver's own name and role, a UTC time,
  a scope and a written statement. It is NOT a digital signature: the only accepted signature entry is {"type": "none"}; a record
  that claims any other signature type is refused, because no signature can be verified here.
* Sealed metrics (D-B3): the BASE-P2 notebook writes held-out metrics and predictions into a separate sealed archive and logs only its
  SHA-256. release_sealed_metrics() allows opening it only after the archive integrity check, a passing gate R in the candidate
  environment and an approval record of scope base_p2_metrics_release bound to that archive. Sealing is procedural and tamper-evident,
  not encryption: whoever can download the notebook output can technically open the archive.
* BASE-P2 gate (D-B4): candidate evaluation may use BASE-P2 only if all 25 runs are classified ok. A failed BASE-P2 is never
  repaired in place; a new BASE-P2 registration must cite the failed run status and an approval record of scope
  base_p2_failure_resolution bound to it. Retries stay exactly those of protocol section 9 (cv5_accept.run_isolated).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_FORMAT = "dentamind-human-approval-v1"
SEAL_FORMAT = "dentamind-sealed-metrics-v1"
SCOPES = ("amendment_01_registration", "amendment_01b_freeze", "amendment_02_registration", "amendment_03_decisions",
          "base_p2_registration", "import_wiring_patch_application", "reviewer_authorization_issue", "base_p2_metrics_release",
          "base_p2_failure_resolution")
MIN_STATEMENT = 20
SEALED_RESULTS = ("cv5_results.json", "oof_predictions.csv", "caries_confusion_findings.csv")   # + runs/*__heldout_pred.npz


class ApprovalError(ValueError):
    pass


class SealError(ValueError):
    pass


class BaseP2NotReady(ValueError):
    pass


def _canonical(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _utc(s):
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


# ------------------------------------------------------------------------------------------------------------- approvals (D-B2)
def approval_content_sha256(rec: dict) -> str:
    return hashlib.sha256(_canonical({k: rec.get(k) for k in ("format", "scope", "artifact", "approver", "approved_at", "statement",
                                                             "signature")})).hexdigest()


def make_approval_record(scope: str, artifact_path, approver_name: str, approver_role: str, statement: str,
                         approved_at: str | None = None) -> dict:
    """For the APPROVER to create their own record (the assistant never calls this with a real identity)."""
    rec = {"format": APPROVAL_FORMAT, "scope": scope,
           "artifact": {"path": Path(artifact_path).as_posix(), "sha256": _sha_file(artifact_path)},
           "approver": {"name": approver_name, "role": approver_role},
           "approved_at": approved_at or datetime.now(timezone.utc).isoformat(), "statement": statement, "signature": {"type": "none"}}
    rec["content_sha256"] = approval_content_sha256(rec)
    return rec


def verify_approval(record, artifact_path, scope: str, now: datetime | None = None) -> dict:
    """record: dict or path. Refuses unless the record is complete, unedited, of this scope, bound to this exact artifact file, dated
    in the past, and makes no unverifiable signature claim."""
    rec = json.loads(Path(record).read_text(encoding="utf-8")) if not isinstance(record, dict) else record
    probs = []
    if rec.get("format") != APPROVAL_FORMAT:
        raise ApprovalError(f"not a {APPROVAL_FORMAT} record")
    if rec.get("content_sha256") != approval_content_sha256(rec):
        raise ApprovalError("approval record was edited after it was made (content_sha256 mismatch)")
    if scope not in SCOPES:
        raise ApprovalError(f"unknown approval scope {scope!r}")
    if rec.get("scope") != scope:
        probs.append(f"scope is {rec.get('scope')!r}, required {scope!r}")
    art = rec.get("artifact") or {}
    p = Path(artifact_path) if artifact_path else None
    if not p or not p.is_file():
        probs.append("approved artifact file not found")
    elif art.get("sha256") != _sha_file(p):
        probs.append("artifact SHA-256 differs from the approved one (artifact changed or a different artifact)")
    who = rec.get("approver") or {}
    for k in ("name", "role"):
        v = str(who.get(k) or "").strip()
        if not v or "<" in v:
            probs.append(f"approver {k} missing")
    t = _utc(rec.get("approved_at"))
    if t is None:
        probs.append("approved_at is not a timezone-aware ISO time")
    elif t > (now or datetime.now(timezone.utc)):
        probs.append("approved_at is in the future")
    if len(str(rec.get("statement") or "").strip()) < MIN_STATEMENT:
        probs.append(f"statement shorter than {MIN_STATEMENT} characters")
    if (rec.get("signature") or {}).get("type") != "none":
        probs.append("record claims a digital signature that cannot be verified here; use signature {'type': 'none'}")
    if probs:
        raise ApprovalError("approval refused: " + "; ".join(probs))
    return {"scope": scope, "artifact_sha256": art["sha256"], "approver": who["name"], "role": who["role"],
            "approved_at": rec["approved_at"], "digital_signature": False}


# ------------------------------------------------------------------------------------------------------------- sealing (D-B3)
def make_sealed_archive(files: dict, out_zip) -> dict:
    """files {archive name: path}. Writes the sealed zip once and returns its manifest (names and hashes only, no values)."""
    import zipfile
    out = Path(out_zip)
    if out.exists():
        raise SealError(f"{out} exists: a sealed archive is written once")
    missing = [n for n, p in files.items() if not Path(p).is_file()]
    if missing:
        raise SealError(f"files to seal are missing: {missing}")
    with zipfile.ZipFile(out, "x", zipfile.ZIP_DEFLATED) as z:
        for n, p in sorted(files.items()):
            z.write(p, n)
    return {"format": SEAL_FORMAT, "archive": out.name, "archive_sha256": _sha_file(out),
            "files": {n: _sha_file(p) for n, p in sorted(files.items())},
            "release_condition": "archive integrity + gate R pass in the candidate environment + approval record "
                                 "(scope base_p2_metrics_release) bound to this archive"}


def release_sealed_metrics(sealed_zip, sealed_manifest: dict, gate_r_result: dict, archive_integrity_ok: bool, approval) -> dict:
    """Returns the release record only when every release condition holds; otherwise raises SealError. Does not open the archive."""
    if sealed_manifest.get("format") != SEAL_FORMAT:
        raise SealError("not a sealed-metrics manifest")
    p = Path(sealed_zip)
    if not p.is_file() or _sha_file(p) != sealed_manifest.get("archive_sha256"):
        raise SealError("sealed archive missing or not the sealed version")
    if archive_integrity_ok is not True:
        raise SealError("BASE-P2 archive integrity (SHA256SUMS) not verified")
    if not (isinstance(gate_r_result, dict) and gate_r_result.get("pass") is True):
        raise SealError("gate R has not passed in the candidate environment")
    try:
        a = verify_approval(approval, p, "base_p2_metrics_release")
    except ApprovalError as e:
        raise SealError(f"no valid release approval: {e}") from e
    return {"released": True, "archive_sha256": sealed_manifest["archive_sha256"], "approval": a,
            "gate_r": {k: gate_r_result.get(k) for k in ("R1_argmax_mismatches", "R2_max_abs_prob_diff", "R3_identical", "pass")}}


# ------------------------------------------------------------------------------------------------------------- BASE-P2 gate (D-B4)
def check_base_p2_complete(run_status: dict, n_expected: int = 25) -> dict:
    """BASE-P2 may serve as comparator only if every one of the 25 runs is classified ok (protocol section 9 classes)."""
    runs = (run_status or {}).get("run_classes") or {}
    bad = {r: c for r, c in runs.items() if c != "ok"}
    if run_status.get("n_expected") != n_expected or len(runs) != n_expected or bad or run_status.get("all_ok") is not True:
        raise BaseP2NotReady(f"BASE-P2 is not complete: {len(runs)}/{n_expected} runs reported, not ok: {dict(list(bad.items())[:10])}. "
                             "Candidate evaluation stops; a documented resolution and a new BASE-P2 registration are required.")
    return {"base_p2_complete": True, "runs": n_expected}


def check_failure_resolution(failed_run_status_path, approval) -> dict:
    """For a new BASE-P2 registration after a failed one: the failed run status must really be a failure, and an approval record of
    scope base_p2_failure_resolution must be bound to that exact file."""
    p = Path(failed_run_status_path)
    if not p.is_file():
        raise BaseP2NotReady("the failed BASE-P2 run_status.json is required")
    st = json.loads(p.read_text(encoding="utf-8"))
    try:
        check_base_p2_complete(st)
    except BaseP2NotReady:
        pass
    else:
        raise BaseP2NotReady("the cited BASE-P2 run status is complete: there is no failure to resolve")
    try:
        a = verify_approval(approval, p, "base_p2_failure_resolution")
    except ApprovalError as e:
        raise BaseP2NotReady(f"failure resolution not approved: {e}") from e
    return {"failed_run_status_sha256": _sha_file(p), "resolution": a}
