"""Clinician review workflow (scripts/dataset/clinical_review.py): suggestions stay suggestions, only registered reviewers with an
explicit decision create labels, non-findings never become labels, and the audit log is append-only and tamper-evident."""
import csv
import json
import sys
from pathlib import Path

import pytest
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/dataset"))
import clinical_review as CR  # noqa: E402


def _reviewers(tmp_path, rows):
    p = tmp_path / "reviewers.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CR.REVIEWER_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


DENTIST = {"reviewer_id": "R1", "display_name": "Dr A", "qualification": "BDS, oral radiology", "registration_no": "X",
           "ls_user": "dr.a@clinic.example", "attested_by": "project owner", "attested_on": "2026-10-16"}


def _pool(tmp_path, rows):
    p = tmp_path / "pool.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["pool_id", "image_sha256", "source_dataset", "split_lock"])
        w.writerows(rows)
    return p


def _region(rid, label, decision=None, fdi=None):
    out = [{"id": rid, "from_name": "tooth", "type": "rectanglelabels", "original_width": 1000, "original_height": 500,
            "value": {"x": 10, "y": 20, "width": 5, "height": 10, "rectanglelabels": [label]}}]
    if decision:
        out.append({"id": rid, "from_name": "decision", "type": "choices", "value": {"choices": [decision]}})
    if fdi:
        out.append({"id": rid, "from_name": "tooth_fdi", "type": "choices", "value": {"choices": [fdi]}})
    return out


def _export(user, regions):
    res = [x for r in regions for x in r] + [{"from_name": "coverage", "type": "choices",
                                             "value": {"choices": ["only the suggested teeth were reviewed"]}}]
    return [{"id": 7, "data": {"image_id": "u_train_1", "pool_id": "P00001"},
             "meta": {"pool_id": "P00001", "image_sha256": "ab" * 32, "source_dataset": "dentex_unlabelled", "split_lock": "unassigned"},
             "annotations": [{"id": 70, "completed_by": {"email": user}, "updated_at": "2026-10-16T10:00:00Z", "result": res}]}]


def test_config_requires_explicit_decision_and_has_no_healthy_label():
    x = CR.review_config_xml()
    assert 'name="decision"' in x and 'required="true"' in x and "SUGGESTIONS" in x
    assert "Healthy" not in x and "No target finding" in x


def test_task_marks_predictions_as_suggestions():
    t = CR.build_review_task({"pool_id": "P1", "image_id": "i", "image_sha256": "s", "source_dataset": "d", "split_lock": "train",
                              "width": "1000", "height": "500", "external_hint": ""}, "/img",
                             [{"box": [100, 100, 200, 300], "fdi": 46, "suggestion": "Periapical Lesion",
                               "probs": {"Periapical Lesion": 0.8}, "queue_id": "P1_t00"}], "m1")
    assert t["predictions"][0]["model_version"].startswith("SUGGESTION ONLY")
    assert "annotations" not in t                                   # nothing is pre-accepted


def test_only_registered_reviewer_with_decision_creates_labels(tmp_path):
    rv = CR.load_reviewers(_reviewers(tmp_path, [DENTIST]))
    regs = [_region("a", "Periapical Lesion", "confirmed", "46"), _region("b", "Deep Caries", "corrected"),
            _region("c", "Caries", "rejected"), _region("d", "No target finding", "confirmed"), _region("e", "Deep Caries")]
    recs = {r["region_id"]: r for r in CR.parse_export(_export("dr.a@clinic.example", regs), rv, "x.json")}
    assert recs["a"]["status"] == "accepted_label" and recs["a"]["fdi"] == "46" and recs["a"]["reviewer_id"] == "R1"
    assert recs["b"]["status"] == "accepted_label"
    assert recs["c"]["status"] == "recorded_not_a_label"           # rejected suggestion
    assert recs["d"]["status"] == "recorded_not_a_label"           # "No target finding" is never a (healthy) label
    assert recs["e"]["status"] == "rejected_invalid"               # no decision
    unknown = CR.parse_export(_export("someone@else", [_region("a", "Periapical Lesion", "confirmed")]), rv, "x.json")
    assert unknown[0]["status"] == "rejected_invalid" and "not in data/annotation/reviewers.csv" in unknown[0]["problems"][0]


def test_incomplete_registry_entries_are_ignored(tmp_path):
    bad = {**DENTIST, "qualification": ""}
    assert CR.load_reviewers(_reviewers(tmp_path, [bad])) == {}


def test_import_is_append_only_hash_chained_and_export_filters(tmp_path):
    rvp = _reviewers(tmp_path, [DENTIST])
    log = tmp_path / "log.jsonl"
    exp = tmp_path / "export.json"
    exp.write_text(json.dumps(_export("dr.a@clinic.example", [_region("a", "Periapical Lesion", "confirmed"),
                                                               _region("d", "No target finding", "confirmed")])))
    assert CR.import_export(exp, log, rvp) == {"accepted_label": 1, "recorded_not_a_label": 1}
    # a later review of the same region supersedes, but both stay in the log
    exp.write_text(json.dumps(_export("dr.a@clinic.example", [_region("a", "Periapical Lesion", "rejected")])))
    CR.import_export(exp, log, rvp)
    assert sum(1 for l in log.read_text().splitlines() if l.strip()) == 3
    assert CR.verify_chain(log) == (True, 3)
    pool = _pool(tmp_path, [("P00001", "ab" * 32, "dentex_unlabelled", "unassigned")])
    res = CR.export_verified(tmp_path / "v.csv", log, pool, tmp_path)
    assert res["training_eligible_findings"] == 0 and res["excluded_findings"] == 0   # latest decision on region a is "rejected"
    lines = log.read_text().splitlines()
    tampered = json.loads(lines[0])
    tampered["label"] = "Deep Caries"
    log.write_text("\n".join([json.dumps(tampered)] + lines[1:]) + "\n")
    assert CR.verify_chain(log)[0] is False


# ------------------------------------------------------------------------------------------------------- queue rules
def _tooth(pl, dc, x=0):
    return {"box": [x, 0, x + 10, 10], "fdi": None, "box_source": "m", "probs": {"Caries": 0.0, "Deep Caries": dc, "Impacted": 0.0,
                                                                                  "Periapical Lesion": pl}}


def test_model_suggestions_are_capped_and_thresholded():
    import build_annotation_queue as Q
    rec = {"image_id": "u_train_1", "teeth": [_tooth(0.99, 0.0, 0), _tooth(0.95, 0.0, 20), _tooth(0.92, 0.0, 40), _tooth(0.6, 0.0, 60),
                                              _tooth(0.0, 0.85, 80), _tooth(0.0, 0.81, 100), _tooth(0.0, 0.83, 120), _tooth(0.0, 0.5, 140)]}
    tier, s = Q.suggestions_for(rec, {"source_dataset": "dentex_unlabelled"})
    assert tier == "B_model_priority"
    pl = [x for x in s if x["suggestion"] == "Periapical Lesion"]
    dc = [x for x in s if x["suggestion"] == "Deep Caries"]
    assert [t["probs"]["Periapical Lesion"] for t in pl] == [0.99, 0.95]          # top 2, p >= 0.9 only
    assert [t["probs"]["Deep Caries"] for t in dc] == [0.85, 0.83]                # top 2, p >= 0.8 only


def test_expert_hint_takes_precedence(monkeypatch):
    import build_annotation_queue as Q
    monkeypatch.setattr(Q, "turkish_lesion_hints", lambda image_id: [([1, 2, 3, 4], 46)])
    tier, s = Q.suggestions_for({"image_id": "dxtest_test_9", "teeth": [_tooth(0.99, 0.9)]}, {"source_dataset": "dentex_official_test"})
    assert tier.startswith("A") and len(s) == 1 and s[0]["fdi"] == 46 and "different taxonomy" in s[0]["hint"]


def test_turkish_hints_read_only_lezyon(tmp_path, monkeypatch):
    import build_annotation_queue as Q
    (tmp_path / "test_5.json").write_text(json.dumps({"shapes": [
        {"label": "7-lezyon-36", "points": [[10, 20], [30, 60]]}, {"label": "2-küretaj-31", "points": [[0, 0], [5, 5]]}]}), encoding="utf-8")
    monkeypatch.setattr(Q, "TEST_LABELS", tmp_path)
    assert Q.turkish_lesion_hints("dxtest_test_5") == [([10, 20, 30, 60], 36)]
    assert Q.turkish_lesion_hints("u_train_5") == []



# ------------------------------------------------------------------------------------------- defects fixed 2026-10-16
def test_uncertain_and_ungradable_are_recorded_not_labels(tmp_path):
    rv = CR.load_reviewers(_reviewers(tmp_path, [DENTIST]))
    recs = {r["region_id"]: r for r in CR.parse_export(_export("dr.a@clinic.example", [
        _region("u", "Periapical Lesion", "uncertain"), _region("g", "Not assessable", "confirmed")]), rv, "x.json")}
    assert recs["u"]["status"] == recs["g"]["status"] == "recorded_not_a_label"
    assert "uncertain" in CR.review_config_xml()


def test_reimporting_the_same_export_is_idempotent(tmp_path):
    rvp = _reviewers(tmp_path, [DENTIST])
    log, exp = tmp_path / "log.jsonl", tmp_path / "e.json"
    exp.write_text(json.dumps(_export("dr.a@clinic.example", [_region("a", "Periapical Lesion", "confirmed")])))
    assert CR.import_export(exp, log, rvp) == {"accepted_label": 1}
    assert CR.import_export(exp, log, rvp) == {"skipped_already_imported": 1}
    assert sum(1 for l in log.read_text().splitlines() if l.strip()) == 1 and CR.verify_chain(log) == (True, 1)


def _accepted(pool_id, sha, coverage="only the suggested teeth were reviewed", split_lock_in_task="train"):
    return {"pool_id": pool_id, "image_sha256": sha, "coverage": coverage, "split_lock": split_lock_in_task}


def test_eligibility_is_derived_from_pool_and_frozen_manifests_not_task_meta(tmp_path):
    pool = {"P1": {"image_sha256": "s1", "split_lock": "unassigned", "source_dataset": "dentex_unlabelled"},
            "P2": {"image_sha256": "s2", "split_lock": "eval_locked", "source_dataset": "dentex_quadrant"},
            "P3": {"image_sha256": "s3", "split_lock": "unassigned", "source_dataset": "dentex_unlabelled"},
            "P4": {"image_sha256": "s4", "split_lock": "unassigned", "source_dataset": "hanoi_periapical"}}
    ev = {"s3"}                                              # s3 sits in a frozen evaluation manifest
    assert CR.training_eligibility(_accepted("P1", "s1"), pool, ev) == ""
    assert "evaluation" in CR.training_eligibility(_accepted("P2", "s2"), pool, ev)      # task meta claims "train": ignored
    assert "evaluation" in CR.training_eligibility(_accepted("P3", "s3"), pool, ev)
    assert "SHA-256" in CR.training_eligibility(_accepted("P1", "other"), pool, ev)
    assert "not in" in CR.training_eligibility(_accepted("P9", "s9"), pool, ev)
    assert "P3" in CR.training_eligibility(_accepted("P4", "s4"), pool, ev)              # Hanoi needs full four-class review
    assert CR.training_eligibility(_accepted("P4", "s4", CR.FULL_COVERAGE), pool, ev) == ""


def test_export_splits_eligible_and_excluded_and_counts_radiographs(tmp_path):
    rvp = _reviewers(tmp_path, [DENTIST])
    log, exp = tmp_path / "log.jsonl", tmp_path / "e.json"
    exp.write_text(json.dumps(_export("dr.a@clinic.example", [_region("a", "Periapical Lesion", "confirmed"),
                                                               _region("b", "Deep Caries", "corrected")])))
    CR.import_export(exp, log, rvp)
    pool = _pool(tmp_path, [("P00001", "ab" * 32, "dentex_unlabelled", "eval_locked")])
    res = CR.export_verified(tmp_path / "v.csv", log, pool, tmp_path)
    assert res == {"training_eligible_findings": 0, "training_eligible_radiographs": 0, "excluded_findings": 2, "excluded_radiographs": 1}
    excl = list(csv.DictReader(open(tmp_path / "verified_findings_not_for_training.csv", encoding="utf-8")))
    assert {r["excluded_reason"][:10] for r in excl} == {"evaluation"}


def test_scoring_resume_drops_partial_trailing_record(tmp_path):
    import build_annotation_queue as Q
    f = tmp_path / "scores.jsonl"
    f.write_text('{"pool_id": "P1"}\n{"pool_id": "P2"}\n{"pool_id": "P3", "tee', encoding="utf-8")
    assert Q.load_done(f) == {"P1", "P2"}
    assert f.read_text(encoding="utf-8") == '{"pool_id": "P1"}\n{"pool_id": "P2"}\n'      # completed records untouched
    assert Q.load_done(f) == {"P1", "P2"} and Q.load_done(tmp_path / "missing.jsonl") == set()


# ------------------------------------------------------------------------------- P1: verified labels -> training rows
def test_verified_rows_rechecked_before_entering_training(tmp_path):
    import hashlib
    import numpy as np
    from PIL import Image
    import verified_to_manifest as VM
    data = tmp_path / "data"
    (data / "img").mkdir(parents=True)
    shas = {}
    for name in ("a", "b", "c", "h"):
        Image.fromarray(np.full((200, 300), ord(name), np.uint8)).save(data / "img" / f"{name}.png")
        shas[name] = hashlib.sha256((data / "img" / f"{name}.png").read_bytes()).hexdigest()
    pool = tmp_path / "pool.csv"
    with open(pool, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["pool_id", "image_id", "image_path", "image_sha256", "source_dataset", "split_lock", "radiograph_group"])
        w.writerow(["P1", "u_a", "img/a.png", shas["a"], "dentex_unlabelled", "unassigned", "pool_g1"])
        w.writerow(["P2", "u_b", "img/b.png", shas["b"], "dentex_quadrant", "eval_locked", "pool_g2"])
        w.writerow(["P3", "u_c", "img/c.png", "0" * 64, "dentex_unlabelled", "unassigned", "pool_g3"])
        w.writerow(["P4", "h_1", "img/h.png", shas["h"], "hanoi_periapical", "unassigned", "pool_g4"])
    rvp = _reviewers(tmp_path, [DENTIST, {**DENTIST, "reviewer_id": "R2", "ls_user": "dr.b@clinic.example"}])
    log = tmp_path / "log.jsonl"
    partial = "only the suggested teeth were reviewed"

    def logged(pool_id, sha, region, label, box, status="accepted_label", reviewer="R1"):
        return CR._append(log, {"pool_id": pool_id, "image_sha256": sha, "region_id": region, "label": label, "box_xyxy": box,
                                "decision": "confirmed", "coverage": partial, "reviewer_id": reviewer, "fdi": "46",
                                "reviewed_at": "2026-10-20", "status": status})
    recs = [logged("P1", shas["a"], "ok", "Periapical Lesion", [10, 10, 60, 120]),
            logged("P1", shas["a"], "tiny", "Caries", [10, 10, 11, 11]),
            logged("P2", shas["b"], "eval", "Deep Caries", [10, 10, 60, 120]),
            logged("P3", "0" * 64, "changed", "Caries", [10, 10, 60, 120]),
            logged("P4", shas["h"], "hanoi", "Periapical Lesion", [10, 10, 60, 120]),
            logged("P1", shas["a"], "edited", "Caries", [10, 10, 60, 120]),
            logged("P1", shas["a"], "superseded", "Deep Caries", [70, 10, 120, 120]),
            logged("P1", shas["a"], "exreviewer", "Impacted", [130, 10, 180, 120], reviewer="R9")]
    later = logged("P1", shas["a"], "superseded", "Deep Caries", [70, 10, 120, 120], status="recorded_not_a_label")
    ver = tmp_path / "verified.csv"
    cols = ["pool_id", "image_sha256", "region_id", "label", "fdi", "box_xyxy", "decision", "reviewer_id", "reviewed_at", "record_hash"]
    with open(ver, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in recs:
            row = {**r, "box_xyxy": json.dumps(r["box_xyxy"])}
            if r["region_id"] == "edited":
                row["label"] = "Periapical Lesion"                      # hand-edited CSV: differs from the logged record
            w.writerow(row)
        w.writerow({"pool_id": "P1", "image_sha256": shas["a"], "region_id": "nolabel", "label": "No target finding",
                    "box_xyxy": "[1, 1, 50, 50]", "record_hash": "x"})
        w.writerow({"pool_id": "P1", "image_sha256": shas["a"], "region_id": "forged", "label": "Deep Caries",
                    "box_xyxy": "[1, 1, 50, 50]", "record_hash": "f" * 64})
    (tmp_path / "splits").mkdir()
    rows, skipped = VM.verified_training_rows(ver, pool, tmp_path / "splits", data, log=log, reviewers_csv=rvp)
    assert [r["annotation_id"] for r in rows] == ["ok"]
    r = rows[0]
    assert r["split"] == "train" and r["source_dataset"] == "clinician_verified:dentex_unlabelled" and r["radiograph_group"] == "pool_g1"
    assert r["bbox_xywh"] == [10, 10, 50, 110] and r["class_index"] == 3 and (r["image_width"], r["image_height"]) == (300, 200)
    reasons = dict(skipped)
    assert "crop rule" in reasons["P1:tiny"] and "not a target class" in reasons["P1:nolabel"]
    assert "evaluation" in reasons["P2:eval"] and "SHA-256" in reasons["P3:changed"] and "P3" in reasons["P4:hanoi"]
    assert "does not match" in reasons["P1:edited"] and "latest" in reasons["P1:superseded"] and "latest" in reasons["P1:forged"]
    assert "registry" in reasons["P1:exreviewer"] or "reviewers.csv" in reasons["P1:exreviewer"]
    assert later["status"] == "recorded_not_a_label"
    assert VM.verified_training_rows(tmp_path / "missing.csv", pool, tmp_path / "splits", data, log=log, reviewers_csv=rvp) == ([], [])
    lines = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join([lines[0].replace("Periapical Lesion", "Deep Caries")] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):                                     # tampered review log: nothing is used
        VM.verified_training_rows(ver, pool, tmp_path / "splits", data, log=log, reviewers_csv=rvp)


def test_manifest_builder_includes_verified_only_on_request():
    src = (ROOT / "scripts/dataset/build_combined_manifest.py").read_text(encoding="utf-8")
    assert '"--include-verified", action="store_true"' in src and "if a.include_verified:" in src


# ------------------------------------------------------------------------------------------ P4: draft grouped folds
def test_cv_folds_keep_groups_together_and_are_deterministic():
    import make_cv_folds as F
    rows = []
    for g in range(60):
        cls = ["Periapical Lesion"] if g % 6 == 0 else (["Deep Caries", "Caries"] if g % 3 == 0 else ["Caries", "Impacted"])
        src = "dentex_official_val" if g % 10 == 0 else "dentex_train_disease"
        rows += [{"radiograph_group": f"g{g}", "target_class": c, "source_dataset": src} for c in cls]
    a, b = F.assign_folds(rows), F.assign_folds(list(reversed(rows)))
    assert a == b and set(a) == {f"g{g}" for g in range(60)} and set(a.values()) == set(range(5))
    pl_folds = Counter(a[f"g{g}"] for g in range(0, 60, 6))
    assert max(pl_folds.values()) - min(pl_folds.values()) <= 1          # PL radiographs spread evenly
