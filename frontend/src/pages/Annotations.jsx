import React, { useRef, useState } from "react";
import { Check, Download, Upload, X } from "lucide-react";
import PageHeader from "../components/PageHeader";
import RegionReview from "../components/RegionReview";
import AnnotationStatusTimeline from "../components/AnnotationStatusTimeline";
import ConfirmDialog from "../components/ConfirmDialog";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { api, downloadBlob } from "../services/api";
import { ARRAY, when } from "../lib/format";

export default function Annotations() {
  const ov = useApi(() => api.annotations(), [], { pollMs: 15000 });
  const recs = useApi(() => api.annotationRecords(), []);
  const fileRef = useRef(null);
  const [picked, setPicked] = useState([]);
  const [reviewer, setReviewer] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [parseErr, setParseErr] = useState(null);
  const imp = useAction((tasks) => api.annotationImport(tasks));
  const pull = useAction((pid) => api.annotationPull(pid));
  const appr = useAction((ids, who) => api.annotationApprove(ids, who));
  const rej = useAction((ids, who) => api.annotationReject(ids, who));
  const [project, setProject] = useState("");

  const reload = () => { ov.reload(true); recs.reload(true); };
  async function onFile(e) {
    setParseErr(null);
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!Array.isArray(data)) throw new Error("Expected a JSON array (Label Studio full JSON export).");
      if (await imp.run(data)) reload();
    } catch (err) { setParseErr(err.message || String(err)); }
  }
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const records = ARRAY(recs.data);
  const counts = ov.data ? Object.fromEntries(ov.data.workflow.map((w) => [w, null])) : {};
  if (ov.data) {
    const r = ov.data.rows;
    counts.selected = r.length; counts.exported = r.length;
    counts.annotated = null;
    counts.imported = records.filter((x) => ["imported", "validated", "approved"].includes(x.status)).length;
    counts.validated = records.filter((x) => ["validated", "approved"].includes(x.status)).length;
    counts.approved = records.filter((x) => x.status === "approved").length;
  }
  const doApprove = async () => { const r = await appr.run(picked, reviewer); setConfirm(false); if (r) { setPicked([]); reload(); } };

  return (
    <div>
      <PageHeader title="Annotation Studio" subtitle="Only annotations a named reviewer has approved can ever be used for training."
        actions={<button className="btn-ghost" onClick={async () => { try { const t = await api.labelConfig(); downloadBlob("labeling_config.xml", t, "application/xml"); } catch (e) { setParseErr(e.message); } }}><Download className="h-4 w-4" aria-hidden />Label config (XML)</button>} />
      <div className="mb-5"><RegionReview /></div>
      <h2 className="h-section mb-2">Label Studio exchange</h2>
      {ov.loading ? <LoadingState /> : ov.error ? <ErrorState error={ov.error} onRetry={ov.reload} /> : (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <MetricCard label="Pending" value={ov.data.counts.pending} />
            <MetricCard label="In progress" value={ov.data.counts.in_progress ?? "N/A"} hint={ov.data.counts.in_progress == null ? "Visible only via live Label Studio" : ""} />
            <MetricCard label="Submitted" value={ov.data.counts.submitted} tone="teal" />
            <MetricCard label="Approved" value={ov.data.counts.approved} tone="ok" />
            <MetricCard label="Rejected" value={ov.data.counts.rejected} tone="bad" />
          </div>
          <div className="card card-pad overflow-x-auto"><AnnotationStatusTimeline stages={ov.data.workflow} counts={counts} /></div>
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="card min-w-0">
              <div className="flex items-center justify-between p-4"><h2 className="h-section">Annotation batches</h2></div>
              {ov.data.rows.length === 0 ? <div className="p-4"><EmptyState title="No annotation batches" message="Export a selection from the Active Learning page to create one." to="/active-learning" actionLabel="Open Active Learning" /></div> : (
                <div className="overflow-x-auto"><table className="w-full"><thead><tr>{["", "Image", "Batch", "Strategy", "Status", "Reviewer", "Problems"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
                  <tbody>{ov.data.rows.map((r) => (
                    <tr key={r.batch + r.image_id}><td className="td"><input type="checkbox" aria-label={`Select ${r.image_id}`} disabled={!["imported", "validated"].includes(r.status)} checked={picked.includes(r.image_id)} onChange={() => toggle(r.image_id)} /></td>
                      <td className="td font-mono text-xs">{r.image_id}</td><td className="td font-mono text-xs">{r.batch}</td><td className="td">{r.strategy}</td>
                      <td className="td"><StatusBadge status={r.status} /></td><td className="td">{r.reviewer || "—"}</td>
                      <td className="td text-xs text-bad">{ARRAY(r.problems).join("; ")}</td></tr>))}</tbody></table></div>)}
              <div className="flex flex-wrap items-end gap-3 border-t border-slate-100 p-4">
                <div><label className="label" htmlFor="rv">Reviewer name</label><input id="rv" className="input" value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Required to approve" /></div>
                <button className="btn-teal" disabled={!picked.length || !reviewer.trim() || appr.busy} title={!picked.length ? "Select at least one imported annotation first" : !reviewer.trim() ? "Enter the approver's name" : ""} onClick={() => setConfirm(true)}><Check className="h-4 w-4" aria-hidden />Approve for training ({picked.length})</button>
                <button className="btn-ghost" disabled={!picked.length || rej.busy} title={!picked.length ? "Select at least one imported annotation first" : ""} onClick={async () => { if (await rej.run(picked, reviewer)) { setPicked([]); reload(); } }}><X className="h-4 w-4" aria-hidden />Reject</button>
              </div>
              {(appr.error || rej.error) && <div className="p-4 pt-0"><ErrorState error={appr.error || rej.error} compact /></div>}
            </div>
            <aside className="space-y-5">
              <div className="card card-pad">
                <h2 className="h-section mb-2">Label Studio</h2>
                <p className="text-sm">{ov.data.label_studio.reachable ? <StatusBadge status="reachable" /> : <StatusBadge status="unreachable" />} <span className="ml-1 text-xs text-muted">{ov.data.label_studio.url}</span></p>
                {ov.data.label_studio.message && <p className="mt-2 text-xs text-muted">{ov.data.label_studio.message}</p>}
                <div className="mt-3 flex gap-2"><input className="input" type="number" min="1" placeholder="Project id" aria-label="Label Studio project id" value={project} onChange={(e) => setProject(e.target.value)} />
                  <button className="btn-ghost" disabled={!project || pull.busy} title={!project ? "Enter a Label Studio project id first (Label Studio must be running and configured)" : ""} onClick={async () => { if (await pull.run(parseInt(project, 10))) reload(); }}>Pull</button></div>
                {pull.error && <div className="mt-2"><ErrorState error={pull.error} compact /></div>}
              </div>
              <div className="card card-pad">
                <h2 className="h-section mb-2">Import annotations (manual)</h2>
                <input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" onChange={onFile} aria-label="Label Studio JSON export" />
                <button className="btn-ghost w-full" disabled={imp.busy} onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" aria-hidden />{imp.busy ? "Importing…" : "Upload Label Studio JSON"}</button>
                {parseErr && <p className="mt-2 text-sm text-bad" role="alert">{parseErr}</p>}
                {imp.error && <div className="mt-2"><ErrorState error={imp.error} compact /></div>}
                {imp.result && <p className="mt-2 text-sm text-ok" role="status">Imported: {JSON.stringify({ ...imp.result, problems: undefined })}</p>}
                {imp.result?.problems && Object.keys(imp.result.problems).length > 0 && <ul className="mt-2 list-disc pl-5 text-xs text-bad">{Object.entries(imp.result.problems).map(([k, v]) => <li key={k}>{k}: {v.join("; ")}</li>)}</ul>}
              </div>
              <div className="card card-pad">
                <h2 className="h-section mb-2">Annotation versions</h2>
                {ARRAY(ov.data.versions).length === 0 ? <p className="text-sm text-muted">No approved snapshot yet.</p> : (
                  <ul className="divide-y divide-slate-100 text-xs">{ov.data.versions.map((v) => <li key={v.version || v.id} className="py-1.5"><span className="font-mono">{v.version || v.id}</span> · {when(v.created)} <span className="block truncate text-muted">sha256 {v.sha256}</span></li>)}</ul>)}
              </div>
            </aside>
          </div>
        </div>)}
      <ConfirmDialog open={confirm} title="Approve annotations for training?" confirmLabel="Approve" busy={appr.busy} onCancel={() => setConfirm(false)} onConfirm={doApprove}>
        <p>{picked.length} image(s) will become eligible for training, attributed to <b>{reviewer}</b>. A versioned snapshot is created.</p>
      </ConfirmDialog>
    </div>
  );
}
