import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Calculator } from "lucide-react";
import PageHeader from "../components/PageHeader";
import UncertaintyScoreCard from "../components/UncertaintyScoreCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { useAppState } from "../hooks/AppState";
import { api } from "../services/api";
import { FLAG_TEXT } from "../lib/fullAnalysis";
import { fmt } from "../lib/format";

const COLS = [["entropy", "Entropy"], ["disagreement", "Flip disagreement"], ["mask_instability", "Mask instability"], ["detection_instability", "Detection instability"], ["combined_score", "Combined"]];

export default function Uncertainty() {
  const nav = useNavigate();
  const { setImageId } = useAppState();
  const t = useApi(() => api.uncertaintyTable(), []);
  const imgs = useApi(() => api.images({ source: "all", limit: 300 }), []);
  const [sortKey, setSortKey] = useState("combined_score");
  const [flagFilter, setFlagFilter] = useState("all");
  const [onlyComputed, setOnlyComputed] = useState(true);
  const [sel, setSel] = useState(null);
  const [pick, setPick] = useState("");
  const calc = useAction((id) => api.uncertaintyImage(id));
  const rows = t.data?.items || [];
  const flags = useMemo(() => [...new Set(rows.flatMap((r) => r.quality_flags || []))], [rows]);
  const shown = useMemo(() => rows.filter((r) => (!onlyComputed || r.computed) && (flagFilter === "all" || (r.quality_flags || []).includes(flagFilter)))
    .sort((a, b) => (b[sortKey] ?? -1) - (a[sortKey] ?? -1)), [rows, sortKey, flagFilter, onlyComputed]);
  const computed = rows.filter((r) => r.combined_score != null);
  const hist = useMemo(() => {
    const bins = Array.from({ length: 10 }, (_, i) => ({ bin: `${(i / 10).toFixed(1)}–${((i + 1) / 10).toFixed(1)}`, count: 0 }));
    computed.forEach((r) => { bins[Math.min(9, Math.floor(r.combined_score * 10))].count += 1; });
    return bins;
  }, [computed]);
  const selected = rows.find((r) => r.id === sel);
  const detail = useApi(() => (selected?.analysis_id ? api.analysis(selected.analysis_id) : Promise.resolve(null)), [selected?.analysis_id]);
  const asRecord = selected && {
    combined_score: selected.combined_score, quality_flags: selected.quality_flags, quality_metrics: selected.quality_metrics, thresholds: selected.thresholds,
    signal_validation: detail.data?.signal_validation || detail.data?.uncertainty?.signal_validation,
    ...Object.fromEntries(["entropy", "disagreement", "mask_instability", "detection_instability"].map((k) => [k, selected[k] != null
      ? { status: "computed", value: selected[k] } : { status: "unavailable", reason: selected.unavailable_reasons?.[k] || selected.unavailable_reasons?.all || "not computed" }])),
  };

  async function compute() {
    const r = await calc.run(pick);
    if (r) { await t.reload(true); setSel(pick); }
  }
  const openAnalysis = (id) => { setImageId(id); nav("/analysis"); };

  return (
    <div>
      <PageHeader title="Uncertainty" subtitle="How unsure are the models? Predictive uncertainty (model doubt) and image-quality warnings are separate things. Every value here was computed from real model passes and saved." />
      <div className="card card-pad mb-5">
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[14rem] flex-1 text-xs text-muted">Calculate for an image (runs detector, numbering, segmenter and classifier, plus flipped passes; ~10 s)
            <select className="input mt-1" aria-label="Image to score" value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">Select an image…</option>
              {(imgs.data?.items || []).map((i) => <option key={i.id} value={i.id}>{i.filename}{i.is_test_data ? " (test data)" : ""}{i.duplicate_split ? ` - same film as ${i.duplicate_split}-split ${i.duplicate_of}` : ""}</option>)}
            </select></label>
          <button className="btn-primary" disabled={!pick || calc.busy} onClick={compute} data-testid="unc-compute"><Calculator className="h-4 w-4" aria-hidden />{calc.busy ? "Computing…" : "Calculate uncertainty"}</button>
        </div>
        {calc.error && <div className="mt-3"><ErrorState error={calc.error} compact /></div>}
        <p className="mt-2 text-xs text-muted">Flip disagreement and instability use test-time augmentation (horizontal flip) of a single network — they are not an ensemble. Thresholds for “needs review” come from the calibration split and are provisional (see Data/reports/uncertainty_evaluation.md).</p>
      </div>
      {t.loading ? <LoadingState /> : t.error ? <ErrorState error={t.error} onRetry={t.reload} /> : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0 space-y-5">
            <div className="card card-pad">
              <h2 className="h-section mb-2">Distribution of combined uncertainty <span className="font-normal text-muted">({computed.length} image(s) computed)</span></h2>
              {computed.length === 0 ? <EmptyState title="No uncertainty computed yet" message="Choose an image above and press Calculate uncertainty, or use Analyze Image on the X-ray Analysis page." /> : (
                <div style={{ height: 200 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={hist}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="bin" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="count" fill="#0F8B8D" /></BarChart></ResponsiveContainer></div>)}
            </div>
            <div className="card">
              <div className="flex flex-wrap items-center gap-3 p-4">
                <h2 className="h-section">Images</h2>
                <label className="text-xs text-muted">Sort by <select className="input !inline-block !w-auto !py-1" value={sortKey} onChange={(e) => setSortKey(e.target.value)}>{COLS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
                <label className="text-xs text-muted">Quality flag <select className="input !inline-block !w-auto !py-1" value={flagFilter} onChange={(e) => setFlagFilter(e.target.value)}><option value="all">all</option>{flags.map((f) => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}</select></label>
                <label className="flex items-center gap-1.5 text-xs text-muted"><input type="checkbox" checked={onlyComputed} onChange={(e) => setOnlyComputed(e.target.checked)} />only computed</label>
              </div>
              {shown.length === 0 ? <div className="p-4"><EmptyState title="Nothing to show" message={onlyComputed ? "No image has saved uncertainty yet." : "No images match."} /></div> : (
                <div className="overflow-x-auto"><table className="w-full" data-testid="unc-table">
                  <thead><tr><th className="th">Image</th>{COLS.map(([, l]) => <th key={l} className="th">{l}</th>)}<th className="th">Quality warnings</th></tr></thead>
                  <tbody>{shown.map((r) => (
                    <tr key={r.id} className={`cursor-pointer hover:bg-slate-50 ${sel === r.id ? "bg-teal-50" : ""}`} onClick={() => setSel(r.id)}>
                      <td className="td"><span className="flex items-center gap-2">{r.thumbnail_url && <img src={r.thumbnail_url} alt="" className="h-8 w-14 rounded bg-slate-200 object-cover" loading="lazy" />}{r.filename}{r.is_test_data && <StatusBadge status="test_data">TEST DATA</StatusBadge>}</span></td>
                      {COLS.map(([k]) => <td key={k} className="td">{r[k] != null ? fmt(r[k]) : <span className="text-xs text-muted" title={r.unavailable_reasons?.[k] || r.unavailable_reasons?.all}>{r.computed ? "unavailable" : "not computed"}</span>}</td>)}
                      <td className="td">{(r.quality_flags || []).length ? r.quality_flags.map((f) => <StatusBadge key={f} tone="warn">{f.replace(/_/g, " ")}</StatusBadge>) : <span className="text-xs text-muted">none</span>}</td>
                    </tr>))}</tbody>
                </table></div>)}
            </div>
          </div>
          <aside className="card card-pad h-fit" aria-label="Selected image">
            <h2 className="h-section mb-3">Selected image</h2>
            {selected ? (
              <>
                <p className="mb-1 text-sm font-medium">{selected.filename}</p>
                <div className="mb-3 flex gap-2">
                  {selected.url && <a className="btn-ghost !py-1 text-xs" href={selected.url} target="_blank" rel="noreferrer">Original image</a>}
                  <button className="btn-ghost !py-1 text-xs" onClick={() => openAnalysis(selected.id)}>Open analysis</button>
                </div>
                {selected.computed ? <UncertaintyScoreCard record={asRecord} /> : <p className="text-sm text-muted">Not computed yet — use the control above.</p>}
                {detail.data?.regions && (
                  <div className="mt-4">
                    <h3 className="h-section mb-1">Regions needing review ({detail.data.regions.filter((g) => g.review_required).length}/{detail.data.regions.length})</h3>
                    <ul className="max-h-56 space-y-1 overflow-auto text-xs">
                      {detail.data.regions.filter((g) => g.review_required).map((g) => (
                        <li key={g.region_id} className="rounded border border-slate-200 p-1.5"><b>#{g.region_no}</b> {g.fdi ? `tooth ${g.fdi}` : "unnumbered"} — {g.flags.map((f) => FLAG_TEXT[f] || f).join(", ")}</li>))}
                    </ul>
                  </div>)}
              </>
            ) : <p className="text-sm text-muted">Select a row to see its signals, reasons for any unavailable value, and the regions that need review.</p>}
          </aside>
        </div>)}
    </div>
  );
}
