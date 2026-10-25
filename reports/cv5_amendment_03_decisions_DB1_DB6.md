# CV5 Amendment 03: decisions D-B1 to D-B6 (DRAFT, NOT IN FORCE)

**Status: DRAFT prepared 2026-10-25. NOT IN FORCE.** It takes effect only through a human approval record of scope
`amendment_03_decisions` bound to this file's SHA-256 (see D-B2), made by the accountable project owner.

* Nothing here changes the approved protocol `reports/cv5_acceptance_protocol.md` (revision 3, `0771b5f8…`), its thresholds or its
  verdict rules.
* Each decision either fills a gap the protocol does not specify or is stricter than it (§7).
* Supporting code is implemented and tested on synthetic fixtures. It is inactive for any real run until this amendment and the
  amendments it depends on are in force.
* No real approval, reviewer, authorization, manifest, signature or disclosure exists, and none was created.

---

## D-B1: revoked reviewers

**Decision:**
* A new import manifest refuses **every** label whose reviewer is revoked in the registered reviewer-authorization version,
  whatever the review date.
* Historical records are never changed:
  - the hash-chained review log;
  - earlier authorization versions (written once);
  - earlier manifests (written once and bound to the authorization version they were built with).
* A manifest built under an earlier authorization version cannot be used once a later version is registered. It must be rebuilt.

**Implementation:**
* `cv5_imports.check_reviewer_bindings`: a status other than `active` → refused.
* `build_reviewer_authorization`: revocations carry forward to every later version; files are written once.

**Tests:** `test_reviewer_authorization.py::test_db1_revocation_rejects_new_imports_and_leaves_history_unchanged`, plus the revoked /
stale cases.

## D-B2: auditable human approval records (not digital signatures)

**Decision:** every human authorization in the CV5 programme is a `dentamind-human-approval-v1` record:
* bound to **one** artifact by SHA-256;
* the approver's own name and role;
* a timezone-aware UTC time that is not in the future;
* a scope from a fixed list;
* a written statement (≥ 20 characters);
* `signature: {"type": "none"}`.

Rules:
* A record that claims any other signature type is refused, because no signature can be verified in this project. No digital
  signature is claimed anywhere.
* The ledger's own disclosure command keeps its own authorizer and reason fields. Approval records do not replace it.

**Scopes:** `amendment_01_registration`, `amendment_01b_freeze`, `amendment_02_registration`, `amendment_03_decisions`,
`base_p2_registration`, `import_wiring_patch_application`, `reviewer_authorization_issue`, `base_p2_metrics_release`,
`base_p2_failure_resolution`.

**Implementation:**
* `kaggle/cv5_approvals.py` (`make_approval_record` for the approver, `verify_approval`).
* `make_base_p2_notebook.write_base_p2_notebook(..., approvals=, require_approvals=)` verifies records for Amendment 01, Amendment 02
  and the registration file.
* **Once this amendment is in force, `require_approvals=True` is mandatory.** The "Registered by" table row alone is then not
  sufficient.

**Tests:** `test_cv5_approvals.py` covers binding, scope, a changed artifact, an edit, missing name / role / placeholders, a short
statement, a naive or future time, and an unverifiable signature claim. `test_cv5_base_p2.py::test_writer_verifies_human_approvals_when_required`.

## D-B3: BASE-P2 metric sealing

**Decision:** BASE-P2 held-out metrics and predictions are sealed until a predefined release condition holds.
* **Sealed** (moved into `dentamind_cv5_BASEP2_SEALED_metrics.zip` and removed from the open notebook output):
  - `cv5_results.json`;
  - `oof_predictions.csv`;
  - `caries_confusion_findings.csv`;
  - every `runs/<run>__heldout_pred.npz`.

  The open output keeps only `sealed_metrics_manifest.json` (file names and SHA-256 values, no values). The pooled-metric log lines
  are replaced by a "SEALED (not logged)" notice.
* **Permitted operational logs:**
  - run status, attempts and exception origins;
  - training-loss lines;
  - the per-epoch inner-validation values printed by the unchanged BASE trainer (`dentamind_kaggle.train_run`), and the selected
    epoch's inner-validation macro-F1.

  These are inner-validation, epoch-selection quantities, not held-out results. The frozen BASE code that prints them is not modified.
* **Release condition** (`cv5_approvals.release_sealed_metrics`), all of:
  1. the sealed archive matches its manifest SHA-256;
  2. the BASE-P2 archive integrity check (SHA256SUMS) passed;
  3. gate R passed in the candidate environment (protocol §4.3). Gate R reads the stored predictions programmatically and records only
     pass / fail, mismatches and probability differences;
  4. a human approval record of scope `base_p2_metrics_release` bound to the sealed archive.
* **Access control (stated honestly):** sealing is a procedural, tamper-evident control, **not encryption**. Anyone with access to the
  private Kaggle notebook output can technically open the archive. The control relies on:
  - the archive being private;
  - the owner not opening it before the release record;
  - its SHA-256 being registered so that substitution is detectable.

  Encrypting the archive would be a separate decision.
* **Effect on the protocol:** none of §5's criteria change. The BASE-P2 vs CV5-BASE run 1 exploratory comparison (§7.1) waits for
  the release.

**Implementation:** the `make_base_p2_notebook` aggregation-cell substitution, the seal cell `8b`, and the package changes. The
registration field is `metrics_policy: "sealed"` (the only accepted value).

**Tests:** `test_cv5_base_p2.py` (no metric log lines; a seal cell that archives and removes files, with no value in the log or
manifest), and `test_cv5_approvals.py` (archive written once; release refused without integrity, gate R, or a bound approval).

## D-B4: BASE-P2 incomplete or divergent

**Decision:**
* **Comparator requirement:** BASE-P2 may serve as the comparator only if all 25 runs are classified `ok`
  (`cv5_approvals.check_base_p2_complete`). If any run ends `incomplete`, `infrastructure` (retries exhausted) or `divergence`,
  **candidate evaluation stops**. No candidate is trained against an incomplete reference.
* **Retries:** exactly those of protocol §9 as implemented in `cv5_accept.run_isolated`. Infrastructure failures retry up to 3 attempts
  in total; computation, ambiguous and manifest failures and divergence are final. No new retry behaviour is added.
* **No repair in place:** a failed BASE-P2 is never repaired, resumed into a different configuration, or partially reused.
* **Proceeding** needs a documented resolution: an approval record of scope `base_p2_failure_resolution` bound to the failed
  `run_status.json`. After that, a **new** BASE-P2 registration with `attempt = N + 1` must cite both hashes.
* **Reporting:** both attempts are reported, mirroring protocol §9's "rerun the whole candidate, and report both runs".
* **Budget:** BASE-P2 uses no budget slot, so no slot is consumed. Candidates already registered keep their reservations; they cannot
  start without a complete BASE-P2.
* **Human decision left open:** whether a second BASE-P2 failure ends the import programme.

**Tests:** `test_cv5_approvals.py` (the gate refuses every non-ok state; the resolution must be bound to a real failure) and
`test_cv5_base_p2.py::test_second_attempt_needs_a_failed_status_and_an_approved_resolution`.

## D-B5: reviewer qualifications and clinical procedure (accountable human / clinical approval required)

**Decision:** these are clinical-governance decisions. The project owner and a named clinical lead must make them. They are **not**
decided here, and no credential, clinical authorization or reviewer is invented:
* acceptable reviewer credentials;
* who the clinical lead is, and their approval of the review procedure;
* the second-reader policy (subset size, selection);
* the adjudication procedure for disagreements;
* how adjudicated outcomes enter the hash-chained review log.

**Until decided:** reviewer authorization version 1 cannot be issued (scope `reviewer_authorization_issue`), so no manifest can be
built and P2 cannot be met through imports.

**Tooling:** the tooling records only that qualification was attested (`qualification_attested`, `attested_on`). It does not judge
credentials.

## D-B6: import-wiring patch

**Decision:**
* `patches/cv5_import_wiring.patch` (`ed26e064…`) stays **unapplied** until an approval record of scope
  `import_wiring_patch_application` bound to that exact patch file exists.
* It is then applied exactly as reviewed, following `reports/cv5_patch_application_plan.md`:
  1. recompute hashes;
  2. build a new candidate bundle version without overwriting v1;
  3. run the full test suite and the Kaggle no-training pre-flight;
  4. verify that the imports-off output is byte-identical to the current output.

---

## 7. Conflict check against the approved protocol (revision 3)

| Decision | Protocol reference | Finding |
|---|---|---|
| D-B1 | §3.1 (imports; V6) | not specified there; a stricter eligibility rule; no conflict |
| D-B2 | §4.5 / §13 (dated amendments, owner decisions) | the protocol has no signature mechanism; approval records add auditability; no conflict. The ledger's own authorization is unchanged |
| D-B3 | §3.2 (sequencing "because training logs print metrics"), §4.3 (gate R), §7.1 | stricter than §3.2. Gate R and pairing still work (programmatic access); the exploratory comparison is delayed until release; no criterion changes |
| D-B4 | §4.3 (reuse only after reproduction), §9 (run classes, retries) | §9 covers candidate runs; D-B4 applies the same classes and retries to the reference and stops candidates, mirroring §4.3's "resolved by a dated amendment"; **new rule** (needs this amendment) |
| D-B5 | — | outside the protocol; human / clinical governance |
| D-B6 | Amendment 01b freeze rule | applies the existing rule (a change to a frozen file is a dated change with new hashes) |

## 8. Code state (unapplied to any real run)

| File | SHA-256 |
|---|---|
| `kaggle/cv5_approvals.py` (new) | `19d83c4251029ab937494f0c91a09e462611906452fa740cec75b435dd66d340` |
| `kaggle/make_base_p2_notebook.py` | `f540e612fd0cd150c3ebdb818d02dae37a7339aca725e2f3a973ea5d62b9e6ca` |
| `kaggle/cv5_imports.py` | `f9c061cb1aab3ecb83a46815b796c68b527c03743b4acc359c7549a10393bf64` |
| `patches/cv5_import_wiring.patch` (unapplied) | `ed26e064e86d9136f6026515937b9ba26c123bfeeb94d9b843957e749e639d5d` |
| `kaggle/make_cv5_notebook.py` (frozen, unchanged) | `4a5efda8951126644d0e91b4778e3d7c6d93e174cebc6a371f3a7001e2920641` |

**Tests:** full suite 524 passed. `test_cv5_approvals.py` 12, `test_cv5_base_p2.py` 24, `test_reviewer_authorization.py` 12,
`test_cv5_import_wiring.py` 14, `test_cv5_imports.py` 22. All synthetic; real-data validity is unverified.

## 9. Approval (to be completed only by the accountable owner, via a D-B2 record; nothing entered here)

| Field | Entry |
|---|---|
| Approval record file and its SHA-256 (scope `amendment_03_decisions`) | |
| Decisions accepted / modified (D-B1 … D-B6) | |
| Open human decisions recorded (D-B4 second failure; D-B5 items) | |
