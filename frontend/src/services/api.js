// Single API client. All pages go through here so error handling is uniform.
export class ApiError extends Error {
  constructor(status, body) {
    const e = (body && body.error) || {};
    super(e.message || `Request failed (${status})`);
    this.status = status;
    this.code = e.code || "request_failed";
    this.hint = e.hint || null;
    this.details = e.details || {};
  }
  get isModelUnavailable() { return this.code === "model_unavailable" || this.code === "no_checkpoint" || this.code === "torch_missing" || this.status === 503; }
  get isDatasetUnavailable() { return this.code === "dataset_unavailable"; }
}

async function request(path, { method = "GET", body, form, raw } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch (err) {
    const e = new ApiError(0, { error: { code: "backend_unreachable", message: "Cannot reach the DentaMind backend.", hint: "Start it with: uvicorn backend.main:app --port 8000" } });
    throw e;
  }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch { /* non-JSON error */ }
    throw new ApiError(res.status, data);
  }
  if (raw) return res;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}

const q = (params = {}) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: (probes = true) => request(`/api/health${q({ probes })}`),
  overview: () => request("/api/overview"),
  settings: () => request("/api/system/settings"),
  datasetStatus: () => request("/api/dataset/status"),
  datasetProcess: (force = true) => request(`/api/dataset/process${q({ force })}`, { method: "POST" }),
  datasetManifest: (p = {}) => request(`/api/dataset/manifest${q(p)}`),
  datasetValidation: () => request("/api/dataset/validation"),
  datasetAudit: () => request("/api/dataset/audit"),
  datasetLeakage: () => request("/api/dataset/leakage"),
  evaluations: () => request("/api/evaluations"),
  images: (p = {}) => request(`/api/images${q(p)}`),
  image: (id) => request(`/api/images/${encodeURIComponent(id)}`),
  imageQuality: (id) => request(`/api/images/${encodeURIComponent(id)}/quality`),
  upload: (file) => { const f = new FormData(); f.append("file", file); return request("/api/images/upload", { method: "POST", form: f }); },
  predict: (image_id) => request("/api/predict", { method: "POST", body: { image_id } }),
  segment: (image_id) => request("/api/segment", { method: "POST", body: { image_id } }),
  explain: (image_id, box) => request("/api/explain", { method: "POST", body: { image_id, box } }),
  analyzeFull: (image_id) => request("/api/analyze/full", { method: "POST", body: { image_id, segmentation: true, uncertainty: true } }),
  uncertaintyImage: (image_id) => request("/api/uncertainty/image", { method: "POST", body: { image_id } }),
  analysis: (id) => request(`/api/analyses/${id}`),
  reviewsQueue: () => request("/api/reviews/queue"),
  reviewSubmit: (body) => request("/api/reviews", { method: "POST", body }),
  reviewList: (p = {}) => request(`/api/reviews${q(p)}`),
  reviewHistory: (image_id, region_id) => request(`/api/reviews/history${q({ image_id, region_id })}`),
  reviewApprove: (ids, approver) => request("/api/reviews/approve", { method: "POST", body: { ids, approver } }),
  reviewReject: (ids, approver) => request("/api/reviews/reject", { method: "POST", body: { ids, approver } }),
  alScorePool: (n, seed = 42) => request(`/api/active-learning/score-pool${q({ n, seed })}`, { method: "POST" }),
  alScoreStatus: (id) => request(`/api/active-learning/score-pool/${id}`),
  uncertaintyScore: (body) => request("/api/uncertainty/score", { method: "POST", body }),
  uncertaintyTable: () => request("/api/uncertainty/table?limit=500"),
  alInfo: () => request("/api/active-learning/info"),
  alPool: () => request("/api/active-learning/pool"),
  alSelect: (body) => request("/api/active-learning/select", { method: "POST", body }),
  alRounds: () => request("/api/active-learning/rounds"),
  alExport: (round_id, push_to_label_studio = false) => request("/api/active-learning/export", { method: "POST", body: { round_id, push_to_label_studio } }),
  annotations: () => request("/api/annotations"),
  annotationConnection: () => request("/api/annotations/connection"),
  annotationImport: (tasks) => request("/api/annotations/import", { method: "POST", body: { tasks } }),
  annotationPull: (project_id) => request("/api/annotations/import-from-label-studio", { method: "POST", body: { project_id } }),
  annotationApprove: (image_ids, reviewer) => request("/api/annotations/approve", { method: "POST", body: { image_ids, reviewer } }),
  annotationReject: (image_ids, reviewer) => request("/api/annotations/reject", { method: "POST", body: { image_ids, reviewer } }),
  annotationRecords: () => request("/api/annotations/records"),
  labelConfig: () => request("/api/annotations/label-config"),
  trainPrereq: (p) => request(`/api/training/prerequisites${q(p)}`),
  trainStart: (cfg) => request("/api/training/start", { method: "POST", body: cfg }),
  trainJobs: () => request("/api/training/jobs"),
  trainStatus: (id) => request(`/api/training/status/${id}`),
  trainStop: (id) => request(`/api/training/stop/${id}`, { method: "POST" }),
  reportGenerate: (body) => request("/api/reports/generate", { method: "POST", body }),
  reports: () => request("/api/reports"),
  report: (id, lang = "en") => request(`/api/reports/${id}?lang=${lang}`),
  reportValidate: (id) => request(`/api/reports/${id}/validate`, { method: "POST" }),
  reportReview: (id, reviewer) => request(`/api/reports/${id}/review`, { method: "POST", body: { reviewer } }),
  experiments: () => request("/api/experiments"),
  experimentSeries: () => request("/api/experiments/series"),
  experimentCompare: (ids) => request(`/api/experiments/compare${q({ ids: ids.join(",") })}`),
  models: () => request("/api/models"),
  modelSelect: (body) => request("/api/models/select", { method: "POST", body }),
  modelPromote: (body) => request("/api/models/promote", { method: "POST", body }),
  modelRollback: (body) => request("/api/models/rollback", { method: "POST", body }),
  modelPromotions: () => request("/api/models/promotions"),
  modelEvidence: (id) => request(`/api/models/evidence?model_id=${encodeURIComponent(id)}`),
  testSetStatus: () => request("/api/integrity/test-set"),
  modelEvaluate: (id) => request(`/api/models/${id}/evaluate`, { method: "POST" }),
};

// Browser download of server-generated or client-generated content.
export function downloadBlob(filename, content, type = "application/json") {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const reportExportUrl = (id, format, lang = "en") => `/api/reports/${id}/export?format=${format}&lang=${lang}`;
export const reviewsExportUrl = (format) => `/api/reviews/export?format=${format}`;
export const experimentsExportUrl = (format) => `/api/experiments/export?format=${format}`;
