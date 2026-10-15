"""Annotation workflow service (Label Studio + manual import/export)."""
from __future__ import annotations

from dentexmodel.annotation import LabelStudioClient, parse_labelstudio_export
from dentexmodel.errors import DentaMindError, ExternalServiceError
from dentexmodel.storage import jload

WORKFLOW = ["selected", "exported", "annotated", "imported", "validated", "approved"]


class AnnotationService:
    def __init__(self, ctx):
        self.ctx = ctx

    def supported_labels(self) -> list:
        lab = ((self.ctx.settings.data_cfg or {}).get("labels") or {}).get("findings") or {}
        return list(lab.values())

    def client(self) -> LabelStudioClient | None:
        s = self.ctx.settings
        return LabelStudioClient(s.label_studio_url, s.label_studio_api_key) if s.label_studio_configured else None

    def connection(self) -> dict:
        s = self.ctx.settings
        c = LabelStudioClient(s.label_studio_url, s.label_studio_api_key)
        h = c.health()
        h.update(url=s.label_studio_url, api_key_configured=bool(s.label_studio_api_key))
        if not h["reachable"]:
            h["message"] = ("Label Studio is not reachable. Start it (docker compose -f docker-compose.dentamind.yml --profile annotation up -d) or use the "
                            "manual workflow: download the task manifest, import it in Label Studio, export JSON, and upload it here.")
        return h

    def overview(self) -> dict:
        batches = self.ctx.db.list("annotation_batches")
        records = self.ctx.annotations.all()
        exported_ids = {i for b in batches for i in (jload(b["image_ids_json"]) or [])}
        counts = {"pending": len(exported_ids - set(records)),
                  "in_progress": None,  # only knowable through the live Label Studio API
                  "submitted": sum(1 for r in records.values() if r["status"] in ("imported", "validated")),
                  "approved": sum(1 for r in records.values() if r["status"] == "approved"),
                  "rejected": sum(1 for r in records.values() if r["status"] == "rejected")}
        rows = []
        for b in batches:
            for iid in jload(b["image_ids_json"]) or []:
                rec = records.get(iid)
                rows.append({"image_id": iid, "batch": b["id"], "strategy": b["strategy"], "created": b["created"],
                             "reviewer": rec.get("reviewer") if rec else None, "status": rec["status"] if rec else "exported",
                             "problems": rec.get("problems", []) if rec else []})
        return {"counts": counts, "rows": rows, "workflow": WORKFLOW, "versions": self.ctx.annotations.list_versions(),
                "label_studio": self.connection()}

    def import_export(self, tasks: list) -> dict:
        records = parse_labelstudio_export(tasks)
        if not records:
            raise DentaMindError("No completed annotations found in the uploaded Label Studio export.", code="empty_import",
                                 hint="Export from Label Studio as JSON (not JSON-MIN) after submitting annotations.")
        summary = self.ctx.annotations.import_records(records, self.supported_labels())
        summary["problems"] = {r.image_id: r.problems for r in records if r.problems}
        return summary

    def pull_from_label_studio(self, project_id: int) -> dict:
        c = self.client()
        if c is None:
            raise ExternalServiceError("Label Studio API key is not configured.", hint="Set LABEL_STUDIO_API_KEY in .env, or upload the JSON export manually.")
        return self.import_export(c.export_annotations(project_id))

    def push_to_label_studio(self, tasks: list, title: str) -> dict:
        c = self.client()
        if c is None:
            raise ExternalServiceError("Label Studio API key is not configured.", hint="Download the task manifest and import it manually in Label Studio.")
        proj = c.create_project(title)
        c.import_tasks(proj["id"], tasks)
        return {"project_id": proj["id"], "url": f"{self.ctx.settings.label_studio_url}/projects/{proj['id']}"}

    def approve(self, image_ids: list, reviewer: str) -> dict:
        if not reviewer or not reviewer.strip():
            raise DentaMindError("A reviewer name is required to approve annotations.", code="reviewer_required")
        changed = self.ctx.annotations.set_status(image_ids, "approved", reviewer.strip())
        v = self.ctx.annotations.create_version(note=f"approved by {reviewer.strip()}") if changed else None
        return {"approved": changed, "version": v}

    def reject(self, image_ids: list, reviewer: str) -> dict:
        return {"rejected": self.ctx.annotations.set_status(image_ids, "rejected", reviewer or None)}
