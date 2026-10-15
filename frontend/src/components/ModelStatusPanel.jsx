import React from "react";
import StatusBadge from "./StatusBadge";

export const MODEL_TASKS = [["detection", "Tooth detection"], ["segmentation", "Tooth segmentation"], ["classification", "Candidate class (finding) classification"], ["numbering", "Tooth numbering (FDI)"]];

/** Availability only, derived from the checkpoints the backend actually found and verified. Architectures, paths and metrics live in the Research tools. */
export function modelAvailability(models = []) {
  return MODEL_TASKS.map(([task, label]) => {
    const all = models.filter((x) => x.task === task);
    const ok = all.some((x) => x.dental_specific);
    const problem = !ok && all.length ? (all[0].provenance || "checkpoint rejected") : null;
    return { task, label, ok, problem };
  });
}

export default function ModelStatusPanel({ models = [] }) {
  return (
    <ul className="divide-y divide-slate-100" data-testid="model-status">
      {modelAvailability(models).map(({ task, label, ok, problem }) => (
        <li key={task} className="flex items-center justify-between gap-3 py-2 text-sm" data-task={task}>
          <span>{label}</span>
          {ok ? <StatusBadge tone="ok">Available</StatusBadge>
            : <span className="flex items-center gap-2 text-right"><StatusBadge tone="warn">Unavailable</StatusBadge>{problem && <span className="max-w-[16rem] text-[11px] text-muted">{problem}</span>}</span>}
        </li>))}
    </ul>
  );
}
