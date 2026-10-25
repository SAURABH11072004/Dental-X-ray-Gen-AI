"""Manuscript v1 audit tooling: traced numbers, tamper detection and the negative-findings traceability table (read-only)."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MS = ROOT / "reports" / "manuscript" / "DentaMind_CV5_manuscript_v1_submission_draft.md"
NEG = ROOT / "reports" / "negative_findings_traceability.json"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pytestmark = pytest.mark.skipif(not (MS.exists() and NEG.exists() and (ROOT / "kaggle" / "artifacts_cv5_run1").exists()),
                                reason="manuscript or archived artifacts not present")


def test_manuscript_has_no_untraced_numbers_tags_or_citations():
    r = _load("audit_manuscript_numbers").audit(MS)
    assert r["untraced"] == [] and r["unknown_tags"] == [] and r["unknown_cites"] == []
    assert r["refs_listed"] == r["cites"] and len(r["traced"]) > 100


def test_tampered_number_is_flagged(tmp_path):
    bad = tmp_path / "ms.md"
    bad.write_text(MS.read_text(encoding="utf-8").replace("0.677 ± 0.008 (95 % CI", "0.681 ± 0.008 (95 % CI", 1), encoding="utf-8")
    r = _load("audit_manuscript_numbers").audit(bad)
    assert [t for _, t, _ in r["untraced"]] == ["0.681"]


def test_unknown_tag_and_citation_are_flagged(tmp_path):
    bad = tmp_path / "ms.md"
    bad.write_text("Value 0.5 `[no.such.row]` [CITE: notakey]\n", encoding="utf-8")
    r = _load("audit_manuscript_numbers").audit(bad)
    assert r["unknown_tags"] and r["unknown_cites"]


def test_no_candidate_results_or_latency_value():
    text = MS.read_text(encoding="utf-8")
    assert "[cost.latency]" in text and "not measured" in text
    assert "ms per" not in text and "ms/" not in text


def test_negative_findings_table_matches_its_sources():
    built = _load("build_negative_findings_traceability").build()
    stored = json.loads(NEG.read_text(encoding="utf-8"))
    assert [(r["id"], r["value"], r["source_sha256"]) for r in built["rows"]] == \
           [(r["id"], r["value"], r["source_sha256"]) for r in stored["rows"]]
    assert all(r["value"] is False for r in stored["rows"] if r["id"].endswith(".pass"))
