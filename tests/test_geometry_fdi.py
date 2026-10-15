import unittest

import numpy as np

import helpers  # noqa: F401
from dentexmodel.data.fdi import fdi_from_parts, is_valid_fdi
from dentexmodel.inference.tooth_numbering import check_numbering
from dentexmodel.utils import geometry as g


class GeometryTests(unittest.TestCase):
    def test_box_conversions_roundtrip(self):
        self.assertEqual(g.xyxy_to_xywh(g.xywh_to_xyxy((10, 20, 30, 40))), (10, 20, 30, 40))

    def test_percent_pixel_roundtrip(self):
        box = (100.0, 50.0, 300.0, 250.0)
        v = g.pixel_to_percent_xywh(box, 1000, 500)
        self.assertAlmostEqual(v["x"], 10.0)
        self.assertAlmostEqual(v["height"], 40.0)
        back = g.percent_to_pixel_xyxy(v, 1000, 500)
        np.testing.assert_allclose(back, box)

    def test_validate_box(self):
        self.assertEqual(g.validate_box_xyxy((1, 1, 10, 10), 100, 100), [])
        self.assertTrue(g.validate_box_xyxy((10, 10, 5, 20), 100, 100))
        self.assertIn("box outside image bounds", g.validate_box_xyxy((0, 0, 200, 10), 100, 100))
        self.assertTrue(g.validate_box_xyxy((0, 0, float("nan"), 1)))

    def test_iou(self):
        self.assertAlmostEqual(g.box_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        self.assertAlmostEqual(g.box_iou((0, 0, 10, 10), (5, 0, 15, 10)), 1 / 3)
        self.assertEqual(g.box_iou((0, 0, 1, 1), (5, 5, 6, 6)), 0.0)

    def test_rle_roundtrip(self):
        rng = np.random.default_rng(0)
        for _ in range(5):
            m = rng.random((17, 23)) > 0.6
            np.testing.assert_array_equal(g.rle_to_mask(g.mask_to_rle(m)), m)
        z = np.zeros((4, 4), bool)
        np.testing.assert_array_equal(g.rle_to_mask(g.mask_to_rle(z)), z)
        full = np.ones((4, 4), bool)
        np.testing.assert_array_equal(g.rle_to_mask(g.mask_to_rle(full)), full)

    def test_rle_rejects_bad_counts(self):
        with self.assertRaises(ValueError):
            g.rle_to_mask({"size": [2, 2], "counts": [1, 1]})

    def test_polygon_mask_is_not_a_box(self):
        tri = g.polygon_to_mask([(0, 0), (20, 0), (0, 20)], 21, 21)
        self.assertTrue(tri[1, 1])
        self.assertFalse(tri[19, 19])  # a filled bounding box would be True here


class FdiTests(unittest.TestCase):
    def test_valid_codes(self):
        self.assertTrue(all(is_valid_fdi(c) for c in (11, 18, 21, 38, 48)))
        for bad in (0, 9, 19, 10, 49, 51, 99, "x", None, 11.5, "1 1"):
            self.assertFalse(is_valid_fdi(bad), bad)
        self.assertTrue(is_valid_fdi(55, allow_deciduous=True))
        self.assertFalse(is_valid_fdi(55))

    def test_from_parts(self):
        self.assertEqual(fdi_from_parts("1", "6"), 16)
        self.assertIsNone(fdi_from_parts("5", "1"))
        self.assertIsNone(fdi_from_parts("a", 1))

    def test_numbering_checks(self):
        teeth = [{"fdi": 11, "box": [10, 10, 30, 40], "fdi_confidence": 0.9},      # upper, left half: ok for Q1
                 {"fdi": 21, "box": [60, 10, 80, 40], "fdi_confidence": 0.9},       # upper, right half: ok for Q2
                 {"fdi": 21, "box": [65, 10, 85, 40], "fdi_confidence": 0.9},       # duplicate
                 {"fdi": 31, "box": [10, 60, 30, 90], "fdi_confidence": 0.9},       # Q3 expected right half but is left
                 {"fdi": 16, "box": [10, 10, 20, 20], "fdi_confidence": 0.2},       # low confidence
                 {"fdi": None, "box": [0, 0, 1, 1]},
                 {"fdi": 77, "box": [0, 0, 1, 1]}]
        r = check_numbering(teeth, 100, 100)
        st = [t["status"] for t in r["teeth"]]
        self.assertEqual(st[0], "assigned")
        self.assertEqual(st[1:3], ["needs_review", "needs_review"])
        self.assertEqual(st[3], "needs_review")
        self.assertEqual(st[4], "needs_review")
        self.assertEqual(st[5], "unassigned")
        self.assertEqual(st[6], "needs_review")


if __name__ == "__main__":
    unittest.main()
