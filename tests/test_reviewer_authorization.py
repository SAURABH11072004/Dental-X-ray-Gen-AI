"""Tests for the reviewer-authorization artifact (scripts/dataset/build_reviewer_authorization.py, kaggle/cv5_imports.py).
All reviewers, registries and reviews here are SYNTHETIC fixtures in a temp folder (see tests/test_cv5_imports.py world)."""
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_cv5_import_manifest as BM  # noqa: E402
import build_reviewer_authorization as BRA  # noqa: E402
import clinical_review as CR  # noqa: E402
import cv5_imports as CIM  # noqa: E402
from test_cv5_imports import PROVENANCE, built, world  # noqa: E402,F401  (fixture)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _registry(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CR.REVIEWER_FIELDS)
        w.writeheader()
        w.writerows(rows)


def _rev(rid, user, attested="2026-10-01", **kw):
    return {"reviewer_id": rid, "display_name": f"Fixture {rid}", "qualification": "fixture", "registration_no": f"REG-{rid}",
            "ls_user": user, "attested_by": "fixture", "attested_on": attested, **kw}


def test_artifact_carries_no_personal_data_and_only_attested_reviewers(tmp_path):
    reg = tmp_path / "reviewers.csv"
    _registry(reg, [_rev("R1", "r1@x"), _rev("R2", "r2@x"), {**_rev("R3", "r3@x"), "attested_by": ""}])   # R3 not attested
    a = BRA.build(reg, 1, "fixture issuer")
    assert [r["reviewer_id"] for r in a["reviewers"]] == ["R1", "R2"]
    text = json.dumps(a)
    for personal in ("Fixture R1", "REG-R1", "r1@x", "display_name", "registration_no", "ls_user"):
        assert personal not in text
    assert a["registry_sha256"] == _sha(reg) and CIM.validate_authorization(a)["active"] == 2
    out = tmp_path / "auth_v1.json"
    h = BRA.write_once(a, out)
    assert CIM.load_reviewer_authorization(out, h)["version"] == 1
    with pytest.raises(CIM.ImportRefused, match="written once"):
        BRA.write_once(a, out)


def test_refuses_without_registry_issuer_or_attested_reviewer(tmp_path):
    with pytest.raises(CIM.ImportRefused):
        BRA.build(tmp_path / "missing.csv", 1, "x")
    reg = tmp_path / "reviewers.csv"
    _registry(reg, [_rev("R1", "r1@x")])
    with pytest.raises(CIM.ImportRefused, match="issued-by"):
        BRA.build(reg, 1, "  ")
    _registry(reg, [{**_rev("R1", "r1@x"), "qualification": ""}])
    with pytest.raises(CIM.ImportRefused, match="no attested reviewer"):
        BRA.build(reg, 1, "x")


def test_versions_chain_and_revocations_persist(tmp_path):
    reg = tmp_path / "reviewers.csv"
    _registry(reg, [_rev("R1", "r1@x"), _rev("R2", "r2@x")])
    v1 = tmp_path / "v1.json"
    BRA.write_once(BRA.build(reg, 1, "x", revoke=["R2=2026-10-20"]), v1)
    with pytest.raises(CIM.ImportRefused, match="--previous"):
        BRA.build(reg, 2, "x")
    with pytest.raises(CIM.ImportRefused, match="stay revoked"):
        BRA.build(reg, 2, "x", previous=v1)
    v2 = BRA.build(reg, 2, "x", previous=v1, revoke=["R2=2026-10-20"], valid_to=["R1=2027-01-01"])
    assert v2["previous_version_sha256"] == _sha(v1) and {r["reviewer_id"]: r["status"] for r in v2["reviewers"]} == {"R1": "active", "R2": "revoked"}
    with pytest.raises(CIM.ImportRefused, match="not in the registry"):
        BRA.build(reg, 1, "x", revoke=["R9=2026-10-20"])


@pytest.mark.parametrize("mutate, msg", [
    (lambda a: a["reviewers"][0].update(display_name="Someone"), "not allowed"),
    (lambda a: a["reviewers"][0].update(status="suspended"), "status must be"),
    (lambda a: a["reviewers"][0].update(status="revoked", revoked_on=None), "revoked without revoked_on"),
    (lambda a: a["reviewers"][0].update(qualification_attested=False), "attestation"),
    (lambda a: a.update(version=2), "previous version"),
])
def test_validation_rejects(tmp_path, mutate, msg):
    reg = tmp_path / "reviewers.csv"
    _registry(reg, [_rev("R1", "r1@x")])
    a = BRA.build(reg, 1, "x")
    mutate(a)
    a["content_sha256"] = CIM.authorization_content_sha256(a)
    with pytest.raises(CIM.ImportRefused, match=msg):
        CIM.validate_authorization(a)
    b = BRA.build(reg, 1, "x")
    b["reviewers"][0]["valid_to"] = "2030-01-01"                                # edited without re-hashing
    with pytest.raises(CIM.ImportRefused, match="edited after it was issued"):
        CIM.validate_authorization(b)


# ---------------------------------------------------------------------------------------------------- binding to the manifest
def test_manifest_is_bound_to_the_authorization(world):
    m = built(world)
    assert m["reviewer_authorization"] == {"sha256": _sha(world["auth"]), "version": 1}
    auth = CIM.load_reviewer_authorization(world["auth"], _sha(world["auth"]))
    out = world["tmp"] / "m.json"
    m2 = CIM.load_import_manifest(out, BM.write_once(m, out))
    assert CIM.check_reviewer_bindings(m2, auth) == {"authorization_version": 1, "findings_checked": 4, "reviewers_used": 1}
    f = copy.deepcopy(m)                                                        # label changed after review, content re-hashed
    f["findings"][0]["target_class"], f["findings"][0]["class_index"] = "Caries", 0
    f["content_sha256"] = CIM.content_sha256(f["findings"], f["sources"])
    with pytest.raises(CIM.ImportRefused, match="binding hash does not match"):
        CIM.validate_manifest(f)


def test_bindings_reject_unlisted_revoked_out_of_window_and_stale(world, tmp_path):
    m = built(world)
    out = world["tmp"] / "m.json"
    m = CIM.load_import_manifest(out, BM.write_once(m, out))
    good = CIM.load_reviewer_authorization(world["auth"], _sha(world["auth"]))

    def variant(**rev):
        a = copy.deepcopy({k: v for k, v in good.items() if not k.startswith("_")})
        a["reviewers"][0].update(rev)
        a["content_sha256"] = CIM.authorization_content_sha256(a)
        p = tmp_path / f"a_{len(list(tmp_path.iterdir()))}.json"
        p.write_text(json.dumps(a))
        loaded = CIM.load_reviewer_authorization(p, _sha(p))
        m2 = dict(m, reviewer_authorization={"sha256": loaded["_file_sha256"], "version": loaded["version"]})
        return m2, loaded

    for rev, msg in (({"reviewer_id": "R9"}, "not in the authorization"), ({"status": "revoked", "revoked_on": "2026-10-26"}, "revoked"),
                     ({"valid_to": "2026-10-24"}, "outside the reviewer's authorization window"),
                     ({"valid_from": "2026-10-26"}, "outside the reviewer's authorization window")):
        m2, a2 = variant(**rev)
        with pytest.raises(CIM.ImportRefused, match=msg):
            CIM.check_reviewer_bindings(m2, a2)
    _, other = variant(valid_to="2030-01-01")                                    # a different (e.g. newer) version than the build used
    with pytest.raises(CIM.ImportRefused, match="different reviewer-authorization version"):
        CIM.check_reviewer_bindings(m, other)
    with pytest.raises(CIM.ImportRefused, match="registered one"):
        CIM.load_reviewer_authorization(world["auth"], "0" * 64)
    with pytest.raises(CIM.ImportRefused, match="does not exist"):
        CIM.load_reviewer_authorization(tmp_path / "none.json", "0" * 64)


def test_builder_refuses_an_authorization_from_another_registry(world, tmp_path):
    reg = tmp_path / "other_reviewers.csv"
    _registry(reg, [_rev("R1", "r1@test")])
    foreign = tmp_path / "foreign_auth.json"
    BRA.write_once(BRA.build(reg, 1, "x"), foreign)
    with pytest.raises(CIM.ImportRefused, match="registry_sha256 mismatch"):
        BM.build(*world["args"], copy.deepcopy(PROVENANCE), foreign)


def test_db1_revocation_rejects_new_imports_and_leaves_history_unchanged(world, tmp_path):
    """DRAFT Amendment 03 D-B1: after a revocation (a NEW authorization version), new manifests refuse the reviewer's labels; the
    earlier authorization version, the review log and earlier manifests stay byte-identical."""
    v1 = world["auth"]
    v1_bytes, log_bytes = v1.read_bytes(), world["log"].read_bytes()
    old_manifest = world["tmp"] / "m_v1.json"
    old_sha = BM.write_once(built(world), old_manifest)
    v2 = world["ann"] / "reviewer_authorization_v2.json"
    BRA.write_once(BRA.build(world["ann"] / "reviewers.csv", 2, "fixture issuer", previous=v1, revoke=["R1=2026-10-26"]), v2)
    with pytest.raises(CIM.ImportRefused, match="revoked"):
        BM.build(*world["args"], copy.deepcopy(PROVENANCE), v2)
    a2 = CIM.load_reviewer_authorization(v2, _sha(v2))
    m1 = CIM.load_import_manifest(old_manifest, old_sha)
    with pytest.raises(CIM.ImportRefused, match="different reviewer-authorization version"):
        CIM.check_reviewer_bindings(m1, a2)                                     # an old manifest cannot be used under v2 either
    assert v1.read_bytes() == v1_bytes and world["log"].read_bytes() == log_bytes and _sha(old_manifest) == old_sha
