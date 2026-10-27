"""Clinician-verified annotation workflow (Label Studio) for new finding labels.

Model output is only ever a *suggestion* (Label Studio ``predictions``). A label becomes usable only when a reviewer who is listed
in ``data/annotation/reviewers.csv`` (qualified dental professional, attested by the project owner) explicitly sets the region
decision to ``confirmed`` or ``corrected``. Every imported decision is appended to ``data/annotation/clinical_reviews.jsonl``
(append-only, SHA-256 hash chain); nothing is overwritten and original dataset files are never modified.

Policy enforced here:
* "No target finding" / "Not assessable" are recorded for the audit trail but are NEVER exported as labels (no healthy class,
  unlabelled teeth are never negatives).
* A region without a decision, or from an unregistered reviewer, is rejected with a reason. ``uncertain`` decisions and the
  "Not assessable" (ungradable) label are recorded, never exported as labels.
* Re-importing the same export is idempotent (identical decisions are not appended twice).
* Training eligibility is NOT taken from task metadata: it is re-derived at export from data/annotation/annotation_pool.csv and the
  frozen evaluation manifests (any radiograph in validation / calibration / test, or eval_locked in the pool, is excluded).
* Hanoi radiographs are training-eligible only with coverage "all target findings ... marked" (protocol proposal P3).
* Corrections of existing DENTEX labels are stored as separate correction records that reference the original annotation id.

CLI:
    python scripts/dataset/clinical_review.py config              > data/annotation/review_config.xml
    python scripts/dataset/clinical_review.py import EXPORT.json  # Label Studio JSON export
    python scripts/dataset/clinical_review.py export              # -> data/annotation/verified_findings.csv
    python scripts/dataset/clinical_review.py verify              # hash-chain integrity check
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANN = ROOT / "data" / "annotation"
TARGET = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
NON_LABELS = ["No target finding", "Not assessable"]
DECISIONS = ["confirmed", "corrected", "rejected", "uncertain"]
REVIEWER_FIELDS = ["reviewer_id", "display_name", "qualification", "registration_no", "ls_user", "attested_by", "attested_on"]
FDI = [str(q * 10 + t) for q in (1, 2, 3, 4) for t in range(1, 9)]


def review_config_xml() -> str:
    labels = "\n".join(f'    <Label value="{v}"/>' for v in TARGET + NON_LABELS)
    fdi = "\n".join(f'    <Choice value="{c}"/>' for c in FDI)
    dec = "\n".join(f'    <Choice value="{c}"/>' for c in DECISIONS)
    return f"""<View>
  <Header value="DentaMind clinical review - pre-drawn boxes are MODEL SUGGESTIONS, not diagnoses. Decide every region."/>
  <Text name="hint" value="$hint"/>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>
  <RectangleLabels name="tooth" toName="image" strokeWidth="2">
{labels}
  </RectangleLabels>
  <Choices name="decision" toName="image" perRegion="true" required="true" choice="single">
{dec}
  </Choices>
  <Choices name="tooth_fdi" toName="image" perRegion="true" choice="single">
{fdi}
  </Choices>
  <TextArea name="region_notes" toName="image" perRegion="true" placeholder="optional note"/>
  <Choices name="coverage" toName="image" choice="single" required="true">
    <Choice value="all target findings on this radiograph are marked"/>
    <Choice value="only the suggested teeth were reviewed"/>
  </Choices>
</View>
"""


def build_review_task(pool_row: dict, image_url: str, teeth: list, model_version: str) -> dict:
    """teeth: [{"box": xyxy px, "fdi": int|None, "suggestion": class, "probs": {class: p}, "queue_id": str}]."""
    w, h = int(pool_row["width"]), int(pool_row["height"])
    res = []
    for t in teeth:
        x1, y1, x2, y2 = t["box"]
        rid = t["queue_id"]
        res.append({"id": rid, "from_name": "tooth", "to_name": "image", "type": "rectanglelabels", "original_width": w,
                    "original_height": h, "image_rotation": 0,
                    "value": {"x": 100 * x1 / w, "y": 100 * y1 / h, "width": 100 * (x2 - x1) / w, "height": 100 * (y2 - y1) / h,
                              "rotation": 0, "rectanglelabels": [t["suggestion"]]}, "score": max(t["probs"].values())})
        if t.get("fdi"):
            res.append({"id": rid, "from_name": "tooth_fdi", "to_name": "image", "type": "choices", "value": {"choices": [str(t["fdi"])]}})
    hint = "Model suggestions only. " + (pool_row.get("external_hint") or "")
    return {"data": {"image": image_url, "image_id": pool_row["image_id"], "pool_id": pool_row["pool_id"], "hint": hint},
            "meta": {"pool_id": pool_row["pool_id"], "image_sha256": pool_row["image_sha256"], "source_dataset": pool_row["source_dataset"],
                     "split_lock": pool_row["split_lock"], "width": w, "height": h},
            "predictions": [{"model_version": f"SUGGESTION ONLY - {model_version}", "result": res}]}


# ------------------------------------------------------------------------------------------------------------ reviewers
def load_reviewers(path=None) -> dict:
    path = Path(path or ANN / "reviewers.csv")
    if not path.is_file():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ok = {}
    for r in rows:
        if r.get("reviewer_id") and r.get("qualification") and r.get("attested_by") and r.get("ls_user"):
            ok[str(r["ls_user"]).strip().lower()] = r
    return ok


def ensure_reviewer_file(path=None):
    path = Path(path or ANN / "reviewers.csv")
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(REVIEWER_FIELDS)
    return path


# ------------------------------------------------------------------------------------------------------- audit log
def _last_hash(log: Path) -> str:
    if not log.is_file():
        return "0" * 64
    last = None
    with open(log, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last = line
    return json.loads(last)["record_hash"] if last else "0" * 64


def _append(log: Path, rec: dict) -> dict:
    rec = {**rec, "prev_hash": _last_hash(log)}
    rec["record_hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def verify_chain(log=None) -> tuple[bool, int]:
    log = Path(log or ANN / "clinical_reviews.jsonl")
    prev, n = "0" * 64, 0
    if not log.is_file():
        return True, 0
    with open(log, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            h = rec.pop("record_hash")
            if rec["prev_hash"] != prev or hashlib.sha256(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != h:
                return False, n
            prev, n = h, n + 1
    return True, n


# ------------------------------------------------------------------------------------------------------------ import
def parse_export(tasks: list, reviewers: dict, export_name: str) -> list:
    """Label Studio JSON export -> review records (accepted and rejected, each with a status and reason)."""
    out, now = [], datetime.now(timezone.utc).isoformat()
    for t in tasks:
        meta, data = t.get("meta") or {}, t.get("data") or {}
        for ann in t.get("annotations", []):
            if ann.get("was_cancelled"):
                continue
            user = ann.get("completed_by")
            user_key = str(user.get("email") if isinstance(user, dict) else user).strip().lower()
            reviewer = reviewers.get(user_key)
            regions, coverage = {}, None
            for r in ann.get("result", []):
                v, rid = r.get("value", {}), r.get("id")
                if r.get("from_name") == "coverage":
                    coverage = (v.get("choices") or [None])[0]
                    continue
                e = regions.setdefault(rid, {})
                if r.get("type") == "rectanglelabels":
                    W, H = r.get("original_width"), r.get("original_height")
                    e["label"] = (v.get("rectanglelabels") or [None])[0]
                    e["box_xyxy"] = [round(v["x"] * W / 100, 1), round(v["y"] * H / 100, 1),
                                     round((v["x"] + v["width"]) * W / 100, 1), round((v["y"] + v["height"]) * H / 100, 1)]
                elif r.get("from_name") == "decision":
                    e["decision"] = (v.get("choices") or [None])[0]
                elif r.get("from_name") == "tooth_fdi":
                    e["fdi"] = (v.get("choices") or [None])[0]
                elif r.get("from_name") == "region_notes":
                    e["notes"] = " ".join(v.get("text") or [])
            for rid, e in regions.items():
                if "box_xyxy" not in e:
                    continue
                problems = []
                if reviewer is None:
                    problems.append(f"reviewer '{user_key}' not in data/annotation/reviewers.csv (qualification not attested)")
                if e.get("decision") not in DECISIONS:
                    problems.append("no explicit decision (confirmed / corrected / rejected)")
                usable = not problems and e.get("decision") in ("confirmed", "corrected") and e.get("label") in TARGET
                status = "rejected_invalid" if problems else ("accepted_label" if usable else "recorded_not_a_label")
                out.append({"type": "review", "imported_at": now, "export_file": export_name, "ls_task_id": t.get("id"),
                            "ls_annotation_id": ann.get("id"), "pool_id": meta.get("pool_id") or data.get("pool_id"),
                            "image_id": data.get("image_id"), "image_sha256": meta.get("image_sha256"),
                            "source_dataset": meta.get("source_dataset"), "split_lock": meta.get("split_lock"),
                            "region_id": rid, "label": e.get("label"), "decision": e.get("decision"), "fdi": e.get("fdi"),
                            "box_xyxy": e["box_xyxy"], "notes": e.get("notes", ""), "coverage": coverage,
                            "reviewer_id": reviewer["reviewer_id"] if reviewer else None, "reviewer_user": user_key,
                            "reviewed_at": ann.get("updated_at") or ann.get("created_at"), "status": status, "problems": problems,
                            "original_annotation_id": meta.get("original_annotation_id")})
    return out


def import_export(export_path, log=None, reviewers_path=None) -> dict:
    tasks = json.loads(Path(export_path).read_text(encoding="utf-8"))
    recs = parse_export(tasks, load_reviewers(reviewers_path), Path(export_path).name)
    log = Path(log or ANN / "clinical_reviews.jsonl")
    seen = set()
    if log.is_file():
        with open(log, encoding="utf-8") as fh:
            seen = {_decision_key(json.loads(l)) for l in fh if l.strip()}
    from collections import Counter
    counts = Counter()
    for r in recs:
        k = _decision_key(r)
        if k in seen:
            counts["skipped_already_imported"] += 1
            continue
        seen.add(k)
        _append(log, r)
        counts[r["status"]] += 1
    return dict(counts)


def _decision_key(r: dict) -> tuple:
    """Identity of one reviewer decision; re-importing the same export yields the same key."""
    return (r.get("ls_task_id"), r.get("ls_annotation_id"), r.get("region_id"), r.get("reviewer_user"), r.get("reviewed_at"),
            r.get("label"), r.get("decision"), json.dumps(r.get("box_xyxy")), r.get("fdi"), r.get("coverage"))


def latest_decisions(log=None) -> dict:
    """Latest record per (pool_id, region_id): a later review supersedes an earlier one, but both stay in the log."""
    log = Path(log or ANN / "clinical_reviews.jsonl")
    cur = {}
    if log.is_file():
        with open(log, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    cur[(r["pool_id"], r["region_id"])] = r
    return cur


FULL_COVERAGE = "all target findings on this radiograph are marked"


def _frozen_eval_shas(splits_dir=None) -> set:
    d = Path(splits_dir or ROOT / "data" / "splits")
    out = set()
    for s in ("validation", "calibration", "test"):
        f = d / f"combined_{s}.csv"
        if f.is_file():
            with open(f, newline="", encoding="utf-8") as fh:
                out |= {r["image_sha256"] for r in csv.DictReader(fh)}
    return out


def training_eligibility(rec: dict, pool: dict, eval_shas: set) -> str:
    """'' if the accepted label may be used for training, else the reason. Never trusts task metadata for the split."""
    p = pool.get(rec.get("pool_id"))
    if p is None:
        return "radiograph not in data/annotation/annotation_pool.csv"
    if p["image_sha256"] != rec.get("image_sha256"):
        return "image SHA-256 differs from the pool record"
    if p["split_lock"] == "eval_locked" or p["image_sha256"] in eval_shas:
        return "evaluation radiograph (frozen validation / calibration / test or eval_locked twin)"
    if p["source_dataset"] == "hanoi_periapical" and rec.get("coverage") != FULL_COVERAGE:
        return "Hanoi radiograph without full four-class review (P3)"
    return ""


def export_verified(out=None, log=None, pool_csv=None, splits_dir=None) -> dict:
    """verified_findings.csv = accepted labels that are training-eligible; verified_findings_not_for_training.csv = accepted
    labels excluded with a reason. Returns counts of findings and unique radiographs for both."""
    rows = [r for r in latest_decisions(log).values() if r["status"] == "accepted_label"]
    pool_csv = Path(pool_csv or ANN / "annotation_pool.csv")
    with open(pool_csv, newline="", encoding="utf-8") as fh:
        pool = {r["pool_id"]: r for r in csv.DictReader(fh)}
    eval_shas = _frozen_eval_shas(splits_dir)
    out = Path(out or ANN / "verified_findings.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["pool_id", "image_id", "image_sha256", "source_dataset", "split_lock", "region_id", "label", "fdi", "box_xyxy",
            "decision", "coverage", "reviewer_id", "reviewed_at", "record_hash", "original_annotation_id", "excluded_reason"]
    ok, excl = [], []
    for r in sorted(rows, key=lambda r: (r["pool_id"], r["region_id"])):
        why = training_eligibility(r, pool, eval_shas)
        row = {**r, "split_lock": pool.get(r["pool_id"], {}).get("split_lock", "unknown"), "box_xyxy": json.dumps(r["box_xyxy"]),
               "excluded_reason": why}
        (excl if why else ok).append(row)
    for path, data in ((out, ok), (out.with_name("verified_findings_not_for_training.csv"), excl)):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)
    return {"training_eligible_findings": len(ok), "training_eligible_radiographs": len({r["image_sha256"] for r in ok}),
            "excluded_findings": len(excl), "excluded_radiographs": len({r["image_sha256"] for r in excl})}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "config":
        print(review_config_xml())
    elif cmd == "import":
        print(import_export(sys.argv[2]))
    elif cmd == "export":
        print(export_verified())
    elif cmd == "verify":
        print("chain ok, records:", verify_chain())
    else:
        print(__doc__)
