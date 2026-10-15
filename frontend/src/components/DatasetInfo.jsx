import React from "react";
import { useApi } from "../hooks/useApi";
import { api } from "../services/api";

/** Compact, collapsed dataset facts. Counts come from the dataset audit written by scripts/audit_dataset.py, and leakage results from
 *  scripts/check_leakage.py (summary derived by the API from the individual checks) - never typed in here. */
export default function DatasetInfo() {
  const audit = useApi(() => api.datasetAudit(), []);
  const leak = useApi(() => api.datasetLeakage(), []);
  const a = audit.data;
  return (
    <details open className="card card-pad" data-testid="dataset-info">
      <summary className="cursor-pointer text-[0.95rem] font-semibold text-navy">Training data facts and data audit</summary>
      {audit.loading ? <p className="mt-2 text-sm text-muted">Loading…</p> : !a ? <p className="mt-2 text-sm text-muted">The dataset audit has not been generated yet (run <code>scripts/audit_dataset.py</code>).</p> : (
        <div className="mt-3 space-y-2 text-sm">
          <dl className="grid gap-x-8 gap-y-1 sm:grid-cols-2 xl:grid-cols-3">
            <div className="flex justify-between"><dt className="text-muted">Image files on disk</dt><dd>{a.totals.images_on_disk}</dd></div>
            <div className="flex justify-between"><dt className="text-muted">Unique radiographs (by pixel content)</dt><dd>{a.duplicates.unique_radiographs}</dd></div>
            <div className="flex justify-between"><dt className="text-muted">Annotated unique radiographs</dt><dd>{a.totals.annotated_distinct_radiographs}</dd></div>
            <div className="flex justify-between"><dt className="text-muted">Unlabeled image files (pool)</dt><dd>{a.totals.unlabeled_images}</dd></div>
            {a.totals.test_data_images != null && (
              <div className="flex justify-between"><dt className="text-muted">Unlabeled validation_data files (demo only)</dt><dd>{a.totals.test_data_images}</dd></div>)}
          </dl>
          <p className="text-xs text-muted">The three annotated DENTEX sub-sets overlap, so the number of files is larger than the number of different radiographs. Splits are assigned per unique radiograph (pixel hash), so identical copies always share a split.</p>
          <LeakageSummary leak={leak} />
        </div>)}
    </details>
  );
}

function LeakageSummary({ leak }) {
  if (leak.loading) return null;
  const d = leak.data;
  if (!d) return <p className="text-xs text-muted" data-testid="leakage-summary">No leakage check has been generated yet (run <code>scripts/check_leakage.py</code>), so split separation is not verified.</p>;
  const sm = d.summary;
  const when = d.generated ? new Date(d.generated).toLocaleString() : "unknown time";
  return (
    <div className="space-y-1 text-xs" data-testid="leakage-summary">
      <p className={sm.failed ? "font-semibold text-bad" : "text-muted"}>
        Leakage check ({when}): {sm.passed} of {sm.total} checks passed
        {sm.failed ? `, ${sm.failed} failed` : ""}{sm.warnings ? `, ${sm.warnings} warning${sm.warnings > 1 ? "s" : ""} (cannot affect any reported metric)` : ""}.
        {!sm.failed && d.stale === false ?" No annotated radiograph is in more than one of train / validation / calibration / test." : ""}
      </p>
      {d.stale !== false && <p className="font-semibold text-warn">Result may be out of date: {d.stale_reason}</p>}
      {sm.unresolved.length > 0 && (
        <ul className="list-disc space-y-1 pl-5">
          {sm.unresolved.map((c) => (
            <li key={c.check}>
              <span className={c.status === "fail" ? "font-semibold text-bad" : "font-semibold text-warn"}>{c.status === "fail" ? "FAIL" : "WARNING"}</span>{" "}
              {c.check}: {c.overlap} image{c.overlap === 1 ? "" : "s"}. <span className="text-muted">{c.note}</span>
            </li>))}
        </ul>)}
    </div>
  );
}
