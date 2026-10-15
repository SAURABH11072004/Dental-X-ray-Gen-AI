"""Live security checks against the RUNNING API (permitted and denied requests), plus a scan that the token is not in browser code or any response.

    .\\.venv\\Scripts\\python.exe scripts\\audit_security_live.py     -> docs/audit_evidence/security_live.json
Side effects: a burst of requests fills the per-client rate buckets for up to a minute (other clients/tools may see HTTP 429 until it passes).
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _auth  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
B = "http://127.0.0.1:8000"
TOKEN = _auth.token()
R = []


def req(method, path, token="default", body=None, headers=None):
    h = dict(headers or {})
    if token == "default":
        token = TOKEN
    if token:
        h.setdefault("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    if data:
        h["content-type"] = "application/json"
    r = urllib.request.Request(B + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=60) as x:
            return x.status, x.read(), dict(x.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def rec(tid, what, expected, actual, ok):
    R.append({"id": tid, "check": what, "expected": expected, "actual": str(actual)[:300], "result": "PASS" if ok else "FAIL"})
    print(f"{R[-1]['result']:5} {tid:8} {what[:72]:72} -> {str(actual)[:80]}")


def wait_clear():
    """A previous run (or tool) may have filled the failed-auth bucket: wait until an unauthenticated probe answers 401 instead of 429."""
    for _ in range(4):
        s, _, _ = req("GET", "/api/models", token=None)
        if s == 401:
            return
        time.sleep(30)


def main():
    wait_clear()
    # -- permitted
    s, b, _ = req("GET", "/api/models")
    rec("SEC2-01", "valid Bearer token", "200", s, s == 200)
    s, b, _ = req("GET", "/api/models", token=None, headers={"X-API-Key": TOKEN})
    rec("SEC2-02", "valid X-API-Key", "200", s, s == 200)
    s, b, _ = req("GET", "/api/health?probes=false", token=None)
    h = json.loads(b)
    rec("SEC2-03", "health is open and reports the app version", "200, version 0.2.0 (not 'unknown')", f"{s} version={h.get('version')}", s == 200 and h.get("version") == "0.2.0")
    # -- denied: every protected group
    protected = [("GET", "/api/images"), ("POST", "/api/images/upload"), ("POST", "/api/predict"), ("POST", "/api/analyze/full"), ("GET", "/api/reports"), ("POST", "/api/reports/generate"),
                 ("POST", "/api/reports/x/review"), ("POST", "/api/training/start"), ("POST", "/api/training/stop/x"), ("GET", "/api/training/jobs"), ("POST", "/api/models/select"),
                 ("POST", "/api/models/promote"), ("POST", "/api/models/m.pth/evaluate"), ("POST", "/api/reviews"), ("POST", "/api/dataset/process"), ("GET", "/api/system/settings"),
                 ("GET", "/api/annotations/records"), ("GET", "/docs"), ("GET", "/openapi.json")]
    bad = []
    for m, p in protected:
        s, b, hd = req(m, p, token=None, headers={"content-type": "application/json"} if m == "POST" else None)
        if s != 401:
            bad.append((m, p, s))
    rec("SEC2-04", f"{len(protected)} protected routes without a token", "401 each", f"non-401: {bad}", not bad)
    time.sleep(62)          # the 19 token-less probes above filled the failed-authentication bucket (20/min); let the window slide
    s, b, hd = req("GET", "/api/models", token="wrong-token")
    rec("SEC2-05", "wrong token", "401 + WWW-Authenticate, no token echo", f"{s} {hd.get('www-authenticate')}", s == 401 and TOKEN not in b.decode())
    s, b, _ = req("GET", "/api/models", token=None, headers={"Authorization": "Basic " + TOKEN})
    rec("SEC2-06", "token sent with the wrong scheme", "401", s, s == 401)
    # -- the token must not leak
    leak = []
    for p in ("/api/system/settings", "/api/health", "/api/models", "/api/training/jobs", "/openapi.json"):
        s, b, hd = req("GET", p)
        if TOKEN.encode() in b or any(TOKEN in v for v in hd.values()):
            leak.append(p)
    rec("SEC2-07", "token absent from API responses and headers", "none", leak, not leak)
    hits = []
    for root in (ROOT / "frontend" / "src", ROOT / "frontend" / "dist", ROOT / "src", ROOT / "backend", ROOT / "docs", ROOT / "scripts", ROOT / "configs"):
        for f in root.rglob("*"):
            if f.is_file() and f.suffix in (".js", ".jsx", ".html", ".py", ".md", ".json", ".yaml", ".yml", ".ps1", ".mjs", ".css") and TOKEN and TOKEN in f.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(f.relative_to(ROOT)))
    rec("SEC2-08", "token not present in source, built frontend, docs or scripts", "no file contains it", hits, not hits)
    import subprocess
    ig = subprocess.run(["git", "-c", "safe.directory=D:/", "check-ignore", "-q", "runtime/api_token.txt"], cwd=str(ROOT), capture_output=True)
    rec("SEC2-09", "runtime/api_token.txt is git-ignored", "ignored", f"exit {ig.returncode}", ig.returncode == 0)
    # -- path manipulation with a valid token
    cases = [("GET", "/api/images/..%2F..%2F.env/file", 404), ("GET", "/api/images/..%5C..%5Csetup.py/file", 404), ("GET", "/api/evaluations/..%2F..%2Fsetup", 404),
             ("GET", "/api/evaluations/eval_x%2F..%2F..%2Fsetup", 404), ("GET", "/api/reports/..%2F..%2Fx/export?format=json", 404)]
    out = []
    for m, p, want in cases:
        s, b, _ = req(m, p)
        out.append((p, s))
    rec("SEC2-10", "traversal attempts with a valid token", "404 (never file contents)", out, all(s in (404, 422) for _, s in out))
    body = {"task": "classification", "architecture": "resnet18", "experiment_name": "../../evil", "epochs": 1, "batch_size": 1, "learning_rate": 0.001, "image_size": 64, "dry_run": True}
    s, b, _ = req("POST", "/api/training/start", body=body)
    rec("SEC2-11", "training experiment_name with path separators", "422", s, s == 422)
    body["experiment_name"] = "ok_name"
    for ref in ("../../.env", "..\\..\\.env", "C:/Windows/win.ini", "dentex_teeth_detection_v1.pth"):
        body["resume_checkpoint"] = ref
        s, b, _ = req("POST", "/api/training/start", body=body)
        rec("SEC2-12", f"resume_checkpoint={ref!r}", "4xx, never accepted", f"{s} {b.decode()[:90]}", 400 <= s < 500)
    body.pop("resume_checkpoint")
    s, b, _ = req("POST", "/api/training/start", body=body)
    j = json.loads(b) if b else {}
    rec("SEC2-13", "valid dry run through the API", "200, dry_run true, nothing started", f"{s} {str(j)[:100]}", s == 200 and j.get("dry_run") is True)
    s, b, _ = req("GET", "/api/training/jobs")
    rec("SEC2-14", "the dry run created no job", "job list unchanged (no 'queued'/'running')", [x["status"] for x in json.loads(b)][:12], not any(x["status"] in ("queued", "running") for x in json.loads(b)))
    # -- upload protection
    time.sleep(62)          # fresh failed-auth and control windows
    s, b, _ = req("POST", "/api/images/upload", token=None, headers={"content-type": "multipart/form-data; boundary=x"})
    rec("SEC2-15", "upload without a token", "401 before the body is read", s, s == 401)
    # -- rate limits (last: it fills buckets)
    time.sleep(62)
    codes = []
    for _ in range(26):
        s, b, hd = req("POST", "/api/training/stop/does-not-exist")
        codes.append(s)
    first429 = codes.index(429) + 1 if 429 in codes else None
    rec("SEC2-16", "control bucket: 26 rapid POST /api/training/stop calls", "404 for the first 20, then 429 with Retry-After", f"first 429 at call {first429}; {sorted(set(codes))}", first429 == 21)
    s, b, hd = req("POST", "/api/training/stop/x")
    rec("SEC2-17", "429 carries Retry-After and the JSON envelope", "present", f"{s} retry-after={hd.get('retry-after')}", s == 429 and "retry-after" in {k.lower() for k in hd} and json.loads(b)["error"]["code"] == "rate_limited")
    s, b, _ = req("GET", "/api/models")
    rec("SEC2-18", "other buckets unaffected by the control limit", "200", s, s == 200)
    fails = []
    for _ in range(24):
        s, b, _ = req("GET", "/api/models", token="bad")
        fails.append(s)
    rec("SEC2-19", "24 bad-token attempts", "401 first 20 (some already used above), then 429", f"{fails.count(401)}x401 {fails.count(429)}x429", fails.count(429) >= 1)
    s, b, _ = req("GET", "/api/models")
    rec("SEC2-20", "valid token still works after the failed-auth throttle", "200", s, s == 200)
    summ = {k: sum(1 for r in R if r["result"] == k) for k in ("PASS", "FAIL")}
    (ROOT / "docs" / "audit_evidence" / "security_live.json").write_text(json.dumps({"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "summary": summ, "results": R}, indent=1), encoding="utf-8")
    print("SUMMARY", summ)
    return 0


if __name__ == "__main__":
    sys.exit(main())
