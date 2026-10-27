import { fmt, pct } from "./format.js";
import { HIGH_UNCERTAINTY_TEXT, topClass } from "./classResult.js";

/**
 * Regions panel of the X-ray Analysis page. Display only: every label below is derived from fields the backend returns
 * (numbering_status, candidate_class, flags, raw scores); no prediction or score is changed or re-computed.
 * Warnings are kept separate by source - detection, tooth number, candidate class, outline - instead of one generic label.
 */
export function describeRegion(g, thr = {}) {
  const cc = g.candidate_class;
  const tc = topClass(cc);
  const number = g.fdi == null
    ? { main: "Unassigned", sub: "no tooth number", tone: "muted" }
    : g.numbering_status === "assigned"
      ? { main: String(g.fdi), sub: null, tone: "plain" }
      : { main: String(g.fdi), sub: "Needs verification", tone: "warn" };
  const ent = g.uncertainty?.entropy;
  const cls = !cc
    ? { main: "No classifier output", tone: "muted", title: "The region could not be classified (for example, too small to crop)." }
    : !tc
      ? { main: "Class scores unavailable", tone: "warn", title: "The classifier output for this region is missing or invalid, so no class is shown." }
      : tc.highUncertainty
        ? { main: tc.label, tone: "plain", warning: HIGH_UNCERTAINTY_TEXT,
            title: `Highest raw model score of the four trained classes - not a confirmed finding. Classifier entropy ${fmt(ent, 3)}${thr.normalised_entropy_ge != null ? ` ≥ review threshold ${fmt(thr.normalised_entropy_ge, 3)}` : ""}.` }
        : { main: tc.label, tone: "plain", title: "Highest raw model score of the four trained classes - not a confirmed finding." };
  const score = tc ? pct(tc.score, 1) : "—";
  const flags = g.flags || [];
  const chips = [];
  if (flags.includes("low_detection_score")) chips.push({ key: "det", text: `Weak detection ${fmt(g.detection_score, 2)}`, title: `Detection score ${fmt(g.detection_score, 3)} is below ${fmt(thr.detection_score_lt ?? 0.5, 2)}: this box may not be a tooth.` });
  if (flags.includes("not_found_on_flipped_image")) chips.push({ key: "detflip", text: "Not found when flipped", title: "The detector did not find this region on the horizontally flipped image." });
  if (flags.includes("unstable_under_flip")) chips.push({ key: "clsflip", text: "Class unstable under flip", title: "The candidate class changed or shifted when the crop was flipped." });
  if (flags.includes("no_matching_mask")) chips.push({ key: "nomask", text: "No outline", title: "No segmentation outline matched this box." });
  if (flags.includes("mask_unstable")) chips.push({ key: "mask", text: "Outline unstable", title: "The outline changed noticeably on the flipped image." });
  return { number, cls, score, chips };
}
