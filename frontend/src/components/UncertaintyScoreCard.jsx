import React from "react";
import { Info } from "lucide-react";
import { fmt } from "../lib/format";
import StatusBadge from "./StatusBadge";

const ROWS = [
  ["entropy", "Classification entropy", "Normalised Shannon entropy of the predicted class distribution (0 = certain, 1 = uniform)."],
  ["disagreement", "Flip (TTA) disagreement", "Jensen–Shannon divergence between the classifier on a crop and on its horizontal flip, normalised to 0–1. Two passes of ONE network — not an ensemble."],
  ["mask_instability", "Segmentation instability", "Mean (1 − IoU) between each mask and the mask predicted on the horizontally flipped image (flipped back). 0 = identical."],
  ["detection_instability", "Detection instability", "Mean (1 − IoU) of each box against its best match on the flipped image. Reported, but not part of the combined score."],
];

/** Predictive uncertainty and image-quality warnings are deliberately shown in separate sections. */
export default function UncertaintyScoreCard({ record }) {
  if (!record) return null;
  const val = (key) => record.signal_validation?.[key];
  return (
    <div className="space-y-3" data-testid="unc-card">
      <div>
        <div className="flex items-center justify-between">
          <h4 className="h-section">Uncertainty</h4>
          <span className="text-xs text-muted">Overall: <b className="text-ink" data-testid="unc-overall">{fmt(record.combined_score)}</b></span>
        </div>
        <dl className="mt-2 divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
          {ROWS.map(([key, label]) => {
            const s = record[key] || {};
            return (
              <div key={key} className="flex items-center justify-between gap-3 px-3 py-1.5">
                <dt className="text-slate-700">{label}</dt>
                <dd className="text-right">{s.status === "computed" ? <b>{fmt(s.value)}</b> : <span className="text-xs text-muted">unavailable</span>}</dd>
              </div>);
          })}
        </dl>
        <p className="mt-2 text-xs font-medium text-slate-700" data-testid="unc-explainer">Uncertainty indicates model doubt, not a confirmed error. These research estimates are not guarantees of correctness.</p>
      </div>
      <div>
        <h4 className="h-section">Image quality <span className="font-normal text-muted">(separate from uncertainty)</span></h4>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {(record.quality_flags || []).length ? record.quality_flags.map((f) => <StatusBadge key={f} tone="warn">{f.replace(/_/g, " ")}</StatusBadge>) : <StatusBadge tone="ok">no quality warnings</StatusBadge>}
        </div>
      </div>
      <details className="rounded-lg border border-slate-200 px-3 py-2 text-xs" data-testid="unc-how">
        <summary className="cursor-pointer font-medium text-teal">How uncertainty is calculated</summary>
        <ul className="mt-2 space-y-2.5">
          {ROWS.map(([key, label, tip]) => (
            <li key={key}>
              <p className="font-medium text-slate-800">{label}</p>
              <p className="text-slate-600">{tip}</p>
              {record[key]?.status !== "computed" && record[key]?.reason && <p className="text-slate-600">Not available: {record[key].reason}</p>}
              {val(key) && <p className="text-muted" data-testid={`sigval-${key}`}>{val(key).auroc == null ? "not validated" : `Measured reliability: ${val(key).verdict} (AUROC ${fmt(val(key).auroc, 2)} against ${val(key).against}, ${val(key).split} split)`}</p>}
            </li>))}
        </ul>
        <p className="mt-2 text-slate-600">Overall = weighted mean of the available signals (entropy 0.4, disagreement 0.4, segmentation instability 0.2), renormalised; a missing signal is never counted as 0. Detection instability is shown but not part of the overall value.</p>
        <p className="mt-1 text-slate-600">AUROC 0.5 means no information and 1.0 a perfect ranking. Weak signals are labelled weak and must not be read as risk scores; none of these values is a calibrated probability.</p>
        {record.thresholds && <p className="mt-1 text-slate-600">Review thresholds are <b>provisional</b> ({record.thresholds.source}).</p>}
        {record.quality_metrics && Object.keys(record.quality_metrics).length > 0 && <p className="mt-1 text-muted">sharpness {fmt(record.quality_metrics.sharpness_laplacian_var, 1)} · contrast {fmt(record.quality_metrics.contrast_std)} · brightness {fmt(record.quality_metrics.brightness_mean)}</p>}
      </details>
    </div>
  );
}
