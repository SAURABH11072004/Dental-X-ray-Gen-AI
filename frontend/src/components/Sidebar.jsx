import React from "react";
import { NavLink } from "react-router-dom";
import { Boxes, Brain, ClipboardCheck, Cpu, Cross, FileText, FlaskConical, Home, Info, Layers, PenTool, ScanSearch, Settings, ShieldQuestion } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";
import { usePrefs } from "../lib/prefs";

// End-user navigation.
export const NAV = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/analysis", label: "X-ray Analysis", icon: ScanSearch },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/review", label: "Review Findings", icon: ClipboardCheck },
];
export const FOOT_NAV = [
  { to: "/about", label: "About & Limitations", icon: Info },
  { to: "/settings", label: "Settings", icon: Settings },
];

// Research / developer tools: every page and route still works; the links are shown only when switched on in Settings.
export const RESEARCH_NAV = [
  { to: "/segmentation", label: "Tooth Segmentation", icon: Layers },
  { to: "/uncertainty", label: "Uncertainty", icon: ShieldQuestion },
  { to: "/active-learning", label: "Active Learning", icon: Brain },
  { to: "/annotations", label: "Annotations", icon: PenTool },
  { to: "/training", label: "Model Training", icon: Cpu },
  { to: "/experiments", label: "Experiments", icon: FlaskConical },
  { to: "/models", label: "Model Registry", icon: Boxes },
];
export const isResearchPath = (p) => RESEARCH_NAV.some((n) => n.to === p);
export const ALL_NAV = [...NAV, ...FOOT_NAV, ...RESEARCH_NAV];

const linkCls = ({ isActive }) => `mb-0.5 flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${isActive ? "bg-white/15 text-white font-medium" : "text-slate-300 hover:bg-white/10 hover:text-white"}`;

export default function Sidebar() {
  const health = useApi(() => api.health(false), [], { pollMs: 20000 });
  const [prefs] = usePrefs();
  const backendOk = health.data?.backend === "ok";
  return (
    <aside className="hidden h-full w-64 shrink-0 flex-col bg-navy text-slate-200 lg:flex" aria-label="Primary">
      <div className="flex items-center gap-3 px-5 py-5">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10"><Cross className="h-5 w-5 text-teal" strokeWidth={3} aria-hidden /></span>
        <div className="text-lg font-semibold leading-tight text-white">DentaMind</div>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 pb-3" aria-label="Main">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={linkCls}><Icon className="h-4 w-4 shrink-0" aria-hidden /> {label}</NavLink>
        ))}
        {prefs.showResearch && (
          <div className="mt-5" data-testid="research-nav">
            <p className="px-3 py-1 text-xs uppercase tracking-wide text-slate-400">Research / Developer Tools</p>
            {RESEARCH_NAV.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} className={linkCls}><Icon className="h-4 w-4 shrink-0" aria-hidden /> {label}</NavLink>
            ))}
          </div>)}
      </nav>
      {health.data && !backendOk && <div className="border-t border-white/10 px-3 py-3 text-sm"><p className="px-3 text-xs text-red-300">Backend offline</p></div>}
    </aside>
  );
}
