import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, ClipboardCheck, FileText, Hash, Layers, ScanSearch, Tags } from "lucide-react";
import StatusBadge from "../components/StatusBadge";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import { modelAvailability } from "../components/ModelStatusPanel";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { when } from "../lib/format";
import { reviewStatus } from "../lib/reportStatus";

// What each model does (plain description only; availability comes from the backend, never from here).
const CAPABILITY = {
  detection: { icon: ScanSearch, title: "Tooth detection", text: "Finds each tooth on the panoramic X-ray and draws a box around it." },
  segmentation: { icon: Layers, title: "Tooth segmentation", text: "Outlines the shape of every detected tooth." },
  classification: { icon: Tags, title: "Candidate finding classification", text: "Names the closest of four trained findings for each tooth. A candidate, not a diagnosis." },
  numbering: { icon: Hash, title: "FDI tooth numbering", text: "Suggests a tooth number (11–48); uncertain numbers are marked for checking." },
};

export default function Overview() {
  const nav = useNavigate();
  const ov = useApi(() => api.overview(), [], { pollMs: 30000 });
  const reports = useApi(() => api.reports(), []);
  const queue = useApi(() => api.reviewsQueue(), []);
  if (ov.loading && !ov.data) return <LoadingState label="Loading…" />;
  if (ov.error && !ov.data) return <ErrorState error={ov.error} onRetry={ov.reload} />;
  const o = ov.data;
  const avail = modelAvailability(o.models);
  const latest = reports.data?.[0];
  const recent = o.recent_activity.slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Introduction */}
      <section className="card overflow-hidden" aria-labelledby="home-title">
        <div className="border-l-4 border-teal p-5 sm:p-7">
          <div className="min-w-0">
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-teal">DentaMind AI · research prototype</p>
            <h1 id="home-title" className="text-[1.75rem] font-bold leading-tight tracking-tight text-navy sm:text-[2.1rem]">AI-Assisted Dental X-ray Review</h1>
            <p className="mt-2 max-w-2xl text-base leading-relaxed text-slate-600">Analyze panoramic dental X-rays, inspect detected teeth and candidate findings, and prepare structured reports for human review.</p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button className="btn-primary btn-lg" onClick={() => nav("/analysis")} data-testid="upload-cta"><ScanSearch className="h-5 w-5" aria-hidden />Start X-ray Analysis</button>
            </div>
          </div>
        </div>
      </section>

      {/* What the models do + live availability */}
      <section aria-labelledby="caps">
        <h2 id="caps" className="h-section mb-3">What DentaMind does</h2>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="model-status">
          {avail.map(({ task, ok, problem }) => {
            const c = CAPABILITY[task];
            const Icon = c.icon;
            return (
              <li key={task} className="card card-pad flex flex-col gap-2" data-task={task}>
                <div className="flex items-start justify-between gap-2">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50 text-teal"><Icon className="h-5 w-5" aria-hidden /></span>
                  {ok ? <StatusBadge tone="ok">Available</StatusBadge> : <StatusBadge tone="warn">Unavailable</StatusBadge>}
                </div>
                <h3 className="font-semibold text-navy">{c.title}</h3>
                <p className="text-sm leading-relaxed text-slate-600">{c.text}</p>
                {!ok && problem && <p className="text-[11px] text-muted">{problem}</p>}
              </li>);
          })}
        </ul>
      </section>

      {/* Activity */}
      <section className="grid gap-4 lg:grid-cols-3" aria-label="Activity">
        <div className="card card-pad flex flex-col" aria-labelledby="recent">
          <div className="card-head"><h2 id="recent" className="h-section">Recent analyses</h2>{recent.length > 0 && <span className="text-xs text-muted">{o.recent_activity.length}</span>}</div>
          {recent.length === 0 ? (
            <div className="flex flex-1 flex-col justify-between gap-3">
              <p className="text-sm text-muted">No analyses yet. Choose or upload an X-ray to run the models.</p>
              <Link to="/analysis" className="btn-ghost self-start">Open X-ray Analysis<ArrowRight className="h-4 w-4" aria-hidden /></Link>
            </div>) : (
            <ul className="divide-y divide-slate-100">{recent.map((a, i) => (
              <li key={i} className="flex items-center gap-3 py-2 text-sm">
                <img src={a.thumbnail_url} alt="" className="h-9 w-14 rounded bg-slate-200 object-cover" loading="lazy" />
                <span className="min-w-0 flex-1 truncate font-mono text-xs">{a.image_id}</span>
                <span className="whitespace-nowrap text-xs text-muted">{when(a.created)}</span>
              </li>))}</ul>)}
        </div>

        <div className="card card-pad flex flex-col" aria-labelledby="latest">
          <div className="card-head"><h2 id="latest" className="h-section">Latest report</h2></div>
          {!latest ? <p className="text-sm text-muted">No reports yet. Analyze an X-ray, then choose “Generate report”.</p> : (
            <div className="flex flex-1 flex-col justify-between gap-3 text-sm">
              <div>
                <p className="font-mono text-xs">{latest.id}</p>
                <p className="mt-0.5 truncate text-sm text-slate-700" title={latest.image_name || latest.image_id}>{latest.image_name || latest.image_id}</p>
                <p className="mt-2 flex flex-wrap items-center gap-2"><StatusBadge tone={reviewStatus(latest.status).tone}>{reviewStatus(latest.status).label}</StatusBadge><span className="text-xs text-muted">{when(latest.created)}</span></p>
              </div>
              <Link to={"/reports?id=" + latest.id} className="btn-ghost self-start"><FileText className="h-4 w-4" aria-hidden />Open report</Link>
            </div>)}
        </div>

        <div className="card card-pad flex flex-col" aria-labelledby="pending">
          <div className="card-head"><h2 id="pending" className="h-section">Findings awaiting review</h2></div>
          <div className="flex flex-1 flex-col justify-between gap-3">
            {queue.data ? <p className="text-sm text-slate-700"><b className="mr-1 text-3xl font-bold text-navy" data-testid="pending-count">{queue.data.total}</b> image(s) have regions that need a person to look at them.</p> : <p className="text-sm text-muted">Loading…</p>}
            <Link to="/review" className="btn-ghost self-start"><ClipboardCheck className="h-4 w-4" aria-hidden />Review findings</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
