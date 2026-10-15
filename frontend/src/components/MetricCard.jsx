import React from "react";
import { Info } from "lucide-react";

export default function MetricCard({ label, value, hint, icon: Icon, tone = "navy", tooltip }) {
  const color = { navy: "text-navy", teal: "text-teal", ok: "text-ok", warn: "text-warn", bad: "text-bad" }[tone];
  return (
    <div className="card card-pad">
      <div className="flex items-center justify-between">
        <span className="label !mb-0 flex items-center gap-1">
          {label}
          {tooltip && <span title={tooltip} className="cursor-help" tabIndex={0} aria-label={tooltip}><Info className="h-3 w-3" aria-hidden /></span>}
        </span>
        {Icon && <Icon className="h-4 w-4 text-slate-400" aria-hidden />}
      </div>
      <div className={`mt-2 text-2xl font-semibold ${color} break-words`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}
