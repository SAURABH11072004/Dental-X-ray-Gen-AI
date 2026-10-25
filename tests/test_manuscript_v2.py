"""Manuscript v2: audit, per-class bootstrap reproduction and figure manifest (read-only)."""
import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "reports" / "manuscript"
MS = MAN / "DentaMind_CV5_manuscript_v2_journal.md"
DOCX = MAN / "DentaMind_CV5_manuscript_v2_journal.docx"
BOOT = ROOT / "reports" / "cv5_per_class_bootstrap.json"

pytestmark = pytest.mark.skipif(not (MS.exists() and BOOT.exists() and (ROOT / "kaggle" / "artifacts_cv5_run1").exists()),
                                reason="manuscript v2 or archived artifacts not present")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v2_has_no_untraced_numbers():
    r = _load("audit_manuscript_numbers").audit(MS)
    assert r["untraced"] == [] and r["unknown_tags"] == [] and r["unknown_cites"] == []


def test_signed_value_written_as_magnitude_is_flagged(tmp_path):
    bad = tmp_path / "ms.md"
    bad.write_text(MS.read_text(encoding="utf-8").replace("the lowest, −0.0138", "the lowest, 0.0138"), encoding="utf-8")
    assert [t for _, t, _ in _load("audit_manuscript_numbers").audit(bad)["untraced"]] == ["0.0138"]


def test_per_class_bootstrap_reproduces_archive_and_stored_file():
    m = _load("per_class_bootstrap_cv5")
    y, groups, matched, preds = m.load()
    import numpy as np
    stored = json.loads(BOOT.read_text(encoding="utf-8"))
    r = m.run(y, groups, matched, preds["det_matched"])
    archived = json.loads((ROOT / "kaggle" / "artifacts_cv5_run1" / "cv5_results.json").read_text(encoding="utf-8"))
    assert np.allclose(r["macro_f1"]["ci95"], archived["bootstrap"]["det_matched"]["ci95"], atol=1e-12)
    assert r["per_class"] == stored["results"]["det_matched"]["per_class"]


def test_figure_manifest_hashes_match():
    man = json.loads((MAN / "figures_v2" / "figures_manifest.json").read_text(encoding="utf-8"))
    assert len(man["figures"]) == 10
    for name, e in man["figures"].items():
        assert hashlib.sha256((MAN / "figures_v2" / name).read_bytes()).hexdigest() == e["sha256"]


@pytest.mark.skipif(not DOCX.exists(), reason="docx not built")
def test_docx_numbers_match_source_and_no_tags():
    x = zipfile.ZipFile(DOCX).read("word/document.xml").decode("utf-8")
    doc = re.sub(r"<[^>]+>", "", x.replace("</w:p>", "\n"))
    md = re.sub(r"`[^`]*`", "", MS.read_text(encoding="utf-8"))
    md = re.sub(r"\[CITE:[^\]]*\]", "", md)
    num = re.compile(r"[−-]?\d[\d,]*\.\d+")
    assert set(num.findall(md)) <= set(num.findall(doc))
    assert "CITE" not in doc and "[boot:" not in doc and "[cv5:" not in doc
