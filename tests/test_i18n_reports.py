"""English / Hindi / Marathi report localisation: values, ids, versions and labels must survive translation unchanged."""
import copy
import re
import unittest

import helpers  # noqa: F401  (puts src/ on sys.path)
from dentexmodel.reporting import make_evidence, template_report, validate_report
from dentexmodel.reporting.i18n import (LANGUAGES, localize_report, render_html_localized, render_text_localized,
                                        verify_localization)

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
FINDINGS = [
    {"tooth_fdi": 36, "label": "Caries", "probability": 0.7186642, "uncertainty": 0.5937347, "box": [1, 2, 30, 40], "kind": "closest_class"},
    {"tooth_fdi": None, "label": "Periapical Lesion", "probability": 0.4594810, "uncertainty": 0.7247589, "box": [5, 6, 50, 60], "kind": "closest_class"},
    {"tooth_fdi": None, "label": "tooth", "probability": 0.99912, "box": [7, 8, 70, 80], "kind": "detection"},
]
VERSIONS = {"detection": "dentex_teeth_detection_v1", "classification": "dentex_findings_classification_v1"}


def make_report():
    ev = make_evidence("IMG_X", VERSIONS["detection"], FINDINGS, VERSIONS)
    return template_report(ev), ev


class LocalizationTests(unittest.TestCase):
    def test_english_localisation_is_identical_to_the_validated_template(self):
        rep, ev = make_report()
        loc = localize_report(rep, "en")
        self.assertEqual(loc["summary"], rep["summary"])
        self.assertEqual([f["narrative"] for f in loc["findings"]], [f["narrative"] for f in rep["findings"]])
        self.assertTrue(validate_report(rep, ev)["passed"])

    def test_every_language_preserves_ids_versions_numbers_and_labels(self):
        rep, _ = make_report()
        for lang in LANGUAGES:
            loc = localize_report(rep, lang)
            chk = verify_localization(rep, loc)
            self.assertTrue(chk["passed"], (lang, chk["problems"]))
            text = loc["summary"] + " " + " ".join(f["narrative"] for f in loc["findings"])
            for fid in ("F1", "F2", "F3"):
                self.assertIn(fid, text)
            for v in VERSIONS.values():
                self.assertIn(v, loc["summary"])
            self.assertIn("0.72", text)          # probability 0.7186 -> same rounded value in every language
            self.assertIn("0.59", text)          # normalised uncertainty is carried over too
            self.assertIn("36", text)            # FDI number
            self.assertIn("Caries", loc["findings"][0]["label_display"])      # original class name kept
            self.assertEqual(loc["status"], "unconfirmed_research_draft")

    def test_hindi_and_marathi_are_real_translations_and_stay_research_drafts(self):
        rep, _ = make_report()
        for lang in ("hi", "mr"):
            loc = localize_report(rep, lang)
            self.assertTrue(DEVANAGARI.search(loc["disclaimer"]) and DEVANAGARI.search(loc["summary"]))
            self.assertTrue(DEVANAGARI.search(loc["status_text"]))
            self.assertNotIn("diagnosed", loc["summary"].lower())
            self.assertFalse(loc["translation_reviewed_by_native_dental_professional"])
            self.assertTrue(len(loc["limitations"]) == len(localize_report(rep, "en")["limitations"]))
        self.assertNotEqual(localize_report(rep, "hi")["summary"], localize_report(rep, "mr")["summary"])

    def test_checker_detects_tampering(self):
        rep, _ = make_report()
        loc = localize_report(rep, "hi")
        bad = copy.deepcopy(loc)
        bad["findings"][0]["narrative"] = bad["findings"][0]["narrative"].replace("0.72", "0.99")
        self.assertFalse(verify_localization(rep, bad)["passed"])
        bad = copy.deepcopy(loc)
        bad["findings"][1]["probability"] = 0.9
        self.assertFalse(verify_localization(rep, bad)["passed"])
        bad = copy.deepcopy(loc)
        bad["summary"] = bad["summary"].replace(VERSIONS["classification"], "other_model")
        self.assertFalse(verify_localization(rep, bad)["passed"])

    def test_closest_class_is_never_stated_as_presence_in_any_language(self):
        rep, _ = make_report()
        en = localize_report(rep, "en")["findings"][0]["narrative"]
        self.assertIn("not evidence that the finding is present", en)
        for lang in ("hi", "mr"):
            self.assertIn("प्रमाण" if lang == "hi" else "पुरावा", localize_report(rep, lang)["findings"][0]["narrative"])

    def test_empty_report_makes_no_claims_in_any_language(self):
        ev = make_evidence("I", "m", [])
        rep = template_report(ev)
        for lang in LANGUAGES:
            loc = localize_report(rep, lang)
            self.assertEqual(loc["findings"], [])
            self.assertTrue(verify_localization(rep, loc)["passed"])

    def test_unreviewed_translations_are_labelled_prominently_in_every_output(self):
        rep, ev = make_report()
        en = localize_report(rep, "en")
        self.assertIsNone(en["linguistic_review"])
        self.assertNotIn("linguistic review", render_text_localized(en).lower())
        for lang in ("hi", "mr"):
            loc = localize_report(rep, lang)
            lr = loc["linguistic_review"]
            self.assertEqual(lr["status"], "awaiting_linguistic_review")
            self.assertFalse(loc["translation_reviewed_by_native_dental_professional"])
            self.assertTrue(DEVANAGARI.search(lr["text"]))
            self.assertIn("native-speaking dental professional", lr["text_en"])
            txt = render_text_localized(loc).splitlines()
            self.assertIn(lr["text"], txt[:5])                       # near the top, not only in the footer
            self.assertIn(lr["text_en"], txt[:5])
            html = render_html_localized(loc)
            self.assertIn('data-linguistic-review="awaiting"', html)
            self.assertLess(html.index("data-linguistic-review"), html.index("<h2>"))

    def test_the_label_does_not_change_any_structured_value(self):
        rep, ev = make_report()
        for lang in ("hi", "mr"):
            loc = localize_report(rep, lang)
            self.assertEqual([f["finding_id"] for f in loc["findings"]], [f["finding_id"] for f in rep["findings"]])
            self.assertEqual([f["probability"] for f in loc["findings"]], [f["probability"] for f in rep["findings"]])
            self.assertEqual(loc["model_versions"], rep["model_versions"])

    def test_unsupported_language_is_rejected(self):
        rep, _ = make_report()
        with self.assertRaises(ValueError):
            localize_report(rep, "fr")

    def test_exports_carry_language_tag_and_all_values(self):
        rep, _ = make_report()
        for lang in ("en", "hi", "mr"):
            loc = localize_report(rep, lang)
            html = render_html_localized(loc, verify_localization(rep, loc))
            self.assertIn(f'<html lang="{lang}">', html)
            self.assertIn('charset="utf-8"', html)
            for token in ("F1", "F3", VERSIONS["detection"], "0.72", loc["disclaimer"][:20]):
                self.assertIn(token, html)
            txt = render_text_localized(loc)
            self.assertIn(VERSIONS["classification"], txt)
            self.assertIn(loc["status_text"], txt)


if __name__ == "__main__":
    unittest.main()
