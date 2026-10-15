import json
import time
import unittest
from unittest import mock

import helpers
from dentexmodel.data.synthetic import write_simulated_main_layout
from dentexmodel.errors import ConfigError, DentaMindError, ModelUnavailableError
from dentexmodel.inference.registry import active_model, scan_checkpoints, set_active
from dentexmodel.inference.system import gpu_info
from dentexmodel.storage import Database
from dentexmodel.training import JobManager, TrainConfig, check_prerequisites


class TrainConfigTests(unittest.TestCase):
    def test_valid_default(self):
        self.assertEqual(TrainConfig().validate(), [])

    def test_invalid_values(self):
        bad = TrainConfig(task="classification", architecture="vgg", experiment_name="a b", epochs=0, batch_size=0, learning_rate=0,
                          image_size=1, device="tpu")
        self.assertEqual(len(bad.validate()), 7)
        with self.assertRaises(ConfigError):
            bad.assert_valid()
        self.assertTrue(TrainConfig(experiment_name="../x").validate())


class PrerequisiteTests(helpers.TmpCase):
    def test_missing_dataset_message(self):
        pre = check_prerequisites(self.s, TrainConfig())
        self.assertFalse(pre["ready"])
        u = {x["code"]: x for x in pre["unmet"]}
        self.assertIn("main_dataset_missing", u)
        self.assertIn("Main dataset is not available", u["main_dataset_missing"]["message"])
        self.assertIn("Place the dataset in", u["main_dataset_missing"]["fix"])

    def test_test_data_does_not_satisfy_prerequisites(self):
        helpers.write_test_data_images(self.s.data_root, 12)
        self.assertIn("main_dataset_missing", [x["code"] for x in check_prerequisites(self.s, TrainConfig())["unmet"]])

    def test_with_main_dataset_only_missing_torch_remains(self):
        write_simulated_main_layout(self.s.data_root, 24)
        pre = check_prerequisites(self.s, TrainConfig(task="classification"))
        codes = [x["code"] for x in pre["unmet"]]
        self.assertNotIn("main_dataset_missing", codes)
        self.assertNotIn("no_training_labels", codes)
        pre_seg = check_prerequisites(self.s, TrainConfig(task="segmentation", architecture="maskrcnn_resnet50_fpn"))
        self.assertNotIn("no_masks", [x["code"] for x in pre_seg["unmet"]])  # synthetic fixture has some polygons

    def test_approved_annotations_required_when_requested(self):
        write_simulated_main_layout(self.s.data_root, 24)
        pre = check_prerequisites(self.s, TrainConfig(use_approved_annotations=True))
        self.assertIn("no_approved_annotations", [x["code"] for x in pre["unmet"]])


class JobManagerTests(helpers.TmpCase):
    """Exercises job plumbing with an injected dummy trainer. The dummy reports whatever the test passes - this
    verifies persistence/cancellation/error handling, it is NOT a model-training result."""

    def _mgr(self, trainer):
        return JobManager(self.s, Database(self.s.db_path), trainer=trainer)

    def _wait(self, mgr, jid):
        for _ in range(100):
            j = mgr.get(jid)
            if j["status"] not in ("queued", "running"):
                return j
            time.sleep(0.05)
        self.fail("job did not finish")

    def test_start_refused_without_prerequisites(self):
        with self.assertRaises(DentaMindError) as cm:
            self._mgr(lambda c, x: {}).start(TrainConfig())
        self.assertEqual(cm.exception.code, "prerequisites_unmet")
        self.assertTrue(cm.exception.details["unmet"])

    def test_success_failure_cancel(self):
        ready = {"ready": True, "unmet": []}
        with mock.patch("dentexmodel.training.jobs.check_prerequisites", return_value=ready):
            def ok(cfg, ctx):
                ctx.progress(1, cfg.epochs, {"train_loss": 1.5})
                return {"checkpoint": "x.pth", "metrics": {"classification": {"macro_f1": 0.5}}, "duration_s": 0.1}
            m = self._mgr(ok)
            j = self._wait(m, m.start(TrainConfig(epochs=3))["id"])
            self.assertEqual(j["status"], "succeeded")
            self.assertEqual(j["metrics"]["history"][0]["train_loss"], 1.5)
            self.assertEqual(len(m.db.list("experiments")), 1)

            def boom(cfg, ctx):
                raise RuntimeError("kaput")
            m2 = self._mgr(boom)
            j2 = self._wait(m2, m2.start(TrainConfig())["id"])
            self.assertEqual(j2["status"], "failed")
            self.assertIn("kaput", j2["error"])
            self.assertEqual(len(m2.db.list("experiments")), 2 - 1)  # failure records no experiment

            def slow(cfg, ctx):
                while not ctx.cancelled:
                    time.sleep(0.01)
                return {}
            m3 = self._mgr(slow)
            jid = m3.start(TrainConfig())["id"]
            time.sleep(0.1)
            m3.cancel(jid)
            self.assertEqual(self._wait(m3, jid)["status"], "cancelled")

    def test_stale_running_jobs_marked_interrupted(self):
        db = Database(self.s.db_path)
        db.insert("jobs", {"id": "old", "kind": "t", "status": "running", "created": "x"})
        JobManager(self.s, db)
        self.assertEqual(db.get("jobs", "old")["status"], "interrupted")


class RegistryTests(helpers.TmpCase):
    def _ckpt(self, name, meta=None):
        p = self.s.checkpoint_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\0" * 1024)
        if meta is not None:
            p.with_suffix(".json").write_text(json.dumps(meta))
        return p

    def test_empty_registry_no_fake_entries(self):
        self.assertEqual(scan_checkpoints(self.s), [])
        with self.assertRaises(ModelUnavailableError) as cm:
            active_model(self.s, "detection")
        self.assertEqual(cm.exception.code, "no_checkpoint")
        self.assertIn("configs/models.yaml", cm.exception.hint)

    def test_unverified_checkpoint_is_not_dental(self):
        self._ckpt("resnet50_imagenet.pth")
        (m,) = scan_checkpoints(self.s)
        self.assertFalse(m.dental_specific)
        self.assertIn("unverified", m.provenance)
        self.assertNotIn("path", m.to_dict())
        with self.assertRaises(ModelUnavailableError):
            active_model(self.s, "classification")
        with self.assertRaises(ModelUnavailableError) as cm:
            set_active(self.s, "classification", "resnet50_imagenet.pth")
        self.assertEqual(cm.exception.code, "unverified_checkpoint")

    def test_dental_sidecar_activation(self):
        self._ckpt("det_v1.pth", {"task": "detection", "dental_specific": True, "version": "det-v1", "architecture": "fasterrcnn_resnet50_fpn"})
        self._ckpt("det_v2.pth", {"task": "detection", "dental_specific": True, "version": "det-v2"})
        self.assertEqual(len([m for m in scan_checkpoints(self.s) if m.dental_specific]), 2)
        with self.assertRaises(ModelUnavailableError) as cm:
            active_model(self.s, "detection")                      # ambiguous -> must choose
        self.assertEqual(cm.exception.code, "model_not_selected")
        set_active(self.s, "detection", "det_v2.pth")
        self.assertEqual(active_model(self.s, "detection").version, "det-v2")
        with self.assertRaises(ModelUnavailableError):
            set_active(self.s, "segmentation", "det_v1.pth")       # wrong task
        with self.assertRaises(ModelUnavailableError):
            set_active(self.s, "detection", "missing.pth")

    def test_single_checkpoint_auto_selected(self):
        self._ckpt("only.pth", {"task": "segmentation", "dental_specific": True})
        self.assertEqual(active_model(self.s, "segmentation").model_id, "only.pth")

    def test_bad_sidecar_json_ignored(self):
        p = self._ckpt("x.pth")
        p.with_suffix(".json").write_text("{bad")
        self.assertFalse(scan_checkpoints(self.s)[0].dental_specific)

    def test_torch_wrappers_fail_cleanly_without_torch_or_checkpoint(self):
        import numpy as np
        from dentexmodel.inference.torch_models import detect_teeth
        with self.assertRaises(ModelUnavailableError):
            detect_teeth(np.zeros((8, 8, 3), np.float32), "x", self.s)

    def test_gpu_info_shape(self):
        g = gpu_info()
        self.assertIn("cuda_available", g)
        self.assertIsInstance(g["cuda_available"], bool)


if __name__ == "__main__":
    unittest.main()
