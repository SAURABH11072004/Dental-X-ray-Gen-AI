from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import Response

from backend.schemas.models import ReportRequest, ReviewRequest
from backend.services.container import get_services

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
def generate(req: ReportRequest):
    return get_services().reports.generate(req.model_dump())


@router.get("")
def list_reports():
    sv = get_services()
    rows = sv.reports.list()
    for r in rows:          # image file name for the list (display only; the stored report is unchanged)
        try:
            r["image_name"] = sv.images.get(r["image_id"]).get("filename")
        except Exception:   # noqa: BLE001 - an image that is no longer registered must not break the list
            r["image_name"] = None
        r["languages"] = ["en", "hi", "mr"]
    return rows


@router.get("/{report_id}")
def get_report(report_id: str, lang: str = Query("en", pattern="^(en|hi|mr)$")):
    return get_services().reports.get(report_id, lang)


@router.post("/{report_id}/validate")
def validate(report_id: str):
    return get_services().reports.validate(report_id)


@router.post("/{report_id}/review")
def review(report_id: str, req: ReviewRequest):
    return get_services().reports.review(report_id, req.reviewer)


@router.get("/{report_id}/export")
def export(report_id: str, format: str = Query("json", pattern="^(json|html|txt)$"), lang: str = Query("en", pattern="^(en|hi|mr)$")):
    body, mime = get_services().reports.export(report_id, format, lang)
    return Response(body.encode("utf-8"), media_type=mime, headers={"Content-Disposition": f'attachment; filename="{report_id}_{lang}.{format}"'})
