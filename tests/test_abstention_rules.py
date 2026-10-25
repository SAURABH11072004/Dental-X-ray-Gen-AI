"""Abstention rules: the production entropy boundary, the offline rule families, missing predictions and inference failures.

The pipeline tests run the real PipelineService.run with deterministic stub models (no checkpoints, no GPU)."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

import helpers  # noqa: F401  (sys.path)
from backend.services.pipeline import PipelineService
from dentexmodel.errors import ModelUnavailableError
from dentexmodel.inference.torch_models import Detection, DetectionResult
from dentexmodel.uncertainty.abstention import Rule, abstains, acceptance_rate, decide, selective_metrics
from dentexmodel.uncertainty.measures import entropy

CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
REGION25 = [0.652, 0.083, 0.016, 0.249]            # the example from the report: normalised entropy 0.648


class _DB:
    def __init__(self):
        self.rows = []

    def insert(self, table, row):
        self.rows.append((table, row))


def run_pipeline(probs, threshold=None, classify_error=None):
    """Run PipelineService.run on 1..n stub boxes; optionally force the production entropy threshold."""
    boxes = [[10 + 60 * i, 10, 60 + 60 * i, 90] for i in range(len(probs))]
    tmp = Path(tempfile.mkdtemp())
    ctx = SimpleNamespace(settings=SimpleNamespace(data_root=tmp), db=_DB())
    svc = PipelineService(ctx, SimpleNamespace(get=lambda i: {"image_id": i}, load_rgb01=lambda i: np.zeros((100, 60 * len(boxes) + 40, 3), np.float32)),
                          SimpleNamespace(quality_for=lambda i: {"flags": [], "metrics": {}}))

    def detect(img, iid, s):
        return DetectionResult(iid, "det_v1", "det_v1.pth", "detection", [Detection(box=b, score=0.95, class_id=1, label="tooth") for b in boxes])

    def classify(img, bxs, s, flip=False):
        if classify_error:
            raise classify_error
        return {"model_version": "cls_v1", "class_names": CLASSES, "probabilities": list(probs), "flipped": flip, "limitations": []}

    def no_numbering(*a, **k):
        raise ModelUnavailableError("numbering model not loaded")

    patches = [mock.patch("dentexmodel.inference.torch_models.detect_teeth", detect),
               mock.patch("dentexmodel.inference.torch_models.classify_regions", classify),
               mock.patch.object(PipelineService, "_number_or_raise", no_numbering)]
    if threshold is not None:
        base = PipelineService.thresholds
        patches.append(mock.patch.object(PipelineService, "thresholds", lambda self: {**base(self), "normalised_entropy_ge": threshold}))
    for p in patches:
        p.start()
    try:
        return svc.run("img", segmentation=False, uncertainty=False)
    finally:
        for p in patches:
            p.stop()


class ProductionEntropyBoundary(unittest.TestCase):
    def test_region25_example_entropy(self):
        self.assertAlmostEqual(float(entropy(np.array(REGION25))), 0.648, places=3)

    def test_threshold_equal_to_entropy_abstains(self):
        h = float(entropy(np.array(REGION25)))
        r = run_pipeline([REGION25], threshold=h)                                 # operator is >=
        self.assertEqual(r["regions"][0]["candidate_class"]["status"], "abstained")
        self.assertIn("high_entropy", r["regions"][0]["flags"])

    def test_threshold_just_above_entropy_accepts(self):
        h = float(entropy(np.array(REGION25)))
        r = run_pipeline([REGION25], threshold=float(np.nextafter(h, 1.0)))
        self.assertEqual(r["regions"][0]["candidate_class"]["status"], "candidate")
        self.assertEqual(r["regions"][0]["candidate_class"]["label"], "Caries")

    def test_abstained_region_shows_highest_class_with_review_warning(self):
        r = run_pipeline([REGION25], threshold=0.3966)
        cc = r["regions"][0]["candidate_class"]
        self.assertEqual((cc["status"], cc["label"]), ("abstained", "Caries"))       # entropy rule unchanged: still abstained
        self.assertEqual(cc["probabilities"]["Caries"], 0.652)                        # raw score untouched
        self.assertIn("high_entropy", r["regions"][0]["review_reasons"])
        fr = r["final_result"]
        self.assertEqual(fr["status"], "finding")                                     # never "healthy" because of high uncertainty
        self.assertEqual([(f["label"], f["score"], f["high_uncertainty"], f["needs_review"]) for f in fr["findings"]],
                         [("Caries", 0.652, True, True)])

    def test_offline_entropy_rule_reproduces_production_decision(self):
        rng = np.random.default_rng(0)
        vecs = [list(v) for v in rng.dirichlet([0.7] * 4, size=40)] + [REGION25, [0.25] * 4, [0.97, 0.01, 0.01, 0.01]]
        thr = 0.3966
        r = run_pipeline(vecs, threshold=thr)
        by_det = sorted(r["regions"], key=lambda g: g["detection_index"])
        for p, g in zip(vecs, by_det):
            self.assertEqual(abstains(p, Rule("entropy", thr)), g["candidate_class"]["status"] == "abstained")


class OfflineRuleFamilies(unittest.TestCase):
    def test_boundaries(self):
        self.assertTrue(abstains([0.5, 0.3, 0.1, 0.1], Rule("max_prob", 0.6)))
        self.assertFalse(abstains([0.6, 0.2, 0.1, 0.1], Rule("max_prob", 0.6)))       # strict <: equal is accepted
        self.assertTrue(abstains([0.45, 0.40, 0.1, 0.05], Rule("margin", 0.10)))
        self.assertFalse(abstains([0.5, 0.25, 0.15, 0.10], Rule("margin", 0.25)))       # margin exactly 0.25 is accepted
        self.assertFalse(abstains([1.0, 0.0, 0.0, 0.0], Rule("entropy", 0.0001)))
        # uniform: the production entropy adds EPS inside the log, so H is just below 1, not exactly 1
        h = float(entropy(np.array([0.25] * 4)))
        self.assertTrue(0.999999 < h < 1.0)
        self.assertTrue(abstains([0.25] * 4, Rule("entropy", h)))
        self.assertFalse(abstains([0.25] * 4, Rule("entropy", 1.0)))

    def test_never_assigns_a_class_when_abstaining(self):
        self.assertIsNone(decide(REGION25, Rule("entropy", 0.3966)))
        self.assertEqual(decide(REGION25, Rule("entropy", 0.70)), 0)

    def test_unknown_family_rejected(self):
        with self.assertRaises(ValueError):
            Rule("healthy", 0.5)


class MissingAndInvalidPredictions(unittest.TestCase):
    def test_missing_prediction_is_counted_separately_and_never_correct(self):
        m = selective_metrics([0, 0, 1], [[0.97, 0.01, 0.01, 0.01], None, [0.25] * 4], Rule("entropy", 0.4), CLASSES)
        self.assertEqual((m["accepted"], m["abstained"], m["missing"]), (1, 1, 1))
        self.assertEqual(m["coverage"], 0.5)                                            # missing excluded from coverage
        self.assertEqual(m["per_class"]["Caries"]["fn"], 1)                             # the missing Caries crop is a miss
        self.assertEqual(m["confusion"][0][5], 1)                                       # MISSING column

    def test_invalid_probability_vectors_raise(self):
        for bad in ([0.5, 0.5, np.nan, 0.0], [0.6, 0.6, 0.0, 0.0], [1.0], [[0.5, 0.5]], [-0.2, 0.6, 0.3, 0.3]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                decide(bad, Rule("entropy", 0.4))

    def test_unlabelled_acceptance_counts_missing_separately(self):
        a = acceptance_rate([[0.97, 0.01, 0.01, 0.01], [0.25] * 4, None], Rule("entropy", 0.4), CLASSES)
        self.assertEqual((a["n"], a["named"], a["abstained"], a["missing"]), (3, 1, 1, 1))
        self.assertEqual(a["named_rate"], 0.5)
        self.assertEqual(a["named_by_class"]["Caries"], 1)

    def test_pipeline_region_without_classifier_output_is_neither_candidate_nor_abstained(self):
        r = run_pipeline([[0.97, 0.01, 0.01, 0.01], None], threshold=0.3966)
        by_det = sorted(r["regions"], key=lambda g: g["detection_index"])
        self.assertEqual(by_det[0]["candidate_class"]["status"], "candidate")
        self.assertIsNone(by_det[1]["candidate_class"])
        self.assertEqual(r["summary"]["n_abstained"], 0)

    def test_inference_failure_is_an_error_not_an_abstention(self):
        r = run_pipeline([REGION25], classify_error=RuntimeError("CUDA error"))
        self.assertTrue(all(g["candidate_class"] is None for g in r["regions"]))
        self.assertEqual(r["summary"]["n_abstained"], 0)
        self.assertEqual(r["final_result"]["status"], "error")


class SelectiveMetricsHandChecked(unittest.TestCase):
    def test_small_example(self):
        y = [0, 0, 1, 3, 3]
        P = [[0.97, 0.01, 0.01, 0.01],      # Caries, accepted, correct
             [0.25, 0.25, 0.25, 0.25],      # Caries, abstained
             [0.90, 0.05, 0.03, 0.02],      # Deep Caries predicted Caries -> FP Caries, FN Deep Caries
             [0.02, 0.01, 0.01, 0.96],      # Periapical, correct
             [0.40, 0.30, 0.10, 0.20]]      # Periapical, abstained
        m = selective_metrics(y, P, Rule("entropy", 0.4), CLASSES)
        self.assertEqual((m["accepted"], m["abstained"]), (3, 2))
        self.assertAlmostEqual(m["risk"], 1 / 3)
        c, pl = m["per_class"]["Caries"], m["per_class"]["Periapical Lesion"]
        self.assertEqual((c["tp"], c["fp"], c["fn"]), (1, 1, 1))
        self.assertAlmostEqual(c["precision"], 0.5)
        self.assertAlmostEqual(c["recall_all"], 0.5)
        self.assertEqual((pl["tp"], pl["fp"], pl["fn"]), (1, 0, 1))
        self.assertEqual(m["confusion"][1], [1, 0, 0, 0, 0, 0])
        self.assertEqual(m["confusion"][3], [0, 0, 0, 1, 1, 0])


class ExperimentRefusesTestSplit(unittest.TestCase):
    def test_collect_refuses_test(self):
        sys.path.insert(0, str(helpers.ROOT / "scripts"))
        import abstention_threshold_experiment as E
        with self.assertRaises(SystemExit):
            E.collect("test")
        self.assertNotIn("test", E.SPLITS)


if __name__ == "__main__":
    unittest.main()
