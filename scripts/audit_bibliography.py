#!/usr/bin/env python
"""Citation audit of documents/dentist-research-references.bib for a manuscript (read-only on the bibliography).

    .venv\\Scripts\\python.exe scripts\\audit_bibliography.py [--online] [--out REPORT]

Offline: every key cited by the manuscript exists; required fields per entry type are present; DOI present; entries dated in the
current year or later are flagged for manual confirmation (very recent, possibly early-access records).
--online: each DOI is looked up (Crossref; DataCite for arXiv 10.48550 DOIs) and the registered title, year and first-author family
name are compared with the entry. A mismatch is a FLAG for a human, never an automatic correction. Only DOIs are sent.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "documents" / "dentist-research-references.bib"
MS = ROOT / "reports" / "manuscript" / "DentaMind_CV5_manuscript_v1_submission_draft.md"
OUT = ROOT / "reports" / "manuscript" / "citation_audit_v1.md"
REQUIRED = {"article": ["author", "title", "journal", "year"], "inproceedings": ["author", "title", "booktitle", "year"],
            "misc": ["title", "year"]}


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse_bib(text: str) -> dict:
    out = {}
    for m in re.finditer(r"@(\w+)\{([^,\s]+),(.*?)\n\}", text, re.S):
        fields = {k.lower(): re.sub(r"\s+", " ", v).strip() for k, v in
                  re.findall(r"(\w+)\s*=\s*[{\"](.*?)[}\"]\s*,?\s*\n", m.group(3) + "\n", re.S)}
        out[m.group(2)] = {"type": m.group(1).lower(), **fields}
    return out


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"[{}\\]", "", s.lower())).strip()


def lookup(doi: str) -> dict:
    ua = {"User-Agent": "dentamind-citation-audit/1"}
    if doi.lower().startswith("10.48550/"):
        d = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.datacite.org/dois/{doi}", headers=ua), timeout=30))
        a = d["data"]["attributes"]
        return {"title": a["titles"][0]["title"], "year": str(a.get("publicationYear")),
                "family": (a.get("creators") or [{}])[0].get("familyName", "")}
    d = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.crossref.org/works/{doi}", headers=ua), timeout=30))
    m = d["message"]
    parts = (m.get("published-print") or m.get("published-online") or m.get("issued") or {}).get("date-parts", [[None]])
    years = {str(p[0]) for k in ("published-print", "published-online", "issued") for p in (m.get(k) or {}).get("date-parts", [])}
    return {"title": (m.get("title") or [""])[0], "year": str(parts[0][0]), "years": years,
            "family": (m.get("author") or [{}])[0].get("family", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--manuscript", default=str(MS))
    a = ap.parse_args()
    ms = Path(a.manuscript).resolve()
    bib = parse_bib(BIB.read_text(encoding="utf-8"))
    cited = sorted({k.strip() for g in re.findall(r"\[CITE:\s*([^\]]+)\]", ms.read_text(encoding="utf-8")) for k in g.split(";")})
    year_now = dt.date.today().year
    rows, flags = [], 0
    for key in sorted(bib, key=lambda k: (k not in cited, k.lower())):
        e = bib[key]
        notes = [f"missing {f}" for f in REQUIRED.get(e["type"], ["title", "year"]) if not e.get(f)]
        if not e.get("doi"):
            notes.append("no DOI (check another identifier)")
        if e.get("year", "0").isdigit() and int(e["year"]) >= year_now:
            notes.append(f"dated {e['year']}: very recent, confirm volume / pages / final version")
        online = "not run"
        if a.online and e.get("doi"):
            try:
                r = lookup(e["doi"])
                ratio = difflib.SequenceMatcher(None, norm(r["title"]), norm(e.get("title", ""))).ratio()
                first = norm(e.get("author", "").split(" and ")[0].split(",")[0])
                checks = [f"title match {ratio:.2f}"]
                if ratio < 0.9:
                    notes.append(f"registered title differs: '{r['title'][:80]}'")
                if e.get("year") and e["year"] != r["year"] and e["year"] not in r.get("years", set()):
                    notes.append(f"registered year {r['year']} differs from {e['year']}")
                if r["family"] and first and norm(r["family"]) not in first and first not in norm(r["family"]):
                    notes.append(f"registered first author '{r['family']}' differs")
                online = "resolved; " + ", ".join(checks)
            except Exception as ex:                       # network or registry error: report, never guess
                online = f"lookup failed ({type(ex).__name__})"
                notes.append("DOI not confirmed online")
        flags += bool(notes)
        rows.append((key, key in cited, e["type"], e.get("year", "-"), e.get("doi", "-"), online, "; ".join(notes) or "ok"))
    missing = [k for k in cited if k not in bib]
    lines = ["# Citation audit", "",
             f"* Date: {dt.date.today().isoformat()}. Bibliography `{BIB.relative_to(ROOT).as_posix()}` (sha256 `{sha(BIB)}`), "
             f"{len(bib)} entries; manuscript `{ms.relative_to(ROOT).as_posix()}` (sha256 `{sha(ms)}`), {len(cited)} cited keys.",
             f"* Script: `scripts/audit_bibliography.py` (sha256 `{sha(Path(__file__))}`); online DOI check: "
             f"{'run (Crossref / DataCite)' if a.online else 'not run'}.",
             f"* Cited keys missing from the bibliography: {', '.join(missing) or 'none'}. Entries with a flag: {flags}.", "",
             "A resolved DOI with a matching title shows that the record exists, not that the paper supports the sentence citing it. "
             "The authors must still read each cited source.", "",
             "| Key | Cited | Type | Year | DOI | Online check | Notes |", "|---|---|---|---|---|---|---|"]
    lines += [f"| `{k}` | {'yes' if c else 'no'} | {t} | {y} | {d} | {o} | {n} |" for k, c, t, y, d, o, n in rows]
    outp = Path(a.out)
    if outp.exists():
        raise SystemExit(f"{outp} exists: write a new audit version instead of overwriting")
    with open(outp, "x", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{len(cited)} cited, {len(missing)} missing, {flags} flagged -> {outp.name}")
    raise SystemExit(1 if missing else 0)


if __name__ == "__main__":
    main()
