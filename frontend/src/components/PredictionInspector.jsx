import React from "react";
import { Link } from "react-router-dom";
import { pct } from "../lib/format";
import { FLAG_TEXT } from "../lib/fullAnalysis";
import { regionName } from "./DetectionOverlay";
import StatusBadge from "./StatusBadge";
import UncertaintyScoreCard from "./UncertaintyScoreCard";

const NUM_TEXT = { assigned: "assigned by the numbering model", needs_review: "needs verification (proposed by the numbering model)", unassigned: "not assigned" };

/** Results inspector. Everything shown is a model output with its meaning stated; nothing is inferred in the browser. */
export default function PredictionInspector({ analysis, selected, reportId }) {
  if (!analysis) return <p className="text-sm text-muted">Analyze an X-ray to see the regions the models found. Nothing is shown until a real model has produced output.</p>;
  const reg = analysis.regions?.[selected];
  if (!reg) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted">Select a region on the image or in the list to see its details.</p>
        {analysis.uncertainty && <UncertaintyScoreCard record={analysis.uncertainty} />}
      </div>);
  }
  const d = analysis.detections[selected];
  const cc = reg.candidate_class;
  const cls = analysis.classification;
  const names = cls?.class_names || [];
  const probs = cls?.probabilities?.[selected];
  const u = reg.uncertainty || {};
  const num = (v) => (v != null ? v.toFixed(3) : "not available");
  return (
    <div className="space-y-4" data-testid="region-detail">
      <div>
        <h3 className="text-base font-semibold text-navy" data-testid="region-title">{regionName(d, selected)}</h3>
        <p className="mt-0.5 font-mono text-[11px] text-muted">id {reg.region_id.split(":")[1]}</p>
        {reg.review_required
          ? <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="needs-review">Needs human review{reg.flags?.length ? `: ${reg.flags.map((f) => FLAG_TEXT[f] || f).join(", ")}` : ""}.</p>
          : <p className="mt-2 text-sm text-slate-600">No review flag was raised for this region.</p>}
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
        <dt className="text-muted">Tooth number (FDI)</dt>
        <dd className="text-right">{reg.fdi != null ? <><b>{reg.fdi}</b> <span className="text-xs text-muted">{NUM_TEXT[reg.numbering_status] || reg.numbering_status}</span></> : <StatusBadge tone="warn">Unassigned</StatusBadge>}</dd>
        {reg.fdi_confidence != null && <><dt className="text-muted">Numbering model score</dt><dd className="text-right">{pct(reg.fdi_confidence, 1)} <span className="text-xs text-muted">raw model score</span></dd></>}
        <dt className="text-muted">Detection score</dt><dd className="text-right">{pct(d.score, 1)} <span className="text-xs text-muted">raw model score</span></dd>
        <dt className="text-muted">Segmentation mask</dt><dd className="text-right">{reg.mask ? `matched (overlap ${(reg.mask.match_iou * 100).toFixed(0)}%)` : "none matched"}</dd>
      </dl>

      <div className="rounded-lg border border-slate-200 p-3 text-sm">
        <h4 className="text-sm font-semibold">Closest trained class</h4>
        {cc?.status === "abstained"
          ? <p className="mt-1 text-xs text-amber-900"><b>No reliable class candidate.</b> The classifier is too unsure about this region (classification entropy {num(u.entropy)} is at or above the review threshold), so no class is named. A person should look at it. The raw scores below are shown for transparency only.</p>
          : cc
            ? <p className="mt-1">Candidate class: <b data-testid="candidate-class">{cc.label}</b> <span className="text-xs text-muted">(raw score {pct(cc.score, 0)})</span></p>
            : <p className="mt-1 text-xs text-muted">No classifier output for this region.</p>}
        <p className="mt-2 text-xs text-slate-600">This is only the closest of four trained classes (Caries, Deep Caries, Impacted, Periapical Lesion). The classifier has no “healthy” class, so a class is always the top score — it is <b>not</b> evidence that the finding is present.</p>
        {probs && names.length > 0 && (
          <ul className="mt-2 space-y-1.5">
            {names.map((n, i) => (
              <li key={n} className="text-xs">
                <div className="flex justify-between"><span>{n}</span><span>{pct(probs[i], 1)}</span></div>
                <div className="h-1.5 rounded bg-slate-100"><div className="h-1.5 rounded bg-teal" style={{ width: `${(probs[i] || 0) * 100}%` }} /></div>
              </li>))}
          </ul>)}
        <p className="mt-2 text-[11px] text-muted">Scores are uncalibrated model outputs, not probabilities of disease.</p>
      </div>

      <div>
        <h4 className="text-sm font-semibold">Uncertainty for this region</h4>
        <dl className="mt-1 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted">Classification entropy</dt><dd>{num(u.entropy)}</dd>
          <dt className="text-muted">Flip disagreement</dt><dd>{num(u.tta_disagreement)}</dd>
          <dt className="text-muted">Mask instability</dt><dd>{num(u.mask_instability)}</dd>
          <dt className="text-muted">Detection instability</dt><dd>{num(u.detection_instability)}</dd>
        </dl>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <Link className="btn-ghost !py-1" to={`/review?image=${encodeURIComponent(analysis.image_id)}`}>Review this region</Link>
        {reportId ? <Link className="btn-ghost !py-1" to={`/reports?id=${reportId}`}>Open the report</Link> : <span className="text-muted">No report yet — use “Generate report”.</span>}
      </div>

      {analysis.uncertainty && <UncertaintyScoreCard record={analysis.uncertainty} />}
    </div>
  );
}
