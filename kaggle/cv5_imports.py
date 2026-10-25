"""Clinician-verified training imports for CV5 (protocol reports/cv5_acceptance_protocol.md rev 3, section 3.1; DRAFT Amendment 02).

Imports are OFF by default: with no manifest, every function here returns the CV5 plans unchanged (the same objects).

An import manifest is an immutable JSON file (format FORMAT) built locally by scripts/dataset/build_cv5_import_manifest.py from the P1
route. Before any use it must:
* match the SHA-256 registered for it (Amendment 02), and its own internal content hash;
* contain, for every finding, the clinician-verification record (latest accepted review-log decision, registered reviewer), the label
  source, the pool identity and split lock, and a source whose licence / provenance metadata is complete;
* be internally consistent (no duplicate finding, image or box; one radiograph group per image).

Independence (section 3.1 item 4) is enforced here on identities (radiograph group, image SHA-256) against the CV pool, the
calibration and test splits and the eval_locked pool groups. Under CV every pool radiograph is held out once, so a pool row locked
"train" (a twin of a CV-pool radiograph) is refused as well - stricter than P1, which was written for a single split. The
near-duplicate image check (dHash + correlation) is cv5_accept.gate_v6 and needs the image files (gate_v6_for_manifest).

Imported rows are added to the FITTING part of every fold only (augment_plans); inner validation, held-out and secondary held-out
lists are passed through untouched. Nothing here writes a file.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from dsutil import CLASSES

FORMAT = "dentamind-cv5-import-manifest-v2"            # v2: reviewer-authorization reference + per-finding binding hash
AUTH_FORMAT = "dentamind-reviewer-authorization-v1"
AUTH_REVIEWER_FIELDS = ("reviewer_id", "qualification_attested", "attested_on", "valid_from", "valid_to", "status", "revoked_on")
BINDING_FIELDS = ("sample_id", "image_sha256", "radiograph_group", "bbox_xywh", "target_class", "source_id", "label_source")
BINDING_VERIFICATION_FIELDS = ("review_record_hash", "reviewer_id", "decision", "reviewed_at")
# P2 targets as in scripts/dataset/expansion_report.py TARGET_TRAIN (provisional P2 of 2026-10-16); the binding count is that report
P2_TARGETS = {"Periapical Lesion": {"findings": 300, "radiographs": 200}, "Deep Caries": {"findings": 750, "radiographs": 400}}
FINDING_FIELDS = ("sample_id", "pool_id", "region_id", "split_lock", "image_path", "image_sha256", "radiograph_group", "bbox_xywh",
                  "target_class", "class_index", "source_dataset", "source_id", "label_source", "verification")
VERIFICATION_FIELDS = ("review_record_hash", "reviewer_id", "status", "decision", "reviewed_at")
SOURCE_FIELDS = ("name", "licence", "licence_terms_url", "provenance_url_or_doi", "version", "retrieved_on", "archive_sha256",
                 "label_taxonomy", "label_mapping", "ethics_statement")
ACCEPTED_DECISIONS = ("confirmed", "corrected")
IMPORTABLE_SPLIT_LOCK = "unassigned"


class ImportRefused(ValueError):
    pass


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_sha256(findings: list, sources: dict) -> str:
    return hashlib.sha256(canonical({"findings": findings, "sources": sources})).hexdigest()


def _sha_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _is_hex64(s) -> bool:
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def validate_manifest(m: dict, reviewer_ids=None) -> dict:
    """Structural, verification, provenance and consistency checks. Returns a summary; raises ImportRefused listing every problem."""
    probs = []
    if m.get("format") != FORMAT:
        raise ImportRefused(f"not a {FORMAT} manifest")
    findings, sources = m.get("findings"), m.get("sources")
    if not isinstance(findings, list) or not findings:
        raise ImportRefused("manifest has no findings: an empty import is never a valid import")
    if not isinstance(sources, dict) or not sources:
        raise ImportRefused("manifest has no source provenance records")
    if m.get("content_sha256") != content_sha256(findings, sources):
        raise ImportRefused("content_sha256 does not match the findings / sources: the manifest was edited after it was built")
    ra = m.get("reviewer_authorization") or {}
    if not _is_hex64(ra.get("sha256")) or not isinstance(ra.get("version"), int):
        raise ImportRefused("manifest does not reference a reviewer-authorization version and SHA-256")
    for sid, s in sources.items():
        miss = [f for f in SOURCE_FIELDS if _blank(s.get(f))]
        if miss:
            probs.append(f"source {sid}: missing provenance / licence fields {miss}")
    seen_ids, seen_boxes, group_of_image, image_of = set(), set(), {}, {}
    for i, f in enumerate(findings):
        tag = f.get("sample_id") or f"#{i}"
        miss = [k for k in FINDING_FIELDS if _blank(f.get(k))]
        if miss:
            probs.append(f"{tag}: missing fields {miss}")
            continue
        v = f["verification"]
        vmiss = [k for k in VERIFICATION_FIELDS if _blank(v.get(k))]
        if vmiss:
            probs.append(f"{tag}: incomplete clinician-verification record {vmiss}")
        if v.get("status") != "accepted_label" or v.get("decision") not in ACCEPTED_DECISIONS:
            probs.append(f"{tag}: not an accepted clinician label (status {v.get('status')!r}, decision {v.get('decision')!r})")
        if not _is_hex64(v.get("review_record_hash")):
            probs.append(f"{tag}: review_record_hash is not a SHA-256")
        if reviewer_ids is not None and v.get("reviewer_id") not in reviewer_ids:
            probs.append(f"{tag}: reviewer {v.get('reviewer_id')!r} is not registered")
        if f["target_class"] not in CLASSES or int(f["class_index"]) != CLASSES.index(f["target_class"]):
            probs.append(f"{tag}: class {f['target_class']!r} / index {f['class_index']!r} invalid")
        if f["source_id"] not in sources:
            probs.append(f"{tag}: source {f['source_id']!r} has no provenance record")
        if f["split_lock"] != IMPORTABLE_SPLIT_LOCK:
            probs.append(f"{tag}: pool split_lock {f['split_lock']!r} - only {IMPORTABLE_SPLIT_LOCK!r} radiographs may be imported under CV")
        if not _is_hex64(f["image_sha256"]):
            probs.append(f"{tag}: image_sha256 is not a SHA-256")
        bb = json.loads(f["bbox_xywh"]) if isinstance(f["bbox_xywh"], str) else f["bbox_xywh"]
        if not (isinstance(bb, list) and len(bb) == 4 and all(isinstance(x, (int, float)) for x in bb) and bb[2] > 0 and bb[3] > 0):
            probs.append(f"{tag}: bbox_xywh invalid")
        if f.get("binding_sha256") != binding_sha256(f, ra.get("sha256")):
            probs.append(f"{tag}: binding hash does not match its review record / reviewer / label / image / group / authorization")
        if f["sample_id"] in seen_ids:
            probs.append(f"{tag}: duplicate sample_id")
        seen_ids.add(f["sample_id"])
        key = (f["image_sha256"], json.dumps(bb))
        if key in seen_boxes:
            probs.append(f"{tag}: duplicate finding (same image and box)")
        seen_boxes.add(key)
        g = group_of_image.setdefault(f["image_sha256"], f["radiograph_group"])
        if g != f["radiograph_group"]:
            probs.append(f"{tag}: image {f['image_sha256'][:12]} appears under two radiograph groups ({g}, {f['radiograph_group']})")
        p = image_of.setdefault(f["image_sha256"], f["image_path"])
        if p != f["image_path"]:
            probs.append(f"{tag}: image {f['image_sha256'][:12]} appears under two paths")
    if probs:
        raise ImportRefused(f"{len(probs)} problem(s): " + "; ".join(probs[:20]) + (" ..." if len(probs) > 20 else ""))
    return {"findings": len(findings), "radiographs": len(group_of_image), "sources": sorted(sources),
            "content_sha256": m["content_sha256"]}


def binding_sha256(f: dict, authorization_sha256) -> str:
    """Binds one finding to its review record, reviewer, label, image, radiograph group, box, source and the reviewer-authorization
    version used to build the manifest."""
    v = f.get("verification") or {}
    return hashlib.sha256(canonical({"finding": {k: f.get(k) for k in BINDING_FIELDS},
                                     "verification": {k: v.get(k) for k in BINDING_VERIFICATION_FIELDS},
                                     "reviewer_authorization_sha256": authorization_sha256})).hexdigest()


def load_import_manifest(path, expected_sha256, reviewer_ids=None):
    """None (imports disabled) when path is None. Otherwise the validated manifest; refuses a missing file, a file whose SHA-256 is
    not the registered one, or any validation problem."""
    if path is None:
        if expected_sha256 is not None:
            raise ImportRefused("an expected manifest SHA-256 was given but no manifest path")
        return None
    p = Path(path)
    if not p.is_file():
        raise ImportRefused(f"import manifest {p} does not exist")
    if not _is_hex64(expected_sha256):
        raise ImportRefused("the registered SHA-256 of the import manifest is required (Amendment 02); refusing an unregistered manifest")
    got = _sha_file(p)
    if got != expected_sha256:
        raise ImportRefused(f"import manifest SHA-256 {got[:16]}... is not the registered {expected_sha256[:16]}...")
    m = json.loads(p.read_text(encoding="utf-8"))
    m["_summary"] = validate_manifest(m, reviewer_ids)
    m["_file_sha256"] = got
    return m


def protected_identities(split_rows: dict, pool_rows: list) -> dict:
    """Groups and image hashes no import may share: every project manifest row (train + validation = CV pool, calibration, test)
    and every annotation-pool row that is not 'unassigned' (twins of project radiographs, eval_locked)."""
    groups, shas = set(), set()
    for rows in split_rows.values():
        for r in rows:
            groups.add(r["radiograph_group"])
            shas.add(r["image_sha256"])
    for r in pool_rows:
        if r.get("split_lock") != IMPORTABLE_SPLIT_LOCK:
            groups.add(r["radiograph_group"])
            shas.add(r["image_sha256"])
    return {"groups": groups, "sha256": shas}


def check_independence(m: dict, protected: dict) -> dict:
    """Identity part of gate V6. Refuses on any shared radiograph group or image SHA-256."""
    hits = []
    for f in m["findings"]:
        if f["radiograph_group"] in protected["groups"]:
            hits.append({"sample_id": f["sample_id"], "rule": "radiograph_group"})
        if f["image_sha256"] in protected["sha256"]:
            hits.append({"sample_id": f["sample_id"], "rule": "image_sha256"})
    if hits:
        raise ImportRefused(f"{len(hits)} import(s) share a radiograph group or image with protected data: {hits[:10]}")
    return {"checked": len(m["findings"]), "hits": 0}


def gate_v6_for_manifest(m: dict, protected_images: list, data_root) -> dict:
    """Full gate V6 (cv5_accept.gate_v6: group, SHA-256 and near-duplicate) on the imported radiographs; needs the image files."""
    import cv5_accept as CA
    seen, imports = set(), []
    for f in m["findings"]:
        if f["image_sha256"] not in seen:
            seen.add(f["image_sha256"])
            imports.append({"id": f["sample_id"], "group": f["radiograph_group"], "sha256": f["image_sha256"],
                            "path": Path(data_root) / f["image_path"]})
    res = CA.gate_v6(imports, protected_images)
    if not res["pass"]:
        raise ImportRefused(f"gate V6: {len(res['hits'])} hit(s): {res['hits'][:10]}")
    return res


def import_rows(m: dict) -> list:
    """Imported findings as training rows (the fields DK.build_crops and the CV plans use)."""
    return [{"sample_id": f["sample_id"], "split": "train", "source_dataset": f"import:{f['source_dataset']}",
             "image_path": f["image_path"], "image_sha256": f["image_sha256"], "radiograph_group": f["radiograph_group"],
             "bbox_xywh": f["bbox_xywh"] if isinstance(f["bbox_xywh"], str) else json.dumps(f["bbox_xywh"]),
             "target_class": f["target_class"], "class_index": str(int(f["class_index"])), "project_image_id": f"import:{f['pool_id']}",
             "import_source_id": f["source_id"], "import_review_record_hash": f["verification"]["review_record_hash"]}
            for f in m["findings"]]


def augment_plans(plans: dict, m, fold_of: dict) -> dict:
    """Section 3.1 item 2. m None -> plans returned unchanged (same object). Otherwise a new dict: for every fold, fit = original fit
    rows + all imported rows; inner / heldout / heldout_secondary are the original lists, untouched. Refuses an import whose
    radiograph group is in the fold file (the CV5 population)."""
    if m is None:
        return plans
    rows = import_rows(m)
    clash = sorted({r["radiograph_group"] for r in rows} & set(fold_of))
    if clash:
        raise ImportRefused(f"imported radiograph groups are in the CV5 fold file: {clash[:10]}")
    out = {}
    for k, plan in plans.items():
        p = dict(plan)
        p["fit"] = list(plan["fit"]) + copy.deepcopy(rows)
        p["imports"] = {"findings": len(rows), "manifest_sha256": m.get("_file_sha256")}
        out[k] = p
    return out


def import_counts(m) -> dict:
    """Findings and unique radiographs per class in the manifest (0 when imports are disabled)."""
    out = {c: {"findings": 0, "radiographs": 0} for c in CLASSES}
    if m is None:
        return out
    imgs = {c: set() for c in CLASSES}
    for f in m["findings"]:
        out[f["target_class"]]["findings"] += 1
        imgs[f["target_class"]].add(f["image_sha256"])
    for c in CLASSES:
        out[c]["radiographs"] = len(imgs[c])
    return out


def base_counts_from_report(csv_path) -> dict:
    """Training-split counts of the ORIGINAL expert labels from reports/expanded_class_distribution.csv ('verified' rows, split
    'train'); clinician rows are excluded so imports are never counted twice."""
    import csv
    out = {c: {"findings": 0, "radiographs": 0} for c in CLASSES}
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["status"] == "verified" and r["split"] == "train" and r["class"] in out:
                out[r["class"]]["findings"] += int(r["findings"])
                out[r["class"]]["radiographs"] += int(r["unique_radiographs_with_class"])
    return out


def p2_status(base: dict, m) -> dict:
    """Consistency check of P2 with imports (the binding count is scripts/dataset/expansion_report.py). Met only if, for every
    targeted class, both findings and radiographs reach the target. With no manifest, imports add nothing."""
    imp = import_counts(m)
    res = {}
    for c, t in P2_TARGETS.items():
        f = base[c]["findings"] + imp[c]["findings"]
        r = base[c]["radiographs"] + imp[c]["radiographs"]
        res[c] = {"findings": f, "radiographs": r, "target": t, "gap_findings": max(0, t["findings"] - f),
                  "gap_radiographs": max(0, t["radiographs"] - r), "met": f >= t["findings"] and r >= t["radiographs"]}
    return {"classes": res, "met": all(v["met"] for v in res.values())}


# ------------------------------------------------------------------------------------------------------------- V6 record and image files
V6_FORMAT = "dentamind-cv5-import-v6-v1"


def verify_image_files(m: dict, root) -> dict:
    """Every imported image exists under root at its manifest path and has the manifest SHA-256 (no file is trusted by name)."""
    bad, seen = [], {}
    for f in m["findings"]:
        if f["image_path"] in seen:
            continue
        p = Path(root) / f["image_path"]
        seen[f["image_path"]] = ok = p.is_file() and _sha_file(p) == f["image_sha256"]
        if not ok:
            bad.append(f["image_path"])
    if bad:
        raise ImportRefused(f"{len(bad)} imported image file(s) missing or not byte-identical to the manifest: {bad[:10]}")
    return {"images_verified": len(seen)}


def make_v6_record(m: dict, v6_result: dict, protected_description: dict) -> dict:
    """The full gate-V6 result for one manifest, computed LOCALLY where the calibration / test / eval_locked images exist (the CV5
    notebook never reads calibration or test images). Only a passing result can be recorded."""
    if not v6_result.get("pass") or v6_result.get("hits"):
        raise ImportRefused("gate V6 did not pass: a failing result is not recorded as a V6 record")
    from datetime import datetime, timezone
    return {"format": V6_FORMAT, "created": datetime.now(timezone.utc).isoformat(), "manifest_sha256": m["_file_sha256"],
            "manifest_content_sha256": m["content_sha256"], "imported_images": v6_result["imports"],
            "protected": protected_description, "result": v6_result}


def load_v6_record(path, expected_sha256, manifest: dict) -> dict:
    """The registered V6 record for this manifest: file SHA-256 as registered, same manifest, passing, covering every imported image."""
    p = Path(path)
    if not p.is_file():
        raise ImportRefused(f"V6 record {p} does not exist")
    if not _is_hex64(expected_sha256) or _sha_file(p) != expected_sha256:
        raise ImportRefused("V6 record SHA-256 is not the registered one")
    r = json.loads(p.read_text(encoding="utf-8"))
    n_images = len({f["image_sha256"] for f in manifest["findings"]})
    if (r.get("format") != V6_FORMAT or r.get("manifest_sha256") != manifest.get("_file_sha256")
            or r.get("manifest_content_sha256") != manifest.get("content_sha256")):
        raise ImportRefused("V6 record does not belong to this import manifest")
    res = r.get("result") or {}
    if not res.get("pass") or res.get("hits") or r.get("imported_images") != n_images or res.get("imports") != n_images:
        raise ImportRefused("V6 record is not a passing check of every imported image")
    return {"protected": r.get("protected"), "imported_images": n_images, "rule": res.get("rule")}


# ------------------------------------------------------------------------------------------------------------- reviewer authorization
# A versioned, hash-registered artifact built LOCALLY from data/annotation/reviewers.csv (scripts/dataset/build_reviewer_authorization.py).
# It carries only internal reviewer ids, attestation / validity dates and status - no name, registration number or contact, so it can
# be attached to Kaggle. registry_sha256 binds it to the local registry it was derived from.

def _date(s):
    from datetime import date, datetime
    if s in (None, ""):
        return None
    if isinstance(s, str) and len(s) == 10:
        return date.fromisoformat(s)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()


def authorization_content_sha256(a: dict) -> str:
    return hashlib.sha256(canonical({k: a.get(k) for k in ("format", "version", "issued_at", "issued_by", "registry_sha256",
                                                           "previous_version_sha256", "reviewers")})).hexdigest()


def validate_authorization(a: dict) -> dict:
    probs = []
    if a.get("format") != AUTH_FORMAT:
        raise ImportRefused(f"not a {AUTH_FORMAT} artifact")
    if a.get("content_sha256") != authorization_content_sha256(a):
        raise ImportRefused("reviewer authorization was edited after it was issued (content_sha256 mismatch)")
    if not isinstance(a.get("version"), int) or a["version"] < 1:
        probs.append("version must be an integer >= 1")
    if a["version"] > 1 and not _is_hex64(a.get("previous_version_sha256")):
        probs.append("a version > 1 must reference the previous version's SHA-256")
    for k in ("issued_at", "issued_by"):
        if _blank(a.get(k)):
            probs.append(f"{k} missing")
    if not _is_hex64(a.get("registry_sha256")):
        probs.append("registry_sha256 missing")
    revs = a.get("reviewers")
    if not isinstance(revs, list) or not revs:
        raise ImportRefused("reviewer authorization lists no reviewer")
    ids = set()
    for r in revs:
        extra = set(r) - set(AUTH_REVIEWER_FIELDS)
        if extra:
            probs.append(f"reviewer {r.get('reviewer_id')!r}: fields {sorted(extra)} are not allowed (no personal data in this artifact)")
        if _blank(r.get("reviewer_id")) or r["reviewer_id"] in ids:
            probs.append(f"reviewer id {r.get('reviewer_id')!r} missing or duplicated")
        ids.add(r.get("reviewer_id"))
        if r.get("qualification_attested") is not True or _blank(r.get("attested_on")) or _blank(r.get("valid_from")):
            probs.append(f"reviewer {r.get('reviewer_id')!r}: qualification attestation / validity start missing")
        if r.get("status") not in ("active", "revoked"):
            probs.append(f"reviewer {r.get('reviewer_id')!r}: status must be active or revoked")
        if r.get("status") == "revoked" and _blank(r.get("revoked_on")):
            probs.append(f"reviewer {r.get('reviewer_id')!r}: revoked without revoked_on")
    if probs:
        raise ImportRefused("reviewer authorization invalid: " + "; ".join(probs))
    return {"version": a["version"], "reviewers": len(revs), "active": sum(r["status"] == "active" for r in revs)}


def load_reviewer_authorization(path, expected_sha256) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ImportRefused(f"reviewer authorization {p} does not exist")
    got = _sha_file(p)
    if not _is_hex64(expected_sha256) or got != expected_sha256:
        raise ImportRefused("reviewer authorization SHA-256 is not the registered one (missing, modified or stale version)")
    a = json.loads(p.read_text(encoding="utf-8"))
    a["_summary"] = validate_authorization(a)
    a["_file_sha256"] = got
    return a


def check_reviewer_bindings(m: dict, auth: dict) -> dict:
    """Every finding: manifest built with THIS authorization version; reviewer listed, qualification attested, status active (a
    revoked reviewer's labels are refused whatever the review date - see the open decision in the review package), review date
    inside the validity window; binding hash intact."""
    ra = m.get("reviewer_authorization") or {}
    if ra.get("sha256") != auth.get("_file_sha256") or ra.get("version") != auth.get("version"):
        raise ImportRefused("manifest was built with a different reviewer-authorization version than the registered one")
    by_id = {r["reviewer_id"]: r for r in auth["reviewers"]}
    probs = []
    for f in m["findings"]:
        v, tag = f["verification"], f["sample_id"]
        r = by_id.get(v["reviewer_id"])
        if r is None:
            probs.append(f"{tag}: reviewer {v['reviewer_id']!r} not in the authorization")
            continue
        if r["status"] != "active":
            probs.append(f"{tag}: reviewer {v['reviewer_id']!r} authorization is {r['status']}")
            continue
        d = _date(v["reviewed_at"])
        lo, hi = _date(r["valid_from"]), _date(r.get("valid_to"))
        if d is None or d < lo or (hi is not None and d > hi):
            probs.append(f"{tag}: review date {v['reviewed_at']} outside the reviewer's authorization window")
        if f.get("binding_sha256") != binding_sha256(f, auth["_file_sha256"]):
            probs.append(f"{tag}: binding hash mismatch")
    if probs:
        raise ImportRefused(f"{len(probs)} reviewer-authorization problem(s): " + "; ".join(probs[:10]))
    return {"authorization_version": auth["version"], "findings_checked": len(m["findings"]),
            "reviewers_used": len({f["verification"]["reviewer_id"] for f in m["findings"]})}


# ------------------------------------------------------------------------------------------------------------- notebook import cell
IMPORT_PARAM_KEYS = ("manifest_sha256", "v6_record_sha256", "reviewer_authorization_sha256", "input_dir")


def check_import_params(imports: dict) -> None:
    if set(imports) != set(IMPORT_PARAM_KEYS):
        raise ValueError(f"imports must give exactly {sorted(IMPORT_PARAM_KEYS)}")
    for k in IMPORT_PARAM_KEYS[:3]:
        if not _is_hex64(str(imports[k])):
            raise ValueError(f"imports[{k!r}] must be the registered SHA-256 (64 lowercase hex characters)")
    d = str(imports["input_dir"])
    if not d.startswith("/kaggle/input/") or ".." in d:
        raise ValueError("imports['input_dir'] must be a folder of an attached Kaggle input (/kaggle/input/...)")


def notebook_import_cell(imports: dict, crops_expr: str) -> str:
    """Source of the notebook cell that applies registered imports (shared by the candidate and BASE-P2 generators). Expects the
    notebook globals DK, SPLITS, POOL, DATA_ROOT, PLANS, FOLDS, FOLD_OF, IDX, X_ALL, Y_ALL, ART, CACHE, log. crops_expr builds
    (X, y, meta) for IMP_ROWS with the run's crop rule."""
    check_import_params(imports)
    return f"""# ---- 6b. registered training imports (protocol section 3.1, Amendment 02): fitting part of every fold only ----------------------
import cv5_imports as CIM
IMPORT_DIR = Path({imports["input_dir"]!r})
IMPORT_MANIFEST_SHA256 = {imports["manifest_sha256"]!r}
IMPORT_V6_RECORD_SHA256 = {imports["v6_record_sha256"]!r}
REVIEWER_AUTHORIZATION_SHA256 = {imports["reviewer_authorization_sha256"]!r}
IMPORTS = CIM.load_import_manifest(IMPORT_DIR / "import_manifest.json", IMPORT_MANIFEST_SHA256)   # registered hash, content, bindings
AUTH = CIM.load_reviewer_authorization(IMPORT_DIR / "reviewer_authorization.json", REVIEWER_AUTHORIZATION_SHA256)
IMPORT_CHECK = {{"manifest": IMPORTS["_summary"], "manifest_sha256": IMPORTS["_file_sha256"],
                "reviewer_authorization": CIM.check_reviewer_bindings(IMPORTS, AUTH),
                "v6_local_record": CIM.load_v6_record(IMPORT_DIR / "import_v6_record.json", IMPORT_V6_RECORD_SHA256, IMPORTS),
                "image_files": CIM.verify_image_files(IMPORTS, IMPORT_DIR)}}
_ids = {{s: DK.load_split(SPLITS, s) for s in ("train", "validation", "calibration", "test")}}   # identities only: no calibration / test image is read
IMPORT_CHECK["identity"] = CIM.check_independence(IMPORTS, CIM.protected_identities(_ids, []))
del _ids
_pool_imgs = {{}}
for r in POOL:
    _pool_imgs.setdefault(r["image_sha256"], {{"id": r["sample_id"], "group": r["radiograph_group"], "sha256": r["image_sha256"],
                                              "path": DATA_ROOT / r["image_path"]}})
IMPORT_CHECK["v6_cv_pool"] = CIM.gate_v6_for_manifest(IMPORTS, list(_pool_imgs.values()), IMPORT_DIR)
_heldout_before = {{k: [r["sample_id"] for r in PLANS[k]["inner"] + PLANS[k]["heldout"] + PLANS[k]["heldout_secondary"]] for k in FOLDS}}
PLANS = CIM.augment_plans(PLANS, IMPORTS, FOLD_OF)
assert all([r["sample_id"] for r in PLANS[k]["inner"] + PLANS[k]["heldout"] + PLANS[k]["heldout_secondary"]] == _heldout_before[k]
           for k in FOLDS), "imports changed an inner-validation or held-out assignment"
IMP_ROWS = CIM.import_rows(IMPORTS)
assert not set(IDX) & {{r["sample_id"] for r in IMP_ROWS}}, "imported sample ids collide with CV5 pool ids"
XI, YI, _ = {crops_expr}
IDX.update({{r["sample_id"]: len(X_ALL) + i for i, r in enumerate(IMP_ROWS)}})
X_ALL, Y_ALL = np.concatenate([X_ALL, XI]), np.concatenate([Y_ALL, YI])
(ART / "import_check.json").write_text(json.dumps(IMPORT_CHECK, indent=1, default=str))
log(f"imports: {{len(IMP_ROWS)}} findings / {{IMPORTS['_summary']['radiographs']}} radiographs added to the fitting part of every fold; "
    f"manifest {{IMPORTS['_file_sha256'][:16]}}; reviewer authorization v{{AUTH['version']}}; V6 identity + CV-pool near-duplicate passed")"""
