import React, { useEffect, useState } from "react";
import { Download, Eye } from "lucide-react";
import PageHeader from "../components/PageHeader";
import ImageUploader from "../components/ImageUploader";
import DentalImageViewer from "../components/DentalImageViewer";
import SegmentationOverlay from "../components/SegmentationOverlay";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { useAppState } from "../hooks/AppState";
import { api, downloadBlob } from "../services/api";
import { ARRAY, PALETTE, fmt } from "../lib/format";

export default function Segmentation() {
  const { imageId, setImageId, segmentation, setSegmentation } = useAppState();
  const imgs = useApi(() => api.images({ source: "all", limit: 200 }), []);
  const info = useApi(() => (imageId ? api.image(imageId) : Promise.resolve(null)), [imageId]);
  const manifest = useApi(() => api.datasetManifest({ which: "main", limit: 2000 }), []);
  const evals = useApi(() => api.evaluations(), []);
  const seg = useAction((id) => api.segment(id));
  const [opacity, setOpacity] = useState(0.5);
  const [selected, setSelected] = useState(null);
  const [sideBySide, setSideBySide] = useState(false);
  const im = info.data;
  const dets = ARRAY(segmentation?.detections).filter((d) => d.mask_rle);
  useEffect(() => setSelected(null), [imageId]);

  const withMasks = manifest.data ? manifest.data.items.filter((r) => r.has_masks).length : null;
  const exportViz = () => {
    if (!im || !segmentation) return;
    downloadBlob(`${im.filename}.segmentation.json`, JSON.stringify({ image_id: im.id, model_version: segmentation.model_version,
      instances: dets.map((d, i) => ({ index: i, box: d.box, score: d.score })) }, null, 1));
  };

  return (
    <div>
      <PageHeader title="Segmentation" subtitle="Instance masks from a trained dental segmentation model. Masks are drawn only from real model output."
        actions={<button className="btn-ghost" disabled={!segmentation} onClick={exportViz}><Download className="h-4 w-4" aria-hidden />Export instances (JSON)</button>} />
      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_300px]">
        <section className="card card-pad space-y-4" aria-label="Image input">
          <ImageUploader onUploaded={(r) => { setImageId(r.id); imgs.reload(); }} />
          <div>
            <label className="label" htmlFor="seg-img">Image</label>
            {imgs.loading ? <LoadingState inline /> : imgs.error ? <ErrorState error={imgs.error} compact onRetry={imgs.reload} /> : (
              <select id="seg-img" className="input" value={imageId || ""} onChange={(e) => e.target.value && setImageId(e.target.value)}>
                <option value="">{imgs.data.total ? "Select an image…" : "No images available"}</option>
                {imgs.data.items.map((i) => <option key={i.id} value={i.id}>{i.filename}{i.is_test_data ? " (test data)" : ""}{i.duplicate_split ? ` - same film as ${i.duplicate_split}-split ${i.duplicate_of}` : ""}</option>)}
              </select>)}
          </div>
          <button className="btn-primary w-full" disabled={!imageId || seg.busy} onClick={async () => { const r = await seg.run(imageId); if (r) setSegmentation(r); }}>
            <Eye className="h-4 w-4" aria-hidden />{seg.busy ? "Segmenting…" : "Run Segmentation"}
          </button>
          <div><label className="label" htmlFor="seg-op">Mask opacity</label><input id="seg-op" type="range" min="0.1" max="1" step="0.05" value={opacity} onChange={(e) => setOpacity(+e.target.value)} className="w-full" /></div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sideBySide} onChange={(e) => setSideBySide(e.target.checked)} />Show original beside segmented</label>
          {seg.error && <ErrorState error={seg.error} compact />}
        </section>

        <section className="min-w-0" aria-label="Segmentation viewer">
          <div className={`grid gap-3 ${sideBySide ? "lg:grid-cols-2" : ""}`}>
            {sideBySide && (
              <div className="card p-3"><p className="label">Original</p>
                <DentalImageViewer src={im?.url} width={im?.width} height={im?.height} heightClass="h-[520px]" alt="Original radiograph" /></div>)}
            <div className="card p-3">
              {sideBySide && <p className="label">Segmented</p>}
              {info.loading && imageId ? <LoadingState /> : (
                <DentalImageViewer src={im?.url} width={im?.width} height={im?.height} heightClass="h-[520px]" onBackgroundClick={() => setSelected(null)} alt="Segmentation result">
                  {dets.length > 0 && <SegmentationOverlay detections={segmentation.detections} width={im.width} height={im.height} opacity={opacity} selected={selected} />}
                </DentalImageViewer>)}
            </div>
          </div>
          {!segmentation && !seg.busy && !seg.error && (
            <div className="mt-3"><EmptyState title="No segmentation yet" message={imageId ? "Press Run Segmentation to run the active instance-segmentation model." : "Select or upload a radiograph first."} /></div>)}
          {seg.busy && <LoadingState label="Running segmentation model…" />}
        </section>

        <section className="space-y-5" aria-label="Instances and evaluation">
          <div className="card card-pad">
            <h2 className="h-section mb-2">Instances</h2>
            {dets.length === 0 ? <p className="text-sm text-muted">No instance masks to list.</p> : (
              <ul className="divide-y divide-slate-100">
                {segmentation.detections.map((d, i) => d.mask_rle && (
                  <li key={i}><button className={`flex w-full items-center justify-between py-1.5 text-left text-sm ${selected === i ? "font-semibold" : ""}`} onClick={() => setSelected(selected === i ? null : i)}>
                    <span className="flex items-center gap-2"><span className="h-3 w-3 rounded-sm" style={{ background: `rgb(${PALETTE[i % PALETTE.length].join(",")})` }} />Instance {i + 1}{d.fdi ? ` · FDI ${d.fdi}` : ""}</span>
                    <span className="text-xs text-muted">score {fmt(d.score, 4)}</span></button></li>))}
              </ul>)}
            {segmentation && <p className="mt-2 text-xs text-muted">Model <span className="font-mono">{segmentation.model_version}</span></p>}
          </div>
          <div className="card card-pad">
            <h2 className="h-section mb-2">Evaluation (measured)</h2>
            {(() => {
              const rows = ARRAY(evals.data?.items).filter((e) => e.task === "segmentation" && (!segmentation || e.model_version === segmentation.model_version));
              if (evals.loading) return <LoadingState inline />;
              if (!rows.length) return <p className="text-sm text-muted">No evaluation report exists for this model yet. Run <code>scripts/evaluate_model.py</code>.</p>;
              return (
                <table className="w-full text-sm"><thead><tr><th className="th">Split</th><th className="th">Mask AP@0.5</th><th className="th">Box mAP</th><th className="th">Images</th></tr></thead>
                  <tbody>{rows.map((e) => (
                    <tr key={e.name}><td className="td">{e.split}{e.split === "test" ? " (locked)" : ""}</td><td className="td">{fmt(e.metrics?.segmentation?.mask_ap50, 3)}</td><td className="td">{fmt(e.metrics?.segmentation?.map, 3)}</td><td className="td">{e.n_images}</td></tr>))}</tbody></table>);
            })()}
            <p className="mt-2 text-xs text-muted">Computed by running the checkpoint on held-out radiographs (mask IoU on a 4x sub-sampled grid). Per-instance scores above are model outputs, not accuracy: the one-class tooth model saturates near 1, so nearly every instance scores &gt; 0.99.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
