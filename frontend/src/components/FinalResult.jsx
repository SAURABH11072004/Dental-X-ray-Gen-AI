import React from "react";
import { AlertTriangle, CheckCircle2, CircleAlert, ScanSearch } from "lucide-react";
import StatusBadge from "./StatusBadge";
import { pct } from "../lib/format";
import { HIGH_UNCERTAINTY_TEXT } from "../lib/classResult";

/**
 * Image-level final result, computed by the backend (dentexmodel.reporting.final_result) and shown the same way everywhere:
 *   finding  -> each predicted finding with its score and tooth / region
 *   healthy  -> "Healthy — No Finding Detected"
 *   error    -> analysis error (never shown as Healthy)
 *   no_teeth -> no teeth detected
 */
export const FINAL_TONE = { finding: "warn", healthy: "ok", error: "bad", no_teeth: "neutral" };
const ICON = { finding: AlertTriangle, healthy: CheckCircle2, error: CircleAlert, no_teeth: ScanSearch };
const BOX = {
  finding: "border-amber-200 bg-amber-50",
  healthy: "border-emerald-200 bg-emerald-50",
  error: "border-red-200 bg-red-50",
  no_teeth: "border-slate-200 bg-slate-50",
};

export const findingWhere = (f) => (f.fdi != null ? `tooth ${f.fdi}` : `region ${f.region_no ?? "?"}`);

/** Short badge for lists (home, reports list, review queue). */
export function FinalResultBadge({ result }) {
  if (!result) return null;
  const counts = Object.entries(result.counts || {});
  const text = result.status === "finding" && counts.length ? counts.map(([k, n]) => (n > 1 ? `${k} ×${n}` : k)).join(", ") : result.label;
  return <span data-testid="final-result-badge" data-status={result.status}><StatusBadge tone={FINAL_TONE[result.status] || "neutral"} title={result.message || result.label}>{text}</StatusBadge></span>;
}

/** Full panel: label plus every predicted finding with score and tooth / region. */
export default function FinalResult({ result, title = "Final result", compact = false }) {
  if (!result) return null;
  const Icon = ICON[result.status] || ScanSearch;
  const label = result.label_display || result.label;
  return (
    <section className={`rounded-lg border px-3 py-2.5 ${BOX[result.status] || BOX.no_teeth}`} data-testid="final-result" data-status={result.status} aria-label={title} role={result.status === "error" ? "alert" : undefined}>
      <p className="flex items-center gap-2 text-sm"><Icon className="h-4 w-4 shrink-0" aria-hidden /><span className="text-xs font-semibold uppercase tracking-wide text-slate-600">{title}</span></p>
      <p className="mt-0.5 text-base font-semibold text-navy" data-testid="final-result-label">{label}</p>
      {result.message && <p className="mt-0.5 text-xs text-slate-700">{result.message}</p>}
      {result.status === "finding" && result.findings?.length > 0 && (
        <ul className={`mt-1.5 space-y-0.5 text-sm ${compact ? "max-h-40 overflow-auto" : ""}`} data-testid="final-result-findings">
          {result.findings.map((f, i) => (
            <li key={f.region_id || f.finding_id || i}>
              {f.text ? <span>{f.text}</span> /* localized report: the backend's line in the report language */ : <>
                <b>{f.label_display || f.label}</b>
                <span className="text-slate-700"> · {findingWhere(f)}{f.region_no != null && f.fdi != null ? ` (region ${f.region_no})` : ""} · raw model score {pct(f.score, 1)}</span></>}
              {f.high_uncertainty   /* a localized line (f.text) already carries the warning in the report language */
                ? !f.text && <span className="text-xs text-warn" data-testid="high-uncertainty-warning"> · {HIGH_UNCERTAINTY_TEXT}</span>
                : f.needs_review && <span className="text-xs text-warn"> · needs review</span>}
            </li>))}
        </ul>)}
    </section>
  );
}
