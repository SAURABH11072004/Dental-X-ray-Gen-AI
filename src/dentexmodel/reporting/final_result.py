"""Image-level final result shown everywhere in the app (analysis page, home, review, reports).

Rule (project decision 2026-10-15, revised 2026-10-16):
* ``finding``  - at least one detected tooth has a valid classifier output: show, for every such tooth, the class with
                 the highest raw model score, the score and tooth / region information.
* ``healthy``  - no longer produced (it only appears in reports saved before 2026-10-16). High classifier uncertainty
                 (status "abstained") is NOT a reason to call a tooth healthy: those teeth are listed with their
                 highest-scoring class and ``high_uncertainty`` set, and are shown as
                 "Needs human review — high classifier uncertainty".
* ``error``    - tooth detection or finding classification failed / was unavailable, or no tooth has a valid
                 classifier output. A failed analysis is never shown as Healthy.
* ``no_teeth`` - detection ran but found no tooth, so nothing could be assessed (not shown as Healthy either).

The entropy rule and its threshold are unchanged: they still set status "abstained" and the review flag; they only no
longer hide the highest-scoring class. Scores are raw (uncalibrated) model outputs and are never invented: a missing or
invalid score vector gives no class (:func:`top_class` returns None).
The function is pure and works on stored analyses created before it existed, so no database migration is needed.
"""
from __future__ import annotations

import math

HEALTHY_LABEL = "Healthy — No Finding Detected"
FINDING_LABEL = "Finding detected"
ERROR_LABEL = "Analysis error"
NO_TEETH_LABEL = "No teeth detected"
CLASS_ORDER = ("Caries", "Deep Caries", "Impacted", "Periapical Lesion")
HIGH_UNCERTAINTY_TEXT = "Needs human review — high classifier uncertainty"


def _valid_score(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0


def top_class(cc) -> dict | None:
    """Highest raw model score among the trained classes of one region's classifier output (``candidate_class``).

    Returns {"label", "score", "scores", "high_uncertainty"}, or None when there is no output or any score is missing,
    non-numeric, non-finite or outside 0-1 (nothing is invented). Status "candidate" and "abstained" are treated alike;
    ``high_uncertainty`` is True for "abstained" (entropy at or above the unchanged review threshold).
    Ties keep the first class in the model's order, as numpy argmax does in the pipeline."""
    if not isinstance(cc, dict):
        return None
    scores = cc.get("probabilities")
    if not isinstance(scores, dict) or not scores or not all(_valid_score(v) for v in scores.values()):
        return None
    names = list(scores)
    label = max(names, key=lambda k: (scores[k], -names.index(k)))
    return {"label": label, "score": float(scores[label]), "scores": {k: float(v) for k, v in scores.items()},
            "high_uncertainty": cc.get("status") == "abstained"}


def _out(status: str, label: str, message: str = "", findings: list | None = None, **extra) -> dict:
    findings = findings or []
    counts: dict = {}
    for f in findings:
        counts[f["label"]] = counts.get(f["label"], 0) + 1
    counts = {k: counts[k] for k in sorted(counts, key=lambda c: (CLASS_ORDER.index(c) if c in CLASS_ORDER else 99, c))}
    return {"status": status, "label": label, "message": message, "findings": findings, "counts": counts, **extra}


def _step_problem(steps: list, name: str):
    """None if the step ran ok; otherwise a short reason. A missing step counts as not run."""
    rec = next((s for s in steps if s.get("step") == name), None)
    if rec is None:
        return "did not run"
    if rec.get("status") != "ok":
        return f"{rec.get('status')}{': ' + rec['message'] if rec.get('message') else ''}"
    return None


def final_result(analysis: dict) -> dict | None:
    """Final result of a stored *full* analysis (``regions`` present). Returns None for other analysis kinds."""
    if not isinstance(analysis, dict) or analysis.get("regions") is None:
        return None
    steps = analysis.get("steps") or []
    regions = analysis["regions"]
    n = {"n_regions": len(regions)}
    p = _step_problem(steps, "detect")
    if p:
        return _out("error", ERROR_LABEL, f"Tooth detection failed ({p}). No result is given for this image.", **n)
    if not regions:
        return _out("no_teeth", NO_TEETH_LABEL, "The detector found no teeth, so this image could not be assessed.", **n)
    p = _step_problem(steps, "classify")
    if p:
        return _out("error", ERROR_LABEL, f"Finding classification failed ({p}). No result is given for this image.", **n)
    classified = [r for r in regions if r.get("candidate_class")]
    if not classified:
        return _out("error", ERROR_LABEL, "No detected tooth could be classified. No result is given for this image.", **n)
    findings = []
    for r in sorted(regions, key=lambda r: r.get("region_no") or 0):
        tc = top_class(r.get("candidate_class"))
        if tc:
            findings.append({"label": tc["label"], "score": tc["score"], "fdi": r.get("fdi"), "region_no": r.get("region_no"),
                             "region_id": r.get("region_id"), "high_uncertainty": tc["high_uncertainty"],
                             "needs_review": bool(r.get("review_required")) or tc["high_uncertainty"]})
    n["n_abstained"] = sum(1 for r in classified if (r.get("candidate_class") or {}).get("status") == "abstained")
    n["n_high_uncertainty"] = sum(1 for f in findings if f["high_uncertainty"])
    n["n_invalid_class_output"] = len(classified) - len(findings)
    if findings:
        return _out("finding", FINDING_LABEL, "", findings, **n)
    return _out("error", ERROR_LABEL, "The classifier output was missing or invalid for every detected tooth. No result is given for this image.", **n)


def final_result_from_evidence(evidence: dict) -> dict:
    """Final result for a report: taken from the analysis when stored there, otherwise derived from the evidence findings."""
    ctx = evidence.get("context") or {}
    if ctx.get("final_result"):
        return ctx["final_result"]
    steps = ctx.get("steps") or []
    fs = evidence.get("findings") or []
    if steps:
        p = _step_problem(steps, "detect")
        if p:
            return _out("error", ERROR_LABEL, f"Tooth detection failed ({p}). No result is given for this image.", n_regions=len(fs))
    if not fs:
        return _out("no_teeth", NO_TEETH_LABEL, "No tooth regions were supplied, so this image could not be assessed.", n_regions=0)
    if steps:
        p = _step_problem(steps, "classify")
        if p:
            return _out("error", ERROR_LABEL, f"Finding classification failed ({p}). No result is given for this image.", n_regions=len(fs))
    if not any(f.get("kind") in ("closest_class", "abstained", "class_unavailable") for f in fs):
        return _out("error", ERROR_LABEL, "No detected tooth could be classified. No result is given for this image.", n_regions=len(fs))
    findings = [{"label": f["label"], "score": f.get("probability"), "fdi": f.get("tooth_fdi"), "region_no": f.get("region_no"),
                 "region_id": f.get("region_id"), "finding_id": f.get("finding_id"), "high_uncertainty": bool(f.get("high_uncertainty")),
                 "needs_review": bool(f.get("needs_review")) or bool(f.get("high_uncertainty"))}
                for f in fs if f.get("kind") == "closest_class" and f.get("label") and _valid_score(f.get("probability"))]
    extra = {"n_regions": len(fs), "n_abstained": sum(1 for f in fs if f.get("kind") == "abstained" or f.get("high_uncertainty")),
             "n_high_uncertainty": sum(1 for f in findings if f["high_uncertainty"])}
    if findings:
        return _out("finding", FINDING_LABEL, "", findings, **extra)
    if any(f.get("kind") == "abstained" for f in fs):      # legacy evidence (before 2026-10-16): abstained entries carry no scores
        return _out("error", ERROR_LABEL, "The classifier was highly uncertain for every detected tooth and this older record does not "
                    "store its class scores. Needs human review; no result is given for this image.", **extra)
    return _out("error", ERROR_LABEL, "The classifier output was missing or invalid for every detected tooth. No result is given for this image.", **extra)
