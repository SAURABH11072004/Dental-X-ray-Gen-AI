"""Inference orchestration, numbering checks, uncertainty scoring."""
from __future__ import annotations


import numpy as np

from dentexmodel.errors import DentaMindError, NotFoundError
from dentexmodel.inference.tooth_numbering import check_numbering
from dentexmodel.reporting.final_result import final_result, top_class
from dentexmodel.storage import jdump, jload, new_id, now
from dentexmodel.uncertainty import (Signal, UncertaintyRecord, entropy, image_quality, jensen_shannon_disagreement,
                                     mask_instability)
from dentexmodel.data.preprocess import load_gray, resize_keep_aspect
from dentexmodel.utils.geometry import rle_to_mask


class AnalysisService:
    def __init__(self, ctx, images):
        self.ctx, self.images = ctx, images

    def predict(self, image_id: str, model_version: str | None = None, with_classification: bool = True) -> dict:
        """Run the active dental detector (and classifier if available). Raises ModelUnavailableError otherwise."""
        from dentexmodel.inference.torch_models import classify_regions, detect_teeth
        s = self.ctx.settings
        info = self.images.get(image_id)
        img = self.images.load_rgb01(image_id)
        res = detect_teeth(img, image_id, s, model_version)
        dets = [d if isinstance(d, dict) else d.__dict__ for d in res.detections]
        numbering_model = self._number(img, dets)
        cls = None
        if with_classification and dets:
            try:
                cls = classify_regions(img, [d["box"] for d in dets], s)
            except DentaMindError as exc:  # classifier missing is not fatal for detection
                cls = {"unavailable": exc.message, "hint": exc.hint}
        w, h = img.shape[1], img.shape[0]
        teeth = [{"box": d["box"], "fdi": d.get("fdi"), "fdi_confidence": d.get("fdi_confidence")} for d in dets]
        numbering = check_numbering(teeth, w, h)
        out = {"image_id": image_id, "image_size": [w, h], **res.to_dict(), "classification": cls, "numbering": numbering,
               "numbering_model": numbering_model,
               "disclaimer": "Model output for research use; not a diagnosis."}
        aid = new_id("an")
        self.ctx.db.insert("analyses", {"id": aid, "image_id": image_id, "kind": "detection", "model_version": res.model_version,
                                        "status": "done", "result_json": jdump(out), "duration_s": res.duration_s, "created": now()})
        out["analysis_id"] = aid
        return out

    def _number(self, img, dets: list) -> dict:
        """FDI numbers from the registered numbering model, if one exists; otherwise numbers stay unassigned."""
        from dentexmodel.inference.torch_models import number_teeth
        try:
            r = number_teeth(img, dets, self.ctx.settings)
            return {"model_version": r["model_version"], "assigned": r["n_assigned"], "of": r["n_detections"], "note": r["note"]}
        except DentaMindError as exc:
            return {"unavailable": exc.message, "hint": exc.hint}

    def segment(self, image_id: str, model_version: str | None = None) -> dict:
        from dentexmodel.inference.torch_models import segment_teeth
        img = self.images.load_rgb01(image_id)
        res = segment_teeth(img, image_id, self.ctx.settings, None, model_version)
        out = {"image_id": image_id, "image_size": [img.shape[1], img.shape[0]], **res.to_dict()}
        out["numbering_model"] = self._number(img, out["detections"])
        aid = new_id("an")
        self.ctx.db.insert("analyses", {"id": aid, "image_id": image_id, "kind": "segmentation", "model_version": res.model_version,
                                        "status": "done", "result_json": jdump(out), "duration_s": res.duration_s, "created": now()})
        out["analysis_id"] = aid
        return out

    def explain(self, image_id: str, box: list) -> dict:
        """Real Grad-CAM from the classifier (503 if no classifier). The explanation is stored (method, model version, box) so it can be audited."""
        from dentexmodel.inference.torch_models import explain_region
        out = {"image_id": image_id, **explain_region(self.images.load_rgb01(image_id), box, self.ctx.settings)}
        eid = new_id("an")
        meta = {k: v for k, v in out.items() if k != "heatmap_png_base64"}
        self.ctx.db.insert("analyses", {"id": eid, "image_id": image_id, "kind": "explanation", "model_version": out["model_version"], "status": "done",
                                        "result_json": jdump(meta), "created": now()})
        out["explanation_id"] = eid
        out["caveat"] = ("The heatmap shows image regions that influenced this model's score for the target class. It does not show that a disease "
                         "is present, and the classifier has no healthy class.")
        return out

    def overlay_png(self, analysis_id: str, min_score: float = 0.3) -> bytes:
        import io
        from dentexmodel.inference.visualize import draw_detections
        a = self.get_analysis(analysis_id)
        if not a.get("detections") and a.get("regions"):
            # full-pipeline analysis: draw each region with its FDI number (if assigned), its highest-scoring class ("?" = high classifier uncertainty) and a review marker
            dets = []
            for r in a["regions"]:
                parts = [f"#{r['fdi']}" if r.get("fdi") is not None else "no number"]
                tc = top_class(r.get("candidate_class"))
                if tc:
                    parts.append(f"~{tc['label']}" + ("?" if tc["high_uncertainty"] else ""))
                if r.get("review_required"):
                    parts.append("review")
                dets.append({"box": r["box"], "score": r.get("detection_score", 0.0), "label": " ".join(parts)})
            a = {**a, "detections": dets, "classification": None}
        if not a.get("detections"):
            raise NotFoundError("This analysis has no detections to draw.")
        cls = a.get("classification")
        img = draw_detections(self.images.load_rgb01(a["image_id"]), a["detections"],
                              cls if isinstance(cls, dict) and "probabilities" in cls else None, min_score)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def get_analysis(self, analysis_id: str) -> dict:
        row = self.ctx.db.get("analyses", analysis_id)
        if not row:
            raise NotFoundError(f"Analysis '{analysis_id}' not found.")
        out = {**jload(row["result_json"]), "analysis_id": analysis_id}
        if out.get("regions") is not None:      # recomputed from the stored regions so older analyses follow the current rule
            out["final_result"] = final_result(out)
        return out

    # ---- uncertainty ------------------------------------------------------------------------------------
    def quality_for(self, image_id: str) -> dict:
        row = self.ctx.db.get("images", image_id)
        if row and row.get("quality_json"):
            return jload(row["quality_json"])
        gray = load_gray(self.images.resolve_path(image_id))
        small, _ = resize_keep_aspect(gray, 1024)
        return image_quality(small, (self.ctx.settings.data_cfg or {}).get("quality"))

    def score_uncertainty(self, payload: dict) -> dict:
        """Compute whichever uncertainty signals the supplied *model outputs* allow; everything else is
        'unavailable' with a reason. ``payload``: image_id?, probabilities (C,) or (N,C), member_probabilities
        (M,C) or (M,N,C), mask_runs (list of lists of RLE masks)."""
        rec = UncertaintyRecord(image_id=str(payload.get("image_id") or "adhoc"), model_version=payload.get("model_version"))
        probs, members, mask_runs = payload.get("probabilities"), payload.get("member_probabilities"), payload.get("mask_runs")
        try:
            if probs is not None:
                h = entropy(np.asarray(probs, dtype=float))
                rec.entropy = Signal.computed(float(np.mean(h)))
            else:
                rec.entropy = Signal.unavailable("no class probabilities supplied (needs a trained classifier)")
            if members is not None:
                rec.disagreement = Signal.computed(float(np.mean(jensen_shannon_disagreement(np.asarray(members, dtype=float)))))
            else:
                rec.disagreement = Signal.unavailable("needs >= 2 ensemble members")
            if mask_runs:
                vals = [mask_instability([rle_to_mask(m) for m in inst]) for inst in mask_runs if len(inst) >= 2]
                rec.mask_instability = Signal.computed(float(np.mean(vals))) if vals else Signal.unavailable("needs >= 2 mask predictions per instance")
            else:
                rec.mask_instability = Signal.unavailable("no segmentation predictions supplied")
        except (ValueError, TypeError) as exc:
            raise DentaMindError(f"Invalid uncertainty input: {exc}", code="invalid_uncertainty_input")
        rec.detection_instability = Signal.unavailable("needs >= 2 detection runs")
        if payload.get("image_id"):
            try:
                q = self.quality_for(payload["image_id"])
                rec.quality_flags, rec.quality_metrics = q["flags"], q["metrics"]
            except NotFoundError:
                rec.note = "image not found; quality flags unavailable"
        d = rec.to_dict(payload.get("weights"))
        if payload.get("image_id") and rec.combined(payload.get("weights")) is not None:
            self.ctx.db.insert("analyses", {"id": new_id("an"), "image_id": payload["image_id"], "kind": "uncertainty",
                                            "model_version": payload.get("model_version"), "status": "done", "result_json": jdump(d),
                                            "created": now()})
        return d

    def latest_uncertainty(self) -> dict:
        """Newest stored uncertainty record per image (only those computed from model outputs)."""
        out: dict = {}
        for r in reversed(self.ctx.db.list("analyses", where="kind='uncertainty'", limit=5000)):
            out[r["image_id"]] = jload(r["result_json"])
        return out
