import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ALL_NAV, NAV, RESEARCH_NAV } from "./Sidebar";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { usePrefs } from "../lib/prefs";
import StatusBadge from "./StatusBadge";

export default function Topbar() {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const [prefs] = usePrefs();
  const title = ALL_NAV.find((n) => n.to === pathname)?.label || "DentaMind";
  const health = useApi(() => api.health(false), [], { pollMs: 20000 });
  const h = health.data;
  // "offline" only after a failed health request, not while the first one is still loading
  const system = !h ? (health.error ? { tone: "bad", text: "Backend offline" } : null) : h.checkpoints_loaded ? null : { tone: "warn", text: "No trained model loaded" };
  const items = [...NAV, ...(prefs.showResearch || RESEARCH_NAV.some((n) => n.to === pathname) ? RESEARCH_NAV : [])];
  return (
    <header className="flex flex-wrap items-center gap-3 border-b border-line bg-white px-4 py-2.5 sm:px-6 xl:px-8">
      <div className="min-w-0 flex-1 truncate text-sm font-medium text-muted"><span className="text-navy">DentaMind AI</span><span aria-hidden> / </span>{title}</div>
      <label className="lg:hidden"><span className="sr-only">Go to page</span>
        <select className="input !w-auto !py-1.5" value={items.some((n) => n.to === pathname) ? pathname : "/"} onChange={(e) => nav(e.target.value)}>
          {items.map((n) => <option key={n.to} value={n.to}>{n.label}</option>)}
        </select></label>
      {system && <StatusBadge tone={system.tone}>{system.text}</StatusBadge>}
    </header>
  );
}
