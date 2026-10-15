from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.services.container import get_services

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class ReviewRequest(BaseModel):
    image_id: str = Field(min_length=1, max_length=128)
    region_id: Optional[str] = Field(default=None, max_length=160)
    action: str = Field(min_length=1, max_length=40)
    corrected_class: Optional[str] = Field(default=None, max_length=64)
    corrected_fdi: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    reviewer: str = Field(min_length=1, max_length=64)


class DecisionRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)
    approver: str = Field(min_length=1, max_length=64)


@router.get("/meta")
def meta():
    return get_services().reviews.meta()


@router.get("/queue")
def queue(limit: int = Query(50, ge=1, le=500)):
    return get_services().reviews.queue(limit)


@router.post("")
def submit(req: ReviewRequest):
    sv = get_services()
    sv.images.get(req.image_id)       # 404 for an unknown image: a review must refer to an image that exists
    return sv.reviews.store.submit(sv.ctx.settings, req.model_dump())


@router.get("")
def list_reviews(image_id: Optional[str] = None, status: Optional[str] = Query(None, pattern="^(submitted|approved|rejected)$"), all_revisions: bool = False):
    return {"items": get_services().reviews.store.list(image_id, status, current_only=not all_revisions)}


@router.get("/history")
def history(image_id: str, region_id: Optional[str] = None):
    return {"items": get_services().reviews.store.history(image_id, region_id)}


@router.post("/approve")
def approve(req: DecisionRequest):
    return {"items": get_services().reviews.store.decide(req.ids, req.approver, True)}


@router.post("/reject")
def reject(req: DecisionRequest):
    return {"items": get_services().reviews.store.decide(req.ids, req.approver, False)}


@router.get("/export")
def export(format: str = Query("json", pattern="^(json|csv)$")):
    body, mime = get_services().reviews.store.export(format)
    return Response(body.encode("utf-8"), media_type=mime, headers={"Content-Disposition": f'attachment; filename="approved_reviews.{format}"'})
