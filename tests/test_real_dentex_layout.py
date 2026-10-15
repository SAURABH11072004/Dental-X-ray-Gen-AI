"""Regression tests for the layout of the real DENTEX download: sub-sets that re-use file names for different
radiographs, the same radiograph stored in several sub-sets, and unlabeled folders that overlap labeled ones.
Images are SYNTHETIC test fixtures."""
import json
import unittest
from pathlib import Path

import helpers
from PIL import Image
from dentexmodel.data.dataset import DatasetService
from dentexmodel.inference.registry import scan_checkpoints, validate_sidecar

N = 12


def _png(path: Path, seed: int, w=96, h=64):
    path.parent.mkdir(parents=True, exist_ok=True)
    import numpy as np
    Image.fromarray(np.random.default_rng(seed).integers(0, 255, (h, w), dtype=np.uint8), mode="L").save(path)   # unique per seed


def _coco(names, with_disease: bool):
    images = [{"id": i + 1, "file_name": n, "width": 96, "height": 64} for i, n in enumerate(names)]
    anns = []
    for i in range(len(names)):
        a = {"id": i + 1, "image_id": i + 1, "bbox": [10, 10, 20, 20], "segmentation": [[10, 10, 30, 10, 30, 30, 10, 30]],
             "area": 400, "iscrowd": 0, "category_id_1": 0, "category_id_2": 0}
        if with_disease:
            a["category_id_3"] = 1
        anns.append(a)
    cats = {"categories_1": [{"id": 0, "name": "1"}], "categories_2": [{"id": 0, "name": "1"}]}
    if with_disease:
        cats["categories_3"] = [{"id": 1, "name": "Caries"}]
    return {"images": images, "annotations": anns, **cats}


class RealLayoutTests(helpers.TmpCase):
    def build(self):
        d = self.s.data_root / "training_data"
        names = [f"train_{i}.png" for i in range(N)]
        for sub, seed0, disease in (("quadrant_enumeration", 0, False), ("quadrant-enumeration-disease", 100, True)):
            for i, n in enumerate(names):          # same names, DIFFERENT pixels, in the two sub-sets
                _png(d / sub / "xrays" / n, seed0 + i)
            fn = "train_quadrant_enumeration_disease.json" if disease else "train_quadrant_enumeration.json"
            (d / sub / fn).write_text(json.dumps(_coco(names, disease)))
        # a third folder: radiographs identical to the first sub-set's, stored under other names, unlabeled
        for i in range(3):
            _png(d / "unlabelled" / "xrays" / f"other_{i}.png", i)
        # unlabeled validation images, one of which duplicates a training radiograph
        v = self.s.data_root / "validation_data" / "quadrant_enumeration_disease" / "xrays"
        _png(v / "val_0.png", 1)
        for i in range(1, 5):
            _png(v / f"val_{i}.png", 500 + i)
        return DatasetService(self.s)

    def test_same_file_name_in_two_subsets_gets_unique_ids(self):
        svc = self.build()
        svc.process(force=True, deep_validation=False)
        rows = svc.manifest("main")
        ids = [r.image_id for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any(i.startswith("qed_") for i in ids) and any(i.startswith("qe_") for i in ids))

    def test_no_false_duplicate_or_dimension_errors(self):
        svc = self.build()
        res = svc.process(force=True, deep_validation=False)
        counts = res["main"]["issue_counts"]
        self.assertNotIn("duplicate_image_id", counts)
        self.assertNotIn("dimension_mismatch", counts)
        self.assertTrue(res["main"]["validation_ok"])

    def test_identical_radiographs_share_a_split_and_unlabeled_copies_are_flagged(self):
        svc = self.build()
        svc.process(force=True, deep_validation=False)
        rows = svc.manifest("main")
        by_hash = {}
        for r in rows:
            if r.annotation_status == "annotated":
                by_hash.setdefault(r.content_hash, set()).add(r.split)
        self.assertTrue(all(len(v) == 1 for v in by_hash.values()))
        unl = [r for r in rows if r.dataset_source.endswith("unlabelled")]
        self.assertEqual({r.split for r in unl}, {"unassigned"})          # never train/val/test examples
        self.assertTrue(all(r.duplicate_of for r in unl))                  # all three copy labeled radiographs

    def test_unlabeled_validation_data_is_not_split_when_main_exists(self):
        svc = self.build()
        svc.process(force=True, deep_validation=False)
        test_rows = svc.manifest("test_data")
        self.assertEqual({r.split for r in test_rows}, {"unassigned"})
        self.assertEqual([r.image_id for r in test_rows if r.duplicate_of], ["val_0"])

    def test_only_annotated_images_are_split(self):
        svc = self.build()
        res = svc.process(force=True, deep_validation=False)
        self.assertEqual(sum(res["main"]["split_counts"].values()), 2 * N)


class SidecarValidationTests(helpers.TmpCase):
    def test_inconsistent_class_count_is_rejected(self):
        self.assertTrue(validate_sidecar({"task": "detection", "class_names": ["tooth"], "num_classes": 5}))
        self.assertFalse(validate_sidecar({"task": "detection", "class_names": ["tooth"], "num_classes": 2}))
        self.assertTrue(validate_sidecar({"task": "classification", "class_names": ["a", "b"], "num_classes": 3}))
        self.assertTrue(validate_sidecar({"task": "detection", "architecture": "not_a_model"}))
        self.assertTrue(validate_sidecar({"task": "nonsense"}))

    def test_registry_marks_bad_sidecar_as_not_dental(self):
        d = self.s.checkpoint_dir
        d.mkdir(parents=True, exist_ok=True)
        (d / "bad.pth").write_bytes(b"x")
        (d / "bad.json").write_text(json.dumps({"task": "detection", "dental_specific": True, "class_names": ["tooth"], "num_classes": 9}))
        (d / "good.pth").write_bytes(b"x")
        (d / "good.json").write_text(json.dumps({"task": "detection", "dental_specific": True, "class_names": ["tooth"], "num_classes": 2}))
        m = {x.model_id: x for x in scan_checkpoints(self.s)}
        self.assertFalse(m["bad.pth"].dental_specific)
        self.assertIn("rejected", m["bad.pth"].provenance)
        self.assertTrue(m["good.pth"].dental_specific)


class NumberingGateTests(helpers.TmpCase):
    BASE = {"task": "numbering", "architecture": "fasterrcnn_resnet50_fpn", "dental_specific": True, "label_mode": "fdi",
            "fdi_codes": [11, 12], "class_names": ["11", "12"], "num_classes": 3}

    def _write(self, name, meta):
        d = self.s.checkpoint_dir
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.pth").write_bytes(b"x")
        (d / f"{name}.json").write_text(json.dumps(meta))

    def test_numbering_checkpoint_is_registered_only_after_a_passing_evaluation(self):
        self._write("pending", dict(self.BASE))
        self._write("failed", {**self.BASE, "evaluated_on": {"passed": False, "gate": "g"}})
        self._write("good", {**self.BASE, "evaluated_on": {"passed": True, "gate": "g"}})
        self._write("not_fdi", {**self.BASE, "label_mode": "tooth", "evaluated_on": {"passed": True}})
        m = {x.model_id: x for x in scan_checkpoints(self.s)}
        self.assertFalse(m["pending.pth"].dental_specific)
        self.assertIn("not registered yet", m["pending.pth"].provenance)
        self.assertFalse(m["failed.pth"].dental_specific)
        self.assertTrue(m["good.pth"].dental_specific)
        self.assertFalse(m["not_fdi.pth"].dental_specific)       # ordinary tooth boxes are not FDI labels

    def test_resolve_numbering_gives_one_box_per_number_and_drops_duplicate_boxes(self):
        try:
            import torch  # noqa: F401
        except ImportError:
            self.skipTest("torch not installed")
        from dentexmodel.training.trainers import resolve_numbering
        boxes = [[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60], [100, 0, 110, 10]]
        scores = [0.9, 0.8, 0.7, 0.2]            # same tooth predicted twice with different numbers; last one below threshold
        labels = [3, 4, 3, 5]
        keep = resolve_numbering(boxes, scores, labels, nms_iou=0.5, min_score=0.3)
        self.assertIn(0, keep)
        self.assertNotIn(1, keep)                  # overlapping lower-scoring duplicate removed
        self.assertNotIn(3, keep)                  # below the score threshold
        # number 3 is predicted by boxes 0 and 2: only the higher-scoring one may keep it
        self.assertEqual(sum(1 for i in keep if labels[i] == 3), 1)


class JobOwnershipTests(helpers.TmpCase):
    def test_restart_only_interrupts_jobs_whose_owner_is_dead(self):
        import subprocess
        import sys
        from dentexmodel.storage import Database, now
        from dentexmodel.training.jobs import JobManager
        db = Database(self.s.db_path)
        live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            for jid, pid in (("job-live", live.pid), ("job-dead", 2_000_000_000), ("job-legacy", None)):
                db.insert("jobs", {"id": jid, "kind": "train_x", "status": "running", "created": now(), "pid": pid})
            JobManager(self.s, db)          # what the API does on start-up
            st = {j["id"]: j["status"] for j in db.list("jobs")}
            self.assertEqual(st["job-live"], "running")           # CLI run owned by a live process is left alone
            self.assertEqual(st["job-dead"], "interrupted")
            self.assertEqual(st["job-legacy"], "interrupted")     # no owner recorded -> cannot be proven alive
        finally:
            live.kill()
            live.wait()


if __name__ == "__main__":
    unittest.main()
