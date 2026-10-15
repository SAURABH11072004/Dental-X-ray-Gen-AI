import React from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";

/** Renders an ApiError (or Error) with its hint and, for known blockers, a link to the place that fixes it. */
export default function ErrorState({ error, onRetry, compact = false }) {
  if (!error) return null;
  const fix = error.isModelUnavailable ? { to: "/models", label: "Open Model Registry" }
    : error.isDatasetUnavailable ? { to: "/settings", label: "Open System Settings" } : null;
  return (
    <div className={`rounded-xl border border-red-200 bg-red-50 ${compact ? "p-3" : "p-4"} text-sm`} role="alert">
      <div className="flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 mt-0.5 text-bad shrink-0" aria-hidden />
        <div className="min-w-0">
          <p className="font-medium text-bad break-words">{error.message || String(error)}</p>
          {error.hint && <p className="mt-1 text-slate-700 break-words">{error.hint}</p>}
          {error.code && error.code !== "request_failed" && <p className="mt-1 text-xs text-muted">code: {error.code}</p>}
          <div className="mt-2 flex gap-2">
            {onRetry && <button className="btn-ghost !py-1" onClick={onRetry}>Retry</button>}
            {fix && <Link className="btn-ghost !py-1" to={fix.to}>{fix.label}</Link>}
          </div>
        </div>
      </div>
    </div>
  );
}
