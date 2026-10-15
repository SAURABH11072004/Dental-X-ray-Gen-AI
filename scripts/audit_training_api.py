"""Real API-started training smoke tests on a SEPARATE server (port 8071) with a temporary checkpoint folder and database, CUDA hidden (CPU only).

    .\\.venv\\Scripts\\python.exe scripts\\audit_training_api.py        -> docs/audit_evidence/training_api.json
Tiny SMOKE runs only (8 training / 4 validation images, 1 epoch, resnet18, 64 px, no pretrained download). They are not models and are deleted with the temp folder.
The real Data\\checkpoints, the real database and the GPU are not touched.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8071
B = f"http://127.0.0.1:{PORT}/api"
TOKEN = "training-audit-token-" + os.urandom(6).hex()
R = []
H = {"Authorization": f"Bearer {TOKEN}", "content-type": "application/json"}


def call(method, path, body=None, token=True):
    h = dict(H) if token else {"content-type": "application/json"}
    r = urllib.request.Request(B + path, json.dumps(body).encode() if body is not None else None, h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw.decode(errors="ignore")[:200]}


def rec(tid, what, expected, actual, ok):
    R.append({"id": tid, "check": what, "expected": expected, "actual": str(actual)[:300], "result": "PASS" if ok else "FAIL"})
    print(f"{R[-1]['result']:5} {tid:8} {what[:74]:74} -> {str(actual)[:90]}")


def wait(job_id, secs=240):
    seen, t0 = [], time.time()
    while time.time() - t0 < secs:
        s, j = call("GET", f"/training/status/{job_id}")
        p = (j.get("progress") or {})
        key = (j["status"], p.get("epoch"))
        if not seen or seen[-1] != key:
            seen.append(key)
        if j["status"] not in ("queued", "running"):
            return j, seen
        time.sleep(0.5)
    return j, seen


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dm_trainapi_"))
    ck = tmp / "ckpt"
    env = {**os.environ, "AUTO_PROCESS_DATASET": "false", "MODEL_CHECKPOINT_DIR": str(ck), "DATABASE_URL": "sqlite:///" + (tmp / "t.sqlite3").as_posix(),
           "DENTAMIND_API_TOKEN": TOKEN, "CUDA_VISIBLE_DEVICES": "-1", "DENTAMIND_RATE_LIMIT": "off"}
    real_before = {p.name: sha(p) for p in (ROOT / "Data" / "checkpoints").glob("*.*")}
    runs_before = set(os.listdir(ROOT / "Data" / "runs")) if (ROOT / "Data" / "runs").is_dir() else set()
    log = open(tmp / "server.log", "w")
    p = subprocess.Popen([str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT)], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(B + "/health?probes=false", timeout=3)
                break
            except Exception:
                time.sleep(0.5)
        cfg = {"task": "classification", "architecture": "resnet18", "experiment_name": "api_smoke", "epochs": 1, "batch_size": 4, "learning_rate": 0.001, "image_size": 64,
               "device": "cpu", "pretrained": False, "max_train_images": 8, "max_val_images": 4}
        s, j = call("POST", "/training/start", {**cfg, "dry_run": True})
        rec("TAPI-01", "dry run", "200, valid, would write api_smoke_classification_v1.pth, no job", f"{s} {j.get('would_write_checkpoint')}", s == 200 and j.get("dry_run") and j.get("would_write_checkpoint") == "api_smoke_classification_v1.pth")
        s, jobs = call("GET", "/training/jobs")
        rec("TAPI-02", "dry run created nothing", "[] jobs, empty checkpoint folder", f"{len(jobs)} jobs, ckpt files={list(ck.glob('*')) if ck.exists() else []}", s == 200 and jobs == [] and not (ck.exists() and any(ck.iterdir())))
        s, j1 = call("POST", "/training/start", cfg)
        rec("TAPI-03", "real smoke training started through the API", "200, queued/running", f"{s} {j1.get('id')} {j1.get('status')}", s == 200 and j1.get("status") in ("queued", "running"))
        s, j2 = call("POST", "/training/start", {**cfg, "experiment_name": "second"})
        rec("TAPI-04", "second start while the first runs", "409 job_already_running", f"{s} {j2.get('error', {}).get('code')}", s == 409 and j2["error"]["code"] == "job_already_running")
        s, j2 = call("POST", "/training/start", {**cfg, "dry_run": True})
        rec("TAPI-05", "dry run while a job runs", "409 as well (the GPU/slot is taken)", s, s == 409)
        s, j = call("POST", f"/training/stop/{'job-doesnotexist'}")
        rec("TAPI-06", "stop an unknown job", "404", s, s == 404)
        done, seen = wait(j1["id"])
        rec("TAPI-07", "job finishes and reports state", "succeeded, checkpoint named, progress seen", f"{done['status']} ckpt={done.get('checkpoint')} states={seen}", done["status"] == "succeeded" and done.get("checkpoint") == "api_smoke_classification_v1.pth")
        v1 = ck / "api_smoke_classification_v1.pth"
        side = json.loads((ck / "api_smoke_classification_v1.json").read_text(encoding="utf-8")) if (ck / "api_smoke_classification_v1.json").is_file() else {}
        rec("TAPI-08", "checkpoint and sidecar written with matching sha256", "sidecar sha == file sha, config recorded", f"{v1.is_file()} {side.get('checkpoint_sha256')} vs {sha(v1)[:16] if v1.is_file() else None} epochs={(side.get('training_config') or {}).get('epochs')}",
            v1.is_file() and side.get("checkpoint_sha256") == sha(v1)[:16] and side.get("training_config", {}).get("max_train_images") == 8)
        sha_v1 = sha(v1)
        s, models = call("GET", "/models")
        rec("TAPI-09", "registry lists the new checkpoint as a verified dental model of the right task", "present, task classification", [(m["model_id"], m["task"], m["dental_specific"]) for m in models.get("items", [])], any(m["model_id"] == v1.name and m["dental_specific"] and m["task"] == "classification" for m in models.get("items", [])))
        s, exps = call("GET", "/experiments")
        items = exps.get("items", exps) if isinstance(exps, dict) else exps
        rec("TAPI-10", "an experiment row was written by the real run", "1 row", len(items), len(items) == 1)
        s, j3 = call("POST", "/training/start", cfg)
        done3, _ = wait(j3["id"])
        v2 = ck / "api_smoke_classification_v2.pth"
        rec("TAPI-11", "same experiment name again never overwrites the earlier checkpoint", "v1 byte-identical, v2 written", f"{done3['status']} v1_same={sha(v1) == sha_v1} v2={v2.is_file()}", done3["status"] == "succeeded" and sha(v1) == sha_v1 and v2.is_file())
        s, j4 = call("POST", "/training/start", {**cfg, "experiment_name": "cancelme", "epochs": 40, "max_train_images": 8})
        time.sleep(4)
        s2, _ = call("POST", f"/training/stop/{j4['id']}")
        done4, seen4 = wait(j4["id"], 120)
        rec("TAPI-12", "cancellation", "cancelled, no checkpoint named 'cancelme' written", f"stop={s2} status={done4['status']} files={[x.name for x in ck.glob('cancelme*')]}", done4["status"] == "cancelled" and not list(ck.glob("cancelme*")))
        s, j5 = call("POST", "/training/start", {**cfg, "experiment_name": "needs_reviews", "use_approved_annotations": True})
        rec("TAPI-13", "approved-annotation training with no approved reviews", "400 prerequisites_unmet with a clear hint", f"{s} {j5.get('error', {}).get('code')} {j5.get('error', {}).get('hint', '')[:80]}", s == 400 and j5["error"]["code"] == "prerequisites_unmet")
        s, j6 = call("POST", "/training/start", {**cfg, "task": "classification", "architecture": "fasterrcnn_resnet50_fpn"})
        rec("TAPI-14", "incompatible architecture for the task", "422", s, s == 422)
        s, j7 = call("POST", "/training/start", {**cfg, "resume_checkpoint": "dentex_teeth_detection_v1.pth"})
        rec("TAPI-15", "resume from a checkpoint that does not exist in this registry", "400", s, s == 400)
        s, j8 = call("POST", "/training/start", {**cfg, "resume_checkpoint": "api_smoke_classification_v1.pth", "task": "detection", "architecture": "fasterrcnn_resnet50_fpn"})
        rec("TAPI-16", "resume a classifier checkpoint into a detection job", "400 incompatible", f"{s} {str(j8.get('error', {}).get('hint', ''))[:90]}", s == 400)
        s, j9 = call("POST", "/training/start", cfg, token=False)
        rec("TAPI-17", "start without a token", "401", s, s == 401)
        s, jobs = call("GET", "/training/jobs")
        leak = json.dumps(jobs)
        rec("TAPI-18", "job list shows no absolute paths or traceback", "none", [k for k in ("D:\\\\", "Traceback", "site-packages") if k in leak], not any(k in leak for k in ("D:\\\\", "Traceback", "site-packages")))
        rec("TAPI-19", "statuses recorded for every job", "succeeded, succeeded, cancelled", [x["status"] for x in sorted(jobs, key=lambda x: x["created"])], [x["status"] for x in sorted(jobs, key=lambda x: x["created"])] == ["succeeded", "succeeded", "cancelled"])
    finally:
        p.terminate()
        try:
            p.wait(15)
        except Exception:
            p.kill()
        log.close()
    real_after = {q.name: sha(q) for q in (ROOT / "Data" / "checkpoints").glob("*.*")}
    runs_after = set(os.listdir(ROOT / "Data" / "runs")) if (ROOT / "Data" / "runs").is_dir() else set()
    rec("TAPI-20", "real Data\\checkpoints byte-identical and no new files", "unchanged", f"files {len(real_before)} -> {len(real_after)}; new Data/runs entries: {sorted(runs_after - runs_before)}", real_before == real_after)
    shutil.rmtree(tmp, ignore_errors=True)
    summ = {k: sum(1 for r in R if r["result"] == k) for k in ("PASS", "FAIL")}
    (ROOT / "docs" / "audit_evidence" / "training_api.json").write_text(json.dumps({"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "note": "SMOKE tests on a separate server with temp dirs; not models", "summary": summ, "results": R}, indent=1), encoding="utf-8")
    print("SUMMARY", summ)


if __name__ == "__main__":
    main()
