import React from "react";
import { Info } from "lucide-react";

const LABELS = { random: "Random Sampling", entropy: "Entropy Sampling", disagreement: "Ensemble Disagreement", combined: "Combined Uncertainty + Diversity" };

export default function AcquisitionStrategySelector({ strategies = [], value, onChange }) {
  return (
    <fieldset>
      <legend className="label">Acquisition strategy</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {strategies.map((s) => (
          <label key={s.id} title={s.description}
            className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-sm ${value === s.id ? "border-teal bg-teal-50" : "border-slate-200 bg-white hover:bg-slate-50"}`}>
            <input type="radio" name="strategy" className="mt-1" checked={value === s.id} onChange={() => onChange(s.id)} />
            <span>
              <span className="flex items-center gap-1 font-medium text-navy">{LABELS[s.id] || s.id}<Info className="h-3 w-3 text-slate-400" aria-hidden /></span>
              <span className="mt-0.5 block text-xs text-muted">{s.description}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
