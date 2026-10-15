// Review status as a person reads it. The stored status values are unchanged.
export function reviewStatus(status) {
  if (status === "reviewed_research_draft") return { key: "reviewed", label: "Reviewed", tone: "ok", detail: "Signed off by a named reviewer (the name is typed in, not verified)." };
  return { key: "awaiting", label: "Awaiting review", tone: "warn", detail: "Not yet reviewed by a person." };
}

export const SAFETY_NOTE = "Research output — not a confirmed diagnosis. Requires qualified professional review.";
