import React from "react";
import { Eye } from "lucide-react";
import StatusBadge from "./StatusBadge";
import { regionLabel } from "./DetectionOverlay";
import { fmt } from "../lib/format";
import { describeRegion } from "../lib/regionText";

export { describeRegion };

function ClassCell({ cls }) {
  return (
    <>
      <span data-testid="table-class">{cls.main}</span>
      {cls.warning && <span className="mt-0.5 block text-xs text-warn" data-testid="high-uncertainty-warning">{cls.warning}</span>}
    </>
  );
}

const TONE = { plain: "text-ink", muted: "text-muted", warn: "text-warn" };

function NumberCell({ n, fdiScore }) {
  return (
    <span title={fdiScore != null ? `Numbering model raw score ${fmt(fdiScore, 2)}` : undefined}>
      <span className={`font-medium ${TONE[n.tone]}`}>{n.main}</span>
      {n.sub && n.tone === "warn" && <span className="text-warn"> · {n.sub}</span>}
    </span>
  );
}

function Chips({ chips }) {
  if (!chips.length) return <span className="text-muted">—</span>;
  return <div className="flex flex-wrap gap-1">{chips.map((c) => <span key={c.key} title={c.title} className="whitespace-nowrap"><StatusBadge tone="warn">{c.text}</StatusBadge></span>)}</div>;
}

export default function RegionTable({ active, selected, onPick, onReview }) {
  const regions = active.regions;
  const thr = active.uncertainty?.thresholds || {};
  const rows = regions.map((g, i) => ({ g, i, d: active.detections[i], info: describeRegion(g, thr) }));
  const keyPick = (e, i) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(i); } };

  return (
    <div className="card card-pad min-w-0" data-testid="region-table" aria-label="Regions">
      <div className="card-head !mb-2">
        <h2 className="h-section">Regions <span className="font-normal text-muted">({regions.length})</span></h2>
        <span className="text-xs text-muted">{regions.filter((g) => g.review_required).length} need review</span>
      </div>
      <dl className="mb-3 grid gap-x-6 gap-y-1 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 sm:grid-cols-2 2xl:grid-cols-4" data-testid="table-help">
        <div><dt className="inline font-semibold text-navy">Region</dt> <dd className="inline">– an area the detector found on the image (R7 = region 7 without a tooth number).</dd></div>
        <div><dt className="inline font-semibold text-navy">Tooth number</dt> <dd className="inline">– an FDI estimate; it can be unassigned or need verification.</dd></div>
        <div><dt className="inline font-semibold text-navy">Candidate class</dt> <dd className="inline">– the highest-scoring of four trained findings, not a confirmed diagnosis.</dd></div>
        <div><dt className="inline font-semibold text-navy">Raw model score</dt> <dd className="inline">– an uncalibrated model output, not a probability of disease.</dd></div>
      </dl>

      {/* table: tablet and wider (scrolls inside its own container only) */}
      <div className="hidden max-h-[440px] overflow-auto rounded-lg border border-slate-100 md:block">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-[1] bg-white"><tr>
            {[["Region"], ["Tooth number"], ["Candidate class"], ["Raw model score", "Raw score of the highest-scoring class (uncalibrated model output, not a probability of disease)"], ["Flags", "Separate warnings for detection, outline and class stability"], ["Review"]].map(([h, t]) => <th key={h} className="th" title={t}>{h}</th>)}
          </tr></thead>
          <tbody>{rows.map(({ g, i, d, info }) => (
            <tr key={g.region_id} tabIndex={0} aria-selected={selected === i} className={`cursor-pointer hover:bg-slate-50 ${selected === i ? "bg-amber-50" : ""}`}
              onClick={() => onPick(i)} onKeyDown={(e) => keyPick(e, i)}>
              <td className="td font-semibold text-navy">{regionLabel(d, i).text}</td>
              <td className="td whitespace-nowrap"><NumberCell n={info.number} fdiScore={g.fdi_confidence} /></td>
              <td className={`td min-w-[10rem] ${TONE[info.cls.tone]}`} title={info.cls.title}><ClassCell cls={info.cls} /></td>
              <td className="td tabular-nums">{info.score}</td>
              <td className="td"><Chips chips={info.chips} /></td>
              <td className="td whitespace-nowrap">
                <div className="flex flex-col items-start gap-1.5 min-[1800px]:flex-row min-[1800px]:items-center">
                  {g.review_required ? <StatusBadge tone="warn">Needs review</StatusBadge> : <StatusBadge tone="neutral">No flag</StatusBadge>}
                  <button className="btn-ghost !px-2 !py-1 text-xs" aria-label={`Review region ${regionLabel(d, i).text}`} onClick={(e) => { e.stopPropagation(); onReview(i); }}>
                    <Eye className="h-3.5 w-3.5" aria-hidden />Review region</button>
                </div>
              </td>
            </tr>))}</tbody>
        </table>
      </div>

      {/* compact cards: phones */}
      <ul className="max-h-[520px] space-y-2 overflow-y-auto md:hidden" aria-label="Regions (compact)">
        {rows.map(({ g, i, d, info }) => (
          <li key={g.region_id}>
            <button className={`w-full rounded-lg border p-3 text-left text-sm ${selected === i ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"}`}
              onClick={() => onReview(i)} aria-label={`Review region ${regionLabel(d, i).text}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-navy">{regionLabel(d, i).text}</span>
                {g.review_required ? <StatusBadge tone="warn">Needs review</StatusBadge> : <StatusBadge tone="neutral">No flag</StatusBadge>}
              </div>
              <p className="mt-1"><span className="text-muted">Tooth </span><NumberCell n={info.number} fdiScore={g.fdi_confidence} /></p>
              <p className={TONE[info.cls.tone]}>{info.cls.main}{info.score !== "—" && <span className="text-muted"> · raw model score {info.score}</span>}</p>
              {info.cls.warning && <p className="text-xs text-warn" data-testid="high-uncertainty-warning">{info.cls.warning}</p>}
              {info.chips.length > 0 && <div className="mt-1.5"><Chips chips={info.chips} /></div>}
            </button>
          </li>))}
      </ul>
    </div>
  );
}
