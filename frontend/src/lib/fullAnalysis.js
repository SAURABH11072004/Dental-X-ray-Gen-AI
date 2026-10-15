// Maps the server's full-analysis result (regions linked by id) onto the shapes the viewer components already use.
// Index i is the same region everywhere (boxes, masks, class probabilities, numbering), because all of them come from ONE
// regions array produced by the backend - nothing is paired by position across separate calls.

export function toAnalysisShape(r) {
  const names = Object.keys(r.regions.find((g) => g.candidate_class)?.candidate_class?.probabilities || {});
  return {
    image_id: r.image_id, analysis_id: r.analysis_id, model_version: r.models.detection, device: "cuda/cpu (see steps)", duration_s: r.summary.seconds,
    detections: r.regions.map((g) => ({ box: g.box, score: g.detection_score, fdi: g.fdi, fdi_status: g.numbering_status, fdi_confidence: g.fdi_confidence, region_no: g.region_no, label: "tooth",
      candidate: g.candidate_class?.status === "candidate" ? g.candidate_class.label : null, region_id: g.region_id, area: g.mask?.area ?? null })),
    classification: names.length ? {
      model_version: r.models.classification, class_names: names, limitations: r.classification_limitations,
      probabilities: r.regions.map((g) => (g.candidate_class ? names.map((n) => g.candidate_class.probabilities[n]) : null)),
    } : null,
    numbering: { teeth: r.regions.map((g, i) => ({ index: i, fdi: g.fdi, status: g.numbering_status, problems: g.numbering_status === "assigned" ? [] : [g.numbering_status.replace(/_/g, " ")] })) },
    numbering_model: r.numbering_model, regions: r.regions, steps: r.steps, summary: r.summary, models: r.models, uncertainty: r.uncertainty,
  };
}

export function toSegmentationShape(r) {
  if (!r.models.segmentation) return null;
  return {
    image_id: r.image_id, model_version: r.models.segmentation,
    detections: r.regions.map((g) => (g.mask ? { box: g.box, score: g.mask.segmentation_score, mask_rle: g.mask.mask_rle, area: g.mask.area, fdi: g.fdi } : { box: g.box, score: null, mask_rle: null })),
  };
}

export const STEP_LABELS = {
  preprocess: "Preprocess / quality check", detect: "Detect teeth", number: "Number teeth (FDI)", segment: "Segment teeth", match: "Match masks to detections",
  classify: "Classify (candidate class)", classify_tta: "Classifier flip pass", detect_tta: "Detector flip pass", segment_tta: "Segmenter flip pass",
};

export const FLAG_TEXT = {
  high_entropy: "high classifier entropy", unstable_under_flip: "unstable under flip", mask_unstable: "mask unstable", no_matching_mask: "no matching mask",
  low_detection_score: "low detection score", tooth_number_needs_review: "tooth number needs review", unassigned_tooth_number: "tooth number unassigned",
  not_found_on_flipped_image: "not found on flipped image",
};
