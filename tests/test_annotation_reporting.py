import json
import unittest

import helpers
from dentexmodel.annotation import AnnotationStore, build_task, labeling_config_xml, parse_labelstudio_export, validate_record
from dentexmodel.annotation.labelstudio import LabelStudioClient
from dentexmodel.errors import DentaMindError, ExternalServiceError
from dentexmodel.reporting import (deidentified_payload, make_evidence, mark_reviewed, render_html, template_report, validate_report)
from dentexmodel.reporting.reports import llm_report

LABELS = ["Caries", "DeepCaries", "Impacted", "PeriapicalLesion"]


def ls_export(image_id="img1", w=2000, h=1000, boxes=None, cancelled=False):
    results = []
    for i, (xywh_pct, label, fdi) in enumerate(boxes if boxes is not None else [((10, 20, 5, 10), "Caries", 16)]):
        x, y, bw, bh = xywh_pct
        results.append({"id": f"r{i}", "from_name": "finding", "to_name": "image", "type": "rectanglelabels", "original_width": w,
                        "original_height": h, "value": {"x": x, "y": y, "width": bw, "height": bh, "rectanglelabels": [label]}})
        if fdi is not None:
            results.append({"id": f"r{i}", "from_name": "tooth_fdi", "to_name": "image", "type": "choices", "value": {"choices": [str(fdi)]}})
    return [{"id": 7, "data": {"image": "http://x", "image_id": image_id}, "annotations": [{"completed_by": 2, "was_cancelled": cancelled, "result": results}]}]


class AnnotationTests(helpers.TmpCase):
    def test_percent_to_pixel_import(self):
        rec = parse_labelstudio_export(ls_export())[0]
        self.assertEqual(rec.boxes[0]["box"], [200.0, 200.0, 300.0, 300.0])
        self.assertEqual(rec.boxes[0]["fdi"], 16)
        self.assertEqual(validate_record(rec, LABELS), [])

    def test_export_roundtrip_with_prediction(self):
        t = build_task("a", "http://u/a.png", 1000, 500, [{"box": [100, 50, 200, 150], "label": "Caries", "fdi": 26, "score": 0.7}], "m1")
        res = t["predictions"][0]["result"]
        rec = parse_labelstudio_export([{"id": 1, "data": t["data"], "annotations": [{"result": res}]}])[0]
        self.assertEqual(rec.boxes[0]["box"], [100.0, 50.0, 200.0, 150.0])
        self.assertNotIn("predictions", build_task("a", "u", 10, 10, None))  # no fake pre-annotations

    def test_cancelled_and_empty_ignored(self):
        self.assertEqual(parse_labelstudio_export(ls_export(cancelled=True)), [])
        self.assertEqual(parse_labelstudio_export([{"id": 1, "data": {"image_id": "a"}, "annotations": []}]), [])

    def test_validation_problems(self):
        bad = parse_labelstudio_export(ls_export(boxes=[((95, 95, 20, 20), "Unknown", 99), ((10, 10, 5, 5), "Caries", 16), ((30, 30, 5, 5), "Caries", 16)]))[0]
        probs = " | ".join(validate_record(bad, LABELS))
        for frag in ("outside image bounds", "unsupported label", "invalid FDI", "duplicate FDI"):
            self.assertIn(frag, probs)

    def test_approval_gate_and_versions(self):
        store = AnnotationStore(self.s.annotations_dir)
        good = parse_labelstudio_export(ls_export("good"))
        bad = parse_labelstudio_export(ls_export("bad", boxes=[((95, 95, 20, 20), "Caries", 16)]))
        summary = store.import_records(good + bad, LABELS)
        self.assertEqual((summary["validated"], summary["with_problems"]), (1, 1))
        self.assertEqual(store.approved_records(), [])                   # nothing trains on unreviewed labels
        with self.assertRaises(DentaMindError):
            store.set_status(["bad"], "approved", "dr")                  # cannot approve an invalid record
        store.set_status(["good"], "approved", "dr")
        self.assertEqual([r["image_id"] for r in store.approved_records()], ["good"])
        v1 = store.create_version("first")
        v2 = store.create_version("second")
        self.assertEqual((v1["version"], v2["version"]), (1, 2))
        self.assertEqual(store.list_versions()[1]["parent"], "annotations_v0001.json")
        store.import_records(good, LABELS)                               # re-import drops approval
        self.assertEqual(store.approved_records(), [])

    def test_label_config_xml(self):
        x = labeling_config_xml(LABELS)
        self.assertIn('<RectangleLabels name="finding"', x)
        self.assertIn('<Choice value="16"/>', x)
        self.assertEqual(x.count("<View>"), 1)
        import xml.dom.minidom
        xml.dom.minidom.parseString(x)  # well-formed

    def test_client_reports_unreachable_service(self):
        c = LabelStudioClient("http://127.0.0.1:1", "token", timeout=0.5)
        self.assertFalse(c.health()["reachable"])
        with self.assertRaises(ExternalServiceError):
            c.import_tasks(1, [])


class ReportTests(unittest.TestCase):
    EV = make_evidence("IMG_A", "det-v1", [{"tooth_fdi": 16, "label": "Caries", "probability": 0.82, "uncertainty": 0.31, "box": [1, 2, 3, 4]},
                                            {"tooth_fdi": None, "label": "Impacted", "probability": 0.4, "uncertainty": 0.9}])

    def test_template_is_valid_and_marked_draft(self):
        r = template_report(self.EV)
        v = validate_report(r, self.EV, vocabulary=LABELS)
        self.assertTrue(v["passed"], v["errors"])
        self.assertEqual(r["status"], "unconfirmed_research_draft")
        self.assertEqual(r["generated_by"], "template")
        self.assertIn("Not a clinical diagnosis", r["disclaimer"])
        narr = " ".join(f["narrative"] for f in r["findings"])
        self.assertIn("unnumbered region", narr)
        self.assertIn("not evidence that the finding is present", narr)      # closest-class output is never a finding
        self.assertEqual(r["model_versions"], {"detection": "det-v1"})

    def test_many_findings_with_ids_like_F11_do_not_trip_the_tooth_number_check(self):
        fs = [{"tooth_fdi": None, "label": "Caries", "probability": 0.5 + i / 100, "uncertainty": 0.5, "box": [1, 2, 3, 4]} for i in range(15)]
        ev = make_evidence("IMG_B", "det-v1", fs, {"detection": "det-v1", "classification": "cls-v2"})
        r = template_report(ev)
        v = validate_report(r, ev, vocabulary=LABELS)
        self.assertTrue(v["passed"], v["errors"])
        self.assertIn("cls-v2", r["summary"])                                  # both models are named
        self.assertNotIn("predicted", r["summary"])

    def test_validator_still_rejects_an_invented_tooth(self):
        r = template_report(self.EV)
        r["summary"] += " Tooth 36 shows a lesion."
        self.assertFalse(validate_report(r, self.EV, vocabulary=LABELS)["passed"])

    def test_detection_only_findings_are_described_as_regions(self):
        ev = make_evidence("IMG_C", "det-v1", [{"label": "tooth", "probability": 0.99, "box": [1, 2, 3, 4]}])
        r = template_report(ev)
        self.assertEqual(ev["findings"][0]["kind"], "detection")
        self.assertIn("detected region", r["findings"][0]["narrative"])
        self.assertTrue(validate_report(r, ev, vocabulary=LABELS)["passed"])

    def test_empty_evidence_makes_no_claims(self):
        ev = make_evidence("I", "m", [])
        r = template_report(ev)
        self.assertTrue(validate_report(r, ev)["passed"])
        self.assertIn("no statements about the radiograph", r["summary"])

    def test_model_version_with_digits_does_not_trip_checks(self):
        ev = make_evidence("I", "unet-v21", [{"tooth_fdi": 16, "label": "Caries", "probability": 0.5, "uncertainty": 0.5}])
        self.assertTrue(validate_report(template_report(ev), ev)["passed"])

    def test_unsupported_claims_rejected(self):
        r = template_report(self.EV)
        for extra, frag in ((" Tooth 26 is affected.", "tooth 26"), (" A root canal is advised.", "root canal"), (" Probability 0.99.", "0.99"),
                            (" Also periapicallesion.", None)):
            r2 = dict(r, summary=r["summary"] + extra)
            v = validate_report(r2, self.EV, vocabulary=LABELS + ["periapicallesion"])
            self.assertFalse(v["passed"], extra)
            if frag:
                self.assertTrue(any(frag in e for e in v["errors"]), v["errors"])
        r3 = dict(r, summary=r["summary"] + " Caries and PeriapicalLesion present.")
        self.assertTrue(any("PeriapicalLesion".lower() in e.lower() for e in validate_report(r3, self.EV, vocabulary=LABELS)["errors"]))

    def test_tampered_evidence_fields_rejected(self):
        r = template_report(self.EV)
        r["findings"][0]["tooth_fdi"] = 17
        r["findings"][1]["probability"] = 0.9
        v = validate_report(r, self.EV)
        self.assertFalse(v["evidence_refs_valid"])
        r = template_report(self.EV); r["findings"].append({"finding_id": "F9"})
        self.assertFalse(validate_report(r, self.EV)["evidence_refs_valid"])

    def test_missing_fields(self):
        r = template_report(self.EV)
        del r["limitations"]; r["status"] = "confirmed"
        v = validate_report(r, self.EV)
        self.assertFalse(v["required_fields_present"] and v["passed"])

    def test_review_flow(self):
        r = mark_reviewed(template_report(self.EV), " Dr X ")
        self.assertEqual(r["status"], "reviewed_research_draft")
        self.assertEqual(r["reviewed_by"], "Dr X")
        with self.assertRaises(ValueError):
            mark_reviewed(r, "  ")
        self.assertTrue(validate_report(r, self.EV)["passed"])

    def test_html_export_escapes(self):
        ev = make_evidence("<script>", "m", [{"tooth_fdi": 11, "label": "Caries", "probability": .5, "uncertainty": .5}])
        h = render_html(template_report(ev))
        self.assertNotIn("<script>", h)
        self.assertIn("UNCONFIRMED RESEARCH DRAFT", h)

    def test_deidentified_payload(self):
        p = deidentified_payload(self.EV)
        blob = json.dumps(p)
        self.assertNotIn("IMG_A", blob)
        self.assertNotIn("box", blob)

    def _settings(self):
        class S:
            llm_configured = True; llm_base_url = "http://llm"; llm_api_key = "k"; llm_model = "m"
        return S()

    def test_llm_good_output_accepted_and_bad_rejected(self):
        good = {"summary": "The model (det-v1) produced 2 structured finding(s).",
                "finding_notes": [{"finding_id": "F1", "text": "F1: tooth 16 - Caries (probability 0.82)."}, {"finding_id": "F2", "text": "F2: Impacted."}]}
        seen = {}
        def transport(url, headers, body):
            seen.update(url=url, body=body)
            return {"choices": [{"message": {"content": json.dumps(good)}}]}
        r = llm_report(self.EV, self._settings(), LABELS, transport=transport)
        self.assertEqual(r["generated_by"], "llm")
        self.assertTrue(seen["url"].endswith("/chat/completions"))
        self.assertNotIn("IMG_A", json.dumps(seen["body"]))        # identifiers never leave the machine
        bad = dict(good, summary="Tooth 36 needs a root canal.")
        r2 = llm_report(self.EV, self._settings(), LABELS, transport=lambda *a: {"choices": [{"message": {"content": json.dumps(bad)}}]})
        self.assertEqual(r2["generated_by"], "template")
        self.assertIn("llm_rejection", r2)
        r3 = llm_report(self.EV, self._settings(), LABELS, transport=lambda *a: {"choices": [{"message": {"content": "not json"}}]})
        self.assertEqual(r3["generated_by"], "template")

    def test_llm_not_configured(self):
        class S:
            llm_configured = False
        with self.assertRaises(ExternalServiceError):
            llm_report(self.EV, S(), LABELS)


if __name__ == "__main__":
    unittest.main()
