"""Improvement round 1: error attribution, blinded review queue, latency record, manuscript v3 (read-only checks)."""
import csv
import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
MS3 = REP / "manuscript" / "DentaMind_CV5_manuscript_v3_journal.md"
DOCX3 = REP / "manuscript" / "DentaMind_CV5_manuscript_v3_journal.docx"
CR = REP / "clinical_review"

pytestmark = pytest.mark.skipif(not (ROOT / "kaggle" / "artifacts_cv5_run1").exists() or not MS3.exists(),
                                reason="archived artifacts or manuscript v3 not present")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_error_attribution_reproduces_archive_and_stored_file():
    t = _load("cv5_error_attribution").analyse()           # raises if any reproduction gate fails
    stored = json.loads((REP / "cv5_error_attribution.json").read_text(encoding="utf-8"))
    assert t["per_class"] == stored["per_class"]
    p = stored["per_class"]
    assert sum(v["findings"] for v in p.values()) == 2851
    assert sum(v["M"] for v in p.values()) == 2745                      # detector-matched population
    assert t["gates"]["consistent_confusion_count_reproduces_archive"] == 110


def test_review_worksheet_is_blinded_and_key_is_complete():
    work = list(csv.DictReader(open(CR / "caries_rereading_worksheet_v1_BLINDED.csv", encoding="utf-8")))
    key = list(csv.DictReader(open(CR / "caries_rereading_key_v1_COORDINATOR_ONLY.csv", encoding="utf-8")))
    banned = {"original_label", "label", "set", "seeds_other_caries_gt", "seeds_other_caries_det", "sample_id", "detector_matched"}
    assert not banned & set(work[0])
    assert all(not any(v for k, v in r.items() if k.startswith(("reviewer_", "image_quality", "comment", "review_date"))) for r in work)
    assert [r["review_id"] for r in work] == [r["review_id"] for r in key]
    assert sum(r["set"] == "target" for r in key) == 110 and sum(r["set"] == "control" for r in key) == 110
    man = json.loads((CR / "caries_rereading_manifest_v1.json").read_text(encoding="utf-8"))
    for e in man["outputs"].values():
        assert hashlib.sha256((ROOT / e["path"]).read_bytes()).hexdigest() == e["sha256"]


@pytest.mark.parametrize("run", ["1", "2"])
def test_latency_record_is_complete_and_measured(run):
    d = json.loads((REP / f"latency_benchmark_rtx3050_run{run}.json").read_text(encoding="utf-8"))
    assert "RTX 3050" in d["environment"]["gpu"] and d["classifier_parameters"] == 23516228
    assert [r["batch"] for r in d["model_only_gpu_fp32"]] == [1, 64]
    assert all(r["repetitions"] == 5 and len(r["ms_per_crop_by_repetition"]) == 5 for r in d["model_only_gpu_fp32"])
    assert d["end_to_end_gpu"]["ms_per_radiograph"]["total"]["n"] == 100


def test_manuscript_v3_audit_passes_and_docx_matches():
    r = _load("audit_manuscript_numbers").audit(MS3)
    assert r["untraced"] == [] and r["unknown_tags"] == [] and r["unknown_cites"] == []
    if DOCX3.exists():
        doc = re.sub(r"<[^>]+>", "", zipfile.ZipFile(DOCX3).read("word/document.xml").decode("utf-8").replace("</w:p>", "\n"))
        md = re.sub(r"\[CITE:[^\]]*\]", "", re.sub(r"`[^`]*`", "", MS3.read_text(encoding="utf-8")))
        num = re.compile(r"[−-]?\d[\d,]*\.\d+")
        assert set(num.findall(md)) <= set(num.findall(doc))
        assert "[attr:" not in doc and "[lat1:" not in doc and "CITE" not in doc


def test_v3_no_longer_claims_candidates_are_registered():
    text = MS3.read_text(encoding="utf-8")
    assert "are registered under the protocol" not in text
    assert "drafted for registration" in text
