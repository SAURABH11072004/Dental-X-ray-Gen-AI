"""Evidence-grounded report drafting.

The generator only ever sees *structured findings produced by models* (``Evidence``). The deterministic
template needs no network. An OpenAI-compatible LLM may rephrase the text, but its JSON output is validated
against the evidence and rejected (falling back to the template) if it introduces unsupported content.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from dentexmodel.data.fdi import is_valid_fdi
from dentexmodel.errors import ExternalServiceError

DISCLAIMER = ("Research draft generated from model outputs. Not a clinical diagnosis and not clinically validated. "
              "Requires review by a qualified professional.")
STATUS_DRAFT = "unconfirmed_research_draft"
STATUS_REVIEWED = "reviewed_research_draft"
DEFAULT_FORBIDDEN = ["diagnos", "prescrib", "recommend", "should be treated", "treatment plan", "extraction",
                     "root canal", "antibiotic", "definitely", "confirmed", "patient has", "suffers"]
LIMITATIONS = ["Findings are model predictions and may be wrong; uncertainty values are not guarantees of correctness.",
               "The classification model has no healthy class and was trained only on teeth labelled with one of four findings; "
               "its closest-class output does not indicate that a tooth is affected.",
               "No clinical history or other examinations were considered.",
               "Tooth numbers marked 'unassigned' or 'needs_review' were not confirmed."]
REQUIRED = ("report_id", "image_id", "model_version", "findings", "summary", "limitations", "status", "disclaimer", "generated_by")


EXTRA_KEYS = ("region_id", "region_no", "numbering_status", "review_reasons", "needs_review", "mask_matched", "mask_iou",
              "segmentation_score", "detection_score", "tta_disagreement", "mask_instability", "detection_instability")


def make_evidence(image_id: str, model_version: str, findings: list, model_versions: dict | None = None, context: dict | None = None) -> dict:
    """Normalise raw findings into an evidence bundle with stable ids (F1, F2, ...).

    ``kind`` is "detection" (a located tooth region, label "tooth") or "closest_class" (the output of a closed-set
    classifier with no healthy class: it names the nearest of its trained findings and does not say a finding is present)."""
    out = []
    for i, f in enumerate(findings, 1):
        out.append({
            "finding_id": f.get("finding_id") or f"F{i}",
            "tooth_fdi": f.get("tooth_fdi"),
            "label": f.get("label"),
            "probability": f.get("probability"),
            "uncertainty": f.get("uncertainty"),
            "evidence_region": f.get("evidence_region") or ({"box": f["box"]} if f.get("box") else None),
            "review_status": f.get("review_status", "unreviewed"),
            "kind": f.get("kind", "closest_class" if f.get("label") not in (None, "tooth") else "detection"),
            **{k: f[k] for k in EXTRA_KEYS if k in f},
        })
    return {"image_id": image_id, "model_version": model_version, "model_versions": model_versions or {"detection": model_version},
            "findings": out, "context": context or {}}


def _fmt(v, nd=2):
    return "n/a" if v is None else f"{float(v):.{nd}f}"


def template_report(evidence: dict, report_id: str | None = None) -> dict:
    fs = evidence["findings"]
    mv = evidence.get("model_versions") or {"detection": evidence["model_version"]}
    lines, notes = [], []
    if not fs:
        lines.append("No model findings were supplied for this image; no statements about the radiograph are made.")
    else:
        lines.append(f"The detection model ({mv.get('detection', evidence['model_version'])}) located {len(fs)} tooth region(s).")
        c = (evidence.get("context") or {}).get("summary_counts")
        if c:
            lines.append(f"Of these, {c['n_numbered']} have a tooth number from the numbering model, {c['n_with_mask']} have a matched segmentation mask, "
                         f"and {c['n_review_required']} are flagged for manual review.")
        if mv.get("segmentation"):
            lines.append(f"Segmentation masks come from the segmentation model ({mv['segmentation']}) and are matched to regions by overlap.")
        if mv.get("numbering"):
            lines.append(f"Tooth numbers (FDI) come from the numbering model ({mv['numbering']}); regions it did not match stay unnumbered.")
        if mv.get("classification"):
            lines.append(f"The classification model ({mv['classification']}) gave each region its closest class among four trained "
                         "findings. It has no healthy class, so a class name here is not a statement that the finding is present.")
    for f in fs:
        tooth = f"tooth {f['tooth_fdi']}" if f.get("tooth_fdi") is not None else "an unnumbered region"
        reasons = ", ".join(r.replace("_", " ") for r in (f.get("review_reasons") or []))
        if f.get("kind") == "abstained":
            txt = (f"{f['finding_id']}: {tooth} - no reliable candidate class (normalised uncertainty {_fmt(f.get('uncertainty'))}); "
                   f"manual review required. Review status: {f.get('review_status')}.")
        elif f.get("kind") == "closest_class":
            txt = (f"{f['finding_id']}: {tooth} - closest trained class '{f.get('label')}' (score {_fmt(f.get('probability'))}, "
                   f"normalised uncertainty {_fmt(f.get('uncertainty'))}); not evidence that the finding is present. "
                   f"Review status: {f.get('review_status')}.")
        else:
            txt = (f"{f['finding_id']}: {tooth} - detected region (detector score {_fmt(f.get('probability'), 3)}). "
                   f"Review status: {f.get('review_status')}.")
        notes.append({"finding_id": f["finding_id"], "text": txt})
    return _assemble(evidence, " ".join(lines), notes, "template", report_id)


def _assemble(evidence: dict, summary: str, notes: list, generated_by: str, report_id: str | None) -> dict:
    note_by = {n["finding_id"]: n["text"] for n in notes}
    return {
        "report_id": report_id or f"RPT-{uuid.uuid4().hex[:10].upper()}",
        "image_id": evidence["image_id"], "model_version": evidence["model_version"],
        "model_versions": evidence.get("model_versions") or {"detection": evidence["model_version"]}, "generated_by": generated_by,
        "status": STATUS_DRAFT, "created": datetime.now(timezone.utc).isoformat(),
        "findings": [{**f, "narrative": note_by.get(f["finding_id"], "")} for f in evidence["findings"]],
        "analysis": evidence.get("context") or {},
        "summary": summary, "limitations": list(LIMITATIONS), "disclaimer": DISCLAIMER,
        "evidence_refs": [f["finding_id"] for f in evidence["findings"]],
    }


def deidentified_payload(evidence: dict) -> dict:
    """Only structured, de-identified content leaves the machine: no image, no path, no original image id."""
    alias = "IMG-" + hashlib.sha256(evidence["image_id"].encode()).hexdigest()[:8]
    return {"image_alias": alias, "model_version": evidence["model_version"],
            "findings": [{k: f.get(k) for k in ("finding_id", "tooth_fdi", "label", "probability", "uncertainty", "review_status", "kind")}
                         for f in evidence["findings"]]}


LLM_SYSTEM = ("You rewrite structured dental-radiograph model findings as a short research draft. Use ONLY the supplied "
              "findings. Entries of kind closest_class come from a classifier with no healthy class: never say a finding is present. Do not add diagnoses, treatment advice, new teeth, new labels or numbers. Return strict JSON: "
              '{"summary": str, "finding_notes": [{"finding_id": str, "text": str}]}')


def llm_report(evidence: dict, settings, vocabulary: list | None = None, transport=None, forbidden=None) -> dict:
    """LLM-assisted draft. ``transport(url, headers, body_dict) -> dict`` is injectable for tests. Output that
    fails validation is rejected and the deterministic template is returned with ``llm_rejection`` details."""
    if not settings.llm_configured:
        raise ExternalServiceError("LLM is not configured.", hint="Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env, or use the template mode.")
    payload = deidentified_payload(evidence)
    body = {"model": settings.llm_model, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": LLM_SYSTEM}, {"role": "user", "content": json.dumps(payload)}]}
    headers = {"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"}
    url = settings.llm_base_url + "/chat/completions"
    try:
        resp = (transport or _http_transport)(url, headers, body)
        content = resp["choices"][0]["message"]["content"]
        data = json.loads(content)
        if not isinstance(data, dict) or not isinstance(data.get("summary"), str) or not isinstance(data.get("finding_notes"), list):
            raise ValueError("LLM JSON missing 'summary' or 'finding_notes'")
    except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        return _rejected(evidence, [f"LLM output was not valid JSON in the required shape: {exc}"])
    notes = [{"finding_id": str(n.get("finding_id")), "text": str(n.get("text", ""))} for n in data["finding_notes"] if isinstance(n, dict)]
    report = _assemble(evidence, data["summary"], notes, "llm", None)
    v = validate_report(report, evidence, vocabulary=vocabulary, forbidden=forbidden)
    if not v["passed"]:
        return _rejected(evidence, v["errors"])
    return report


def _rejected(evidence: dict, reasons: list) -> dict:
    rep = template_report(evidence)
    rep["llm_rejection"] = {"reasons": reasons, "note": "LLM output rejected; deterministic template used instead."}
    return rep


def _http_transport(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ExternalServiceError(f"LLM request failed: {getattr(exc, 'reason', exc)}")


_FDI_RX = re.compile(r"(?<![\d.])([1-8][1-8])(?![\d.%])")
_DEC_RX = re.compile(r"\d+\.\d+")


def validate_report(report: dict, evidence: dict, vocabulary: list | None = None, forbidden: list | None = None,
                    tolerance: float = 1e-6) -> dict:
    errors, warnings = [], []
    missing = [k for k in REQUIRED if k not in report or report[k] in (None, "")]
    if "findings" in report and report["findings"] == [] and not evidence["findings"]:
        missing = [m for m in missing if m != "findings"]
    schema_ok = (not missing and isinstance(report.get("findings"), list) and isinstance(report.get("limitations"), list)
                 and isinstance(report.get("summary"), str) and report.get("generated_by") in ("template", "llm"))
    if missing:
        errors.append(f"missing required fields: {missing}")
    if not schema_ok and not missing:
        errors.append("report fields have the wrong types")
    ev = {f["finding_id"]: f for f in evidence["findings"]}
    refs_ok = True
    for f in report.get("findings", []) if isinstance(report.get("findings"), list) else []:
        e = ev.get(f.get("finding_id"))
        if e is None:
            refs_ok = False
            errors.append(f"finding '{f.get('finding_id')}' has no matching evidence")
            continue
        for k in ("tooth_fdi", "label"):
            if f.get(k) != e.get(k):
                refs_ok = False
                errors.append(f"{f['finding_id']}: {k} {f.get(k)!r} differs from evidence {e.get(k)!r}")
        for k in ("probability", "uncertainty"):
            a, b = f.get(k), e.get(k)
            if (a is None) != (b is None) or (a is not None and abs(float(a) - float(b)) > tolerance):
                refs_ok = False
                errors.append(f"{f['finding_id']}: {k} {a!r} differs from evidence {b!r}")
        if f.get("tooth_fdi") is not None and not is_valid_fdi(f["tooth_fdi"]):
            refs_ok = False
            errors.append(f"{f['finding_id']}: invalid FDI {f['tooth_fdi']}")
    if isinstance(report.get("findings"), list) and len(report["findings"]) != len(ev):
        refs_ok = False
        errors.append(f"report has {len(report['findings'])} findings but evidence has {len(ev)}")
    # the evidence itself must be sane: scores inside [0, 1] and categories the models can actually output
    import math
    norm = lambda x: re.sub(r"[\s_-]+", "", str(x).lower())      # 'Deep Caries' (model output) == 'DeepCaries' (config spelling)
    vocab_l = {norm(v) for v in (vocabulary or [])}
    for f in evidence["findings"]:
        for k in ("probability", "uncertainty"):
            v = f.get(k)
            if v is None:
                continue
            try:
                bad = not (math.isfinite(float(v)) and 0.0 <= float(v) <= 1.0)
            except (TypeError, ValueError):
                bad = True
            if bad:
                refs_ok = False
                errors.append(f"{f.get('finding_id')}: {k} {v!r} is outside the valid range 0-1")
        if vocab_l and f.get("kind") not in ("detection", "abstained") and f.get("label") and norm(f["label"]) not in vocab_l:
            refs_ok = False
            errors.append(f"{f.get('finding_id')}: label {f['label']!r} is not a category the models produce ({', '.join(sorted(vocabulary))})")
    # unsupported-claim scan over all free text
    texts = [report.get("summary", "")] + [f.get("narrative", "") for f in report.get("findings", []) if isinstance(f, dict)]
    blob = " ".join(t for t in texts if isinstance(t, str)).lower()
    claims_ok = True
    for ph in (forbidden or DEFAULT_FORBIDDEN):
        if ph in blob:
            claims_ok = False
            errors.append(f"unsupported/clinical phrase '{ph}' in generated text")
    allowed_teeth = {str(f["tooth_fdi"]) for f in evidence["findings"] if f.get("tooth_fdi") is not None}
    scan = " ".join(t for t in texts if isinstance(t, str))
    versions = [evidence.get("model_version"), report.get("model_version"), evidence.get("image_id"),
                *(evidence.get("model_versions") or {}).values(), *(report.get("model_versions") or {}).values()]
    for token in versions:
        if token:
            scan = scan.replace(str(token), " ")
    scan = re.sub(r"\bF\d+\b", " ", scan)          # finding ids such as F11 are references, not tooth numbers
    scan = re.sub(r"located \d+ tooth region\(s\)", " ", scan)   # the generator's own count, e.g. "located 15 tooth region(s)"
    scan = re.sub(r"Of these, \d+ have a tooth number.*?flagged for manual review\.", " ", scan)   # generator's own counts sentence
    for m in set(_FDI_RX.findall(scan)):
        if m not in allowed_teeth:
            claims_ok = False
            errors.append(f"text mentions tooth {m} which is not in the evidence")
    allowed_nums = {str(len(ev)), str(len(ev) + 1)}
    for f in evidence["findings"]:
        for k in ("probability", "uncertainty"):
            if f.get(k) is not None:
                v = float(f[k])
                allowed_nums |= {f"{v:.1f}", f"{v:.2f}", f"{v:.3f}", f"{v:.4f}"}
    for m in set(_DEC_RX.findall(re.sub(r"\bf\d+\b", " ", blob.replace(str(evidence.get("model_version", "")).lower(), " ")))):
        if m not in allowed_nums:
            claims_ok = False
            errors.append(f"text contains number {m} not supported by the evidence")
    # Finding names the text must not mention unless they are in the evidence. Names of findings that ARE in the evidence are
    # removed from the text first, so 'caries' inside 'Deep Caries' is not mistaken for a separate 'Caries' claim.
    vocab = set()
    for v in vocabulary or []:
        vocab |= {v.lower(), re.sub(r"(?<=[a-z])(?=[A-Z])", " ", v).lower()}      # 'DeepCaries' (config) and 'deep caries' (model output)
    used_text = sorted({str(f["label"]).lower() for f in evidence["findings"] if f.get("label")}, key=len, reverse=True)
    used_norm = {norm(u) for u in used_text}
    scan_blob = blob
    for u in used_text:
        scan_blob = scan_blob.replace(u, " ")
    for v in sorted(vocab):
        if norm(v) in used_norm:
            continue
        if re.search(rf"\b{re.escape(v)}\b", scan_blob):
            claims_ok = False
            errors.append(f"text mentions finding '{v}' that is not in the evidence")
    if report.get("status") not in (STATUS_DRAFT, STATUS_REVIEWED):
        errors.append("report status must be an unconfirmed/reviewed research draft")
    return {"schema_valid": schema_ok, "evidence_refs_valid": refs_ok, "unsupported_claims_free": claims_ok,
            "required_fields_present": not missing, "passed": not errors, "errors": errors, "warnings": warnings}


def mark_reviewed(report: dict, reviewer: str) -> dict:
    if not reviewer or not reviewer.strip():
        raise ValueError("reviewer name is required")
    r = dict(report)
    r["status"], r["reviewed_by"], r["reviewed_at"] = STATUS_REVIEWED, reviewer.strip(), datetime.now(timezone.utc).isoformat()
    return r


def render_html(report: dict) -> str:
    e = html.escape
    rows = "".join(f"<tr><td>{e(str(f.get('finding_id')))}</td><td>{e(str(f.get('tooth_fdi') or 'unassigned'))}</td>"
                   f"<td>{e(str(f.get('label')))}</td><td>{e(str(f.get('probability')))}</td><td>{e(str(f.get('uncertainty')))}</td>"
                   f"<td>{e(str(f.get('review_status')))}</td></tr>" for f in report.get("findings", []))
    lim = "".join(f"<li>{e(x)}</li>" for x in report.get("limitations", []))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(report['report_id'])}</title>
<style>body{{font-family:Inter,Arial,sans-serif;max-width:820px;margin:2rem auto;color:#1C2938}}
.banner{{background:#FEF3C7;border:1px solid #D97706;padding:.6rem 1rem;border-radius:6px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #cbd5e1;padding:.35rem .5rem;text-align:left}}</style></head><body>
<h1>DentaMind AI - Research Draft Report</h1><p class="banner"><b>{e(report['status'].replace('_', ' ').upper())}</b> - {e(report['disclaimer'])}</p>
<p>Report <b>{e(report['report_id'])}</b> | Image <b>{e(report['image_id'])}</b> | Models <b>{e(', '.join(f'{k}: {v}' for k, v in (report.get('model_versions') or {'detection': report['model_version']}).items()))}</b> | Generated by <b>{e(report['generated_by'])}</b></p>
<h2>Summary</h2><p>{e(report['summary'])}</p><h2>Findings</h2>
<table><tr><th>ID</th><th>Tooth (FDI)</th><th>Class</th><th>Score</th><th>Uncertainty</th><th>Review</th></tr>{rows}</table>
<h2>Limitations</h2><ul>{lim}</ul></body></html>"""
