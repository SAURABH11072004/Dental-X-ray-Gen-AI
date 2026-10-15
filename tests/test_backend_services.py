"""Service-layer tests (framework independent). The FastAPI routers are thin wrappers over these services."""
import json
import unittest

import helpers
from backend.services.container import Services
from backend.services.context import AppContext
from dentexmodel.data.synthetic import write_simulated_main_layout
from dentexmodel.errors import DatasetUnavailableError, DentaMindError, ImageValidationError, ModelUnavailableError, NotFoundError
from tests_labelstudio_fixture import ls_export


class ServiceCase(helpers.TmpCase):
    def setUp(self):
        super().setUp()
        self.ctx = AppContext(self.s)
        self.sv = Services(self.ctx)


class UploadTests(ServiceCase):
    def test_upload_flow(self):
        rec = self.sv.images.upload("x.png", helpers.png_bytes(1))
        self.assertTrue(rec["id"].startswith("up_"))
        self.assertEqual((rec["width"], rec["height"]), (512, 256))
        self.assertIn("quality", rec)
        self.assertTrue(self.sv.images.resolve_path(rec["id"]).is_file())
        self.assertTrue(self.sv.images.upload("again.png", helpers.png_bytes(1))["duplicate"])
        self.assertEqual(self.sv.images.list("uploads")["total"], 1)
        thumb = self.sv.images.thumbnail(rec["id"], 128)
        self.assertEqual(thumb[:3], b"\xff\xd8\xff")

    def test_upload_rejections(self):
        for name, data in (("a.txt", b"hello"), ("a.png", b"not png at all"), ("a.png", b"")):
            with self.assertRaises(ImageValidationError):
                self.sv.images.upload(name, data)
        self.s.max_upload_mb = 0
        with self.assertRaises(ImageValidationError) as cm:
            self.sv.images.upload("a.png", helpers.png_bytes(2))
        self.assertEqual(cm.exception.code, "file_too_large")

    def test_filename_cannot_escape_upload_dir(self):
        rec = self.sv.images.upload("../../evil.png", helpers.png_bytes(3))
        p = self.sv.images.resolve_path(rec["id"])
        self.assertEqual(p.parent, self.s.upload_dir.resolve())
        self.assertEqual(rec["filename"], "evil.png")

    def test_unknown_and_traversal_ids(self):
        for bad in ("nope", "../../etc/passwd", "..%2f..%2fetc"):
            with self.assertRaises(NotFoundError):
                self.sv.images.resolve_path(bad)

    def test_dataset_images_served_only_if_in_manifest(self):
        helpers.write_test_data_images(self.s.data_root, 12)
        self.ctx.dataset.process()
        items = self.sv.images.list("test_data")["items"]
        self.assertEqual(len(items), 12)
        self.assertTrue(self.sv.images.resolve_path(items[0]["id"]).is_file())
        self.assertTrue(items[0]["is_test_data"])
        (self.s.data_root / "secret.png").write_bytes(helpers.png_bytes(9))
        with self.assertRaises(NotFoundError):
            self.sv.images.resolve_path("secret")


class InferenceTests(ServiceCase):
    def test_predict_without_model_is_actionable_error(self):
        rec = self.sv.images.upload("x.png", helpers.png_bytes(1))
        with self.assertRaises(ModelUnavailableError) as cm:
            self.sv.analysis.predict(rec["id"])
        self.assertEqual(cm.exception.status_code, 503)
        self.assertTrue(cm.exception.hint)
        self.assertEqual(self.ctx.db.count("analyses"), 0)       # nothing fabricated or stored

    def test_uncertainty_only_what_inputs_allow(self):
        rec = self.sv.images.upload("x.png", helpers.png_bytes(1))
        d = self.sv.analysis.score_uncertainty({"image_id": rec["id"]})
        self.assertEqual(d["entropy"]["status"], "unavailable")
        self.assertIsNone(d["entropy"]["value"])
        self.assertIsNone(d["combined_score"])
        self.assertIn("metrics", {"metrics": d["quality_metrics"]})
        d2 = self.sv.analysis.score_uncertainty({"probabilities": [[0.5, 0.5], [1.0, 0.0]],
                                                 "member_probabilities": [[[1, 0], [1, 0]], [[0, 1], [1, 0]]]})
        self.assertAlmostEqual(d2["entropy"]["value"], 0.5)
        self.assertEqual(d2["disagreement"]["status"], "computed")
        self.assertEqual(d2["mask_instability"]["status"], "unavailable")
        self.assertIsNotNone(d2["combined_score"])

    def test_uncertainty_rejects_invalid_probabilities(self):
        with self.assertRaises(DentaMindError):
            self.sv.analysis.score_uncertainty({"probabilities": [[0.9, 0.9]]})

    def test_stored_uncertainty_feeds_active_learning(self):
        helpers.write_test_data_images(self.s.data_root, 12)
        self.ctx.dataset.process()
        ids = [i["id"] for i in self.sv.images.list("test_data")["items"]]
        for k, iid in enumerate(ids):
            self.sv.analysis.score_uncertainty({"image_id": iid, "probabilities": [[0.5 + 0.04 * k, 0.5 - 0.04 * k]]})
        res = self.sv.al.select({"strategy": "entropy", "budget": 3, "seed": 1})
        self.assertEqual(res["selected_ids"][0], ids[0])              # most uncertain = highest entropy
        self.assertTrue(res["uncertainty_signals_available"])


class ActiveLearningTests(ServiceCase):
    def test_no_data(self):
        with self.assertRaises(DatasetUnavailableError) as cm:
            self.sv.al.select({"strategy": "random", "budget": 2})
        self.assertIn("Main dataset is not available", cm.exception.message)

    def test_test_data_selection_is_flagged(self):
        helpers.write_test_data_images(self.s.data_root, 12)
        self.ctx.dataset.process()
        r = self.sv.al.select({"strategy": "random", "budget": 4, "seed": 3})
        self.assertTrue(r["is_test_data"])
        self.assertIn("TEST DATA", r["warning"])
        self.assertEqual(len(r["selected"]), 4)
        r2 = self.sv.al.select({"strategy": "entropy", "budget": 4})
        self.assertEqual(r2["selected"], [])                         # no model -> nothing scored, nothing invented
        self.assertTrue(r2["notes"])
        rounds = self.sv.al.rounds()
        self.assertEqual(len(rounds), 2)
        self.assertTrue(all(x["is_test_data"] for x in rounds))
        tm = self.sv.al.task_manifest(r["round_id"], self.sv.images)
        self.assertEqual(tm["n_tasks"], 4)
        self.assertNotIn("predictions", tm["tasks"][0])
        self.assertTrue(tm["tasks"][0]["data"]["image"].startswith("http://localhost:8000/api/images/"))

    def test_split_test_images_never_selected(self):
        write_simulated_main_layout(self.s.data_root, 40)
        self.ctx.dataset.process()
        splits = json.loads((self.s.splits_dir / "dentex_splits.json").read_text())["assignments"]
        test_ids = {k for k, v in splits.items() if v == "test"}
        self.assertTrue(test_ids)
        # all synthetic main images are annotated -> pool is empty by definition (nothing unlabeled)
        r = self.sv.al.select({"strategy": "random", "budget": 5})
        self.assertEqual(r["selected"], [])
        self.assertFalse(set(r["selected_ids"]) & test_ids)

    def test_invalid_config(self):
        helpers.write_test_data_images(self.s.data_root, 12)
        self.ctx.dataset.process()
        with self.assertRaises(DentaMindError):
            self.sv.al.select({"strategy": "combined", "budget": -3})


class AnnotationServiceTests(ServiceCase):
    def test_import_approve_flow(self):
        out = self.sv.annotations.import_export(ls_export("a") + ls_export("b"))
        self.assertEqual(out["imported"], 2)
        with self.assertRaises(DentaMindError):
            self.sv.annotations.import_export([])
        with self.assertRaises(DentaMindError):
            self.sv.annotations.approve(["a"], "  ")                # reviewer required
        res = self.sv.annotations.approve(["a"], "Dr Q")
        self.assertEqual(res["version"]["n_images"], 1)
        ov = self.sv.annotations.overview()
        self.assertEqual(ov["counts"]["approved"], 1)
        self.assertEqual(ov["counts"]["submitted"], 1)
        self.assertIsNone(ov["counts"]["in_progress"])               # unknowable without Label Studio -> not invented
        self.assertFalse(ov["label_studio"]["reachable"])
        self.assertIn("manual workflow", ov["label_studio"]["message"])

    def test_push_without_key_explains(self):
        from dentexmodel.errors import ExternalServiceError
        with self.assertRaises(ExternalServiceError):
            self.sv.annotations.push_to_label_studio([], "t")


class ReportServiceTests(ServiceCase):
    def test_requires_evidence(self):
        with self.assertRaises(DentaMindError) as cm:
            self.sv.reports.generate({})
        self.assertEqual(cm.exception.code, "no_evidence")

    def test_generate_validate_review_export(self):
        out = self.sv.reports.generate({"image_id": "IMG1", "model_version": "m1", "mode": "auto",
                                        "findings": [{"tooth_fdi": 16, "label": "Caries", "probability": 0.8, "uncertainty": 0.2}]})
        self.assertTrue(out["validation"]["passed"])
        self.assertEqual(out["report"]["generated_by"], "template")        # no LLM configured
        rid = out["report"]["report_id"]
        self.assertEqual(self.sv.reports.get(rid)["report"]["status"], "unconfirmed_research_draft")
        rev = self.sv.reports.review(rid, "Dr Z")
        self.assertEqual(rev["status"], "reviewed_research_draft")
        body, mime = self.sv.reports.export(rid, "html")
        self.assertTrue(mime.startswith("text/html"))
        self.assertEqual(json.loads(self.sv.reports.export(rid, "json")[0])["report"]["report_id"], rid)
        with self.assertRaises(NotFoundError):
            self.sv.reports.get("nope")

    def test_llm_mode_without_config_is_explicit_error(self):
        from dentexmodel.errors import ExternalServiceError
        with self.assertRaises(ExternalServiceError):
            self.sv.reports.generate({"image_id": "I", "findings": [], "mode": "llm"})


class SystemTests(ServiceCase):
    def test_overview_has_no_invented_numbers(self):
        o = self.sv.system.overview()
        self.assertEqual((o["images_uploaded"], o["images_analyzed"], o["teeth_detected"], o["al_rounds"]), (0, 0, 0, 0))
        self.assertEqual(o["models"], [])
        self.assertIsNone(o["latest_metrics"])
        self.assertEqual(o["al_curves"], {})
        self.assertFalse(o["dataset"]["main_available"])
        self.assertIn("Main dataset is not available", o["dataset"]["message"])

    def test_health_and_settings_no_secrets(self):
        self.s.llm_api_key, self.s.label_studio_api_key = "SECRET-LLM", "SECRET-LS"
        h = self.sv.system.health(probes=False)
        self.assertEqual(h["backend"], "ok")
        blob = json.dumps(self.sv.system.settings()) + json.dumps(h)
        self.assertNotIn("SECRET", blob)
        diags = [d["message"] for d in self.sv.system.settings()["diagnostics"]]
        self.assertTrue(any("Main dataset is not available" in d for d in diags))

    def test_probe_unreachable(self):
        from backend.services.system import probe
        self.assertFalse(probe("http://127.0.0.1:1", 0.3)["reachable"])


class ExperimentTests(ServiceCase):
    def _add(self, id, strategy, budget, f1, ds="v1", test=0, seed=1):
        from dentexmodel.storage import jdump, now
        self.ctx.db.insert("experiments", {"id": id, "strategy": strategy, "dataset_version": ds, "model_version": "m", "budget": budget,
                                           "round": 1, "seed": seed, "duration_s": 1.0, "metrics_json": jdump({"classification": {"macro_f1": f1}}),
                                           "config_json": jdump({"seed": seed}), "status": "completed", "is_test_data": test, "created": now()})

    def test_series_and_compare(self):
        self._add("e1", "random", 100, 0.5); self._add("e2", "random", 200, 0.6); self._add("e3", "combined", 100, 0.55, ds="v2", seed=2)
        self._add("e4", "random", 100, 0.9, test=1)
        s = self.sv.experiments.series()["classification_macro_f1"]
        self.assertEqual([p["budget"] for p in s["random"]], [100, 200])
        self.assertNotIn(0.9, [p["value"] for p in s["random"]])      # test-data records are excluded from curves
        c = self.sv.experiments.compare(["e1", "e3"])
        self.assertTrue(any("dataset versions" in w for w in c["warnings"]))
        self.assertTrue(any("random seeds" in w for w in c["warnings"]))
        self.assertEqual(c["comparable_metrics"], ["classification_macro_f1"])
        self.assertTrue(any("TEST DATA" in w for w in self.sv.experiments.compare(["e4"])["warnings"]))


if __name__ == "__main__":
    unittest.main()
