import React from "react";
import { fmt, when } from "../lib/format";
import { HIGH_UNCERTAINTY_TEXT } from "../lib/classResult";
import { SAFETY_NOTE, reviewStatus } from "../lib/reportStatus";
import EvidenceReference from "./EvidenceReference";
import StatusBadge from "./StatusBadge";
import FinalResult from "./FinalResult";

const UncertainNote = ({ f }) => (f.high_uncertainty ? <span className="block text-xs text-warn" data-testid="high-uncertainty-warning">{HIGH_UNCERTAINTY_TEXT}</span> : null);

export function ValidationIndicators({ validation }) {
  if (!validation) return null;
  const items = [["Schema valid", validation.schema_valid], ["Evidence references valid", validation.evidence_refs_valid],
    ["No unsupported claims", validation.unsupported_claims_free], ["Required fields present", validation.required_fields_present]];
  return (
    <div>
      <ul className="grid gap-1.5 sm:grid-cols-2">
        {items.map(([l, ok]) => <li key={l} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-1.5 text-sm"><span>{l}</span><StatusBadge tone={ok ? "ok" : "bad"}>{ok ? "pass" : "fail"}</StatusBadge></li>)}
      </ul>
      {validation.errors?.length > 0 && <ul className="mt-2 list-disc pl-5 text-xs text-bad">{validation.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
    </div>
  );
}

/** One compact, neutral safety note. English uses the fixed sentence; Hindi/Marathi use the translated disclaimer of the same report. */
function SafetyNote({ text }) {
  return <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-700" role="note" data-testid="safety-note">{text}</p>;
}

function Section({ title, children, testid }) {
  return <section data-testid={testid}><h3 className="h-section mb-1.5">{title}</h3>{children}</section>;
}

function LocalizedReport({ loc, report, imageName, check, validation, techExtra }) {
  const h = loc.headings;
  const st = reviewStatus(loc.status);
  const created = report?.created;
  const unc = loc.analysis?.combined_uncertainty;
  const needs = loc.findings.filter((f) => f.needs_review);
  return (
    <article className="space-y-5" lang={loc.lang} data-testid="localized-report">
      {/* 1. heading and status */}
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div><h2 className="text-lg font-semibold text-navy">{loc.title}</h2>
          <p className="mt-0.5 text-xs text-muted">{h.report} <span className="font-mono">{loc.report_id}</span></p></div>
        <StatusBadge tone={st.tone} title={st.detail}><span data-testid="review-status">{st.label}</span></StatusBadge>
      </header>
      <SafetyNote text={loc.lang === "en" ? SAFETY_NOTE : loc.disclaimer} />
      {loc.linguistic_review && <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="ling-review" role="note">{loc.linguistic_review.text}<br /><span className="text-xs text-slate-700">{loc.linguistic_review.text_en}</span></p>}

      {/* 2. image and date */}
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
        <div><dt className="text-xs text-muted">{h.image}</dt><dd>{imageName || loc.image_id}</dd></div>
        <div><dt className="text-xs text-muted">Analysis / report date</dt><dd>{created ? when(created) : "—"}</dd></div>
        <div><dt className="text-xs text-muted">{h.reviewed_by}</dt><dd>{loc.reviewed_by || h.not_reviewed}</dd></div>
      </dl>

      {/* final result (finding / healthy / error), same rule as the analysis page */}
      {(loc.final_result || report?.final_result) && <FinalResult result={loc.final_result || report.final_result} title={loc.final_result?.heading || "Final result"} />}

      {/* 3. summary */}
      <Section title={h.summary}>
        <p className="text-sm leading-relaxed">{loc.summary}</p>
        {loc.analysis?.summary_counts && <p className="mt-2 text-xs text-muted">{["n_regions", "n_numbered", "n_with_mask", "n_review_required", "n_abstained"].map((k) => `${k === "n_abstained" ? "high classifier uncertainty" : k.replace(/^n_/, "").replace(/_/g, " ")}: ${loc.analysis.summary_counts[k]}`).join(" · ")}{loc.analysis.image_quality_flags?.length ? ` · image quality: ${loc.analysis.image_quality_flags.join(", ")}` : ""}</p>}
      </Section>

      {/* 4. findings */}
      <Section title={h.findings}>
        {loc.findings.length === 0 ? <p className="text-sm text-muted">—</p> : (
          <div className="max-h-[420px] overflow-auto"><table className="w-full">
            <thead className="sticky top-0 bg-white"><tr>{loc.columns.map((c) => <th key={c} className="th">{c}</th>)}</tr></thead>
            <tbody>{loc.findings.map((f) => (
              <tr key={f.finding_id}><td className="td font-mono text-xs">{f.finding_id}</td><td className="td">{f.tooth_fdi ?? loc.unassigned}</td>
                <td className="td">{f.kind === "class_unavailable" ? <span className="text-warn">class scores unavailable</span> : f.label_display}<UncertainNote f={f} /></td><td className="td">{fmt(f.probability, f.kind === "detection" ? 3 : 2)}</td>
                <td className="td">{fmt(f.uncertainty, 2)}</td><td className="td">{f.review_status_text}</td></tr>))}</tbody></table></div>)}
      </Section>

      {/* 5. areas requiring human review */}
      {needs.length > 0 && (
        <Section title={loc.headings_review} testid="review-regions">
          <ul className="list-disc space-y-0.5 pl-5 text-sm text-slate-700">{needs.map((f) => <li key={f.finding_id}><span className="font-mono text-xs">{f.finding_id}</span> · {f.tooth_fdi ?? loc.unassigned} · {f.review_reasons_text.join("; ") || "—"}</li>)}</ul>
        </Section>)}

      {/* 6. uncertainty and limitations */}
      <Section title={`${h.limitations} · uncertainty`}>
        {unc != null && <p className="mb-2 text-sm">Overall uncertainty: <b>{fmt(unc, 2)}</b> <span className="text-xs text-muted">(model doubt, not proof of error; scores are uncalibrated)</span></p>}
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{loc.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
      </Section>

      {/* 7. reviewer details and history */}
      <Section title="Review">
        {report?.reviewed_by
          ? <p className="text-sm">Reviewed by <b>{report.reviewed_by}</b>{report.reviewed_at ? ` on ${when(report.reviewed_at)}` : ""}. <span className="text-xs text-muted">The name was typed in and is not identity-verified.</span></p>
          : <p className="text-sm text-muted">No review recorded yet.</p>}
      </Section>

      {/* technical metadata, collapsed */}
      <details className="rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid="tech-details">
        <summary className="cursor-pointer font-medium text-teal">Technical details</summary>
        <div className="mt-3 space-y-3">
          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
            <div><dt className="text-muted">Report id</dt><dd className="font-mono">{loc.report_id}</dd></div>
            <div><dt className="text-muted">Image id</dt><dd className="font-mono">{loc.image_id}</dd></div>
            <div className="sm:col-span-2"><dt className="text-muted">{h.models}</dt><dd className="font-mono">{Object.entries(loc.model_versions).map(([k, v]) => `${k}: ${v}`).join(" · ")}</dd></div>
            <div><dt className="text-muted">{h.generated}</dt><dd>{loc.generated_by}</dd></div>
            {loc.analysis?.analysis_id && <div><dt className="text-muted">Analysis id</dt><dd className="font-mono">{loc.analysis.analysis_id}</dd></div>}
          </dl>
          <div><h4 className="text-xs font-semibold text-muted">Finding descriptions</h4>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-slate-700">{loc.findings.map((f) => <li key={f.finding_id}>{f.narrative}</li>)}</ul></div>
          <p className="text-xs text-muted">{loc.note} {check && <StatusBadge tone={check.passed ? "ok" : "bad"}>{check.passed ? "values match English report" : "mismatch with English report"}</StatusBadge>}</p>
          {validation && <div><h4 className="mb-1 text-xs font-semibold text-muted">Validation</h4><ValidationIndicators validation={validation} /></div>}
          {techExtra}
        </div>
      </details>
    </article>
  );
}

export default function ReportPreview({ report, localized, check, imageName, validation, techExtra }) {
  if (!report) return null;
  if (localized) return <LocalizedReport loc={localized} report={report} imageName={imageName} check={check} validation={validation} techExtra={techExtra} />;
  const st = reviewStatus(report.status);
  return (
    <article className="space-y-4">
      <header className="flex items-start justify-between gap-2"><h2 className="text-lg font-semibold text-navy">Report {report.report_id}</h2><StatusBadge tone={st.tone}>{st.label}</StatusBadge></header>
      <SafetyNote text={SAFETY_NOTE} />
      {report.final_result && <FinalResult result={report.final_result} />}
      <Section title="Summary"><p className="text-sm leading-relaxed">{report.summary}</p></Section>
      <Section title="Structured findings">
        {report.findings.length === 0 ? <p className="text-sm text-muted">No findings were supplied.</p> : (
          <div className="overflow-x-auto"><table className="w-full">
            <thead><tr>{["Tooth", "Highest-scoring class / region", "Raw model score", "Uncertainty", "Evidence", "Review"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
            <tbody>{report.findings.map((f) => (
              <tr key={f.finding_id}><td className="td">{f.tooth_fdi ?? <StatusBadge status="unassigned" />}</td><td className="td">{f.kind === "class_unavailable" ? <span className="text-warn">class scores unavailable</span> : f.label}<UncertainNote f={f} /></td>
                <td className="td">{fmt(f.probability, f.kind === "detection" ? 3 : 2)}</td><td className="td">{fmt(f.uncertainty, 2)}</td>
                <td className="td"><EvidenceReference finding={f} /></td><td className="td"><StatusBadge status={f.review_status} /></td></tr>))}</tbody></table></div>)}
      </Section>
      <Section title="Limitations"><ul className="list-disc pl-5 text-sm text-slate-700">{report.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></Section>
    </article>
  );
}
