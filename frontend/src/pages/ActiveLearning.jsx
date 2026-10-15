import React, { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Download, Send } from "lucide-react";
import PageHeader from "../components/PageHeader";
import AcquisitionStrategySelector from "../components/AcquisitionStrategySelector";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { api, downloadBlob } from "../services/api";
import { ARRAY, fmt, when } from "../lib/format";

const STEPS = ["Dataset & pool", "Strategy", "Parameters", "Run selection", "Review", "Export"];

export default function ActiveLearning() {
  const info = useApi(() => api.alInfo(), []);
  const pool = useApi(() => api.alPool(), []);
  const rounds = useApi(() => api.alRounds(), []);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({ strategy: "combined", budget: 20, batch_size: 10, seed: 42, diversity_weight: 0.3 });
  const sel = useAction((b) => api.alSelect(b));
  const exp = useAction((id, push) => api.alExport(id, push));
  const result = sel.result;
  const [nScore, setNScore] = useState(30);
  const [job, setJob] = useState(null);
  const scoreStart = useAction((n) => api.alScorePool(n));
  useEffect(() => {
    if (!job || ["succeeded", "failed"].includes(job.status)) return undefined;
    const t = setInterval(async () => { try { const j = await api.alScoreStatus(job.job_id); setJob((o) => ({ ...o, ...j })); if (j.status !== "running") pool.reload(true); } catch { /* keep polling */ } }, 3000);
    return () => clearInterval(t);
  }, [job?.job_id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps
  async function startScoring() { const r = await scoreStart.run(nScore); if (r) setJob({ ...r, status: "running", progress: { done: 0, total: r.total } }); }
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const poolN = pool.data?.size ?? 0;
  const paramErr = form.budget < 1 ? "Budget must be at least 1." : form.batch_size < 1 ? "Batch size must be at least 1." : form.diversity_weight < 0 || form.diversity_weight > 1 ? "Diversity weight must be between 0 and 1." : null;

  async function run() { const r = await sel.run({ ...form }); if (r) { setStep(4); rounds.reload(); } }
  async function doExport(push) {
    const r = await exp.run(result.round_id, push);
    if (r && !push) downloadBlob(`${result.round_id}_label_studio_tasks.json`, JSON.stringify(r.tasks, null, 1));
  }

  return (
    <div>
      <PageHeader title="Active Learning" subtitle="Choose which radiographs are most worth annotating next. The test split is never eligible." />
      <ol className="mb-5 flex flex-wrap gap-2" aria-label="Steps">
        {STEPS.map((s, i) => (
          <li key={s}><button onClick={() => (i <= 3 || result) && setStep(i)} disabled={i > 3 && !result} title={i > 3 && !result ? "Available after you run a selection (step 4)" : ""} className={`rounded-full border px-3 py-1 text-xs font-medium ${i === step ? "border-teal bg-teal text-white" : "border-slate-300 bg-white text-ink"}`} aria-current={i === step ? "step" : undefined}>{i + 1}. {s}</button></li>))}
      </ol>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="card card-pad min-w-0" aria-label={STEPS[step]}>
          {step === 0 && (pool.loading ? <LoadingState /> : pool.error ? (
            <ErrorState error={pool.error} onRetry={pool.reload} />) : (
            <div className="space-y-3">
              <h2 className="h-section">Candidate pool</h2>
              {pool.data.is_test_data && <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-violet-800"><StatusBadge status="test_data">TEST DATA</StatusBadge> The pool is made of unlabeled sample radiographs. Selection here validates the software only.</div>}
              <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                <div><dt className="text-muted">Pool images</dt><dd className="text-lg font-semibold">{poolN}</dd></div>
                <div><dt className="text-muted">Locked test images</dt><dd className="text-lg font-semibold">{pool.data.excluded_test_split}</dd></div>
                <div><dt className="text-muted">Already labeled (approved)</dt><dd className="text-lg font-semibold">{pool.data.labeled}</dd></div>
              </dl>
              <div className="rounded-lg border border-slate-200 p-3" data-testid="score-pool">
                <p className="text-sm font-medium">Uncertainty signals: {pool.data.scored} of {poolN} pool images scored</p>
                <p className="mt-1 text-xs text-muted">Entropy / flip disagreement / mask instability need the models to be run on each image (about 10 s each on the GPU). Unscored images cannot be ranked by an uncertainty strategy — their signals are reported as unavailable, never zero. Pixel-duplicates of labeled images ({pool.data.excluded_duplicates_of_labeled}) are excluded.</p>
                <div className="mt-2 flex flex-wrap items-end gap-2">
                  <label className="text-xs text-muted">Images to score <input type="number" min="1" max="500" className="input mt-0.5 !w-24" value={nScore} onChange={(e) => setNScore(Math.max(1, Math.min(500, parseInt(e.target.value || "1", 10))))} /></label>
                  <button className="btn-teal" disabled={scoreStart.busy || job?.status === "running" || poolN === 0} onClick={startScoring}>{job?.status === "running" ? "Scoring…" : "Score pool images"}</button>
                  {job && <span className="text-xs text-muted" role="status">{job.status}: {job.progress?.done ?? 0}/{job.progress?.total ?? job.total}{job.progress?.failed ? ` (${job.progress.failed} failed)` : ""}</span>}
                </div>
                {scoreStart.error && <div className="mt-2"><ErrorState error={scoreStart.error} compact /></div>}
              </div>
              {poolN === 0 && <EmptyState title="The candidate pool is empty" message="All images are labeled or reserved for testing." />}
            </div>))}
          {step === 1 && (info.loading ? <LoadingState /> : info.error ? <ErrorState error={info.error} onRetry={info.reload} /> :
            <AcquisitionStrategySelector strategies={info.data.strategies} value={form.strategy} onChange={(v) => set("strategy", v)} />)}
          {step === 2 && (
            <div className="grid gap-4 sm:grid-cols-2">
              {[["budget", "Annotation budget (images)", 1], ["batch_size", "Batch size", 1], ["seed", "Random seed", 0]].map(([k, l, min]) => (
                <div key={k}><label className="label" htmlFor={k}>{l}</label><input id={k} type="number" min={min} className="input" value={form[k]} onChange={(e) => set(k, Math.max(min, parseInt(e.target.value || min, 10)))} /></div>))}
              <div><label className="label" htmlFor="dw">Diversity weight (0–1)</label><input id="dw" type="number" step="0.05" min="0" max="1" className="input" value={form.diversity_weight} disabled={form.strategy !== "combined"} onChange={(e) => set("diversity_weight", parseFloat(e.target.value || 0))} /></div>
              {paramErr && <p className="text-sm text-bad sm:col-span-2" role="alert">{paramErr}</p>}
            </div>)}
          {step === 3 && (
            <div className="space-y-3">
              <h2 className="h-section">Run selection</h2>
              <p className="text-sm text-muted">Strategy <b className="text-ink">{form.strategy}</b> · budget {form.budget} · seed {form.seed}. The result and its configuration are stored so the round can be reproduced.</p>
              <button className="btn-primary" disabled={sel.busy || !!paramErr || poolN === 0} onClick={run}>{sel.busy ? "Selecting…" : "Run selection"}</button>
              {sel.error && <ErrorState error={sel.error} compact />}
            </div>)}
          {step === 4 && (!result ? <EmptyState title="Nothing selected yet" message="Run a selection first." /> : (
            <div className="space-y-3">
              <h2 className="h-section">Selected images ({result.selected.length})</h2>
              {result.warning && <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm text-violet-800">{result.warning}</div>}
              {!result.uncertainty_signals_available && form.strategy !== "random" && <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">No model uncertainty signals exist yet, so the ranking could not use them. See the notes below.</div>}
              {ARRAY(result.notes).length > 0 && <ul className="list-disc pl-5 text-sm text-slate-700">{result.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
              <div className="overflow-x-auto"><table className="w-full"><thead><tr>{["#", "Image", "Score", "Reason", "Quality"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
                <tbody>{result.selected.map((s, i) => <tr key={s.image_id}><td className="td">{i + 1}</td><td className="td font-mono text-xs">{s.image_id}</td><td className="td">{fmt(s.score)}</td><td className="td text-xs">{s.reason}</td>
                  <td className="td">{ARRAY(s.quality_flags).map((f) => <StatusBadge key={f} tone="warn">{f.replace(/_/g, " ")}</StatusBadge>)}</td></tr>)}</tbody></table></div>
            </div>))}
          {step === 5 && (!result ? <EmptyState title="Nothing to export" message="Run a selection first." /> : (
            <div className="space-y-3">
              <h2 className="h-section">Export to annotation</h2>
              <p className="text-sm text-muted">Creates a Label Studio task manifest. No model pre-annotations are attached unless a dental model produced them.</p>
              <div className="flex flex-wrap gap-2">
                <button className="btn-teal" disabled={exp.busy} onClick={() => doExport(false)}><Download className="h-4 w-4" aria-hidden />Download task manifest</button>
                <button className="btn-ghost" disabled={exp.busy} onClick={() => doExport(true)}><Send className="h-4 w-4" aria-hidden />Push to Label Studio</button>
              </div>
              {exp.error && <ErrorState error={exp.error} compact />}
              {exp.result && <p className="text-sm text-ok" role="status">Batch <span className="font-mono">{exp.result.batch_id}</span> recorded ({exp.result.n_tasks} tasks){exp.result.pushed?.url ? ` · ${exp.result.pushed.url}` : ""}.</p>}
            </div>))}
          <div className="mt-6 flex justify-between">
            <button className="btn-ghost" disabled={step === 0} title={step === 0 ? "You are on the first step" : ""} onClick={() => setStep(step - 1)}><ArrowLeft className="h-4 w-4" aria-hidden />Back</button>
            {step < 3 && <button className="btn-primary" disabled={step === 2 && !!paramErr} onClick={() => setStep(step + 1)}>Next<ArrowRight className="h-4 w-4" aria-hidden /></button>}
            {step === 4 && <button className="btn-primary" onClick={() => setStep(5)}>Export<ArrowRight className="h-4 w-4" aria-hidden /></button>}
          </div>
        </section>
        <aside className="card card-pad h-fit" aria-label="Round history">
          <h2 className="h-section mb-2">Round history</h2>
          {rounds.loading ? <LoadingState inline /> : rounds.error ? <ErrorState error={rounds.error} compact onRetry={rounds.reload} /> : rounds.data.length === 0 ? <p className="text-sm text-muted">No rounds recorded.</p> : (
            <ul className="divide-y divide-slate-100">{rounds.data.map((r) => (
              <li key={r.id} className="py-2 text-sm"><div className="flex items-center justify-between"><span className="font-mono text-xs">{r.id}</span>{r.is_test_data && <StatusBadge status="test_data">TEST</StatusBadge>}</div>
                <div className="text-xs text-muted">{r.strategy} · {r.n_selected}/{r.budget} · seed {r.seed}</div><div className="text-xs text-muted">{when(r.created)}</div></li>))}</ul>)}
        </aside>
      </div>
    </div>
  );
}
