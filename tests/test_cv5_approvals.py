"""Tests for kaggle/cv5_approvals.py (DRAFT Amendment 03: D-B2 human approval records, D-B3 metric sealing, D-B4 BASE-P2 gate).
Every approval, approver, status and archive here is a SYNTHETIC fixture in a temp folder."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kaggle"))
import cv5_approvals as CAP  # noqa: E402

T = "2026-10-25T00:00:00+00:00"


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture()
def artifact(tmp_path):
    p = tmp_path / "artifact.md"
    p.write_text("fixture artifact v1")
    return p


def _rec(artifact, scope="amendment_01_registration", **kw):
    return CAP.make_approval_record(scope, artifact, kw.pop("name", "Fixture Approver"), kw.pop("role", "fixture role"),
                                    kw.pop("statement", "Fixture approval statement for a test only."), approved_at=kw.pop("at", T))


# ---------------------------------------------------------------------------------------------------- D-B2 approval records
def test_valid_record_is_bound_to_the_exact_artifact_and_is_not_a_signature(artifact, tmp_path):
    rec = _rec(artifact)
    v = CAP.verify_approval(rec, artifact, "amendment_01_registration")
    assert v["artifact_sha256"] == _sha(artifact) and v["digital_signature"] is False
    p = tmp_path / "rec.json"
    p.write_text(json.dumps(rec))
    assert CAP.verify_approval(p, artifact, "amendment_01_registration")["approver"] == "Fixture Approver"


def test_record_refusals(artifact, tmp_path):
    rec = _rec(artifact)
    with pytest.raises(CAP.ApprovalError, match="scope"):
        CAP.verify_approval(rec, artifact, "amendment_02_registration")
    with pytest.raises(CAP.ApprovalError, match="unknown approval scope"):
        CAP.verify_approval(rec, artifact, "anything")
    artifact.write_text("fixture artifact v2")                                  # approved artifact changed afterwards
    with pytest.raises(CAP.ApprovalError, match="artifact SHA-256 differs"):
        CAP.verify_approval(rec, artifact, "amendment_01_registration")
    with pytest.raises(CAP.ApprovalError, match="not found"):
        CAP.verify_approval(rec, tmp_path / "none.md", "amendment_01_registration")
    edited = copy.deepcopy(_rec(artifact))
    edited["approver"]["name"] = "Someone Else"
    with pytest.raises(CAP.ApprovalError, match="edited after"):
        CAP.verify_approval(edited, artifact, "amendment_01_registration")


@pytest.mark.parametrize("kw, msg", [
    (dict(name=" "), "approver name"), (dict(role="<role>"), "approver role"), (dict(statement="ok"), "statement shorter"),
    (dict(at="2026-10-25T00:00:00"), "timezone-aware"), (dict(at="not a time"), "timezone-aware"),
])
def test_incomplete_records_are_refused(artifact, kw, msg):
    with pytest.raises(CAP.ApprovalError, match=msg):
        CAP.verify_approval(_rec(artifact, **kw), artifact, "amendment_01_registration")


def test_future_dates_and_unverifiable_signature_claims_are_refused(artifact):
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    with pytest.raises(CAP.ApprovalError, match="in the future"):
        CAP.verify_approval(_rec(artifact, at=future), artifact, "amendment_01_registration")
    rec = _rec(artifact)
    rec["signature"] = {"type": "pgp", "value": "fixture"}
    rec["content_sha256"] = CAP.approval_content_sha256(rec)
    with pytest.raises(CAP.ApprovalError, match="digital signature that cannot be verified"):
        CAP.verify_approval(rec, artifact, "amendment_01_registration")


# ---------------------------------------------------------------------------------------------------- D-B3 sealing
@pytest.fixture()
def sealed(tmp_path):
    files = {}
    for n in ("cv5_results.json", "oof_predictions.csv"):
        p = tmp_path / n
        p.write_text(f"{n} fixture value 0.5")
        files[n] = p
    man = CAP.make_sealed_archive(files, tmp_path / "sealed.zip")
    return tmp_path / "sealed.zip", man, files


def test_sealed_archive_written_once_and_manifest_has_no_values(sealed, tmp_path):
    z, man, files = sealed
    assert man["archive_sha256"] == _sha(z) and set(man["files"]) == set(files) and "0.5" not in json.dumps(man)
    with pytest.raises(CAP.SealError, match="written once"):
        CAP.make_sealed_archive(files, z)
    with pytest.raises(CAP.SealError, match="missing"):
        CAP.make_sealed_archive({"x": tmp_path / "none"}, tmp_path / "s2.zip")


def test_release_requires_integrity_gate_r_and_a_bound_approval(sealed, tmp_path):
    z, man, _ = sealed
    ok_r = {"pass": True, "R1_argmax_mismatches": 0, "R2_max_abs_prob_diff": 0.0, "R3_identical": True}
    appr = _rec(z, scope="base_p2_metrics_release")
    rel = CAP.release_sealed_metrics(z, man, ok_r, True, appr)
    assert rel["released"] and rel["approval"]["artifact_sha256"] == man["archive_sha256"]
    with pytest.raises(CAP.SealError, match="integrity"):
        CAP.release_sealed_metrics(z, man, ok_r, False, appr)
    with pytest.raises(CAP.SealError, match="gate R"):
        CAP.release_sealed_metrics(z, man, dict(ok_r, **{"pass": False}), True, appr)
    with pytest.raises(CAP.SealError, match="gate R"):
        CAP.release_sealed_metrics(z, man, None, True, appr)
    with pytest.raises(CAP.SealError, match="no valid release approval"):
        CAP.release_sealed_metrics(z, man, ok_r, True, _rec(z, scope="base_p2_registration"))
    other = tmp_path / "other.txt"
    other.write_text("x")
    with pytest.raises(CAP.SealError, match="no valid release approval"):
        CAP.release_sealed_metrics(z, man, ok_r, True, _rec(other, scope="base_p2_metrics_release"))
    z.write_bytes(z.read_bytes() + b"\0")                                       # archive altered
    with pytest.raises(CAP.SealError, match="not the sealed version"):
        CAP.release_sealed_metrics(z, man, ok_r, True, appr)


# ---------------------------------------------------------------------------------------------------- D-B4 BASE-P2 gate
def _status(ok=True, drop=0, cls=None):
    runs = {f"CV5_BASEP2_f{k}_s{s}": "ok" for k in range(5) for s in range(42, 47)}
    for r in list(runs)[:drop]:
        del runs[r]
    if cls:
        runs["CV5_BASEP2_f2_s43"] = cls
    return {"run_classes": runs, "n_expected": 25, "all_ok": ok and not drop and not cls}


def test_base_p2_gate_requires_all_25_runs_ok():
    assert CAP.check_base_p2_complete(_status())["base_p2_complete"]
    for st in (_status(drop=1), _status(cls="divergence"), _status(cls="infrastructure"), _status(cls="incomplete"),
               dict(_status(), n_expected=20), dict(_status(), all_ok=False), {}):
        with pytest.raises(CAP.BaseP2NotReady, match="Candidate evaluation stops"):
            CAP.check_base_p2_complete(st)


def test_failure_resolution_must_be_approved_and_bound(tmp_path):
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps(_status(cls="divergence")))
    res = CAP.check_failure_resolution(failed, _rec(failed, scope="base_p2_failure_resolution"))
    assert res["failed_run_status_sha256"] == _sha(failed)
    with pytest.raises(CAP.BaseP2NotReady, match="not approved"):
        CAP.check_failure_resolution(failed, _rec(failed, scope="base_p2_registration"))
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_status()))
    with pytest.raises(CAP.BaseP2NotReady, match="no failure to resolve"):
        CAP.check_failure_resolution(good, _rec(good, scope="base_p2_failure_resolution"))
    with pytest.raises(CAP.BaseP2NotReady, match="required"):
        CAP.check_failure_resolution(tmp_path / "none.json", {})
