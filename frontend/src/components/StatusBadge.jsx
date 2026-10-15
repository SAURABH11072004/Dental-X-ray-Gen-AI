import React from "react";

const TONES = {
  ok: "bg-emerald-50 text-ok border-emerald-200",
  warn: "bg-amber-50 text-warn border-amber-200",
  bad: "bg-red-50 text-bad border-red-200",
  info: "bg-teal-50 text-teal-700 border-teal-200",
  neutral: "bg-slate-100 text-slate-600 border-slate-200",
  test: "bg-violet-50 text-violet-700 border-violet-200",
};
const MAP = {
  succeeded: "ok", approved: "ok", validated: "ok", done: "ok", ok: "ok", available: "ok", assigned: "ok", completed: "ok", reachable: "ok",
  running: "info", queued: "info", exported: "info", imported: "info", submitted: "info", computed: "ok",
  failed: "bad", rejected: "bad", error: "bad", unreachable: "bad", interrupted: "warn", cancelled: "warn",
  warning: "warn", needs_review: "warn", unassigned: "neutral", unavailable: "neutral", pending: "warn", unreviewed: "neutral",
  test_data: "test", unconfirmed_research_draft: "warn", reviewed_research_draft: "ok",
};

export default function StatusBadge({ status, tone, children, title }) {
  const t = tone || MAP[status] || "neutral";
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${TONES[t]}`}>
      {children ?? String(status).replace(/_/g, " ")}
    </span>
  );
}
