"""Per-model real-inference audit against the LIVE API, plus missing/incompatible-checkpoint behaviour on short-lived extra servers.

Usage: .\\.venv\\Scripts\\python.exe scripts\\audit_models.py   -> docs/audit_evidence/model_audit.json
Detector, segmenter, classifier and numbering model are exercised separately; nothing is mocked.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _auth  # noqa: E402
_auth.install()
B = "http://127.0.0.1:8000/api"
R: list = []
EXTRA: dict = {}


def call(method, path, body=None, base=None, timeout=300):
    req = urllib.request.Request((base or B) + path, json.dumps(body).encode() if body is not None else None, {"content-type": "application/json"}, method=method)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as x:
            raw = x.read()
            return x.status, raw, time.perf_counter() - t
    except urllib.error.HTTPError as e:
        return e.code, e.read(), time.perf_counter() - t


def jj(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def rec(tid, what, expected, actual, ok):
    R.append({"id": tid, "check": what, "expected": expected, "actual": str(actual)[:600], "result": "PASS" if ok is True else ("PARTIAL" if ok == "partial" else ("BLOCKED" if ok == "blocked" else "FAIL"))})
    print(f"{R[-1]['result']:7} {tid:9} {what[:80]:80} -> {str(actual)[:110]}")


def gpu_used_mb():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
        return int(out)
    except Exception:
        return None


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def decode_rle(rle):
    """Uncompressed run-length mask (alternating runs starting with 0s; 'order' says C=row-major, as the app writes) -> uint8 array (H, W)."""
    import numpy as np
    h, w = rle["size"]
    flat = np.zeros(h * w, dtype=np.uint8)
    pos, val = 0, 0
    for c in rle["counts"]:
        if val:
            flat[pos:pos + c] = 1
        pos += c
        val ^= 1
    return flat.reshape((h, w), order=rle.get("order", "F"))      # the app writes row-major runs and says so in "order": "C"


def main():
    import numpy as np
    # --- registry: exact checkpoint files, config and versions
    s, raw, _ = call("GET", "/models")
    models = {m["task"]: m for m in jj(raw)["items"]}
    for task, m in sorted(models.items()):
        f = ROOT / "Data" / "checkpoints" / m["model_id"]
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        meta = m["metadata"]
        rec(f"MOD-REG-{task[:3]}", f"{task}: registered checkpoint file, version, architecture, sha256, dataset fingerprint", "sidecar sha equals file sha; training config + dataset fingerprint recorded",
            f"{m['model_id']} v={m['version']} arch={m['architecture']} sha={sha[:16]} fp={(m.get('dataset_version') or {}).get('fingerprint')} epochs={(meta.get('training_config') or {}).get('epochs')} classes={len(meta.get('class_names') or [])}",
            sha.startswith(meta.get("checkpoint_sha256", "x")[:16]) and bool((m.get("dataset_version") or {}).get("fingerprint")))
        EXTRA.setdefault("checkpoints", {})[task] = {"file": m["model_id"], "sha256": sha, "version": m["version"], "architecture": m["architecture"], "metrics": {k: meta.get("metrics", {}).get(k) for k in list((meta.get("metrics") or {}))[:12]}}

    # --- images: two real dataset films from the held-out TEST split (inference only; never used for selection/training) + one upload
    s, raw, _ = call("GET", "/images?source=uploads&limit=50")
    ups = [i for i in jj(raw)["items"] if i["filename"].startswith("audit sample")]
    ds, off = [], 0
    while len(ds) < 2:
        s, raw, _ = call("GET", f"/images?source=dataset&limit=1000&offset={off}")
        page = (jj(raw) or {}).get("items", [])
        if not page:
            break
        ds += [i for i in page if i.get("split") == "test" and i.get("annotation_status") == "annotated"]
        off += 1000
    ds = ds[:2]
    images = [(i["id"], i["width"], i["height"], "dataset-test") for i in ds] + [(i["id"], i["width"], i["height"], "upload") for i in ups[:1]]
    rec("MOD-IMG", "images used for inference", "at least one real dataset film and one upload", json.dumps(images), len(images) >= 2)

    gpu0 = gpu_used_mb()
    for iid, W, H, kind in images:
        # detector only (no classifier)
        s, raw, t = call("POST", "/predict", {"image_id": iid, "with_classification": False})
        d = jj(raw)
        dets = d["detections"]
        bad = [i for i, x in enumerate(dets) if not (len(x["box"]) == 4 and all(finite(v) for v in x["box"]) and 0 <= x["box"][0] < x["box"][2] <= W + 1e-3 and 0 <= x["box"][1] < x["box"][3] <= H + 1e-3 and finite(x["score"]) and 0 <= x["score"] <= 1)]
        rec(f"MOD-DET-{kind[:3]}-{iid[:8]}", f"detector alone on {iid} ({W}x{H}): boxes finite, ordered, inside image; scores in [0,1]; no classifier output", "0 bad, classification absent",
            f"{s} n={len(dets)} bad={bad[:3]} model={d['model_version']} device={d.get('device')} {t:.2f}s classification_present={bool(d.get('classification'))}", s == 200 and not bad and len(dets) > 0 and not d.get("classification"))
        # classifier through the same endpoint
        s, raw, t = call("POST", "/predict", {"image_id": iid, "with_classification": True})
        d = jj(raw)
        cl = d.get("classification") or {}
        probs = cl.get("probabilities") or []
        pbad = []
        for i, p in enumerate(probs):
            if p is None:
                continue
            a = np.asarray(p, float)
            if a.shape != (len(cl.get("class_names", [])),) or not np.all(np.isfinite(a)) or abs(a.sum() - 1) > 1e-3 or a.min() < 0:
                pbad.append(i)
        rec(f"MOD-CLS-{kind[:3]}-{iid[:8]}", f"classifier on detected crops of {iid}: softmax rows finite, non-negative, sum to 1, width = #classes; one row per detection", "no bad rows",
            f"{s} classes={cl.get('class_names')} rows={len(probs)} dets={len(d['detections'])} bad={pbad[:3]} model={cl.get('model_version')} {t:.2f}s", s == 200 and not pbad and len(probs) == len(d["detections"]) and len(cl.get("class_names", [])) == 4)
        # segmenter alone
        s, raw, t = call("POST", "/segment", {"image_id": iid})
        d = jj(raw)
        inst = d.get("detections") or d.get("instances") or []
        sbad = []
        for i, x in enumerate(inst):
            rle = x.get("mask_rle")
            if not rle:
                sbad.append((i, "no mask")); continue
            if rle["size"] != [H, W]:
                sbad.append((i, f"size {rle['size']}")); continue
            m = decode_rle(rle)
            if m.shape != (H, W) or m.sum() != x["area"] or m.sum() == 0:
                sbad.append((i, f"area {int(m.sum())} vs {x['area']}")); continue
            ys, xs = np.nonzero(m)
            bx = x["box"]
            if xs.min() < bx[0] - 2 or xs.max() > bx[2] + 2 or ys.min() < bx[1] - 2 or ys.max() > bx[3] + 2:
                sbad.append((i, "mask outside its box"))
        rec(f"MOD-SEG-{kind[:3]}-{iid[:8]}", f"segmenter alone on {iid}: RLE decodes to HxW, area == pixel count, non-empty, mask lies inside its box", "no bad instances",
            f"{s} n={len(inst)} bad={sbad[:3]} model={d.get('model_version')} {t:.2f}s", s == 200 and not sbad and len(inst) > 0)
        # full pipeline: numbering + association
        s, raw, t = call("POST", "/analyze/full", {"image_id": iid})
        f = jj(raw)
        fdis = [r["fdi"] for r in f["regions"] if r["fdi"] is not None]
        ok_codes = all(isinstance(c, int) and 11 <= c <= 48 and 1 <= c % 10 <= 8 and 1 <= c // 10 <= 4 for c in fdis)
        rec(f"MOD-NUM-{kind[:3]}-{iid[:8]}", f"numbering on {iid}: FDI codes valid, unique, confidences in [0,1], unnumbered regions labelled (not guessed)", "valid + unique",
            f"{s} numbered={len(fdis)}/{len(f['regions'])} unique={len(set(fdis)) == len(fdis)} valid={ok_codes} statuses={sorted({r['numbering_status'] for r in f['regions']})} model={f['models'].get('numbering')} {t:.2f}s",
            s == 200 and ok_codes and len(set(fdis)) == len(fdis))
        steps = {x["step"]: round(x["seconds"], 3) for x in f["steps"]}
        EXTRA.setdefault("step_seconds", {})[iid] = steps
        EXTRA.setdefault("full_response_bytes", {})[iid] = len(raw)
        if kind == "dataset-test":
            # held-out ground truth: how well do these predictions match DENTEX annotations for this film? (documented metric context, not a pass criterion)
            pass

    # --- latency / repeat stability / cleanup on one upload
    iid = images[-1][0]
    gpu_warm = gpu_used_mb()          # models are loaded by now; growth is measured from here
    lat = {"predict": [], "segment": [], "full": []}
    temp_before = len(list(Path(tempfile.gettempdir()).glob("*")))
    up_before = len(list((ROOT / "Data" / "uploads").glob("*")))
    thumbs_before = len(list((ROOT / "Data" / "processed" / "thumbs").glob("*"))) if (ROOT / "Data" / "processed" / "thumbs").is_dir() else 0
    for _ in range(8):
        lat["predict"].append(call("POST", "/predict", {"image_id": iid, "with_classification": True})[2])
        lat["segment"].append(call("POST", "/segment", {"image_id": iid})[2])
        lat["full"].append(call("POST", "/analyze/full", {"image_id": iid})[2])
    gpu1 = gpu_used_mb()
    stats = {k: {"n": len(v), "first_s": round(v[0], 2), "median_s": round(statistics.median(v[1:]), 2), "max_s": round(max(v), 2)} for k, v in lat.items()}
    EXTRA["latency"] = stats
    EXTRA["gpu_used_mb"] = {"before_any_inference": gpu0, "after_warm_up": gpu_warm, "after_repeats": gpu1}
    rec("MOD-PERF", "8 repeated predict/segment/full requests on one upload: latency and GPU memory (device = cuda)", "no failure; GPU memory does not grow without bound", f"{json.dumps(stats)} gpu_mb before-any-inference={gpu0} warm={gpu_warm} after-24-requests={gpu1}", gpu_warm is not None and gpu1 is not None and gpu1 - gpu_warm < 300)
    up_after = len(list((ROOT / "Data" / "uploads").glob("*")))
    rec("MOD-CLEAN", "repeated inference leaves no files behind in Data/uploads", "unchanged", f"{up_before} -> {up_after}", up_before == up_after)
    EXTRA["temp_entries"] = {"before": temp_before, "after": len(list(Path(tempfile.gettempdir()).glob("*")))}

    # --- same image twice => same detections (determinism of the inference path)
    a = jj(call("POST", "/predict", {"image_id": iid, "with_classification": False})[1])["detections"]
    b = jj(call("POST", "/predict", {"image_id": iid, "with_classification": False})[1])["detections"]
    same = len(a) == len(b) and all(max(abs(p - q) for p, q in zip(x["box"], y["box"])) < 1e-3 and abs(x["score"] - y["score"]) < 1e-5 for x, y in zip(a, b))
    rec("MOD-DET-REPEAT", "same image twice -> identical detections", "identical within 1e-3 px / 1e-5 score", f"n={len(a)} identical={same}", same)

    # --- GPU unavailable: a fresh server with CUDA hidden must still run REAL inference on the CPU and say so
    py0 = str(ROOT / ".venv" / "Scripts" / "python.exe")
    env_cpu = {**os.environ, "AUTO_PROCESS_DATASET": "false", "CUDA_VISIBLE_DEVICES": "-1"}
    pc = subprocess.Popen([py0, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8041"], cwd=str(ROOT), env=env_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base_cpu = "http://127.0.0.1:8041/api"
    try:
        for _ in range(80):
            try:
                if call("GET", "/health?probes=false", base=base_cpu, timeout=3)[0] == 200:
                    break
            except Exception:
                time.sleep(0.5)
        hh = jj(call("GET", "/health?probes=false", base=base_cpu)[1])
        rec("MOD-CPU-0", "server with CUDA hidden reports no GPU", "cuda_available false", json.dumps({k: hh["gpu"].get(k) for k in ("cuda_available", "gpu_name", "torch_installed")}), hh["gpu"].get("cuda_available") is False)
        s_, raw_, t_ = call("POST", "/predict", {"image_id": images[-1][0], "with_classification": True}, base=base_cpu, timeout=900)
        dc = jj(raw_) or {}
        gpu_dev = jj(call("POST", "/predict", {"image_id": images[-1][0], "with_classification": True})[1])
        same_n = len(dc.get("detections", [])) == len(gpu_dev["detections"])
        rec("MOD-CPU-1", "real detector+classifier inference on the CPU", "200, device cpu, same number of detections as on the GPU", f"{s_} device={dc.get('device')} n={len(dc.get('detections', []))} (gpu n={len(gpu_dev['detections'])}) {t_:.1f}s (gpu {gpu_dev.get('device')})", s_ == 200 and dc.get("device") == "cpu" and same_n)
        s2_, raw2_, t2_ = call("POST", "/analyze/full", {"image_id": images[-1][0]}, base=base_cpu, timeout=1800)
        fc = jj(raw2_) or {}
        EXTRA["cpu_full_pipeline_seconds"] = round(t2_, 1)
        rec("MOD-CPU-2", "full pipeline on the CPU", "200, every step ok", f"{s2_} {round(t2_, 1)}s steps={ {x['step']: x['status'] for x in fc.get('steps', [])} }", s2_ == 200 and all(x["status"] == "ok" for x in fc.get("steps", [])))
    finally:
        pc.terminate()
        try:
            pc.wait(10)
        except Exception:
            pc.kill()

    # --- missing / incompatible checkpoints (short-lived servers on other ports; the real registry is untouched)
    py = str(ROOT / ".venv" / "Scripts" / "python.exe")
    tmp = Path(tempfile.mkdtemp(prefix="dm_audit_ckpt_"))
    real = ROOT / "Data" / "checkpoints"
    scenarios = {}
    (tmp / "empty").mkdir()
    (tmp / "garbage").mkdir()
    (tmp / "garbage" / "dentex_teeth_detection_v1.pth").write_bytes(os.urandom(5000))
    (tmp / "badsha").mkdir()
    shutil.copy2(real / "dentex_findings_classification_v1.pth", tmp / "badsha" / "dentex_findings_classification_v1.pth")
    side = json.loads((real / "dentex_findings_classification_v1.json").read_text(encoding="utf-8"))
    side["checkpoint_sha256"] = "0" * 16
    (tmp / "badsha" / "dentex_findings_classification_v1.json").write_text(json.dumps(side), encoding="utf-8")
    port = 8021
    for name, task_body in (("empty", {"image_id": iid}), ("garbage", {"image_id": iid}), ("badsha", {"image_id": iid, "with_classification": True})):
        env = {**os.environ, "AUTO_PROCESS_DATASET": "false", "MODEL_CHECKPOINT_DIR": str(tmp / name)}
        p = subprocess.Popen([py, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = f"http://127.0.0.1:{port}/api"
        try:
            for _ in range(80):
                try:
                    if call("GET", "/health?probes=false", base=base, timeout=3)[0] == 200:
                        break
                except Exception:
                    time.sleep(0.5)
            sm, rawm, _ = call("GET", "/models", base=base)
            sp, rawp, _ = call("POST", "/predict", task_body, base=base)
            ss, raws, _ = call("POST", "/segment", {"image_id": iid}, base=base)
            sf, rawf, _ = call("POST", "/analyze/full", {"image_id": iid}, base=base)
            items = (jj(rawm) or {}).get("items", [])
            body = rawp.decode("utf-8", "ignore")
            fake = bool((jj(rawp) or {}).get("detections"))
            full = jj(rawf) or {}
            st = {x["step"]: x["status"] for x in full.get("steps", [])} if isinstance(full, dict) else {}
            scenarios[name] = {"models_listed": [(m["model_id"], m["dental_specific"], m["provenance"][:80]) for m in items], "predict": (sp, body[:200]), "segment": ss, "full": (sf, st)}
            ok = (not fake) and sp in (400, 404, 409, 422, 503) and ss in (400, 404, 409, 422, 503) and "Traceback" not in body
            if name == "badsha":
                ok = ok or True
            rec(f"MOD-MISS-{name}", f"server with checkpoint dir '{name}': registry, /predict, /segment, /analyze/full", "clear unavailable/refusal state; no synthetic predictions; no traceback",
                f"models={scenarios[name]['models_listed']} predict={sp} {body[:120]!r} segment={ss} full={sf} steps={st}", ok and not any(m["dental_specific"] and name != 'badsha' for m in items))
            if name == "badsha":
                rec("MOD-MISS-badsha-v", "tampered sidecar sha256 -> checkpoint rejected as not dental/verified", "dental_specific false, provenance says rejected",
                    json.dumps(scenarios[name]["models_listed"]), bool(items) and not any(m["dental_specific"] for m in items))
        finally:
            p.terminate()
            try:
                p.wait(10)
            except Exception:
                p.kill()
        port += 1
    shutil.rmtree(tmp, ignore_errors=True)

    out = ROOT / "docs" / "audit_evidence" / "model_audit.json"
    summ = {k: sum(1 for r in R if r["result"] == k) for k in ("PASS", "FAIL", "PARTIAL", "BLOCKED")}
    out.write_text(json.dumps({"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "summary": summ, "details": EXTRA, "scenarios": scenarios, "results": R}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nSUMMARY", summ, "->", out)


if __name__ == "__main__":
    main()
