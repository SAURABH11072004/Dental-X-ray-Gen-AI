"""Active-learning service: candidate pool, selection, round history, Label Studio task manifests."""
from __future__ import annotations

from dentexmodel.active_learning import ALConfig, STRATEGIES, select_candidates
from dentexmodel.annotation import build_task
from dentexmodel.data.image_stats import compute_image_stats
from dentexmodel.data.splits import load_split_file
from dentexmodel.errors import DatasetUnavailableError, NotFoundError
from dentexmodel.storage import jdump, jload, new_id, now

STRATEGY_INFO = {
    "random": "Seeded uniform sampling. The baseline every other strategy is compared against.",
    "entropy": "Highest normalised predictive entropy: the classifier's probability mass is spread over many classes.",
    "disagreement": "Highest ensemble disagreement (generalised Jensen-Shannon): ensemble members predict different things.",
    "combined": "Weighted entropy + disagreement + mask instability, then a diversity-aware (embedding distance) greedy pass that drops near-duplicates.",
}


class ActiveLearningService:
    def __init__(self, ctx, analysis, pipeline=None):
        self.ctx, self.analysis, self.pipeline = ctx, analysis, pipeline

    def info(self) -> dict:
        return {"strategies": [{"id": k, "description": STRATEGY_INFO[k]} for k in STRATEGIES],
                "defaults": (self.ctx.settings.al_cfg or {}).get("defaults", {})}

    def pool(self) -> dict:
        """Candidate pool = images that may be queried: never test-split images; unlabeled main-dataset images, or (when
        only TEST DATA exists) the test-data images - flagged so results are never presented as research output."""
        st = self.ctx.dataset.status()
        if st.state == "missing":
            raise DatasetUnavailableError("Main dataset is not available. Please place the dataset in " + st.expected_location,
                                          hint="Active learning needs radiographs in the data directory.")
        key = "main" if st.main_available else "test_data"
        rows = self.ctx.dataset.manifest(key)
        splits = load_split_file(self.ctx.settings.splits_dir / ("dentex_splits.json" if key == "main" else "test_data_splits.json")).get("assignments", {})
        test_ids = {i for i, v in splits.items() if v == "test"}
        labeled_approved = {r["image_id"] for r in self.ctx.annotations.approved_records()}
        # pixel-identical copies of labeled radiographs are not new information and could leak a test image into training
        rows = [r for r in rows if r.image_id not in test_ids and r.split != "test" and r.image_id not in labeled_approved
                and not r.duplicate_of and (key == "test_data" or r.annotation_status == "unlabeled")]
        return {"key": key, "is_test_data": key == "test_data", "rows": rows, "test_ids": test_ids, "labeled": labeled_approved}

    def start_score_pool(self, n: int, seed: int) -> dict:
        """Run the uncertainty pipeline over a seeded random sample of eligible pool images, in a background thread."""
        import random
        import threading
        if self.pipeline is None:
            raise DatasetUnavailableError("Pipeline is not available.")
        pool = self.pool()
        scored = set(self.analysis.latest_uncertainty())
        todo = [r.image_id for r in pool["rows"] if r.image_id not in scored]
        random.Random(seed).shuffle(todo)
        todo = todo[:n]
        job_id = new_id("job")
        self.ctx.db.insert("jobs", {"id": job_id, "kind": "al_score_pool", "status": "running", "config_json": jdump({"n": n, "seed": seed, "images": todo}),
                                    "progress_json": jdump({"done": 0, "total": len(todo)}), "created": now(), "started": now(), "pid": __import__("os").getpid()})

        def run():
            done, failed = 0, []
            for iid in todo:
                try:
                    self.pipeline.run(iid, True, True)
                except Exception as exc:  # noqa: BLE001 - one bad image must not stop the job
                    failed.append({"image_id": iid, "error": str(exc)[:200]})
                done += 1
                self.ctx.db.update("jobs", "id", job_id, {"progress_json": jdump({"done": done, "total": len(todo), "failed": len(failed)})})
            self.ctx.db.update("jobs", "id", job_id, {"status": "succeeded" if not failed else "failed", "finished": now(),
                                                      "error": None if not failed else jdump(failed)[:800]})
        threading.Thread(target=run, daemon=True, name=job_id).start()
        return {"job_id": job_id, "total": len(todo), "pool_size": len(pool["rows"]), "already_scored": len(scored & {r.image_id for r in pool["rows"]})}

    def score_job(self, job_id: str) -> dict:
        j = self.ctx.db.get("jobs", job_id)
        if not j or j["kind"] != "al_score_pool":
            raise NotFoundError(f"Job '{job_id}' not found.")
        return {"job_id": job_id, "status": j["status"], "progress": jload(j["progress_json"]), "error": j["error"], "started": j["started"], "finished": j["finished"]}

    def candidates(self, pool: dict) -> list:
        stats = compute_image_stats(self.ctx.settings, pool["rows"])
        unc = self.analysis.latest_uncertainty()
        out = []
        for r in pool["rows"]:
            u = unc.get(r.image_id, {})
            def sig(name):
                s = u.get(name) or {}
                return s.get("value") if s.get("status") == "computed" else None
            e = stats.get(r.image_id, {})
            out.append({"image_id": r.image_id, "entropy": sig("entropy"), "disagreement": sig("disagreement"),
                        "mask_instability": sig("mask_instability"), "embedding": e.get("embedding"),
                        "quality_flags": e.get("flags", [])})
        return out

    def select(self, payload: dict) -> dict:
        defaults = (self.ctx.settings.al_cfg or {}).get("defaults", {})
        cfg = ALConfig(strategy=payload.get("strategy", defaults.get("strategy", "combined")), budget=payload.get("budget", defaults.get("budget", 20)),
                       batch_size=payload.get("batch_size", defaults.get("batch_size", 10)), seed=payload.get("seed", defaults.get("seed", 42)),
                       diversity_weight=payload.get("diversity_weight", defaults.get("diversity_weight", 0.3)),
                       weights=payload.get("weights", defaults.get("weights", {})), near_duplicate_cosine=defaults.get("near_duplicate_cosine", 0.995))
        cfg.validate()
        pool = self.pool()
        cands = self.candidates(pool)
        res = select_candidates(cands, cfg, exclude_ids=pool["labeled"], test_ids=pool["test_ids"])
        flags = {c["image_id"]: c["quality_flags"] for c in cands}
        out = res.to_dict()
        for s in out["selected"]:
            s["quality_flags"] = flags.get(s["image_id"], [])
        round_id = new_id("round")
        dataset_version = self.ctx.dataset.last_processed() or {}
        # model that produced the uncertainty signals behind this selection (None for a pure random draw: no model was used)
        unc = self.analysis.latest_uncertainty()
        used = sorted({(unc.get(i) or {}).get("model_version") for i in out["selected_ids"]} - {None}) if cfg.strategy != "random" else []
        model_version = payload.get("model_version") or (",".join(used) or None)
        out["model_version"] = model_version
        row = {"id": round_id, "strategy": cfg.strategy, "budget": cfg.budget, "seed": cfg.seed,
               "dataset_version": dataset_version.get("fingerprint"), "model_version": model_version,
               "config_json": jdump(out["config"]), "selected_json": jdump(out), "is_test_data": int(pool["is_test_data"]), "created": now()}
        self.ctx.db.insert("al_rounds", row)
        out.update(round_id=round_id, is_test_data=pool["is_test_data"], dataset_fingerprint=row["dataset_version"],
                   uncertainty_signals_available=any(c["entropy"] is not None or c["disagreement"] is not None for c in cands))
        if pool["is_test_data"]:
            out["warning"] = "Selection ran on TEST DATA (unlabeled sample radiographs); it validates the software only."
        return out

    def rounds(self) -> list:
        out = []
        for r in self.ctx.db.list("al_rounds"):
            sel = jload(r["selected_json"]) or {}
            out.append({"id": r["id"], "strategy": r["strategy"], "budget": r["budget"], "seed": r["seed"], "created": r["created"],
                        "dataset_version": r["dataset_version"], "model_version": r["model_version"], "is_test_data": bool(r["is_test_data"]),
                        "n_selected": len(sel.get("selected", [])), "notes": sel.get("notes", []),
                        "selected_ids": sel.get("selected_ids", [])})
        return out

    def task_manifest(self, round_id: str, images) -> dict:
        r = self.ctx.db.get("al_rounds", round_id)
        if not r:
            raise NotFoundError(f"Round '{round_id}' not found.")
        sel = jload(r["selected_json"])
        tasks = []
        for item in sel["selected"]:
            info = images.get(item["image_id"])
            tasks.append(build_task(item["image_id"], f"{self.ctx.public_api_url}{info['url']}", info["width"], info["height"], None, None,
                                    {"round_id": round_id, "strategy": r["strategy"], "score": item.get("score"), "reason": item.get("reason")}))
        batch_id = new_id("batch")
        self.ctx.db.insert("annotation_batches", {"id": batch_id, "round_id": round_id, "strategy": r["strategy"],
                                                  "image_ids_json": jdump([t["data"]["image_id"] for t in tasks]), "status": "exported", "created": now()})
        return {"batch_id": batch_id, "round_id": round_id, "n_tasks": len(tasks), "tasks": tasks,
                "note": "Real model predictions would appear as pre-annotations; none are included because no dental model is active." if not any(
                    t.get("predictions") for t in tasks) else ""}
