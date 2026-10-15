from __future__ import annotations

from fastapi import APIRouter, Query

from backend.schemas.models import TrainRequest
from backend.services.container import get_services
from dentexmodel.training import TrainConfig, check_prerequisites

router = APIRouter(prefix="/api/training", tags=["training"])


def _tensorboard_state(settings) -> dict:
    """What is really true about TensorBoard here: package installed? event files written by real training runs present?"""
    import importlib.util
    runs = settings.runs_dir
    logs = sum(1 for _ in runs.rglob("events.out.tfevents.*")) if runs.is_dir() else 0
    installed = importlib.util.find_spec("tensorboard") is not None
    return {"installed": installed, "event_files": logs,
            "message": ("TensorBoard is not installed (pip install tensorboard); training runs write no event files until it is." if not installed
                        else ("No event files yet: they appear after a training run." if not logs else f"{logs} event file(s) from real training runs."))}


@router.get("/prerequisites")
def prerequisites(task: str = Query("classification", pattern="^(classification|detection|segmentation|numbering)$"), architecture: str | None = None,
                  use_approved_annotations: bool = False):
    arch = architecture or {"classification": "resnet50", "detection": "fasterrcnn_resnet50_fpn", "segmentation": "maskrcnn_resnet50_fpn", "numbering": "fasterrcnn_resnet50_fpn"}[task]
    cfg = TrainConfig(task=task, architecture=arch, use_approved_annotations=use_approved_annotations)
    sv = get_services()
    return {**check_prerequisites(sv.ctx.settings, cfg), "architectures": {
        "classification": ["resnet50", "resnet18"], "detection": ["fasterrcnn_resnet50_fpn"], "segmentation": ["maskrcnn_resnet50_fpn"], "numbering": ["fasterrcnn_resnet50_fpn"]},
        "tensorboard_url": sv.ctx.settings.tensorboard_url, "tensorboard": _tensorboard_state(sv.ctx.settings)}


@router.post("/start")
def start(req: TrainRequest):
    d = req.model_dump()
    dry = d.pop("dry_run", False)
    return get_services().ctx.jobs.start(TrainConfig(**d), dry_run=dry)


@router.get("/status/{job_id}")
def status(job_id: str):
    return get_services().ctx.jobs.get(job_id)


@router.get("/jobs")
def jobs():
    return get_services().ctx.jobs.list()


@router.post("/stop/{job_id}")
def stop(job_id: str):
    return get_services().ctx.jobs.cancel(job_id)
