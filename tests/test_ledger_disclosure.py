"""Retrospective test-use disclosure (test_ledger.record_retrospective_disclosure). Temporary ledger only; the real
data/reports/test_set_ledger.json is never touched."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from dentexmodel.errors import DentaMindError
from dentexmodel.evaluation import test_ledger as TL
from test_research_integrity import REASON, Base

ROOT = Path(__file__).resolve().parents[1]
DISCLOSE_REASON = "external GPU run evaluated the test split once; disclosed for transparency"


def fields(n=5, **over):
    f = {"task": "classification", "version": "kaggle_BASE_s42-46", "description": "BASE recipe, 5 seeds, test split evaluated once",
         "evaluated_at": "2026-10-16T11:53:27Z", "checkpoint_sha256s": [hashlib.sha256(str(i).encode()).hexdigest() for i in range(n)],
         "split_version_at_evaluation": {"assignments_sha": "x"}, "n_findings": 354, "n_images": 73,
         "metrics": {"macro_f1_mean": 0.693}, "report": "test_eval.json", "script": "notebook v2", "selection": "validation only"}
    f.update(over)
    return f


class DisclosureTests(Base):
    def test_disclosure_is_chained_and_listed(self):
        e = TL.record_retrospective_disclosure(self.s, fields(), "Approver One", DISCLOSE_REASON)
        self.assertEqual(e["kind"], TL.DISCLOSURE_KIND)
        self.assertTrue(e["retrospective"] and e["checkpoint_sha256"] is None and len(e["checkpoint_sha256s"]) == 5)
        led = TL.read_ledger(self.s)
        self.assertEqual(TL.verify_chain(led), [])
        self.assertIn({"task": "classification", "version": "kaggle_BASE_s42-46"}, TL.status(self.s)["used_by"])

    def test_requires_authorizer_reason_and_every_field(self):
        for who, why, f, code in (("", DISCLOSE_REASON, fields(), "test_authorization_required"),
                                  ("Approver One", "short", fields(), "test_authorization_required"),
                                  ("Approver One", DISCLOSE_REASON, fields(evaluated_at=""), "disclosure_incomplete"),
                                  ("Approver One", DISCLOSE_REASON, fields(checkpoint_sha256s=["abc"]), "disclosure_incomplete")):
            with self.assertRaises(DentaMindError) as c:
                TL.record_retrospective_disclosure(self.s, f, who, why)
            self.assertEqual(c.exception.code, code)
        self.assertEqual(TL.read_ledger(self.s).get("entries", []), [])            # nothing written on refusal

    def test_duplicate_and_tampered_ledger_are_refused(self):
        TL.record_retrospective_disclosure(self.s, fields(), "Approver One", DISCLOSE_REASON)
        with self.assertRaises(DentaMindError) as c:
            TL.record_retrospective_disclosure(self.s, fields(), "Approver One", DISCLOSE_REASON)
        self.assertEqual(c.exception.code, "already_recorded")
        p = TL.ledger_path(self.s)
        led = json.loads(p.read_text(encoding="utf-8"))
        led["entries"][-1]["metrics"] = {"macro_f1_mean": 0.99}
        p.write_text(json.dumps(led), encoding="utf-8")
        with self.assertRaises(DentaMindError) as c:
            TL.record_retrospective_disclosure(self.s, fields(n=2), "Approver One", DISCLOSE_REASON)
        self.assertEqual(c.exception.code, "ledger_tampered")

    def test_disclosure_does_not_block_a_future_candidate_but_is_reported_as_prior_use(self):
        TL.record_retrospective_disclosure(self.s, fields(), "Approver One", DISCLOSE_REASON)
        a = self.ckpt("cand_a", with_manifest=True)
        self.report(a, "val")
        ctx = TL.authorize(self.s, a, "final_metrics", "Approver One", REASON)       # not refused (no candidate slot used)
        self.assertTrue(TL.test_status_for_report(ctx)["previously_used"])
        self.assertIn(TL.DISCLOSURE_KIND, [p["kind"] for p in ctx["prior"]])


def test_cli_help_lists_record_disclosure():
    out = subprocess.run([sys.executable, str(ROOT / "scripts/test_set_ledger.py"), "--help"], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0 and "--record-disclosure" in out.stdout
