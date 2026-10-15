"""Health checks and aggregated overview numbers. Everything is measured, nothing is assumed."""
from __future__ import annotations

import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

from backend.version import APP_VERSION
from dentexmodel.inference.registry import scan_checkpoints
from dentexmodel.inference.system import environment_report, gpu_info
from dentexmodel.storage import jload


def probe(url: str, timeout: float = 1.5) -> dict:
    u = urlparse(url)
    host, port = u.hostname or "localhost", u.port or (443 if u.scheme == "https" else 80)
    if host == "localhost":      # on Windows 'localhost' is tried over IPv6 first and a closed port makes each attempt wait; use the IPv4 loopback
        host = "127.0.0.1"
        url_try = url.replace("//localhost", "//127.0.0.1", 1)
    else:
        url_try = url
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return {"reachable": False, "url": url, "error": str(exc)}
    try:
        with urllib.request.urlopen(urllib.request.Request(url_try, method="GET"), timeout=timeout) as r:
            return {"reachable": True, "url": url, "status_code": r.status}
    except urllib.error.HTTPError as exc:
        return {"reachable": True, "url": url, "status_code": exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"reachable": True, "url": url, "note": str(exc)}


class SystemService:
    def __init__(self, ctx, annotation_service, experiments, al):
        self.ctx, self.ann, self.exp, self.al = ctx, annotation_service, experiments, al

    def health(self, probes: bool = True) -> dict:
        s = self.ctx.settings
        try:
            self.ctx.db.count("images")
            db_ok = True
        except Exception:  # noqa: BLE001
            db_ok = False
        ds = self.ctx.dataset.status()
        h = {"backend": "ok", "version": APP_VERSION, "database": "ok" if db_ok else "error",
             "dataset": {"state": ds.state, "main_available": ds.main_available, "message": ds.messages[0] if ds.messages else ""},
             "gpu": gpu_info(), "checkpoints_loaded": len(scan_checkpoints(s))}
        if probes:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as pool:      # independent services: probe them concurrently
                tb, ls = pool.submit(probe, s.tensorboard_url), pool.submit(probe, s.label_studio_url + "/health")
                h["tensorboard"] = tb.result()
                h["label_studio"] = {**ls.result(), "api_key_configured": bool(s.label_studio_api_key)}
        h["llm"] = {"configured": s.llm_configured, "mode": "llm" if s.llm_configured else "template"}
        return h

    def settings(self) -> dict:
        s = self.ctx.settings
        env = environment_report()
        diagnostics = []
        ds = self.ctx.dataset.status()
        if not ds.main_available:
            diagnostics.append({"severity": "warning", "message": "Main dataset is not available. Please place the dataset in " + ds.expected_location,
                                "fix": "Copy the DENTEX data into the data directory; it is detected automatically."})
        if not env["packages"].get("torch"):
            diagnostics.append({"severity": "warning", "message": "PyTorch is not installed (inference/training disabled).", "fix": "pip install -r requirements-ml.txt"})
        elif not env["gpu"]["cuda_available"]:
            diagnostics.append({"severity": "info", "message": "CUDA is not available; CPU will be used.", "fix": "Install an NVIDIA driver and a CUDA build of PyTorch."})
        if not scan_checkpoints(s):
            diagnostics.append({"severity": "warning", "message": "No model checkpoints found.", "fix": f"Place trained checkpoints in {s.checkpoint_dir.name}/ with a .json metadata sidecar."})
        if not s.label_studio_api_key:
            diagnostics.append({"severity": "info", "message": "LABEL_STUDIO_API_KEY is not set; use manual export/import.", "fix": "Add the token to .env."})
        if not s.llm_configured:
            diagnostics.append({"severity": "info", "message": "LLM not configured; reports use the deterministic template.", "fix": "Set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (optional)."})
        return {"settings": s.public_dict(), "environment": env, "diagnostics": diagnostics}

    def overview(self) -> dict:
        db = self.ctx.db
        ds = self.ctx.dataset.status()
        analyses = db.list("analyses", where="kind='detection'", limit=5000)
        teeth = sum(len((jload(a["result_json"]) or {}).get("detections", [])) for a in analyses)
        ann = self.ann.overview()
        exps = self.exp.list()
        latest = next((e for e in exps if not e["is_test_data"]), None)
        recent = []
        for a in db.list("analyses", where="kind IN ('detection','segmentation')", limit=8):
            recent.append({"image_id": a["image_id"], "kind": a["kind"], "model_version": a["model_version"], "status": a["status"], "created": a["created"],
                           "thumbnail_url": f"/api/images/{a['image_id']}/thumbnail"})
        return {"images_uploaded": db.count("images"), "images_in_dataset": ds.main_image_count + ds.test_image_count,
                "images_analyzed": len({a["image_id"] for a in analyses}), "teeth_detected": teeth,
                "pending_annotations": ann["counts"]["pending"], "al_rounds": db.count("al_rounds"),
                "models": [m.to_dict() for m in scan_checkpoints(self.ctx.settings)], "gpu": gpu_info(),
                "dataset": {"state": ds.state, "main_available": ds.main_available, "message": ds.messages[0] if ds.messages else "",
                            "test_image_count": ds.test_image_count, "main_image_count": ds.main_image_count},
                "latest_metrics": latest["metrics"] if latest else None, "latest_experiment": latest["id"] if latest else None,
                "recent_activity": recent, "al_curves": self.exp.series()}
