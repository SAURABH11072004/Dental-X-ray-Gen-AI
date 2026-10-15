import React from "react";
import { Link } from "react-router-dom";
import { Inbox } from "lucide-react";

/** `compact` keeps the empty state small so it never becomes a giant blank card. */
export default function EmptyState({ title, message, icon: Icon = Inbox, action, to, actionLabel, children, compact = false }) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/60 text-center ${compact ? "px-4 py-6" : "px-6 py-10"}`} role="status">
      <Icon className={`${compact ? "mb-2 h-6 w-6" : "mb-3 h-8 w-8"} text-slate-400`} aria-hidden />
      <p className="font-semibold text-navy">{title}</p>
      {message && <p className="mt-1 max-w-xl text-sm text-muted">{message}</p>}
      {children}
      {to && <Link to={to} className={`btn-ghost ${compact ? "mt-3" : "mt-4"}`}>{actionLabel || "Open"}</Link>}
      {action && <button className={`btn-ghost ${compact ? "mt-3" : "mt-4"}`} onClick={action.onClick}>{action.label}</button>}
    </div>
  );
}
