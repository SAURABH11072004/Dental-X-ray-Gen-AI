import React from "react";
import { Link2 } from "lucide-react";

export default function EvidenceReference({ finding }) {
  const box = finding.evidence_region?.box;
  return (
    <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-600"
      title={box ? `Region on the radiograph [x1, y1, x2, y2] = [${box.map((v) => Math.round(v)).join(", ")}]` : "No region recorded"}>
      <Link2 className="h-3 w-3" aria-hidden /> {finding.finding_id}{box ? ` · [${box.map((v) => Math.round(v)).join(", ")}]` : ""}
    </span>
  );
}
