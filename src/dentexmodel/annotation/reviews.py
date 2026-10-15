"""Human review of model regions: confirm / correct / reject candidate classes and tooth numbers, with an audit trail.

Rules enforced here (not only in the UI):
* a reviewer name is required; it is self-declared, so every record says ``reviewer_qualification = "self-declared, not verified"``
  and nothing is ever called expert-verified by the software;
* a region action must refer to a region that exists in the image's latest full analysis; classes must be among the classifier's
  classes; tooth numbers must be valid FDI codes;
* resubmitting an identical decision is rejected (duplicate); a different decision by the same reviewer creates a new revision and
  keeps the old one in the history;
* approval needs a named approver who is NOT the reviewer (second look); only approved records can be exported or used for training;
* records on test/calibration/validation-split images are stored but flagged ``usable_for_training = 0`` and never exported as training data.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path

from dentexmodel.data.fdi import is_valid_fdi
from dentexmodel.errors import DentaMindError, NotFoundError
from dentexmodel.storage import Database, jdump, jload, new_id, now

ACTIONS = ("confirm_candidate", "correct_class", "reject_candidate", "set_tooth_number", "mark_number_unassigned", "specialist_review", "unusable_image")
IMAGE_LEVEL = {"unusable_image", "specialist_review"}
QUAL = "self-declared, not verified"
_NAME = re.compile(r"^[^\x00-\x1f]{2,64}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS region_reviews(id TEXT PRIMARY KEY, image_id TEXT, region_id TEXT, analysis_id TEXT, revision INT, is_current INT,
  action TEXT, previous_json TEXT, corrected_class TEXT, corrected_fdi INT, notes TEXT, reviewer TEXT, reviewer_qualification TEXT,
  status TEXT, approved_by TEXT, approved_at TEXT, created TEXT, models_json TEXT, split TEXT, usable_for_training INT, fingerprint TEXT);
"""


class ReviewStore:
    def __init__(self, db: Database):
        self.db = db
        with db.conn() as c:
            c.executescript(SCHEMA)

    # ------------------------------------------------------------------------------------------ helpers
    @staticmethod
    def _name(v: str, what: str) -> str:
        v = (v or "").strip()
        if not _NAME.match(v):
            raise DentaMindError(f"{what} is required (2-64 characters).", code="reviewer_required",
                                 hint="Enter your name; it is recorded in the audit history.")
        return v

    def latest_full_analysis(self, image_id: str) -> dict | None:
        rows = self.db.list("analyses", where="image_id=? AND kind='full'", params=(image_id,), limit=1)
        return ({**jload(rows[0]["result_json"]), "analysis_id": rows[0]["id"]}) if rows else None

    @staticmethod
    def _labeled_hash_splits(settings) -> dict:
        """SHA-256 of every annotated main-dataset radiograph -> its split (same unit as the split groups)."""
        try:
            from dentexmodel.data.dataset import DatasetService
            return {r.content_hash: r.split for r in DatasetService(settings).manifest("main") if r.annotation_status == "annotated" and r.content_hash}
        except Exception:  # noqa: BLE001 - no manifest: there are no labeled radiographs to collide with
            return {}

    def _split_of(self, settings, image_id: str) -> tuple[str, bool]:
        """(split, usable_for_training). Only pool images (unassigned) and uploads may ever feed training. An upload that is
        pixel-identical to a labeled radiograph is that radiograph: it takes its split and is never usable (it could be a
        val/calibration/test film)."""
        if image_id.startswith("up_"):
            row = self.db.get("images", image_id) or {}
            owner = self._labeled_hash_splits(settings).get(row.get("sha256"))
            return (owner, False) if owner else ("upload", True)
        try:
            from dentexmodel.data.dataset import DatasetService
            svc = DatasetService(settings)
            for key in ("main", "test_data"):
                for r in svc.manifest(key):
                    if r.image_id == image_id:
                        usable = (key == "main" and r.split == "unassigned" and r.annotation_status != "annotated" and not r.duplicate_of)
                        return ("test_data" if key == "test_data" else r.split), usable
        except Exception:  # noqa: BLE001 - unknown image: not usable
            pass
        return "unknown", False

    # ------------------------------------------------------------------------------------------ create
    def submit(self, settings, payload: dict) -> dict:
        reviewer = self._name(payload.get("reviewer"), "Reviewer name")
        action = payload.get("action")
        if action not in ACTIONS:
            raise DentaMindError(f"Unknown action '{action}'.", code="invalid_action", hint=f"Use one of: {', '.join(ACTIONS)}.")
        image_id = str(payload.get("image_id") or "")
        analysis = self.latest_full_analysis(image_id)
        if analysis is None and action not in IMAGE_LEVEL:
            raise DentaMindError("This image has no full analysis yet.", code="no_analysis", hint="Run the full analysis first (X-ray Analysis page).")
        region_id = payload.get("region_id") or None
        region = None
        if action in IMAGE_LEVEL:
            region_id = None
        else:
            region = next((r for r in (analysis or {}).get("regions", []) if r["region_id"] == region_id), None)
            if region is None:
                raise DentaMindError("Region not found in the latest analysis of this image.", code="unknown_region",
                                     hint="Reload the analysis; region ids are tied to the model outputs they came from.")
        cc = payload.get("corrected_class") or None
        fdi = payload.get("corrected_fdi")
        classes = (region or {}).get("candidate_class", {}) and list(region["candidate_class"]["probabilities"].keys())
        if action == "correct_class":
            if not classes or cc not in classes:
                raise DentaMindError(f"Corrected class must be one of {classes or 'the classifier classes'}; there is no 'healthy' label.", code="invalid_class")
        elif action == "confirm_candidate":
            if not classes or (region["candidate_class"] or {}).get("status") != "candidate":
                raise DentaMindError("Only a region with a candidate class (not abstained) can be confirmed.", code="nothing_to_confirm",
                                     hint="Use 'correct class', 'reject candidate' or 'specialist review'.")
            cc = region["candidate_class"]["label"]
        else:
            cc = None
        if action == "set_tooth_number":
            try:
                fdi = int(fdi)
            except (TypeError, ValueError):
                raise DentaMindError("A tooth number is required.", code="invalid_fdi")
            if not is_valid_fdi(fdi):
                raise DentaMindError(f"{fdi} is not a valid FDI permanent-tooth number.", code="invalid_fdi")
        else:
            fdi = None
        notes = (payload.get("notes") or "").strip()[:500]
        fp = hashlib.sha256(json.dumps([image_id, region_id, action, cc, fdi, reviewer, notes], sort_keys=True).encode()).hexdigest()[:16]
        prev = self.db.list("region_reviews", where="image_id=? AND IFNULL(region_id,'')=? AND reviewer=? AND is_current=1",
                            params=(image_id, region_id or "", reviewer), limit=1)
        if prev and prev[0]["fingerprint"] == fp:
            raise DentaMindError("This identical decision was already submitted.", code="duplicate_submission", hint="Change the decision to add a new revision.")
        revision = (prev[0]["revision"] + 1) if prev else 1
        if prev:
            self.db.update("region_reviews", "id", prev[0]["id"], {"is_current": 0})
        split, usable = self._split_of(settings, image_id)
        snapshot = None
        if region:
            snapshot = {"candidate_class": region["candidate_class"], "fdi": region["fdi"], "fdi_confidence": region["fdi_confidence"], "box": region["box"],
                        "detection_score": region["detection_score"], "uncertainty": region["uncertainty"], "flags": region["flags"],
                        "numbering_status": region["numbering_status"]}
        rid = new_id("rev")
        self.db.insert("region_reviews", {"id": rid, "image_id": image_id, "region_id": region_id, "analysis_id": (analysis or {}).get("analysis_id"),
                                          "revision": revision, "is_current": 1, "action": action, "previous_json": jdump(snapshot), "corrected_class": cc,
                                          "corrected_fdi": fdi, "notes": notes, "reviewer": reviewer, "reviewer_qualification": QUAL, "status": "submitted",
                                          "created": now(), "models_json": jdump((analysis or {}).get("models")), "split": split,
                                          "usable_for_training": int(usable and action in ("confirm_candidate", "correct_class")), "fingerprint": fp})
        return self.get(rid)

    # ------------------------------------------------------------------------------------------ read
    def _public(self, r: dict) -> dict:
        d = dict(r)
        d["previous"] = jload(d.pop("previous_json"))
        d["models"] = jload(d.pop("models_json"))
        d["is_current"] = bool(d["is_current"])
        d["usable_for_training"] = bool(d["usable_for_training"])
        d.pop("fingerprint", None)
        return d

    def get(self, rid: str) -> dict:
        r = self.db.get("region_reviews", rid)
        if not r:
            raise NotFoundError(f"Review '{rid}' not found.")
        return self._public(r)

    def list(self, image_id: str | None = None, status: str | None = None, current_only: bool = True, limit: int = 500) -> list:
        where, params = [], []
        if image_id:
            where.append("image_id=?")
            params.append(image_id)
        if status:
            where.append("status=?")
            params.append(status)
        if current_only:
            where.append("is_current=1")
        return [self._public(r) for r in self.db.list("region_reviews", where=" AND ".join(where), params=tuple(params), limit=limit)]

    def history(self, image_id: str, region_id: str | None) -> list:
        rows = self.db.list("region_reviews", where="image_id=? AND IFNULL(region_id,'')=?", params=(image_id, region_id or ""), order="created ASC", limit=500)
        return [self._public(r) for r in rows]

    # ------------------------------------------------------------------------------------------ approve / reject
    def decide(self, ids: list, approver: str, approve: bool) -> list:
        approver = self._name(approver, "Approver name")
        out = []
        for rid in ids:
            r = self.db.get("region_reviews", rid)
            if not r:
                raise NotFoundError(f"Review '{rid}' not found.")
            if r["reviewer"].strip().lower() == approver.lower():
                raise DentaMindError("A review cannot be approved by the person who made it.", code="self_approval", hint="Ask a second reviewer.")
            if r["status"] != "submitted" or not r["is_current"]:
                raise DentaMindError(f"Review {rid} is not an open, current submission.", code="not_open")
            self.db.update("region_reviews", "id", rid, {"status": "approved" if approve else "rejected", "approved_by": approver, "approved_at": now()})
            out.append(self.get(rid))
        return out

    # ------------------------------------------------------------------------------------------ export / training
    def export(self, fmt: str = "json") -> tuple[str, str]:
        rows = [self._public(r) for r in self.db.list("region_reviews", where="status='approved' AND is_current=1", limit=100000)]
        usable = [r for r in rows if r["usable_for_training"]]
        skipped = len(rows) - len(usable)
        recs = [{"review_id": r["id"], "image_id": r["image_id"], "region_id": r["region_id"], "box": (r["previous"] or {}).get("box"), "action": r["action"],
                 "class": r["corrected_class"], "fdi": r["corrected_fdi"], "previous_prediction": (r["previous"] or {}).get("candidate_class"),
                 "reviewer": r["reviewer"], "reviewer_qualification": r["reviewer_qualification"], "approved_by": r["approved_by"],
                 "approved_at": r["approved_at"], "models": r["models"]} for r in usable]
        if fmt == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            cols = ["review_id", "image_id", "region_id", "action", "class", "fdi", "reviewer", "reviewer_qualification", "approved_by", "approved_at"]
            w.writerow(cols)
            for r in recs:
                w.writerow([r[c] for c in cols])
            return buf.getvalue(), "text/csv; charset=utf-8"
        body = {"format": "dentamind-region-reviews-v1", "exported": now(), "n_records": len(recs),
                "n_approved_but_excluded": skipped, "exclusion_rule": "records on test/calibration/validation/labelled-train images are never exported as training data",
                "note": "Reviewer identity is self-declared; no record here is expert-verified.", "records": recs}
        return json.dumps(body, indent=1), "application/json"

    def training_items(self, settings) -> tuple[list, dict]:
        """Approved, usable classification examples: ``[{path, box, label, review_id}]`` plus counts of what was skipped."""
        from dentexmodel.data.dataset import DatasetService
        paths: dict = {}
        svc = DatasetService(settings)
        for key in ("main", "test_data"):
            for r in svc.manifest(key):
                paths[r.image_id] = settings.data_root / r.file_path
        labeled = self._labeled_hash_splits(settings)
        items, skipped = [], {"not_usable": 0, "no_image": 0, "no_box": 0, "identical_to_labeled": 0}
        for r in self.db.list("region_reviews", where="status='approved' AND is_current=1 AND action IN ('confirm_candidate','correct_class')", limit=100000):
            if not r["usable_for_training"]:
                skipped["not_usable"] += 1
                continue
            prev = jload(r["previous_json"]) or {}
            p = paths.get(r["image_id"])
            if p is None and r["image_id"].startswith("up_"):
                row = self.db.get("images", r["image_id"])
                p = (settings.upload_dir / row["rel_path"]) if row else None
            if p is None or not Path(p).is_file():
                skipped["no_image"] += 1
                continue
            if hashlib.sha256(Path(p).read_bytes()).hexdigest() in labeled:   # re-checked at use: splits may have changed since submission
                skipped["identical_to_labeled"] += 1
                continue
            if not prev.get("box"):
                skipped["no_box"] += 1
                continue
            items.append({"path": str(p), "box": prev["box"], "label": r["corrected_class"], "review_id": r["id"]})
        return items, skipped
