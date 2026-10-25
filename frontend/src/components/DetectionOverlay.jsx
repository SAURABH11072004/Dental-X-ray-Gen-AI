import React, { useMemo } from "react";

/**
 * What a label means (never mix these up):
 *   "14"   a tooth number (FDI) assigned by the numbering model and consistent with its neighbours
 *   "14?"  the numbering model proposed 14 but the number needs checking
 *   "R7"   Region 7: a detected region with NO tooth number (the 7 is only the order of detection, not anatomy)
 */
export function regionLabel(d, i) {
  const n = d.region_no ?? i + 1;
  if (d.fdi == null) return { text: `R${n}`, kind: "region" };
  return d.fdi_status && d.fdi_status !== "assigned" ? { text: `${d.fdi}?`, kind: "check" } : { text: String(d.fdi), kind: "tooth" };
}
export const regionName = (d, i) => {
  const n = d.region_no ?? i + 1;
  if (d.fdi == null) return `Region ${n} (no tooth number)`;
  return d.fdi_status && d.fdi_status !== "assigned" ? `Region ${n} (proposed tooth ${d.fdi}, needs review)` : `Region ${n} (tooth ${d.fdi})`;
};

const overlap = (a, b, m) => a.x < b.x + b.w + m && b.x < a.x + a.w + m && a.y < b.y + b.h + m && b.y < a.y + a.h + m;

/** Collision-aware label placement in image pixels: above the box, then below, then inside; a label that cannot be placed without covering another is omitted (the box and the region list stay usable). */
export function placeLabels(items, fs, selected, W, H) {
  const placed = [];
  const out = new Map();
  const order = items.map((it, i) => i).sort((a, b) => (a === selected ? -1 : b === selected ? 1 : items[a].box[0] - items[b].box[0]));
  for (const i of order) {
    const { box: [x1, y1, x2, y2], text } = items[i];
    const w = text.length * fs * 0.62 + fs * 0.9, h = fs * 1.45;
    const clamp = (c) => (W && H ? { x: Math.min(Math.max(0, c.x), Math.max(0, W - w)), y: Math.min(Math.max(0, c.y), Math.max(0, H - h)) } : c);   // labels stay inside the image
    const cands = [{ x: x1, y: y1 - h }, { x: x1, y: y2 }, { x: x1, y: y1 }, { x: x2 - w, y: y1 - h }, { x: x2 - w, y: y2 }].map(clamp);
    const pick = cands.find((c) => !placed.some((p) => overlap({ ...c, w, h }, p, fs * 0.15)));
    if (pick || i === selected) { const c = pick || cands[0]; placed.push({ ...c, w, h }); out.set(i, { ...c, w, h }); }
  }
  return out;
}

/** SVG layer (image pixel coordinates). Only draws regions that really came from the models. */
export default function DetectionOverlay({ detections = [], selected, onSelect, showBoxes = true, showIds = true, showLabels = false, k = 1, width, height }) {
  const fs = 13 / k;      // constant on-screen text size
  const items = useMemo(() => detections.map((d, i) => {
    const l = regionLabel(d, i);
    const cls = showLabels && d.candidate ? ` ~${d.candidate}${d.candidate_uncertain ? "?" : ""}` : "";
    return { box: d.box, text: l.text + cls, kind: l.kind };
  }), [detections, showLabels]);
  const layout = useMemo(() => (showIds || showLabels ? placeLabels(items, fs, selected, width, height) : new Map()), [items, fs, selected, showIds, showLabels, width, height]);
  if (!showBoxes) return null;
  return (
    <g>
      {detections.map((d, i) => {
        const [x1, y1, x2, y2] = d.box;
        const sel = selected === i;
        const it = items[i];
        const color = sel ? "#A75B04" : it.kind === "region" ? "#64748B" : it.kind === "check" ? "#C44343" : "#0D7D7F";
        const lp = layout.get(i);
        return (
          <g key={i} onClick={(e) => { e.stopPropagation(); onSelect?.(i); }} style={{ cursor: "pointer" }} data-testid="detection-box" data-region={d.region_no ?? i + 1}>
            <title>{regionName(d, i)}</title>
            <rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} fill={sel ? "rgba(217,119,6,0.14)" : "rgba(15,139,141,0.05)"} stroke={color} strokeWidth={sel ? 3 : 2} vectorEffect="non-scaling-stroke" />
            {lp && (
              <g data-testid="region-label">
                <rect x={lp.x} y={lp.y} width={lp.w} height={lp.h} fill={color} rx={fs * 0.2} />
                <text x={lp.x + fs * 0.4} y={lp.y + lp.h * 0.74} fontSize={fs} fill="#fff" fontFamily="Inter, sans-serif">{it.text}</text>
              </g>)}
          </g>
        );
      })}
    </g>
  );
}

export function OverlayLegend({ showClasses }) {
  const sw = (c) => <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: c }} aria-hidden />;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600" aria-label="Legend" data-testid="legend">
      <li className="flex items-center gap-1.5">{sw("#0D7D7F")}<b>14</b> tooth number from the numbering model</li>
      <li className="flex items-center gap-1.5">{sw("#C44343")}<b>14?</b> proposed number, needs checking</li>
      <li className="flex items-center gap-1.5">{sw("#64748B")}<b>R7</b> region without a tooth number (R = region, 7 = detection order)</li>
      <li className="flex items-center gap-1.5">{sw("#A75B04")}selected region</li>
      {showClasses && <li><b>~Caries</b> highest-scoring trained class, not a finding · <b>~Caries?</b> needs human review — high classifier uncertainty</li>}
    </ul>
  );
}
