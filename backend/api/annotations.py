from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from backend.schemas.models import ApproveRequest, ImportRequest, PullRequest
from backend.services.container import get_services
from dentexmodel.annotation import labeling_config_xml

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


@router.get("")
def overview():
    return get_services().annotations.overview()


@router.get("/label-config")
def label_config():
    sv = get_services()
    return Response(labeling_config_xml(sv.annotations.supported_labels() or None), media_type="application/xml")


@router.get("/connection")
def connection():
    return get_services().annotations.connection()


@router.post("/import")
def import_annotations(req: ImportRequest):
    return get_services().annotations.import_export(req.tasks)


@router.post("/import-from-label-studio")
def pull(req: PullRequest):
    return get_services().annotations.pull_from_label_studio(req.project_id)


@router.post("/approve")
def approve(req: ApproveRequest):
    return get_services().annotations.approve(req.image_ids, req.reviewer)


@router.post("/reject")
def reject(req: ApproveRequest):
    return get_services().annotations.reject(req.image_ids, req.reviewer)


@router.get("/records")
def records():
    return list(get_services().ctx.annotations.all().values())
