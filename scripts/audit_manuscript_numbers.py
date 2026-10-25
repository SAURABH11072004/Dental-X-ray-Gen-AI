#!/usr/bin/env python
"""Audit every number, source tag and citation key of a manuscript draft (read-only; computes no metric).

    .venv\\Scripts\\python.exe scripts\\audit_manuscript_numbers.py [MANUSCRIPT] [--out REPORT]

Source tags (in backticks, same paragraph / bullet / table row as the number):
  `[row-id]`        a row of reports/results_traceability.json or reports/negative_findings_traceability.json
  `[cv5:json/path]` a field of kaggle/artifacts_cv5_run1/cv5_results.json, read after checking it against SHA256SUMS.txt
  `[boot:json/path]` a field of reports/cv5_per_class_bootstrap.json (post-hoc per-class intervals that reproduce the archive)
  `[attr:json/path]` a field of reports/cv5_error_attribution.json (descriptive error attribution, reproduction-gated)
  `[lat1:json/path]`, `[lat2:json/path]` fields of reports/latency_benchmark_rtx3050_run{1,2}.json (measured latency)
A number is TRACED if it equals a tagged value of its unit at the displayed precision (list / dict values, their sum, and element /
sum percentages of archived count vectors are accepted). Otherwise it must be a DECLARED constant (design parameter, protocol
threshold, integrity count) listed below with its source; anything else is UNTRACED. Citation keys `[CITE: a; b]` must exist in
documents/dentist-research-references.bib. Exit status 1 on any untraced number, unknown tag or unknown citation key.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "kaggle" / "artifacts_cv5_run1"
DEFAULT_MS = ROOT / "reports" / "manuscript" / "DentaMind_CV5_manuscript_v1_submission_draft.md"
DEFAULT_OUT = ROOT / "reports" / "manuscript" / "manuscript_v1_number_audit.md"

# value -> source. Not results of a model: design parameters, protocol thresholds, counts verified by integrity checks.
CONSTANTS = {
    "1": "small count (design / structure; human check)", "2": "small count (design / structure; human check)",
    "3": "small count (design / structure; human check)", "4": "small count: classes, folds, Hamming distance (human check)",
    "5": "small count: folds, seeds, weight cap, ledger entries (human check)", "10": "design: ECE bins", "15": "design: epochs; protocol lifetime budget k",
    "20": "protocol/rule: cross pairs minimum", "25": "design: 5 folds x 5 seeds", "32": "design: batch size",
    "42": "design: first seed", "46": "design: last seed", "50": "architecture name ResNet-50", "95": "confidence level",
    "224": "design: crop size", "384": "candidate C1 crop size (design, no result)", "2000": "design: bootstrap resamples",
    "20000": "protocol: B", "0": "design: bootstrap seed / zero", "0.10": "design: context padding",
    "0.25": "candidate C2 padding (design, no result)", "0.5": "design: IoU match threshold", "0.97": "design: near-duplicate r",
    "0.027": "protocol threshold delta", "0.05": "protocol alpha", "9": "report-level: validation Periapical Lesion findings "
    "(reports/training_summary.md section 1)", "88": "integrity count verified this session", "61": "integrity count verified this session",
    "39": "integrity count verified this session", "133": "row count of results_traceability.json", "49": "row count of "
    "negative_findings_traceability.json", "541": "population (also tagged where reported as a result)",
    "6": "figure / table / contribution number", "64": "protocol section 7: latency batch size",
    "0.3": "design: detector score threshold (kaggle/dentamind_kaggle.DET_SCORE)", "3050": "hardware model name (RTX 3050)",
    "2.6": "software version (torch 2.6; latency_benchmark environment)", "12.4": "software version (CUDA 12.4; latency_benchmark environment)",
}
NUM = re.compile(r"(?<![\w.\-])[−\-]?\d(?:[\d,]*\d)?(?:\.\d+)?(?![\w])")   # skips compounds: ResNet-50, SHA-256, 3e-4
TAG = re.compile(r"`\[([^\]`]+)\]`")
CITE = re.compile(r"\[CITE:\s*([^\]]+)\]")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def cv5_results() -> dict:
    sums = {}
    for line in (ART / "SHA256SUMS.txt").read_text().splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            sums[name.strip().lstrip("*").replace("\\", "/")] = h
    if sums.get("cv5_results.json") != sha(ART / "cv5_results.json"):
        raise SystemExit("cv5_results.json does not match SHA256SUMS.txt")
    return json.loads((ART / "cv5_results.json").read_text(encoding="utf-8"))


def boot() -> dict:
    """reports/cv5_per_class_bootstrap.json (post-hoc per-class intervals; the file records that it reproduces the archive)."""
    d = json.loads((ROOT / "reports" / "cv5_per_class_bootstrap.json").read_text(encoding="utf-8"))
    if not all(r.get("reproduces_archived_macro_f1_bootstrap") for r in d["results"].values()):
        raise SystemExit("cv5_per_class_bootstrap.json does not record reproduction of the archived bootstrap")
    return d


def attr() -> dict:
    """reports/cv5_error_attribution.json (descriptive; written only after its three reproduction gates passed)."""
    d = json.loads((ROOT / "reports" / "cv5_error_attribution.json").read_text(encoding="utf-8"))
    if not (d["gates"]["matched_flags_reproduce_archive"] and d["gates"]["end_to_end_recall_reproduces_archive"]):
        raise SystemExit("cv5_error_attribution.json does not record its reproduction gates")
    return d


def lat(run: str) -> dict:
    """reports/latency_benchmark_rtx3050_run<N>.json (measured on this machine; descriptive)."""
    return json.loads((ROOT / "reports" / f"latency_benchmark_rtx3050_run{run}.json").read_text(encoding="utf-8"))


SOURCES = {"boot": boot, "attr": attr, "lat1": lambda: lat("1"), "lat2": lambda: lat("2")}


def units(text: str):
    """Paragraphs, bullets, numbered items, headings and table rows; continuation lines join the open unit."""
    cur, start, in_code = [], 0, False
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        new = not s or s[0] in "-*|#" or re.match(r"\d+\.\s", s) or s.startswith("**")
        if new and cur:
            yield start, " ".join(cur)
            cur = []
        if s:
            if not cur:
                start = i
            cur.append(s)
            if s[0] in "|#":
                yield start, " ".join(cur)
                cur = []
    if cur:
        yield start, " ".join(cur)


def candidates(v, cv5: bool) -> list[float]:
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return []
    if isinstance(v, (int, float)):
        return [float(v)]
    vals = list(v.values()) if isinstance(v, dict) else list(v)
    nums = [float(x) for x in vals if isinstance(x, (int, float)) and not isinstance(x, bool)]
    out = nums + [y for x in vals if isinstance(x, (list, dict)) for y in candidates(x, cv5)]
    if cv5 and nums and len(nums) == len(vals):
        total = sum(nums)
        out.append(total)
        out += [100 * x / total for x in nums] if total else []
    return out


def matches(token: str, vals: list[float]) -> bool:
    t = token.replace("−", "-").replace(",", "")
    d = len(t.split(".")[1]) if "." in t else 0
    x = float(t)
    return any(abs(round(v, d) - x) < 1e-9 for v in vals)


def audit(ms: Path) -> dict:
    rows = {}
    for f in ("results_traceability.json", "negative_findings_traceability.json"):
        p = ROOT / "reports" / f
        for r in json.loads(p.read_text(encoding="utf-8"))["rows"]:
            rows[r["id"]] = r["value"]
    res = cv5_results()
    bib = set(re.findall(r"^@\w+\{([^,\s]+),", (ROOT / "documents" / "dentist-research-references.bib").read_text(encoding="utf-8"),
                         re.M))
    text = ms.read_text(encoding="utf-8")
    out = {"traced": [], "constant": [], "untraced": [], "unknown_tags": [], "tags_used": set(), "cites": set(), "unknown_cites": []}
    for line, u in units(text):
        vals = []
        for tag in TAG.findall(u):
            if tag.startswith("CITE"):
                continue
            out["tags_used"].add(tag)
            if tag.split(":", 1)[0] in ("cv5", *SOURCES) and ":" in tag:
                d = res if tag.startswith("cv5:") else SOURCES[tag.split(":", 1)[0]]()
                try:
                    for k in tag.split(":", 1)[1].split("/"):
                        d = d[int(k)] if isinstance(d, list) else d[k]
                except (KeyError, IndexError, ValueError):
                    out["unknown_tags"].append((line, tag))
                    continue
                vals += candidates(d, tag.startswith("cv5:"))
            elif tag in rows:
                vals += candidates(rows[tag], False)
            else:
                out["unknown_tags"].append((line, tag))
        for keys in CITE.findall(u):
            for k in (x.strip() for x in keys.split(";")):
                out["cites"].add(k)
                if k not in bib:
                    out["unknown_cites"].append((line, k))
        body = re.sub(r"`[^`]*`", " ", u)                                  # code spans: tags, paths, hashes
        body = CITE.sub(" ", body)
        body = re.sub(r"\d{4}-\d{2}-\d{2}", " ", body)                     # dates
        body = re.sub(r"\b\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4}",
                      " ", body)                                           # dates written out
        body = re.sub(r"\bSections? \d+(?:\.\d+)?(?:[–\-]\d+(?:\.\d+)?)?", " ", body)  # section references in prose
        body = re.sub(r"§\s?[\d.]+(?:[–\-][\d.]+)?", " ", body)       # section references
        body = re.sub(r"^#+\s*[\d.]*", " ", body)                          # heading numbers
        body = re.sub(r"^(?:\|\s*)?\d+\.\s", " ", body)                    # list numbering
        body = re.sub(r"\b[A-Z]\.\d+\b", " ", body)                        # appendix numbering A.1
        for tok in NUM.findall(body):
            norm = tok.replace("−", "-").replace(",", "")
            if vals and matches(tok, vals):
                out["traced"].append((line, tok))
            elif norm.lstrip("-") in CONSTANTS:
                out["constant"].append((line, tok, CONSTANTS[norm.lstrip("-")]))
            else:
                out["untraced"].append((line, tok, u[:140]))
    out["refs_listed"] = set()
    m = re.search(r"cited here:(.*?)\. The bibliography", text, re.S)
    if m:
        out["refs_listed"] = {k.strip() for k in m.group(1).replace("\n", " ").split(",") if k.strip()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manuscript", nargs="?", default=str(DEFAULT_MS))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    ms, outp = Path(a.manuscript), Path(a.out)
    r = audit(ms)
    ok = not (r["untraced"] or r["unknown_tags"] or r["unknown_cites"]) and (not r["refs_listed"] or r["refs_listed"] == r["cites"])
    lines = ["# Manuscript number and citation audit", "",
             f"* Manuscript: `{ms.resolve().relative_to(ROOT).as_posix() if ms.resolve().is_relative_to(ROOT) else ms}` (sha256 `{sha(ms)}`)",
             f"* Audit script: `scripts/audit_manuscript_numbers.py` (sha256 `{sha(Path(__file__))}`)",
             f"* Traceability: `reports/results_traceability.json` (`{sha(ROOT / 'reports' / 'results_traceability.json')}`), "
             f"`reports/negative_findings_traceability.json` (`{sha(ROOT / 'reports' / 'negative_findings_traceability.json')}`), "
             f"`kaggle/artifacts_cv5_run1/cv5_results.json` (`{sha(ART / 'cv5_results.json')}`, checked against SHA256SUMS.txt)", "",
             f"**Result: {'PASS' if ok else 'FAIL'}.** Numbers traced to a source: {len(r['traced'])}; declared constants: "
             f"{len(r['constant'])}; untraced: {len(r['untraced'])}; unknown tags: {len(r['unknown_tags'])}; distinct tags: "
             f"{len(r['tags_used'])}; citation keys: {len(r['cites'])}, unknown: {len(r['unknown_cites'])}; reference list matches cited "
             f"keys: {r['refs_listed'] == r['cites'] if r['refs_listed'] else 'no reference list found'}.", "",
             "Limits: the audit proves that each number equals a tagged artifact value at its displayed precision, or is a declared "
             "constant. It does not prove that the surrounding sentence describes the value correctly; that remains a human check.", ""]
    if r["untraced"]:
        lines += ["## Untraced numbers", "", "| Line | Number | Context |", "|---|---|---|"]
        lines += [f"| {ln} | {t} | {c.replace('|', '/')} |" for ln, t, c in r["untraced"]] + [""]
    if r["unknown_tags"] or r["unknown_cites"]:
        lines += ["## Unknown tags / citation keys", ""] + [f"* line {ln}: `{t}`" for ln, t in r["unknown_tags"] + r["unknown_cites"]] + [""]
    lines += ["## Declared constants used", "", "| Line | Number | Declared as |", "|---|---|---|"]
    lines += [f"| {ln} | {t} | {s} |" for ln, t, s in r["constant"]]
    lines += ["", "## Citation keys", "", ", ".join(sorted(r["cites"]))]
    if outp.exists():
        raise SystemExit(f"{outp} exists: write the audit of a new manuscript version to a new file")
    with open(outp, "x", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"{'PASS' if ok else 'FAIL'}: traced {len(r['traced'])}, constants {len(r['constant'])}, untraced {len(r['untraced'])}, "
          f"unknown tags {len(r['unknown_tags'])}, unknown cites {len(r['unknown_cites'])} -> {outp.name}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
