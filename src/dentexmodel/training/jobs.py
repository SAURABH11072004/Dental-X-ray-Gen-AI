"""Background training jobs (thread-based, SQLite-persisted). The API never blocks on training."""
from __future__ import annotations

import logging
import os
import threading
import traceback
from typing import Callable

from dentexmodel.config import Settings
from dentexmodel.errors import ConflictError, DentaMindError, NotFoundError
from dentexmodel.storage import Database, jdump, jload, new_id, now
from dentexmodel.training.config import TrainConfig, check_prerequisites

logger = logging.getLogger(__name__)


def pid_alive(pid: int | None) -> bool:
    """True if a process with this id is running. Never signals the process (os.kill(pid, 0) would terminate it on Windows)."""
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, int(pid))      # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return bool(ok) and code.value == 259                  # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class JobContext:
    """Passed to a trainer: report real progress/metrics and poll for cancellation."""

    def __init__(self, db: Database, job_id: str, settings: Settings):
        self.db, self.job_id, self.settings = db, job_id, settings
        self.cancel_event = threading.Event()
        self.log_path = settings.logs_dir / f"{job_id}.log"
        self.tb_dir = settings.runs_dir / job_id

    def log(self, msg: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{now()} {msg}\n")

    def progress(self, epoch: int, total: int, metrics: dict | None = None) -> None:
        row = self.db.get("jobs", self.job_id) or {}
        hist = (jload(row.get("metrics_json")) or {}).get("history", [])
        if metrics is not None:
            hist.append({"epoch": epoch, **metrics})
        self.db.update("jobs", "id", self.job_id, {"progress_json": jdump({"epoch": epoch, "total_epochs": total}),
                                                    "metrics_json": jdump({"history": hist})})

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()


def strip_paths(text: str) -> str:
    """Reduce absolute Windows paths to their file name (path segments may contain spaces; this project's own folder does)."""
    import re
    return re.sub(r"[A-Za-z]:[\\/](?:[^\\/:*?\"<>|\r\n]+[\\/])*([^\\/:*?\"<>|\r\n']*)", lambda m: m.group(1) or "<path>", text)


def short_error(text, max_len: int = 400):
    """Public form of a stored job error: the final exception line(s) only, traceback frames dropped and absolute
    paths reduced to file names. The raw text stays in the database/log; the API never serves local paths."""
    if not text:
        return text
    lines = [l.rstrip() for l in str(text).splitlines() if l.strip()]
    keep = [l for l in lines if not l.lstrip().startswith(("File ", "Traceback")) and not l.startswith("    ")]
    msg = " | ".join(keep[-3:] if keep else lines[-1:])
    return strip_paths(msg)[:max_len]


class JobManager:
    def __init__(self, settings: Settings, db: Database, trainer: Callable | None = None):
        self.s, self.db = settings, db
        self.trainer = trainer
        self._ctx: dict = {}
        # Jobs whose owning process is gone can never finish. A job owned by another LIVE process (e.g. a CLI training
        # run started with scripts/train_model.py while the API restarts) must be left alone.
        for j in self.db.list("jobs", where="status IN ('running','queued')"):
            if j.get("pid") and j["pid"] != os.getpid() and pid_alive(j["pid"]):
                continue
            self.db.update("jobs", "id", j["id"], {"status": "interrupted", "error": "Server restarted while the job was running.",
                                                    "finished": now()})

    def default_trainer(self):
        from dentexmodel.training.trainers import run_training  # lazy: needs torch
        return run_training

    def running_jobs(self) -> list:
        """Jobs that still hold (or may hold) the GPU: running/queued jobs of this process or of another LIVE process."""
        return [j for j in self.db.list("jobs", where="status IN ('running','queued')")
                if not j.get("pid") or j["pid"] == os.getpid() or pid_alive(j["pid"])]

    def start(self, cfg: TrainConfig, dry_run: bool = False) -> dict:
        cfg.assert_valid()
        pre = check_prerequisites(self.s, cfg)
        if not pre["ready"]:
            raise DentaMindError("Training prerequisites are not met.", code="prerequisites_unmet",
                                 hint="; ".join(u["message"] + " " + u["fix"] for u in pre["unmet"]), details=pre)
        busy = self.running_jobs()
        if busy:     # one job at a time: the GPU (4 GB here) cannot hold two, and two jobs could race for the same experiment name
            raise ConflictError(f"Another job is still running ({busy[0]['kind']} {busy[0]['id']}).", code="job_already_running",
                                hint="Wait for it to finish (GET /api/training/jobs) or stop it, then start this job.")
        if dry_run:   # everything above was checked for real; nothing is started or written
            stem = f"{cfg.experiment_name}_{cfg.task}"
            i = 1
            while (self.s.checkpoint_dir / f"{stem}_v{i}.pth").exists():
                i += 1
            return {"dry_run": True, "valid": True, "config": cfg.to_dict(), "prerequisites": pre, "would_write_checkpoint": f"{stem}_v{i}.pth",
                    "note": "Validation only: no job was created and no file was written."}
        job_id = new_id("job")
        self.db.insert("jobs", {"id": job_id, "kind": f"train_{cfg.task}", "status": "queued", "config_json": jdump(cfg.to_dict()),
                                "progress_json": jdump({"epoch": 0, "total_epochs": cfg.epochs}), "created": now(),
                                "pid": os.getpid()})
        ctx = JobContext(self.db, job_id, self.s)
        self._ctx[job_id] = ctx
        t = threading.Thread(target=self._run, args=(job_id, cfg, ctx), daemon=True, name=job_id)
        t.start()
        return self.get(job_id)

    def _run(self, job_id: str, cfg: TrainConfig, ctx: JobContext) -> None:
        self.db.update("jobs", "id", job_id, {"status": "running", "started": now(), "log_path": ctx.log_path.name})
        try:
            trainer = self.trainer or self.default_trainer()
            result = trainer(cfg, ctx) or {}
            status = "cancelled" if ctx.cancelled else "succeeded"
            # record the experiment BEFORE publishing the terminal status, so anything that sees "succeeded" also sees its experiment
            if status == "succeeded" and result.get("metrics"):
                self._record_experiment(job_id, cfg, result)
            self.db.update("jobs", "id", job_id, {"status": status, "finished": now(), "checkpoint": result.get("checkpoint")})
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            logger.exception("job %s failed", job_id)
            ctx.log(traceback.format_exc())
            msg = exc.message if isinstance(exc, DentaMindError) else f"{type(exc).__name__}: {exc}"
            self.db.update("jobs", "id", job_id, {"status": "failed", "error": msg, "finished": now()})

    def _record_experiment(self, job_id: str, cfg: TrainConfig, result: dict) -> None:
        from dentexmodel.inference.system import gpu_info
        job = self.db.get("jobs", job_id)
        self.db.insert("experiments", {"id": new_id("exp"), "strategy": result.get("strategy", "supervised"),
                                       "dataset_version": cfg.dataset_version, "model_version": cfg.experiment_name,
                                       "budget": result.get("budget"), "round": result.get("round"), "seed": cfg.seed,
                                       "duration_s": result.get("duration_s"), "metrics_json": jdump(result["metrics"]),
                                       "config_json": jdump(cfg.to_dict()), "gpu": gpu_info().get("gpu_name"),
                                       "checkpoint": result.get("checkpoint"), "status": "completed", "is_test_data": 0, "created": now()})

    def cancel(self, job_id: str) -> dict:
        if self.db.get("jobs", job_id) is None:
            raise NotFoundError(f"Unknown job '{job_id}'.", code="job_not_found")
        ctx = self._ctx.get(job_id)
        if ctx is None:
            raise DentaMindError("Job is not running in this server process.", code="job_not_running")
        ctx.cancel_event.set()
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        j = self.db.get("jobs", job_id)
        if j is None:
            raise NotFoundError(f"Unknown job '{job_id}'.", code="job_not_found")
        return self._public(j)

    def list(self) -> list:
        return [self._public(j) for j in self.db.list("jobs", limit=100)]

    def _public(self, j: dict) -> dict:
        log_tail = []
        if j.get("log_path"):
            p = self.s.logs_dir / j["log_path"]
            if p.is_file():
                log_tail = [strip_paths(l) for l in p.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]]
        return {"id": j["id"], "kind": j["kind"], "status": j["status"], "config": jload(j["config_json"]),
                "progress": jload(j["progress_json"]), "metrics": jload(j["metrics_json"]), "checkpoint": j["checkpoint"],
                "error": short_error(j["error"]), "created": j["created"], "started": j["started"], "finished": j["finished"], "log_tail": log_tail,
                "tensorboard_logdir": f"{self.s.runs_dir.name}/{j['id']}"}
