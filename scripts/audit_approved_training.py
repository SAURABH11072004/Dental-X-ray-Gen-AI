"""Dry-run verification of 'train on approved annotations' on the RUNNING API (nothing is trained).

Creates real analyses/reviews in the app database (remove with scripts/audit_cleanup.py --cutoff <UTC time of this run>):
  * a pool image (never labelled): confirm a candidate region, approve it with a DIFFERENT named person -> it must count as training data;
  * a validation/test-split image: reviewed and approved the same way -> it must be EXCLUDED from training data.
Then POST /api/training/start with use_approved_annotations=true and dry_run=true.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _auth  # noqa: E402

_auth.install()
ROOT = Path(__file__).resolve().parents[1]
B = "http://127.0.0.1:8000/api"
R = []


def call(m, p, b=None):
    r = urllib.request.Request(B + p, json.dumps(b).encode() if b is not None else None, {"content-type": "application/json"}, method=m)
    try:
        with urllib.request.urlopen(r, timeout=300) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def rec(tid, what, expected, actual, ok):
    R.append({"id": tid, "check": what, "expected": expected, "actual": str(actual)[:260], "result": "PASS" if ok else "FAIL"})
    print(f"{R[-1]['result']:5} {tid:8} {what[:78]:78} -> {str(actual)[:90]}")


def candidate_region(image_id):
    s, full = call("POST", "/analyze/full", {"image_id": image_id})
    reg = next((r for r in full["regions"] if (r.get("candidate_class") or {}).get("status") == "candidate"), None)
    return full, reg


def main():
    body = {"task": "classification", "architecture": "resnet18", "experiment_name": "approved_dry", "epochs": 1, "batch_size": 2, "learning_rate": 0.001, "image_size": 64,
            "device": "cpu", "use_approved_annotations": True, "dry_run": True}
    s, j = call("POST", "/training/start", body)
    rec("APPR-01", "dry run with no approved reviews", "400 prerequisites_unmet (no approved annotations)", f"{s} {j.get('error', {}).get('code')}", s == 400 and j["error"]["code"] == "prerequisites_unmet")
    # a pool image: the first scored pool candidate that is not in the test/val split
    pool_img, val_img, off = None, None, 0
    while (pool_img is None or val_img is None) and off < 4000:
        s, page = call("GET", f"/images?source=dataset&limit=1000&offset={off}")
        for i in page.get("items", []):
            if pool_img is None and i.get("annotation_status") == "unlabeled" and i.get("split") != "test":
                pool_img = i["id"]
            if val_img is None and i.get("split") == "val" and i.get("annotation_status") == "annotated":
                val_img = i["id"]
        off += 1000
    full, reg = candidate_region(pool_img)
    rec("APPR-02", f"real analysis of an unlabelled pool image {pool_img} yields a candidate region to review", "a region with a candidate class", bool(reg), bool(reg))
    s, rv = call("POST", "/reviews", {"image_id": pool_img, "region_id": reg["region_id"], "action": "confirm_candidate", "reviewer": "Audit Reviewer A"})
    rec("APPR-03", "review saved; usable_for_training for a pool image", "usable_for_training true", f"{s} usable={rv.get('usable_for_training')} split={rv.get('split')}", s == 200 and rv.get("usable_for_training") is True)
    s, ap = call("POST", "/reviews/approve", {"ids": [rv["id"]], "approver": "Audit Reviewer A"})
    rec("APPR-04", "approval by the same person is refused", "400", s, s == 400)
    s, ap = call("POST", "/reviews/approve", {"ids": [rv["id"]], "approver": "Audit Approver B"})
    rec("APPR-05", "approval by a second named person", "200 approved", f"{s} {[x['status'] for x in ap.get('items', [])]}", s == 200 and ap["items"][0]["status"] == "approved")
    # a held-out image
    fullv, regv = candidate_region(val_img)
    s, rvv = call("POST", "/reviews", {"image_id": val_img, "region_id": regv["region_id"], "action": "confirm_candidate", "reviewer": "Audit Reviewer A"})
    rec("APPR-06", f"review of a validation-split film {val_img}", "usable_for_training false", f"{s} usable={rvv.get('usable_for_training')} split={rvv.get('split')}", s == 200 and rvv.get("usable_for_training") is False)
    s, ap2 = call("POST", "/reviews/approve", {"ids": [rvv["id"]], "approver": "Audit Approver B"})
    s, ex = call("GET", "/reviews/export?format=json")
    ids = [r.get("image_id") for r in ex.get("records", [])]
    rec("APPR-07", "export contains the pool review and not the validation-split one", f"[{pool_img}] and excluded >= 1", f"records={ids} excluded={ex.get('n_approved_but_excluded')}", pool_img in ids and val_img not in ids and ex.get("n_approved_but_excluded", 0) >= 1)
    s, j = call("POST", "/training/start", body)
    rec("APPR-08", "dry run with one eligible approved review", "200, valid, nothing started", f"{s} {str(j)[:110]}", s == 200 and j.get("dry_run") is True)
    s, jobs = call("GET", "/training/jobs")
    rec("APPR-09", "no job was created by the dry run", "no queued/running job", [x["status"] for x in jobs][:5], not any(x["status"] in ("queued", "running") for x in jobs))
    summ = {k: sum(1 for r in R if r["result"] == k) for k in ("PASS", "FAIL")}
    (ROOT / "docs" / "audit_evidence" / "approved_training_dry_run.json").write_text(json.dumps({"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "summary": summ, "results": R}, indent=1), encoding="utf-8")
    print("SUMMARY", summ)


if __name__ == "__main__":
    main()
