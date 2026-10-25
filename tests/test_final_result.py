"""Final image-level result: every tooth with a valid classifier output is listed with its highest-scoring class (high entropy adds a review warning, never "healthy"); failures -> error.

The pipeline tests replace the four models with deterministic stubs (no checkpoints, no GPU) and run the real
PipelineService.run, so the rule is checked exactly where the application computes it."""
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
from dentexmodel.reporting import make_evidence, template_report, validate_report
from dentexmodel.reporting.final_result import (ERROR_LABEL, FINDING_LABEL, HEALTHY_LABEL, NO_TEETH_LABEL, final_result,
                                                final_result_from_evidence)
from dentexmodel.reporting.i18n import localize_report, render_html_localized, render_text_localized, verify_localization

CLASSES = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
BOXES = [[10, 10, 60, 90], [80, 10, 130, 90], [150, 10, 200, 90]]


def confident(k):        # normalised entropy ~0.12 -> a candidate (below the 0.40 default review threshold)
    p = [0.01] * 4
    p[k] = 0.97
    return p


UNIFORM = [0.25, 0.25, 0.25, 0.25]      # normalised entropy 1.0 -> abstained


class _DB:
    def __init__(self):
        self.rows = []

    def insert(self, table, row):
        self.rows.append((table, row))


class PipelineFinalResult(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        settings = SimpleNamespace(data_root=self.tmp)          # no thresholds file -> built-in defaults
        ctx = SimpleNamespace(settings=settings, db=_DB())
        images = SimpleNamespace(get=lambda iid: {"image_id": iid}, load_rgb01=lambda iid: np.zeros((100, 220, 3), np.float32))
        analysis = SimpleNamespace(quality_for=lambda iid: {"flags": [], "metrics": {}})
        self.svc = PipelineService(ctx, images, analysis)
        self.ctx = ctx

    def run_with(self, probs=None, boxes=BOXES, detect_error=None, classify_error=None):
        def detect(img, iid, s):
            if detect_error:
                raise detect_error
            return DetectionResult(iid, "det_v1", "det_v1.pth", "detection",
                                   [Detection(box=b, score=0.95, class_id=1, label="tooth") for b in boxes])

        def classify(img, bxs, s, flip=False):
            if classify_error:
                raise classify_error
            return {"model_version": "cls_v1", "class_names": CLASSES, "probabilities": [probs[i] for i in range(len(bxs))], "flipped": flip, "limitations": []}

        def no_numbering(*a, **k):
            raise ModelUnavailableError("numbering model not loaded")

        with mock.patch("dentexmodel.inference.torch_models.detect_teeth", detect), \
                mock.patch("dentexmodel.inference.torch_models.classify_regions", classify), \
                mock.patch("dentexmodel.inference.torch_models.segment_teeth", side_effect=AssertionError("not used")), \
                mock.patch.object(PipelineService, "_number_or_raise", no_numbering):
            return self.svc.run("img1", segmentation=False, uncertainty=False)

    # ---- each finding class -----------------------------------------------------------------------------
    def test_each_finding_class_is_shown_with_its_label(self):
        for k, cls in enumerate(CLASSES):
            with self.subTest(cls=cls):
                r = self.run_with(probs=[confident(k), confident(k), confident(k)])
                fr = r["final_result"]
                self.assertEqual(fr["status"], "finding")
                self.assertEqual(fr["label"], FINDING_LABEL)
                self.assertEqual([f["label"] for f in fr["findings"]], [cls] * 3)
                self.assertAlmostEqual(fr["findings"][0]["score"], 0.97, places=6)
                self.assertEqual(fr["counts"], {cls: 3})
                self.assertFalse(any(f["high_uncertainty"] for f in fr["findings"]))
                self.assertIsNotNone(fr["findings"][0]["region_no"])

    def test_example_region_above_entropy_threshold_shows_highest_class_and_review_warning(self):
        """Region 22 / tooth 33 example: Caries .726, Deep Caries .140, Impacted .034, Periapical Lesion .100 (entropy ~0.616)."""
        example = [0.726, 0.140, 0.034, 0.100]
        r = self.run_with(probs=[example, confident(2), example], boxes=BOXES)
        reg = r["regions"][0]
        self.assertGreaterEqual(reg["uncertainty"]["entropy"], 0.3966)                 # at/above the unchanged review threshold
        self.assertAlmostEqual(reg["uncertainty"]["entropy"], 0.616, places=2)
        self.assertEqual(reg["candidate_class"]["status"], "abstained")
        self.assertEqual(reg["candidate_class"]["probabilities"], dict(zip(CLASSES, example)))   # raw scores unchanged
        self.assertTrue(reg["review_required"])
        f = next(x for x in r["final_result"]["findings"] if x["region_no"] == reg["region_no"])
        self.assertEqual((f["label"], f["score"]), ("Caries", 0.726))
        self.assertTrue(f["high_uncertainty"] and f["needs_review"])
        self.assertEqual(r["final_result"]["status"], "finding")
        self.assertEqual(r["final_result"]["n_high_uncertainty"], 2)

    def test_five_confident_and_22_high_uncertainty_regions_are_all_listed(self):
        """val_36-like image: 27 regions, 5 confident Caries, 22 above the entropy threshold -> all 27 listed, 22 flagged for review."""
        boxes = [[10 + 30 * i, 10, 35 + 30 * i, 90] for i in range(27)]
        caries_at = {1, 7, 11, 16, 25}
        probs = [confident(0) if i in caries_at else [0.4, 0.3, 0.2, 0.1] for i in range(27)]
        r = self.run_with(probs=probs, boxes=boxes)
        statuses = [g["candidate_class"]["status"] for g in r["regions"]]
        self.assertEqual((statuses.count("candidate"), statuses.count("abstained")), (5, 22))     # entropy rule unchanged
        fr = r["final_result"]
        self.assertEqual(fr["status"], "finding")
        self.assertEqual(fr["counts"], {"Caries": 27})
        self.assertEqual((fr["n_abstained"], fr["n_high_uncertainty"]), (22, 22))
        flagged = {g["region_no"] for g in r["regions"] if g["candidate_class"]["status"] == "abstained"}
        self.assertEqual({f["region_no"] for f in fr["findings"] if f["high_uncertainty"]}, flagged)

    def test_several_findings_are_all_listed(self):
        fr = self.run_with(probs=[confident(0), confident(3), confident(0)])["final_result"]
        self.assertEqual(fr["status"], "finding")
        self.assertEqual(fr["counts"], {"Caries": 2, "Periapical Lesion": 1})
        self.assertEqual(len(fr["findings"]), 3)

    # ---- empty finding prediction ------------------------------------------------------------------------
    def test_all_regions_high_uncertainty_is_never_healthy(self):
        r = self.run_with(probs=[UNIFORM, UNIFORM, UNIFORM])
        self.assertTrue(all(g["candidate_class"]["status"] == "abstained" for g in r["regions"]))
        fr = r["final_result"]
        self.assertEqual(fr["status"], "finding")
        self.assertNotEqual(fr["label"], HEALTHY_LABEL)
        self.assertEqual([f["label"] for f in fr["findings"]], ["Caries"] * 3)     # exact tie -> first class, as numpy argmax
        self.assertTrue(all(f["high_uncertainty"] and f["needs_review"] for f in fr["findings"]))
        self.assertEqual(fr["n_abstained"], 3)
        stored = [row for t, row in self.ctx.db.rows if t == "analyses" and row["kind"] == "full"][0]
        self.assertIn('"final_result"', stored["result_json"])          # saved with the analysis

    def test_non_finite_scores_give_no_class(self):
        r = self.run_with(probs=[[float("nan"), 0.2, 0.2, 0.2], confident(1), [float("inf"), 0, 0, 0]])
        bad = [g for g in r["regions"] if g["detection_index"] in (0, 2)]
        self.assertTrue(all(g["candidate_class"] is None and "invalid_classifier_output" in g["review_reasons"] for g in bad))
        self.assertEqual([f["label"] for f in r["final_result"]["findings"]], ["Deep Caries"])
        fr = self.run_with(probs=[[float("nan")] * 4] * 3)["final_result"]
        self.assertEqual(fr["status"], "error")

    # ---- inference failures --------------------------------------------------------------------------------
    def test_classifier_failure_is_an_error_not_healthy(self):
        r = self.run_with(probs=None, classify_error=RuntimeError("CUDA out of memory"))
        fr = r["final_result"]
        self.assertEqual(fr["status"], "error")
        self.assertEqual(fr["label"], ERROR_LABEL)
        self.assertNotEqual(fr["label"], HEALTHY_LABEL)
        self.assertIn("CUDA out of memory", fr["message"])

    def test_classifier_unavailable_is_an_error(self):
        fr = self.run_with(probs=None, classify_error=ModelUnavailableError("no classifier checkpoint"))["final_result"]
        self.assertEqual(fr["status"], "error")

    def test_detector_failure_is_an_error(self):
        fr = self.run_with(probs=None, detect_error=RuntimeError("bad checkpoint"))["final_result"]
        self.assertEqual(fr["status"], "error")
        self.assertIn("detection", fr["message"].lower())

    def test_no_teeth_detected_is_not_healthy(self):
        fr = self.run_with(probs=[], boxes=[])["final_result"]
        self.assertEqual(fr["status"], "no_teeth")
        self.assertEqual(fr["label"], NO_TEETH_LABEL)

    def test_regions_without_any_classifier_output_are_an_error(self):
        fr = self.run_with(probs=[None, None, None])["final_result"]
        self.assertEqual(fr["status"], "error")


class StoredAndReportFinalResult(unittest.TestCase):
    def _analysis(self, statuses, steps_ok=True):
        regs = []
        for i, st in enumerate(statuses, 1):
            probs = {c: (0.7 if c == CLASSES[i % 4] else 0.1) for c in CLASSES}
            cc = None if st is None else {"label": CLASSES[i % 4], "score": 0.7, "probabilities": probs, "status": st}
            regs.append({"region_id": f"img:{i}", "region_no": i, "box": [0, 0, 5, 5], "fdi": 10 + i, "candidate_class": cc, "review_required": st != "candidate"})
        steps = [{"step": "detect", "status": "ok"}, {"step": "classify", "status": "ok" if steps_ok else "failed", "message": "boom"}]
        return {"regions": regs, "steps": steps}

    def test_old_stored_analysis_without_field_gets_same_rule(self):
        fr = final_result(self._analysis(["abstained", "abstained"]))
        self.assertEqual(fr["status"], "finding")                       # stored abstained regions now show their top class
        self.assertEqual([(f["label"], f["high_uncertainty"]) for f in fr["findings"]], [("Deep Caries", True), ("Impacted", True)])
        self.assertEqual(final_result(self._analysis(["abstained", "candidate"]))["status"], "finding")
        self.assertEqual(final_result(self._analysis(["candidate"], steps_ok=False))["status"], "error")
        self.assertIsNone(final_result({"detections": []}))            # not a full analysis

    def test_top_class_validation(self):
        from dentexmodel.reporting.final_result import top_class
        ok = {"Caries": 0.726, "Deep Caries": 0.14, "Impacted": 0.034, "Periapical Lesion": 0.1}
        tc = top_class({"probabilities": ok, "status": "abstained", "label": "Caries"})
        self.assertEqual((tc["label"], tc["score"], tc["high_uncertainty"], tc["scores"]), ("Caries", 0.726, True, ok))
        self.assertFalse(top_class({"probabilities": ok, "status": "candidate"})["high_uncertainty"])
        for bad in (None, {}, {"probabilities": {}}, {"probabilities": {**ok, "Caries": float("nan")}},
                    {"probabilities": {**ok, "Impacted": float("inf")}}, {"probabilities": {**ok, "Impacted": None}},
                    {"probabilities": {**ok, "Impacted": "0.3"}}, {"probabilities": {**ok, "Impacted": 1.5}}, {"probabilities": [0.7, 0.3]}):
            with self.subTest(bad=bad):
                self.assertIsNone(top_class(bad))

    def _evidence(self, kinds, steps=None, fr=None):
        fs = []
        for i, k in enumerate(kinds, 1):
            hu = k == "high_uncertainty"
            k = "closest_class" if hu else k
            fs.append({"tooth_fdi": 10 + i, "kind": k, "label": "Caries" if k == "closest_class" else (None if k in ("abstained", "class_unavailable") else "tooth"),
                       "probability": 0.82 if k not in ("abstained", "class_unavailable") else None, "uncertainty": 0.1 if k != "detection" else None,
                       "high_uncertainty": hu, "needs_review": hu})
        ctx = {}
        if steps:
            ctx["steps"] = steps
        if fr:
            ctx["final_result"] = fr
        return make_evidence("img1", "det_v1", fs, {"detection": "det_v1", "classification": "cls_v1"}, ctx)

    def test_evidence_rules(self):
        self.assertEqual(final_result_from_evidence(self._evidence(["closest_class", "abstained"]))["status"], "finding")
        fr = final_result_from_evidence(self._evidence(["high_uncertainty", "high_uncertainty"]))
        self.assertEqual(fr["status"], "finding")
        self.assertTrue(all(f["high_uncertainty"] and f["needs_review"] for f in fr["findings"]))
        legacy = final_result_from_evidence(self._evidence(["abstained", "abstained"]))      # old evidence without scores
        self.assertEqual(legacy["status"], "error")
        self.assertNotEqual(legacy["label"], HEALTHY_LABEL)
        self.assertEqual(final_result_from_evidence(self._evidence(["class_unavailable"]))["status"], "error")
        self.assertEqual(final_result_from_evidence(self._evidence(["detection"]))["status"], "error")
        self.assertEqual(final_result_from_evidence(self._evidence([]))["status"], "no_teeth")
        bad = [{"step": "detect", "status": "ok"}, {"step": "classify", "status": "unavailable"}]
        self.assertEqual(final_result_from_evidence(self._evidence(["abstained"], steps=bad))["status"], "error")

    def test_report_carries_final_result_and_still_validates(self):
        for kinds, status in [(["high_uncertainty", "high_uncertainty"], "finding"), (["closest_class", "abstained"], "finding"),
                              (["class_unavailable"], "error")]:
            with self.subTest(status=status):
                ev = self._evidence(kinds)
                rep = template_report(ev)
                self.assertEqual(rep["final_result"]["status"], status)
                self.assertTrue(validate_report(rep, ev, vocabulary=CLASSES)["passed"])

    def test_localized_reports_show_same_result(self):
        rep = template_report(self._evidence(["high_uncertainty", "closest_class"]))
        en, hi, mr = (localize_report(rep, lang) for lang in ("en", "hi", "mr"))
        self.assertEqual(en["final_result"]["label_display"], FINDING_LABEL)
        self.assertEqual({hi["final_result"]["status"], mr["final_result"]["status"]}, {"finding"})
        for loc in (en, hi, mr):
            self.assertTrue(verify_localization(rep, loc)["passed"])
        self.assertIn("raw model score 0.82; needs human review — high classifier uncertainty", en["final_result"]["findings"][0]["text"])
        self.assertNotIn("uncertainty", en["final_result"]["findings"][1]["text"])
        self.assertIn("Needs human review — high classifier uncertainty", en["findings"][0]["narrative"])
        self.assertIn("मानव समीक्षा आवश्यक", hi["findings"][0]["narrative"])
        self.assertIn("मानवी पुनरावलोकन आवश्यक", mr["findings"][0]["narrative"])
        self.assertIn('data-final-result="finding"', render_html_localized(en))
        self.assertNotIn(HEALTHY_LABEL, render_text_localized(en))
        rep2 = template_report(self._evidence(["closest_class"]))
        self.assertIn("Caries", render_text_localized(localize_report(rep2, "en")))

    def test_verify_localization_catches_a_changed_final_result(self):
        rep = template_report(self._evidence(["closest_class"]))
        loc = localize_report(rep, "hi")
        loc["final_result"] = {**loc["final_result"], "status": "healthy"}
        self.assertFalse(verify_localization(rep, loc)["passed"])


if __name__ == "__main__":
    unittest.main()
