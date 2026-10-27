"""Label Studio integration: labeling config, task/pre-annotation export, annotation import + validation,
approval gate, versioned annotation manifest, and a small REST client (token from .env)."""
from __future__ import annotations

import hashlib
import json
import logging
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import quoteattr

from dentexmodel.data.fdi import all_permanent_fdi, is_valid_fdi
from dentexmodel.errors import DentaMindError, ExternalServiceError
from dentexmodel.utils.geometry import (percent_to_pixel_xyxy, pixel_to_percent_xywh, polygon_percent_to_pixel,
                                        validate_box_xyxy)

logger = logging.getLogger(__name__)
STATUSES = ("selected", "exported", "annotated", "imported", "validated", "approved", "rejected")
DEFAULT_FINDINGS = ["Caries", "DeepCaries", "Impacted", "PeriapicalLesion"]


def labeling_config_xml(findings: list | None = None) -> str:
    """Label Studio config: boxes with finding label, per-region FDI choice, optional polygon masks."""
    findings = findings or DEFAULT_FINDINGS
    rect = "\n".join(f"    <Label value={quoteattr(f)}/>" for f in findings)
    poly = "\n".join(f"    <Label value={quoteattr(f)}/>" for f in findings)
    fdi = "\n".join(f"    <Choice value=\"{c}\"/>" for c in all_permanent_fdi())
    return f"""<View>
  <Header value="DentaMind AI - correct tooth boxes, FDI numbers and findings (research use)"/>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>
  <RectangleLabels name="finding" toName="image" strokeWidth="2">
{rect}
  </RectangleLabels>
  <PolygonLabels name="mask" toName="image" strokeWidth="2">
{poly}
  </PolygonLabels>
  <Choices name="tooth_fdi" toName="image" perRegion="true" choice="single">
{fdi}
  </Choices>
</View>
"""


def build_task(image_id: str, image_url: str, width: int, height: int, detections: list | None = None,
               model_version: str | None = None, meta: dict | None = None) -> dict:
    """One Label Studio task. ``detections`` (real model output only) become editable pre-annotations."""
    task = {"data": {"image": image_url, "image_id": image_id}, "meta": {"image_id": image_id, "width": width, "height": height,
                                                                         **(meta or {})}}
    results = []
    for i, d in enumerate(detections or []):
        val = pixel_to_percent_xywh(d["box"], width, height)
        rid = f"det{i}"
        results.append({"id": rid, "from_name": "finding", "to_name": "image", "type": "rectanglelabels",
                        "original_width": width, "original_height": height, "image_rotation": 0,
                        "value": {**val, "rotation": 0, "rectanglelabels": [d.get("label", "Caries")]}, "score": d.get("score")})
        if d.get("fdi") is not None:
            results.append({"id": rid, "from_name": "tooth_fdi", "to_name": "image", "type": "choices",
                            "value": {"choices": [str(d["fdi"])]}})
    if results:
        task["predictions"] = [{"model_version": model_version or "unknown", "result": results}]
    return task


@dataclass
class AnnotationRecord:
    image_id: str
    width: int
    height: int
    boxes: list = field(default_factory=list)      # {"box": xyxy px, "label", "fdi"}
    polygons: list = field(default_factory=list)   # {"points": [(x,y) px], "label"}
    annotator: str | None = None
    ls_task_id: int | None = None
    status: str = "imported"
    problems: list = field(default_factory=list)


def parse_labelstudio_export(tasks: list) -> list:
    """Parse the Label Studio JSON export (list of tasks with ``annotations``). Cancelled annotations and
    tasks without a (non-skipped) annotation are ignored. Percent -> pixel conversion uses the *original*
    image size stored on each result."""
    records = []
    for t in tasks:
        anns = [a for a in t.get("annotations", []) if not a.get("was_cancelled")]
        if not anns:
            continue
        ann = anns[-1]
        image_id = (t.get("data") or {}).get("image_id") or (t.get("meta") or {}).get("image_id")
        if not image_id:
            continue
        w = h = None
        rec = AnnotationRecord(image_id=str(image_id), width=0, height=0, annotator=str(ann.get("completed_by")) if ann.get("completed_by") is not None else None,
                               ls_task_id=t.get("id"))
        by_id: dict = {}
        for r in ann.get("result", []):
            w = r.get("original_width", w) or w
            h = r.get("original_height", h) or h
            rid = r.get("id")
            entry = by_id.setdefault(rid, {})
            v = r.get("value", {})
            if r.get("type") == "rectanglelabels":
                if r.get("original_width"):
                    entry["box_pct"] = v
                    entry["w"], entry["h"] = r["original_width"], r["original_height"]
                    entry["label"] = (v.get("rectanglelabels") or [None])[0]
            elif r.get("type") == "polygonlabels":
                entry["poly_pct"] = v.get("points", [])
                entry["w"], entry["h"] = r.get("original_width"), r.get("original_height")
                entry["label"] = (v.get("polygonlabels") or [None])[0]
            elif r.get("type") == "choices" and r.get("from_name") == "tooth_fdi":
                ch = v.get("choices") or []
                entry["fdi"] = int(ch[0]) if ch and str(ch[0]).isdigit() else None
        for entry in by_id.values():
            if "box_pct" in entry and entry.get("w"):
                box = percent_to_pixel_xyxy(entry["box_pct"], entry["w"], entry["h"])
                rec.boxes.append({"box": [round(x, 2) for x in box], "label": entry.get("label"), "fdi": entry.get("fdi")})
            if "poly_pct" in entry and entry.get("w"):
                pts = polygon_percent_to_pixel(entry["poly_pct"], entry["w"], entry["h"])
                rec.polygons.append({"points": [[round(x, 2), round(y, 2)] for x, y in pts], "label": entry.get("label"), "fdi": entry.get("fdi")})
        rec.width, rec.height = int(w or 0), int(h or 0)
        records.append(rec)
    return records


def validate_record(rec: AnnotationRecord, supported_labels: list, allow_deciduous: bool = False) -> list:
    """Return a list of problems; an empty list means the annotation may be marked 'validated'."""
    probs = []
    if rec.width <= 0 or rec.height <= 0:
        probs.append("missing original image size")
    for i, b in enumerate(rec.boxes):
        for p in validate_box_xyxy(b["box"], rec.width or None, rec.height or None):
            probs.append(f"box {i}: {p}")
        if b.get("label") not in supported_labels:
            probs.append(f"box {i}: unsupported label {b.get('label')!r}")
        if b.get("fdi") is not None and not is_valid_fdi(b["fdi"], allow_deciduous):
            probs.append(f"box {i}: invalid FDI {b['fdi']}")
    for i, pg in enumerate(rec.polygons):
        if len(pg["points"]) < 3:
            probs.append(f"polygon {i}: fewer than 3 points")
    fdis = [b["fdi"] for b in rec.boxes if b.get("fdi") is not None]
    dup = sorted({f for f in fdis if fdis.count(f) > 1})
    if dup:
        probs.append(f"duplicate FDI numbers: {dup}")
    if not rec.boxes and not rec.polygons:
        probs.append("no regions annotated (confirm this is intended)")
    return probs


class AnnotationStore:
    """File-backed, versioned store under ``<data>/annotations``. Only *approved* records are exposed to
    training (:meth:`approved_records`). Approval is an explicit call - never automatic."""

    def __init__(self, annotations_dir: Path):
        self.dir = Path(annotations_dir)
        self.records_file = self.dir / "records.json"

    def _load(self) -> dict:
        if self.records_file.is_file():
            return json.loads(self.records_file.read_text(encoding="utf-8"))
        return {}

    def _save(self, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.records_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(self.records_file)

    def import_records(self, records: list, supported_labels: list, allow_deciduous: bool = False) -> dict:
        data = self._load()
        summary = {"imported": 0, "validated": 0, "with_problems": 0}
        for rec in records:
            probs = validate_record(rec, supported_labels, allow_deciduous)
            hard = [p for p in probs if not p.startswith("no regions")]
            rec.problems = probs
            rec.status = "validated" if not hard else "imported"
            prev = data.get(rec.image_id)
            if prev and prev["status"] == "approved":
                rec.status = "imported"  # a re-import never silently keeps approval
            data[rec.image_id] = {**asdict(rec), "updated": datetime.now(timezone.utc).isoformat()}
            summary["imported"] += 1
            summary["validated" if rec.status == "validated" else "with_problems"] += 1
        self._save(data)
        return summary

    def set_status(self, image_ids: list, status: str, reviewer: str | None = None) -> list:
        if status not in ("approved", "rejected", "validated", "imported"):
            raise DentaMindError(f"invalid status {status}", code="invalid_status")
        data = self._load()
        changed = []
        for iid in image_ids:
            rec = data.get(iid)
            if rec is None:
                continue
            if status == "approved" and rec["status"] not in ("validated", "approved"):
                raise DentaMindError(f"'{iid}' is {rec['status']}; only validated annotations can be approved.",
                                     code="not_validated", hint="Fix the listed problems and re-validate first.")
            rec["status"], rec["reviewer"] = status, reviewer
            rec["updated"] = datetime.now(timezone.utc).isoformat()
            changed.append(iid)
        self._save(data)
        return changed

    def all(self) -> dict:
        return self._load()

    def approved_records(self) -> list:
        return [r for r in self._load().values() if r["status"] == "approved"]

    def create_version(self, note: str = "") -> dict:
        """Snapshot approved records as ``versions/annotations_vNNNN.json`` with checksum and parent link."""
        approved = sorted(self.approved_records(), key=lambda r: r["image_id"])
        vdir = self.dir / "versions"
        vdir.mkdir(parents=True, exist_ok=True)
        existing = sorted(vdir.glob("annotations_v*.json"))
        n = len(existing) + 1
        payload = {"version": n, "created": datetime.now(timezone.utc).isoformat(), "note": note,
                   "parent": existing[-1].name if existing else None, "n_images": len(approved), "records": approved}
        body = json.dumps(payload["records"], sort_keys=True).encode()
        payload["sha256"] = hashlib.sha256(body).hexdigest()
        path = vdir / f"annotations_v{n:04d}.json"
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        return {"version": n, "file": path.name, "n_images": len(approved), "sha256": payload["sha256"]}

    def list_versions(self) -> list:
        vdir = self.dir / "versions"
        out = []
        for p in sorted(vdir.glob("annotations_v*.json")) if vdir.is_dir() else []:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append({k: d[k] for k in ("version", "created", "note", "parent", "n_images", "sha256")} | {"file": p.name})
        return out


class LabelStudioClient:
    """Minimal REST client. Needs LABEL_STUDIO_URL and LABEL_STUDIO_API_KEY (legacy token). Not exercised in
    CI because no Label Studio server is available; connection failures are reported, not raised blindly."""

    def __init__(self, url: str, api_key: str, timeout: float = 5.0):
        self.url, self.key, self.timeout = url.rstrip("/"), api_key, timeout

    def _req(self, method: str, path: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"Authorization": f"Token {self.key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raise ExternalServiceError(f"Label Studio returned HTTP {exc.code} for {path}",
                                       hint="Check LABEL_STUDIO_API_KEY (Account & Settings -> Access Token).")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ExternalServiceError(f"Cannot reach Label Studio at {self.url}: {getattr(exc, 'reason', exc)}",
                                       hint="Start Label Studio (docker compose --profile annotation up -d) or use the manual export/import workflow.")

    def health(self) -> dict:
        # on Windows 'localhost' is tried over IPv6 first and a closed port makes the attempt wait ~4 s (this probe runs on every
        # Home dashboard load); use the IPv4 loopback, as backend/services/system.py:probe does
        url = self.url.replace("//localhost", "//127.0.0.1", 1)
        u = urllib.parse.urlparse(url)
        if u.hostname in ("127.0.0.1", "::1"):
            # a refused loopback connection still takes ~2 s on Windows (SYN retries); a running local server accepts in
            # milliseconds, so a short port check first keeps the dashboard fast when Label Studio is not started
            try:
                socket.create_connection((u.hostname, u.port or 80), timeout=0.5).close()
            except OSError as exc:
                return {"reachable": False, "error": str(exc)}
        try:
            req = urllib.request.Request(url + "/health", method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return {"reachable": True, "status_code": r.status, "authenticated": bool(self.key)}
        except Exception as exc:  # noqa: BLE001
            return {"reachable": False, "error": str(getattr(exc, 'reason', exc))}

    def create_project(self, title: str, findings: list | None = None) -> dict:
        return self._req("POST", "/api/projects", {"title": title, "label_config": labeling_config_xml(findings)})

    def import_tasks(self, project_id: int, tasks: list) -> dict:
        return self._req("POST", f"/api/projects/{project_id}/import", tasks)

    def export_annotations(self, project_id: int) -> list:
        return self._req("GET", f"/api/projects/{project_id}/export?exportType=JSON")
