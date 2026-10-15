from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse, Response

from backend.services.container import get_services

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    sv = get_services()
    limit = sv.ctx.settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)  # never buffer more than limit+1 bytes
    return sv.images.upload(file.filename or "upload", data)


@router.get("")
def list_images(source: str = Query("all", pattern="^(all|uploads|dataset|test_data)$"), limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return get_services().images.list(source, limit, offset)


@router.get("/{image_id}")
def get_image(image_id: str):
    return get_services().images.get(image_id)


@router.get("/{image_id}/file")
def image_file(image_id: str):
    path = get_services().images.resolve_path(image_id)
    return FileResponse(path)


@router.get("/{image_id}/thumbnail")
def thumbnail(image_id: str, size: int = Query(320, ge=64, le=1024)):
    return Response(get_services().images.thumbnail(image_id, size), media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@router.get("/{image_id}/quality")
def quality(image_id: str):
    return get_services().analysis.quality_for(image_id)
