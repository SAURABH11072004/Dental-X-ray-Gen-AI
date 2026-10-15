"""Experiments listing, comparability checks and chart series (real records only)."""
from __future__ import annotations

from dentexmodel.storage import jload

METRIC_PATHS = {"detection_map": ("detection", "map"), "detection_ap50": ("detection", "ap50"), "classification_macro_f1": ("classification", "macro_f1"),
                "mask_ap": ("segmentation", "mask_ap"), "calibration_ece": ("calibration", "ece")}


def _metric(m: dict, name: str):
    a, b = METRIC_PATHS[name]
    v = (m.get(a) or {}).get(b)
    return None if v is None else float(v)


class ExperimentService:
    def __init__(self, ctx):
        self.ctx = ctx

    def list(self) -> list:
        out = []
        for r in self.ctx.db.list("experiments"):
            m = jload(r["metrics_json"]) or {}
            out.append({"id": r["id"], "strategy": r["strategy"], "dataset_version": r["dataset_version"], "model_version": r["model_version"],
                        "budget": r["budget"], "round": r["round"], "seed": r["seed"], "duration_s": r["duration_s"], "gpu": r["gpu"],
                        "checkpoint": r["checkpoint"], "status": r["status"], "is_test_data": bool(r["is_test_data"]), "created": r["created"],
                        "metrics": {k: _metric(m, k) for k in METRIC_PATHS}, "config": jload(r["config_json"])})
        return out

    def compare(self, ids: list) -> dict:
        exps = [e for e in self.list() if e["id"] in set(ids)]
        warnings = []
        if len({e["dataset_version"] for e in exps}) > 1:
            warnings.append("Selected experiments use different dataset versions; results are not directly comparable.")
        if len({(e["config"] or {}).get("seed") for e in exps}) > 1 and len({e["strategy"] for e in exps}) > 1:
            warnings.append("Experiments use different random seeds; differences between strategies may be noise.")
        if len({e["budget"] for e in exps}) > 1:
            warnings.append("Experiments use different annotation budgets.")
        if any(e["is_test_data"] for e in exps):
            warnings.append("Includes records marked as TEST DATA; they are not research results.")
        common = [k for k in METRIC_PATHS if all(e["metrics"].get(k) is not None for e in exps)] if exps else []
        return {"experiments": exps, "comparable_metrics": common, "warnings": warnings}

    def series(self) -> dict:
        """Performance vs annotation budget, grouped by strategy - only experiments that recorded both."""
        by: dict = {}
        for e in self.list():
            if e["budget"] is None or e["is_test_data"]:
                continue
            for k, v in e["metrics"].items():
                if v is not None:
                    by.setdefault(k, {}).setdefault(e["strategy"], []).append({"budget": e["budget"], "value": v, "round": e["round"], "id": e["id"]})
        for k in by:
            for s in by[k]:
                by[k][s].sort(key=lambda p: p["budget"])
        return by
