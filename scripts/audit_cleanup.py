"""Remove the records the functionality audit created in the app database - and nothing else.

    .\\.venv\\Scripts\\python.exe scripts\\audit_cleanup.py --cutoff 2026-10-14T10:15:00            # dry run: counts and ids only
    .\\.venv\\Scripts\\python.exe scripts\\audit_cleanup.py --cutoff 2026-10-14T10:15:00 --apply    # back up the DB, then delete

Only rows whose ``created`` timestamp (UTC) is >= the cutoff are touched, in these tables: analyses, reports, region_reviews, al_rounds, annotation_batches,
and uploaded ``images`` (row + the stored file + its cached thumbnails). Jobs and experiments are history and are never deleted.
``--remove-active-models`` additionally deletes Data/checkpoints/active_models.json (the audit's UI crawl created it; it did not exist before).
Checkpoints, datasets, the original uploads and every row older than the cutoff are left alone. A SQLite backup is written first (``--backup-dir``).
The ids of everything removed are written to docs/audit_evidence/cleanup_log_<UTC time>.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TABLES = ("analyses", "reports", "region_reviews", "al_rounds", "annotation_batches")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cutoff", required=True, help="UTC ISO timestamp; rows created at or after it are audit records")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup-dir", default=str(ROOT / "runtime" / "backups"))
    ap.add_argument("--remove-active-models", action="store_true")
    a = ap.parse_args()
    from dentexmodel.config import get_settings
    s = get_settings()
    db_path = Path(s.db_path)
    con = sqlite3.connect(str(db_path))
    plan: dict = {}
    for t in TABLES:
        plan[t] = [r[0] for r in con.execute(f"SELECT id FROM {t} WHERE created >= ?", (a.cutoff,))]
    imgs = con.execute("SELECT id, rel_path, filename FROM images WHERE created >= ? AND source = 'upload'", (a.cutoff,)).fetchall()
    plan["images"] = [r[0] for r in imgs]
    before = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in (*TABLES, "images", "jobs", "experiments")}
    print("cutoff", a.cutoff, "| rows before:", before)
    print("to remove:", {k: len(v) for k, v in plan.items()})
    am = s.checkpoint_dir / "active_models.json"
    if a.remove_active_models and am.is_file():
        print("also removing", am.name)
    if not a.apply:
        print("dry run - nothing changed. Re-run with --apply.")
        return 0
    bdir = Path(a.backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = bdir / f"dentamind_before_audit_cleanup_{stamp}.sqlite3"
    dst = sqlite3.connect(str(backup))
    con.backup(dst)
    dst.close()
    print("backup written:", backup)
    removed_files = []
    for t in TABLES:
        con.executemany(f"DELETE FROM {t} WHERE id = ?", [(i,) for i in plan[t]])
    for iid, rel, _fn in imgs:
        con.execute("DELETE FROM images WHERE id = ?", (iid,))
        f = (s.upload_dir / rel).resolve()
        if s.upload_dir.resolve() in f.parents and f.is_file():          # only files inside the uploads folder
            f.unlink()
            removed_files.append(rel)
        for th in (s.processed_dir / "thumbs").glob(f"{iid}_*"):
            th.unlink()
    con.commit()
    after = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in (*TABLES, "images", "jobs", "experiments")}
    con.close()
    if a.remove_active_models and am.is_file():
        am.unlink()
    log = {"at": stamp, "cutoff": a.cutoff, "backup": str(backup.name), "rows_before": before, "rows_after": after, "removed_ids": plan, "removed_upload_files": removed_files,
           "removed_active_models_json": bool(a.remove_active_models)}
    out = ROOT / "docs" / "audit_evidence" / f"cleanup_log_{stamp}.json"
    out.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print("after:", after, "| log:", out.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
