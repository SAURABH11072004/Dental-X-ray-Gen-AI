"""Runtime configuration.

Everything comes from environment variables / a ``.env`` file / ``configs/*.yaml``. No absolute paths are
hard-coded. The data directory is auto-located (``data`` or ``Data`` - Windows checkouts often use the
latter) relative to the project root, or set explicitly with ``DATA_ROOT``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote


def find_project_root() -> Path:
    env = os.environ.get("PROJECT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "configs").is_dir() and (parent / "src" / "dentexmodel").is_dir():
            return parent
    return Path.cwd().resolve()


def _load_dotenv(root: Path) -> None:
    """Load ``.env`` without overriding variables already set in the real environment."""
    env_file = root / ".env"
    if not env_file.is_file():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_file, override=False)
        return
    except ImportError:
        pass
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_yaml(path: Path) -> dict:
    """Read a YAML config; returns {} if the file or PyYAML is missing."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return {}
    if not Path(path).is_file():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve(root: Path, value: str | None, default: Path) -> Path:
    if not value:
        return default
    p = Path(value).expanduser()
    return (p if p.is_absolute() else root / p).resolve()


def _locate_data_root(root: Path, value: str | None) -> Path:
    if value:
        return _resolve(root, value, root / "data")
    for name in ("data", "Data", "DATA"):
        if (root / name).is_dir():
            return (root / name).resolve()
    return (root / "data").resolve()


def _sqlite_path(url: str | None, default: Path, root: Path) -> Path:
    if not url:
        return default
    parsed = urlparse(url)
    if parsed.scheme not in ("sqlite", ""):
        raise ValueError(f"Only sqlite DATABASE_URL is supported, got '{parsed.scheme}'.")
    raw = unquote(parsed.path if parsed.scheme else url)
    if parsed.scheme and raw.startswith("/"):
        raw = raw[1:]  # sqlite:///rel.db -> rel.db ; sqlite:////abs.db -> /abs.db (SQLAlchemy convention)
    p = Path(raw)
    return (p if p.is_absolute() else root / p).resolve()


@dataclass
class Settings:
    project_root: Path
    data_root: Path
    checkpoint_dir: Path
    runs_dir: Path
    reports_dir: Path
    annotations_dir: Path
    splits_dir: Path
    processed_dir: Path
    raw_dir: Path
    results_dir: Path
    upload_dir: Path
    logs_dir: Path
    configs_dir: Path
    db_path: Path
    label_studio_url: str = "http://localhost:8080"
    label_studio_api_key: str = field(default="", repr=False)
    llm_base_url: str = ""
    llm_api_key: str = field(default="", repr=False)
    llm_model: str = ""
    frontend_url: str = "http://localhost:5173"
    tensorboard_url: str = "http://localhost:6006"
    max_upload_mb: int = 25
    auto_process: bool = True
    auto_process_interval_s: int = 15
    log_level: str = "INFO"
    data_cfg: dict = field(default_factory=dict)
    models_cfg: dict = field(default_factory=dict)
    al_cfg: dict = field(default_factory=dict)
    reporting_cfg: dict = field(default_factory=dict)

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @property
    def label_studio_configured(self) -> bool:
        return bool(self.label_studio_url and self.label_studio_api_key)

    def ensure_dirs(self) -> None:
        for p in (self.data_root, self.checkpoint_dir, self.runs_dir, self.reports_dir, self.annotations_dir,
                  self.splits_dir, self.processed_dir, self.raw_dir, self.results_dir, self.upload_dir, self.logs_dir):
            try:
                p.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass

    def public_dict(self) -> dict[str, Any]:
        """Settings safe to show in the UI (no secrets)."""
        def rel(p: Path) -> str:
            try:
                return Path(p).resolve().relative_to(self.project_root).as_posix()
            except ValueError:
                return str(p)
        return {
            "data_root": rel(self.data_root), "checkpoint_dir": rel(self.checkpoint_dir),
            "runs_dir": rel(self.runs_dir), "db_path": rel(self.db_path),
            "label_studio_url": self.label_studio_url, "label_studio_api_key_set": bool(self.label_studio_api_key),
            "tensorboard_url": self.tensorboard_url, "llm_configured": self.llm_configured,
            "llm_model": self.llm_model or None, "llm_base_url_set": bool(self.llm_base_url),
            "max_upload_mb": self.max_upload_mb, "auto_process": self.auto_process,
        }


def get_settings(root: Path | None = None, load_env: bool = True) -> Settings:
    root = Path(root).resolve() if root else find_project_root()
    if load_env:
        _load_dotenv(root)
    env = os.environ.get
    data_root = _locate_data_root(root, env("DATA_ROOT"))
    configs_dir = root / "configs"
    s = Settings(
        project_root=root,
        data_root=data_root,
        checkpoint_dir=_resolve(root, env("MODEL_CHECKPOINT_DIR"), data_root / "checkpoints"),
        runs_dir=data_root / "runs",
        reports_dir=data_root / "reports",
        annotations_dir=data_root / "annotations",
        splits_dir=data_root / "splits",
        processed_dir=data_root / "processed",
        raw_dir=data_root / "raw",
        results_dir=data_root / "results",
        upload_dir=data_root / "uploads",
        logs_dir=root / "logs",
        configs_dir=configs_dir,
        db_path=_sqlite_path(env("DATABASE_URL"), root / "runtime" / "dentamind.sqlite3", root),  # kept out of the image data folder
        label_studio_url=(env("LABEL_STUDIO_URL") or "http://localhost:8080").rstrip("/"),
        label_studio_api_key=env("LABEL_STUDIO_API_KEY") or "",
        llm_base_url=(env("LLM_BASE_URL") or "").rstrip("/"),
        llm_api_key=env("LLM_API_KEY") or "",
        llm_model=env("LLM_MODEL") or "",
        frontend_url=env("FRONTEND_URL") or "http://localhost:5173",
        tensorboard_url=env("TENSORBOARD_URL") or "http://localhost:6006",
        max_upload_mb=int(env("MAX_UPLOAD_MB") or 25),
        auto_process=_bool(env("AUTO_PROCESS_DATASET"), True),
        auto_process_interval_s=int(env("AUTO_PROCESS_INTERVAL_S") or 15),
        log_level=env("LOG_LEVEL") or "INFO",
        data_cfg=load_yaml(configs_dir / "data.yaml"),
        models_cfg=load_yaml(configs_dir / "models.yaml"),
        al_cfg=load_yaml(configs_dir / "active_learning.yaml"),
        reporting_cfg=load_yaml(configs_dir / "reporting.yaml"),
    )
    return s
