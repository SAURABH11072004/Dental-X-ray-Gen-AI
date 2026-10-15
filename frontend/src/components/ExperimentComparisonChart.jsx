import React from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import EmptyState from "./EmptyState";

const COLORS = { random: "#64748B", entropy: "#A75B04", disagreement: "#7C3AED", combined: "#0D7D7F", supervised: "#15304B" };

/** series: { strategy: [{budget, value}] }. Draws only strategies with real records. */
export default function ExperimentComparisonChart({ series, yLabel, height = 280 }) {
  const strategies = Object.keys(series || {});
  if (!strategies.length) {
    return <EmptyState title="No evaluation results yet" message="Run an experiment to populate this chart." />;
  }
  const budgets = [...new Set(strategies.flatMap((s) => series[s].map((p) => p.budget)))].sort((a, b) => a - b);
  const rows = budgets.map((b) => Object.fromEntries([["budget", b], ...strategies.map((s) => [s, series[s].find((p) => p.budget === b)?.value ?? null])]));
  return (
    <div style={{ height }} role="img" aria-label={`${yLabel} versus annotation budget`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="budget" tick={{ fontSize: 12 }} label={{ value: "Annotation budget (images)", position: "insideBottom", offset: -2, fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} domain={[0, "auto"]} label={{ value: yLabel, angle: -90, position: "insideLeft", fontSize: 12 }} />
          <Tooltip />
          <Legend formatter={(v) => <span style={{ color: "#1C2938" }}>{v}</span>} />
          {strategies.map((s) => <Line key={s} type="monotone" dataKey={s} stroke={COLORS[s] || "#0F8B8D"} strokeWidth={2.5} dot={{ r: 4 }} connectNulls />)}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
