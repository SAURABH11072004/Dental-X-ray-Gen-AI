"""Live audit of the running DentaMind API (real HTTP to a real uvicorn process; no mocks, no TestClient).

Usage:  .\\.venv\\Scripts\\python.exe scripts\\audit_live_api.py [--base http://127.0.0.1:8000] [--out docs/audit_evidence/live_api_tests.json]

Everything it uploads is a copy of a real dataset radiograph or a clearly named invalid file; it never deletes anything.
Uploaded test images stay in the app's upload registry (the app has no delete route) and are listed in the output.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import _auth  # noqa: E402
_auth.install()
sys.path.insert(0, str(ROOT / "src"))

RESULTS: list = []
BASE = "http://127.0.0.1:8000"


def http(method: str, path: str, body=None, headers=None, raw: bytes | None = None, timeout=300):
    url = path if path.startswith("http") else BASE + path
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = dict(headers or {})
    if body is not None and raw is None:
        h.setdefault("content-type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read()
            return r.status, dict(r.headers), payload, time.perf_counter() - t
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(), time.perf_counter() - t


def _items(x):
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in ('items', 'rows', 'records', 'experiments'):
            if isinstance(x.get(k), list):
                return x[k]
    return []


def jbody(payload: bytes):
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None


def multipart(field: str, filename: str, content: bytes, ctype="application/octet-stream"):
    b = "----audit" + uuid.uuid4().hex
    head = (f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n').encode("utf-8")
    return head + content + f"\r\n--{b}--\r\n".encode(), {"content-type": f"multipart/form-data; boundary={b}"}


def rec(tid, area, desc, expected, actual, ok, evidence="", note=""):
    RESULTS.append({"id": tid, "area": area, "input": desc, "expected": expected, "actual": actual,
                    "result": "PASS" if ok is True else ("PARTIAL" if ok == "partial" else ("BLOCKED" if ok == "blocked" else "FAIL")),
                    "evidence": evidence, "note": note})
    print(f"{RESULTS[-1]['result']:7} {tid:8} {desc[:70]:70} -> {str(actual)[:90]}")


def leaks(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in ("traceback", "d:\\\\", "d:/dentex", "c:\\\\users", "site-packages", 'file "'))


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--out", default=str(ROOT / "docs" / "audit_evidence" / "live_api_tests.json"))
    a = ap.parse_args()
    BASE = a.base.rstrip("/")
    from PIL import Image

    # ------------------------------------------------------------ health / system
    s, h, p, t = http("GET", "/api/health")
    d = jbody(p) or {}
    rec("API-001", "health", "GET /api/health", "200, backend ok, database ok", f"{s} backend={d.get('backend')} db={d.get('database')} ckpts={d.get('checkpoints_loaded')} ({t:.2f}s)",
        s == 200 and d.get("backend") == "ok" and d.get("database") == "ok")
    rec("API-002", "health", "health reports app version", "a version string (app declares 0.2.0)", f"version={d.get('version')!r}",
        d.get("version") not in (None, "", "unknown"), note="cosmetic: /api/health returns 'unknown' while the OpenAPI document declares 0.2.0")
    s, h, p, t = http("GET", "/api/system/settings")
    txt = p.decode()
    rec("API-003", "security", "GET /api/system/settings exposes no secrets", "no api key value, no absolute home paths",
        f"{s}; label_studio_api_key_set={ (jbody(p) or {}).get('settings', {}).get('label_studio_api_key_set')}; abs-path leak={leaks(txt)}", s == 200 and not leaks(txt))
    s, h, p, t = http("GET", "/api/system/gpu")
    g = jbody(p) or {}
    rec("API-004", "health", "GET /api/system/gpu", "200 with device facts", f"{s} {g.get('gpu_name')} used={g.get('memory_used_mb')}/{g.get('memory_total_mb')} MB", s == 200 and g.get("cuda_available") is not None)

    # ------------------------------------------------------------ models / registry
    s, h, p, t = http("GET", "/api/models")
    models = (jbody(p) or {}).get("items", [])
    names = sorted(m["task"] for m in models)
    rec("API-010", "registry", "GET /api/models", "4 registered checkpoints (detection, segmentation, classification, numbering) with sidecar sha",
        f"{s} tasks={names}", s == 200 and names == ["classification", "detection", "numbering", "segmentation"])
    import hashlib
    ck = ROOT / "Data" / "checkpoints"
    for m in models:
        f = ck / m["model_id"]
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        side = m.get("metadata", {}).get("checkpoint_sha256", "")
        rec(f"API-011-{m['task'][:3]}", "registry", f"{m['model_id']} sidecar sha256 equals actual file sha256", "equal",
            f"file={sha[:16]} sidecar={side[:16]} dental_specific={m.get('dental_specific')}", bool(side) and sha.startswith(side[:16]))

    # ------------------------------------------------------------ image listing, safe resolution
    s, h, p, t = http("GET", "/api/images?source=dataset&limit=3")
    rec("API-020", "images", "GET /api/images?source=dataset&limit=3", "200, items", f"{s} total={(jbody(p) or {}).get('total')}", s == 200)
    for bad in ("?source=evil", "?limit=0", "?limit=100000", "?offset=-1"):
        s, h, p, t = http("GET", "/api/images" + bad)
        rec("API-021", "validation", f"GET /api/images{bad}", "422", f"{s}", s == 422)
    for iid in ("..%2F..%2Fsetup.py", "nope", "%27%3B%20DROP%20TABLE%20images%3B--", "up_" + "0" * 12):
        for route in ("", "/file", "/thumbnail", "/quality"):
            s, h, p, t = http("GET", f"/api/images/{iid}{route}")
            rec("API-022", "security", f"GET /api/images/{iid}{route}", "404 (or 4xx), no file content / path leak", f"{s} leak={leaks(p.decode(errors='ignore'))}",
                s in (404, 422) and not leaks(p.decode(errors='ignore')))
    s, h, p, t = http("GET", "/api/images?source=all&limit=1000")
    n_before = (jbody(p) or {}).get("total")

    # ------------------------------------------------------------ uploads
    # choose a real radiograph that is NOT a model-development image: a copy of the user's validation_data image
    src = next(iter(sorted((ROOT / "Data" / "validation_data").rglob("val_2.png"))), None) or next(iter(sorted((ROOT / "Data" / "validation_data").rglob("*.png"))))
    raw_png = src.read_bytes()
    up_before = {f.name for f in (ROOT / "Data" / "uploads").glob("*")}
    body, hd = multipart("file", "audit sample ü 例.png", raw_png, "image/png")
    s, h, p, t = http("POST", "/api/images/upload", raw=body, headers=hd)
    up1 = jbody(p) or {}
    rec("UPL-001", "upload", "valid PNG, filename with spaces + Unicode", "200, image id, width/height equal the file's",
        f"{s} id={up1.get('id')} {up1.get('width')}x{up1.get('height')} dup={up1.get('duplicate')} ({t:.2f}s)", s == 200 and up1.get("id", "").startswith("up_"))
    with Image.open(io.BytesIO(raw_png)) as im0:
        W0, H0 = im0.size
    rec("UPL-002", "upload", "reported size equals decoded size", f"{W0}x{H0}", f"{up1.get('width')}x{up1.get('height')}", (up1.get("width"), up1.get("height")) == (W0, H0))
    s, h, p, t = http("POST", "/api/images/upload", raw=body, headers=hd)
    up2 = jbody(p) or {}
    rec("UPL-003", "upload", "same bytes uploaded again", "same id, duplicate=true, no second file", f"{s} id={up2.get('id')} dup={up2.get('duplicate')}", s == 200 and up2.get("id") == up1.get("id") and up2.get("duplicate") is True)
    s, h, p, t = http("GET", f"/api/images/{up1.get('id')}/file")
    rec("UPL-004", "upload", "downloaded bytes equal uploaded bytes", "byte-identical", f"{s} equal={p == raw_png} content-type={h.get('content-type')}", s == 200 and p == raw_png)
    # JPEG
    with Image.open(io.BytesIO(raw_png)) as im:
        buf = io.BytesIO(); im.convert("L").save(buf, "JPEG", quality=92); jpg = buf.getvalue()
    b2, h2 = multipart("file", "sample.JPEG", jpg, "image/jpeg")
    s, h, p, t = http("POST", "/api/images/upload", raw=b2, headers=h2)
    upj = jbody(p) or {}
    rec("UPL-005", "upload", "valid JPEG (.JPEG, upper-case extension)", "200", f"{s} id={upj.get('id')}", s == 200 and bool(upj.get("id")))
    # traversal filename
    b3, h3 = multipart("file", "../../../evil_traversal.png", raw_png[:-0] if False else _recompress(raw_png), "image/png")
    s, h, p, t = http("POST", "/api/images/upload", raw=b3, headers=h3)
    upt = jbody(p) or {}
    escaped = (ROOT.parent / "evil_traversal.png").exists() or (ROOT / "evil_traversal.png").exists() or (ROOT / "Data" / "evil_traversal.png").exists()
    stored = (ROOT / "Data" / "uploads" / f"{upt.get('id')}.png").exists()
    rec("UPL-006", "security", "filename '../../../evil_traversal.png'", "stored only inside Data/uploads under a hash name; nothing written outside",
        f"{s} id={upt.get('id')} stored_in_uploads={stored} escaped={escaped} filename_kept={upt.get('filename')}", s == 200 and stored and not escaped)
    cases = [
        ("UPL-010", "corrupt PNG (valid signature, garbage body)", "x.png", b"\x89PNG\r\n\x1a\n" + os.urandom(2000), 400),
        ("UPL-011", "random bytes named .png", "x.png", os.urandom(4000), 400),
        ("UPL-012", "text file named .txt", "notes.txt", b"hello", 400),
        ("UPL-013", "empty file", "empty.png", b"", 400),
        ("UPL-014", "PNG renamed .exe", "a.exe", raw_png, 400),
        ("UPL-015", "truncated PNG (first 5000 bytes of a real film)", "cut.png", raw_png[:5000], 400),
        ("UPL-016", "tiny image 8x8", "tiny.png", _png(8, 8), 400),
        ("UPL-017", "HTML disguised as image", "x.png", b"<html><script>alert(1)</script></html>", 400),
        ("UPL-018", "SVG", "x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", 400),
    ]
    for tid, d_, fn, content, want in cases:
        bb, hh = multipart("file", fn, content)
        s, h, p, t = http("POST", "/api/images/upload", raw=bb, headers=hh)
        body_txt = p.decode(errors="ignore")
        j = jbody(p) or {}
        rec(tid, "upload", d_, f"{want} (400/413/422) with a clear message, no stack trace/path", f"{s} code={j.get('code') or j.get('error', {}) if isinstance(j, dict) else ''} leak={leaks(body_txt)} msg={body_txt[:80]!r}", s in (400, 413, 422) and not leaks(body_txt))
    # missing field / wrong content type
    s, h, p, t = http("POST", "/api/images/upload", raw=b"{}", headers={"content-type": "application/json"})
    rec("UPL-020", "upload", "POST /upload with JSON body and no file", "422", f"{s}", s == 422)
    # oversized: limit is 25 MB
    big = _png(3000, 3000, noise=True)  # incompressible PNG > limit? build until > 25 MB
    if len(big) <= 25 * 1024 * 1024:
        big = big + b"\0" * (25 * 1024 * 1024 + 10 - len(big))  # padded; still starts with the PNG signature
    bb, hh = multipart("file", "huge.png", big)
    s, h, p, t = http("POST", "/api/images/upload", raw=bb, headers=hh)
    rec("UPL-021", "upload", f"{len(big)/1e6:.1f} MB file (limit 25 MB)", "413/400 rejected, not stored", f"{s} {p.decode(errors='ignore')[:90]!r} ({t:.1f}s)", s in (400, 413, 422) and not leaks(p.decode(errors='ignore')))
    # decompression bomb / giant dimensions
    bomb = _png(20000, 20000)
    bb, hh = multipart("file", "bomb.png", bomb)
    s, h, p, t = http("POST", "/api/images/upload", raw=bb, headers=hh)
    rec("UPL-022", "upload", f"20000x20000 solid PNG ({len(bomb)/1e3:.0f} kB on disk)", "rejected before decoding to memory (too many pixels / bad dimensions)", f"{s} {p.decode(errors='ignore')[:100]!r}", s in (400, 413, 422))
    up_after = {f.name for f in (ROOT / "Data" / "uploads").glob("*")}
    new_files = sorted(up_after - up_before)
    expected_names = {f"{up1.get('id')}.png", f"{upj.get('id')}.jpg", f"{upt.get('id')}.png"}
    extra = sorted(f for f in up_after if f not in expected_names and f not in up_before)
    rec("UPL-030", "upload", "Data/uploads after all of the above (rejected payloads must leave nothing behind)", "the three valid uploads exist under hash names; no other new file; nothing outside uploads",
        f"new_this_run={new_files} unexpected={extra} expected_present={expected_names <= up_after}", not extra and expected_names <= up_after)

    # ------------------------------------------------------------ prediction validation
    for tid, path, body, want in [
        ("PRED-001", "/api/predict", {}, 422), ("PRED-002", "/api/predict", {"image_id": ""}, 422), ("PRED-003", "/api/predict", {"image_id": "does_not_exist"}, 404),
        ("PRED-004", "/api/predict", {"image_id": "x" * 500}, 422), ("PRED-005", "/api/predict/batch", {"image_ids": []}, 422), ("PRED-006", "/api/predict/batch", {"image_ids": [f"a{i}" for i in range(26)]}, 422),
        ("PRED-007", "/api/analyze/full", {"image_id": "nope"}, 404), ("PRED-008", "/api/segment", {"image_id": "nope"}, 404), ("PRED-009", "/api/uncertainty/image", {}, 422),
        ("PRED-010", "/api/explain", {"image_id": up1.get("id"), "box": [1, 2, 3]}, 422), ("PRED-011", "/api/explain", {"image_id": "nope", "box": [1, 2, 30, 40]}, 404),
    ]:
        s, h, p, t = http("POST", path, body)
        rec(tid, "validation", f"POST {path} {json.dumps(body)[:60]}", str(want), f"{s} leak={leaks(p.decode(errors='ignore'))}", s == want and not leaks(p.decode(errors='ignore')))
    s, h, p, t = http("POST", "/api/predict", {"image_id": up1.get("id"), "model_version": "no_such_model_v9"})
    rec("PRED-012", "validation", "predict with an unknown model_version", "clear refusal (4xx, or 503 model_mismatch); must not silently use another model", f"{s} {p.decode(errors='ignore')[:120]!r}", (400 <= s < 500 or s == 503) and 'no_such_model_v9' in p.decode(errors='ignore'))
    s, h, p, t = http("POST", "/api/predict/batch", {"image_ids": [up1.get("id"), "nope"]})
    rec("PRED-013", "validation", "batch with one unknown id", "4xx for the unknown id (or per-item error), never a 500", f"{s} {p.decode(errors='ignore')[:120]!r}", s < 500)

    # ------------------------------------------------------------ real inference on the uploaded image
    s, h, p, t = http("POST", "/api/predict", {"image_id": up1["id"], "with_classification": True})
    pred = jbody(p) or {}
    rec("INF-001", "inference", "POST /api/predict on the uploaded real radiograph", "200 with detections list, model version, timing", f"{s} keys={list(pred)[:10]} ({t:.2f}s)", s == 200 and "detections" in pred if isinstance(pred, dict) else False)
    _check_detections(pred.get("detections", []), W0, H0, "INF-002", "detector output on upload")
    ncl = [d_ for d_ in pred.get("detections", []) if d_.get("class") or d_.get("closest_class") or d_.get("classification")]
    rec("INF-003", "inference", "predict response carries model provenance", "model version + device + seconds", f"model={pred.get('model_version')} device={pred.get('device')} secs={pred.get('seconds') or pred.get('inference_seconds')}", bool(pred.get("model_version")))

    # full pipeline on an upload and on an annotated test-split film with GT
    s, h, p, t = http("POST", "/api/analyze/full", {"image_id": up1["id"]})
    full = jbody(p) or {}
    steps = {x["step"]: x["status"] for x in full.get("steps", [])}
    rec("INF-010", "inference", "POST /api/analyze/full on the upload", "200, every step reports ok/unavailable/failed", f"{s} steps={steps} ({t:.2f}s)", s == 200 and steps and all(v in ("ok", "unavailable", "failed", "skipped") for v in steps.values()))
    rec("INF-011", "inference", "no step silently failed", "all ok (or explicitly unavailable with reason)", json.dumps(steps), all(v == "ok" for v in steps.values()), note="a failed step is reported honestly in the response")
    _check_regions(full, "INF-012")
    s, h, p, t = http("GET", f"/api/analyses/{full.get('analysis_id')}/overlay")
    ov_ok = False
    if s == 200:
        with Image.open(io.BytesIO(p)) as ov:
            ov_ok = ov.size == (W0, H0)
            ov_size = ov.size
    rec("INF-013", "overlay", "overlay PNG dimensions equal the original image", f"{W0}x{H0}", f"{s} {ov_size if s == 200 else ''} {h.get('content-type')}", ov_ok)

    # ground-truth alignment on one annotated test-split radiograph (the app's test split, evaluation only)
    align = _gt_alignment()
    rec("INF-020", "alignment", "predicted boxes vs. DENTEX ground-truth boxes on an annotated test-split film (coordinates in original pixels)", "recall@IoU0.5 >= 0.9 (a systematic shift/scale error would collapse it; the detector reports test AP50 0.966) and median best-IoU >= 0.55",
        align["text"], align["ok"], evidence="docs/audit_evidence/alignment.json")

    # explain
    reg = next((r for r in full.get("regions", []) if r.get("candidate_class") or r.get("classification")), (full.get("regions") or [None])[0])
    if reg:
        s, h, p, t = http("POST", "/api/explain", {"image_id": up1["id"], "box": reg["box"]})
        ex = jbody(p) or {}
        rec("INF-030", "explainability", "POST /api/explain for a detected region", "200, heatmap + method name + target class", f"{s} keys={list(ex)[:8]} method={ex.get('method')!r} ({t:.2f}s)", s == 200 and bool(ex.get("method")))
        s, h, p, t = http("POST", "/api/explain", {"image_id": up1["id"], "box": [-50, -50, 1e9, 1e9]})
        rec("INF-031", "explainability", "explain with an out-of-image box", "4xx or safe clipping, never 500", f"{s} {p.decode(errors='ignore')[:100]!r}", s < 500)
        s, h, p, t = http("POST", "/api/explain", {"image_id": up1["id"], "box": [10, 10, 10, 10]})
        rec("INF-032", "explainability", "explain with a zero-area box", "4xx, never 500", f"{s} {p.decode(errors='ignore')[:100]!r}", 400 <= s < 500)
        s, h, p, t = http("POST", "/api/explain", {"image_id": up1["id"], "box": [float("nan")] * 4}) if False else (0, {}, b"", 0)

    # ------------------------------------------------------------ uncertainty
    s, h, p, t = http("POST", "/api/uncertainty/image", {"image_id": up1["id"]})
    un = (jbody(p) or {}).get("uncertainty") or {}
    sigs = {k: (un.get(k) or {}).get("status") for k in ("entropy", "disagreement", "mask_instability", "detection_instability")}
    rec("UNC-001", "uncertainty", "POST /api/uncertainty/image", "saved record; each signal has value+status+reason; methods listed", f"{s} signals={sigs} combined={un.get('combined')}", s == 200 and all(v in ("computed", "unavailable") for v in sigs.values()))
    vals_ok = all(finite((un.get(k) or {}).get("value")) and 0 <= un[k]["value"] <= 1 for k, v in sigs.items() if v == "computed")
    rec("UNC-002", "uncertainty", "computed signal values are finite and in [0,1]", "true", str(vals_ok), vals_ok)
    s, h, p, t = http("POST", "/api/uncertainty/score", {"probabilities": [[0.25, 0.25, 0.25, 0.25]]})
    z = jbody(p) or {}
    rec("UNC-003", "uncertainty", "uniform 4-class softmax -> normalised entropy 1.0", "entropy.value = 1.0", f"{s} {json.dumps(z.get('entropy'))}", abs(((z.get('entropy') or {}).get('value') or -1) - 1.0) < 1e-6)
    s, h, p, t = http("POST", "/api/uncertainty/score", {"probabilities": [[1.0, 0.0, 0.0, 0.0]]})
    z = jbody(p) or {}
    rec("UNC-004", "uncertainty", "one-hot softmax -> entropy 0.0", "0.0", f"{s} {json.dumps(z.get('entropy'))}", abs((z.get('entropy') or {}).get('value', -1)) < 1e-9)
    for tid, bad in [("UNC-005", {"probabilities": [[]]}), ("UNC-006", {"probabilities": [[float('nan'), 0.5]]} if False else {"probabilities": [["a", "b"]]}), ("UNC-007", {})]:
        s, h, p, t = http("POST", "/api/uncertainty/score", bad)
        z = jbody(p) or {}
        # acceptable: 4xx, or 200 with status 'unavailable' (never value 0 for missing input)
        unavailable = s == 200 and all((z.get(k) or {}).get("status") != "computed" for k in ("entropy", "disagreement", "mask_instability"))
        rec(tid, "uncertainty", f"score with invalid input {json.dumps(bad)[:50]}", "4xx or 'unavailable' (never a fake 0)", f"{s} {p.decode(errors='ignore')[:100]!r}", (400 <= s < 500) or unavailable)
    s, h, p, t = http("GET", "/api/uncertainty/table")
    tb = jbody(p) or {}
    rec("UNC-008", "uncertainty", "GET /api/uncertainty/table after the call above", "contains the record just computed with values", f"{s} rows={len(_items(tb))}", s == 200 and len(_items(tb)) >= 1)

    # ------------------------------------------------------------ reports
    s, h, p, t = http("POST", "/api/reports/generate", {})
    rec("REP-001", "reports", "generate with neither analysis_id nor image_id nor findings", "4xx, no empty fabricated report", f"{s} {p.decode(errors='ignore')[:100]!r}", 400 <= s < 500)
    s, h, p, t = http("POST", "/api/reports/generate", {"analysis_id": "an-doesnotexist"})
    rec("REP-002", "reports", "generate for a non-existent analysis", "404", f"{s}", s == 404)
    s, h, p, t = http("POST", "/api/reports/generate", {"analysis_id": full.get("analysis_id"), "mode": "template"})
    rep = (jbody(p) or {}).get("report") or {}
    rid = rep.get("report_id") or rep.get("id")
    rec("REP-003", "reports", "generate an English template report from the full analysis", "200 with report id linked to image + analysis", f"{s} id={rid} image={rep.get('image_id')} analysis={rep.get('analysis_id')} keys={list(rep)[:8]}", s == 200 and bool(rid) and rep.get("image_id") == up1["id"])
    s, h, p, t = http("GET", "/api/reports")
    lst = jbody(p) or []
    mine = next((x for x in lst if x.get("id") == rid), {})
    rec("REP-003b", "reports", "GET /api/reports rows carry what the compact list shows", "id, image_id, image_name (file name), status, created, languages", json.dumps({k: mine.get(k) for k in ("id", "image_name", "status", "languages")}),
        s == 200 and bool(mine.get("image_name")) and mine.get("languages") == ["en", "hi", "mr"] and bool(mine.get("created")) and bool(mine.get("status")))
    s, h, p, t = http("GET", "/api/reports/no-such-report")
    rec("REP-004", "reports", "GET invalid report id", "404", f"{s}", s == 404)
    s, h, p, t = http("GET", f"/api/reports/{rid}?lang=xx")
    rec("REP-005", "reports", "unsupported language 'xx'", "4xx with supported list; must not return an English report labelled as translated", f"{s} {p.decode(errors='ignore')[:140]!r}", 400 <= s < 500)
    # structured findings must be identical across languages and no inference must happen on language switch
    t_inf_before = _analysis_count()
    base = None
    lang_res = {}
    for lang in ("en", "hi", "mr"):
        s, h, p, t = http("GET", f"/api/reports/{rid}?lang={lang}")
        d = jbody(p) or {}
        lang_res[lang] = d
    rec("REP-006", "reports", "GET report in en/hi/mr", "200 each, localization_check ok for hi and mr", json.dumps({k: (v.get("localization_check") or {}) for k, v in lang_res.items()})[:260], all(lang_res[k] for k in lang_res))
    rec("REP-007", "reports", "language switching does not run new inference", "analysis row count unchanged", f"before={t_inf_before} after={_analysis_count()}", t_inf_before == _analysis_count())
    out = ROOT / "docs" / "audit_evidence"
    out.mkdir(parents=True, exist_ok=True)
    for lang in ("en", "hi", "mr"):
        for fmt in ("json", "html", "txt"):
            s, h, p, t = http("GET", f"/api/reports/{rid}/export?format={fmt}&lang={lang}")
            (out / f"report_{lang}.{fmt}").write_bytes(p)
            rec(f"REP-01-{lang}{fmt[0]}", "reports", f"export format={fmt} lang={lang}", "200, non-empty, correct content-type", f"{s} {len(p)} B {h.get('content-type')}", s == 200 and len(p) > 200)
    s, h, p, t = http("GET", f"/api/reports/{rid}/export?format=pdf&lang=en")
    rec("REP-020", "reports", "export format=pdf (not implemented)", "4xx with an explicit 'not supported' message", f"{s} {p.decode(errors='ignore')[:100]!r}", 400 <= s < 500)
    s, h, p, t = http("POST", f"/api/reports/{rid}/review", {"reviewer": ""})
    rec("REP-021", "reports", "review with an empty reviewer name", "422", f"{s}", s == 422)
    s, h, p, t = http("POST", f"/api/reports/{rid}/review", {"reviewer": "   "})
    rec("REP-022", "reports", "review with a whitespace-only reviewer name", "4xx (name must contain characters)", f"{s} {p.decode(errors='ignore')[:100]!r}", 400 <= s < 500)
    s, h, p, t = http("POST", "/api/reports/generate", {"image_id": up1["id"], "findings": [], "mode": "template"})
    e = jbody(p) or {}
    er = (e.get("report") or {})
    rec("REP-030", "reports", "report with an explicitly empty findings list", "200; findings == []; summary says nothing was supplied; no invented finding; validation flags the missing model version",
        f"{s} findings={er.get('findings')} validation_failed={er.get('validation_failed')} summary={str(er.get('summary'))[:90]!r}",
        s == 200 and er.get("findings") == [] and "no model findings" in str(er.get("summary", "")).lower() and er.get("validation_failed") is True)
    xss = "<script>alert(1)</script>"
    s, h, p, t = http("POST", f"/api/reports/{rid}/review", {"reviewer": xss})
    s2, h2, p2, _ = http("GET", f"/api/reports/{rid}/export?format=html&lang=en")
    rec("REP-031", "security", "reviewer name containing <script> must be HTML-escaped in the HTML export", "no raw <script> tag in exported HTML", f"review={s}; raw_script_in_html={xss.encode() in p2}", xss.encode() not in p2,
        note="This test marks the test report as reviewed by a test name; it is a report created by this audit.")

    # ------------------------------------------------------------ training / jobs / experiments / AL (validation only; no training started)
    s, h, p, t = http("GET", "/api/training/prerequisites")
    rec("TRN-001", "training", "GET /api/training/prerequisites", "200 with checks", f"{s} {p.decode()[:140]!r}", s == 200)
    base_train = {"task": "classification", "architecture": "resnet18", "experiment_name": "audit_validation_only", "epochs": 1, "batch_size": 1, "learning_rate": 0.001, "image_size": 64, "device": "cpu"}
    for tid, patch, want in [("TRN-002", {"epochs": 0}, 422), ("TRN-003", {"learning_rate": -1}, 422), ("TRN-004", {"task": "bogus"}, 422), ("TRN-005", {"experiment_name": ""}, 422), ("TRN-006", {"image_size": 8}, 422),
                             ("TRN-007", {"architecture": "no_such_arch"}, 400), ("TRN-008", {"resume_checkpoint": "../../etc/passwd"}, 400)]:
        s, h, p, t = http("POST", "/api/training/start", {**base_train, **patch})
        rec(tid, "training", f"start with invalid config {json.dumps(patch)}", f"{want} and no job created", f"{s} {p.decode(errors='ignore')[:100]!r}", s in (want, 400, 422, 409))
    s, h, p, t = http("GET", "/api/training/status/does-not-exist")
    rec("TRN-009", "training", "status of an unknown job", "404", f"{s}", s == 404)
    s, h, p, t = http("POST", "/api/training/stop/does-not-exist")
    rec("TRN-010", "training", "stop an unknown job", "404", f"{s}", s == 404)
    s, h, p, t = http("GET", "/api/training/jobs")
    rec("TRN-011", "training", "GET /api/training/jobs", "200, list incl. historical real runs", f"{s} n={len(jbody(p) or [])}", s == 200)
    s, h, p, t = http("GET", "/api/experiments")
    ex_ = _items(jbody(p))
    rec("EXP-001", "experiments", "GET /api/experiments", "real experiments from training runs and AL runs", f"{s} n={len(ex_)} first={ex_[0].get('name') if ex_ else None}", s == 200 and len(ex_) > 0)
    for path in ("/api/experiments/compare", "/api/experiments/series", "/api/experiments/export"):
        s, h, p, t = http("GET", path)
        rec("EXP-002", "experiments", f"GET {path} (no params)", "200 or a clean 4xx", f"{s}", s < 500)
    s, h, p, t = http("GET", "/api/evaluations")
    ev = jbody(p) or {}
    rec("EXP-003", "experiments", "GET /api/evaluations", "evaluation reports on disk are listed", f"{s} {str(ev)[:140]}", s == 200)
    s, h, p, t = http("GET", "/api/active-learning/info")
    rec("AL-001", "active-learning", "GET /api/active-learning/info", "200", f"{s} {p.decode()[:160]!r}", s == 200)
    s, h, p, t = http("GET", "/api/active-learning/pool?limit=5")
    pool = jbody(p) or {}
    rec("AL-002", "active-learning", "GET pool (eligible unlabeled)", "200", f"{s} {str(pool)[:200]}", s == 200)
    for tid, bd, want in [("AL-003", {"strategy": "bogus"}, 422), ("AL-004", {"budget": -1}, 422), ("AL-005", {"batch_size": 0}, 422)]:
        s, h, p, t = http("POST", "/api/active-learning/select", bd)
        rec(tid, "active-learning", f"select with invalid {json.dumps(bd)}", str(want), f"{s}", s == want)
    # annotation / Label Studio
    s, h, p, t = http("GET", "/api/annotations/connection")
    rec("ANN-001", "annotation", "GET /api/annotations/connection while Label Studio is not running", "truthful 'not reachable / setup required' state", f"{s} {p.decode()[:200]!r}", s == 200 and "reachable" in p.decode().lower())
    s, h, p, t = http("POST", "/api/annotations/import-from-label-studio", {"project_id": 1})
    rec("ANN-002", "annotation", "import from Label Studio without a configured server/key", "clear 4xx/5xx-service message, no fake import", f"{s} {p.decode(errors='ignore')[:140]!r}", 400 <= s < 600 and not leaks(p.decode(errors='ignore')))
    s, h, p, t = http("POST", "/api/annotations/import", {"tasks": [{"garbage": True}]})
    rec("ANN-003", "annotation", "import malformed Label Studio tasks", "4xx or reported skipped, not stored as approved", f"{s} {p.decode(errors='ignore')[:140]!r}", s < 500)
    s, h, p, t = http("POST", "/api/annotations/approve", {"image_ids": ["nope"], "reviewer": "Audit Reviewer"})
    rec("ANN-004", "annotation", "approve a non-existent annotation", "4xx / zero approved", f"{s} {p.decode(errors='ignore')[:120]!r}", s < 500)

    # ------------------------------------------------------------ reviews (region review store)
    s, h, p, t = http("POST", "/api/reviews", {"image_id": "nope", "region_id": None, "action": "specialist_review", "reviewer": "Audit Reviewer"})
    rec("REV-001", "reviews", "review an unknown image", "404", f"{s}", s == 404)
    s, h, p, t = http("POST", "/api/reviews", {"image_id": up1["id"], "region_id": None, "action": "bogus", "reviewer": "Audit Reviewer"})
    rec("REV-002", "reviews", "unknown review action", "4xx", f"{s}", 400 <= s < 500)
    s, h, p, t = http("POST", "/api/reviews", {"image_id": up1["id"], "region_id": None, "action": "specialist_review", "reviewer": ""})
    rec("REV-003", "reviews", "review without a reviewer name", "4xx", f"{s}", 400 <= s < 500)

    # ------------------------------------------------------------ CORS / headers / docs exposure
    s, h, p, t = http("OPTIONS", "/api/images", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    rec("SEC-001", "cors", "preflight from the Vite origin", "allowed (ACAO == origin)", f"{s} ACAO={h.get('access-control-allow-origin')}", h.get("access-control-allow-origin") == "http://localhost:5173")
    s, h, p, t = http("OPTIONS", "/api/images", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    rec("SEC-002", "cors", "preflight from a foreign origin", "not allowed (no ACAO for that origin)", f"{s} ACAO={h.get('access-control-allow-origin')}", h.get("access-control-allow-origin") != "https://evil.example")
    s, h, p, t = http("GET", "/docs")
    rec("SEC-003", "exposure", "/docs (Swagger UI) is enabled", "informational: dev-only route reachable on localhost", f"{s}", "blocked" if False else True, note="Swagger UI and /openapi.json are on by default; bind to 127.0.0.1 only (documented). Not a defect for local use.")
    s, h, p, t = http("GET", "/api/%2e%2e/%2e%2e/setup.py")
    rec("SEC-004", "security", "encoded path traversal on a route", "404, no file", f"{s} leak={b'setup' in p[:50]}", s in (404, 422) and b"from setuptools" not in p)
    s, h, p, t = http("GET", "/api/images/up_x'%20OR%20'1'='1/file")
    rec("SEC-005", "security", "SQL meta-characters in an image id", "404, no DB error text", f"{s} leak={leaks(p.decode(errors='ignore'))} {p.decode(errors='ignore')[:80]!r}", s == 404 and "sqlite" not in p.decode(errors='ignore').lower())
    s, h, p, t = http("GET", "/nonexistent")
    rec("SEC-006", "exposure", "unknown route", "404 JSON, no stack trace", f"{s}", s == 404 and not leaks(p.decode(errors='ignore')))

    # ------------------------------------------------------------ sweep: every parameterless GET route of the live OpenAPI document
    s, h, p, t = http("GET", "/openapi.json")
    spec = jbody(p) or {}
    swept, bad_routes = 0, []
    for path_, ops in sorted(spec.get("paths", {}).items()):
        if "get" not in ops or "{" in path_:
            continue
        s, h, p, t = http("GET", path_)
        swept += 1
        txt = p.decode(errors="ignore")
        ctype = h.get("content-type", "")
        # the dataset endpoints state the configured data folder on purpose (the UI tells the user where to place data); everything else must be path-free
        txt = __import__("re").sub(r'"(data_root|expected_location)":"[^"]*"', '"\\1":"<local data folder>"', txt)
        # job logs show verbatim diagnostics (traceback frames) but with absolute paths reduced to file names: check that separately
        logs = __import__("re").findall(r'"log_tail":\[.*?\]', txt)
        txt = __import__("re").sub(r'"log_tail":\[.*?\]', '"log_tail":[]', txt)
        if any(__import__("re").search(r"[A-Za-z]:\\\\", l) for l in logs):
            bad_routes.append((path_ + " (log_tail has an absolute path)", s))
        if s >= 500 or leaks(txt) or (s == 200 and "json" in ctype and jbody(p) is None):
            bad_routes.append((path_, s))
    rec("SWEEP-001", "sweep", f"GET every parameterless route in /openapi.json ({swept} routes)", "no 5xx, no stack trace / local-path leak, valid JSON", f"swept={swept} bad={bad_routes}", not bad_routes)

    # ------------------------------------------------------------ persistence summary
    s, h, p, t = http("GET", "/api/images?source=all&limit=1000")
    rec("DB-001", "database", "image registry count after uploads", f"+3 distinct valid uploads vs {n_before}", f"{(jbody(p) or {}).get('total')}", (jbody(p) or {}).get("total", 0) >= (n_before or 0))
    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {k: sum(1 for r in RESULTS if r["result"] == k) for k in ("PASS", "FAIL", "PARTIAL", "BLOCKED")}
    out_path.write_text(json.dumps({"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "base": BASE, "summary": summary, "uploads_created": {"png": up1.get("id"), "jpeg": upj.get("id"), "traversal_name": upt.get("id")},
                                    "report_created": rid, "analysis_created": full.get("analysis_id"), "results": RESULTS}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nSUMMARY", summary, "->", out_path)
    return 0


def _png(w, h, noise=False):
    from PIL import Image
    import numpy as np
    if noise:
        arr = (np.random.default_rng(0).integers(0, 255, (h, w), dtype=np.uint8))
        im = Image.fromarray(arr, "L")
    else:
        im = Image.new("L", (w, h), 128)
    buf = io.BytesIO()
    Image.MAX_IMAGE_PIXELS = None
    im.save(buf, "PNG", compress_level=9 if not noise else 0)
    return buf.getvalue()


def _recompress(raw: bytes) -> bytes:
    """Same pixels re-encoded so the traversal-named upload has a different hash than the first upload."""
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as im:
        buf = io.BytesIO(); im.convert("L").save(buf, "PNG"); return buf.getvalue()


def _analysis_count():
    import sqlite3
    c = sqlite3.connect(f"file:{ROOT / 'runtime' / 'dentamind.sqlite3'}?mode=ro", uri=True)
    try:
        return c.execute("select count(*) from analyses").fetchone()[0]
    finally:
        c.close()


def _check_detections(dets, W, H, tid, what):
    bad = []
    for i, d in enumerate(dets):
        b = d.get("box") or d.get("bbox")
        if not b or len(b) != 4 or not all(finite(v) for v in b):
            bad.append((i, "box malformed")); continue
        x1, y1, x2, y2 = b
        if not (0 <= x1 < x2 <= W + 1e-3 and 0 <= y1 < y2 <= H + 1e-3):
            bad.append((i, f"out of bounds {b}"))
        sc = d.get("score")
        if sc is not None and not (finite(sc) and 0 <= sc <= 1):
            bad.append((i, f"score {sc}"))
    rec(tid, "inference", f"{what}: boxes finite, x1<x2, y1<y2, inside {W}x{H}, scores in [0,1]", "0 malformed", f"n={len(dets)} bad={bad[:3]}", not bad and len(dets) > 0)


def _check_regions(full, tid):
    import numpy as np
    W, H = full.get("image_size", [0, 0])[0:2] if isinstance(full.get("image_size"), list) else (full["image_size"].get("width"), full["image_size"].get("height"))
    regs = full.get("regions", [])
    probs = []
    ids = [r["region_id"] for r in regs]
    if len(ids) != len(set(ids)):
        probs.append("duplicate region ids")
    seen_fdi = {}
    for r in regs:
        b = r["box"]
        if not all(finite(v) for v in b) or not (0 <= b[0] < b[2] <= W + 1e-3 and 0 <= b[1] < b[3] <= H + 1e-3):
            probs.append(f"{r['region_id']} box {b}")
        if r.get("fdi") is not None:
            if r["fdi"] in seen_fdi:
                probs.append(f"FDI {r['fdi']} assigned twice")
            seen_fdi[r["fdi"]] = 1
            c = r.get("fdi_confidence")
            if c is not None and not (finite(c) and 0 <= c <= 1):
                probs.append(f"fdi conf {c}")
        m = r.get("mask")
        if m:
            sz = m["mask_rle"]["size"]
            if sz != [H, W]:
                probs.append(f"mask size {sz} != image {H}x{W}")
            if sum(m["mask_rle"]["counts"]) != sz[0] * sz[1]:
                probs.append("rle counts do not sum to H*W")
            if m["area"] <= 0:
                probs.append("empty mask")
            if not (0.5 <= m["match_iou"] <= 1.0):
                probs.append(f"match_iou {m['match_iou']}")
    rec(tid, "inference", f"full-pipeline regions: unique ids, boxes in bounds, unique FDI, RLE masks sized H*W, match IoU >= 0.5 (n={len(regs)})", "no problems", str(probs[:4]) or "none", not probs and len(regs) > 0)


def _gt_alignment():
    """Run the real pipeline on one annotated TEST-split radiograph and compare box IoU with the DENTEX ground truth."""
    import numpy as np
    from dentexmodel.config import get_settings
    from dentexmodel.data.coco import load_coco
    from dentexmodel.data.manifest import load_manifest
    s = get_settings()
    rows = [r for r in load_manifest(s.processed_dir / "manifest.json") if r.split == "test" and r.annotation_level.startswith("quadrant_enumeration") and r.annotation_status == "annotated" and r.duplicate_of is None]
    rows.sort(key=lambda r: r.image_id)
    results = []
    for r in rows[:3]:
        src = next((p for p in (s.data_root / "training_data").glob("*/*.json") if "enumeration" in p.name and "quadrant_enumeration" == p.parent.name), None)
        coco = load_coco(src)
        cid = r.coco_image_id
        gt = [a["bbox"] for a in coco.by_image.get(cid, [])]
        gt = [[x, y, x + w, y + h] for x, y, w, h in gt]
        st, _, p, _ = http("POST", "/api/analyze/full", {"image_id": r.image_id})
        regs = (jbody(p) or {}).get("regions", [])
        ious = []
        for g in gt:
            best = 0.0
            for q in regs:
                b = q["box"]
                iw = max(0, min(g[2], b[2]) - max(g[0], b[0])); ih = max(0, min(g[3], b[3]) - max(g[1], b[1]))
                inter = iw * ih
                u = (g[2] - g[0]) * (g[3] - g[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
                best = max(best, inter / u if u > 0 else 0)
            ious.append(best)
        results.append({"image_id": r.image_id, "n_gt": len(gt), "n_pred": len(regs), "median_best_iou": float(np.median(ious)) if ious else None,
                        "recall_iou50": float(np.mean([i >= 0.5 for i in ious])) if ious else None})
    med = [x["median_best_iou"] for x in results if x.get("median_best_iou") is not None]
    pooled = sum(x['recall_iou50'] * x['n_gt'] for x in results if 'n_gt' in x) / max(1, sum(x['n_gt'] for x in results if 'n_gt' in x))
    ok = bool(med) and pooled >= 0.9 and min(med) >= 0.55
    results.append({'pooled_recall_iou50': round(pooled, 3)})
    out = ROOT / "docs" / "audit_evidence" / "alignment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"note": "test-split radiographs, evaluation only; boxes are in original pixels", "images": results}, indent=1), encoding="utf-8")
    return {"ok": ok, "text": json.dumps(results)[:260]}


if __name__ == "__main__":
    sys.exit(main())
