"""End-to-end data/ML pipeline orchestrator with per-step status, timing, error capture and logging.

Works with whatever is present in DATA_ROOT:
* main dataset present  -> manifest, validation, splits, stats, inference (if checkpoints exist), evaluation hooks
* only unlabeled TEST DATA -> everything that does not need labels or a trained model (clearly marked as test data)
* nothing -> a clear "dataset missing" report; exit code 0 (not a crash)

Training is *not* started automatically; it is a deliberate action (``scripts/train_model.py`` or the API).
"""
from __future__ import annotations

import json
import logging
import time
import traceback
from datetime import datetime, timezone

from dentexmodel.active_learning import ALConfig, select_candidates
from dentexmodel.config import Settings
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.image_stats import compute_image_stats
from dentexmodel.errors import DentaMindError, ModelUnavailableError
from dentexmodel.inference.registry import TASKS, active_model
from dentexmodel.inference.system import gpu_info

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, settings: Settings):
        self.s = settings
        self.steps: list = []

    def _step(self, name: str, fn, *a, **kw):
        t0 = time.time()
        rec = {"step": name, "status": "ok", "message": "", "details": {}}
        try:
            out = fn(*a, **kw)
            if isinstance(out, dict) and out.get("_skipped"):
                rec["status"], rec["message"] = "skipped", out["_skipped"]
                out = {k: v for k, v in out.items() if k != "_skipped"}
            rec["details"] = out if isinstance(out, dict) else {}
        except DentaMindError as exc:
            rec["status"], rec["message"] = "failed", f"{exc.message} {exc.hint or ''}".strip()
            logger.warning("step %s failed: %s", name, exc.message)
        except Exception as exc:  # noqa: BLE001
            rec["status"], rec["message"] = "failed", f"{type(exc).__name__}: {exc}"
            rec["traceback"] = traceback.format_exc()
            logger.exception("step %s crashed", name)
        rec["seconds"] = round(time.time() - t0, 2)
        self.steps.append(rec)
        logger.info("pipeline step %-24s %s (%.1fs) %s", name, rec["status"], rec["seconds"], rec["message"])
        return rec

    def run(self, max_images: int | None = None, deep_validation: bool = True, force: bool = False) -> dict:
        self.s.ensure_dirs()
        self.steps = []
        svc = DatasetService(self.s)
        started = datetime.now(timezone.utc).isoformat()
        status = svc.status()
        mode = {"main_available": "main_dataset", "test_data_only": "test_data_smoke", "missing": "no_data"}[status.state]
        report = {"started": started, "mode": mode, "dataset": status.to_dict(), "steps": self.steps,
                  "notice": ("TEST DATA ONLY - unlabeled radiographs; results validate the software, not the model." if mode == "test_data_smoke"
                             else "Main dataset is not available. Please place the dataset in " + status.expected_location if mode == "no_data" else "")}
        if mode == "no_data":
            self._step("dataset_discovery", lambda: {"_skipped": " ".join(status.messages)})
            return self._finish(report)
        self._step("dataset_discovery", lambda: {"state": status.state, "sources": len(status.sources), "messages": status.messages})
        proc = self._step("process_dataset", svc.process, force=force, deep_validation=deep_validation)
        key = "main" if status.main_available else "test_data"
        rows = svc.manifest("main" if status.main_available else "test_data")
        stats = self._step("image_stats", lambda: self._stats(rows, max_images))
        models = self._step("model_availability", self._models)
        have_all = models["details"].get("any_available", False)
        self._step("inference", lambda: {"_skipped": "No dental checkpoint is active, so no predictions were generated. "
                                         "No synthetic predictions are produced."} if not have_all else {"_skipped": "Batch inference runs via /api/predict or scripts/score_unlabeled.py."})
        self._step("uncertainty", lambda: {"_skipped": "Model-based signals (entropy, disagreement, mask instability) need predictions; "
                                           "only image-quality signals are available."})
        self._step("active_learning_dry_run", lambda: self._al_dry_run(rows, status.main_available, max_images))
        self._step("evaluation", lambda: {"_skipped": "Needs ground-truth labels and predictions from a trained model."})
        self._step("training_prerequisites", self._train_prereq)
        report["summary"] = {"dataset_key": key, "n_images": len(rows), "processed": proc["details"].get(key) if isinstance(proc["details"], dict) else None}
        return self._finish(report)

    def _stats(self, rows, max_images):
        st = compute_image_stats(self.s, rows, max_images)
        errs = {k: v["error"] for k, v in st.items() if v.get("error")}
        flags: dict = {}
        for v in st.values():
            for f in v.get("flags", []):
                flags[f] = flags.get(f, 0) + 1
        return {"computed": len(st) - len(errs), "errors": errs, "quality_flag_counts": flags}

    def _models(self):
        avail = {}
        for t in TASKS:
            try:
                m = active_model(self.s, t)
                avail[t] = {"available": True, "version": m.version}
            except ModelUnavailableError as exc:
                avail[t] = {"available": False, "reason": exc.message, "hint": exc.hint}
        return {"tasks": avail, "any_available": any(v["available"] for v in avail.values()), "gpu": gpu_info()}

    def _al_dry_run(self, rows, main: bool, max_images):
        stats = compute_image_stats(self.s, rows, max_images)
        cands = [{"image_id": r.image_id, "embedding": stats.get(r.image_id, {}).get("embedding")}
                 for r in rows if not r.split == "test"]
        cfg = ALConfig(strategy="random", budget=min(5, len(cands)), batch_size=5, seed=42)
        res = select_candidates(cands, cfg)
        return {"strategy": "random", "selected": [s.image_id for s in res.selected], "pool_size": res.pool_size,
                "note": "Dry run of the selection engine" + ("" if main else " on TEST DATA; not a research result.")}

    def _train_prereq(self):
        from dentexmodel.training.config import TrainConfig, check_prerequisites
        return {t: check_prerequisites(self.s, TrainConfig(task=t, architecture={"classification": "resnet50", "detection": "fasterrcnn_resnet50_fpn",
                                                                                   "segmentation": "maskrcnn_resnet50_fpn"}[t])) for t in
                ("classification", "detection", "segmentation")}

    def _finish(self, report: dict) -> dict:
        failed = [s for s in self.steps if s["status"] == "failed"]
        report["finished"] = datetime.now(timezone.utc).isoformat()
        report["ok"] = not failed
        report["failed_steps"] = [s["step"] for s in failed]
        try:
            self.s.results_dir.mkdir(parents=True, exist_ok=True)
            (self.s.results_dir / "pipeline_report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        except OSError as exc:
            logger.warning("could not write pipeline report: %s", exc)
        return report
