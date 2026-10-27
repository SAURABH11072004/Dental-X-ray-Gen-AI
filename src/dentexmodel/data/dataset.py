"""High-level dataset facade: discover -> manifest -> validate -> split, with fingerprint-based caching.

When the real dataset appears in DATA_ROOT, :meth:`DatasetService.process` (called by the pipeline, the API and
the optional background watcher) picks it up without any code change.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone

from dentexmodel.config import Settings
from dentexmodel.data import splits as splitmod
from dentexmodel.data.discovery import DatasetStatus, discover
from dentexmodel.data.manifest import build_manifest, load_manifest, save_manifest
from dentexmodel.data.validation import check_split_leakage, validate_dataset

logger = logging.getLogger(__name__)


class DatasetService:
    def __init__(self, settings: Settings):
        self.s = settings
        self._lock = threading.Lock()
        self._last_fp: str | None = None

    # -- discovery ---------------------------------------------------------------------------------------
    def status(self) -> DatasetStatus:
        return discover(self.s)

    @property
    def state_file(self):
        return self.s.results_dir / "dataset_state.json"

    def last_processed(self) -> dict | None:
        if self.state_file.is_file():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    # -- processing --------------------------------------------------------------------------------------
    def process(self, force: bool = False, deep_validation: bool = True) -> dict:
        """Build manifest + validation + splits for whatever is present. Idempotent."""
        with self._lock:
            status = self.status()
            prev = self.last_processed()
            if (not force and prev and prev.get("fingerprint") == status.fingerprint and status.fingerprint
                    and prev.get("state") == status.state):
                prev["cached"] = True
                return prev
            t0 = time.time()
            self.s.ensure_dirs()
            summary: dict = {"state": status.state, "main_available": status.main_available, "fingerprint": status.fingerprint,
                             "processed_at": datetime.now(timezone.utc).isoformat(), "messages": list(status.messages),
                             "cached": False, "outputs": {}}
            fcfg = (self.s.data_cfg or {}).get("splits", {})
            seed = int(fcfg.get("seed", 42))
            fractions = fcfg.get("fractions") or {"train": 0.7, "val": 0.1, "calibration": 0.1, "test": 0.1}
            min_n = int(fcfg.get("min_images_for_split", 10))
            all_rows = build_manifest(self.s, status, fcfg.get("patient_id_regex"))
            groups = {"main": [r for r in all_rows if not r.is_test_data],
                      "test_data": [r for r in all_rows if r.is_test_data]}
            for key, rows in groups.items():
                if not rows:
                    continue
                if key == "main" and not status.main_available:
                    # unlabeled non-test images without any annotation file are not a "main dataset"
                    summary.setdefault("notes", []).append(
                        f"{len(rows)} unlabeled image(s) found outside test folders; waiting for the annotation file.")
                stem = "manifest" if key == "main" else "manifest_test_data"
                purpose = ("training/evaluation splits for the main dataset" if key == "main"
                           else "TEST DATA: pipeline smoke test only - not research results")
                split_path = self.s.splits_dir / ("dentex_splits.json" if key == "main" else "test_data_splits.json")
                # Only labeled images are split. Unlabeled images stay "unassigned" (the active-learning pool) and
                # must never be counted as train/val/test examples.
                splittable = [r for r in rows if r.annotation_status == "annotated"] if key == "main" else rows
                if key == "test_data" and status.main_available:
                    # With a real dataset present, the unlabeled validation_data images are held-out TEST DATA only:
                    # they get no train/val/test assignment (they must never look like training examples).
                    splittable, assign = [], {}
                    summary.setdefault("notes", []).append(
                        f"{len(rows)} unlabeled validation_data image(s) kept as test data; not split, not trainable.")
                elif len(splittable) >= min_n:
                    existing = splitmod.load_split_file(split_path).get("assignments", {})
                    ids = {r.image_id for r in splittable}
                    existing = {k: v for k, v in existing.items() if k in ids}   # drop ids from older manifests
                    assign = splitmod.assign_splits(splittable, seed, fractions, existing)
                    for r in rows:
                        r.split = assign.get(r.image_id, "unassigned")
                    splitmod.save_split_file(split_path, assign, seed, fractions, purpose,
                                             {"dataset": key, "fingerprint": status.fingerprint})
                else:
                    assign = {}
                    summary.setdefault("notes", []).append(f"{key}: only {len(splittable)} splittable image(s) (< {min_n}); splits not created.")
                report = validate_dataset(self.s, status, rows, deep=deep_validation)
                if assign:
                    check_split_leakage(rows, assign, report)
                report.ok = not any(sev == "error" for sev in report.severities.values())
                out_m = save_manifest(rows, self.s.processed_dir, stem)
                vfile = self.s.results_dir / f"validation_{key}.json"
                vfile.write_text(json.dumps(report.to_dict(), indent=1), encoding="utf-8")
                split_counts = {k: sum(1 for v in assign.values() if v == k) for k in splitmod.SPLIT_NAMES} if assign else {}
                summary[key] = {"n_images": len(rows), "validation_ok": report.ok, "issue_counts": report.counts,
                                "split_counts": split_counts,
                                "annotation_levels": sorted({r.annotation_level for r in rows}),
                                "n_with_masks": sum(1 for r in rows if r.has_masks),
                                "n_annotated": sum(1 for r in rows if r.annotation_status == "annotated"),
                                "manifest": out_m, "validation_file": vfile.name,
                                "is_test_data": key == "test_data"}
                summary["outputs"][key] = {"manifest": f"processed/{stem}.json", "validation": f"results/validation_{key}.json"}
            summary["elapsed_s"] = round(time.time() - t0, 2)
            self.state_file.write_text(json.dumps(summary, indent=1), encoding="utf-8")
            logger.info("Dataset processed: state=%s main=%s in %.2fs", status.state, status.main_available, summary["elapsed_s"])
            return summary

    def manifest(self, which: str = "auto") -> list:
        st = self.status()
        key = "main" if (which == "main" or (which == "auto" and st.main_available)) else "test_data"
        path = self.s.processed_dir / ("manifest.json" if key == "main" else "manifest_test_data.json")
        if not path.is_file():
            self.process()
        return load_manifest(path) if path.is_file() else []

    # -- watcher -----------------------------------------------------------------------------------------
    def start_watcher(self, interval_s: float | None = None) -> threading.Thread:
        """Poll DATA_ROOT; process the dataset when its fingerprint changes (e.g. real data was just copied in)."""
        interval = float(interval_s or self.s.auto_process_interval_s)
        stop = threading.Event()

        def loop():
            first = True
            while first or not stop.wait(interval):
                first = False
                try:
                    fp = discover(self.s).fingerprint
                    if fp != self._last_fp:
                        self._last_fp = fp
                        self.process()
                except Exception:  # noqa: BLE001 - watcher must never die
                    logger.exception("dataset watcher iteration failed")

        t = threading.Thread(target=loop, name="dataset-watcher", daemon=True)
        t.stop_event = stop  # type: ignore[attr-defined]
        t.start()
        return t
