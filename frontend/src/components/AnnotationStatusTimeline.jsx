import React from "react";
import { Check } from "lucide-react";

const LABEL = { selected: "Selected", exported: "Exported", annotated: "Annotated", imported: "Imported", validated: "Validated", approved: "Approved for Training" };

/** `counts` maps workflow stage -> real record count (null = unknown). */
export default function AnnotationStatusTimeline({ stages, counts = {} }) {
  return (
    <ol className="flex flex-wrap items-center gap-y-2" aria-label="Annotation workflow">
      {stages.map((s, i) => {
        const n = counts[s];
        const done = n > 0;
        return (
          <li key={s} className="flex items-center">
            <div className="flex items-center gap-2">
              <span className={`flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold ${done ? "border-teal bg-teal text-white" : "border-slate-300 bg-white text-muted"}`}>
                {done ? <Check className="h-4 w-4" aria-hidden /> : i + 1}
              </span>
              <div className="leading-tight">
                <div className="text-sm font-medium text-ink">{LABEL[s] || s}</div>
                <div className="text-xs text-muted">{n === null || n === undefined ? "N/A" : `${n} image${n === 1 ? "" : "s"}`}</div>
              </div>
            </div>
            {i < stages.length - 1 && <div className="mx-3 h-px w-8 bg-slate-300" aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}
