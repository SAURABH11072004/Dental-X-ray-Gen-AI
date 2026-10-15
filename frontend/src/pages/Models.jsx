import React, { useState } from "react";
import PageHeader from "../components/PageHeader";
import ConfirmDialog from "../components/ConfirmDialog";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import ModelStatusPanel from "../components/ModelStatusPanel";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { ARRAY, fmt, when } from "../lib/format";

const TASKS = ["detection", "segmentation", "numbering", "classification"];

export default function Models() {
  const m = useApi(() => api.models(), []);
  const ts = useApi(() => api.testSetStatus(), []);
  const hist = useApi(() => api.modelPromotions(), []);
  const select = useAction((b) => api.modelSelect(b));
  const promote = useAction((b) => api.modelPromote(b));
  const rollback = useAction((b) => api.modelRollback(b));
  const evalA = useAction((id) => api.modelEvaluate(id));
  const [target, setTarget] = useState(null);
  const ev = useApi(() => (target ? api.modelEvidence(target.model_id) : Promise.resolve(null)), [target?.model_id]);
  const [approver, setApprover] = useState("");
  const [why, setWhy] = useState("");
  const [rb, setRb] = useState({ task: "classification", approved_by: "", reason: "" });
  const items = ARRAY(m.data?.items);
  const reloadAll = () => { m.reload(true); hist.reload(true); };
  const blocked = !ev.data || ev.data.blockers.length > 0;

  return (
    <div>
      <PageHeader title="Model Registry" subtitle="Lists only checkpoint files that actually exist. A file without a valid metadata sidecar is not treated as a dental model." />
      {ts.data?.previously_used && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm" data-testid="test-set-status">
          <b className="text-warn">Internal test split already used.</b> {ts.data.statement}{" "}
          Used for: {ts.data.used_by.map((u) => `${u.version} (${u.task})`).join(", ")}.
          {!ts.data.ledger_initialised && " These are historical results found in the report files; the append-only ledger is created on the next authorized test evaluation."}
          {ts.data.chain_problems.length > 0 && <span className="font-semibold text-bad"> Ledger integrity problem: {ts.data.chain_problems.join("; ")}</span>}
        </div>)}
      {m.loading ? <LoadingState /> : m.error ? <ErrorState error={m.error} onRetry={m.reload} /> : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="card min-w-0">
            {items.length === 0 ? <div className="p-4"><EmptyState title="No model checkpoints found" message={`Place trained checkpoints in ${m.data.checkpoint_dir}/ together with a .json metadata sidecar (task, architecture, version, dataset version), or train one.`} to="/training" actionLabel="Open Model Training" /></div> : (
              <div className="overflow-x-auto"><table className="w-full">
                <thead><tr>{["Version", "Task", "Architecture", "Dental", "Provenance", "Created", "Evaluation", "Test split", "Active for", "Actions"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
                <tbody>{items.map((x) => (
                  <tr key={x.model_id}><td className="td font-mono text-xs">{x.version}</td><td className="td">{x.task}</td><td className="td">{x.architecture || "—"}</td>
                    <td className="td">{x.dental_specific ? <StatusBadge status="available">dental</StatusBadge> : <StatusBadge tone="warn">not dental</StatusBadge>}</td>
                    <td className="td text-xs" title={x.provenance_level?.detail || ""}>{x.provenance_level?.verified ? <StatusBadge tone="ok">image-level manifest</StatusBadge> : x.provenance_level?.legacy ? <StatusBadge tone="warn">legacy</StatusBadge> : <StatusBadge tone="bad">manifest broken</StatusBadge>}</td>
                    <td className="td text-xs">{when(x.created)}</td><td className="td"><StatusBadge tone="neutral">{x.eval_status}</StatusBadge></td>
                    <td className="td text-xs">{x.test_split_used ? <StatusBadge tone="warn">used (historical)</StatusBadge> : "not used"}</td>
                    <td className="td">{ARRAY(x.active_for).join(", ") || "—"}{x.promoted && <> <StatusBadge tone="ok">promoted</StatusBadge></>}</td>
                    <td className="td whitespace-nowrap"><button className="btn-ghost !py-1" disabled={!x.dental_specific} onClick={async () => { if (await select.run({ task: x.task, model_id: x.model_id })) reloadAll(); }}>Use</button>{" "}
                      <button className="btn-ghost !py-1" disabled={!x.dental_specific} onClick={() => { setWhy(""); setTarget(x); }}>Promote</button>{" "}
                      <button className="btn-ghost !py-1" disabled={evalA.busy} onClick={() => evalA.run(x.model_id)}>Evaluate</button></td></tr>))}</tbody></table></div>)}
            {evalA.result && <p className="p-4 text-sm" role="status" data-testid="eval-started">Evaluation started on the validation split (job {evalA.result.job_id}). One job runs at a time; the measured report appears as {evalA.result.report_name} on the Experiments page when it finishes. Check Training → jobs for progress or errors.</p>}
            {(select.error || promote.error || evalA.error || rollback.error) && <div className="p-4"><ErrorState error={select.error || promote.error || evalA.error || rollback.error} compact /></div>}
          </div>
          <aside className="space-y-5">
            <div className="card card-pad"><h2 className="h-section mb-2">Active dental models</h2><ModelStatusPanel models={items} /></div>
            <div className="card card-pad space-y-2" data-testid="rollback">
              <h2 className="h-section">Roll back</h2>
              <p className="text-xs text-muted">Re-activates the model that the last promotion replaced (recorded below).</p>
              <select className="input" value={rb.task} onChange={(e) => setRb({ ...rb, task: e.target.value })}>{TASKS.map((t) => <option key={t}>{t}</option>)}</select>
              <input className="input" placeholder="Your name" value={rb.approved_by} onChange={(e) => setRb({ ...rb, approved_by: e.target.value })} />
              <input className="input" placeholder="Reason" value={rb.reason} onChange={(e) => setRb({ ...rb, reason: e.target.value })} />
              <button className="btn-ghost w-full" disabled={rollback.busy || !rb.approved_by.trim() || !rb.reason.trim()} onClick={async () => { if (await rollback.run(rb)) reloadAll(); }}>Roll back {rb.task}</button>
            </div>
            <div className="card card-pad" data-testid="promotion-history"><h2 className="h-section mb-2">Promotion record</h2>
              {ARRAY(hist.data?.items).length === 0 ? <p className="text-xs text-muted">No promotions recorded yet. Models active before this record existed were selected directly.</p> : (
                <ul className="space-y-2 text-xs">{hist.data.items.map((h) => (
                  <li key={h.id}><b>{h.action}</b> {h.task}: <span className="font-mono">{h.version}</span> by {h.approved_by}, {when(h.created)}<br /><span className="text-muted">replaced {h.previous_model_id || "nothing"}. {h.justification}</span></li>))}</ul>)}
            </div>
            <p className="text-xs text-muted">{m.data.note}</p>
          </aside>
        </div>)}
      <ConfirmDialog open={!!target} wide title="Promote this model?" confirmLabel="Promote" busy={promote.busy} confirmDisabled={blocked || !approver.trim() || why.trim().length < 20}
        onCancel={() => setTarget(null)}
        onConfirm={async () => { if (await promote.run({ task: target.task, model_id: target.model_id, approved_by: approver, justification: why, confirm: true })) { setTarget(null); reloadAll(); } }}>
        <p>Promoting <span className="font-mono">{target?.version}</span> makes it the active {target?.task} model. Promotion is never automatic and is recorded with the evidence below.</p>
        {ev.loading ? <p className="text-muted">Collecting evidence…</p> : ev.error ? <ErrorState error={ev.error} compact /> : ev.data && <Evidence ev={ev.data} />}
        <label className="label" htmlFor="apr">Approved by</label><input id="apr" className="input" value={approver} onChange={(e) => setApprover(e.target.value)} />
        <label className="label" htmlFor="why">Justification (which validation evidence, which limitations you accept)</label>
        <textarea id="why" className="input min-h-[70px]" value={why} onChange={(e) => setWhy(e.target.value)} />
        {(!approver.trim() || why.trim().length < 20) && <p className="text-xs text-muted">A name and a justification of at least 20 characters are required.</p>}
        {promote.error && <ErrorState error={promote.error} compact />}
      </ConfirmDialog>
    </div>
  );
}

function Metrics({ m }) {
  if (!m) return <span className="text-muted">none</span>;
  const flat = Object.entries(m).flatMap(([k, v]) => (v && typeof v === "object" ? Object.entries(v).filter(([, x]) => typeof x === "number").map(([kk, x]) => `${k}.${kk} ${fmt(x)}`) : []));
  return <span className="font-mono text-xs">{flat.slice(0, 6).join(" · ") || "—"}</span>;
}

function Evidence({ ev }) {
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 p-3 text-xs" data-testid="promotion-evidence">
      {ev.blockers.length > 0 && <div><b className="text-bad">Cannot be promoted:</b><ul className="list-disc pl-5">{ev.blockers.map((b) => <li key={b}>{b}</li>)}</ul></div>}
      <div><b>Basis - validation split:</b> {ev.validation ? <><Metrics m={ev.validation.metrics} /> (n={ev.validation.n_images}, {when(ev.validation.generated)}; tied by {ev.validation.tied_to_checkpoint_by})</> : <span className="text-bad">missing</span>}</div>
      <div><b>Provenance:</b> {ev.provenance.level}</div>
      <div className="text-muted"><b>Training-time metrics (not a basis):</b> <Metrics m={ev.training_metrics.metrics} /></div>
      {ev.calibration && <div className="text-muted"><b>Calibration split (not a basis):</b> <Metrics m={ev.calibration.metrics} /></div>}
      <div className="text-muted"><b>Test split:</b> {ev.test_history.length ? ev.test_history.map((t) => `${t.kind}${t.historical ? " (historical)" : ""} ${when(t.evaluated_at)}`).join("; ") : "not evaluated"} - context only, never a basis.</div>
      {ev.warnings.length > 0 && <div><b className="text-warn">Warnings:</b><ul className="list-disc pl-5">{ev.warnings.map((w) => <li key={w}>{w}</li>)}</ul></div>}
      <div><b>Limitations:</b><ul className="list-disc pl-5">{ev.limitations.map((l) => <li key={l}>{l}</li>)}</ul></div>
    </div>
  );
}
