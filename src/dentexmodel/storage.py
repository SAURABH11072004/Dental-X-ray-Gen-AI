"""SQLite metadata store (stdlib only): images, analyses, AL rounds, annotation batches, jobs, experiments,
reports, model approvals. One short-lived connection per call; safe to use from API threads and job threads."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY, filename TEXT, rel_path TEXT, width INT, height INT, sha256 TEXT,
  source TEXT, quality_json TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY, image_id TEXT, kind TEXT, model_version TEXT, status TEXT,
  result_json TEXT, error TEXT, duration_s REAL, created TEXT);
CREATE TABLE IF NOT EXISTS al_rounds(id TEXT PRIMARY KEY, strategy TEXT, budget INT, seed INT, dataset_version TEXT,
  model_version TEXT, config_json TEXT, selected_json TEXT, is_test_data INT DEFAULT 0, created TEXT);
CREATE TABLE IF NOT EXISTS annotation_batches(id TEXT PRIMARY KEY, round_id TEXT, strategy TEXT, image_ids_json TEXT,
  status TEXT, label_studio_project INT, created TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, status TEXT, config_json TEXT, progress_json TEXT,
  metrics_json TEXT, log_path TEXT, checkpoint TEXT, error TEXT, created TEXT, started TEXT, finished TEXT);
CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, strategy TEXT, dataset_version TEXT, model_version TEXT,
  budget INT, round INT, seed INT, duration_s REAL, metrics_json TEXT, config_json TEXT, gpu TEXT, checkpoint TEXT,
  status TEXT, is_test_data INT DEFAULT 0, created TEXT);
CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, image_id TEXT, status TEXT, generated_by TEXT, report_json TEXT,
  validation_json TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS model_state(path TEXT PRIMARY KEY, eval_status TEXT, promoted INT DEFAULT 0, approved_by TEXT,
  updated TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.conn() as c:
                c.executescript(SCHEMA)
                if "pid" not in {r[1] for r in c.execute("PRAGMA table_info(jobs)")}:
                    c.execute("ALTER TABLE jobs ADD COLUMN pid INTEGER")   # owner process of a running job
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError(
                f"Cannot open the SQLite database at '{self.path}': {exc}. The folder must be on a local, writable disk "
                "(network, cloud-synced or virtual drives can break SQLite locking). Set DATABASE_URL in .env, e.g. "
                "DATABASE_URL=sqlite:///C:/DentaMind/dentamind.sqlite3") from exc

    @contextmanager
    def conn(self):
        with self._lock:
            c = sqlite3.connect(self.path, timeout=30)
            c.row_factory = sqlite3.Row
            try:
                yield c
                c.commit()
            finally:
                c.close()

    # generic helpers --------------------------------------------------------------------------------------
    def insert(self, table: str, row: dict) -> None:
        cols = ",".join(row)
        with self.conn() as c:
            c.execute(f"INSERT OR REPLACE INTO {table}({cols}) VALUES({','.join('?' * len(row))})", list(row.values()))

    def update(self, table: str, key: str, key_val, fields: dict) -> None:
        sets = ",".join(f"{k}=?" for k in fields)
        with self.conn() as c:
            c.execute(f"UPDATE {table} SET {sets} WHERE {key}=?", [*fields.values(), key_val])

    def get(self, table: str, key_val, key: str = "id") -> dict | None:
        with self.conn() as c:
            r = c.execute(f"SELECT * FROM {table} WHERE {key}=?", (key_val,)).fetchone()
        return dict(r) if r else None

    def list(self, table: str, order: str = "created DESC", limit: int = 500, where: str = "", params: tuple = ()) -> list:
        with self.conn() as c:
            rows = c.execute(f"SELECT * FROM {table} {('WHERE ' + where) if where else ''} ORDER BY {order} LIMIT ?", (*params, limit)).fetchall()
        return [dict(r) for r in rows]

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        with self.conn() as c:
            return c.execute(f"SELECT COUNT(*) FROM {table} {('WHERE ' + where) if where else ''}", params).fetchone()[0]


def jdump(obj) -> str:
    return json.dumps(obj, default=str)


def jload(s):
    return json.loads(s) if s else None
