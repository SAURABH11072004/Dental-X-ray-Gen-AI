// Run with: npm test   (node's built-in test runner; no extra dependencies)
import test from "node:test";
import assert from "node:assert/strict";
import { HIGH_UNCERTAINTY_TEXT, topClass } from "./classResult.js";
import { describeRegion } from "./regionText.js";

// Region 22 / tooth 33 example: entropy 0.616 is at or above the review threshold, so the backend status is "abstained".
const EXAMPLE = { label: "Caries", score: 0.726, status: "abstained",
  probabilities: { Caries: 0.726, "Deep Caries": 0.14, Impacted: 0.034, "Periapical Lesion": 0.1 } };
const REGION = { region_no: 22, fdi: 33, numbering_status: "assigned", fdi_confidence: 0.996, detection_score: 0.997,
  candidate_class: EXAMPLE, uncertainty: { entropy: 0.616 }, flags: ["high_entropy"], review_required: true };

test("highest raw score is chosen even when entropy is at or above the review threshold", () => {
  const tc = topClass(EXAMPLE);
  assert.equal(tc.label, "Caries");
  assert.equal(tc.score, 0.726);
  assert.equal(tc.highUncertainty, true);
  assert.deepEqual(tc.scores, Object.entries(EXAMPLE.probabilities));       // all four scores, unchanged
});

test("a confident region has no uncertainty warning", () => {
  assert.equal(topClass({ ...EXAMPLE, status: "candidate" }).highUncertainty, false);
});

test("highest score wins regardless of the stored label or class order", () => {
  const tc = topClass({ status: "candidate", probabilities: { Caries: 0.1, "Deep Caries": 0.2, Impacted: 0.05, "Periapical Lesion": 0.65 } });
  assert.equal(tc.label, "Periapical Lesion");
});

test("missing, invalid or non-finite scores give no class", () => {
  for (const bad of [null, undefined, {}, { probabilities: {} }, { probabilities: [0.7, 0.3] },
    { probabilities: { ...EXAMPLE.probabilities, Caries: NaN } }, { probabilities: { ...EXAMPLE.probabilities, Impacted: Infinity } },
    { probabilities: { ...EXAMPLE.probabilities, Impacted: null } }, { probabilities: { ...EXAMPLE.probabilities, Impacted: "0.3" } },
    { probabilities: { ...EXAMPLE.probabilities, Impacted: 1.5 } }]) {
    assert.equal(topClass(bad), null, JSON.stringify(bad));
  }
});

test("region table shows the class, its raw score and the review warning (never 'No reliable class candidate')", () => {
  const info = describeRegion(REGION, { normalised_entropy_ge: 0.3966 });
  assert.equal(info.cls.main, "Caries");
  assert.equal(info.cls.warning, HIGH_UNCERTAINTY_TEXT);
  assert.equal(info.score, "72.6%");
  assert.doesNotMatch(JSON.stringify(info), /No reliable class candidate/);
});

test("region table shows an unavailable state for invalid scores and does not invent a class", () => {
  const info = describeRegion({ ...REGION, candidate_class: { ...EXAMPLE, probabilities: { ...EXAMPLE.probabilities, Caries: NaN } } });
  assert.equal(info.cls.main, "Class scores unavailable");
  assert.equal(info.score, "—");
  assert.equal(describeRegion({ ...REGION, candidate_class: null }).cls.main, "No classifier output");
});
