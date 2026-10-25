#!/usr/bin/env python
"""Clinician review queue: rank pool radiographs for review using expert hints and the CURRENT production models (read-only).

    .venv\\Scripts\\python.exe scripts\\dataset\\build_annotation_queue.py score        # resumable model scoring (GPU if available)
    .venv\\Scripts\\python.exe scripts\\dataset\\build_annotation_queue.py queue [--batch-size 300 --audit-frac 0.1]

score: for every pool radiograph with split_lock train/unassigned, tooth boxes come from DENTEX enumeration ground truth when
       available, otherwise from the production tooth detector (+ numbering model for FDI). Each tooth crop is classified by the
       production finding classifier. Results: data/annotation/pool_model_scores.jsonl (one line per radiograph, resumable).
queue: review batch 1 in three tiers
       A  expert marks from other taxonomies used as hints only: DENTEX-test '7-lezyon' tooth polygons, Hanoi PAI>=3 lesion boxes
       B  model priority: at most 2 teeth with P(PL) >= 0.9 and 2 teeth with P(DC) >= 0.8 per radiograph
       C  seeded random audit sample, reviewed fully with NO suggestions (unbiased yield estimate)
       Writes reports/annotation_review_queue.csv, data/annotation/review_batch_01_tasks.json (Label Studio),
       data/annotation/review_config.xml and data/annotation/review_batch_01_stats.json.

The classifier has no "healthy" class and was trained only on teeth with findings: on unlabelled radiographs it gives P(PL) >= 0.5 for
about 14 % of ALL teeth. Its probabilities only order the review; they are not evidence that a tooth is diseased or healthy.
No production file, model or threshold is changed.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from urllib.parse import quote
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(Path(__file__).resolve().parent)]
from clinical_review import build_review_task, review_config_xml  # noqa: E402
from dsutil import read_csv, write_csv  # noqa: E402

DATA = ROOT / "data"
ANN = DATA / "annotation"
SCORES = ANN / "pool_model_scores.jsonl"
CLS = ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"]
PL_TOPK, PL_MIN = 2, 0.90
DC_TOPK, DC_MIN = 2, 0.80
TEST_LABELS = DATA / "raw/external/dentex_hf/test_data/disease/label"


def gt_tooth_boxes():
    """image file name -> [(xyxy, fdi)] from the DENTEX quadrant_enumeration COCO file (ground-truth tooth boxes)."""
    c = json.loads((DATA / "training_data/quadrant_enumeration/train_quadrant_enumeration.json").read_text(encoding="utf-8"))
    c1 = {x["id"]: x["name"] for x in c["categories_1"]}
    c2 = {x["id"]: x["name"] for x in c["categories_2"]}
    names = {im["id"]: im["file_name"] for im in c["images"]}
    out = {}
    for a in c["annotations"]:
        x, y, w, h = a["bbox"]
        out.setdefault(names[a["image_id"]], []).append(([x, y, x + w, y + h], int(c1[a["category_id_1"]]) * 10 + int(c2[a["category_id_2"]])))
    return out


def load_done(path) -> set:
    """Pool ids already scored. A trailing line without a newline is the partial write of a killed run: it is removed (and
    reported) so the resumed run neither crashes nor appends onto it. Completed records are never rewritten."""
    path = Path(path)
    if not path.is_file():
        return set()
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        cut = raw.rfind(b"\n") + 1
        with open(path, "r+b") as fh:
            fh.truncate(cut)
        print(f"removed an incomplete trailing record ({len(raw) - cut} bytes) left by an interrupted run", flush=True)
        raw = raw[:cut]
    return {json.loads(l)["pool_id"] for l in raw.decode("utf-8").splitlines() if l.strip()}


def score(limit=None):
    from dentexmodel.config import get_settings
    from dentexmodel.data.preprocess import load_gray
    from dentexmodel.inference import torch_models as TM
    s = get_settings()
    pool = [r for r in read_csv(ANN / "annotation_pool.csv") if r["split_lock"] in ("train", "unassigned")]
    done = load_done(SCORES)
    gt = gt_tooth_boxes()
    todo = [r for r in pool if r["pool_id"] not in done][: limit or None]
    print(f"pool (train/unassigned): {len(pool)}, already scored: {len(done)}, to score: {len(todo)}", flush=True)
    t0 = time.time()
    with open(SCORES, "a", encoding="utf-8") as fh:
        for i, r in enumerate(todo):
            g = load_gray(DATA / r["image_path"])
            rgb = np.repeat(g[..., None], 3, axis=2)
            H, W = g.shape
            name = Path(r["image_path"]).name
            if r["tooth_boxes_available"].startswith("yes") and name in gt:
                teeth = [{"box": b, "fdi": f, "box_source": "dentex_enumeration_gt", "fdi_source": "dentex_enumeration_gt"} for b, f in gt[name]]
                det_model = None
            else:
                det = TM.detect_teeth(rgb, r["image_id"], s)
                teeth = [{"box": [round(v, 1) for v in d.box], "score": round(d.score, 4), "fdi": None,
                          "box_source": f"model:{det.model_version}"} for d in det.detections]
                det_model = det.model_version
                if teeth:
                    num = TM.number_teeth(rgb, teeth, s)
                    for t in teeth:
                        t["fdi_source"] = f"model:{num['model_version']}" if t.get("fdi") else None
            probs = TM.classify_regions(rgb, [t["box"] for t in teeth], s)["probabilities"] if teeth else []
            for t, p in zip(teeth, probs):
                t["probs"] = None if p is None else {c: round(float(v), 4) for c, v in zip(CLS, p)}
            fh.write(json.dumps({"pool_id": r["pool_id"], "image_id": r["image_id"], "width": W, "height": H, "detector": det_model,
                                 "teeth": teeth}) + "\n")
            fh.flush()
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(todo)}  {(time.time() - t0) / (i + 1):.2f}s/img", flush=True)
    print("done", flush=True)


# ------------------------------------------------------------------------------------------------------------- hints
def turkish_lesion_hints(image_id):
    """DENTEX official-test '7-lezyon' tooth polygons -> [(xyxy, fdi)] (expert marks in another taxonomy; review hints only)."""
    if not image_id.startswith("dxtest_"):
        return []
    f = TEST_LABELS / f"{image_id[len('dxtest_'):]}.json"
    if not f.is_file():
        return []
    out = []
    for sh in json.loads(f.read_text(encoding="utf-8"))["shapes"]:
        code, _, tooth = sh["label"].rpartition("-")
        if code == "7-lezyon":
            xs, ys = [q[0] for q in sh["points"]], [q[1] for q in sh["points"]]
            out.append(([min(xs), min(ys), max(xs), max(ys)], int(tooth) if tooth.isdigit() else None))
    return out


def hanoi_lesion_hints(pool_row):
    """Hanoi PAI lesion boxes for this radiograph -> [(xyxy, 'PAI n')]; empty until scripts/dataset/hanoi_mapping.py exists."""
    if pool_row.get("source_dataset") != "hanoi_periapical":
        return []
    try:
        from hanoi_mapping import lesion_boxes
    except ImportError:
        return []
    return lesion_boxes(pool_row)


def _inter(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def suggestions_for(rec, pool_row):
    """(tier, suggestions) for one scored radiograph. Expert hints take precedence over model suggestions."""
    teeth = [t for t in rec["teeth"] if t.get("probs")]
    hints = turkish_lesion_hints(rec["image_id"])
    if hints:
        return "A_expert_hint_periapical", [{"box": b, "fdi": f, "box_source": "DENTEX-test Turkish tooth polygon (7-lezyon)",
                                             "fdi_source": "DENTEX-test Turkish label", "suggestion": "Periapical Lesion", "probs": None,
                                             "hint": "expert mark '7-lezyon' (different taxonomy, unverified)"} for b, f in hints]
    hl = hanoi_lesion_hints(pool_row)
    if hl:
        out = []
        for box, pai in hl:     # model tooth box with the largest overlap with the lesion box (suggestion only)
            best = max(teeth, key=lambda t: _inter(t["box"], box), default=None)
            if best is not None and _inter(best["box"], box) > 0:
                out.append({**best, "suggestion": "Periapical Lesion", "hint": f"Hanoi lesion {pai} at {[round(v) for v in box]}"})
        if out:
            return "A_expert_hint_periapical", out
    pl = sorted([t for t in teeth if t["probs"]["Periapical Lesion"] >= PL_MIN], key=lambda t: -t["probs"]["Periapical Lesion"])[:PL_TOPK]
    dc = sorted([t for t in teeth if t["probs"]["Deep Caries"] >= DC_MIN and t not in pl], key=lambda t: -t["probs"]["Deep Caries"])[:DC_TOPK]
    return "B_model_priority", ([{**t, "suggestion": "Periapical Lesion", "hint": ""} for t in pl]
                                + [{**t, "suggestion": "Deep Caries", "hint": ""} for t in dc])


# ------------------------------------------------------------------------------------------------------------- queue
def queue(batch_size=300, audit_frac=0.10, seed=42, tier_a_max=None):
    pool = {r["pool_id"]: r for r in read_csv(ANN / "annotation_pool.csv")}
    recs = [json.loads(l) for l in SCORES.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = [r for r in recs if r["pool_id"] in pool]
    stale = [r["pool_id"] for r in recs if r["image_id"] != pool[r["pool_id"]]["image_id"]]
    if stale:
        raise SystemExit(f"{len(stale)} score records no longer match the pool (e.g. {stale[:3]}); delete {SCORES} and re-run 'score'")

    def mx(rec, c):
        return max([t["probs"][c] for t in rec["teeth"] if t.get("probs")] or [0.0])
    info = {}
    for rec in recs:
        rec["max_pl"], rec["max_dc"] = mx(rec, "Periapical Lesion"), mx(rec, "Deep Caries")
        info[rec["pool_id"]] = suggestions_for(rec, pool[rec["pool_id"]])
    n_audit = int(round(batch_size * audit_frac))
    tier_a = [r for r in recs if info[r["pool_id"]][0].startswith("A")]
    random.Random(seed).shuffle(tier_a)
    # same-domain DENTEX expert hints first, then external (Hanoi) hints
    tier_a.sort(key=lambda r: pool[r["pool_id"]]["source_dataset"] == "hanoi_periapical")
    tier_a = tier_a[: min(len(tier_a), tier_a_max or (batch_size - n_audit) // 2)]
    chosen, reason = list(tier_a), {r["pool_id"]: "A_expert_hint_periapical" for r in tier_a}
    rest = [r for r in recs if r["pool_id"] not in reason and info[r["pool_id"]][0].startswith("B") and info[r["pool_id"]][1]]
    by_pl = sorted(rest, key=lambda r: -r["max_pl"])
    by_dc = sorted(rest, key=lambda r: -r["max_dc"])
    for a, b in zip(by_pl, by_dc):
        for rec in (a, b):
            if len(chosen) < batch_size - n_audit and rec["pool_id"] not in reason:
                chosen.append(rec)
                reason[rec["pool_id"]] = "B_model_priority"
        if len(chosen) >= batch_size - n_audit:
            break
    # audit = yield estimate for the DENTEX pool; Hanoi radiographs were all selected for lesions, so they are not audited
    left = [r for r in recs if r["pool_id"] not in reason and pool[r["pool_id"]]["source_dataset"] != "hanoi_periapical"]
    for rec in random.Random(seed + 1).sample(left, min(n_audit, len(left))):
        chosen.append(rec)
        reason[rec["pool_id"]] = "C_random_audit_full_review"

    rows, tasks = [], []
    for rank, rec in enumerate(chosen, 1):
        p = pool[rec["pool_id"]]
        why = reason[rec["pool_id"]]
        sugg = [] if why.startswith("C") else [{**t, "queue_id": f"{rec['pool_id']}_s{k:02d}"} for k, t in enumerate(info[rec["pool_id"]][1])]
        base = {"batch": "01", "priority_rank": rank, "selection_reason": why, "pool_id": p["pool_id"], "source_dataset": p["source_dataset"],
                "image_id": p["image_id"], "image_path": p["image_path"], "image_sha256": p["image_sha256"],
                "radiograph_group": p["radiograph_group"], "split_lock": p["split_lock"], "external_hint": p["external_hint"],
                "max_p_periapical": round(rec["max_pl"], 4), "max_p_deep_caries": round(rec["max_dc"], 4),
                "review_status": "pending", "reviewer_id": "", "reviewed_at": "", "clinician_label": "", "clinician_decision": "", "notes": ""}
        for t in sugg:
            pr = t.get("probs") or {}
            rows.append({**base, "queue_id": t["queue_id"], "review_scope": "suggested tooth, then mark any other target findings",
                         "fdi_suggested": t.get("fdi") or "", "fdi_source": t.get("fdi_source") or "", "box_source": t["box_source"],
                         "tooth_box_xyxy": json.dumps([round(v, 1) for v in t["box"]]), "model_suggestion": t["suggestion"],
                         "suggestion_basis": t.get("hint") or "model probability",
                         **{f"p_{c.lower().replace(' ', '_')}": pr.get(c, "") for c in CLS}})
        if not sugg:
            rows.append({**base, "queue_id": f"{p['pool_id']}_full", "review_scope": "full radiograph, no suggestion shown",
                         "fdi_suggested": "", "fdi_source": "", "box_source": "", "tooth_box_xyxy": "", "model_suggestion": "",
                         "suggestion_basis": "", **{f"p_{c.lower().replace(' ', '_')}": "" for c in CLS}})
        row_p = {**p, "width": rec["width"], "height": rec["height"]}
        task_sugg = [{**t, "probs": t.get("probs") or {"hint": 1.0}} for t in sugg]
        tasks.append(build_review_task(row_p, "/data/local-files/?d=" + quote(p["image_path"]), task_sugg,
                                       "production dentex_findings_classification_v1 / external expert hints"))
    cols = ["queue_id", "batch", "priority_rank", "selection_reason", "review_scope", "pool_id", "source_dataset", "image_id",
            "image_path", "image_sha256", "radiograph_group", "split_lock", "box_source", "tooth_box_xyxy", "fdi_suggested", "fdi_source",
            "model_suggestion", "suggestion_basis", "p_caries", "p_deep_caries", "p_impacted", "p_periapical_lesion", "max_p_periapical",
            "max_p_deep_caries", "external_hint", "review_status", "reviewer_id", "reviewed_at", "clinician_label", "clinician_decision", "notes"]
    write_csv(ROOT / "reports/annotation_review_queue.csv", rows, cols)
    (ANN / "review_batch_01_tasks.json").write_text(json.dumps(tasks, indent=1, ensure_ascii=False), encoding="utf-8")
    (ANN / "review_config.xml").write_text(review_config_xml(), encoding="utf-8")
    n_sugg_rad = sum(1 for r in chosen if not reason[r["pool_id"]].startswith("C"))
    stats = {"scored_radiographs": len(recs), "batch_radiographs": len(chosen), "queue_rows": len(rows),
             "by_tier": dict(Counter(reason[r["pool_id"]] for r in chosen)),
             "by_source": dict(Counter(pool[r["pool_id"]]["source_dataset"] for r in chosen)),
             "suggested_teeth": sum(1 for r in rows if r["model_suggestion"]),
             "suggestions_per_suggested_radiograph": round(sum(1 for r in rows if r["model_suggestion"]) / max(1, n_sugg_rad), 2),
             "tier_A_available": sum(1 for r in recs if info[r["pool_id"]][0].startswith("A")),
             "tier_B_available": sum(1 for r in recs if info[r["pool_id"]][0].startswith("B") and info[r["pool_id"]][1]),
             "rule": {"model_PL": f"top {PL_TOPK} teeth with p >= {PL_MIN}", "model_DC": f"top {DC_TOPK} teeth with p >= {DC_MIN}",
                      "audit": f"{audit_frac:.0%} seeded random sample, full review, no suggestions"}}
    (ANN / "review_batch_01_stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["score", "queue"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch-size", type=int, default=300)
    ap.add_argument("--audit-frac", type=float, default=0.10)
    ap.add_argument("--tier-a-max", type=int)
    a = ap.parse_args()
    score(a.limit) if a.cmd == "score" else queue(a.batch_size, a.audit_frac, tier_a_max=a.tier_a_max)
