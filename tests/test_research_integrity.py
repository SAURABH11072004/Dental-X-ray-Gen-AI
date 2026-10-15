"""Test-set ledger/gate, checkpoint training manifests and evidence-backed promotion. Checkpoints here are SYNTHETIC files
(random bytes + sidecars) in a temp dir; nothing touches the real Data/ folder."""
import hashlib
import json
import os

import helpers
from dentexmodel.data.manifest import ManifestRow
from dentexmodel.errors import DentaMindError
from dentexmodel.evaluation import test_ledger as TL
from dentexmodel.inference import promotion
from dentexmodel.inference.registry import active_model, read_overrides, scan_checkpoints, set_active
from dentexmodel.storage import Database
from dentexmodel.training import provenance as P
from dentexmodel.training.config import TrainConfig

REASON = "model selection finished on validation; final candidate"
JUST = "best validation macro-F1, limitations accepted"


class Base(helpers.TmpCase):
    def setUp(self):
        super().setUp()
        self.s.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.rep = self.s.data_root / "reports"
        self.rep.mkdir(parents=True, exist_ok=True)
        self.s.splits_dir.mkdir(parents=True, exist_ok=True)
        (self.s.splits_dir / "dentex_splits.json").write_text(json.dumps({"assignments": {"a": "train", "b": "test"}}), encoding="utf-8")
        self.db = Database(self.s.db_path)

    def ckpt(self, name, task="classification", with_manifest=False):
        p = self.s.checkpoint_dir / f"{name}.pth"
        p.write_bytes(os.urandom(256) + name.encode())
        meta = {"task": task, "architecture": "resnet18", "version": name, "dental_specific": True, "class_names": ["A", "B"], "num_classes": 2,
                "checkpoint_sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16], "metrics": {"classification": {"macro_f1": 0.5}}}
        if with_manifest:
            rows = [(ManifestRow(image_id="a", file_path="x/a.png", dataset_source="x", annotation_level="lvl", width=1, height=1, content_hash="h" * 64), 3)]
            meta["training_manifest"] = P.write(p, P.build(self.s, TrainConfig(task=task, architecture="resnet18"), "lvl", {"train": rows, "val": []},
                                                           {"A": 0, "B": 1}, {"normalize": "imagenet"}))
        p.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        return self.info(name)

    def info(self, name):
        return next(m for m in scan_checkpoints(self.s) if m.version == name)

    def report(self, info, split, sha="match", **extra):
        d = {"generated": "2026-10-01T00:00:00+00:00", "model_version": info.version, "model_id": info.model_id, "task": info.task, "split": split,
             "n_images": 10, "metrics": {"classification": {"macro_f1": 0.6}}, "dataset_version": {"splits_sha": "x"}, **extra}
        if sha == "match":
            d["checkpoint_sha256"] = TL.file_sha256(info.path)
        elif sha:
            d["checkpoint_sha256"] = sha
        (self.rep / f"eval_{info.version}_{split}.json").write_text(json.dumps(d), encoding="utf-8")


class LedgerTests(Base):
    def test_historical_results_are_preserved_and_the_split_is_marked_used(self):
        old = self.ckpt("legacy_v1")
        self.report(old, "test", sha=None, final_test=True)
        st = TL.status(self.s)
        self.assertTrue(st["previously_used"])
        self.assertFalse(st["ledger_initialised"])                     # derived only; a GET never writes
        led = TL.ensure_ledger(self.s)
        e = led["entries"][0]
        self.assertEqual((e["historical"], e["version"], e["authorized_by"]), (True, "legacy_v1", None))
        self.assertIn("before the ledger existed", e["authorization"])
        self.assertEqual(e["metrics"], {"classification": {"macro_f1": 0.6}})
        self.assertEqual(TL.verify_chain(led), [])
        self.assertTrue((self.rep / "eval_legacy_v1_test.json").is_file())    # the historical report itself is untouched
        self.assertEqual(TL.ensure_ledger(self.s)["entries"], led["entries"])   # idempotent

    def test_edits_to_the_ledger_are_detected_and_block_further_use(self):
        self.report(self.ckpt("legacy_v1"), "test", sha=None)
        led = TL.ensure_ledger(self.s)
        led["entries"][0]["metrics"] = {"classification": {"macro_f1": 0.99}}
        TL.ledger_path(self.s).write_text(json.dumps(led), encoding="utf-8")
        self.assertTrue(TL.verify_chain(TL.read_ledger(self.s)))
        new = self.ckpt("new_v1", with_manifest=True)
        self.report(new, "val")
        with self.assertRaises(DentaMindError) as c:
            TL.authorize(self.s, new, "final_metrics", "Approver One", REASON)
        self.assertEqual(c.exception.code, "ledger_tampered")

    def test_authorization_name_and_reason_are_required(self):
        new = self.ckpt("new_v1", with_manifest=True)
        self.report(new, "val")
        for who, why in (("", REASON), ("A", REASON), ("Approver One", "too short")):
            with self.assertRaises(DentaMindError) as c:
                TL.authorize(self.s, new, "final_metrics", who, why)
            self.assertEqual(c.exception.code, "test_authorization_required")

    def test_validation_report_for_the_same_file_is_required_first(self):
        new = self.ckpt("new_v1", with_manifest=True)
        with self.assertRaises(DentaMindError) as c:
            TL.authorize(self.s, new, "final_metrics", "Approver One", REASON)
        self.assertEqual(c.exception.code, "validation_first")
        self.report(new, "val", sha="0" * 64)                          # report for a different file
        with self.assertRaises(DentaMindError) as c:
            TL.authorize(self.s, new, "final_metrics", "Approver One", REASON)
        self.assertEqual(c.exception.code, "validation_first")

    def test_one_use_per_checkpoint_and_one_new_candidate_per_task(self):
        old = self.ckpt("legacy_v1")
        self.report(old, "test", sha=None)
        a = self.ckpt("cand_a", with_manifest=True)
        self.report(a, "val")
        ctx = TL.authorize(self.s, a, "final_metrics", "Approver One", REASON)
        self.assertTrue(TL.test_status_for_report(ctx)["previously_used"])     # the historical result is disclosed
        e = TL.record(self.s, a, "final_metrics", ctx, "Approver One", REASON, {"m": 1}, 10, "r.json", "test")
        for k in ("checkpoint_sha256", "evaluated_at", "split_version", "metrics", "authorized_by", "reason"):
            self.assertIn(k, e)
        self.assertEqual(e["checkpoint_sha256"], TL.file_sha256(a.path))
        self.assertTrue(e["test_set_previously_used"])
        with self.assertRaises(DentaMindError) as c:                        # same checkpoint again
            TL.authorize(self.s, a, "final_metrics", "Approver One", REASON)
        self.assertEqual(c.exception.code, "test_already_used")
        b = self.ckpt("cand_b", with_manifest=True)
        self.report(b, "val")
        with self.assertRaises(DentaMindError) as c:                        # second candidate on the same test images
            TL.authorize(self.s, b, "final_metrics", "Approver One", REASON)
        self.assertEqual(c.exception.code, "test_candidate_limit")
        self.assertEqual(TL.verify_chain(TL.read_ledger(self.s)), [])

    def test_legacy_checkpoints_can_only_reproduce_into_a_separate_folder(self):
        old = self.ckpt("legacy_v1")
        self.report(old, "val", sha=None)
        self.report(old, "test", sha=None)
        with self.assertRaises(DentaMindError) as c:
            TL.authorize(self.s, old, "final_metrics", "Approver One", REASON)
        self.assertEqual(c.exception.code, "legacy_checkpoint")
        with self.assertRaises(DentaMindError) as c:
            TL.authorize(self.s, old, "reproduction", "Approver One", REASON)
        self.assertEqual(c.exception.code, "out_dir_required")
        ctx = TL.authorize(self.s, old, "reproduction", "Approver One", REASON, out_dir=str(self.tmp / "repro"))
        self.assertTrue(ctx["legacy"])
        fresh = self.ckpt("never_tested", with_manifest=True)
        with self.assertRaises(DentaMindError) as c:
            TL.authorize(self.s, fresh, "reproduction", "Approver One", REASON, out_dir="x")
        self.assertEqual(c.exception.code, "nothing_to_reproduce")


class ProvenanceTests(Base):
    def test_legacy_checkpoints_are_labelled_and_never_inferred_from_counts(self):
        old = self.ckpt("legacy_v1")
        lv = P.level(old.path, old.metadata)
        self.assertEqual((lv["level"], lv["legacy"], lv["verified"]), (P.LEGACY, True, False))
        self.assertIn("cannot be proven", lv["detail"])
        self.assertTrue(old.dental_specific)                           # still usable, only labelled

    def test_manifest_records_image_ids_hashes_and_configuration(self):
        new = self.ckpt("new_v1", with_manifest=True)
        lv = P.level(new.path, new.metadata)
        self.assertEqual((lv["level"], lv["verified"]), (P.VERIFIED, True))
        m = json.loads((self.s.checkpoint_dir / "new_v1.training_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["images"]["train"], [{"image_id": "a", "content_sha256": "h" * 64, "file_path": "x/a.png", "dataset_source": "x", "n_items": 3}])
        for k in ("dataset", "class_mapping", "preprocessing", "seed", "training_config"):
            self.assertIn(k, m)
        self.assertIn("assignments_sha", m["dataset"])
        self.assertIsNotNone(m["dataset"]["assignments_sha"])

    def test_edited_manifest_rejects_the_checkpoint(self):
        self.ckpt("new_v1", with_manifest=True)
        mp = self.s.checkpoint_dir / "new_v1.training_manifest.json"
        mp.write_text(mp.read_text(encoding="utf-8").replace('"n_items": 3', '"n_items": 4'), encoding="utf-8")
        info = self.info("new_v1")
        self.assertFalse(info.dental_specific)
        self.assertIn("training manifest", info.provenance)

    def test_save_checkpoint_writes_the_manifest_and_links_it(self):
        from dentexmodel.training.trainers import _save_checkpoint

        class Ctx:
            settings, cancelled = self.s, False

            def log(self, *_a):
                pass
        cfg = TrainConfig(task="classification", architecture="resnet18", experiment_name="prov")
        rows = [(ManifestRow(image_id="a", file_path="x/a.png", dataset_source="x", annotation_level="l", width=1, height=1, content_hash="h" * 64), 2)]
        prov = P.build(self.s, cfg, "l", {"train": rows, "val": []}, {"A": 0}, {"normalize": "imagenet"})
        ck = _save_checkpoint(Ctx(), cfg, {}, {"class_names": ["A"], "num_classes": 1}, provenance=prov)
        meta = json.loads((self.s.checkpoint_dir / ck).with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(meta["training_manifest"]["counts"], {"train": 1, "val": 0})
        self.assertTrue(P.level(self.s.checkpoint_dir / ck, meta)["verified"])

    def test_used_lists_only_images_that_contributed(self):
        from dentexmodel.training.trainers import _used
        rows = [ManifestRow(image_id=i, file_path=i, dataset_source="x", annotation_level="l", width=1, height=1) for i in ("a", "b", "c")]
        items = [(r, [], {}) for r in rows]
        self.assertEqual([(r.image_id, n) for r, n in _used(items, ["a", "c", "a"])], [("a", 2), ("c", 1)])


class PromotionTests(Base):
    def setUp(self):
        super().setUp()
        self.old = self.ckpt("legacy_v1")
        set_active(self.s, "classification", self.old.model_id)
        self.new = self.ckpt("new_v1", with_manifest=True)

    def promote(self, **kw):
        a = {"task": "classification", "model_id": self.new.model_id, "approved_by": "Approver One", "justification": JUST, "confirm": True}
        a.update(kw)
        return promotion.promote(self.s, self.db, a["task"], a["model_id"], a["approved_by"], a["justification"], a["confirm"])

    def test_training_or_calibration_metrics_alone_are_refused(self):
        self.report(self.new, "calibration")
        with self.assertRaises(DentaMindError) as c:
            self.promote()
        self.assertEqual(c.exception.code, "promotion_evidence_missing")
        self.assertIn("validation-split", c.exception.message)
        self.assertEqual(read_overrides(self.s)["classification"], self.old.model_id)   # nothing changed

    def test_validation_report_must_name_this_file(self):
        self.report(self.new, "val", sha=None)
        self.assertFalse(promotion.evidence(self.s, self.new)["promotable"])
        self.report(self.new, "val", sha="1" * 64)
        self.assertFalse(promotion.evidence(self.s, self.new)["promotable"])

    def test_approval_confirmation_and_justification_are_required(self):
        self.report(self.new, "val")
        for kw, code in (({"confirm": False}, "approval_required"), ({"approved_by": ""}, "approval_required"), ({"justification": "ok"}, "justification_required")):
            with self.assertRaises(DentaMindError) as c:
                self.promote(**kw)
            self.assertEqual(c.exception.code, code)

    def test_promotion_records_evidence_and_rollback_restores_the_previous_model(self):
        self.report(self.new, "val")
        r = self.promote()
        self.assertEqual((r["previous_model_id"], r["approved_by"]), (self.old.model_id, "Approver One"))
        self.assertEqual(r["evidence"]["validation"]["tied_to_checkpoint_by"], "file sha256")
        self.assertEqual(r["evidence"]["test_history"], [])                  # no test result needed or used
        self.assertIn("Patient-level separation is not proven", " ".join(r["evidence"]["limitations"]))
        self.assertEqual(active_model(self.s, "classification").model_id, self.new.model_id)
        rb = promotion.rollback(self.s, self.db, "classification", "Approver Two", "regression found")
        self.assertEqual((rb["action"], rb["model_id"], rb["previous_model_id"]), ("rollback", self.old.model_id, self.new.model_id))
        self.assertEqual(active_model(self.s, "classification").model_id, self.old.model_id)
        self.assertEqual([h["action"] for h in promotion.history(self.db, "classification")], ["rollback", "promote"])

    def test_rollback_without_a_recorded_previous_model_is_refused(self):
        with self.assertRaises(DentaMindError) as c:
            promotion.rollback(self.s, self.db, "classification", "Approver Two", "regression found")
        self.assertEqual(c.exception.code, "nothing_to_roll_back")

    def test_use_cannot_bypass_promotion_for_new_checkpoints(self):
        with self.assertRaises(DentaMindError) as c:
            promotion.assert_selectable(self.s, self.db, self.new)
        self.assertEqual(c.exception.code, "promotion_required")
        promotion.assert_selectable(self.s, self.db, self.old)             # legacy: switching back stays possible
        self.report(self.new, "val")
        self.promote()
        promotion.assert_selectable(self.s, self.db, self.new)             # promoted once: may be re-selected

    def test_legacy_checkpoint_with_unhashed_validation_report_is_promotable_with_a_warning(self):
        self.report(self.old, "val", sha=None)
        ev = promotion.evidence(self.s, self.old)
        self.assertTrue(ev["promotable"])
        self.assertEqual(ev["validation"]["tied_to_checkpoint_by"], "model id/version only (report predates checkpoint hashing)")
        self.assertTrue(any("legacy" in w.lower() or "cannot be proven" in w for w in ev["warnings"]))
