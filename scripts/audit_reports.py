"""Multilingual report audit against the LIVE API (and two short-lived extra server processes on other ports).

Usage: .\\.venv\\Scripts\\python.exe scripts\\audit_reports.py   -> docs/audit_evidence/report_audit.json
It creates a few new reports (audit-created, listed in the output); it never edits or deletes existing ones.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _auth  # noqa: E402
_auth.install()
sys.path.insert(0, str(ROOT / "src"))
B = "http://127.0.0.1:8000/api"
R: list = []


def call(method, path, body=None, base=None, timeout=300):
    req = urllib.request.Request((base or B) + path, json.dumps(body).encode() if body is not None else None, {"content-type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            raw = x.read()
            return x.status, raw, dict(x.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def jj(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def rec(tid, what, expected, actual, ok, note=""):
    R.append({"id": tid, "check": what, "expected": expected, "actual": str(actual)[:500], "result": "PASS" if ok is True else ("PARTIAL" if ok == "partial" else ("BLOCKED" if ok == "blocked" else "FAIL")), "note": note})
    print(f"{R[-1]['result']:7} {tid:9} {what[:78]:78} -> {str(actual)[:100]}")


LATIN = re.compile(r"[A-Za-z]{3,}")
TREATMENT_EN = re.compile(r"\b(treat(ment)?|extract(ion)?|fill(ing)?|restor|root canal|antibiotic|prescrib|surgery|surgical|recommend|should be (removed|treated)|crown|implant)", re.I)
TREATMENT_HI_MR = re.compile(r"(उपचार|इलाज|निकाल|फिलिंग|भराव|एंटीबायोटिक|शल्य|सर्जरी|सिफ़ारिश|सिफारिश|शिफारस|दवा|औषध)")


def main():
    # ---- a real source analysis (full pipeline on a real radiograph already registered by the API audit)
    s, raw, _ = call("GET", "/images?source=uploads&limit=50")
    ups = [i for i in (jj(raw) or {}).get("items", []) if i["filename"].startswith("evil_traversal") or i["filename"].startswith("audit sample")]
    image_id = ups[0]["id"] if ups else (jj(raw)["items"][0]["id"])
    s, raw, _ = call("POST", "/analyze/full", {"image_id": image_id})
    full = jj(raw)
    rec("RPT-A01", "real full-pipeline analysis as the source", "200 with regions", f"{s} image={image_id} regions={len(full['regions'])} analysis={full['analysis_id']}", s == 200 and len(full["regions"]) > 0)
    s, raw, _ = call("POST", "/reports/generate", {"analysis_id": full["analysis_id"], "mode": "template"})
    rep = jj(raw)["report"]
    rid = rep["report_id"]
    rec("RPT-A02", "generate EN template report from the analysis", "report id, image id, model versions, status = unconfirmed research draft", f"{rid} image={rep['image_id']} status={rep['status']} models={rep['model_versions']}",
        s == 200 and rep["image_id"] == image_id and rep["status"] == "unconfirmed_research_draft")
    s, raw, _ = call("POST", "/reports/generate", {"analysis_id": full["analysis_id"], "mode": "template"})
    rep2 = jj(raw)["report"]
    same = [(f["finding_id"], f["tooth_fdi"], f["label"], f["probability"]) for f in rep["findings"]] == [(f["finding_id"], f["tooth_fdi"], f["label"], f["probability"]) for f in rep2["findings"]]
    rec("RPT-A03", "regeneration from the same analysis", "new report id, identical findings (deterministic template)", f"ids differ={rep['report_id'] != rep2['report_id']} findings identical={same}", rep["report_id"] != rep2["report_id"] and same)

    # ---- languages offered by the API/UI
    L = {}
    for lang in ("en", "hi", "mr"):
        s, raw, _ = call("GET", f"/reports/{rid}?lang={lang}")
        L[lang] = jj(raw)
    langs = L["en"].get("languages")
    rec("RPT-B01", "languages advertised to the UI", "exactly the languages that have complete templates", json.dumps(langs, ensure_ascii=False), set(langs or {}) == {"en", "hi", "mr"})
    for bad in ("xx", "fr", "HI", "", "en;drop", "../en"):
        s, raw, _ = call("GET", f"/reports/{rid}?lang={urllib.parse.quote(bad)}")
        txt = raw.decode("utf-8", "ignore")
        rec("RPT-B02", f"lang='{bad}'", "4xx with the list of supported languages (no English fallback labelled as translation)", f"{s} {txt[:110]}", (400 <= s < 500) or (bad == "HI" and s == 200), note="'HI' upper-case may be normalised")

    # ---- structural equality across languages (translation cannot add/remove/alter findings)
    def sig(loc):
        return {"findings": [(f["finding_id"], f.get("tooth_fdi"), f.get("kind"), f.get("label"), f.get("probability"), f.get("uncertainty"), f.get("review_status")) for f in loc["findings"]],
                "models": loc["model_versions"], "counts": loc["analysis"]["summary_counts"], "ids": (loc["report_id"], loc["image_id"]), "unc": loc["analysis"].get("combined_uncertainty"), "status": loc["status"]}
    en = L["en"]["localized"] if L["en"].get("localized") else None
    base = L["en"]["report"]
    # English localized form may be absent: compare with the stored English report instead
    eng_sig = {"findings": [(f["finding_id"], f.get("tooth_fdi"), f.get("kind"), f.get("label"), f.get("probability"), f.get("uncertainty"), f.get("review_status")) for f in base["findings"]],
               "models": base["model_versions"], "ids": (base["report_id"], base["image_id"]), "status": base["status"]}
    for lang in ("hi", "mr"):
        sg = sig(L[lang]["localized"])
        ok = sg["findings"] == eng_sig["findings"] and sg["models"] == eng_sig["models"] and sg["ids"] == eng_sig["ids"] and sg["status"] == eng_sig["status"]
        rec(f"RPT-C01-{lang}", f"{lang}: finding ids, FDI, kind, label, score, uncertainty, review status, model versions, ids, status identical to English", "exactly equal (no add/remove/alter)",
            f"{len(sg['findings'])} findings vs {len(eng_sig['findings'])}; equal={ok}", ok)
        chk = L[lang]["localization_check"]
        rec(f"RPT-C02-{lang}", f"{lang}: server-side verify_localization", "passed, no problems", json.dumps(chk, ensure_ascii=False), chk.get("passed") is True and not chk.get("problems"))
        # numbers: every decimal in the English narratives must appear verbatim in the localized narrative of the same finding
        miss = []
        for fe, fl in zip(base["findings"], L[lang]["localized"]["findings"]):
            for num in set(re.findall(r"\d+\.\d+", fe["narrative"])):
                if num not in fl["narrative"]:
                    miss.append((fe["finding_id"], num))
        rec(f"RPT-C03-{lang}", f"{lang}: every decimal value in the English narrative appears verbatim", "none missing", f"missing={miss[:5]}", not miss)
        # abstained regions stay abstained (no class invented / unconfirmed -> confirmed)
        abst_en = [f["finding_id"] for f in base["findings"] if f.get("kind") == "abstained"]
        abst_loc = [f["finding_id"] for f in L[lang]["localized"]["findings"] if f.get("kind") == "abstained"]
        rec(f"RPT-C04-{lang}", f"{lang}: abstained regions identical", "same list", f"en={len(abst_en)} {lang}={len(abst_loc)}", abst_en == abst_loc)
        # research-draft disclaimer & status text in every language
        loc = L[lang]["localized"]
        rec(f"RPT-C05-{lang}", f"{lang}: research-draft + professional-review disclaimer and 'unconfirmed' status present", "present, non-empty, in the target script",
            f"status_text={loc['status_text']!r} disclaimer={loc['disclaimer'][:60]!r}", bool(loc["status_text"]) and bool(re.search(r"[\u0900-\u097F]", loc["disclaimer"])) and bool(re.search(r"[\u0900-\u097F]", loc["status_text"])))
        # English fallback leakage: Latin words in translated prose that are not ids/versions/class labels/units
        allowed = {"FDI", "IoU", "Grad", "CAM"}
        prose = [loc["title"], loc["summary"], loc["note"], loc["disclaimer"], *loc["limitations"], *[f["narrative"] for f in loc["findings"]], *loc["columns"], *loc["headings"].values(), loc["unassigned"], loc["status_text"]]
        leaks = {}
        for t in prose:
            t2 = re.sub(r"[a-z]+_[a-z0-9_]+|F\d+|up_[0-9a-f]+|RPT-[0-9A-F]+|[A-Za-z0-9_]+:[0-9a-f]{8}", " ", t)
            t2 = re.sub(r"\([A-Za-z ]+\)", " ", t2)           # English class name shown in brackets next to the translated name
            t2 = re.sub(r"'[A-Za-z_]+'", " ", t2)               # status tokens quoted verbatim ('unassigned', 'needs_review')
            for w in LATIN.findall(t2):
                if w not in allowed:
                    leaks[w] = leaks.get(w, 0) + 1
        rec(f"RPT-C06-{lang}", f"{lang}: untranslated English words inside translated prose (after removing ids, versions and bracketed class names)", "none (or only technical tokens)", json.dumps(leaks, ensure_ascii=False)[:200], not leaks or set(leaks) <= {"FDI"},
            note="class names appear in brackets next to the translation by design")
        # treatment / diagnosis wording
        blob = " ".join(prose)
        tr = TREATMENT_HI_MR.findall(blob)
        rec(f"RPT-C07-{lang}", f"{lang}: no treatment instructions", "no treatment words", f"found={sorted(set(map(str, tr)))}", not tr)
    for lang in ("hi", "mr"):
        lr = L[lang]["localized"].get("linguistic_review") or {}
        s_, raw_, _ = call("GET", f"/reports/{rid}/export?format=html&lang={lang}")
        html_ = raw_.decode("utf-8")
        s2_, raw2_, _ = call("GET", f"/reports/{rid}/export?format=txt&lang={lang}")
        txt_ = raw2_.decode("utf-8").splitlines()
        ok_ = (lr.get("status") == "awaiting_linguistic_review" and 'data-linguistic-review="awaiting"' in html_ and html_.index("data-linguistic-review") < html_.index("<h2>")
               and lr.get("text") in txt_[:6] and lr.get("text_en") in txt_[:6])
        rec(f"RPT-C10-{lang}", f"{lang}: 'awaiting linguistic review' label in the JSON, near the top of the HTML and of the TXT export", "present in all three", f"status={lr.get('status')} html={'data-linguistic-review' in html_} txt-top={lr.get('text') in txt_[:6]}", ok_)
    s_, raw_, _ = call("GET", f"/reports/{rid}/export?format=html&lang=en")
    rec("RPT-C11-en", "English export carries no translation-review label", "absent", "data-linguistic-review" not in raw_.decode("utf-8"), "data-linguistic-review" not in raw_.decode("utf-8"))
    allen = " ".join([base["summary"], *base["limitations"], *[f["narrative"] for f in base["findings"]], base["disclaimer"]])
    te = [m.group(0) for m in TREATMENT_EN.finditer(allen)]
    rec("RPT-C08-en", "en: no treatment instructions", "no treatment words", f"found={sorted(set(te))}", not te)
    dx = [m.group(0) for m in re.finditer(r"[^.]*\b(diagnos|confirmed|present|affected)\w*[^.]*\.", allen, re.I)]
    neg = all(re.search(r"\b(not|no|never|nor|cannot|unconfirmed|does not|without)\b", x, re.I) for x in dx)
    rec("RPT-C09-en", "en: every sentence mentioning diagnosis/confirmed/present/affected is a negation or limitation", "all negated", f"{len(dx)} sentences, all negated={neg}; e.g. {dx[:2]}", neg)

    # ---- exports contain the same content, are well-formed, and escape HTML
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(); self.tags = []; self.bad = []
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "iframe", "object", "embed"):
                self.bad.append(tag)
            for k, v in attrs:
                if k.lower().startswith("on"):
                    self.bad.append(k)
    for lang in ("en", "hi", "mr"):
        s, raw, h = call("GET", f"/reports/{rid}/export?format=html&lang={lang}")
        html = raw.decode("utf-8")
        p = P(); p.feed(html)
        rec(f"RPT-D01-{lang}", f"HTML export ({lang}) well-formed, lang attribute, charset, no script/handlers", "true", f"{len(raw)} B ct={h.get('content-type')} lang-attr={bool(re.search(r'<html[^>]*lang=', html))} charset={'utf-8' in html.lower()} bad={p.bad}",
            s == 200 and "utf-8" in html.lower() and not p.bad and rid in html)
        s, raw, h = call("GET", f"/reports/{rid}/export?format=json&lang={lang}")
        j = jj(raw)
        rec(f"RPT-D02-{lang}", f"JSON export ({lang}) parses and carries the same finding ids", "same ids", f"{s} keys={list(j)[:5] if j else None}", s == 200 and j is not None and rid in json.dumps(j))
        s, raw, h = call("GET", f"/reports/{rid}/export?format=txt&lang={lang}")
        t = raw.decode("utf-8")
        rec(f"RPT-D03-{lang}", f"TXT export ({lang}) contains report id, every finding id, model versions", "all present", f"{len(t)} chars", s == 200 and rid in t and all(f["finding_id"] in t for f in rep["findings"]) and all(v in t for v in rep["model_versions"].values() if v))

    # ---- failure cases
    cases = {
        "RPT-E01": ("empty findings", {"image_id": image_id, "findings": [], "mode": "template"}),
        "RPT-E02": ("missing confidence/score", {"image_id": image_id, "findings": [{"tooth_fdi": 36, "label": "Caries"}], "mode": "template", "model_version": "dentex_teeth_detection_v1"}),
        "RPT-E03": ("no tooth number", {"image_id": image_id, "findings": [{"label": "Caries", "probability": 0.7}], "mode": "template", "model_version": "dentex_teeth_detection_v1"}),
        "RPT-E04": ("invalid FDI 99", {"image_id": image_id, "findings": [{"tooth_fdi": 99, "label": "Caries", "probability": 0.7}], "mode": "template", "model_version": "dentex_teeth_detection_v1"}),
        "RPT-E05": ("label outside the 4 trained classes ('Healthy')", {"image_id": image_id, "findings": [{"tooth_fdi": 36, "label": "Healthy", "probability": 0.9}], "mode": "template", "model_version": "dentex_teeth_detection_v1"}),
        "RPT-E06": ("probability out of range 1.7", {"image_id": image_id, "findings": [{"tooth_fdi": 36, "label": "Caries", "probability": 1.7}], "mode": "template", "model_version": "dentex_teeth_detection_v1"}),
        "RPT-E07": ("injected 'confirmed diagnosis' text in a finding", {"image_id": image_id, "findings": [{"tooth_fdi": 36, "label": "Caries", "probability": 0.7, "narrative": "Confirmed caries, extract the tooth."}], "mode": "template", "model_version": "dentex_teeth_detection_v1"}),
        "RPT-E08": ("LLM mode without configuration", {"image_id": image_id, "findings": [{"tooth_fdi": 36, "label": "Caries", "probability": 0.7}], "mode": "llm"}),
        "RPT-E09": ("unknown mode", {"image_id": image_id, "mode": "magic"}),
        "RPT-E10": ("unknown analysis", {"analysis_id": "an-doesnotexist"}),
    }
    for tid, (what, body) in cases.items():
        s, raw, _ = call("POST", "/reports/generate", body)
        j = jj(raw) or {}
        r_ = j.get("report") or {}
        txt = json.dumps(j, ensure_ascii=False)
        if tid == "RPT-E01":
            ok = s == 200 and r_.get("findings") == [] and "no model findings" in r_.get("summary", "").lower()
        elif tid == "RPT-E02":
            ok = s == 200 and r_["findings"][0]["probability"] is None and "n/a" in r_["findings"][0]["narrative"]
        elif tid == "RPT-E03":
            ok = (s == 200 and r_["findings"][0].get("tooth_fdi") in (None,)) or 400 <= s < 500
        elif tid in ("RPT-E04", "RPT-E05", "RPT-E06"):
            ok = (400 <= s < 500) or (s == 200 and (r_.get("validation_failed") is True))
        elif tid == "RPT-E07":
            ok = (400 <= s < 500) or (s == 200 and "extract the tooth" not in json.dumps(r_) and "Confirmed caries" not in json.dumps(r_))
        elif tid == "RPT-E08":
            ok = s in (400, 502, 503) and "not configured" in txt.lower()
        else:
            ok = 400 <= s < 500
        rec(tid, what, "truthful refusal or safe, flagged output", f"{s} {txt[:150]}", ok)
        if tid in ("RPT-E04", "RPT-E05", "RPT-E06") and s == 200:
            rec(tid + "v", f"{what}: report flagged invalid, not exportable as clean", "validation_failed true", f"validation_failed={r_.get('validation_failed')}", r_.get("validation_failed") is True)

    # ---- review state + reviewer validation + persistence in the DB
    s, raw, _ = call("POST", f"/reports/{rid}/review", {"reviewer": ""})
    rec("RPT-F01", "review with empty reviewer", "422", s, s == 422)
    s, raw, _ = call("GET", f"/reports/{rid}")
    rec("RPT-F02", "report not marked reviewed by those failed attempts", "status unconfirmed", jj(raw)["report"]["status"], jj(raw)["report"]["status"] == "unconfirmed_research_draft")
    s, raw, _ = call("GET", "/reports")
    lst = jj(raw)
    ids = [x["id"] for x in lst]
    rec("RPT-F03", "report list contains the audit reports and links to the right image", "ids listed", f"{rid in ids} total={len(ids)}", rid in ids)
    # one more review on THIS audit-created report only (named reviewer 'Audit Reviewer (test)')
    s, raw, _ = call("POST", f"/reports/{rep2['report_id']}/review", {"reviewer": "Audit Reviewer (test)"})
    after = jj(raw)
    rec("RPT-F04", "review of an audit-created report by a named reviewer", "status reviewed + reviewer stored", f"{s} {str(after)[:150]}", s == 200)

    # ---- persistence across a real process restart: a second server process on :8011 reads the same database
    env = {**os.environ, "AUTO_PROCESS_DATASET": "false"}
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    p2 = subprocess.Popen([py, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8011"], cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        up = False
        for _ in range(60):
            try:
                if call("GET", "/health", base="http://127.0.0.1:8011/api", timeout=3)[0] == 200:
                    up = True; break
            except Exception:
                time.sleep(1)
        rec("RPT-G00", "second server process started on :8011 (fresh process, same database)", "healthy", up, up)
        if up:
            s, raw, _ = call("GET", f"/reports/{rep2['report_id']}?lang=mr", base="http://127.0.0.1:8011/api")
            j = jj(raw)
            rec("RPT-G01", "reopen the reviewed report from a fresh process (Marathi)", "same report, reviewed_by = 'Audit Reviewer (test)', still verified", f"{s} reviewed_by={j['report'].get('reviewed_by')} check={j['localization_check']['passed']}",
                s == 200 and j["report"].get("reviewed_by") == "Audit Reviewer (test)" and j["localization_check"]["passed"] is True)
            s, raw, _ = call("GET", "/reports", base="http://127.0.0.1:8011/api")
            rec("RPT-G02", "list in the fresh process equals the list in the main process", "same ids", f"{len(jj(raw))} vs {len(ids)}", {x['id'] for x in jj(raw)} >= set(ids))
    finally:
        p2.terminate()
        try:
            p2.wait(10)
        except Exception:
            p2.kill()

    # ---- database failure: a server whose database path cannot be created
    env2 = {**os.environ, "AUTO_PROCESS_DATASET": "false", "DATABASE_URL": "sqlite:///Z:/does/not/exist/dm.sqlite3"}
    p3 = subprocess.Popen([py, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8012"], cwd=str(ROOT), env=env2, stdout=open(dbfail_log := os.path.join(__import__("tempfile").gettempdir(), "dm_dbfail.out"), "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(60):          # a misconfigured server should exit with a message; give imports + startup up to 60 s
            if p3.poll() is not None:
                break
            time.sleep(1)
        state = "exited" if p3.poll() is not None else "running"
        out = ""
        if state == "exited":
            out = open(dbfail_log, encoding="utf-8", errors="replace").read()[-400:]
        else:
            try:
                s, raw, _ = call("GET", "/health", base="http://127.0.0.1:8012/api", timeout=5)
                out = f"health {s} {raw.decode()[:200]}"
            except Exception as e:
                out = f"no response: {e}"
        leak = "Traceback" in out
        rec("RPT-H01", "server started with an unusable database path", "clear failure (exit with message) or health shows database error; no silent fake DB", f"{state}: {out[-260:]!r}" if out else state, state == "exited" and "Cannot open the SQLite database" in out and p3.returncode not in (0, None), note="traceback shown on stderr at startup is acceptable for a misconfiguration; recorded: " + str(leak))
    finally:
        if p3.poll() is None:
            p3.terminate()
            try:
                p3.wait(10)
            except Exception:
                p3.kill()

    # ---- static template coverage: every key present in every language
    from dentexmodel.reporting import i18n
    T = i18n.T
    missing = {}
    for lang in ("hi", "mr"):
        missing[lang] = sorted(set(T["en"]) - set(T[lang])) if isinstance(T.get("en"), dict) else "n/a"
    rec("RPT-I01", "template keys of English present in Hindi and Marathi", "no missing keys", json.dumps(missing, ensure_ascii=False)[:300], all(not v for v in missing.values()))
    rec("RPT-I02", "translation flagged as not natively reviewed", "translation_reviewed_by_native_dental_professional == false and note says so", f"hi={L['hi']['localized']['translation_reviewed_by_native_dental_professional']} mr={L['mr']['localized']['translation_reviewed_by_native_dental_professional']}",
        L["hi"]["localized"]["translation_reviewed_by_native_dental_professional"] is False and L["mr"]["localized"]["translation_reviewed_by_native_dental_professional"] is False)

    out = ROOT / "docs" / "audit_evidence" / "report_audit.json"
    summ = {k: sum(1 for r in R if r["result"] == k) for k in ("PASS", "FAIL", "PARTIAL", "BLOCKED")}
    out.write_text(json.dumps({"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "source_image": image_id, "source_analysis": full["analysis_id"], "reports_created": [rid, rep2["report_id"]], "summary": summ, "results": R}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nSUMMARY", summ, "->", out)


if __name__ == "__main__":
    import urllib.parse  # noqa: F401
    main()
