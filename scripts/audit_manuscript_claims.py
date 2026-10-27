#!/usr/bin/env python
"""Rule-based claims audit of a manuscript source (complements the number and citation audits; read-only).

    .venv\\Scripts\\python.exe scripts\\audit_manuscript_claims.py MANUSCRIPT.md --out REPORT.md

REQUIRED rules: a statement that must be present (regex, case-insensitive), with the line(s) found as evidence.
FORBIDDEN rules: claims that must not appear unless negated; every hit is listed with its line for human judgement.
A rule pass is mechanical evidence only - a human still reads the text. Exit 1 if a REQUIRED rule is missing or a FORBIDDEN hit
is not negated. The report is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    ("latency: classifier-only reported separately", r"classifier only"),
    ("latency: full-pipeline reported separately", r"end-to-end, gpu, ms per radiograph"),
    ("latency: checkpoint is not a stored CV5 fold checkpoint", r"cross-validation checkpoints themselves are not stored locally"),
    ("latency: power / thermal state not controlled", r"power and thermal state were not controlled|without control of power or thermal state"),
    ("latency: hardware-specific", r"other hardware will give different values"),
    ("negative results labelled as validation split, not CV5", r"fixed validation split"),
    ("negative results not comparable with CV5", r"not comparable with section 3\.1"),
    ("every earlier remedy failed its rule", r"none of the earlier remedies met its pre-registered acceptance rule"),
    ("post-hoc analyses declared descriptive", r"post-hoc analyses\.\*\* the per-class intervals and the error attribution"),
    ("no improvement claim", r"we make no claim that any model improves on the baseline"),
    ("no clinical validation", r"has not been validated for clinical use"),
    ("no external test set", r"there is no external test set"),
    ("candidates not registered or trained", r"none has yet been registered or trained"),
    ("confused findings not called label errors", r"we do not claim that they are labelling errors"),
    ("test split previously used, no test result reported", r"no test result is reported here"),
]
FORBIDDEN = [
    ("deployment / clinical readiness", r"\b(deployment[- ]ready|ready for (clinical )?deployment|clinically ready|real-time clinical)\b"),
    ("clinical validation claimed", r"\bclinically validated\b|\bvalidated for clinical\b"),
    ("external validation claimed", r"\bexternal(ly)? validat\w*"),
    ("superiority / state of the art", r"\b(state[- ]of[- ]the[- ]art|outperform\w*|superior to)\b"),
    ("improvement achieved", r"\b(significant(ly)? improv\w*|improved performance|achiev\w* (an? )?improvement)\b"),
    ("candidates called registered", r"\bare registered under\b"),
    ("diagnostic claim", r"\b(diagnoses|can diagnose|diagnostic accuracy)\b"),
]
NEGATION = re.compile(r"\b(not|no|never|without|cannot|nor|none)\b", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manuscript")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ms, out = Path(a.manuscript), Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists: write a new audit file")
    lines = ms.read_text(encoding="utf-8").splitlines()
    sha = hashlib.sha256(ms.read_bytes()).hexdigest()
    rows, ok = [], True
    for name, rx in REQUIRED:
        hits = [i + 1 for i, l in enumerate(lines) if re.search(rx, l, re.I)]
        ok &= bool(hits)
        rows.append(f"| REQUIRED | {name} | {'present' if hits else '**MISSING**'} | {', '.join(map(str, hits[:6])) or '-'} |")
    for name, rx in FORBIDDEN:
        hits = [(i + 1, l) for i, l in enumerate(lines) if re.search(rx, l, re.I)]
        bad = [n for n, l in hits if not NEGATION.search(l)]
        ok &= not bad
        verdict = "absent" if not hits else ("only in negated statements" if not bad else "**UNNEGATED HIT**")
        rows.append(f"| FORBIDDEN | {name} | {verdict} | {', '.join(str(n) for n, _ in hits[:6]) or '-'} |")
    rep = ["# Manuscript claims audit", "",
           f"* Manuscript: `{ms.resolve().relative_to(ROOT).as_posix()}` (sha256 `{sha}`)",
           f"* Script: `scripts/audit_manuscript_claims.py` (sha256 `{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}`)", "",
           f"**Result: {'PASS' if ok else 'FAIL'}.** Mechanical evidence only; negated hits still need a human read.", "",
           "| Kind | Rule | Result | Lines |", "|---|---|---|---|", *rows]
    with open(out, "x", encoding="utf-8") as fh:
        fh.write("\n".join(rep) + "\n")
    print(("PASS" if ok else "FAIL") + f" -> {out.name}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
