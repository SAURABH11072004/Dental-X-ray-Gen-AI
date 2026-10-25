"""Tests of the PROPOSED, UNAPPLIED approval-tooling patch patches/cv5_approvals_policy_tooling.patch (DRAFT approval policy).

The patch is applied only to a temporary copy of kaggle/cv5_approvals.py (the live module stays byte-identical). Every person, register,
log and record here is a SYNTHETIC fixture in a temp folder; no real approval exists or is created."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "cv5_approvals_policy_tooling.patch"
LIVE = ROOT / "kaggle" / "cv5_approvals.py"
LIVE_SHA = "19d83c4251029ab937494f0c91a09e462611906452fa740cec75b435dd66d340"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)          # synthetic clock in the past (future approvals are refused)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def A(tmp_path_factory):
    t = tmp_path_factory.mktemp("approvals_patched")
    (t / "kaggle").mkdir()
    shutil.copy2(LIVE, t / "kaggle" / "cv5_approvals.py")
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(t.parent)}
    r = subprocess.run(["git", "-c", "core.autocrlf=false", "apply", str(PATCH)], cwd=t, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    spec = importlib.util.spec_from_file_location("cv5_approvals_patched", t / "kaggle" / "cv5_approvals.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_patch_targets_the_live_module_and_is_not_applied():
    assert _sha(LIVE) == LIVE_SHA
    r = subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--check", str(PATCH)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert _sha(LIVE) == LIVE_SHA and PATCH.read_text(encoding="utf-8").count("diff --git") == 1


def test_existing_api_unchanged(A, tmp_path):
    a = tmp_path / "x.md"
    a.write_text("artifact")
    rec = A.make_approval_record("amendment_01_registration", a, "F O", "project_owner", "Fixture statement long enough.",
                                 "2026-10-25T00:00:00+00:00")
    assert A.verify_approval(rec, a, "amendment_01_registration")["digital_signature"] is False
    for s in ("patch_set_application", "amendment_01c_freeze", "clinical_governance_decision"):
        assert s in A.SCOPES and s in A.POLICY


# ---------------------------------------------------------------------------------------------------- synthetic world
class World:
    def __init__(self, A, tmp):
        self.A, self.tmp, self.log, self.n = A, tmp, tmp / "approval_log.jsonl", 0
        reg = {"format": A.REGISTER_FORMAT, "version": 1, "issued_at": T0.isoformat(), "previous_version_sha256": None,
               "approvers": [
                   {"name": "Fixture Owner", "roles": ["project_owner"], "valid_from": T0.isoformat(), "valid_to": None, "status": "active"},
                   {"name": "Fixture Clinician", "roles": ["clinical_lead"], "valid_from": T0.isoformat(), "valid_to": None, "status": "active"},
                   {"name": "Fixture Reviewer", "roles": ["independent_reviewer"], "valid_from": T0.isoformat(), "valid_to": None,
                    "status": "active"},
                   {"name": "Fixture Former", "roles": ["project_owner"], "valid_from": T0.isoformat(), "valid_to": None,
                    "status": "revoked", "revoked_on": (T0 + timedelta(hours=2)).isoformat()}]}   # revoked before the approvals below
        reg["content_sha256"] = A.register_content_sha256(reg)
        self.reg_path = tmp / "approver_register_v1.json"
        self.reg_path.write_text(json.dumps(reg))
        self.reg = A.load_register(self.reg_path, _sha(self.reg_path))
        self.clock = T0

    def tick(self, hours=1):
        self.clock += timedelta(hours=hours)
        return self.clock.isoformat()

    def artifact(self, name, text=None):
        p = self.tmp / name
        p.write_text(text or f"fixture artifact {name}")
        self.A.append_log(self.log, "artifact_registered", at=self.tick(), artifact_sha256=_sha(p), path=name)
        return p

    def approve(self, scope, artifact, who="Fixture Owner", role="project_owner", at=None, log=True):
        self.n += 1
        at = at or self.tick()
        rec = self.A.make_approval_record(scope, artifact, who, role, "Fixture approval statement for a test only.", approved_at=at)
        p = self.tmp / f"rec_{self.n}_{scope}.json"
        rsha = self.A.write_approval_record(rec, p)
        if log:
            self.A.append_log(self.log, "approval_recorded", at=self.tick(), record_sha256=rsha, scope=scope,
                              artifact_sha256=_sha(artifact), approver=who, role=role)
        return p

    def verify(self, rec, artifact, scope, cs=False):
        return self.A.verify_approval_policy(rec, artifact, scope, self.reg, self.log, as_countersign=cs)

    def bootstrap(self):
        pol = self.artifact("policy.md")
        self.verify(self.approve("approval_policy_adoption", pol), pol, "approval_policy_adoption")
        self.verify(self.approve("approver_register_issue", self.reg_path_logged()), self.reg_path, "approver_register_issue")

    def reg_path_logged(self):
        self.A.append_log(self.log, "artifact_registered", at=self.tick(), artifact_sha256=_sha(self.reg_path), path="register")
        return self.reg_path


@pytest.fixture()
def W(A, tmp_path):
    return World(A, tmp_path)


def test_valid_flow_with_countersignatures(W):
    W.bootstrap()
    a3 = W.artifact("amendment_03.md")
    r1 = W.approve("amendment_03_decisions", a3)
    r2 = W.approve("amendment_03_decisions", a3, "Fixture Clinician", "clinical_lead")
    assert W.A.approval_complete("amendment_03_decisions", a3, W.reg, W.log, [r1, r2])["complete"]
    ps = W.artifact("patch_set.json")
    p1 = W.approve("patch_set_application", ps)
    p2 = W.approve("patch_set_application", ps, "Fixture Reviewer", "independent_reviewer")
    res = W.A.approval_complete("patch_set_application", ps, W.reg, W.log, [p1, p2])
    assert res["approvers"] == ["Fixture Owner"] and res["countersigned_by"] == ["Fixture Reviewer"]
    W.A.append_log(W.log, "execution_started", at=W.tick(), artifact_sha256=_sha(ps))
    W.A.append_log(W.log, "execution_completed", at=W.tick(), artifact_sha256="e" * 64, kind="plan_v2_steps_5_12")
    c = W.artifact("amendment_01c.md")
    q1 = W.approve("amendment_01c_freeze", c)
    q2 = W.approve("amendment_01c_freeze", c, "Fixture Reviewer", "independent_reviewer")
    assert W.A.approval_complete("amendment_01c_freeze", c, W.reg, W.log, [q1, q2])["complete"]
    cg = W.artifact("clinical_governance.md")
    g1 = W.approve("clinical_governance_decision", cg, "Fixture Clinician", "clinical_lead")
    g2 = W.approve("clinical_governance_decision", cg)
    assert W.A.approval_complete("clinical_governance_decision", cg, W.reg, W.log, [g1, g2])["countersigned_by"] == ["Fixture Owner"]


def test_unauthorized_roles_and_people_are_refused(W):
    W.bootstrap()
    a3 = W.artifact("amendment_03.md")
    W.approve("amendment_03_decisions", a3)
    ps = W.artifact("patch_set.json")
    with pytest.raises(W.A.ApprovalError, match="may not approve"):
        W.verify(W.approve("patch_set_application", ps, "Fixture Clinician", "clinical_lead"), ps, "patch_set_application")
    with pytest.raises(W.A.ApprovalError, match="holds no role"):
        W.verify(W.approve("patch_set_application", ps, "Fixture Clinician", "project_owner"), ps, "patch_set_application")
    with pytest.raises(W.A.ApprovalError, match="holds no role"):
        W.verify(W.approve("patch_set_application", ps, "Someone Else", "project_owner"), ps, "patch_set_application")
    with pytest.raises(W.A.ApprovalError, match="revoked"):
        W.verify(W.approve("patch_set_application", ps, "Fixture Former", "project_owner"), ps, "patch_set_application")
    cg = W.artifact("cg.md")
    with pytest.raises(W.A.ApprovalError, match="may not approve"):
        W.verify(W.approve("clinical_governance_decision", cg), cg, "clinical_governance_decision")   # the owner cannot decide clinically
    with pytest.raises(W.A.ApprovalError, match="cannot be approved"):
        W.verify(W.approve("import_wiring_patch_application", ps), ps, "import_wiring_patch_application")


def test_countersignature_must_be_a_different_person(W):
    W.bootstrap()
    a3 = W.artifact("amendment_03.md")
    r1 = W.approve("amendment_03_decisions", a3)
    with pytest.raises(W.A.ApprovalError, match="countersignature"):
        W.A.approval_complete("amendment_03_decisions", a3, W.reg, W.log, [r1])


def test_ordering_rules(W):
    W.bootstrap()
    ps = W.artifact("patch_set.json")
    with pytest.raises(W.A.ApprovalError, match="required earlier approval 'amendment_03_decisions'"):
        W.verify(W.approve("patch_set_application", ps), ps, "patch_set_application")           # predecessor missing
    a3 = W.artifact("amendment_03.md")
    W.approve("amendment_03_decisions", a3)
    early = W.tmp / "unlogged.md"
    early.write_text("not registered yet")
    with pytest.raises(W.A.ApprovalError, match="not registered in the log before"):
        W.verify(W.approve("patch_set_application", early, at=(W.clock - timedelta(minutes=1)).isoformat()), early,
                 "patch_set_application")                                                    # approval before the artifact existed
    ps2 = W.artifact("patch_set_2.json")
    W.A.append_log(W.log, "execution_started", at=W.tick(), artifact_sha256=_sha(ps2))
    with pytest.raises(W.A.ApprovalError, match="retrospective"):
        W.verify(W.approve("patch_set_application", ps2), ps2, "patch_set_application")
    ps3 = W.artifact("patch_set_3.json")
    W.verify(W.approve("patch_set_application", ps3), ps3, "patch_set_application")
    c = W.artifact("amendment_01c.md")
    with pytest.raises(W.A.ApprovalError, match="advance approval"):
        W.verify(W.approve("amendment_01c_freeze", c), c, "amendment_01c_freeze")


def test_log_integrity_and_no_overwrite(W):
    W.bootstrap()
    a3 = W.artifact("amendment_03.md")
    r = W.approve("amendment_03_decisions", a3)
    with pytest.raises(W.A.ApprovalError, match="already in the log"):
        W.A.append_log(W.log, "approval_recorded", at=W.tick(), record_sha256=_sha(r), scope="amendment_03_decisions",
                       artifact_sha256=_sha(a3), approver="Fixture Owner", role="project_owner")
    with pytest.raises(FileExistsError):
        W.A.write_approval_record({"x": 1}, r)
    with pytest.raises(W.A.ApprovalError, match="dated before"):
        W.A.append_log(W.log, "artifact_registered", at=T0.isoformat(), artifact_sha256="f" * 64)
    unlogged = W.approve("amendment_03_decisions", a3, log=False)
    with pytest.raises(W.A.ApprovalError, match="not in the approval log"):
        W.verify(unlogged, a3, "amendment_03_decisions")
    W.A.append_log(W.log, "approval_revoked", at=W.tick(), record_sha256=_sha(r))
    with pytest.raises(W.A.ApprovalError, match="revoked in the log"):
        W.verify(r, a3, "amendment_03_decisions")
    lines = W.log.read_text().splitlines()
    assert '"path": "policy.md"' in lines[0]
    lines[0] = lines[0].replace('"path": "policy.md"', '"path": "other.md"')            # edit an earlier entry
    W.log.write_text("\n".join(lines) + "\n")
    with pytest.raises(W.A.ApprovalError, match="broken"):
        W.A.read_log(W.log)


def test_register_rules(A, tmp_path):
    reg = {"format": A.REGISTER_FORMAT, "version": 1, "issued_at": T0.isoformat(), "previous_version_sha256": None,
           "approvers": [{"name": "Fixture Owner", "roles": ["project_owner"], "valid_from": T0.isoformat(), "status": "active"}]}
    reg["content_sha256"] = A.register_content_sha256(reg)
    p = tmp_path / "r.json"
    p.write_text(json.dumps(reg))
    A.load_register(p, _sha(p))
    with pytest.raises(A.ApprovalError, match="stale or modified"):
        A.load_register(p, "0" * 64)
    for change, msg in ((lambda r: r["approvers"][0].update(roles=["superuser"]), "roles"),
                        (lambda r: r["approvers"][0].update(name="<name>"), "placeholder"),
                        (lambda r: r.update(version=2), "previous version"),
                        (lambda r: r["approvers"][0].update(status="revoked"), "revoked with revoked_on")):
        bad = json.loads(json.dumps(reg))
        change(bad)
        bad["content_sha256"] = A.register_content_sha256(bad)
        with pytest.raises(A.ApprovalError, match=msg):
            A.validate_register(bad)
    edited = dict(reg, approvers=[dict(reg["approvers"][0], roles=["clinical_lead"])])
    with pytest.raises(A.ApprovalError, match="edited after"):
        A.validate_register(edited)


def test_signature_claims_still_refused(W):
    W.bootstrap()
    a3 = W.artifact("amendment_03.md")
    rec = W.A.make_approval_record("amendment_03_decisions", a3, "Fixture Owner", "project_owner", "Fixture statement long enough.",
                                   approved_at=W.tick())
    rec["signature"] = {"type": "gpg", "value": "fixture"}
    rec["content_sha256"] = W.A.approval_content_sha256(rec)
    p = W.tmp / "sig.json"
    W.A.write_approval_record(rec, p)
    W.A.append_log(W.log, "approval_recorded", at=W.tick(), record_sha256=_sha(p), scope="amendment_03_decisions",
                   artifact_sha256=_sha(a3), approver="Fixture Owner", role="project_owner")
    with pytest.raises(W.A.ApprovalError, match="digital signature"):
        W.verify(p, a3, "amendment_03_decisions")
