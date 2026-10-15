"""Dataset layer + pipeline tests. ``simulate_main`` lays SYNTHETIC TEST DATA out like the real dataset inside a
temp dir so the 'main dataset present' code paths can be exercised; it is never the real dataset."""
import json
import unittest

import helpers
from dentexmodel.data import splits as sp
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.discovery import discover
from dentexmodel.data.manifest import build_manifest
from dentexmodel.data.synthetic import write_simulated_main_layout, write_synthetic_dataset
from dentexmodel.data.validation import check_split_leakage, validate_dataset
from dentexmodel.pipeline import Pipeline


class DiscoveryTests(helpers.TmpCase):
    def test_missing_data_dir_message(self):
        import shutil
        shutil.rmtree(self.s.data_root)
        st = discover(self.s)
        self.assertEqual(st.state, "missing")
        self.assertFalse(st.main_available)
        self.assertIn("Main dataset is not available. Please place the dataset in", st.messages[0])

    def test_empty_data_dir(self):
        st = discover(self.s)
        self.assertEqual(st.state, "missing")
        self.assertIn("Please place the dataset", " ".join(st.messages))

    def test_unlabeled_images_are_test_data_only(self):
        helpers.write_test_data_images(self.s.data_root, 6)
        st = discover(self.s)
        self.assertEqual(st.state, "test_data_only")
        self.assertFalse(st.main_available)
        self.assertEqual(st.test_image_count, 6)
        self.assertTrue(st.sources[0]["is_test_data"])
        self.assertEqual(st.sources[0]["role"], "unlabeled")

    def test_synthetic_fixture_dir_is_never_main(self):
        write_synthetic_dataset(self.s.data_root, 6)
        self.assertEqual(discover(self.s).state, "missing")

    def test_real_layout_is_detected_automatically_when_added(self):
        helpers.write_test_data_images(self.s.data_root, 6)
        self.assertEqual(discover(self.s).state, "test_data_only")
        write_simulated_main_layout(self.s.data_root, 24)  # "the dataset appears"
        st = discover(self.s)
        self.assertEqual(st.state, "main_available")
        self.assertTrue(st.main_available)

    def test_images_without_annotation_file_are_not_main(self):
        helpers.write_test_data_images(self.s.data_root, 6, subdir="training_data/quadrant_enumeration_disease/xrays")
        self.assertEqual(discover(self.s).state, "test_data_only")

    def test_data_folder_case_variants(self):
        """A Windows-style ``Data`` folder is found when no lower-case ``data`` exists."""
        import shutil
        from dentexmodel.config import get_settings
        shutil.rmtree(self.s.data_root)
        (self.tmp / "Data").mkdir()
        self.assertEqual(get_settings(self.tmp, load_env=False).data_root.name, "Data")


class ProcessingTests(helpers.TmpCase):
    def setUp(self):
        super().setUp()
        write_simulated_main_layout(self.s.data_root, 24)
        self.svc = DatasetService(self.s)

    def test_process_outputs_and_cache(self):
        res = self.svc.process()
        self.assertTrue(res["main_available"])
        self.assertEqual(res["main"]["n_images"], 24)
        self.assertTrue(res["main"]["validation_ok"])
        self.assertEqual(sum(res["main"]["split_counts"].values()), 24)
        self.assertGreater(res["main"]["split_counts"]["test"], 0)
        self.assertTrue((self.s.processed_dir / "manifest.json").is_file())
        self.assertTrue((self.s.processed_dir / "manifest.csv").is_file())
        self.assertTrue((self.s.splits_dir / "dentex_splits.json").is_file())
        self.assertTrue(self.svc.process()["cached"])
        self.assertFalse(self.svc.process(force=True)["cached"])

    def test_manifest_fields(self):
        rows = self.svc.manifest("main")
        r = rows[0]
        for f in ("image_id", "file_path", "dataset_source", "annotation_level", "width", "height", "tooth_ids", "labels", "has_masks", "split", "annotation_status"):
            self.assertTrue(hasattr(r, f), f)
        self.assertEqual(r.annotation_level, "quadrant_enumeration_disease")
        self.assertNotIn("\\", r.file_path)
        self.assertFalse(r.file_path.startswith("/"))
        self.assertTrue(all(11 <= t <= 48 for row in rows for t in row.tooth_ids))

    def test_splits_are_stable_and_test_never_moves(self):
        self.svc.process()
        first = json.loads((self.s.splits_dir / "dentex_splits.json").read_text())["assignments"]
        rows = self.svc.manifest("main")
        again = sp.assign_splits(rows, 42, {"train": .7, "val": .1, "calibration": .1, "test": .1}, existing=first)
        self.assertEqual(first, again)
        # adding images does not reshuffle existing ones
        extra = rows + [type(rows[0])(**{**rows[0].__dict__, "image_id": f"new_{i}"}) for i in range(10)]
        grown = sp.assign_splits(extra, 42, {"train": .7, "val": .1, "calibration": .1, "test": .1}, existing=first)
        self.assertTrue(all(grown[k] == v for k, v in first.items()))

    def test_fractions_validated(self):
        with self.assertRaises(Exception):
            sp.validate_fractions({"train": .5, "val": .1, "calibration": .1, "test": .1})

    def test_patient_groups_not_split(self):
        rows = self.svc.manifest("main")
        for i, r in enumerate(rows):
            r.patient_id = f"P{i // 3}"
        a = sp.assign_splits(rows, 1, {"train": .6, "val": .2, "calibration": 0.0, "test": .2})
        by_patient = {}
        for r in rows:
            by_patient.setdefault(r.patient_id, set()).add(a[r.image_id])
        self.assertTrue(all(len(v) == 1 for v in by_patient.values()))
        self.assertEqual(check_split_leakage(rows, a), [])

    def test_leakage_detection(self):
        rows = self.svc.manifest("main")
        for r in rows[:4]:
            r.patient_id = "P0"
        bad = {r.image_id: "train" for r in rows}
        bad[rows[0].image_id] = "test"
        issues = check_split_leakage(rows, bad)
        self.assertTrue(any("patient/group 'P0'" in i.message for i in issues))

    def test_validation_detects_injected_problems(self):
        status = self.svc.status()
        ann_path = self.s.data_root / status.sources[0]["annotation_file"]
        coco = json.loads(ann_path.read_text())
        coco["annotations"][0]["bbox"] = [10, 10, -5, 20]                      # invalid box
        coco["annotations"][1]["bbox"] = [10, 10, 10000, 20]                   # outside image
        coco["annotations"][2]["category_id_3"] = 99                           # unsupported label
        coco["annotations"][3]["category_id_2"] = 99                           # unsupported enumeration -> unsupported + invalid fdi
        coco["images"].append({"id": 999, "file_name": "ghost.png", "width": 512, "height": 256})  # missing image
        coco["images"][1]["width"] = 1111                                       # dimension mismatch
        ann_path.write_text(json.dumps(coco))
        (self.s.data_root / status.sources[0]["images_dir"] / "synth_2.png").write_bytes(b"not an image")  # corrupt
        status = self.svc.status()
        rows = build_manifest(self.s, status)
        rows.append(type(rows[0])(**{**rows[0].__dict__}))                      # duplicate id
        rep = validate_dataset(self.s, status, rows)
        for code in ("invalid_box", "unsupported_label", "invalid_fdi", "missing_image", "corrupt_image", "duplicate_image_id", "dimension_mismatch"):
            self.assertIn(code, rep.counts, code)
        self.assertFalse(rep.ok)

    def test_missing_masks_is_info_not_error(self):
        status = self.svc.status()
        rep = validate_dataset(self.s, status, self.svc.manifest("main"))
        self.assertEqual(rep.severities.get("missing_masks", "info"), "info")
        self.assertTrue(rep.ok)

    def test_corrupt_coco_is_reported_not_crashing(self):
        status = self.svc.status()
        (self.s.data_root / status.sources[0]["annotation_file"]).write_text("{not json")
        st = discover(self.s)
        self.assertFalse(st.main_available)
        self.assertTrue(any("Ignoring" in m for m in st.messages))


class TestDataModeTests(helpers.TmpCase):
    def test_test_data_processing_is_labelled(self):
        helpers.write_test_data_images(self.s.data_root, 12)
        res = DatasetService(self.s).process()
        self.assertEqual(res["state"], "test_data_only")
        self.assertNotIn("main", res)
        self.assertTrue(res["test_data"]["is_test_data"])
        self.assertTrue((self.s.splits_dir / "test_data_splits.json").is_file())
        self.assertFalse((self.s.splits_dir / "dentex_splits.json").exists())
        payload = json.loads((self.s.splits_dir / "test_data_splits.json").read_text())
        self.assertIn("TEST DATA", payload["purpose"])
        rows = DatasetService(self.s).manifest("auto")
        self.assertTrue(all(r.is_test_data and r.annotation_status == "unlabeled" and r.annotation_level == "none" for r in rows))

    def test_few_images_skip_splits(self):
        helpers.write_test_data_images(self.s.data_root, 4)
        res = DatasetService(self.s).process()
        self.assertTrue(any("splits not created" in n for n in res["notes"]))


class PipelineTests(helpers.TmpCase):
    def test_no_data(self):
        rep = Pipeline(self.s).run()
        self.assertEqual(rep["mode"], "no_data")
        self.assertIn("Please place the dataset", rep["notice"])
        self.assertTrue(rep["ok"])
        self.assertTrue((self.s.results_dir / "pipeline_report.json").is_file())

    def test_test_data_smoke(self):
        helpers.write_test_data_images(self.s.data_root, 12)
        rep = Pipeline(self.s).run()
        self.assertEqual(rep["mode"], "test_data_smoke")
        self.assertTrue(rep["ok"], rep["failed_steps"])
        by = {s["step"]: s for s in rep["steps"]}
        self.assertEqual(by["image_stats"]["details"]["computed"], 12)
        self.assertEqual(by["inference"]["status"], "skipped")        # no checkpoint -> no fabricated predictions
        self.assertIn("No synthetic predictions", by["inference"]["message"])
        self.assertEqual(by["uncertainty"]["status"], "skipped")
        self.assertEqual(by["evaluation"]["status"], "skipped")
        self.assertIn("TEST DATA", rep["notice"])
        self.assertEqual(by["active_learning_dry_run"]["details"]["strategy"], "random")
        tp = by["training_prerequisites"]["details"]["classification"]
        self.assertFalse(tp["ready"])
        self.assertEqual(tp["unmet"][0]["code"], "main_dataset_missing")

    def test_main_mode(self):
        write_simulated_main_layout(self.s.data_root, 24)
        rep = Pipeline(self.s).run()
        self.assertEqual(rep["mode"], "main_dataset")
        self.assertTrue(rep["ok"], rep["failed_steps"])

    def test_pipeline_survives_corrupt_image(self):
        d = helpers.write_test_data_images(self.s.data_root, 12)
        (d / "val_3.png").write_bytes(b"garbage")
        rep = Pipeline(self.s).run()
        by = {s["step"]: s for s in rep["steps"]}
        self.assertIn("val_3", by["image_stats"]["details"]["errors"])
        self.assertEqual(by["image_stats"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
