import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, FileText, Flame, Image as ImageIcon, Play, RefreshCw, Sparkles } from "lucide-react";
import PageHeader from "../components/PageHeader";
import ImageUploader from "../components/ImageUploader";
import DentalImageViewer from "../components/DentalImageViewer";
import DetectionOverlay, { OverlayLegend, regionLabel } from "../components/DetectionOverlay";
import SegmentationOverlay from "../components/SegmentationOverlay";
import PredictionInspector from "../components/PredictionInspector";
import RegionTable from "../components/RegionTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useApi, useAction } from "../hooks/useApi";
import { useAppState } from "../hooks/AppState";
import { usePrefs } from "../lib/prefs";
import { useMedia } from "../lib/useMedia";
import { api } from "../services/api";
import { FLAG_TEXT, STEP_LABELS, toAnalysisShape, toSegmentationShape } from "../lib/fullAnalysis";
import { fmt, mb } from "../lib/format";

const tone = (s) => (s === "ok" || s === "skipped" ? "ok" : s === "unavailable" ? "warn" : "bad");

const Step = ({ n }) => <span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-navy text-[11px] font-bold text-white" aria-hidden>{n}</span>;

/** Shown in place of the viewer until an X-ray is chosen: exactly what to do, without a large empty dark box. */
function EmptyViewer() {
  return (
    <div className="max-w-md text-center">
      <ImageIcon className="mx-auto mb-2 h-8 w-8 text-slate-400" aria-hidden />
      <p className="font-semibold text-navy">No X-ray selected yet</p>
      <ol className="mt-2 space-y-1 text-left text-sm text-slate-600">
        <li><b>1.</b> Drop a panoramic X-ray (PNG or JPEG) on the left, or pick an existing image.</li>
        <li><b>2.</b> Press <b>Analyze X-ray</b>.</li>
        <li><b>3.</b> Select any box or table row to see that tooth's details.</li>
      </ol>
    </div>
  );
}

export default function Analysis() {
  const nav = useNavigate();
  const { imageId, setImageId, analysis, setAnalysis, segmentation, setSegmentation, setLastReportId } = useAppState();
  const [prefs, setPrefs] = usePrefs();
  const wide = useMedia("(min-width: 1024px)");
  const [source, setSource] = useState("all");
  const imgs = useApi(() => api.images({ source, limit: 200 }), [source]);
  const info = useApi(() => (imageId ? api.image(imageId) : Promise.resolve(null)), [imageId]);
  const quality = useApi(() => (imageId ? api.imageQuality(imageId) : Promise.resolve(null)), [imageId]);
  const [showBoxes, setShowBoxes] = useState(true);
  const [selected, setSelected] = useState(null);
  const [explain, setExplain] = useState(null);
  const [opacity, setOpacity] = useState(0.5);
  const [heat, setHeat] = useState(0.7);
  const [reportId, setReportId] = useState(null);
  const full = useAction((id) => api.analyzeFull(id));
  const exp = useAction((id, box) => api.explain(id, box));
  const rep = useAction((body) => api.reportGenerate(body));

  useEffect(() => { setSelected(null); setExplain(null); setReportId(null); }, [imageId]);
  const im = info.data;
  const active = analysis && analysis.image_id === imageId && analysis.regions ? analysis : null;
  const segActive = segmentation && segmentation.image_id === imageId ? segmentation : null;
  const hasMasks = useMemo(() => !!(segActive?.detections || []).some((d) => d.mask_rle), [segActive]);
  const regions = active?.regions;
  const qFlags = quality.data?.flags || im?.quality?.flags || [];
  const modelBlocker = [full.error, exp.error].find((e) => e?.isModelUnavailable);
  const otherError = [full.error, exp.error, rep.error].find((e) => e && !e.isModelUnavailable);
  const selReg = regions?.[selected];

  async function analyze() {
    const r = await full.run(imageId);
    if (r) { setAnalysis(toAnalysisShape(r)); setSegmentation(toSegmentationShape(r)); setSelected(null); setExplain(null); setReportId(null); }
  }
  async function explainSel() { const r = await exp.run(imageId, active.detections[selected].box); if (r) setExplain(r); }
  async function makeReport() {
    const r = await rep.run({ analysis_id: active.analysis_id, mode: "auto" });
    if (r) { setLastReportId(r.report.report_id); setReportId(r.report.report_id); nav("/reports?id=" + r.report.report_id); }
  }
  const uploader = (
    <>
      <ImageUploader showInfo={false} onUploaded={(r) => { setImageId(r.id); imgs.reload(); }} />
      <div>
        <label className="label" htmlFor="src">Or choose an existing image</label>
        <select id="src" className="input mb-2" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="all">All sources</option><option value="uploads">My uploads</option><option value="dataset">Main dataset</option><option value="test_data">Test data (unlabeled)</option>
        </select>
        {imgs.loading ? <LoadingState inline /> : imgs.error ? <ErrorState error={imgs.error} compact onRetry={imgs.reload} /> : (
          <select className="input" aria-label="Image" value={imageId || ""} onChange={(e) => e.target.value && setImageId(e.target.value)}>
            <option value="">{imgs.data.total ? "Select an image…" : "No images available"}</option>
            {imgs.data.items.map((i) => <option key={i.id} value={i.id}>{i.filename}{i.is_test_data ? " (test data)" : ""}{i.duplicate_split ? ` - same film as ${i.duplicate_split}-split ${i.duplicate_of}` : ""}</option>)}
          </select>)}
      </div>
    </>
  );
  const detailRef = useRef(null);
  useEffect(() => { if (!wide && selected != null) detailRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [selected, wide]);
  const pickRegion = (i) => setSelected(selected === i ? null : i);

  return (
    <div>
      <PageHeader title="X-ray Analysis" subtitle="Choose or upload a panoramic X-ray, run the trained models, then inspect each detected tooth. Every mark is a model prediction for a qualified person to review." />
      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)] lg:grid-rows-[auto_1fr] lg:items-start xl:grid-cols-[320px_minmax(0,1fr)]">
        {/* A. image and controls */}
        <section className="contents" aria-label="Image and controls">
          <div className="card card-pad order-1 flex flex-col gap-4 lg:col-start-1 lg:row-start-1">
            <div className="order-1 space-y-2 lg:order-3 lg:border-t lg:border-slate-100 lg:pt-4">
              <p className="hidden text-xs font-semibold uppercase tracking-wide text-navy lg:block"><Step n="2" />Run the models</p>
              {active ? (
                <div className="space-y-2">
                  <p className="flex items-center gap-2 text-sm" role="status"><StatusBadge tone="ok">Analysis ready</StatusBadge><span className="text-xs text-muted">{regions.length} regions · {active.summary.seconds}s</span></p>
                  <button className="btn-ghost w-full" disabled={full.busy} onClick={analyze} data-testid="rerun"><RefreshCw className="h-4 w-4" aria-hidden />{full.busy ? "Analyzing…" : "Analyze again"}</button>
                </div>
              ) : (
                <button className="btn-primary w-full" disabled={!imageId || full.busy} onClick={analyze} data-testid="run-full"><Play className="h-4 w-4" aria-hidden />{full.busy ? "Analyzing…" : "Analyze X-ray"}</button>)}
              {!imageId && <p className="text-xs text-muted">Choose or upload an X-ray to enable analysis.</p>}
              <p className="text-xs text-muted">Your original file is never modified.</p>
            </div>
            {im && (
              <dl className="order-2 grid grid-cols-2 gap-1 text-xs" data-testid="image-info">
                <dt className="text-muted">Image</dt><dd className="truncate text-right" title={im.filename}>{im.filename}</dd>
                <dt className="text-muted">Dimensions</dt><dd className="text-right">{im.width} × {im.height} px</dd>
                <dt className="text-muted">File size</dt><dd className="text-right">{im.size_bytes != null ? mb(im.size_bytes) : "unknown"}</dd>
                <dt className="text-muted">Image quality</dt>
                <dd className="text-right" data-testid="quality">{quality.loading ? "checking…" : qFlags.length ? <span className="text-warn">{qFlags.map((f) => f.replace(/_/g, " ")).join(", ")}</span> : <span className="text-ok">no warnings</span>}</dd>
              </dl>)}
            <div className="order-3 lg:order-1">
              {wide ? <div className="space-y-3"><p className="text-xs font-semibold uppercase tracking-wide text-navy"><Step n="1" />Choose an X-ray</p>{uploader}</div> : (
                <details open={!imageId} data-testid="change-image">
                  <summary className="cursor-pointer py-1 text-sm font-medium text-teal">{imageId ? "Change image" : "Choose an image"}</summary>
                  <div className="mt-3 space-y-4">{uploader}</div>
                </details>)}
            </div>
          </div>

          <div className="card card-pad order-3 lg:order-none lg:col-start-1 lg:row-start-2">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-navy"><Step n="3" />Show on image</h3>
            <ul className="space-y-1.5 text-sm">
              <li><label className="flex items-center gap-2" title={active ? "" : "Available after an analysis"}><input type="checkbox" checked={showBoxes} disabled={!active} onChange={(e) => setShowBoxes(e.target.checked)} /> Region boxes</label></li>
              <li><label className="flex items-center gap-2" title={active ? "" : "Available after an analysis"}><input type="checkbox" checked={prefs.showIds} disabled={!active} onChange={(e) => setPrefs({ showIds: e.target.checked })} /> Tooth numbers / region labels</label></li>
              <li><label className="flex items-center gap-2" title={active ? "" : "Available after an analysis"}><input type="checkbox" checked={prefs.showClasses} disabled={!active} onChange={(e) => setPrefs({ showClasses: e.target.checked })} /> Candidate classes</label></li>
              <li><label className={`flex items-center gap-2 ${hasMasks ? "" : "text-slate-500"}`} title={hasMasks ? "" : "No segmentation masks yet"}><input type="checkbox" checked={prefs.showMasks && hasMasks} disabled={!hasMasks} onChange={(e) => setPrefs({ showMasks: e.target.checked })} /> Segmentation masks</label></li>
            </ul>
            {hasMasks && prefs.showMasks && <div className="mt-3"><label className="label" htmlFor="op">Mask opacity</label><input id="op" type="range" min="0.1" max="1" step="0.05" value={opacity} onChange={(e) => setOpacity(+e.target.value)} className="w-full" /></div>}
            {explain && <div className="mt-3"><label className="label" htmlFor="hop">Heatmap opacity</label><input id="hop" type="range" min="0.1" max="1" step="0.05" value={heat} onChange={(e) => setHeat(+e.target.value)} className="w-full" /></div>}
          </div>
        </section>

        {/* B. viewer, C. region list and inspector */}
        <section aria-label="Image viewer and results" className="order-2 min-w-0 space-y-4 lg:order-none lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <div className="card p-3 sm:p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-1">
              <h2 className="min-w-0 truncate text-base font-semibold text-navy" title={im?.filename}>{im ? im.filename : "No X-ray selected"}</h2>
              <p className="text-xs text-muted">{active ? "Boxes, numbers and classes are model predictions, not confirmed findings." : imageId ? "Press Analyze X-ray to run the trained models on this image." : "Choose an X-ray on the left to begin."}</p>
            </div>
            {info.loading && imageId ? <LoadingState /> : (
              <div className="relative">
                <DentalImageViewer src={im?.url} width={im?.width} height={im?.height} onBackgroundClick={() => setSelected(null)} alt={im ? `Radiograph ${im.filename}` : "No radiograph selected"}
                  fitViewport emptyContent={<EmptyViewer />}>
                  {(k) => (<>
                    {prefs.showMasks && hasMasks && <SegmentationOverlay detections={segActive.detections} width={im.width} height={im.height} opacity={opacity} selected={selected} />}
                    {explain && <image href={`data:image/png;base64,${explain.heatmap_png_base64}`} x={explain.box[0]} y={explain.box[1]} width={explain.box[2] - explain.box[0]} height={explain.box[3] - explain.box[1]} opacity={heat} />}
                    {active && <DetectionOverlay width={im.width} height={im.height} detections={active.detections} selected={selected} onSelect={setSelected} showBoxes={showBoxes} showIds={prefs.showIds} showLabels={prefs.showClasses} k={k} />}
                  </>)}
                </DentalImageViewer>
                {full.busy && (
                  <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-white/70" role="status" aria-live="polite" data-testid="analyzing">
                    <LoadingState inline label="Analyzing… the first run also loads the models" />
                  </div>)}
              </div>)}
            {active && <div className="mt-3"><OverlayLegend showClasses={prefs.showClasses} /></div>}
          </div>

          {active && (
            <div className="card card-pad" data-testid="summary">
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-sm"><b>{active.summary.n_review_required}</b> of <b>{regions.length}</b> regions are recommended for human review. {active.summary.n_numbered} of {regions.length} have a tooth number; {active.summary.n_with_mask} have a segmentation mask.</p>
                <div className="ml-auto flex flex-wrap gap-2">
                  <button className="btn-ghost" disabled={selected == null || !selReg?.candidate_class || exp.busy} title={selected == null ? "Select a region first" : !selReg?.candidate_class ? "This region has no classifier output" : ""} onClick={explainSel}><Flame className="h-4 w-4" aria-hidden />{exp.busy ? "Working…" : "Show attention heatmap"}</button>
                  <button className="btn-teal" disabled={rep.busy} onClick={makeReport} data-testid="make-report"><FileText className="h-4 w-4" aria-hidden />{rep.busy ? "Generating…" : reportId ? "Generate another report" : "Generate report"}</button>
                </div>
              </div>
              {qFlags.length > 0 && <p className="mt-2 flex items-center gap-1.5 text-xs text-warn"><AlertTriangle className="h-3.5 w-3.5" aria-hidden />Image-quality warning: {qFlags.map((f) => f.replace(/_/g, " ")).join(", ")}. This is separate from model uncertainty.</p>}
              {active.steps?.some((s) => s.status !== "ok" && s.status !== "skipped") && <p className="mt-2 text-xs text-warn">Some steps did not complete, so results that depend on them are absent (never estimated). Details below.</p>}
              <details className="mt-2 text-xs" data-testid="steps-details">
                <summary className="cursor-pointer text-teal">How this analysis ran</summary>
                <ol className="mt-2 grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3" aria-label="Pipeline steps" data-testid="pipeline-steps">
                  {active.steps.map((s) => (
                    <li key={s.step} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 px-2.5 py-1.5" title={s.message}>
                      <span>{STEP_LABELS[s.step] || s.step}</span><StatusBadge tone={tone(s.status)}>{s.status}</StatusBadge></li>))}
                </ol>
                <p className="mt-2 text-muted">Detector <span className="font-mono">{active.model_version}</span></p>
              </details>
            </div>)}

          {modelBlocker && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm" role="alert">
              <p className="font-semibold text-amber-900"><Sparkles className="mr-1 inline h-4 w-4" aria-hidden />A required model is not available</p>
              <p className="mt-1 text-amber-900">{modelBlocker.message}</p>{modelBlocker.hint && <p className="mt-1 text-amber-900">{modelBlocker.hint}</p>}
            </div>)}
          {otherError && <ErrorState error={otherError} compact />}

          {active && (
            <div className="grid gap-4 min-[1800px]:grid-cols-[minmax(0,1fr)_minmax(340px,400px)]">
              <RegionTable active={active} selected={selected} onPick={pickRegion}
                onReview={(i) => { setSelected(i); detailRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }} />
              <aside ref={detailRef} className={`card card-pad h-fit scroll-mt-4 lg:order-none ${selected != null ? "order-first" : ""}`} aria-label="Region details">
                <h2 className="h-section mb-3">Region details</h2>
                <PredictionInspector analysis={active} selected={selected} reportId={reportId} />
                {explain && <p className="mt-3 border-t border-slate-100 pt-3 text-xs text-muted">Heatmap ({explain.method}) for “{explain.target_class}”. {explain.caveat}</p>}
              </aside>
            </div>)}
          {!active && !full.busy && imageId && <p className="note">Press <b>Analyze X-ray</b> to run the trained models on this image.</p>}
        </section>
      </div>
    </div>
  );
}
