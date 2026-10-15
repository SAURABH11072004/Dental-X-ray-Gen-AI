from __future__ import annotations

from fastapi import APIRouter, Query

from backend.services.container import get_services
from dentexmodel.inference.system import gpu_info

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(probes: bool = Query(True)):
    return get_services().system.health(probes)


@router.get("/system/gpu")
def gpu():
    return gpu_info()


@router.get("/system/settings")
def settings():
    return get_services().system.settings()


@router.get("/overview")
def overview():
    return get_services().system.overview()


@router.get("/dataset/status")
def dataset_status():
    sv = get_services()
    st = sv.ctx.dataset.status().to_dict()
    st["last_processed"] = sv.ctx.dataset.last_processed()
    return st


@router.post("/dataset/process")
def dataset_process(force: bool = False):
    return get_services().ctx.dataset.process(force=force)


@router.get("/dataset/manifest")
def dataset_manifest(which: str = Query("auto", pattern="^(auto|main|test_data)$"), limit: int = Query(100, ge=1, le=2000), offset: int = Query(0, ge=0)):
    from dataclasses import asdict
    rows = get_services().ctx.dataset.manifest(which)
    return {"total": len(rows), "items": [asdict(r) for r in rows[offset:offset + limit]]}


@router.get("/dataset/audit")
def dataset_audit():
    """Summary written by ``python scripts/audit_dataset.py`` (Data/reports/dataset_audit.json)."""
    import json
    from dentexmodel.errors import NotFoundError
    p = get_services().ctx.settings.data_root / "reports" / "dataset_audit.json"
    if not p.is_file():
        raise NotFoundError("No dataset audit has been generated yet.", code="audit_missing", hint="Run: python scripts/audit_dataset.py")
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/dataset/leakage")
def dataset_leakage():
    """Result of scripts/check_leakage.py (pixel-identical + near-duplicate checks across splits and model training sets)."""
    import hashlib
    import json
    from dentexmodel.data.leakage import summarize
    from dentexmodel.errors import NotFoundError
    from dentexmodel.training.trainers import assignments_sha
    s = get_services().ctx.settings
    p = s.data_root / "reports" / "leakage_check.json"
    if not p.is_file():
        raise NotFoundError("No leakage check has been generated yet.", code="leakage_missing", hint="Run: python scripts/check_leakage.py")
    out = json.loads(p.read_text(encoding="utf-8"))
    out["summary"] = summarize(out.get("checks", []))       # always derived from the rows, never trusted from the file
    # stale = the split assignments or manifests changed after the check ran (a report without recorded inputs cannot be verified)
    sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.is_file() else None  # noqa: E731
    now_inputs = {"manifest_sha": sha(s.processed_dir / "manifest.json"), "manifest_test_data_sha": sha(s.processed_dir / "manifest_test_data.json"),
                  "assignments_sha": assignments_sha(s.splits_dir / "dentex_splits.json")}
    rec = out.get("inputs")
    out["stale"] = None if not rec else any(rec.get(k) != v for k, v in now_inputs.items())
    out["stale_reason"] = ("report predates input tracking; re-run scripts/check_leakage.py" if not rec else
                           "manifest or split assignments changed after this check ran; re-run scripts/check_leakage.py" if out["stale"] else None)
    return out


@router.get("/dataset/validation")
def dataset_validation(which: str = Query("auto", pattern="^(auto|main|test_data)$")):
    import json
    sv = get_services()
    key = "main" if (which == "main" or (which == "auto" and sv.ctx.dataset.status().main_available)) else "test_data"
    p = sv.ctx.settings.results_dir / f"validation_{key}.json"
    if not p.is_file():
        sv.ctx.dataset.process()
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"ok": None, "counts": {}, "examples": {}}
