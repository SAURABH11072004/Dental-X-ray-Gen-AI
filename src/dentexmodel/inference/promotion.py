"""Evidence-backed manual model promotion, an append-only approval record, and rollback.

Enforced here: a checkpoint is promoted only with (1) a validation-split evaluation report for that checkpoint - training-time
metrics and calibration-split results are shown but are never sufficient; for a non-legacy checkpoint the report must name the
exact file SHA-256; (2) an intact provenance record (legacy checkpoints are allowed but labelled); (3) a named approver, an
explicit confirmation and a written justification. Every promotion and rollback stores who, when, the previously active model
and a snapshot of the evidence. A test-split result is never required and never a basis: it is shown as context only.
"""
from __future__ import annotations

import json
import re

from dentexmodel.errors import DentaMindError, ModelUnavailableError
from dentexmodel.storage import jdump, jload, new_id, now

SCHEMA = """CREATE TABLE IF NOT EXISTS model_promotions(id TEXT PRIMARY KEY, task TEXT, action TEXT, model_id TEXT, version TEXT,
  checkpoint_sha256 TEXT, previous_model_id TEXT, approved_by TEXT, justification TEXT, evidence_json TEXT, created TEXT);"""
_NAME = re.compile(r"^[^\x00-\x1f]{2,64}$")
MIN_JUSTIFICATION = 20
LIMITATIONS = [
    "Patient-level separation is not proven: DENTEX provides no patient ids; only identical images are kept in one split.",
    "Validation metrics also chose the training epoch, so they are optimistic for that checkpoint.",
    "Research software: no promoted model is clinically validated.",
]


def _db_init(db):
    with db.conn() as c:
        c.executescript(SCHEMA)


def _load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except (OSError, json.JSONDecodeError):
        return None


def evidence(settings, info) -> dict:
    """Everything a person should see before promoting ``info`` (a registry ModelInfo), plus blockers that refuse promotion."""
    from dentexmodel.evaluation.test_ledger import file_sha256, status as test_status
    from dentexmodel.training import provenance as P
    rep = settings.data_root / "reports"
    prov = P.level(info.path, info.metadata)
    sha = file_sha256(info.path)
    blockers, warnings = [], []
    if not info.dental_specific:
        blockers.append(f"not a verified dental checkpoint ({info.provenance})")
    val = _load(rep / f"eval_{info.version}_val.json")
    val_ev = None
    if val is None:
        blockers.append("no validation-split evaluation report for this checkpoint; training-time metrics and calibration results are not sufficient")
    else:
        recorded = val.get("checkpoint_sha256")
        tied = "file sha256" if recorded == sha else ("model id/version only (report predates checkpoint hashing)" if recorded is None else "MISMATCH")
        val_ev = {"report": f"eval_{info.version}_val", "generated": val.get("generated"), "n_images": val.get("n_images"),
                  "metrics": val.get("metrics"), "tied_to_checkpoint_by": tied}
        if recorded is not None and recorded != sha:
            blockers.append("the validation report was produced for a different file (sha256 mismatch); re-evaluate this checkpoint")
        elif recorded is None and not prov["legacy"]:
            blockers.append("the validation report does not record the checkpoint sha256; re-run scripts/evaluate_model.py for this checkpoint")
        elif recorded is None:
            warnings.append("validation report predates checkpoint hashing; it is tied to this checkpoint by model id and version only")
        if val.get("model_id") not in (None, info.model_id):
            blockers.append("the validation report names a different model id")
    if prov["level"] == P.BROKEN:
        blockers.append(prov["detail"])
    elif prov["legacy"]:
        warnings.append(prov["detail"])
    cal = _load(rep / f"eval_{info.version}_calibration.json")
    ts = test_status(settings)
    mine = [e for e in ts["entries"] if e.get("checkpoint_sha256") == sha or (e.get("version") == info.version and e.get("historical"))]
    if ts["previously_used"]:
        warnings.append("the internal test split has already been used; any test number shown is context, not an untouched estimate")
    return {"model_id": info.model_id, "version": info.version, "task": info.task, "checkpoint_sha256": sha, "provenance": prov,
            "validation": val_ev,
            "calibration": ({"report": f"eval_{info.version}_calibration", "metrics": cal.get("metrics"),
                             "note": "shown for information; never a basis for promotion"} if cal else None),
            "training_metrics": {"metrics": info.metadata.get("metrics"), "measured_on": info.metadata.get("measured_on"),
                                 "note": "recorded during training on the split that also chose the epoch; not a basis for promotion"},
            "test_history": [{"kind": e.get("kind"), "evaluated_at": e.get("evaluated_at"), "historical": e.get("historical"),
                              "report": e.get("report")} for e in mine],
            "blockers": blockers, "warnings": warnings, "limitations": LIMITATIONS, "promotable": not blockers}


def _find(settings, model_id):
    from dentexmodel.inference.registry import scan_checkpoints
    return next((m for m in scan_checkpoints(settings) if m.model_id == str(model_id).replace("\\", "/")), None)


def _current(settings, task) -> str | None:
    from dentexmodel.inference.registry import active_model
    try:
        return active_model(settings, task).model_id
    except ModelUnavailableError:
        return None


def history(db, task: str | None = None, limit: int = 100) -> list:
    _db_init(db)
    rows = db.list("model_promotions", where="task=?" if task else "", params=(task,) if task else (), limit=limit)
    return [{**{k: v for k, v in r.items() if k != "evidence_json"}, "evidence": jload(r["evidence_json"])} for r in rows]


def promote(settings, db, task: str, model_id: str, approved_by: str, justification: str, confirm: bool) -> dict:
    from dentexmodel.inference.registry import set_active
    if not confirm or not _NAME.match((approved_by or "").strip()):
        raise DentaMindError("Promotion requires explicit approval: provide approved_by and confirm=true.", code="approval_required")
    if len((justification or "").strip()) < MIN_JUSTIFICATION:
        raise DentaMindError(f"A written justification of at least {MIN_JUSTIFICATION} characters is required.", code="justification_required",
                             hint="Say which validation evidence supports this model and what limitations you accept.")
    info = _find(settings, model_id)
    if info is None or info.task != task:
        raise ModelUnavailableError(f"'{model_id}' is not a {task} checkpoint in the registry.", code="checkpoint_missing")
    ev = evidence(settings, info)
    if ev["blockers"]:
        raise DentaMindError("Promotion refused: " + "; ".join(ev["blockers"]), code="promotion_evidence_missing",
                             hint="Run scripts/evaluate_model.py on the validation split for this checkpoint, then promote.")
    _db_init(db)
    previous = _current(settings, task)
    set_active(settings, task, info.model_id)
    rec = {"id": new_id("promo"), "task": task, "action": "promote", "model_id": info.model_id, "version": info.version,
           "checkpoint_sha256": ev["checkpoint_sha256"], "previous_model_id": previous, "approved_by": approved_by.strip(),
           "justification": justification.strip(), "evidence_json": jdump(ev), "created": now()}
    db.insert("model_promotions", rec)
    db.insert("model_state", {"path": info.model_id, "eval_status": f"validation report {ev['validation']['report']}", "promoted": 1,
                              "approved_by": approved_by.strip(), "updated": now()})
    return {**{k: v for k, v in rec.items() if k != "evidence_json"}, "evidence": ev}


def rollback(settings, db, task: str, approved_by: str, reason: str) -> dict:
    """Re-activate the model that was active before the current one, as recorded by the last promotion/rollback."""
    from dentexmodel.inference.registry import set_active
    if not _NAME.match((approved_by or "").strip()) or len((reason or "").strip()) < 5:
        raise DentaMindError("Rollback needs a named person and a short reason.", code="approval_required")
    _db_init(db)
    current = _current(settings, task)
    last = next((r for r in db.list("model_promotions", where="task=?", params=(task,), limit=500) if r["model_id"] == current), None)
    if last is None or not last["previous_model_id"]:
        raise DentaMindError(f"No recorded previous {task} model to roll back to.", code="nothing_to_roll_back",
                             hint="Only a change made through Promote records the model it replaced.")
    target = _find(settings, last["previous_model_id"])
    if target is None or not target.dental_specific:
        raise ModelUnavailableError(f"The previous model '{last['previous_model_id']}' is no longer a valid checkpoint.", code="checkpoint_missing")
    set_active(settings, task, target.model_id)
    rec = {"id": new_id("promo"), "task": task, "action": "rollback", "model_id": target.model_id, "version": target.version,
           "checkpoint_sha256": None, "previous_model_id": current, "approved_by": approved_by.strip(), "justification": reason.strip(),
           "evidence_json": jdump({"rolled_back_from": current, "restores_record": last["id"]}), "created": now()}
    db.insert("model_promotions", rec)
    return {k: v for k, v in rec.items() if k != "evidence_json"}


def assert_selectable(settings, db, info) -> None:
    """'Use' (switch without a new approval) is allowed for legacy checkpoints and for models that were promoted before;
    a new checkpoint must go through promote()."""
    from dentexmodel.training import provenance as P
    if P.level(info.path, info.metadata)["legacy"]:
        return
    _db_init(db)
    if not db.count("model_promotions", where="model_id=? AND action='promote'", params=(info.model_id,)):
        raise DentaMindError(f"'{info.version}' has never been promoted; activating it needs the promotion workflow (evidence + approval).",
                             code="promotion_required", hint="Use Promote on the Model Registry page.")
