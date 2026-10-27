# Independent-review packet: approval-tooling patch (v1)

Prepared 2026-10-25 for the **independent reviewer (IR)**. The packet decides nothing.
* The patch is **NOT applied**.
* No approval record, register or log exists.
* The reviewer's verdict, and any approval, must be recorded by the humans concerned, bound to the exact SHA-256 below.

## 1. Artifact under review

| Item | Value |
|---|---|
| Patch | `patches/cv5_approvals_policy_tooling.patch` |
| Patch SHA-256 | `de92744b…` (full value in §8, computed when this packet was generated) |
| Target file | `kaggle/cv5_approvals.py`, before-state SHA-256 `19d83c4251029ab937494f0c91a09e462611906452fa740cec75b435dd66d340` (verified unchanged) |
| Size | one file; 2 hunks; 224 lines added, 1 removed (the closing line of `SCOPES`, re-emitted with new entries) |
| Applies cleanly | `git -c core.autocrlf=false apply --check` → OK (re-run in this session) |
| Policy it implements | `reports/cv5_approval_policy_DRAFT.md` (DRAFT; §2 role table, §4 register, §5 ordering, §6 log) |
| Separate from | the CV5 patch set `patches/cv5_patch_set_v1.json` (`55271334…`), which this patch does not touch |

## 2. What the patch adds
* **Scopes:** `approval_policy_adoption`, `approver_register_issue`, `patch_set_application`, `amendment_01c_freeze` and
  `clinical_governance_decision`, added to `SCOPES`.
* **`POLICY`:** for each scope, the approving roles, the countersigning roles and the required earlier scopes.
  - The superseded `import_wiring_patch_application` gets empty approver roles, so it can never be approved.
* **Roles:** `ROLES` lists `project_owner`, `test_set_authorizer`, `clinical_lead`, `independent_reviewer` and `institution`.
* **Approver register:**
  - `register_content_sha256`, `validate_register`, `load_register(path, expected_sha256)`;
  - versioned and content-hashed, chained by `previous_version_sha256`;
  - placeholder names are refused;
  - revocation requires `revoked_on`.
* **Approval log:** `append_log` and `read_log` keep an append-only JSONL with `prev_hash` and `entry_hash`. Duplicate records,
  back-dated entries and edited earlier entries are rejected.
* **`write_approval_record`:** opens the file in exclusive-create mode, so an existing record is never overwritten.
* **`verify_approval_policy`:** layers the policy checks on the unchanged `verify_approval`:
  - role, register and validity window;
  - the record is logged and not revoked;
  - the artifact was registered before the approval;
  - required earlier approvals exist;
  - no retrospective approval of work already started;
  - no advance approval of Amendment 01c;
  - signature level S0 only.
* **`approval_complete`:** requires a countersignature by a **different person** in an allowed countersigning role, where the policy
  demands one.
* **Existing API:** `verify_approval`, `make_approval_record` and the sealing functions are unchanged.

## 3. Behaviour evidence (all on a temporary patched copy; the live module stays `19d83c42…`)

| Requirement from the review brief | Test | Result |
|---|---|---|
| Records cannot be overwritten | `test_log_integrity_and_no_overwrite` (`FileExistsError`) | pass |
| Self-countersignature rejected: same record only | `test_countersignature_must_be_a_different_person` | pass |
| Self-countersignature rejected: same person under a second role | `test_self_countersignature_under_a_second_role_is_refused` *(new, review supplement)* | pass |
| Incorrect scope rejected | `test_record_cannot_be_used_for_another_scope_or_artifact` *(new)* | pass |
| Record bound to the exact artifact; an edited artifact is rejected | same *(new)* | pass |
| Invalid ordering rejected (missing predecessor, approval before artifact, retrospective, advance) | `test_ordering_rules` | pass |
| Unauthorized roles, unknown people, revoked approvers, owner deciding clinically, superseded scope | `test_unauthorized_roles_and_people_are_refused` | pass |
| Log tampering, duplicates, back-dating, unlogged and revoked records | `test_log_integrity_and_no_overwrite` | pass |
| Register rules (roles, placeholders, version chain, revocation, edits) | `test_register_rules` | pass |
| Unverifiable signature claims refused | `test_signature_claims_still_refused` | pass |
| Future-dated approvals refused; unknown scope never verifies | `test_unknown_scope_and_future_dated_approval_are_refused` *(new)* | pass |
| `POLICY` matches the DRAFT policy table | `test_policy_table_matches_the_draft_policy` *(new)* | pass |
| Full flow (bootstrap → Amendment 03 → patch set → execution → 01c → clinical governance) | `test_valid_flow_with_countersignatures` | pass |

* **Commands:** `pytest tests/test_cv5_approval_tooling_patch.py tests/test_cv5_approval_tooling_review_extra.py` gives **13 passed**
  (9 original and 4 supplementary).
* **Full suite:** before the supplement, 553 passed.

## 4. Known limitations (for the reviewer's judgement)
1. **Identity is self-asserted (S0).** The register limits who *may* approve; it cannot prove who *did*. Approvers are matched by exact
   name and role. S1 (institutional e-signature) and S2 (cryptographic) are not implemented, and any signature claim is refused.
2. **Predecessor check is shallow.** "Required predecessor" means a logged, non-revoked approval of that scope. The predecessor's own
   countersignature is not re-verified.
3. **`POLICY` mirrors the DRAFT policy.** If the owner amends the policy, the patch must be regenerated and reviewed again.
4. **Observation R1 (new).** `make_approval_record` (live code, unchanged by the patch) does not validate the scope at creation.
   A record with an unknown scope can be written but never verifies (`unknown approval scope`). This is low severity. The reviewer may
   ask for validation at creation in a follow-up patch.
5. **Files can still be deleted outside the tooling.** Deletion or replacement of a record file is detected at verification, because
   the log holds the record hash. Deletion of the log itself is not detectable without an external copy, so keep a backup or an
   institutional copy.
6. **Clock trust.** `approved_at` is supplied by the approver. Ordering is checked against the log, not against a trusted
   time-stamping service.

## 5. Application and rollback procedure (for use only after approval)
1. **Precondition:** the IR's review verdict and the PO's approval (scope to be decided: this patch predates the register, so its
   approval is part of the bootstrap) are recorded against patch SHA-256 `de92744b…`.
2. **Back up:**
   - copy `kaggle/cv5_approvals.py` to a backup outside the repository;
   - verify the backup's SHA-256 is `19d83c42…`.
3. **Apply:** `git -c core.autocrlf=false apply patches/cv5_approvals_policy_tooling.patch`.
4. **Post-checks:**
   - the new file hash equals the after-hash recorded by the reviewer (computed in the dry run on a temporary copy);
   - the full test suite passes;
   - `verify_approval` behaves as before on existing fixtures.
5. **Rollback:**
   - restore the backup and confirm SHA-256 `19d83c42…`, or run `git -c core.autocrlf=false apply -R …`;
   - re-run the tests;
   - no other file is affected.
6. **Do not commit** unless separately requested.

## 6. Reviewer checklist
- [ ] Patch hash equals the value in §8, and the target before-hash equals `19d83c42…`.
- [ ] The diff contains only `kaggle/cv5_approvals.py`.
- [ ] `POLICY` matches the policy the owner intends to adopt.
- [ ] The 13 tests pass on the reviewer's machine.
- [ ] Limitations 1–6 are acceptable, or follow-up work is requested.
- [ ] Verdict (accept / accept with changes / reject), with name, role and date, recorded by the reviewer, **not** by the assistant.

## 7. Supplementary test file
`tests/test_cv5_approval_tooling_review_extra.py`. Its SHA-256 is in §8.

## 8. Exact patch content and hashes (appended verbatim by the generator)

| Item | SHA-256 |
|---|---|
| `patches/cv5_approvals_policy_tooling.patch` | `de92744b50c2d7f0c02add2f483bfdff5d2f514543bfcb9ba19cad1d0b0b6088` |
| `kaggle/cv5_approvals.py` before (live, unchanged) | `19d83c4251029ab937494f0c91a09e462611906452fa740cec75b435dd66d340` |
| `kaggle/cv5_approvals.py` after (dry run on a temporary copy) | `0221036c2ee640b84eb6cff53d0eea25bb53e103e2fe11c89bb1b624b5c21194` |
| `tests/test_cv5_approval_tooling_patch.py` | `ffa0693f367207c6f9e9d5f26f27426acfd67b764a1c13038ea073696a2871fc` |
| `tests/test_cv5_approval_tooling_review_extra.py` | `f12d1fbe4e08f9bceaba8eed28e3a3c35347cd4147ab694be44423b1faf08dd3` |
| `reports/cv5_approval_policy_DRAFT.md` | `1bd2a0cda953f52a70b9c61e27b31f307a2a69a1ce6f05f5a3ed2993d5e67e51` |

```diff
diff --git a/kaggle/cv5_approvals.py b/kaggle/cv5_approvals.py
index d8c22c1..e025ced 100644
--- a/kaggle/cv5_approvals.py
+++ b/kaggle/cv5_approvals.py
@@ -23,7 +23,10 @@ APPROVAL_FORMAT = "dentamind-human-approval-v1"
 SEAL_FORMAT = "dentamind-sealed-metrics-v1"
 SCOPES = ("amendment_01_registration", "amendment_01b_freeze", "amendment_02_registration", "amendment_03_decisions",
           "base_p2_registration", "import_wiring_patch_application", "reviewer_authorization_issue", "base_p2_metrics_release",
-          "base_p2_failure_resolution")
+          "base_p2_failure_resolution",
+          # added by the approval-tooling patch (DRAFT policy reports/cv5_approval_policy_DRAFT.md)
+          "approval_policy_adoption", "approver_register_issue", "patch_set_application", "amendment_01c_freeze",
+          "clinical_governance_decision")
 MIN_STATEMENT = 20
 SEALED_RESULTS = ("cv5_results.json", "oof_predictions.csv", "caries_confusion_findings.csv")   # + runs/*__heldout_pred.npz
 
@@ -183,3 +186,223 @@ def check_failure_resolution(failed_run_status_path, approval) -> dict:
     except ApprovalError as e:
         raise BaseP2NotReady(f"failure resolution not approved: {e}") from e
     return {"failed_run_status_sha256": _sha_file(p), "resolution": a}
+
+
+# ------------------------------------------------------------------------------------------------------------- policy v2 (G1-G7)
+# Enforcement of the DRAFT approval policy reports/cv5_approval_policy_DRAFT.md. Opt-in: verify_approval() above is unchanged; the
+# functions below add the approver register (who may approve which scope), the append-only hash-chained approval log, chronological
+# ordering and countersignatures. Records stay signature level S0 (no cryptographic signature is claimed or verified).
+ROLES = ("project_owner", "test_set_authorizer", "clinical_lead", "independent_reviewer", "institution")
+REGISTER_FORMAT = "dentamind-approver-register-v1"
+LOG_FORMAT = "dentamind-approval-log-v1"
+LOG_EVENTS = ("artifact_registered", "approval_recorded", "approval_revoked", "execution_started", "execution_completed")
+BOOTSTRAP_SCOPES = ("approval_policy_adoption", "approver_register_issue")
+# scope -> approving roles, countersigning roles (a different person), scopes that must already be approved earlier in the log,
+# accepted signature levels (S0 only until the institution adopts S1 / S2 and a verifier exists)
+POLICY = {
+    "approval_policy_adoption": {"approve": ("project_owner",), "countersign": (), "requires": ()},
+    "approver_register_issue": {"approve": ("project_owner",), "countersign": (), "requires": ("approval_policy_adoption",)},
+    "amendment_01_registration": {"approve": ("project_owner",), "countersign": (), "requires": ("approver_register_issue",)},
+    "amendment_01b_freeze": {"approve": ("project_owner",), "countersign": (), "requires": ("approver_register_issue",)},
+    "amendment_03_decisions": {"approve": ("project_owner",), "countersign": ("clinical_lead",), "requires": ("approver_register_issue",)},
+    "patch_set_application": {"approve": ("project_owner",), "countersign": ("independent_reviewer",),
+                              "requires": ("amendment_03_decisions",)},
+    "amendment_01c_freeze": {"approve": ("project_owner",), "countersign": ("independent_reviewer",),
+                             "requires": ("patch_set_application",), "needs_execution_completed": True},
+    "clinical_governance_decision": {"approve": ("clinical_lead",), "countersign": ("project_owner",),
+                                     "requires": ("approver_register_issue",)},
+    "reviewer_authorization_issue": {"approve": ("clinical_lead",), "countersign": ("project_owner",),
+                                     "requires": ("clinical_governance_decision",)},
+    "amendment_02_registration": {"approve": ("project_owner",), "countersign": ("clinical_lead",),
+                                  "requires": ("amendment_01_registration", "reviewer_authorization_issue")},
+    "base_p2_registration": {"approve": ("project_owner",), "countersign": (), "requires": ("amendment_02_registration",)},
+    "base_p2_metrics_release": {"approve": ("project_owner",), "countersign": (), "requires": ("base_p2_registration",)},
+    "base_p2_failure_resolution": {"approve": ("project_owner",), "countersign": (), "requires": ("base_p2_registration",)},
+    "import_wiring_patch_application": {"approve": (), "countersign": (), "requires": ()},       # superseded: never approvable
+}
+SIGNATURE_LEVELS = {"none": "S0"}
+ACCEPTED_LEVELS = ("S0",)
+
+
+def write_approval_record(rec: dict, path) -> str:
+    """Writes an approval record once (never overwrites). Returns its SHA-256. For the APPROVER's own use."""
+    p = Path(path)
+    with open(p, "x", encoding="utf-8") as fh:
+        json.dump(rec, fh, indent=1)
+    return _sha_file(p)
+
+
+# ---- approver register
+def register_content_sha256(reg: dict) -> str:
+    return hashlib.sha256(_canonical({k: reg.get(k) for k in ("format", "version", "issued_at", "previous_version_sha256",
+                                                              "approvers")})).hexdigest()
+
+
+def validate_register(reg: dict) -> dict:
+    if reg.get("format") != REGISTER_FORMAT:
+        raise ApprovalError(f"not a {REGISTER_FORMAT} register")
+    if reg.get("content_sha256") != register_content_sha256(reg):
+        raise ApprovalError("approver register was edited after it was issued")
+    probs = []
+    if not isinstance(reg.get("version"), int) or reg["version"] < 1:
+        probs.append("version must be an integer >= 1")
+    elif reg["version"] > 1 and not str(reg.get("previous_version_sha256") or "").strip():
+        probs.append("a version > 1 must reference the previous version")
+    if _utc(reg.get("issued_at")) is None:
+        probs.append("issued_at is not a timezone-aware ISO time")
+    names = set()
+    for a in reg.get("approvers") or []:
+        n = str(a.get("name") or "").strip()
+        if not n or "<" in n or n in names:
+            probs.append(f"approver name missing, placeholder or duplicated: {n!r}")
+        names.add(n)
+        if not a.get("roles") or set(a["roles"]) - set(ROLES):
+            probs.append(f"{n}: roles must be a non-empty subset of {ROLES}")
+        if _utc(a.get("valid_from")) is None:
+            probs.append(f"{n}: valid_from missing")
+        if a.get("status") not in ("active", "revoked") or (a.get("status") == "revoked" and _utc(a.get("revoked_on")) is None):
+            probs.append(f"{n}: status must be active, or revoked with revoked_on")
+    if not names:
+        probs.append("register lists no approver")
+    if probs:
+        raise ApprovalError("approver register invalid: " + "; ".join(probs))
+    return {"version": reg["version"], "approvers": len(names)}
+
+
+def load_register(path, expected_sha256) -> dict:
+    p = Path(path)
+    if not p.is_file() or _sha_file(p) != expected_sha256:
+        raise ApprovalError("approver register missing or not the registered version (stale or modified)")
+    reg = json.loads(p.read_text(encoding="utf-8"))
+    validate_register(reg)
+    reg["_file_sha256"] = expected_sha256
+    return reg
+
+
+def _register_entry(reg: dict, name: str, role: str, at: datetime):
+    for a in reg["approvers"]:
+        if a["name"] == name and role in a["roles"]:
+            lo, hi = _utc(a["valid_from"]), _utc(a.get("valid_to")) if a.get("valid_to") else None
+            if a["status"] == "revoked" and _utc(a["revoked_on"]) <= at:
+                return None, f"{name} was revoked on {a['revoked_on']}"
+            if at < lo or (hi is not None and at > hi):
+                return None, f"{name} was not authorized at {at.isoformat()}"
+            return a, None
+    return None, f"{name!r} holds no role {role!r} in the register"
+
+
+# ---- append-only, hash-chained approval log
+def _entry_hash(e: dict) -> str:
+    return hashlib.sha256(_canonical({k: v for k, v in e.items() if k != "entry_hash"})).hexdigest()
+
+
+def read_log(path) -> list:
+    """All entries; raises if the chain, the hashes or the chronological order is broken."""
+    p = Path(path)
+    if not p.is_file():
+        return []
+    out, prev, last = [], "0" * 64, None
+    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
+        if not line.strip():
+            continue
+        e = json.loads(line)
+        if e.get("format") != LOG_FORMAT or e.get("prev_hash") != prev or e.get("entry_hash") != _entry_hash(e):
+            raise ApprovalError(f"approval log broken at line {i + 1} (edited, reordered or truncated)")
+        t = _utc(e.get("at"))
+        if t is None or (last is not None and t < last):
+            raise ApprovalError(f"approval log line {i + 1} is out of chronological order")
+        prev, last = e["entry_hash"], t
+        out.append(e)
+    return out
+
+
+def append_log(log_path, event: str, at: str | None = None, **fields) -> dict:
+    """Appends one event (never rewrites earlier lines). An approval record may be logged once only."""
+    if event not in LOG_EVENTS:
+        raise ApprovalError(f"unknown log event {event!r}")
+    entries = read_log(log_path)
+    if event == "approval_recorded" and any(e.get("record_sha256") == fields.get("record_sha256") for e in entries
+                                            if e["event"] == "approval_recorded"):
+        raise ApprovalError("this approval record is already in the log")
+    e = {"format": LOG_FORMAT, "event": event, "at": at or datetime.now(timezone.utc).isoformat(), **fields,
+         "prev_hash": entries[-1]["entry_hash"] if entries else "0" * 64}
+    if entries and _utc(e["at"]) < _utc(entries[-1]["at"]):
+        raise ApprovalError("a log entry may not be dated before the previous entry")
+    e["entry_hash"] = _entry_hash(e)
+    with open(log_path, "a", encoding="utf-8") as fh:
+        fh.write(json.dumps(e, sort_keys=True) + "\n")
+    return e
+
+
+def _valid_approvals(entries: list, scope: str, upto: int) -> list:
+    revoked = {e.get("record_sha256") for e in entries[:upto] if e["event"] == "approval_revoked"}
+    return [e for e in entries[:upto] if e["event"] == "approval_recorded" and e.get("scope") == scope
+            and e.get("record_sha256") not in revoked]
+
+
+def verify_approval_policy(record_path, artifact_path, scope: str, register: dict, log_path, as_countersign: bool = False,
+                           now: datetime | None = None) -> dict:
+    """verify_approval() plus the policy: approver authorized for the scope in the register at approved_at; record logged once and not
+    revoked; the artifact registered in the log no later than the approval; every required predecessor scope approved earlier; no
+    work on the artifact started before its approval (no retrospective approval); amendment_01c_freeze only after the logged
+    execution evidence (no advance approval); signature level accepted."""
+    if scope not in POLICY or not (POLICY[scope]["countersign"] if as_countersign else POLICY[scope]["approve"]):
+        raise ApprovalError(f"scope {scope!r} cannot be {'countersigned' if as_countersign else 'approved'} under the policy")
+    base = verify_approval(record_path, artifact_path, scope, now=now)
+    rec = json.loads(Path(record_path).read_text(encoding="utf-8"))
+    level = SIGNATURE_LEVELS.get((rec.get("signature") or {}).get("type"))
+    if level not in ACCEPTED_LEVELS:
+        raise ApprovalError(f"signature level {level} is not accepted for {scope}")
+    at = _utc(rec["approved_at"])
+    role = rec["approver"]["role"]
+    allowed = POLICY[scope]["countersign"] if as_countersign else POLICY[scope]["approve"]
+    if role not in allowed:
+        raise ApprovalError(f"role {role!r} may not {'countersign' if as_countersign else 'approve'} {scope} (allowed: {allowed})")
+    entry, why = _register_entry(register, rec["approver"]["name"], role, at)
+    if entry is None:
+        raise ApprovalError(f"approver not authorized: {why}")
+    entries = read_log(log_path)
+    rsha = _sha_file(record_path)
+    idx = next((i for i, e in enumerate(entries) if e["event"] == "approval_recorded" and e.get("record_sha256") == rsha), None)
+    if idx is None:
+        raise ApprovalError("approval record is not in the approval log")
+    if any(e["event"] == "approval_revoked" and e.get("record_sha256") == rsha for e in entries):
+        raise ApprovalError("approval record was revoked in the log")
+    if entries[idx].get("scope") != scope or entries[idx].get("artifact_sha256") != base["artifact_sha256"]:
+        raise ApprovalError("log entry does not match the record's scope / artifact")
+    reg_i = next((i for i, e in enumerate(entries[:idx]) if e["event"] == "artifact_registered"
+                  and e.get("artifact_sha256") == base["artifact_sha256"]), None)
+    if reg_i is None or _utc(entries[reg_i]["at"]) > at:
+        raise ApprovalError("artifact was not registered in the log before the approval time (approval before the artifact existed)")
+    if _utc(entries[idx]["at"]) < at:
+        raise ApprovalError("record logged before its own approval time")
+    started = [e for e in entries[:idx] if e["event"] == "execution_started" and e.get("artifact_sha256") == base["artifact_sha256"]]
+    if started and not as_countersign:
+        raise ApprovalError("work on this artifact started before it was approved (retrospective approval)")
+    for req in POLICY[scope]["requires"]:
+        if not _valid_approvals(entries, req, idx):
+            raise ApprovalError(f"required earlier approval {req!r} is missing from the log")
+    if POLICY[scope].get("needs_execution_completed"):
+        done = [e for e in entries[:idx] if e["event"] == "execution_completed" and _utc(e["at"]) <= at]
+        if not done:
+            raise ApprovalError("no logged execution evidence precedes this approval (advance approval)")
+    return {**base, "policy_role": role, "countersign": as_countersign, "log_index": idx, "signature_level": level}
+
+
+def approval_complete(scope: str, artifact_path, register: dict, log_path, records: list, now=None) -> dict:
+    """Complete = one valid approval by an approving role plus, where the policy requires it, one valid countersignature by a
+    DIFFERENT person in a countersigning role."""
+    approvers, counters = [], []
+    for r in records:
+        rec = json.loads(Path(r).read_text(encoding="utf-8"))
+        cs = rec.get("approver", {}).get("role") in POLICY.get(scope, {}).get("countersign", ()) and \
+            rec.get("approver", {}).get("role") not in POLICY.get(scope, {}).get("approve", ())
+        v = verify_approval_policy(r, artifact_path, scope, register, log_path, as_countersign=cs, now=now)
+        (counters if cs else approvers).append(v)
+    if not approvers:
+        raise ApprovalError(f"{scope}: no valid approval")
+    if POLICY[scope]["countersign"]:
+        if not [c for c in counters if c["approver"] not in {a["approver"] for a in approvers}]:
+            raise ApprovalError(f"{scope}: countersignature by a different person in {POLICY[scope]['countersign']} required")
+    return {"scope": scope, "complete": True, "approvers": [a["approver"] for a in approvers],
+            "countersigned_by": [c["approver"] for c in counters]}
```
