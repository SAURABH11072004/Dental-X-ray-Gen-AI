from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Query
from fastapi.responses import Response

from backend.schemas.models import EvaluateRequest, ModelSelectRequest, RollbackRequest
from backend.services.container import get_services
from dentexmodel.errors import ConflictError, DentaMindError
from dentexmodel.inference.registry import scan_checkpoints, set_active
from dentexmodel.storage import now

router = APIRouter(prefix="/api", tags=["experiments", "models"])


@router.get("/experiments")
def experiments():
    return get_services().experiments.list()


@router.get("/experiments/compare")
def compare(ids: str = Query(..., min_length=1)):
    return get_services().experiments.compare([i for i in ids.split(",") if i])


@router.get("/experiments/series")
def series():
    return get_services().experiments.series()


@router.get("/experiments/export")
def export(format: str = Query("json", pattern="^(json|csv)$")):
    rows = get_services().experiments.list()
    if format == "json":
        return Response(json.dumps(rows, indent=1), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="experiments.json"'})
    buf = io.StringIO()
    cols = ["id", "strategy", "dataset_version", "model_version", "budget", "round", "seed", "duration_s", "status", "is_test_data"]
    mcols = ["detection_map", "detection_ap50", "classification_macro_f1", "mask_ap", "calibration_ece"]
    w = csv.writer(buf)
    w.writerow(cols + mcols)
    for r in rows:
        w.writerow([r[c] for c in cols] + [r["metrics"].get(m) for m in mcols])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="experiments.csv"'})


@router.get("/models")
def models():
    sv = get_services()
    state = {r["path"]: r for r in sv.ctx.db.list("model_state", order="updated DESC")}
    from dentexmodel.errors import ModelUnavailableError
    from dentexmodel.inference.registry import TASKS, active_model
    active = {}
    for t in TASKS:                     # the model inference actually uses: env var > active_models.json > configs/models.yaml
        try:
            active[t] = active_model(sv.ctx.settings, t).model_id
        except ModelUnavailableError:
            pass
    out = []
    for m in scan_checkpoints(sv.ctx.settings):
        d = m.to_dict()
        st = state.get(m.model_id)
        d["promoted"] = bool(st["promoted"]) if st else False
        d["eval_status"] = st["eval_status"] if st else "not evaluated"
        done = sorted(q.stem.rsplit("_", 1)[1] for q in _reports_dir().glob(f"eval_{m.version}_*.json"))
        if done and d["eval_status"] == "not evaluated":
            d["eval_status"] = "evaluated on " + ", ".join(done)       # a real report file exists under Data/reports
        d["evaluation_reports"] = [f"eval_{m.version}_{x}" for x in done]
        d["active_for"] = [t for t, mid in active.items() if mid == m.model_id]
        from dentexmodel.training.provenance import level as prov_level
        d["provenance_level"] = prov_level(m.path, m.metadata)
        d["test_split_used"] = "test" in done        # historical or ledger-recorded test evaluation exists for this version
        out.append(d)
    return {"items": out, "checkpoint_dir": sv.ctx.settings.checkpoint_dir.name,
            "note": "Only files present in the checkpoint directory are listed. Files without a valid metadata sidecar are not treated as dental models."}


@router.post("/models/select")
def select_model(req: ModelSelectRequest):
    """Switch the active model without a new approval: only legacy checkpoints or ones promoted before (see promotion.assert_selectable)."""
    from dentexmodel.inference import promotion
    sv = get_services()
    info = next((m for m in scan_checkpoints(sv.ctx.settings) if m.model_id == req.model_id), None)
    if info is not None:
        promotion.assert_selectable(sv.ctx.settings, sv.ctx.db, info)
    set_active(sv.ctx.settings, req.task, req.model_id)
    return {"selected": req.model_id, "task": req.task}


@router.post("/models/promote")
def promote(req: ModelSelectRequest):
    from dentexmodel.inference import promotion
    sv = get_services()
    return promotion.promote(sv.ctx.settings, sv.ctx.db, req.task, req.model_id, req.approved_by or "", req.justification or "", req.confirm)


@router.post("/models/rollback")
def rollback(req: RollbackRequest):
    from dentexmodel.inference import promotion
    sv = get_services()
    return promotion.rollback(sv.ctx.settings, sv.ctx.db, req.task, req.approved_by, req.reason)


@router.get("/models/promotions")
def promotions(task: str | None = Query(None, pattern="^(detection|segmentation|classification|numbering)$")):
    from dentexmodel.inference import promotion
    return {"items": promotion.history(get_services().ctx.db, task)}


@router.get("/models/evidence")
def model_evidence(model_id: str = Query(..., min_length=1, max_length=256)):
    """What a person must see before promoting: validation report, provenance, test history, blockers, limitations."""
    from dentexmodel.errors import NotFoundError
    from dentexmodel.inference import promotion
    sv = get_services()
    info = next((m for m in scan_checkpoints(sv.ctx.settings) if m.model_id == model_id), None)
    if info is None:
        raise NotFoundError(f"Checkpoint '{model_id}' not found.")
    return promotion.evidence(sv.ctx.settings, info)


@router.get("/integrity/test-set")
def test_set_status():
    """Recorded uses of the internal test split (ledger, or derived from historical reports until the ledger exists)."""
    from dentexmodel.evaluation.test_ledger import status
    return status(get_services().ctx.settings)


def _reports_dir():
    return get_services().ctx.settings.data_root / "reports"


@router.get("/evaluations")
def list_evaluations():
    """Evaluation reports written by scripts/evaluate_model.py (or the evaluate endpoint): measured results only."""
    import json
    out = []
    for p in sorted(_reports_dir().glob("eval_*.json"), key=lambda q: q.stat().st_mtime, reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"name": p.stem, "model_version": d.get("model_version"), "task": d.get("task"), "split": d.get("split"),
                    "n_images": d.get("n_images"), "generated": d.get("generated"), "metrics": d.get("metrics")})
    return {"items": out}


@router.get("/evaluations/{name}")
def get_evaluation(name: str, format: str = Query("json", pattern="^(json|md)$")):
    import re
    from fastapi.responses import PlainTextResponse
    from dentexmodel.errors import NotFoundError
    if not re.fullmatch(r"eval_[A-Za-z0-9._-]+", name) or ".." in name:   # a file stem only, never a path
        raise NotFoundError("Evaluation report not found.")
    p = _reports_dir() / f"{name}.{format}"
    if not p.is_file():
        raise NotFoundError("Evaluation report not found.", hint="Run scripts/evaluate_model.py for this checkpoint.")
    return PlainTextResponse(p.read_text(encoding="utf-8"), media_type="application/json" if format == "json" else "text/markdown")


@router.post("/models/{model_id:path}/evaluate")
def evaluate(model_id: str, req: EvaluateRequest | None = None):
    """Start an evaluation of one checkpoint on the validation (or calibration) split as a background job.
    The locked test split is intentionally not reachable from the API."""
    import os
    import subprocess
    import sys
    import threading
    from dentexmodel.storage import jdump, new_id
    sv = get_services()
    st = sv.ctx.dataset.status()
    if not st.main_available:
        raise DentaMindError("Main dataset is not available. Please place the dataset in " + st.expected_location, code="dataset_unavailable",
                             hint="Evaluation needs held-out labelled data (validation split).")
    info = next((m for m in scan_checkpoints(sv.ctx.settings) if m.model_id == model_id), None)
    if info is None or not info.dental_specific:
        raise DentaMindError(f"'{model_id}' is not a usable dental checkpoint ({info.provenance if info else 'not found'}).", code="unverified_checkpoint")
    req = req or EvaluateRequest()
    busy = sv.ctx.jobs.running_jobs()
    if busy:    # the 4 GB GPU holds one job at a time; a second evaluation fails with out-of-memory (observed) and could leave a partial report
        raise ConflictError(f"Another job is still running ({busy[0]['kind']} {busy[0]['id']}).", code="job_already_running",
                            hint="Wait for it to finish (GET /api/training/jobs), then start the evaluation.")
    root = sv.ctx.settings.project_root
    cmd = [sys.executable, str(root / "scripts" / "evaluate_model.py"), "--checkpoint", model_id, "--split", req.split]
    if req.max_images:
        cmd += ["--max-images", str(req.max_images)]
    job_id = new_id("job")
    sv.ctx.db.insert("jobs", {"id": job_id, "kind": "evaluate", "status": "running", "config_json": jdump({"model_id": model_id, **req.model_dump()}),
                              "created": now(), "started": now(), "pid": os.getpid()})

    def run():
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
        ok = proc.returncode == 0
        sv.ctx.db.update("jobs", "id", job_id, {"status": "succeeded" if ok else "failed", "finished": now(),
                                                "error": None if ok else (proc.stdout + proc.stderr)[-800:]})
    threading.Thread(target=run, daemon=True, name=job_id).start()
    return {"job_id": job_id, "status": "running", "report_name": f"eval_{info.version}_{req.split}",
            "note": "Poll GET /api/training/jobs; the report appears under GET /api/evaluations when finished."}
