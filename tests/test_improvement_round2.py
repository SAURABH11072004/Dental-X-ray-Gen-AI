"""Round 2: blinded worksheet v2, manuscript v3.1 (test-split disclosure, audits, Word consistency), M1 registration status."""
import csv
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CR = ROOT / "reports" / "clinical_review"
MAN = ROOT / "reports" / "manuscript"
MS31 = MAN / "DentaMind_CV5_manuscript_v3_1_journal.md"

pytestmark = pytest.mark.skipif(not (CR / "caries_rereading_manifest_v2.json").exists() or not MS31.exists(),
                                reason="round-2 outputs not present")


def test_worksheet_v2_reveals_nothing_that_identifies_the_public_label():
    w = list(csv.DictReader(open(CR / "caries_rereading_worksheet_v2_BLINDED.csv", encoding="utf-8")))
    assert set(w[0]) >= {"review_id", "image_code", "fdi_tooth"}
    assert not {"image_path", "image_sha256", "box_xyxy_px", "original_label", "set", "sample_id"} & set(w[0])
    text = (CR / "caries_rereading_worksheet_v2_BLINDED.csv").read_text(encoding="utf-8")
    assert not re.search(r"train_\d+|val_\d+|\.png|[0-9a-f]{64}", text)
    k = list(csv.DictReader(open(CR / "caries_rereading_key_v2_COORDINATOR_ONLY.csv", encoding="utf-8")))
    assert [r["review_id"] for r in w] == [r["review_id"] for r in k]
    codes = {}
    for r in k:
        assert codes.setdefault(r["image_code"], r["image_path"]) == r["image_path"]     # one code per image
    assert len(codes) == len(set(codes.values())) == 158
    man = json.loads((CR / "caries_rereading_manifest_v2.json").read_text(encoding="utf-8"))
    for e in man["outputs"].values():
        assert hashlib.sha256((ROOT / e["path"]).read_bytes()).hexdigest() == e["sha256"]


def test_v1_worksheet_and_key_unchanged():
    man = json.loads((CR / "caries_rereading_manifest_v1.json").read_text(encoding="utf-8"))
    for e in man["outputs"].values():
        assert hashlib.sha256((ROOT / e["path"]).read_bytes()).hexdigest() == e["sha256"]


def test_v3_1_discloses_test_split_use_and_passes_all_audits(tmp_path):
    t = MS31.read_text(encoding="utf-8")
    assert "5 historical entries" in t and "No test result is reported here" in t
    py = sys.executable
    for script, extra in (("audit_manuscript_numbers.py", []), ("audit_manuscript_claims.py", [])):
        r = subprocess.run([py, str(ROOT / "scripts" / script), str(MS31), "--out", str(tmp_path / f"{script}.md"), *extra],
                           capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 0, r.stdout + r.stderr
    v3 = (MAN / "DentaMind_CV5_manuscript_v3_journal.md").read_text(encoding="utf-8")
    assert t.replace(v3.split("\n", 3)[2], "") != v3          # v3.1 differs from v3 beyond the header
    assert hashlib.sha256((MAN / "DentaMind_CV5_manuscript_v3_journal.md").read_bytes()).hexdigest().startswith("ec96748c")


def test_v3_1_docx_matches_source():
    doc = re.sub(r"<[^>]+>", "", zipfile.ZipFile(MAN / "DentaMind_CV5_manuscript_v3_1_journal.docx").read("word/document.xml")
                 .decode("utf-8").replace("</w:p>", "\n"))
    md = re.sub(r"\[CITE:[^\]]*\]", "", re.sub(r"`[^`]*`", "", MS31.read_text(encoding="utf-8")))
    num = re.compile(r"[−-]?\d[\d,]*\.\d+")
    assert set(num.findall(md)) <= set(num.findall(doc))
    assert "Earlier use of the test split" in doc and "CITE" not in doc


def test_matching_registration_is_draft_and_no_m1_result_exists():
    reg = (ROOT / "reports" / "cv5_matching_rule_registration_DRAFT.md").read_text(encoding="utf-8")
    assert "NOT REGISTERED. NOT RUN" in reg
    assert not list((ROOT / "reports").glob("*m1*result*")) and not list((ROOT / "reports").glob("*matching*result*"))
