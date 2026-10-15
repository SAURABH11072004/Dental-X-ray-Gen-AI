"""Review workflow, region matching, uncertainty record semantics and region-based reports. Fixtures are SYNTHETIC test data."""
import json
import unittest

import helpers
from backend.services.pipeline import _greedy_match, region_key
from backend.services.reports import ReportService
from dentexmodel.annotation.reviews import ReviewStore
from dentexmodel.errors import DentaMindError
from dentexmodel.reporting import template_report, validate_report
from dentexmodel.reporting.i18n import localize_report, verify_localization
from dentexmodel.storage import Database, jdump, new_id, now
from dentexmodel.uncertainty.record import Signal, UncertaintyRecord

PROBS = {"Caries": 0.7, "Deep Caries": 0.1, "Impacted": 0.1, "Periapical Lesion": 0.1}


def region(no, status="candidate", fdi=36, flags=None, key="aaaa1111"):
    return {"region_id": f"IMG:{key}", "region_no": no, "detection_index": no - 1, "box": [10 * no, 10, 10 * no + 8, 40], "detection_score": 0.998,
            "fdi": fdi, "fdi_confidence": 0.9, "numbering_status": "assigned" if fdi else "unassigned",
            "mask": {"segmentation_index": no - 1, "match_iou": 0.91, "segmentation_score": 0.99, "area": 120, "mask_rle": None},
            "candidate_class": {"label": "Caries", "score": 0.7, "probabilities": PROBS, "status": status, "kind": "closest"},
            "uncertainty": {"entropy": 0.45, "tta_disagreement": 0.02, "mask_instability": 0.05, "detection_instability": 0.04},
            "flags": flags or [], "review_reasons": flags or [], "review_required": bool(flags)}


def full_analysis(regions):
    return {"image_id": "IMG", "image_size": [100, 50], "models": {"detection": "det-v1", "segmentation": "seg-v1", "numbering": "num-v1", "classification": "cls-v1"},
            "regions": regions, "steps": [{"step": "detect", "status": "ok", "message": "", "seconds": 0.1}],
            "summary": {"n_regions": len(regions), "n_numbered": sum(1 for r in regions if r["fdi"]), "n_with_mask": len(regions),
                        "n_review_required": sum(1 for r in regions if r["review_required"]), "n_abstained": sum(1 for r in regions if r["candidate_class"]["status"] == "abstained"),
                        "all_steps_ok": True, "seconds": 1.0}, "uncertainty": {"combined_score": 0.2, "thresholds": {"provisional": True}},
            "preprocess": {"quality_flags": []}}


class MatchingTests(unittest.TestCase):
    def test_greedy_match_is_one_to_one_and_threshold_bound(self):
        a = [[0, 0, 10, 10], [20, 0, 30, 10], [100, 0, 110, 10]]
        b = [[21, 0, 31, 10], [1, 0, 11, 10], [500, 500, 510, 510]]
        m = _greedy_match(a, b)
        self.assertEqual(m[0][0], 1)          # matched by overlap, not by list position
        self.assertEqual(m[1][0], 0)
        self.assertNotIn(2, m)                # nothing overlaps: stays unmatched
        self.assertEqual(len({j for j, _ in m.values()}), len(m))

    def test_region_id_is_stable_for_identical_boxes_and_changes_with_model_or_box(self):
        k = region_key("IMG", [10, 10, 50, 90], "det-v1")
        self.assertEqual(k, region_key("IMG", [10, 10, 50, 90], "det-v1"))
        self.assertEqual(k, region_key("IMG", [11, 9, 51, 91], "det-v1"))     # within the 8 px rounding
        self.assertNotEqual(k, region_key("IMG", [10, 10, 50, 90], "det-v2"))
        self.assertNotEqual(k, region_key("IMG", [200, 10, 250, 90], "det-v1"))


class UncertaintySemanticsTests(unittest.TestCase):
    def test_missing_signals_are_never_zero_and_combined_renormalises(self):
        r = UncertaintyRecord("I")
        r.entropy = Signal.computed(0.6)
        r.disagreement = Signal.unavailable("needs the classifier")
        r.mask_instability = Signal.unavailable("no segmenter")
        d = r.to_dict()
        self.assertAlmostEqual(d["combined_score"], 0.6)            # only the available signal counts
        self.assertIsNone(d["disagreement"]["value"])
        self.assertEqual(d["disagreement"]["status"], "unavailable")
        self.assertIn("needs the classifier", d["disagreement"]["reason"])
        r.mask_instability = Signal.computed(0.0)                    # a genuine 0 is different from "unavailable"
        self.assertLess(r.to_dict()["combined_score"], 0.6)
        self.assertIsNone(UncertaintyRecord("J").to_dict()["combined_score"])   # nothing available -> None, not 0


class ReportFromRegionsTests(unittest.TestCase):
    def test_abstained_regions_are_not_named_and_report_validates_in_all_languages(self):
        regs = [region(1), region(2, status="abstained", flags=["high_entropy"], key="bbbb2222"), region(3, fdi=None, flags=["unassigned_tooth_number"], key="cccc3333")]
        ev = ReportService._evidence_from_full(None, full_analysis(regs))
        self.assertEqual([f["kind"] for f in ev["findings"]], ["closest_class", "abstained", "closest_class"])
        self.assertIsNone(ev["findings"][1]["label"])                # nothing is claimed for an abstained region
        rep = template_report(ev)
        self.assertTrue(validate_report(rep, ev)["passed"], validate_report(rep, ev)["errors"])
        self.assertIn("no reliable candidate class", rep["findings"][1]["narrative"])
        self.assertNotIn("Caries", rep["findings"][1]["narrative"])
        self.assertEqual(rep["analysis"]["summary_counts"]["n_review_required"], 2)
        for lang in ("en", "hi", "mr"):
            loc = localize_report(rep, lang)
            chk = verify_localization(rep, loc)
            self.assertTrue(chk["passed"], (lang, chk["problems"]))
            self.assertEqual([f["needs_review"] for f in loc["findings"]], [False, True, True])
            self.assertEqual(loc["findings"][1]["region_id"], "IMG:bbbb2222")       # ids survive translation

    def test_versions_reflect_which_models_actually_contributed(self):
        ev = ReportService._evidence_from_full(None, full_analysis([region(1, fdi=None, flags=["unassigned_tooth_number"])]))
        self.assertNotIn("numbering", ev["model_versions"])         # no number was assigned, so that model is not credited
        self.assertEqual(ev["model_versions"]["segmentation"], "seg-v1")


class ReviewWorkflowTests(helpers.TmpCase):
    def setUp(self):
        super().setUp()
        self.db = Database(self.s.db_path)
        self.store = ReviewStore(self.db)
        a = full_analysis([region(1), region(2, status="abstained", flags=["high_entropy"], key="bbbb2222")])
        self.aid = new_id("an")
        self.db.insert("analyses", {"id": self.aid, "image_id": "IMG", "kind": "full", "model_version": "det-v1", "status": "done", "result_json": jdump(a), "created": now()})

    def sub(self, **kw):
        base = {"image_id": "IMG", "region_id": "IMG:aaaa1111", "action": "confirm_candidate", "reviewer": "Reviewer One"}
        base.update(kw)
        return self.store.submit(self.s, base)

    def test_confirm_records_the_exact_model_output_that_was_reviewed(self):
        r = self.sub()
        self.assertEqual(r["corrected_class"], "Caries")
        self.assertEqual(r["previous"]["candidate_class"]["label"], "Caries")
        self.assertEqual(r["models"]["classification"], "cls-v1")
        self.assertEqual(r["status"], "submitted")
        self.assertIn("not verified", r["reviewer_qualification"])

    def test_validation_rules(self):
        with self.assertRaises(DentaMindError) as c:
            self.sub(reviewer=" ")
        self.assertEqual(c.exception.code, "reviewer_required")
        with self.assertRaises(DentaMindError) as c:
            self.sub(region_id="IMG:nope")
        self.assertEqual(c.exception.code, "unknown_region")
        with self.assertRaises(DentaMindError) as c:
            self.sub(action="correct_class", corrected_class="Healthy")
        self.assertEqual(c.exception.code, "invalid_class")                # there is no healthy label
        with self.assertRaises(DentaMindError) as c:
            self.sub(action="set_tooth_number", corrected_fdi=19)
        self.assertEqual(c.exception.code, "invalid_fdi")
        with self.assertRaises(DentaMindError) as c:
            self.sub(region_id="IMG:bbbb2222")                             # abstained region: nothing to confirm
        self.assertEqual(c.exception.code, "nothing_to_confirm")
        with self.assertRaises(DentaMindError) as c:
            self.sub(action="bogus")
        self.assertEqual(c.exception.code, "invalid_action")

    def test_duplicates_are_rejected_and_changes_create_revisions_with_history(self):
        first = self.sub()
        with self.assertRaises(DentaMindError) as c:
            self.sub()
        self.assertEqual(c.exception.code, "duplicate_submission")
        second = self.sub(action="correct_class", corrected_class="Impacted")
        self.assertEqual(second["revision"], 2)
        hist = self.store.history("IMG", "IMG:aaaa1111")
        self.assertEqual([h["revision"] for h in hist], [1, 2])
        self.assertEqual([h["is_current"] for h in hist], [False, True])      # the old decision stays in the audit trail
        self.assertEqual(self.store.get(first["id"])["corrected_class"], "Caries")

    def test_approval_needs_a_different_named_person_and_only_open_current_records(self):
        r = self.sub()
        with self.assertRaises(DentaMindError) as c:
            self.store.decide([r["id"]], "reviewer one", True)
        self.assertEqual(c.exception.code, "self_approval")
        with self.assertRaises(DentaMindError):
            self.store.decide([r["id"]], "", True)
        ok = self.store.decide([r["id"]], "Second Person", True)[0]
        self.assertEqual((ok["status"], ok["approved_by"]), ("approved", "Second Person"))
        with self.assertRaises(DentaMindError) as c:
            self.store.decide([r["id"]], "Third Person", True)             # already decided
        self.assertEqual(c.exception.code, "not_open")

    def test_nothing_on_a_non_pool_image_is_exported_or_used_for_training(self):
        r = self.sub()                                                      # IMG is unknown to the dataset -> not usable for training
        self.assertFalse(r["usable_for_training"])
        self.store.decide([r["id"]], "Second Person", True)
        body = json.loads(self.store.export("json")[0])
        self.assertEqual(body["n_records"], 0)
        self.assertEqual(body["n_approved_but_excluded"], 1)
        self.assertEqual(self.store.training_items(self.s)[0], [])
        self.assertIn("never exported", body["exclusion_rule"])

    def test_upload_images_are_eligible_after_approval_and_appear_in_export(self):
        a = full_analysis([region(1)])
        a["image_id"] = "up_test123456"
        self.db.insert("analyses", {"id": new_id("an"), "image_id": "up_test123456", "kind": "full", "model_version": "det-v1", "status": "done", "result_json": jdump(a), "created": now()})
        r = self.store.submit(self.s, {"image_id": "up_test123456", "region_id": "IMG:aaaa1111", "action": "confirm_candidate", "reviewer": "Reviewer One"})
        self.assertTrue(r["usable_for_training"])
        self.assertEqual(json.loads(self.store.export("json")[0])["n_records"], 0)      # still not approved
        self.store.decide([r["id"]], "Second Person", True)
        body = json.loads(self.store.export("json")[0])
        self.assertEqual(body["n_records"], 1)
        self.assertEqual(body["records"][0]["approved_by"], "Second Person")
        self.assertIn("self-declared", body["records"][0]["reviewer_qualification"])
        self.assertIn("review_id", self.store.export("csv")[0])

    def test_image_level_flags_need_no_region(self):
        r = self.sub(action="specialist_review", region_id=None, notes="blurred")
        self.assertIsNone(r["region_id"])
        self.assertFalse(r["usable_for_training"])


if __name__ == "__main__":
    unittest.main()
