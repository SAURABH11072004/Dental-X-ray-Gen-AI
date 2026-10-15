import React, { useEffect, useRef } from "react";

export default function ConfirmDialog({ open, title, children, confirmLabel = "Confirm", danger = false, onConfirm, onCancel, busy, confirmDisabled = false, wide = false }) {
  const ref = useRef(null);
  useEffect(() => { if (open) ref.current?.focus(); }, [open]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onCancel?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy/40 p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className={`card card-pad w-full ${wide ? "max-w-2xl max-h-[90vh] overflow-y-auto" : "max-w-md"}`} tabIndex={-1} ref={ref}>
        <h2 className="text-lg font-semibold text-navy">{title}</h2>
        <div className="mt-2 text-sm text-slate-700 space-y-2">{children}</div>
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-ghost" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className={danger ? "btn-danger" : "btn-primary"} onClick={onConfirm} disabled={busy || confirmDisabled}>{busy ? "Working…" : confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
