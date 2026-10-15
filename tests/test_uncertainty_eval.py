import unittest

import numpy as np

import helpers  # noqa: F401
from dentexmodel.evaluation import average_precision, classification_report, detection_map, mean_mask_iou
from dentexmodel.uncertainty import (Signal, UncertaintyRecord, brier_score, detection_instability, entropy,
                                     expected_calibration_error, image_quality, jensen_shannon_disagreement, mask_instability,
                                     reliability_bins, risk_coverage)
from dentexmodel.uncertainty.measures import mc_dropout_summary


class EntropyTests(unittest.TestCase):
    def test_extremes(self):
        np.testing.assert_allclose(entropy([[1, 0, 0], [1 / 3] * 3]), [0.0, 1.0], atol=1e-9)

    def test_unnormalized(self):
        self.assertAlmostEqual(float(entropy([0.5, 0.5], normalize=False)), np.log(2))

    def test_rejects_bad_input(self):
        for bad in ([[0.5, 0.2]], [[-0.1, 1.1]], [[np.nan, 1.0]], [1.0]):
            with self.assertRaises(ValueError):
                entropy(bad)

    def test_disagreement(self):
        agree = [[[0.9, 0.1]], [[0.9, 0.1]]]
        disagree = [[[1.0, 0.0]], [[0.0, 1.0]]]
        self.assertAlmostEqual(float(jensen_shannon_disagreement(agree)[0]), 0.0, places=9)
        self.assertAlmostEqual(float(jensen_shannon_disagreement(disagree)[0]), 1.0, places=6)  # max for 2 classes
        with self.assertRaises(ValueError):
            jensen_shannon_disagreement([[[0.5, 0.5]]])  # one member

    def test_mc_dropout_decomposition(self):
        s = mc_dropout_summary([[[1.0, 0.0]], [[0.0, 1.0]]])
        self.assertAlmostEqual(float(s["epistemic"][0]), np.log(2))
        self.assertAlmostEqual(float(s["aleatoric"][0]), 0.0, places=6)

    def test_mask_instability(self):
        a = np.zeros((10, 10), bool); a[:5] = True
        self.assertEqual(mask_instability([a, a.copy()]), 0.0)
        b = np.zeros((10, 10), bool); b[5:] = True
        self.assertEqual(mask_instability([a, b]), 1.0)
        with self.assertRaises(ValueError):
            mask_instability([a])

    def test_detection_instability(self):
        r1 = [((0, 0, 10, 10), 0.9)]
        r2 = [((0, 0, 10, 10), 0.8)]
        d = detection_instability([r1, r2])
        self.assertAlmostEqual(d["localization_instability"], 0.0)
        self.assertAlmostEqual(d["score_abs_diff"], 0.1)
        d2 = detection_instability([r1, []])
        self.assertEqual(d2["unmatched_fraction"], 1.0)
        self.assertIsNone(d2["localization_instability"])


class RecordTests(unittest.TestCase):
    def test_unavailable_is_not_zero(self):
        r = UncertaintyRecord("a")
        self.assertIsNone(r.combined())
        d = r.to_dict()
        self.assertIsNone(d["entropy"]["value"])
        self.assertEqual(d["entropy"]["status"], "unavailable")

    def test_combined_renormalizes_over_available(self):
        r = UncertaintyRecord("a", entropy=Signal.computed(0.5), mask_instability=Signal.computed(0.1))
        self.assertAlmostEqual(r.combined({"entropy": 0.4, "disagreement": 0.4, "mask_instability": 0.2}), (0.4 * 0.5 + 0.2 * 0.1) / 0.6)


class CalibrationTests(unittest.TestCase):
    def test_perfect_and_overconfident(self):
        p = [[1, 0], [1, 0], [0, 1], [0, 1]]
        y = [0, 0, 1, 1]
        self.assertEqual(expected_calibration_error(p, y), 0.0)
        self.assertEqual(brier_score(p, y), 0.0)
        bad = [[1, 0]] * 4
        self.assertAlmostEqual(expected_calibration_error(bad, [1, 1, 1, 0]), 0.75)
        self.assertAlmostEqual(brier_score(bad, [1, 1, 1, 0]), 1.5)

    def test_bins_and_errors(self):
        self.assertEqual(sum(b["count"] for b in reliability_bins([[0.6, 0.4], [0.2, 0.8]], [0, 1], 5)), 2)
        with self.assertRaises(ValueError):
            expected_calibration_error([[0.5, 0.5]], [3])
        with self.assertRaises(ValueError):
            expected_calibration_error(np.zeros((0, 2)), [])

    def test_risk_coverage(self):
        rc = risk_coverage([0.9, 0.8, 0.7, 0.6], [True, True, False, True])
        self.assertEqual(rc["risk"], [0.0, 0.0, 1 / 3, 0.25])
        self.assertEqual(rc["coverage"][-1], 1.0)


class QualityTests(unittest.TestCase):
    def test_flags(self):
        flat = np.full((64, 64), 0.5, np.float32)
        q = image_quality(flat)
        self.assertIn("low_sharpness", q["flags"])
        self.assertIn("low_contrast", q["flags"])
        rng = np.random.default_rng(0)
        good = np.clip(rng.normal(0.5, 0.2, (64, 64)), 0.01, 0.99).astype(np.float32)
        self.assertEqual(image_quality(good)["flags"], [])
        self.assertIn("too_dark", image_quality(good * 0.1)["flags"])


class MetricTests(unittest.TestCase):
    def test_f1_excludes_absent_classes(self):
        r = classification_report([0, 1, 1, 2], [0, 1, 2, 2], 4, ["a", "b", "c", "d"])
        self.assertAlmostEqual(r["macro_f1"], (1 + 2 / 3 + 2 / 3) / 3)
        self.assertEqual(r["classes_without_support"], ["d"])

    def test_ap(self):
        gts = [("a", (0, 0, 10, 10)), ("a", (20, 20, 30, 30))]
        perfect = [("a", 0.9, (0, 0, 10, 10)), ("a", 0.8, (20, 20, 30, 30))]
        self.assertAlmostEqual(average_precision(perfect, gts), 1.0)
        half = [("a", 0.9, (0, 0, 10, 10)), ("a", 0.8, (50, 50, 60, 60))]
        self.assertAlmostEqual(average_precision(half, gts), 0.5)
        self.assertIsNone(average_precision(perfect, []))

    def test_duplicate_detection_is_false_positive(self):
        gts = [("a", (0, 0, 10, 10))]
        dup = [("a", 0.9, (0, 0, 10, 10)), ("a", 0.8, (0, 0, 10, 10))]
        self.assertAlmostEqual(average_precision(dup, gts), 1.0)  # recall reached at rank 1; later FP cannot lower the envelope

    def test_map_structure(self):
        gts = [("a", 0, (0, 0, 10, 10))]
        preds = [("a", 0, 0.9, (0, 0, 10, 10))]
        m = detection_map(preds, gts)
        self.assertAlmostEqual(m["map"], 1.0)
        self.assertEqual(m["n_classes_with_gt"], 1)
        self.assertIsNone(detection_map(preds, [])["map"])

    def test_mask_iou_mean(self):
        a = np.zeros((4, 4), bool); a[:2] = True
        self.assertAlmostEqual(mean_mask_iou([a], [a]), 1.0)
        self.assertIsNone(mean_mask_iou([a], []))


if __name__ == "__main__":
    unittest.main()
