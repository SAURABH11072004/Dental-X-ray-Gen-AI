import React, { useMemo, useState } from "react";
import { Download } from "lucide-react";
import PageHeader from "../components/PageHeader";
import ExperimentComparisonChart from "../components/ExperimentComparisonChart";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useApi } from "../hooks/useApi";
import { api, experimentsExportUrl } from "../services/api";
import { fmt, when } from "../lib/format";

const METRICS = [["detection_map", "Detection mAP"], ["detection_ap50", "Detection AP50"], ["classification_macro_f1", "Classification macro-F1"], ["mask_ap", "Mask AP"], ["calibration_ece", "Calibration ECE (lower is better)"]];

export default function Experiments() {
  const exps = useApi(() => api.experiments(), []);
  const series = useApi(() => api.experimentSeries(), []);
  const [picked, setPicked] = useState([]);
  const [metric, setMetric] = useState("classification_macro_f1");
  const cmp = useApi(() => (picked.length >= 2 ? api.experimentCompare(picked) : Promise.resolve(null)), [picked.join(",")]);
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  const chartSeries = useMemo(() => series.data?.[metric] || {}, [series.data, metric]);
  const rows = exps.data || [];

  return (
    <div>
      <PageHeader title="Experiment Comparison" subtitle="Real recorded runs only. Different dataset versions, seeds or budgets are flagged before you compare."
        actions={<><a className="btn-ghost" href={experimentsExportUrl("csv")}><Download className="h-4 w-4" aria-hidden />CSV</a><a className="btn-ghost" href={experimentsExportUrl("json")}><Download className="h-4 w-4" aria-hidden />JSON</a></>} />
      {exps.loading ? <LoadingState /> : exps.error ? <ErrorState error={exps.error} onRetry={exps.reload} /> : (
        <div className="space-y-5">
          <div className="card card-pad">
            <div className="mb-3 flex items-center gap-3"><h2 className="h-section">Performance vs annotation budget</h2>
              <select className="input !w-auto" aria-label="Metric" value={metric} onChange={(e) => setMetric(e.target.value)}>{METRICS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
            {series.error ? <ErrorState error={series.error} compact /> : <ExperimentComparisonChart series={chartSeries} yLabel={METRICS.find((m) => m[0] === metric)[1]} />}
            <p className="mt-2 text-xs text-muted">Records marked TEST DATA are excluded from this chart.</p>
          </div>
          <div className="card">
            {rows.length === 0 ? <div className="p-4"><EmptyState title="No experiments recorded" message="Experiments are recorded by training and evaluation runs on the main dataset." to="/training" actionLabel="Open Model Training" /></div> : (
              <div className="overflow-x-auto"><table className="w-full">
                <thead><tr>{["", "Experiment", "Strategy", "Budget", "Round", "Seed", "Status", "mAP", "Macro-F1", "ECE", "Created"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
                <tbody>{rows.map((e) => (
                  <tr key={e.id}><td className="td"><input type="checkbox" aria-label={`Compare ${e.id}`} checked={picked.includes(e.id)} onChange={() => toggle(e.id)} /></td>
                    <td className="td font-mono text-xs">{e.id}{e.is_test_data && <> <StatusBadge status="test_data">TEST DATA</StatusBadge></>}</td><td className="td">{e.strategy || "—"}</td><td className="td">{e.budget ?? "—"}</td><td className="td">{e.round ?? "—"}</td>
                    <td className="td">{e.seed ?? "—"}</td><td className="td"><StatusBadge status={e.status} /></td><td className="td">{fmt(e.metrics.detection_map)}</td><td className="td">{fmt(e.metrics.classification_macro_f1)}</td><td className="td">{fmt(e.metrics.calibration_ece)}</td><td className="td text-xs">{when(e.created)}</td></tr>))}</tbody></table></div>)}
          </div>
          {picked.length >= 2 && (
            <div className="card card-pad" aria-label="Comparison">
              <h2 className="h-section mb-2">Comparison of {picked.length} runs</h2>
              {cmp.loading ? <LoadingState inline /> : cmp.error ? <ErrorState error={cmp.error} compact /> : cmp.data && (<>
                {cmp.data.warnings.map((w, i) => <p key={i} className="mb-1 rounded-lg bg-amber-50 p-2 text-sm text-amber-900" role="alert">{w}</p>)}
                {cmp.data.comparable_metrics.length === 0 ? <p className="text-sm text-muted">These runs share no metric, so no side-by-side values can be shown.</p> : (
                  <table className="w-full"><thead><tr><th className="th">Metric</th>{cmp.data.experiments.map((e) => <th key={e.id} className="th font-mono">{e.id}</th>)}</tr></thead>
                    <tbody>{cmp.data.comparable_metrics.map((m) => <tr key={m}><td className="td">{m.replace(/_/g, " ")}</td>{cmp.data.experiments.map((e) => <td key={e.id} className="td">{fmt(e.metrics[m])}</td>)}</tr>)}</tbody></table>)}</>)}
            </div>)}
        </div>)}
    </div>
  );
}
