"""Application context: one place that wires settings, DB and service objects (no globals at import time)."""
from __future__ import annotations

import os
import threading

from dentexmodel.annotation import AnnotationStore
from dentexmodel.config import Settings, get_settings
from dentexmodel.data.dataset import DatasetService
from dentexmodel.storage import Database
from dentexmodel.training import JobManager
from dentexmodel.utils.logging_utils import setup_logging


class AppContext:
    def __init__(self, settings: Settings | None = None, trainer=None):
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        setup_logging(self.settings.logs_dir, self.settings.log_level)
        self.db = Database(self.settings.db_path)
        self.dataset = DatasetService(self.settings)
        self.annotations = AnnotationStore(self.settings.annotations_dir)
        self.jobs = JobManager(self.settings, self.db, trainer=trainer)
        self.public_api_url = (os.environ.get("PUBLIC_API_URL") or "http://localhost:8000").rstrip("/")
        self._watcher = None

    def start_background(self) -> None:
        if self.settings.auto_process and self._watcher is None:
            self._watcher = self.dataset.start_watcher()

    def stop_background(self) -> None:
        if self._watcher is not None:
            self._watcher.stop_event.set()  # type: ignore[attr-defined]
            self._watcher = None


_ctx: AppContext | None = None
_lock = threading.Lock()


def get_context() -> AppContext:
    global _ctx
    with _lock:
        if _ctx is None:
            _ctx = AppContext()
        return _ctx


def reset_context(ctx: AppContext | None = None) -> None:
    global _ctx
    with _lock:
        _ctx = ctx
