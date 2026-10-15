import React from "react";
import { RefreshCw } from "lucide-react";
import PageHeader from "../components/PageHeader";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { ARRAY, when } from "../lib/format";
import { usePrefs } from "../lib/prefs";

const SEV = { warning: "warn", info: "info", error: "bad" };

export default function SettingsPage() {
  const s = useApi(() => api.settings(), []);
  const h = useApi(() => api.health(true), [], { pollMs: 20000 });
  const ds = useApi(() => api.datasetStatus(), [], { pollMs: 10000 });
  const val = useApi(() => api.datasetValidation(), []);
  const proc = useAction(() => api.datasetProcess(true));
  const reprocess = async () => { if (await proc.run()) { ds.reload(true); val.reload(true); } };
  const d = ds.data;
  const [prefs, setPrefs] = usePrefs();

  return (
    <div>
      <PageHeader title="Settings" subtitle="Display preferences and read-only system diagnostics. Secrets are never displayed; server configuration is changed in .env."
        actions={<button className="btn-ghost" onClick={() => { s.reload(); h.reload(); ds.reload(); val.reload(); }}><RefreshCw className="h-4 w-4" aria-hidden />Refresh</button>} />
      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3 xl:items-start">
      <section className="card card-pad lg:col-span-2 xl:col-span-1" aria-label="Display preferences" data-testid="prefs">
        <h2 className="h-section mb-3">Display preferences</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
          <div><label className="label" htmlFor="pl">Default report language</label>
            <select id="pl" className="input" value={prefs.reportLang} onChange={(e) => setPrefs({ reportLang: e.target.value })}>
              <option value="en">English</option><option value="hi">हिन्दी (awaiting linguistic review)</option><option value="mr">मराठी (awaiting linguistic review)</option></select>
            <p className="mt-1 text-xs text-muted">Used when a report is opened. You can still switch language on the report page.</p></div>
          <div><span className="label">On the X-ray</span>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={prefs.showIds} onChange={(e) => setPrefs({ showIds: e.target.checked })} /> Show tooth numbers / region labels</label>
            <label className="mt-1 flex items-center gap-2 text-sm"><input type="checkbox" checked={prefs.showClasses} onChange={(e) => setPrefs({ showClasses: e.target.checked })} /> Show candidate classes</label>
            <label className="mt-1 flex items-center gap-2 text-sm"><input type="checkbox" checked={prefs.showMasks} onChange={(e) => setPrefs({ showMasks: e.target.checked })} /> Show segmentation masks</label></div>
        </div>
        <div className="mt-4 border-t border-slate-100 pt-4">
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" data-testid="show-research" checked={prefs.showResearch} onChange={(e) => setPrefs({ showResearch: e.target.checked })} />
            <span><b>Show Research / Developer Tools</b> in the sidebar (segmentation, uncertainty research, active learning, annotations, training, experiments, model registry).
              <span className="block text-xs text-muted">These pages are for model development and project evaluation. They are not password-protected: the API token protects the server, and this setting only hides or shows the links in this browser.</span></span></label>
        </div>
      </section>

        <section className="card card-pad" aria-label="Dataset">
          <div className="mb-2 flex items-center justify-between"><h2 className="h-section">Dataset status</h2>
            <button className="btn-ghost !py-1" disabled={proc.busy || !d || d.state === "missing"} onClick={reprocess}>{proc.busy ? "Processing…" : "Re-process dataset"}</button></div>
          {ds.loading ? <LoadingState inline /> : ds.error ? <ErrorState error={ds.error} compact onRetry={ds.reload} /> : (<>
            <p className="flex items-center gap-2 text-sm">{d.state === "main_available" ? <StatusBadge tone="ok">main dataset available</StatusBadge> : d.state === "test_data_only" ? <StatusBadge status="test_data">test data only</StatusBadge> : <StatusBadge tone="bad">no data found</StatusBadge>}</p>
            {ARRAY(d.messages).map((m, i) => <p key={i} className="mt-2 text-sm">{m}</p>)}
            <dl className="mt-3 grid grid-cols-2 gap-y-1 text-sm"><dt className="text-muted">Data folder</dt><dd className="text-right font-mono text-xs">{d.data_root}</dd>
              <dt className="text-muted">Main images</dt><dd className="text-right">{d.main_image_count}</dd><dt className="text-muted">Test-data images</dt><dd className="text-right">{d.test_image_count}</dd>
              <dt className="text-muted">Last processed</dt><dd className="text-right text-xs">{when(d.last_processed?.processed_at || d.last_processed?.created)}</dd></dl>
            {!d.main_available && <p className="mt-3 rounded-lg bg-slate-50 p-2 text-xs text-muted">Expected location: <span className="font-mono">{d.expected_location}</span>. It is detected and processed automatically when it appears.</p>}
            {proc.error && <div className="mt-2"><ErrorState error={proc.error} compact /></div>}</>)}
          {val.data && val.data.counts && Object.keys(val.data.counts).length > 0 && (
            <div className="mt-4"><h3 className="h-section mb-1">Validation</h3>
              <ul className="text-sm">{Object.entries(val.data.counts).map(([k, v]) => <li key={k} className="flex justify-between border-b border-slate-100 py-1"><span>{k.replace(/_/g, " ")}</span><b>{typeof v === "object" ? JSON.stringify(v) : v}</b></li>)}</ul></div>)}
        </section>

        <section className="card card-pad" aria-label="Services">
          <h2 className="h-section mb-2">Services</h2>
          {h.loading ? <LoadingState inline /> : h.error ? <ErrorState error={h.error} compact onRetry={h.reload} /> : (
            <ul className="divide-y divide-slate-100 text-sm">
              <li className="flex justify-between py-2"><span>Backend</span><StatusBadge status="ok">v{h.data.version}</StatusBadge></li>
              <li className="flex justify-between py-2"><span>Database</span><StatusBadge status={h.data.database} /></li>
              <li className="flex justify-between py-2"><span>GPU</span>{h.data.gpu?.cuda_available ? <StatusBadge tone="ok">{h.data.gpu.name || "CUDA"}</StatusBadge> : <StatusBadge tone="neutral">CPU only</StatusBadge>}</li>
              <li className="flex justify-between py-2"><span>Model checkpoints</span><b>{h.data.checkpoints_loaded}</b></li>
              <li className="flex justify-between py-2"><span>Label Studio</span>{h.data.label_studio?.reachable ? <StatusBadge status="reachable" /> : <StatusBadge status="unreachable" />}</li>
              <li className="flex justify-between py-2"><span>TensorBoard</span>{h.data.tensorboard?.reachable ? <StatusBadge status="reachable" /> : <StatusBadge status="unreachable" />}</li>
              <li className="flex justify-between py-2"><span>Report generation</span><StatusBadge tone={h.data.llm?.configured ? "ok" : "neutral"}>{h.data.llm?.mode === "llm" ? "LLM (validated)" : "deterministic template"}</StatusBadge></li>
            </ul>)}
        </section>

        <section className="card card-pad lg:col-span-2 xl:col-span-3" aria-label="Diagnostics">
          <h2 className="h-section mb-2">Diagnostics</h2>
          {s.loading ? <LoadingState inline /> : s.error ? <ErrorState error={s.error} compact onRetry={s.reload} /> : (<>
            {s.data.diagnostics.length === 0 ? <StatusBadge tone="ok">no issues detected</StatusBadge> : (
              <ul className="space-y-2">{s.data.diagnostics.map((x, i) => <li key={i} className="text-sm"><StatusBadge tone={SEV[x.severity] || "neutral"}>{x.severity}</StatusBadge> <span className="ml-1">{x.message}</span><span className="block pl-1 text-xs text-muted">Fix: {x.fix}</span></li>)}</ul>)}
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <div><h3 className="h-section mb-1">Configuration</h3><dl className="grid grid-cols-2 gap-y-1 text-sm">
                {Object.entries(s.data.settings).map(([k, v]) => <React.Fragment key={k}><dt className="text-muted">{k.replace(/_/g, " ")}</dt><dd className="break-all text-right font-mono text-xs">{String(v)}</dd></React.Fragment>)}</dl></div>
              <div><h3 className="h-section mb-1">Environment</h3><p className="text-xs text-muted">Python {s.data.environment.python} · {s.data.environment.platform}</p>
                <ul className="mt-1 grid grid-cols-2 gap-x-4 text-sm">{Object.entries(s.data.environment.packages).map(([k, v]) => <li key={k} className="flex justify-between"><span>{k}</span><span className={v ? "font-mono text-xs" : "text-muted"}>{v || "not installed"}</span></li>)}</ul></div>
            </div></>)}
        </section>
      </div>
    </div>
  );
}
