import React, { useState } from "react";
import { ExternalLink, Play, Square } from "lucide-react";
import PageHeader from "../components/PageHeader";
import ConfirmDialog from "../components/ConfirmDialog";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { ARRAY, when } from "../lib/format";

const DEFAULTS = { task: "classification", architecture: "resnet50", experiment_name: "exp_001", dataset_version: "current", epochs: 30, batch_size: 8, learning_rate: 0.0001, image_size: 512, device: "auto", seed: 42, use_approved_annotations: false };

export default function Training() {
  const [form, setForm] = useState(DEFAULTS);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const pre = useApi(() => api.trainPrereq({ task: form.task, architecture: form.architecture, use_approved_annotations: form.use_approved_annotations }), [form.task, form.architecture, form.use_approved_annotations]);
  const jobs = useApi(() => api.trainJobs(), [], { pollMs: 3000 });
  const start = useAction((cfg) => api.trainStart(cfg));
  const dry = useAction((cfg) => api.trainStart({ ...cfg, dry_run: true }));
  const stop = useAction((id) => api.trainStop(id));
  const [confirmStop, setConfirmStop] = useState(null);
  const archs = pre.data?.architectures?.[form.task] || [];
  const ready = pre.data?.ready;
  const fieldErr = form.epochs < 1 || form.batch_size < 1 || !(form.learning_rate > 0) || form.image_size < 32 || !form.experiment_name.trim();
  const num = (k, parse = parseInt) => (e) => { const v = parse(e.target.value, 10); set(k, Number.isNaN(v) ? 0 : v); };

  return (
    <div>
      <PageHeader title="Model Training" subtitle="Training starts only when its prerequisites are met. Nothing here is simulated." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="card card-pad" aria-label="Training configuration">
          <div className="grid gap-4 sm:grid-cols-2">
            <div><label className="label" htmlFor="t-task">Task</label>
              <select id="t-task" className="input" value={form.task} onChange={(e) => { const t = e.target.value; setForm((f) => ({ ...f, task: t, architecture: { classification: "resnet50", detection: "fasterrcnn_resnet50_fpn", segmentation: "maskrcnn_resnet50_fpn" }[t] })); }}>
                <option value="classification">Finding classification</option><option value="detection">Tooth detection</option><option value="segmentation">Instance segmentation</option></select></div>
            <div><label className="label" htmlFor="t-arch">Architecture</label>
              <select id="t-arch" className="input" value={form.architecture} onChange={(e) => set("architecture", e.target.value)}>{archs.map((a) => <option key={a}>{a}</option>)}{!archs.length && <option>{form.architecture}</option>}</select></div>
            <div><label className="label" htmlFor="t-name">Experiment name</label><input id="t-name" className="input" value={form.experiment_name} maxLength={64} onChange={(e) => set("experiment_name", e.target.value)} /></div>
            <div><label className="label" htmlFor="t-dev">Device</label><select id="t-dev" className="input" value={form.device} onChange={(e) => set("device", e.target.value)}><option>auto</option><option>cpu</option><option>cuda</option></select></div>
            <div><label className="label" htmlFor="t-ep">Epochs</label><input id="t-ep" type="number" min="1" className="input" value={form.epochs} onChange={num("epochs")} /></div>
            <div><label className="label" htmlFor="t-bs">Batch size</label><input id="t-bs" type="number" min="1" className="input" value={form.batch_size} onChange={num("batch_size")} /></div>
            <div><label className="label" htmlFor="t-lr">Learning rate</label><input id="t-lr" type="number" step="0.00001" min="0" className="input" value={form.learning_rate} onChange={num("learning_rate", parseFloat)} /></div>
            <div><label className="label" htmlFor="t-sz">Image size</label><input id="t-sz" type="number" min="32" className="input" value={form.image_size} onChange={num("image_size")} /></div>
            <div><label className="label" htmlFor="t-seed">Seed</label><input id="t-seed" type="number" className="input" value={form.seed} onChange={num("seed")} /></div>
            <label className="flex items-center gap-2 self-end text-sm"><input type="checkbox" checked={form.use_approved_annotations} onChange={(e) => set("use_approved_annotations", e.target.checked)} />Include approved Label Studio annotations</label>
          </div>
          <div className="mt-5 rounded-xl border border-slate-200 p-4" aria-live="polite">
            <h2 className="h-section mb-2">Prerequisites</h2>
            {pre.loading ? <LoadingState inline /> : pre.error ? <ErrorState error={pre.error} compact onRetry={pre.reload} /> : ready ? <StatusBadge tone="ok">all prerequisites met</StatusBadge> : (
              <ul className="space-y-2">{ARRAY(pre.data.unmet).map((u) => <li key={u.code} className="text-sm"><StatusBadge tone="warn">{u.code.replace(/_/g, " ")}</StatusBadge> <span className="ml-1">{u.message}</span><span className="block pl-1 text-xs text-muted">Fix: {u.fix}</span></li>)}</ul>)}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button className="btn-primary" disabled={!ready || fieldErr || start.busy} onClick={async () => { if (await start.run(form)) jobs.reload(true); }}><Play className="h-4 w-4" aria-hidden />{start.busy ? "Starting…" : "Start training"}</button>
            <button className="btn-ghost" disabled={!ready || fieldErr || dry.busy} title={!ready ? "Prerequisites are not met" : "Checks the configuration, prerequisites and job conflicts without starting anything"} data-testid="train-dry-run" onClick={() => dry.run(form)}>{dry.busy ? "Validating…" : "Validate only (no training)"}</button>
            {fieldErr && <span className="text-xs text-bad" role="alert">Check the numeric fields and name.</span>}
            {pre.data?.tensorboard?.event_files > 0 ? <a className="btn-ghost" href={pre.data.tensorboard_url} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" aria-hidden />TensorBoard</a>
              : pre.data?.tensorboard && <span className="text-xs text-muted" data-testid="tb-state">{pre.data.tensorboard.message}</span>}
          </div>
          {start.error && <div className="mt-3"><ErrorState error={start.error} compact /></div>}
          {dry.error && <div className="mt-3"><ErrorState error={dry.error} compact /></div>}
          {dry.result && !dry.error && <p className="mt-3 text-sm" role="status" data-testid="dry-run-result">Configuration is valid and no other job is running. A real run would write <span className="font-mono">{dry.result.would_write_checkpoint}</span>. Nothing was started or written.</p>}
        </section>

        <section className="card card-pad min-w-0" aria-label="Training jobs">
          <h2 className="h-section mb-2">Jobs</h2>
          {jobs.loading ? <LoadingState inline /> : jobs.error ? <ErrorState error={jobs.error} compact onRetry={jobs.reload} /> : jobs.data.length === 0 ? <EmptyState title="No training jobs" message="Jobs appear here once a run has started." /> : (
            <ul className="space-y-3">{jobs.data.map((j) => {
              const p = j.progress || {};
              const pctDone = p.total_epochs ? Math.round(((p.epoch || 0) / p.total_epochs) * 100) : 0;
              return (
                <li key={j.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                  <div className="flex items-center justify-between"><span className="font-mono text-xs">{j.id}</span><StatusBadge status={j.status} /></div>
                  <div className="text-xs text-muted">{j.kind} · {j.config?.architecture} · {when(j.created)}</div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded bg-slate-100" role="progressbar" aria-valuenow={pctDone} aria-valuemin={0} aria-valuemax={100}><div className="h-full bg-teal" style={{ width: `${pctDone}%` }} /></div>
                  <div className="mt-1 text-xs text-muted">epoch {p.epoch || 0}/{p.total_epochs || "?"}{p.loss != null ? ` · loss ${Number(p.loss).toFixed(4)}` : ""}</div>
                  {j.error && <p className="mt-1 text-xs text-bad">{j.error}</p>}
                  {j.checkpoint && <p className="mt-1 text-xs">Checkpoint <span className="font-mono">{j.checkpoint}</span></p>}
                  {ARRAY(j.log_tail).length > 0 && <pre className="mt-2 max-h-28 overflow-auto rounded bg-slate-900 p-2 text-[11px] text-slate-100">{j.log_tail.join("\n")}</pre>}
                  {["queued", "running"].includes(j.status) && <button className="btn-ghost mt-2 !py-1" onClick={() => setConfirmStop(j.id)}><Square className="h-3 w-3" aria-hidden />Stop</button>}
                </li>); })}</ul>)}
          {stop.error && <div className="mt-2"><ErrorState error={stop.error} compact /></div>}
        </section>
      </div>
      <ConfirmDialog open={!!confirmStop} danger title="Stop this training job?" confirmLabel="Stop job" busy={stop.busy} onCancel={() => setConfirmStop(null)}
        onConfirm={async () => { await stop.run(confirmStop); setConfirmStop(null); jobs.reload(true); }}>
        <p>Stopping is cooperative: the job ends after the current step. No checkpoint is promoted automatically.</p>
      </ConfirmDialog>
    </div>
  );
}
