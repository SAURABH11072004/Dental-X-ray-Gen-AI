"""Supplementary checks for the independent review of the UNAPPLIED approval-tooling patch (review packet
reports/review/approval_tooling_review_packet_v1.md). Same method as tests/test_cv5_approval_tooling_patch.py: the patch is applied to
a temporary copy only; every person and record is a synthetic fixture."""
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("tooling_base", Path(__file__).with_name("test_cv5_approval_tooling_patch.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
A = base.A            # module fixture: patched temporary copy
W = base.W
_sha = base._sha


def _dual_register(w):
    """Register in which one person holds both project_owner and independent_reviewer."""
    T0 = base.T0
    reg = {"format": w.A.REGISTER_FORMAT, "version": 1, "issued_at": T0.isoformat(), "previous_version_sha256": None,
           "approvers": [{"name": "Dual Person", "roles": ["project_owner", "independent_reviewer"], "valid_from": T0.isoformat(),
                          "valid_to": None, "status": "active"},
                         {"name": "Fixture Clinician", "roles": ["clinical_lead"], "valid_from": T0.isoformat(), "valid_to": None,
                          "status": "active"}]}
    reg["content_sha256"] = w.A.register_content_sha256(reg)
    w.reg_path.write_text(json.dumps(reg))
    w.reg = w.A.load_register(w.reg_path, _sha(w.reg_path))


def test_self_countersignature_under_a_second_role_is_refused(W):
    _dual_register(W)
    pol = W.artifact("policy.md")
    W.verify(W.approve("approval_policy_adoption", pol, "Dual Person"), pol, "approval_policy_adoption")
    W.verify(W.approve("approver_register_issue", W.reg_path_logged(), "Dual Person"), W.reg_path, "approver_register_issue")
    a3 = W.artifact("amendment_03.md")
    W.approve("amendment_03_decisions", a3, "Dual Person")
    ps = W.artifact("patch_set.json")
    p1 = W.approve("patch_set_application", ps, "Dual Person", "project_owner")
    p2 = W.approve("patch_set_application", ps, "Dual Person", "independent_reviewer")
    with pytest.raises(W.A.ApprovalError, match="countersignature"):
        W.A.approval_complete("patch_set_application", ps, W.reg, W.log, [p1, p2])


def test_record_cannot_be_used_for_another_scope_or_artifact(W):
    W.bootstrap()
    a3 = W.artifact("amendment_03.md")
    r = W.approve("amendment_03_decisions", a3)
    W.verify(r, a3, "amendment_03_decisions")
    with pytest.raises(W.A.ApprovalError):
        W.verify(r, a3, "patch_set_application")                       # wrong scope
    other = W.artifact("other.md")
    with pytest.raises(W.A.ApprovalError):
        W.verify(r, other, "amendment_03_decisions")                   # wrong artifact (hash binding)
    a3.write_text("edited after approval")
    with pytest.raises(W.A.ApprovalError):
        W.verify(r, a3, "amendment_03_decisions")                      # artifact changed after approval


def test_unknown_scope_and_future_dated_approval_are_refused(W):
    W.bootstrap()
    a = W.artifact("x.md")
    # review observation R1: creation does NOT validate the scope (live code, unchanged by the patch) ...
    rec = W.A.make_approval_record("not_a_scope", a, "Fixture Owner", "project_owner", "Fixture approval statement.",
                                   approved_at=W.tick())
    # ... but such a record can never verify, under the old or the new API
    with pytest.raises(W.A.ApprovalError, match="unknown approval scope"):
        W.A.verify_approval(rec, a, "not_a_scope")
    p = W.tmp / "bad_scope.json"
    W.A.write_approval_record(rec, p)
    with pytest.raises(W.A.ApprovalError):
        W.verify(p, a, "not_a_scope")
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    a3 = W.artifact("amendment_03.md")
    with pytest.raises(W.A.ApprovalError):
        W.verify(W.approve("amendment_03_decisions", a3, at=future, log=False), a3, "amendment_03_decisions")


def test_policy_table_matches_the_draft_policy(A):
    # countersigning roles and approvers of the DRAFT policy section 2 table
    expect = {"approval_policy_adoption": "project_owner", "patch_set_application": "project_owner",
              "amendment_01c_freeze": "project_owner", "clinical_governance_decision": "clinical_lead",
              "reviewer_authorization_issue": "clinical_lead"}
    for scope, role in expect.items():
        assert role in json.dumps(A.POLICY[scope]), (scope, A.POLICY[scope])
