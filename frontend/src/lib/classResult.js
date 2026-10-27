// Highest-scoring trained class of one region, mirroring dentexmodel.reporting.final_result.top_class on the backend.
// Display only: scores are the classifier's raw (uncalibrated) outputs and are never changed or re-computed here.
// High classifier entropy (status "abstained", set by the unchanged backend threshold) keeps the class visible and adds
// a human-review warning. Missing or invalid scores give null - no class or score is ever invented.

export const HIGH_UNCERTAINTY_TEXT = "Needs human review — high classifier uncertainty";

const validScore = (v) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1;

/** candidate_class -> { label, score, scores: [[name, score], ...], highUncertainty } or null. Ties keep the first class (numpy argmax). */
export function topClass(cc) {
  const probs = cc?.probabilities;
  if (!probs || typeof probs !== "object" || Array.isArray(probs)) return null;
  const scores = Object.entries(probs);
  if (!scores.length || !scores.every(([, v]) => validScore(v))) return null;
  let best = scores[0];
  for (const s of scores) if (s[1] > best[1]) best = s;
  return { label: best[0], score: best[1], scores, highUncertainty: cc.status === "abstained" };
}
