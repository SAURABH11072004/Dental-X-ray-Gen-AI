import React from "react";

/** Page title block: bold title, one short plain-language description, optional actions aligned to the right. */
export default function PageHeader({ title, subtitle, actions, eyebrow }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3 sm:mb-6">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-teal">{eyebrow}</p>}
        <h1 className="text-2xl font-bold leading-tight tracking-tight text-navy sm:text-[1.75rem]">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-3xl text-[0.95rem] leading-relaxed text-slate-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
