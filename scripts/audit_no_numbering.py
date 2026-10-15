"""Acceptance check: with the numbering checkpoint absent, the pipeline must report numbering as unavailable and assign NO tooth numbers.
Starts a temporary server (port 8051) whose checkpoint folder holds detection + segmentation + classification only (copies; the real folder is untouched)."""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import _auth
_auth.install()
py = str(ROOT / ".venv" / "Scripts" / "python.exe")
tmp = Path(tempfile.mkdtemp(prefix="dm_nonum_"))
for n in ("dentex_teeth_detection_v1", "dentex_teeth_segmentation_v1", "dentex_findings_classification_v1"):
    for ext in (".pth", ".json"):
        shutil.copy2(ROOT / "Data" / "checkpoints" / (n + ext), tmp / (n + ext))
env = {**os.environ, "AUTO_PROCESS_DATASET": "false", "MODEL_CHECKPOINT_DIR": str(tmp)}
log = open(tmp / "server.log", "w")
p = subprocess.Popen([py, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8051"], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
B = "http://127.0.0.1:8051/api"
out = {}
try:
    for _ in range(120):
        try:
            urllib.request.urlopen(B + "/health?probes=false", timeout=3); break
        except Exception:
            time.sleep(0.5)
    models = json.load(urllib.request.urlopen(B + "/models"))["items"]
    out["models_listed"] = sorted(m["task"] for m in models)
    req = urllib.request.Request(B + "/analyze/full", json.dumps({"image_id": "val_12"}).encode(), {"content-type": "application/json"})
    full = json.load(urllib.request.urlopen(req, timeout=600))
    steps = {s["step"]: (s["status"], s["message"][:110]) for s in full["steps"]}
    fdis = [r["fdi"] for r in full["regions"]]
    out.update(steps=steps, n_regions=len(full["regions"]), n_with_fdi=sum(f is not None for f in fdis), numbering_statuses=sorted({r["numbering_status"] for r in full["regions"]}),
               summary=full["summary"], numbering_model=full.get("numbering_model"))
    out["PASS"] = (steps.get("number", ("",))[0] in ("unavailable", "skipped", "failed") and out["n_with_fdi"] == 0 and out["n_regions"] > 0)
    # a report built from this analysis must not contain tooth numbers either
    rq = urllib.request.Request(B + "/reports/generate", json.dumps({"analysis_id": full["analysis_id"], "mode": "template"}).encode(), {"content-type": "application/json"})
    rep = json.load(urllib.request.urlopen(rq))["report"]
    out["report_findings_with_tooth_number"] = sum(1 for f in rep["findings"] if f.get("tooth_fdi") is not None)
    out["report_models"] = rep["model_versions"]
    out["PASS"] = out["PASS"] and out["report_findings_with_tooth_number"] == 0 and "numbering" not in rep["model_versions"]
finally:
    p.terminate()
    try:
        p.wait(10)
    except Exception:
        p.kill()
    log.close()
    shutil.rmtree(tmp, ignore_errors=True)
Path(ROOT / "docs" / "audit_evidence" / "no_numbering_check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(out, indent=1, ensure_ascii=False)[:1800])
sys.exit(0 if out.get("PASS") else 1)
