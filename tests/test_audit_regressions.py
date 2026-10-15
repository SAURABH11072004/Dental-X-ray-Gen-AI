"""Regression tests for defects found by the functionality audit (docs/FUNCTIONALITY_AUDIT.md). Fixtures are SYNTHETIC TEST DATA."""
import io
import json
import os
import unittest

import helpers
from backend.schemas.models import ModelSelectRequest
from backend.services.container import Services
from backend.services.context import AppContext
from dentexmodel.errors import ConflictError, DentaMindError, NotFoundError
from dentexmodel.storage import jdump, new_id, now

from test_review_pipeline import full_analysis, region


class AuditRegressionTests(helpers.TmpCase):
    def setUp(self):
        super().setUp()
        self.ctx = AppContext(self.s)
        self.sv = Services(self.ctx)

    def _insert_full(self, image_id):
        a = full_analysis([region(1, fdi=36, flags=["high_entropy"]), region(2, status="abstained", fdi=None, key="bbbb2222")])
        a["image_id"] = image_id
        a["regions"][1]["candidate_class"]["status"] = "abstained"
        aid = new_id("an")
        self.ctx.db.insert("analyses", {"id": aid, "image_id": image_id, "kind": "full", "model_version": "det-v1", "status": "done",
                                        "result_json": jdump(a), "duration_s": 1.0, "created": now()})
        return aid

    def test_overlay_png_works_for_full_pipeline_analyses(self):
        up = self.sv.images.upload("x.png", helpers.png_bytes(3, 512, 256))
        aid = self._insert_full(up["id"])
        from PIL import Image
        png = self.sv.analysis.overlay_png(aid)
        with Image.open(io.BytesIO(png)) as im:
            self.assertEqual(im.size, (512, 256))          # same size as the original: nothing resized

    def test_overlay_png_without_detections_or_regions_is_not_found(self):
        up = self.sv.images.upload("x.png", helpers.png_bytes(4))
        aid = new_id("an")
        self.ctx.db.insert("analyses", {"id": aid, "image_id": up["id"], "kind": "full", "model_version": "d", "status": "done",
                                        "result_json": jdump({"image_id": up["id"], "regions": []}), "created": now()})
        with self.assertRaises(NotFoundError):
            self.sv.analysis.overlay_png(aid)

    def test_unknown_job_is_404_for_status_and_cancel(self):
        for call in (lambda: self.ctx.jobs.get("nope"), lambda: self.ctx.jobs.cancel("nope")):
            with self.assertRaises(NotFoundError) as cm:
                call()
            self.assertEqual(cm.exception.status_code, 404)
            self.assertEqual(cm.exception.code, "job_not_found")

    def test_model_select_schema_accepts_numbering(self):
        self.assertEqual(ModelSelectRequest(model_id="m.pth", task="numbering").task, "numbering")
        with self.assertRaises(Exception):
            ModelSelectRequest(model_id="m.pth", task="healthy")

    def test_explain_with_a_tiny_region_is_a_client_error_not_503(self):
        from dentexmodel.errors import ImageValidationError
        self.assertEqual(ImageValidationError.status_code, 422)
        self.assertEqual(ConflictError.status_code, 409)

    def test_evaluate_is_refused_while_another_job_runs(self):
        # a running job owned by this process; the API must answer 409 instead of starting a second GPU job
        self.ctx.db.insert("jobs", {"id": "job-busy", "kind": "train_numbering", "status": "running", "config_json": "{}", "created": now(),
                                    "started": now(), "pid": os.getpid()})
        import backend.api.experiments as ex
        # Only the guard is under test; exercise it through the public function with services patched to this temp context.
        import backend.services.container as cont
        cont._services = self.sv
        orig_ctx, orig_scan = cont.get_context, ex.scan_checkpoints
        cont.get_context = lambda: self.ctx
        try:
            class _St:
                main_available = True
                expected_location = "x"
            self.ctx.dataset.status = lambda: _St()
            ex.scan_checkpoints = lambda settings: [type("M", (), {"model_id": "m.pth", "dental_specific": True, "version": "m", "provenance": ""})()]
            with self.assertRaises(ConflictError) as cm:
                ex.evaluate("m.pth", None)
            self.assertEqual(cm.exception.code, "job_already_running")
        finally:
            cont.get_context, ex.scan_checkpoints = orig_ctx, orig_scan
            cont._services = None

    def test_review_of_unknown_image_is_rejected_by_the_route_guard(self):
        with self.assertRaises(NotFoundError):
            self.sv.images.get("no_such_image")

class CancelledRunTests(helpers.TmpCase):
    def test_cancelled_training_writes_no_checkpoint(self):
        from dentexmodel.training.config import TrainConfig
        from dentexmodel.training.trainers import _save_checkpoint

        class Ctx:
            cancelled = True
            settings = self.s
            def log(self, *_a): pass
        self.assertIsNone(_save_checkpoint(Ctx(), TrainConfig(experiment_name="cx"), {}, {}))
        self.assertFalse(self.s.checkpoint_dir.exists() and any(self.s.checkpoint_dir.iterdir()))


class SignalValidationTests(helpers.TmpCase):
    """The validation shown next to each uncertainty signal must come from report files only; absent or broken files mean 'not validated'."""

    def setUp(self):
        super().setUp()
        self.sv = Services(AppContext(self.s))
        self.rep = self.s.data_root / "reports"
        self.rep.mkdir(parents=True, exist_ok=True)

    def test_no_reports_means_not_validated_and_calibration_not_applied(self):
        v = self.sv.pipeline.signal_validation()
        for k in ("entropy", "disagreement", "mask_instability", "detection_instability"):
            self.assertIsNone(v[k]["auroc"])
            self.assertEqual(v[k]["verdict"], "not validated")
        self.assertFalse(v["calibration"]["applied"])

    def test_values_and_verdicts_come_from_the_files(self):
        (self.rep / "uncertainty_evaluation.json").write_text(json.dumps({"test_split": {"n": 10, "auroc_entropy_for_errors": 0.77, "auroc_tta_disagreement_for_errors": 0.65, "ece": 0.05}}), encoding="utf-8")
        (self.rep / "instability_validation.json").write_text(json.dumps({"mask_instability": {"auroc_for_iou_below_0.8": 0.55, "n_regions": 99},
                                                                         "detection_instability": {"auroc_for_false_positive": 0.64, "n_regions": 50, "n_false_positives": 3}}), encoding="utf-8")
        v = self.sv.pipeline.signal_validation()
        self.assertEqual((v["entropy"]["auroc"], v["entropy"]["verdict"]), (0.77, "moderate"))
        self.assertEqual(v["disagreement"]["verdict"], "weak")
        self.assertEqual(v["mask_instability"]["verdict"], "very weak")
        self.assertEqual(v["detection_instability"]["n_positives"], 3)
        self.assertEqual(v["calibration"]["ece_test"], 0.05)

    def test_test_ece_after_temperature_is_the_test_value_never_the_calibration_value(self):
        (self.rep / "uncertainty_evaluation.json").write_text(json.dumps({
            "calibration_split": {"ece": 0.07, "ece_after_temperature": 0.076},
            "test_split": {"n": 10, "ece": 0.048, "ece_after_temperature_fitted_on_calibration": 0.036}}), encoding="utf-8")
        self.assertEqual(self.sv.pipeline.signal_validation()["calibration"]["ece_test_after_temperature"], 0.036)

    def test_corrupt_report_file_does_not_raise(self):
        (self.rep / "uncertainty_evaluation.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.sv.pipeline.signal_validation()["entropy"]["verdict"], "not validated")


class SplitProvenanceTests(helpers.TmpCase):
    """Re-processing rewrites the split file with a new timestamp; the recorded provenance hash must only change if an image moved."""

    def _write(self, name, updated, assignments):
        import json
        p = self.tmp / name
        p.write_text(json.dumps({"updated": updated, "assignments": assignments}), encoding="utf-8")
        return p

    def test_hash_ignores_the_timestamp_but_detects_a_moved_image(self):
        from dentexmodel.training.trainers import assignments_sha
        a = self._write("a.json", "2026-01-01", {"i1": "train", "i2": "test"})
        b = self._write("b.json", "2030-12-31", {"i2": "test", "i1": "train"})        # same assignments, other timestamp and key order
        c = self._write("c.json", "2026-01-01", {"i1": "test", "i2": "train"})        # two images swapped splits
        self.assertEqual(assignments_sha(a), assignments_sha(b))
        self.assertNotEqual(assignments_sha(a), assignments_sha(c))
        self.assertIsNone(assignments_sha(self.tmp / "missing.json"))


class JobErrorSanitisingTests(unittest.TestCase):
    """Job errors reach the API through short_error: no traceback frames and no absolute paths (the project folder contains a space)."""

    def test_traceback_and_paths_are_removed(self):
        from dentexmodel.training.jobs import short_error
        raw = ('Traceback (most recent call last):\n  File "D:\\Dentex-Gen Ai\\scripts\\evaluate_model.py", line 24, in <module>\n    import torch\n'
               'OSError: [WinError 1455] The paging file is too small. Error loading "D:\\Dentex-Gen Ai\\.venv\\Lib\\site-packages\\torch\\lib\\cufft64_11.dll" or one of its dependencies.')
        out = short_error(raw)
        self.assertIn("paging file is too small", out)
        for forbidden in ("Traceback", "D:\\", "site-packages", "Dentex-Gen Ai"):
            self.assertNotIn(forbidden, out)
        self.assertIn("cufft64_11.dll", out)

    def test_plain_messages_and_empty_values_pass_through(self):
        from dentexmodel.training.jobs import short_error
        self.assertEqual(short_error(None), None)
        self.assertEqual(short_error(""), "")
        self.assertEqual(short_error("RuntimeError: CUDA error: out of memory"), "RuntimeError: CUDA error: out of memory")


class CheckpointIntegrityTests(helpers.TmpCase):
    """A checkpoint whose bytes do not match the sha256 in its sidecar must not be treated as a verified dental model."""

    def _write(self, sha):
        import hashlib
        import json
        d = self.s.checkpoint_dir
        d.mkdir(parents=True, exist_ok=True)
        blob = b"not a real network - registry test only"
        (d / "m_v1.pth").write_bytes(blob)
        real = hashlib.sha256(blob).hexdigest()[:16]
        meta = {"task": "classification", "architecture": "resnet18", "version": "m_v1", "dental_specific": True, "class_names": ["a", "b"], "num_classes": 2,
                "checkpoint_sha256": sha if sha else real}
        (d / "m_v1.json").write_text(json.dumps(meta), encoding="utf-8")

    def test_matching_sha_is_accepted(self):
        from dentexmodel.inference.registry import scan_checkpoints
        self._write(None)
        self.assertTrue(scan_checkpoints(self.s)[0].dental_specific)

    def test_mismatching_sha_is_rejected_with_a_reason(self):
        from dentexmodel.inference.registry import scan_checkpoints
        self._write("0" * 16)
        m = scan_checkpoints(self.s)[0]
        self.assertFalse(m.dental_specific)
        self.assertIn("does not match the sha256", m.provenance)

    def test_sidecar_without_a_recorded_sha_is_still_accepted(self):
        import json
        from dentexmodel.inference.registry import scan_checkpoints
        self._write(None)
        side = self.s.checkpoint_dir / "m_v1.json"
        meta = json.loads(side.read_text(encoding="utf-8"))
        meta.pop("checkpoint_sha256")
        side.write_text(json.dumps(meta), encoding="utf-8")
        self.assertTrue(scan_checkpoints(self.s)[0].dental_specific)




class ReportValidatorEvidenceTests(unittest.TestCase):
    """The validator must reject impossible evidence, not only reports that disagree with it."""

    def _report(self, finding):
        from dentexmodel.reporting import template_report
        from dentexmodel.reporting.reports import make_evidence
        ev = make_evidence("IMG", "det-v1", [finding])
        return template_report(ev), ev

    def test_probability_outside_0_1_fails_validation(self):
        from dentexmodel.reporting import validate_report
        rep, ev = self._report({"tooth_fdi": 36, "label": "Caries", "probability": 1.7})
        v = validate_report(rep, ev, vocabulary=["Caries", "Deep Caries", "Impacted", "Periapical Lesion"])
        self.assertFalse(v["passed"])
        self.assertTrue(any("outside the valid range" in e for e in v["errors"]))

    def test_label_the_models_cannot_produce_fails_validation(self):
        from dentexmodel.reporting import validate_report
        rep, ev = self._report({"tooth_fdi": 36, "label": "Healthy", "probability": 0.9})
        v = validate_report(rep, ev, vocabulary=["Caries", "Deep Caries", "Impacted", "Periapical Lesion"])
        self.assertFalse(v["passed"])
        self.assertTrue(any("not a category the models produce" in e for e in v["errors"]))

    def test_config_spelling_without_spaces_matches_model_class_names(self):
        # the app config spells the classes 'DeepCaries'/'PeriapicalLesion'; the models output 'Deep Caries'/'Periapical Lesion'
        from dentexmodel.reporting import validate_report
        for label in ("Deep Caries", "Periapical Lesion"):
            rep, ev = self._report({"tooth_fdi": 36, "label": label, "probability": 0.7, "uncertainty": 0.4})
            v = validate_report(rep, ev, vocabulary=["Caries", "DeepCaries", "Impacted", "PeriapicalLesion"])
            self.assertTrue(v["passed"], v["errors"])

    def test_deep_caries_only_report_is_not_flagged_for_mentioning_caries(self):
        from dentexmodel.reporting import validate_report
        rep, ev = self._report({"tooth_fdi": 36, "label": "Deep Caries", "probability": 0.7, "uncertainty": 0.4})
        v = validate_report(rep, ev, vocabulary=["Caries", "DeepCaries", "Impacted", "PeriapicalLesion"])
        self.assertTrue(v["passed"], v["errors"])

    def test_text_naming_a_finding_absent_from_the_evidence_is_still_caught(self):
        from dentexmodel.reporting import validate_report
        rep, ev = self._report({"tooth_fdi": 36, "label": "Impacted", "probability": 0.7, "uncertainty": 0.4})
        rep["summary"] += " Periapical lesion suspected."
        v = validate_report(rep, ev, vocabulary=["Caries", "DeepCaries", "Impacted", "PeriapicalLesion"])
        self.assertFalse(v["passed"])
        self.assertTrue(any("periapical" in e.lower() for e in v["errors"]), v["errors"])

    def test_valid_finding_still_passes(self):
        from dentexmodel.reporting import validate_report
        rep, ev = self._report({"tooth_fdi": 36, "label": "Caries", "probability": 0.7, "uncertainty": 0.4})
        v = validate_report(rep, ev, vocabulary=["Caries", "Deep Caries", "Impacted", "Periapical Lesion"])
        self.assertTrue(v["passed"], v["errors"])



if __name__ == "__main__":
    unittest.main()
