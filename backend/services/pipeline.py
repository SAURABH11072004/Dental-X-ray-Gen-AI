"""Full analysis pipeline: preprocess -> detect -> number -> segment -> match -> classify -> uncertainty.

Everything here is computed from real checkpoint outputs. Regions are linked by IDs and documented spatial matching
(IoU), never by list position. A step that cannot run is reported as ``unavailable``/``failed`` with the reason; later
steps that do not depend on it still run, and a signal that cannot be computed is "unavailable", never 0.

Uncertainty methods (all single-network; none is an ensemble):
* entropy          - normalised Shannon entropy of the classifier softmax for each tooth crop (0 certain .. 1 uniform).
* tta_disagreement - Jensen-Shannon divergence between the classifier's prediction on the crop and on its horizontal flip,
                     normalised by log 2 (2 passes), so it also spans 0..1.
* mask_instability - 1 - IoU between each segmentation mask and the mask the segmenter gives for the horizontally flipped
                     image (flipped back); an instance with no counterpart counts as 1.
* detection_instability - 1 - IoU of each detector box against its best match on the flipped image (unmatched -> reported separately).
Combined score = weighted mean of the available image-level signals (entropy .4, disagreement .4, mask instability .2),
weights renormalised over what is available. Thresholds come from Data/reports/uncertainty_thresholds.json (chosen on the
calibration split by scripts/evaluate_uncertainty.py) and are PROVISIONAL.
"""
from __future__ import annotations

import hashlib
import json
import time

import numpy as np

from dentexmodel.errors import DentaMindError
from dentexmodel.inference.tooth_numbering import check_numbering
from dentexmodel.reporting.final_result import final_result
from dentexmodel.storage import jdump, new_id, now
from dentexmodel.uncertainty import entropy
from dentexmodel.uncertainty.measures import detection_instability, mask_instability
from dentexmodel.uncertainty.record import Signal, UncertaintyRecord
from dentexmodel.utils.geometry import box_iou, mask_iou, mask_to_rle, rle_to_mask

DEFAULT_THRESHOLDS = {"normalised_entropy_ge": 0.40, "tta_disagreement_ge": 0.10, "mask_instability_ge": 0.30, "detection_score_lt": 0.50,
                      "source": "built-in defaults (no calibration report found)", "provisional": True}
MATCH_IOU = 0.5


def _flip(img: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(img[:, ::-1])


def _unflip_box(b, w):
    return [w - b[2], b[1], w - b[0], b[3]]


def region_key(image_id: str, box, version: str) -> str:
    """Stable id from the image, the model version and the box rounded to 8 px (identical reruns give identical ids)."""
    q = ",".join(str(int(round(v / 8.0))) for v in box)
    return hashlib.sha1(f"{image_id}|{version}|{q}".encode()).hexdigest()[:8]


def _greedy_match(a_boxes, b_boxes, thr=MATCH_IOU):
    """Greedy one-to-one IoU matching, best pairs first. Returns {a_index: (b_index, iou)}."""
    pairs = sorted(((box_iou(a, b), i, j) for i, a in enumerate(a_boxes) for j, b in enumerate(b_boxes)), reverse=True)
    out, ua, ub = {}, set(), set()
    for v, i, j in pairs:
        if v < thr:
            break
        if i in ua or j in ub:
            continue
        out[i] = (j, v)
        ua.add(i)
        ub.add(j)
    return out


class PipelineService:
    def __init__(self, ctx, images, analysis):
        self.ctx, self.images, self.analysis = ctx, images, analysis

    # ------------------------------------------------------------------------------------------ thresholds
    def thresholds(self) -> dict:
        p = self.ctx.settings.data_root / "reports" / "uncertainty_thresholds.json"
        t = dict(DEFAULT_THRESHOLDS)
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                t.update(normalised_entropy_ge=d["review_if_any"]["normalised_entropy_ge"],
                         tta_disagreement_ge=d["unstable_under_flip_if"]["tta_disagreement_ge"],
                         source=f"Data/reports/uncertainty_thresholds.json ({d.get('chosen_on')}, model {d.get('model_version')})",
                         provisional=bool(d.get("provisional", True)))
            except (OSError, KeyError, ValueError):
                pass
        return t

    def signal_validation(self) -> dict:
        """What was MEASURED about each signal (read from Data/reports files written by scripts/evaluate_uncertainty.py and evaluate_instability.py).
        Nothing is invented: a signal without a report file is 'not validated'. AUROC is a ranking quality, not a probability."""
        rep = self.ctx.settings.data_root / "reports"

        def load(name):
            try:
                return json.loads((rep / name).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return {}

        def verdict(a):
            return "not validated" if a is None else ("moderate" if a >= 0.7 else ("weak" if a >= 0.6 else "very weak"))
        ue, iv = load("uncertainty_evaluation.json"), load("instability_validation.json")
        t = ue.get("test_split", {})
        out = {"entropy": {"auroc": t.get("auroc_entropy_for_errors"), "against": "classifier errors on ground-truth crops", "split": "test", "n": t.get("n")},
               "disagreement": {"auroc": t.get("auroc_tta_disagreement_for_errors"), "against": "classifier errors on ground-truth crops", "split": "test", "n": t.get("n")},
               "mask_instability": {"auroc": (iv.get("mask_instability") or {}).get("auroc_for_iou_below_0.8"), "against": "mask IoU < 0.8 against the DENTEX polygon", "split": "val", "n": (iv.get("mask_instability") or {}).get("n_regions")},
               "detection_instability": {"auroc": (iv.get("detection_instability") or {}).get("auroc_for_false_positive"), "against": "false-positive boxes", "split": "val",
                                         "n": (iv.get("detection_instability") or {}).get("n_regions"), "n_positives": (iv.get("detection_instability") or {}).get("n_false_positives")}}
        for v in out.values():
            v["verdict"] = verdict(v["auroc"])
        out["calibration"] = {"applied": False, "ece_test": t.get("ece"), "ece_test_after_temperature": t.get("ece_after_temperature_fitted_on_calibration"),
                              "note": "Scores are uncalibrated model scores; temperature scaling was measured but is not applied, and it did not improve calibration on the calibration split."}
        return out

    # ------------------------------------------------------------------------------------------ run
    def run(self, image_id: str, segmentation: bool = True, uncertainty: bool = True) -> dict:
        from dentexmodel.inference.torch_models import classify_regions, detect_teeth, segment_teeth
        s = self.ctx.settings
        steps: list = []
        t_all = time.time()

        def step(name, fn):
            t0 = time.time()
            rec = {"step": name, "status": "ok", "message": "", "seconds": 0.0}
            try:
                out = fn()
            except DentaMindError as exc:
                rec.update(status="unavailable" if exc.status_code == 503 else "failed", message=exc.message + (f" {exc.hint}" if exc.hint else ""))
                out = None
            except Exception as exc:  # noqa: BLE001 - a failed step must not hide the others
                rec.update(status="failed", message=f"{type(exc).__name__}: {exc}")
                out = None
            rec["seconds"] = round(time.time() - t0, 3)
            steps.append(rec)
            return out

        info = self.images.get(image_id)         # NotFoundError propagates: nothing to analyse
        img = self.images.load_rgb01(image_id)
        H, W = img.shape[:2]
        thr = self.thresholds()

        def pre():
            q = self.analysis.quality_for(image_id)
            return {"original_size": [W, H], "original_unchanged": True,
                    "model_input": "original RGB float 0-1 at full resolution (torchvision's transform resizes internally: min_size 800 / max_size 1333); "
                                   "no contrast change is applied to model inputs",
                    "quality_assessment": "grayscale, percentile contrast statistics and aspect-preserving 1024 px resize are used ONLY for quality flags",
                    "quality_flags": q.get("flags", []), "quality_metrics": q.get("metrics", {})}
        preprocess = step("preprocess", pre) or {}

        det_res = step("detect", lambda: detect_teeth(img, image_id, s))
        dets = [dict(d.__dict__) for d in det_res.detections] if det_res else []
        det_version = det_res.model_version if det_res else None
        numbering_model = step("number", lambda: self._number_or_raise(img, dets)) if dets else None
        if dets and numbering_model is None:
            numbering_model = {"unavailable": next((x["message"] for x in steps if x["step"] == "number"), "numbering not run")}
        seg_res = step("segment", lambda: segment_teeth(img, image_id, s)) if (segmentation and dets) else None
        seg = [dict(d.__dict__) for d in seg_res.detections] if seg_res else []

        # ---- match segmentation instances to detections by IoU (documented rule: one-to-one, IoU >= 0.5)
        det_boxes, seg_boxes = [d["box"] for d in dets], [d["box"] for d in seg]
        mm = _greedy_match(det_boxes, seg_boxes) if (dets and seg) else {}
        steps.append({"step": "match", "status": "ok" if (dets and seg) else "skipped", "seconds": 0.0,
                      "message": f"{len(mm)}/{len(dets)} detections matched to a segmentation instance (one-to-one, IoU >= {MATCH_IOU})"
                                 if (dets and seg) else "needs both a detector and a segmenter output"})

        # ---- classification of each detected box (+ flipped copy for TTA disagreement)
        cls = step("classify", lambda: classify_regions(img, det_boxes, s)) if dets else None
        cls_flip = step("classify_tta", lambda: classify_regions(img, det_boxes, s, flip=True)) if (dets and cls and uncertainty) else None
        names = (cls or {}).get("class_names", [])

        # ---- flipped passes for detection / mask instability
        det_flip = seg_flip = None
        if uncertainty and dets:
            imgf = _flip(img)
            r = step("detect_tta", lambda: detect_teeth(imgf, image_id, s))
            det_flip = [{"box": _unflip_box(d.box, W), "score": d.score} for d in r.detections] if r else None
            if seg:
                r2 = step("segment_tta", lambda: segment_teeth(imgf, image_id, s))
                seg_flip = [{"box": _unflip_box(d.box, W), "mask": rle_to_mask(d.mask_rle)[:, ::-1] if d.mask_rle else None} for d in r2.detections] if r2 else None
        det_match_flip = _greedy_match(det_boxes, [d["box"] for d in det_flip]) if det_flip else {}

        numbering = check_numbering([{"box": d["box"], "fdi": d.get("fdi"), "fdi_confidence": d.get("fdi_confidence")} for d in dets], W, H) if dets else {"teeth": []}

        # ---- regions (ordered left->right, top->bottom; the id is content-derived, not positional)
        order = sorted(range(len(dets)), key=lambda i: ((dets[i]["box"][0] + dets[i]["box"][2]) / 2, (dets[i]["box"][1] + dets[i]["box"][3]) / 2))
        regions, ent_vals, tta_vals, mask_vals = [], [], [], []
        for no, i in enumerate(order, 1):
            d = dets[i]
            reg = {"region_id": f"{image_id}:{region_key(image_id, d['box'], det_version or '')}", "region_no": no, "detection_index": i,
                   "box": d["box"], "detection_score": d["score"], "fdi": d.get("fdi"), "fdi_confidence": d.get("fdi_confidence"),
                   "numbering_status": (numbering["teeth"][i]["status"] if i < len(numbering["teeth"]) else "unassigned") if d.get("fdi") is not None else "unassigned",
                   "mask": None, "candidate_class": None, "uncertainty": {}, "flags": [], "review_reasons": []}
            if i in mm:
                j, v = mm[i]
                reg["mask"] = {"segmentation_index": j, "match_iou": round(v, 4), "segmentation_score": seg[j]["score"], "area": seg[j].get("area"), "mask_rle": seg[j].get("mask_rle")}
            elif seg:
                reg["flags"].append("no_matching_mask")
            u = reg["uncertainty"]
            if cls and cls["probabilities"][i] is not None and not np.all(np.isfinite(np.asarray(cls["probabilities"][i], float))):
                reg["flags"].append("invalid_classifier_output")      # NaN / inf scores: no class or entropy is derived from them
            elif cls and cls["probabilities"][i] is not None:
                p = np.asarray(cls["probabilities"][i], float)
                h = float(entropy(p))
                u["entropy"] = h
                ent_vals.append(h)
                top = int(p.argmax())
                reg["candidate_class"] = {"label": names[top], "score": float(p[top]), "probabilities": dict(zip(names, p.tolist())),
                                          "kind": "closest of the trained classes; the classifier has no healthy class, so this is not a finding",
                                          "status": "candidate"}
                if cls_flip and cls_flip["probabilities"][i] is not None:
                    q = np.asarray(cls_flip["probabilities"][i], float)
                    m = (p + q) / 2
                    hh = lambda a: float(-(a * np.log(a + 1e-12)).sum())
                    js = max(hh(m) - (hh(p) + hh(q)) / 2, 0.0) / np.log(2)
                    u["tta_disagreement"] = js
                    tta_vals.append(js)
                    reg["candidate_class"]["flip_top_class"] = names[int(q.argmax())]
                if h >= thr["normalised_entropy_ge"]:
                    reg["flags"].append("high_entropy")
                if u.get("tta_disagreement", 0) >= thr["tta_disagreement_ge"]:
                    reg["flags"].append("unstable_under_flip")
            if seg_flip is not None and reg["mask"]:
                primary = rle_to_mask(reg["mask"]["mask_rle"]) if reg["mask"]["mask_rle"] else None
                fm = _greedy_match([seg[reg["mask"]["segmentation_index"]]["box"]], [x["box"] for x in seg_flip])
                other = seg_flip[fm[0][0]]["mask"] if 0 in fm else None
                if primary is not None:
                    inst = mask_instability([primary, other if other is not None else np.zeros_like(primary)])
                    u["mask_instability"] = inst
                    mask_vals.append(inst)
                    if inst >= thr["mask_instability_ge"]:
                        reg["flags"].append("mask_unstable")
            if det_flip is not None:
                u["detection_instability"] = (1 - det_match_flip[i][1]) if i in det_match_flip else None
                if i not in det_match_flip:
                    reg["flags"].append("not_found_on_flipped_image")
            if d["score"] < thr["detection_score_lt"]:
                reg["flags"].append("low_detection_score")
            if reg["numbering_status"] == "unassigned":
                reg["flags"].append("unassigned_tooth_number")
            elif reg["numbering_status"] != "assigned":
                reg["flags"].append("tooth_number_needs_review")
            reasons = [f for f in reg["flags"] if f in ("high_entropy", "unstable_under_flip", "mask_unstable", "no_matching_mask", "low_detection_score",
                                                       "tooth_number_needs_review", "not_found_on_flipped_image", "invalid_classifier_output")]
            reg["review_reasons"] = reasons
            reg["review_required"] = bool(reasons) or reg["numbering_status"] == "unassigned"
            if reg["candidate_class"] and ("high_entropy" in reg["flags"]):
                reg["candidate_class"]["status"] = "abstained"       # high classifier uncertainty: class still shown, flagged for human review
            regions.append(reg)

        # ---- image-level uncertainty record (saved for the Uncertainty page and active learning)
        rec = UncertaintyRecord(image_id=image_id, model_version=det_version)
        why = lambda k, default: default
        rec.entropy = Signal.computed(np.mean(ent_vals)) if ent_vals else Signal.unavailable("no classifier output for any region" if not cls else "no region could be cropped")
        if tta_vals:
            rec.disagreement = Signal.computed(np.mean(tta_vals))
        else:
            rec.disagreement = Signal.unavailable("flip-TTA needs the classifier and the uncertainty option" if cls else "needs a classifier output")
        rec.mask_instability = Signal.computed(np.mean(mask_vals)) if mask_vals else Signal.unavailable(
            "needs a segmentation checkpoint and matched instances" if not seg else "flipped-image segmentation did not run")
        di = [r["uncertainty"]["detection_instability"] for r in regions if r["uncertainty"].get("detection_instability") is not None]
        rec.detection_instability = Signal.computed(np.mean(di)) if di else Signal.unavailable("needs a detector output and the uncertainty option")
        rec.quality_flags, rec.quality_metrics = preprocess.get("quality_flags", []), preprocess.get("quality_metrics", {})
        rec.methods = {"entropy": "mean over regions of normalised Shannon entropy of the classifier softmax (uncalibrated model scores)",
                       "disagreement": "flip test-time augmentation: Jensen-Shannon divergence between crop and flipped crop, normalised by log 2; NOT an ensemble",
                       "mask_instability": "1 - IoU between each mask and the mask predicted on the horizontally flipped image (flipped back)",
                       "detection_instability": "1 - IoU of each box against its best match on the flipped image; excluded from the combined score by default",
                       "combined": "weighted mean of available {entropy .4, disagreement .4, mask_instability .2}, weights renormalised; unavailable signals are never zero"}
        rec_dict = rec.to_dict()
        rec_dict["thresholds"] = thr
        rec_dict["signal_validation"] = self.signal_validation()

        ok_steps = [x for x in steps if x["status"] in ("ok", "skipped")]
        result = {
            "image_id": image_id, "image_size": [W, H], "created": now(), "steps": steps,
            "models": {"detection": det_version, "segmentation": seg_res.model_version if seg_res else None,
                       "numbering": (numbering_model or {}).get("model_version"), "classification": (cls or {}).get("model_version")},
            "preprocess": preprocess, "numbering_model": numbering_model, "regions": regions,
            "summary": {"n_regions": len(regions), "n_numbered": sum(1 for r in regions if r["fdi"] is not None),
                        "n_with_mask": sum(1 for r in regions if r["mask"]), "n_review_required": sum(1 for r in regions if r["review_required"]),
                        "n_abstained": sum(1 for r in regions if (r["candidate_class"] or {}).get("status") == "abstained"),
                        "all_steps_ok": len(ok_steps) == len(steps), "seconds": round(time.time() - t_all, 2)},
            "uncertainty": rec_dict, "classification_limitations": (cls or {}).get("limitations", []),
            "disclaimer": "Model output for research use; candidate classes are not findings and nothing here is a diagnosis.",
        }
        result["final_result"] = final_result(result)       # image-level result shown across the app (finding / healthy / error)
        aid = new_id("an")
        self.ctx.db.insert("analyses", {"id": aid, "image_id": image_id, "kind": "full", "model_version": det_version, "status": "done" if result["summary"]["all_steps_ok"] else "partial",
                                        "result_json": jdump(result), "duration_s": result["summary"]["seconds"], "created": now()})
        if rec_dict.get("combined_score") is not None or rec.available():
            rec_dict["analysis_id"] = aid
            self.ctx.db.insert("analyses", {"id": new_id("an"), "image_id": image_id, "kind": "uncertainty", "model_version": det_version, "status": "done",
                                            "result_json": jdump(rec_dict), "created": now()})
        result["analysis_id"] = aid
        return result

    def _number_or_raise(self, img, dets):
        from dentexmodel.inference.torch_models import number_teeth
        r = number_teeth(img, dets, self.ctx.settings)
        return {"model_version": r["model_version"], "assigned": r["n_assigned"], "of": r["n_detections"], "note": r["note"]}

    # ------------------------------------------------------------------------------------------ pool scoring job
    def score_pool(self, image_ids: list) -> dict:
        """Run the uncertainty pipeline over ``image_ids`` (used by active learning). Failures are recorded per image."""
        done, failed = [], []
        for iid in image_ids:
            try:
                r = self.run(iid, segmentation=True, uncertainty=True)
                done.append({"image_id": iid, "combined_score": r["uncertainty"].get("combined_score")})
            except DentaMindError as exc:
                failed.append({"image_id": iid, "error": exc.message})
        return {"scored": len(done), "failed": failed, "results": done}
