"""Report service: evidence from stored analyses -> template/LLM draft -> validation -> persistence/export."""
from __future__ import annotations

import json

from dentexmodel.errors import DentaMindError, NotFoundError
from dentexmodel.reporting import make_evidence, mark_reviewed, render_html, template_report, validate_report
from dentexmodel.reporting.i18n import (LANGUAGES, localize_report, render_html_localized, render_text_localized,
                                       verify_localization)
from dentexmodel.reporting.reports import llm_report
from dentexmodel.storage import jdump, jload, now


class ReportService:
    def __init__(self, ctx, analysis):
        self.ctx, self.analysis = ctx, analysis

    def _vocab(self) -> list:
        return list((((self.ctx.settings.data_cfg or {}).get("labels") or {}).get("findings") or {}).values())

    def _evidence_from_full(self, a: dict) -> dict:
        """Evidence from a stored full analysis: one finding per region, linked by region id (never by list position)."""
        findings = []
        for r in a["regions"]:
            cc, u = r.get("candidate_class"), r.get("uncertainty", {})
            base = {"tooth_fdi": r.get("fdi"), "evidence_region": {"box": r["box"]}, "review_status": "unreviewed", "region_id": r["region_id"],
                    "region_no": r["region_no"], "numbering_status": r["numbering_status"], "review_reasons": r["review_reasons"],
                    "needs_review": r["review_required"], "detection_score": r["detection_score"], "mask_matched": bool(r.get("mask")),
                    "mask_iou": (r.get("mask") or {}).get("match_iou"), "segmentation_score": (r.get("mask") or {}).get("segmentation_score"),
                    "tta_disagreement": u.get("tta_disagreement"), "mask_instability": u.get("mask_instability"),
                    "detection_instability": u.get("detection_instability")}
            if cc and cc["status"] == "candidate":
                findings.append({**base, "kind": "closest_class", "label": cc["label"], "probability": cc["score"], "uncertainty": u.get("entropy")})
            elif cc:      # abstained: too uncertain to name a candidate
                findings.append({**base, "kind": "abstained", "label": None, "probability": None, "uncertainty": u.get("entropy")})
            else:
                findings.append({**base, "kind": "detection", "label": "tooth", "probability": r["detection_score"], "uncertainty": None})
        versions = {"detection": a["models"]["detection"]}
        for k in ("segmentation", "numbering", "classification"):
            if a["models"].get(k) and (k != "numbering" or any(f["tooth_fdi"] is not None for f in findings)) and (k != "segmentation" or a["summary"]["n_with_mask"]):
                versions[k] = a["models"][k]
        un = a.get("uncertainty") or {}
        ctx = {"analysis_id": a.get("analysis_id"), "summary_counts": {k: a["summary"][k] for k in ("n_regions", "n_numbered", "n_with_mask", "n_review_required", "n_abstained")},
               "image_quality_flags": (a.get("preprocess") or {}).get("quality_flags", []), "combined_uncertainty": un.get("combined_score"),
               "thresholds_provisional": (un.get("thresholds") or {}).get("provisional", True), "steps": [{"step": s["step"], "status": s["status"]} for s in a["steps"]]}
        return make_evidence(a["image_id"], a["models"]["detection"], findings, versions, ctx)

    def _evidence_from_analysis(self, analysis_id: str) -> dict:
        a = self.analysis.get_analysis(analysis_id)
        if a.get("regions") is not None:
            return self._evidence_from_full(a)
        cls = a.get("classification") or {}
        names, probs = cls.get("class_names", []), cls.get("probabilities", [])
        findings = []
        for i, d in enumerate(a.get("detections", [])):
            label, p, unc = d.get("label"), d.get("score"), None
            if i < len(probs) and names:
                import numpy as np
                from dentexmodel.uncertainty import entropy
                pr = np.asarray(probs[i], dtype=float)
                label, p = names[int(pr.argmax())], float(pr.max())
                unc = float(entropy(pr))
            findings.append({"tooth_fdi": d.get("fdi"), "label": label, "probability": p, "uncertainty": unc,
                             "evidence_region": {"box": d["box"]}, "review_status": "unreviewed",
                             "kind": "closest_class" if (i < len(probs) and names) else "detection"})
        versions = {"detection": a["model_version"]}
        nm = a.get("numbering_model") or {}
        if nm.get("model_version") and any(f["tooth_fdi"] is not None for f in findings):
            versions["numbering"] = nm["model_version"]
        if cls.get("model_version") and any(f["kind"] == "closest_class" for f in findings):
            versions["classification"] = cls["model_version"]
        return make_evidence(a["image_id"], a["model_version"], findings, versions)

    def generate(self, payload: dict) -> dict:
        mode = payload.get("mode", "auto")
        if payload.get("analysis_id"):
            evidence = self._evidence_from_analysis(payload["analysis_id"])
        elif payload.get("findings") is not None and payload.get("image_id"):
            evidence = make_evidence(payload["image_id"], payload.get("model_version", "unspecified"), payload["findings"])
        else:
            raise DentaMindError("No model findings to report on.", code="no_evidence",
                                 hint="Run an analysis with an available dental model first (X-ray Analysis page), or supply reviewed findings.")
        vocab = self._vocab()
        s = self.ctx.settings
        use_llm = mode == "llm" or (mode == "auto" and s.llm_configured)
        report = llm_report(evidence, s, vocab) if use_llm else template_report(evidence)
        v = validate_report(report, evidence, vocabulary=vocab)
        if not v["passed"]:  # never present an invalid draft as valid; template drafts should always pass
            report["validation_failed"] = True
        rid = report["report_id"]
        self.ctx.db.insert("reports", {"id": rid, "image_id": report["image_id"], "status": report["status"], "generated_by": report["generated_by"],
                                       "report_json": jdump({"report": report, "evidence": evidence}), "validation_json": jdump(v),
                                       "created": now(), "updated": now()})
        return {"report": report, "validation": v, "evidence": evidence}

    def get(self, report_id: str, lang: str | None = None) -> dict:
        r = self.ctx.db.get("reports", report_id)
        if not r:
            raise NotFoundError(f"Report '{report_id}' not found.")
        d = jload(r["report_json"])
        out = {"report": d["report"], "evidence": d["evidence"], "validation": jload(r["validation_json"])}
        if lang:
            loc = self._localize(d["report"], lang)
            out["localized"] = loc
            out["localization_check"] = verify_localization(d["report"], loc)
        out["languages"] = LANGUAGES
        return out

    def _localize(self, report: dict, lang: str) -> dict:
        try:
            return localize_report(report, lang)
        except ValueError as exc:
            raise DentaMindError(str(exc), code="unsupported_language", hint=f"Use one of: {', '.join(LANGUAGES)}.")

    def list(self) -> list:
        return [{"id": r["id"], "image_id": r["image_id"], "status": r["status"], "generated_by": r["generated_by"], "created": r["created"]}
                for r in self.ctx.db.list("reports", limit=200)]

    def validate(self, report_id: str) -> dict:
        d = self.get(report_id)
        v = validate_report(d["report"], d["evidence"], vocabulary=self._vocab())
        self.ctx.db.update("reports", "id", report_id, {"validation_json": jdump(v), "updated": now()})
        return v

    def review(self, report_id: str, reviewer: str) -> dict:
        d = self.get(report_id)
        if not d["validation"]["passed"]:
            raise DentaMindError("Only reports that pass validation can be marked as reviewed.", code="report_invalid")
        try:
            rep = mark_reviewed(d["report"], reviewer)
        except ValueError as exc:
            raise DentaMindError(str(exc), code="reviewer_required")
        self.ctx.db.update("reports", "id", report_id, {"status": rep["status"], "report_json": jdump({"report": rep, "evidence": d["evidence"]}), "updated": now()})
        return rep

    def export(self, report_id: str, fmt: str, lang: str = "en"):
        d = self.get(report_id, lang)
        loc, check = d["localized"], d["localization_check"]
        if not check["passed"]:       # never export a translation that does not match the English evidence
            raise DentaMindError("The localised report does not match the English report.", code="localization_mismatch",
                                 details={"problems": check["problems"]})
        if fmt == "json":
            return json.dumps({"report": d["report"], "evidence": d["evidence"], "validation": d["validation"],
                               "localized": loc, "localization_check": check}, indent=1, ensure_ascii=False), "application/json; charset=utf-8"
        if fmt == "txt":
            return render_text_localized(loc), "text/plain; charset=utf-8"
        return render_html_localized(loc, check), "text/html; charset=utf-8"
