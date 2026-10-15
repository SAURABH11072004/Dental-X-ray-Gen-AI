"""Regression tests for the split-leakage audit (scripts/check_leakage.py -> dentexmodel.data.leakage) and the review-to-training
path it guards. Fixtures are SYNTHETIC TEST DATA laid out like the real dataset in a temp dir."""
import hashlib
import shutil
import unittest

import helpers
from dentexmodel.annotation.reviews import ReviewStore
from dentexmodel.data import splits as sp
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.leakage import split_checks, summarize
from dentexmodel.data.manifest import ManifestRow, _link_duplicates
from dentexmodel.data.synthetic import write_simulated_main_layout
from dentexmodel.storage import Database, jdump, new_id, now
from dentexmodel.training.trainers import TASK_LEVEL

FR = {"train": .7, "val": .1, "calibration": .1, "test": .1}


def row(image_id, h, level="quadrant_enumeration", status="annotated", test_data=False, source="s"):
    return ManifestRow(image_id=image_id, file_path=f"{source}/{image_id}.png", dataset_source=source, annotation_level=level,
                       width=100, height=50, annotation_status=status, is_test_data=test_data, content_hash=h)


def check(out, prefix):
    return next(c for c in out["checks"] if c["check"].startswith(prefix))


class SplitCheckTests(unittest.TestCase):
    def setUp(self):
        self.rows = [row(f"a{i}", f"h{i}") for i in range(8)]
        self.assign = {"a0": "train", "a1": "train", "a2": "train", "a3": "train", "a4": "val", "a5": "calibration", "a6": "test", "a7": "test"}

    def test_clean_splits_pass_every_check(self):
        out = split_checks(self.rows, [row("v0", "hX", status="unlabeled", test_data=True)], self.assign, TASK_LEVEL, set())
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["checks"]), 6 + 2 * len(TASK_LEVEL) + 3)        # 17 original checks + review-training check
        self.assertEqual(summarize(out["checks"])["unresolved"], [])

    def test_validation_data_copy_of_a_test_film_is_a_visible_warning_not_a_pass(self):
        """The check that failed on the real data (3 validation_data files identical to test radiographs)."""
        vd = [row("val_4", "h6", status="unlabeled", test_data=True), row("val_9", "h0", status="unlabeled", test_data=True)]
        out = split_checks(self.rows, vd, self.assign, TASK_LEVEL)
        c = check(out, "validation_data (unlabeled) vs test")
        self.assertEqual((c["overlap"], c["passed"], c["informational"], c["status"]), (1, False, True, "warning"))
        self.assertIn("val_4", c["note"])
        self.assertEqual(out["validation_data_identical_to_test"], ["val_4"])
        self.assertEqual(out["validation_data_identical_to_labeled"], 2)
        self.assertTrue(out["ok"])                                               # cannot affect a metric ...
        sm = summarize(out["checks"])
        self.assertEqual((sm["passed"], sm["failed"], sm["warnings"]), (sm["total"] - 1, 0, 1))   # ... but is never counted as passed
        self.assertEqual(sm["unresolved"][0]["status"], "warning")

    def test_same_radiograph_in_train_and_test_fails(self):
        rows = self.rows + [row("dup", "h6", level="quadrant_enumeration_disease", source="other")]   # copy of test film a6 in another sub-set
        out = split_checks(rows, [], {**self.assign, "dup": "train"}, TASK_LEVEL)
        self.assertFalse(out["ok"])
        self.assertEqual(check(out, "train vs test")["overlap"], 1)
        self.assertEqual(check(out, "classification: training images used")["overlap"], 1)
        self.assertGreaterEqual(summarize(out["checks"])["failed"], 2)

    def test_unlabeled_pool_copy_of_test_film_fails_unless_excluded(self):
        pool = row("p0", "h7", status="unlabeled")
        self.assertEqual(check(split_checks(self.rows + [pool], [], self.assign, TASK_LEVEL), "unlabeled pool")["overlap"], 1)
        pool.duplicate_of = "a7"
        self.assertEqual(check(split_checks(self.rows + [pool], [], self.assign, TASK_LEVEL), "unlabeled pool")["overlap"], 0)

    def test_review_training_items_identical_to_held_out_films_fail(self):
        for h, expect in (("h4", 1), ("h5", 1), ("h6", 1), ("h0", 0), ("new", 0)):    # val, calibration, test, train, unseen
            out = split_checks(self.rows, [], self.assign, TASK_LEVEL, {h})
            self.assertEqual(check(out, "approved-review training items")["overlap"], expect, h)


class GroupingTests(unittest.TestCase):
    def test_identical_pixels_across_dentex_subsets_always_share_a_split(self):
        rows = []
        for i in range(30):          # every radiograph exists in all three sub-sets under different ids
            for src, lvl in (("q", "quadrant"), ("qe", "quadrant_enumeration"), ("qed", "quadrant_enumeration_disease")):
                rows.append(row(f"{src}_{i}", hashlib.sha256(str(i).encode()).hexdigest(), level=lvl, source=src))
        _link_duplicates(rows)
        a = sp.assign_splits(rows, 7, FR)
        per_hash = {}
        for r in rows:
            per_hash.setdefault(r.content_hash, set()).add(a[r.image_id])
        self.assertTrue(all(len(v) == 1 for v in per_hash.values()))
        self.assertEqual({v for s in per_hash.values() for v in s}, set(FR))
        self.assertTrue(split_checks(rows, [], a, TASK_LEVEL)["ok"])


class ReviewLeakageTests(helpers.TmpCase):
    """An upload that is a copy of a labeled radiograph must never feed review labels into training."""

    def setUp(self):
        super().setUp()
        write_simulated_main_layout(self.s.data_root, 24)
        DatasetService(self.s).process()
        self.db = Database(self.s.db_path)
        self.store = ReviewStore(self.db)
        rows = DatasetService(self.s).manifest("main")
        self.test_row = next(r for r in rows if r.split == "test" and r.annotation_status == "annotated")

    def _upload(self, src_path, image_id):
        self.s.upload_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_path, self.s.upload_dir / f"{image_id}.png")
        data = (self.s.upload_dir / f"{image_id}.png").read_bytes()
        self.db.insert("images", {"id": image_id, "filename": f"{image_id}.png", "rel_path": f"{image_id}.png", "width": 1, "height": 1,
                                  "sha256": hashlib.sha256(data).hexdigest(), "source": "upload", "quality_json": jdump({}), "created": now()})
        reg = {"region_id": "R:1", "region_no": 1, "box": [1, 1, 30, 30], "fdi": 36, "fdi_confidence": .9, "numbering_status": "assigned",
               "detection_score": .99, "uncertainty": {}, "flags": [],
               "candidate_class": {"label": "Caries", "score": .7, "probabilities": {"Caries": .7, "Impacted": .3}, "status": "candidate"}}
        self.db.insert("analyses", {"id": new_id("an"), "image_id": image_id, "kind": "full", "model_version": "x", "status": "done",
                                    "result_json": jdump({"regions": [reg], "models": {}}), "created": now()})
        return self.store.submit(self.s, {"image_id": image_id, "region_id": "R:1", "action": "confirm_candidate", "reviewer": "Reviewer One"})

    def test_upload_identical_to_a_test_radiograph_is_not_usable(self):
        r = self._upload(self.s.data_root / self.test_row.file_path, "up_copyoftest")
        self.assertEqual((r["split"], r["usable_for_training"]), ("test", False))
        self.store.decide([r["id"]], "Second Person", True)
        self.assertEqual(self.store.training_items(self.s)[0], [])

    def test_stored_usable_record_is_rechecked_when_training_items_are_built(self):
        r = self._upload(self.s.data_root / self.test_row.file_path, "up_legacy")
        self.db.update("region_reviews", "id", r["id"], {"usable_for_training": 1})    # record written before the check existed
        self.store.decide([r["id"]], "Second Person", True)
        items, skipped = self.store.training_items(self.s)
        self.assertEqual((items, skipped["identical_to_labeled"]), ([], 1))

    def test_genuinely_new_upload_stays_usable(self):
        p = self.tmp / "new.png"
        p.write_bytes(helpers.png_bytes(seed=999))
        r = self._upload(p, "up_new")
        self.assertEqual((r["split"], r["usable_for_training"]), ("upload", True))
        self.store.decide([r["id"]], "Second Person", True)
        self.assertEqual(len(self.store.training_items(self.s)[0]), 1)


if __name__ == "__main__":
    unittest.main()
