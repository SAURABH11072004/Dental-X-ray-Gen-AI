"""Test-set use ledger and the authorization gate for final test evaluations.

What is enforced here (in code):
* every evaluation on the internal ``test`` split goes through :func:`authorize` and is appended to
  ``Data/reports/test_set_ledger.json`` with checkpoint SHA-256, time, manifest/split hashes, metrics and the named authorizer;
* a named authorizer and a written reason are required;
* a checkpoint must have a validation-split report for the *same file* (SHA-256) first - model selection happens on val;
* legacy checkpoints (no training manifest) may only *reproduce* their historical result, into a separate folder;
* the same checkpoint cannot be test-evaluated twice for the same purpose (``kind``);
* only ONE new candidate per task may be evaluated on a given test-split version beyond the historical results - repeated
  candidate comparisons on the same test images are refused;
* entries are hash-chained, so editing or deleting a past entry is detectable by :func:`verify_chain`.

What is NOT enforced: anyone with write access to the files or the source code can edit the ledger, delete it, or call the
metric code directly. The ledger makes test use visible and auditable; it cannot make the test images secret.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from dentexmodel.errors import DentaMindError

FORMAT = "dentamind-test-ledger-v1"
KINDS = ("final_metrics", "uncertainty", "reproduction")
_NAME = re.compile(r"^[^\x00-\x1f]{2,64}$")
MIN_REASON = 20


def ledger_path(settings) -> Path:
    return settings.data_root / "reports" / "test_set_ledger.json"


_SHA_CACHE: dict = {}


def file_sha256(path) -> str:
    """Full SHA-256 of a file, cached per (path, size, mtime) so status pages do not re-hash large checkpoints."""
    st = Path(path).stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _SHA_CACHE:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        _SHA_CACHE[key] = h.hexdigest()
    return _SHA_CACHE[key]


def _entry_hash(e: dict) -> str:
    body = {k: v for k, v in e.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def split_version(settings) -> dict:
    """Identity of the current internal test split: assignment hash (timestamp-free) plus manifest hash."""
    from dentexmodel.training.trainers import assignments_sha
    mp = settings.processed_dir / "manifest.json"
    return {"assignments_sha": assignments_sha(settings.splits_dir / "dentex_splits.json"),
            "manifest_sha256": file_sha256(mp) if mp.is_file() else None}


# ------------------------------------------------------------------------------------------------ historical (pre-ledger) results
def historical_entries(settings) -> list:
    """Test evaluations that happened before the ledger existed, derived from the report files they wrote. Read-only."""
    from dentexmodel.inference.registry import scan_checkpoints
    rep = settings.data_root / "reports"
    models = {m.version: m for m in scan_checkpoints(settings)}
    out = []
    for p in sorted(rep.glob("eval_*_test.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("split") != "test":
            continue
        m = models.get(d.get("model_version"))
        out.append({"kind": "final_metrics", "historical": True, "model_id": d.get("model_id"), "version": d.get("model_version"),
                    "task": d.get("task"), "evaluated_at": d.get("generated"),
                    "checkpoint_sha256_recorded_at_training": (m.metadata.get("checkpoint_sha256") if m else None),
                    "checkpoint_sha256": file_sha256(m.path) if m else None,
                    "dataset_version_at_evaluation": d.get("dataset_version"), "n_images": d.get("n_images"), "metrics": d.get("metrics"),
                    "report": p.name, "authorized_by": None,
                    "authorization": "none recorded - evaluated before the ledger existed (--final-test flag only)"})
    ue = rep / "uncertainty_evaluation.json"
    if ue.is_file():
        try:
            d = json.loads(ue.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            d = {}
        if d.get("test_split"):
            m = models.get(d.get("model_version"))
            out.append({"kind": "uncertainty", "historical": True, "model_id": m.model_id if m else None, "version": d.get("model_version"),
                        "task": "classification", "evaluated_at": d.get("generated"),
                        "checkpoint_sha256_recorded_at_training": (m.metadata.get("checkpoint_sha256") if m else None),
                        "checkpoint_sha256": file_sha256(m.path) if m else None, "n_images": None,
                        "metrics": {k: d["test_split"].get(k) for k in ("n", "accuracy", "ece", "brier", "auroc_entropy_for_errors",
                                                                         "auroc_tta_disagreement_for_errors", "ece_after_temperature_fitted_on_calibration")},
                        "report": ue.name, "authorized_by": None,
                        "authorization": "none recorded - evaluated before the ledger existed (--final-test flag only)"})
    return out


# ------------------------------------------------------------------------------------------------ ledger file
def read_ledger(settings) -> dict:
    p = ledger_path(settings)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"format": FORMAT, "entries": [], "initialised": None}


def _write(settings, led: dict) -> None:
    p = ledger_path(settings)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(led, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def _append(led: dict, entry: dict) -> dict:
    entry = {**entry, "seq": len(led["entries"]) + 1, "prev_entry_sha256": led["entries"][-1]["entry_sha256"] if led["entries"] else None}
    entry["entry_sha256"] = _entry_hash(entry)
    led["entries"].append(entry)
    return entry


def ensure_ledger(settings) -> dict:
    """Create the ledger with the historical (pre-ledger) results if it does not exist yet. Never rewrites existing entries."""
    led = read_ledger(settings)
    if led.get("initialised"):
        return led
    led["initialised"] = datetime.now(timezone.utc).isoformat()
    led["note"] = ("Append-only record of every use of the internal DENTEX test split. Historical entries were derived from report files "
                   "written before this ledger existed; their authorization was not recorded.")
    for e in historical_entries(settings):
        _append(led, e)
    _write(settings, led)
    return led


def verify_chain(led: dict) -> list:
    """Problems with the hash chain (empty = intact)."""
    problems, prev = [], None
    for i, e in enumerate(led.get("entries", []), 1):
        if e.get("seq") != i:
            problems.append(f"entry {i}: sequence number {e.get('seq')} (an entry was removed or reordered)")
        if e.get("prev_entry_sha256") != prev:
            problems.append(f"entry {i}: previous-entry hash does not match (an earlier entry was changed or removed)")
        if e.get("entry_sha256") != _entry_hash(e):
            problems.append(f"entry {i}: content does not match its hash (edited)")
        prev = e.get("entry_sha256")
    return problems


# ------------------------------------------------------------------------------------------------ status + gate
def status(settings) -> dict:
    """Display summary: is the internal test split already used, by which checkpoints, and is the ledger intact."""
    led = read_ledger(settings)
    entries = led["entries"] if led.get("initialised") else historical_entries(settings)
    used_by = sorted({(e.get("task"), e.get("version")) for e in entries if e.get("kind") != "reproduction"}, key=str)
    return {"previously_used": bool(entries), "ledger_initialised": bool(led.get("initialised")),
            "chain_problems": verify_chain(led) if led.get("initialised") else [],
            "n_entries": len(entries), "used_by": [{"task": t, "version": v} for t, v in used_by],
            "current_split_version": split_version(settings), "entries": entries,
            "statement": ("The internal DENTEX test split has already been used for final evaluation of the checkpoints listed here. "
                          "Their test results are historical results. Any later test result on the same images is not an untouched "
                          "estimate; an unbiased estimate for a new model needs an external test set that was never used (docs/RESEARCH_INTEGRITY.md)."
                          if entries else "No recorded use of the internal test split.")}


def _val_report_for(settings, info, sha: str) -> dict | None:
    p = settings.data_root / "reports" / f"eval_{info.version}_val.json"
    if not p.is_file():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return d if d.get("checkpoint_sha256") == sha else None


def authorize(settings, info, kind: str, authorized_by: str, reason: str, out_dir: str | None = None) -> dict:
    """Raise :class:`DentaMindError` unless this test evaluation is allowed; return the context to pass to :func:`record`."""
    if kind not in KINDS:
        raise DentaMindError(f"Unknown test-evaluation kind '{kind}'.", code="invalid_kind")
    if not _NAME.match((authorized_by or "").strip()):
        raise DentaMindError("A named authorizer is required for any test-split evaluation.", code="test_authorization_required",
                             hint="Pass --authorized-by \"<name>\" and --reason \"<why this is the final evaluation>\".")
    if len((reason or "").strip()) < MIN_REASON:
        raise DentaMindError(f"A written reason of at least {MIN_REASON} characters is required.", code="test_authorization_required",
                             hint="State why model selection is finished and this checkpoint is the final candidate.")
    led = ensure_ledger(settings)
    if verify_chain(led):
        raise DentaMindError("The test-set ledger fails its integrity check; refusing to add to it.", code="ledger_tampered",
                             hint="Inspect Data/reports/test_set_ledger.json against its backup before any further test evaluation.")
    sha = file_sha256(info.path)
    legacy = not info.metadata.get("training_manifest")
    mine = [e for e in led["entries"] if e.get("checkpoint_sha256") == sha]
    sv = split_version(settings)
    if kind == "reproduction":
        if not any(e["kind"] != "reproduction" for e in mine):
            raise DentaMindError("Only a checkpoint that already has a recorded test result can be reproduced.", code="nothing_to_reproduce")
        if not out_dir:
            raise DentaMindError("A reproduction must be written to a separate folder (--out-dir), never over the historical report.", code="out_dir_required")
        return {"sha": sha, "legacy": legacy, "split_version": sv, "prior": mine}
    if legacy:
        raise DentaMindError(f"'{info.version}' is a legacy checkpoint without a training manifest; its historical test result is already recorded.",
                             code="legacy_checkpoint", hint="Use --reproduce with --out-dir to re-run the historical evaluation; it is recorded as a reproduction.")
    if any(e["kind"] == kind for e in mine):
        raise DentaMindError(f"This checkpoint (sha256 {sha[:16]}) already has a recorded '{kind}' test evaluation.", code="test_already_used",
                             hint="Read the existing report; repeated test evaluation of the same model is not allowed.")
    if _val_report_for(settings, info, sha) is None:
        raise DentaMindError("No validation-split report exists for this exact checkpoint file.", code="validation_first",
                             hint=f"Run scripts/evaluate_model.py --checkpoint {info.model_id} (validation split) first; select models on validation only.")
    others = [e for e in led["entries"] if e.get("task") == info.task and not e.get("historical") and e["kind"] == kind
              and e.get("checkpoint_sha256") != sha and (e.get("split_version") or {}).get("assignments_sha") == sv["assignments_sha"]]
    if others:
        raise DentaMindError(f"A different {info.task} candidate ({others[0].get('version')}) was already evaluated on this test split. "
                             "Comparing several candidates on the same test images turns the test set into a selection set.",
                             code="test_candidate_limit", hint="Evaluate further candidates on validation, and use an external untouched test set (docs/RESEARCH_INTEGRITY.md).")
    prior = [e for e in led["entries"] if e.get("task") == info.task and e["kind"] != "reproduction"]
    return {"sha": sha, "legacy": False, "split_version": sv, "prior": prior}


def record(settings, info, kind: str, ctx: dict, authorized_by: str, reason: str, metrics: dict, n_images, report: str, script: str) -> dict:
    led = ensure_ledger(settings)
    prior = ctx.get("prior") or []
    entry = {"kind": kind, "historical": False, "model_id": info.model_id, "version": info.version, "task": info.task,
             "evaluated_at": datetime.now(timezone.utc).isoformat(), "checkpoint_sha256": ctx["sha"], "split_version": ctx["split_version"],
             "n_images": n_images, "metrics": metrics, "report": report, "script": script,
             "authorized_by": authorized_by.strip(), "reason": reason.strip(),
             "test_set_previously_used": bool(prior), "prior_uses_for_task": [{"version": e.get("version"), "kind": e.get("kind"),
                                                                                "evaluated_at": e.get("evaluated_at")} for e in prior]}
    e = _append(led, entry)
    _write(settings, led)
    return e


def test_status_for_report(ctx: dict) -> dict:
    """Block embedded in a test report so the number is never read without its context."""
    prior = ctx.get("prior") or []
    return {"previously_used": bool(prior), "prior_uses_for_task": [{"version": e.get("version"), "kind": e.get("kind"),
                                                                     "evaluated_at": e.get("evaluated_at")} for e in prior],
            "interpretation": ("The internal test split was already used for this task; this result is not an untouched estimate."
                               if prior else "First recorded use of the internal test split for this task.")}


# ------------------------------------------------------------------------------------------------ retrospective disclosure
DISCLOSURE_KIND = "retrospective_disclosure"
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
DISCLOSURE_FIELDS = ("task", "version", "description", "evaluated_at", "checkpoint_sha256s", "split_version_at_evaluation",
                     "n_findings", "n_images", "metrics", "report", "script", "selection")


def record_retrospective_disclosure(settings, fields: dict, authorized_by: str, reason: str) -> dict:
    """Append a disclosure of a test-split use that ALREADY happened outside :func:`authorize` (e.g. an external GPU run).

    * Same authorizer / reason rules as :func:`authorize`; refuses a ledger that fails :func:`verify_chain`.
    * Every field in ``DISCLOSURE_FIELDS`` must be supplied (nothing is filled in or guessed); checkpoint hashes must be full SHA-256.
    * Kind ``retrospective_disclosure`` is NOT ``final_metrics``: it does not occupy the one-candidate-per-task slot of the gate, but it
      is listed among prior uses, so every later test report states that the split was used again.
    * The same set of checkpoints cannot be disclosed twice.
    """
    if not _NAME.match((authorized_by or "").strip()):
        raise DentaMindError("A named authorizer is required for a test-split disclosure.", code="test_authorization_required")
    if len((reason or "").strip()) < MIN_REASON:
        raise DentaMindError(f"A written reason of at least {MIN_REASON} characters is required.", code="test_authorization_required")
    missing = [k for k in DISCLOSURE_FIELDS if fields.get(k) in (None, "", [], {})]
    if missing:
        raise DentaMindError(f"Disclosure fields missing: {', '.join(missing)}", code="disclosure_incomplete")
    shas = sorted(str(s).lower() for s in fields["checkpoint_sha256s"])
    if not all(_SHA64.match(s) for s in shas):
        raise DentaMindError("checkpoint_sha256s must be full 64-character SHA-256 hashes.", code="disclosure_incomplete")
    led = ensure_ledger(settings)
    if verify_chain(led):
        raise DentaMindError("The test-set ledger fails its integrity check; refusing to add to it.", code="ledger_tampered")
    if any(e.get("kind") == DISCLOSURE_KIND and sorted(e.get("checkpoint_sha256s") or []) == shas for e in led["entries"]):
        raise DentaMindError("These checkpoints are already disclosed in the ledger.", code="already_recorded")
    prior = [e for e in led["entries"] if e.get("task") == fields["task"] and e.get("kind") != "reproduction"]
    entry = {"kind": DISCLOSURE_KIND, "historical": False, "retrospective": True, "model_id": None,
             **{k: fields[k] for k in DISCLOSURE_FIELDS if k != "checkpoint_sha256s"}, "checkpoint_sha256s": shas,
             "checkpoint_sha256": None, "recorded_at": datetime.now(timezone.utc).isoformat(),
             "split_version_at_record": split_version(settings),
             "authorized_by": authorized_by.strip(), "reason": reason.strip(),
             "authorization": "recorded retrospectively; this evaluation did not pass through authorize()",
             "test_set_previously_used": bool(prior),
             "prior_uses_for_task": [{"version": e.get("version"), "kind": e.get("kind"), "evaluated_at": e.get("evaluated_at")} for e in prior]}
    e = _append(led, entry)
    _write(settings, led)
    return e
