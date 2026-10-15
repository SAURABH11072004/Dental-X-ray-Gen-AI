from __future__ import annotations

from fastapi import APIRouter, Query

from backend.schemas.models import ExportRequest, SelectRequest
from backend.services.container import get_services

router = APIRouter(prefix="/api/active-learning", tags=["active-learning"])


@router.get("/info")
def info():
    return get_services().al.info()


@router.post("/score-pool")
def score_pool(n: int = Query(30, ge=1, le=500), seed: int = 42):
    """Compute real uncertainty for n unscored pool images (background job). Needs the trained checkpoints."""
    return get_services().al.start_score_pool(n, seed)


@router.get("/score-pool/{job_id}")
def score_pool_status(job_id: str):
    return get_services().al.score_job(job_id)


@router.get("/pool")
def pool():
    sv = get_services()
    p = sv.al.pool()
    scored = set(sv.analysis.latest_uncertainty()) & {r.image_id for r in p["rows"]}
    return {"key": p["key"], "is_test_data": p["is_test_data"], "size": len(p["rows"]), "excluded_test_split": len(p["test_ids"]), "labeled": len(p["labeled"]),
            "scored": len(scored), "excluded_duplicates_of_labeled": sum(1 for r in sv.ctx.dataset.manifest(p["key"]) if r.duplicate_of)}


@router.post("/select")
def select(req: SelectRequest):
    return get_services().al.select(req.model_dump())


@router.get("/rounds")
def rounds():
    return get_services().al.rounds()


@router.get("/rounds/{round_id}/tasks")
def round_tasks(round_id: str):
    sv = get_services()
    return sv.al.task_manifest(round_id, sv.images)


@router.post("/export")
def export(req: ExportRequest):
    sv = get_services()
    manifest = sv.al.task_manifest(req.round_id, sv.images)
    out = {"batch_id": manifest["batch_id"], "n_tasks": manifest["n_tasks"], "pushed": None}
    if req.push_to_label_studio:
        out["pushed"] = sv.annotations.push_to_label_studio(manifest["tasks"], req.title or f"DentaMind {req.round_id}")
    out["tasks"] = manifest["tasks"]
    return out
