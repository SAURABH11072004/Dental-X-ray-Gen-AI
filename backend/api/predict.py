from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from backend.schemas.models import ExplainRequest, FullAnalysisRequest, PredictBatchRequest, PredictRequest, UncertaintyRequest
from backend.services.container import get_services

router = APIRouter(prefix="/api", tags=["inference"])


@router.post("/predict")
def predict(req: PredictRequest):
    """Real model inference. Responds 503 with a model_unavailable error when no dental checkpoint is active."""
    return get_services().analysis.predict(req.image_id, req.model_version, req.with_classification)


@router.post("/predict/batch")
def predict_batch(req: PredictBatchRequest):
    """Sequential inference over up to 25 images. A failing image is reported in place and does not abort the batch;
    a missing model is raised once (every item would fail the same way)."""
    from dentexmodel.errors import DentaMindError, ModelUnavailableError
    sv = get_services()
    results = []
    for iid in dict.fromkeys(req.image_ids):
        try:
            results.append({"image_id": iid, "ok": True, "result": sv.analysis.predict(iid, None, req.with_classification)})
        except ModelUnavailableError:
            raise
        except DentaMindError as exc:
            results.append({"image_id": iid, "ok": False, "error": exc.to_dict()})
    return {"count": len(results), "succeeded": sum(1 for r in results if r["ok"]), "results": results}


@router.get("/analyses/{analysis_id}/overlay")
def analysis_overlay(analysis_id: str, min_score: float = 0.3):
    """PNG of the stored detections (and top finding per box) drawn on the original radiograph."""
    png = get_services().analysis.overlay_png(analysis_id, min_score)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/analyze/full")
def analyze_full(req: FullAnalysisRequest):
    """preprocess -> detect -> number -> segment -> match -> classify -> uncertainty. Each step reports ok / unavailable / failed;
    regions are linked by IoU matching and stable ids, and the image-level uncertainty record is saved for the Uncertainty page."""
    return get_services().pipeline.run(req.image_id, req.segmentation, req.uncertainty)


@router.post("/uncertainty/image")
def uncertainty_image(req: FullAnalysisRequest):
    """Compute and persist real uncertainty signals for one image (runs the pipeline) and return the saved record."""
    r = get_services().pipeline.run(req.image_id, True, True)
    return {"image_id": req.image_id, "analysis_id": r["analysis_id"], "uncertainty": r["uncertainty"], "summary": r["summary"], "steps": r["steps"]}


@router.post("/segment")
def segment(req: PredictRequest):
    return get_services().analysis.segment(req.image_id, req.model_version)


@router.post("/explain")
def explain(req: ExplainRequest):
    """Grad-CAM for one region; 503 model_unavailable until a dental classification checkpoint is active."""
    return get_services().analysis.explain(req.image_id, req.box)


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    return get_services().analysis.get_analysis(analysis_id)


@router.post("/uncertainty/score")
def uncertainty_score(req: UncertaintyRequest):
    return get_services().analysis.score_uncertainty(req.model_dump())


@router.get("/uncertainty/table")
def uncertainty_table(limit: int = 200):
    """Rows for the Uncertainty page: every image with a SAVED uncertainty record (real signals, with their reasons when a signal is
    unavailable), then a few images that have none yet. Image-quality flags are reported separately from predictive uncertainty."""
    sv = get_services()
    unc = sv.analysis.latest_uncertainty()
    by_id = {}
    for it in sv.images.list("all", 1000, 0)["items"]:
        by_id[it["id"]] = it
    rows = []
    for iid, u in unc.items():
        it = by_id.get(iid)
        if it is None:
            try:
                it = sv.images.get(iid)
            except Exception:  # noqa: BLE001 - image removed after analysis
                continue
        sig = {k: (u[k]["value"] if u[k]["status"] == "computed" else None) for k in ("entropy", "disagreement", "mask_instability", "detection_instability")}
        reasons = {k: u[k]["reason"] for k in sig if u[k]["status"] != "computed"}
        rows.append({**{k: it.get(k) for k in ("id", "filename", "width", "height", "source", "split", "url", "thumbnail_url", "is_test_data")}, **sig,
                     "combined_score": u.get("combined_score"), "quality_flags": u.get("quality_flags", []), "quality_metrics": u.get("quality_metrics", {}),
                     "unavailable_reasons": reasons, "methods": u.get("methods", {}), "analysis_id": u.get("analysis_id"), "thresholds": u.get("thresholds"),
                     "computed": True})
    rows.sort(key=lambda r: -(r["combined_score"] if r["combined_score"] is not None else -1))
    scored = {r["id"] for r in rows}
    rest = [it for iid, it in by_id.items() if iid not in scored][:max(0, limit - len(rows))]
    for it in rest:
        rows.append({**{k: it.get(k) for k in ("id", "filename", "width", "height", "source", "split", "url", "thumbnail_url", "is_test_data")},
                     "entropy": None, "disagreement": None, "mask_instability": None, "detection_instability": None, "combined_score": None,
                     "quality_flags": [], "unavailable_reasons": {"all": "uncertainty has not been computed for this image yet (X-ray Analysis -> Calculate Uncertainty)"},
                     "analysis_id": None, "computed": False})
    return {"items": rows[:limit], "total": len(rows), "n_computed": len(scored), "model_signals_available": bool(scored)}
