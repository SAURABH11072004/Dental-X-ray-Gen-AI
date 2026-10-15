import React, { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CheckCircle2, Download, FileText, ShieldCheck } from "lucide-react";
import PageHeader from "../components/PageHeader";
import ReportPreview from "../components/ReportPreview";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { api, reportExportUrl } from "../services/api";
import { when } from "../lib/format";
import { usePrefs } from "../lib/prefs";
import { reviewStatus } from "../lib/reportStatus";

const PAGE = 8;
const LANG_NAME = { en: "English", hi: "हिन्दी", mr: "मराठी" };
const FORMATS = [["html", "HTML", "Web page, opens in any browser"], ["txt", "TXT", "Plain text"], ["json", "JSON", "Structured data for other software"]];

export default function Reports() {
  const [params, setParams] = useSearchParams();
  const id = params.get("id");
  const list = useApi(() => api.reports(), []);
  const [prefs, setPrefs] = usePrefs();
  const lang = prefs.reportLang;
  const [shown, setShown] = useState(PAGE);
  const rep = useApi(() => (id ? api.report(id, lang) : Promise.resolve(null)), [id, lang]);
  const val = useAction((rid) => api.reportValidate(rid));
  const rev = useAction((rid, who) => api.reportReview(rid, who));
  const [reviewer, setReviewer] = useState("");
  const [done, setDone] = useState(null);
  const data = rep.data;
  const validation = val.result || data?.validation;
  const rows = list.data || [];
  const current = rows.find((r) => r.id === id);
  const langs = data?.languages || LANG_NAME;
  const nameOk = reviewer.trim().length >= 2;
  const invalid = validation?.passed === false;
  const already = data?.report?.status === "reviewed_research_draft";

  const visible = useMemo(() => rows.slice(0, shown), [rows, shown]);
  const open = (rid) => { setDone(null); setParams({ id: rid }); };
  async function sign() {
    if (rev.busy) return;                       // one request per click
    if (await rev.run(id, reviewer.trim())) { setDone(`Saved: reviewed by ${reviewer.trim()}.`); rep.reload(true); list.reload(true); }
  }

  return (
    <div>
      <PageHeader title="Reports" subtitle="Draft reports are built only from the structured model results of an analysis. They stay research output until a named person has reviewed them." />
      <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)] lg:items-start xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="card card-pad lg:sticky lg:top-0" aria-label="Report list">
          <div className="card-head !mb-2"><h2 className="h-section">Saved reports</h2><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">{rows.length}</span></div>
          {list.loading ? <LoadingState inline /> : list.error ? <ErrorState error={list.error} compact onRetry={list.reload} /> : rows.length === 0 ? (
            <p className="text-sm text-muted" data-testid="no-reports">No reports yet. Analyze an X-ray, then choose “Generate report”.</p>) : (
            <>
              <ul className="max-h-[62vh] space-y-1.5 overflow-y-auto pr-0.5" data-testid="report-list">{visible.map((r) => {
                const st = reviewStatus(r.status);
                return (
                  <li key={r.id}>
                    <div className={`rounded-lg border px-2.5 py-2 text-sm ${r.id === id ? "border-teal bg-teal-50" : "border-slate-200 bg-white"}`}>
                      <div className="flex items-center justify-between gap-2"><span className="truncate font-mono text-xs">{r.id}</span><StatusBadge tone={st.tone}>{st.label}</StatusBadge></div>
                      <p className="mt-1 truncate text-xs text-slate-700" title={r.image_name || r.image_id}>{r.image_name || r.image_id}</p>
                      <div className="mt-1 flex items-center justify-between gap-2 text-[11px] text-slate-600"><span>{when(r.created)}</span><span title="Languages this report can be viewed in">EN · HI · MR</span></div>
                      <button className="btn-ghost mt-2 w-full !py-1 text-xs" aria-current={r.id === id ? "true" : undefined} aria-label={`Open report ${r.id}`} onClick={() => open(r.id)}><FileText className="h-3.5 w-3.5" aria-hidden />{r.id === id ? "Open (viewing)" : "Open"}</button>
                    </div>
                  </li>);
              })}</ul>
              {rows.length > shown && <button className="btn-ghost mt-2 w-full !py-1 text-xs" onClick={() => setShown(shown + PAGE)}>Show more ({rows.length - shown} more)</button>}
            </>)}
        </aside>

        <section className="card card-pad min-w-0" aria-label="Report">
          {!id ? <EmptyState compact icon={FileText} title="No report selected" message="Open a saved report from the list, or analyze an X-ray and choose “Generate report”." to="/analysis" actionLabel="Open X-ray Analysis" />
            : rep.error ? <ErrorState error={rep.error} onRetry={rep.reload} /> : (rep.loading || !data) ? <LoadingState /> : (
              <div className="space-y-5">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-slate-100 pb-3">
                  {current && <div className="mr-auto flex min-w-0 flex-wrap items-center gap-2"><span className="font-mono text-sm font-semibold text-navy">{current.id}</span><span className="truncate text-sm text-slate-600" title={current.image_name || current.image_id}>{current.image_name || current.image_id}</span><StatusBadge tone={reviewStatus(current.status).tone}>{reviewStatus(current.status).label}</StatusBadge></div>}
                  <label className="flex items-center gap-2 text-sm"><span className="text-muted">Language</span>
                    <select className="input !w-auto !py-1.5" aria-label="Report language" value={lang} onChange={(e) => setPrefs({ reportLang: e.target.value })}>
                      {Object.entries(langs).map(([k, v]) => <option key={k} value={k}>{v}{k !== "en" ? " — translation awaiting review" : ""}</option>)}
                    </select></label>
                  <span className="w-full text-xs text-muted lg:w-auto">Same findings and values in every language.</span>
                </div>

                <ReportPreview report={data.report} localized={data.localized} check={data.localization_check} imageName={current?.image_name} validation={validation}
                  techExtra={<button className="btn-ghost !py-1 text-xs" disabled={val.busy} onClick={() => val.run(id)}><ShieldCheck className="h-3.5 w-3.5" aria-hidden />{val.busy ? "Validating…" : "Re-validate report"}</button>} />

                <section aria-label="Review and export" className="grid gap-4 border-t border-slate-100 pt-4 lg:grid-cols-2">
                  <div data-testid="review-box">
                    <h3 className="h-section mb-1.5">Record a review</h3>
                    {already
                      ? <p className="text-sm" role="status"><StatusBadge tone="ok">Reviewed</StatusBadge> by <b>{data.report.reviewed_by}</b>. This status is saved with the report.</p>
                      : (
                        <>
                          <label className="label" htmlFor="rvname">Reviewer name</label>
                          <div className="flex flex-wrap gap-2">
                            <input id="rvname" className="input !w-56" placeholder="Your name" value={reviewer} onChange={(e) => { setReviewer(e.target.value); setDone(null); }} aria-describedby="rvhelp" />
                            <button className="btn-teal" disabled={!nameOk || rev.busy || invalid} onClick={sign}><CheckCircle2 className="h-4 w-4" aria-hidden />{rev.busy ? "Saving…" : "Mark reviewed"}</button>
                          </div>
                          <p id="rvhelp" className="mt-1 text-xs text-muted">{invalid ? "This report failed validation and cannot be signed off." : !nameOk ? "Type at least two characters to enable the button. " : ""}The name is typed in and is not identity-verified.</p>
                        </>)}
                    {done && <p className="mt-2 text-sm text-ok" role="status" data-testid="review-saved">{done}</p>}
                    {(val.error || rev.error) && <div className="mt-2"><ErrorState error={val.error || rev.error} compact /></div>}
                  </div>
                  <div>
                    <h3 className="h-section mb-1.5">Export</h3>
                    <ul className="flex flex-wrap gap-2">{FORMATS.map(([f, label, hint]) => (
                      <li key={f}><a className="btn-ghost" href={reportExportUrl(id, f, lang)} data-testid={`export-${f}`} title={hint}><Download className="h-4 w-4" aria-hidden />{label}</a></li>))}</ul>
                    <p className="mt-1 text-xs text-muted">Exports use the language selected above and keep the limitations and the review status. PDF is not offered.</p>
                  </div>
                </section>
              </div>)}
        </section>
      </div>
    </div>
  );
}
