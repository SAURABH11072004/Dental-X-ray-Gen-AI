import React, { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Check, ClipboardCheck, Download, X } from "lucide-react";
import DentalImageViewer from "./DentalImageViewer";
import DetectionOverlay from "./DetectionOverlay";
import EmptyState from "./EmptyState";
import ErrorState from "./ErrorState";
import LoadingState from "./LoadingState";
import StatusBadge from "./StatusBadge";
import { useAction, useApi } from "../hooks/useApi";
import { api, reviewsExportUrl } from "../services/api";
import { FLAG_TEXT } from "../lib/fullAnalysis";
import { fmt, when } from "../lib/format";

const ACTION_TEXT = {
  confirm_candidate: "Confirm candidate class", correct_class: "Correct the class", reject_candidate: "Reject candidate (do not use)",
  set_tooth_number: "Set tooth number", mark_number_unassigned: "Mark tooth number unassigned", specialist_review: "Flag: needs specialist review", unusable_image: "Flag: image unusable",
};
const read = (k) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };

export default function RegionReview() {
  const queue = useApi(() => api.reviewsQueue(), []);
  const list = useApi(() => api.reviewList({ all_revisions: true }), []);
  const [open, setOpen] = useState(null);                      // { image_id, analysis_id }
  const [sel, setSel] = useState(null);                        // region index
  const [reviewer, setReviewer] = useState(read("dm_reviewer"));
  const [approver, setApprover] = useState("");
  const [form, setForm] = useState({ action: "confirm_candidate", corrected_class: "", corrected_fdi: "", notes: "" });
  const [picked, setPicked] = useState([]);
  const [params] = useSearchParams();
  const wantImage = params.get("image");
  useEffect(() => {                                   // arriving from "Review this region": open that image's task if it is in the queue
    if (!open && wantImage && queue.data) { const hit = (queue.data.items || []).find((x) => x.image_id === wantImage); if (hit) setOpen({ image_id: hit.image_id, analysis_id: hit.analysis_id }); }
  }, [wantImage, queue.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const analysis = useApi(() => (open ? api.analysis(open.analysis_id) : Promise.resolve(null)), [open?.analysis_id]);
  const image = useApi(() => (open ? api.image(open.image_id) : Promise.resolve(null)), [open?.image_id]);
  const a = analysis.data;
  const reg = a?.regions?.[sel];
  const hist = useApi(() => (open && reg ? api.reviewHistory(open.image_id, reg.region_id) : Promise.resolve(null)), [open?.image_id, reg?.region_id, list.data]);
  const submit = useAction((b) => api.reviewSubmit(b));
  const decide = useAction((ids, who, ok) => (ok ? api.reviewApprove(ids, who) : api.reviewReject(ids, who)));
  useEffect(() => { try { localStorage.setItem("dm_reviewer", reviewer); } catch { /* storage unavailable */ } }, [reviewer]);
  useEffect(() => { setSel(null); }, [open?.analysis_id]);
  const classes = reg?.candidate_class ? Object.keys(reg.candidate_class.probabilities) : ["Caries", "Deep Caries", "Impacted", "Periapical Lesion"];
  const detections = useMemo(() => (a?.regions || []).map((g) => ({ box: g.box, score: g.detection_score, fdi: g.fdi, fdi_status: g.numbering_status, region_no: g.region_no, label: "" })), [a]);
  const imageLevel = form.action === "unusable_image" || form.action === "specialist_review";
  const reviews = list.data?.items || [];
  const current = reviews.filter((r) => r.is_current);

  const sending = useRef(false);
  async function send() {
    if (sending.current || submit.busy) return;          // a double click must not create two submissions
    sending.current = true;
    try { await send2(); } finally { sending.current = false; }
  }
  async function send2() {
    const body = { image_id: open.image_id, region_id: imageLevel ? null : reg?.region_id, action: form.action, reviewer,
      corrected_class: form.action === "correct_class" ? form.corrected_class : null, corrected_fdi: form.action === "set_tooth_number" ? Number(form.corrected_fdi) : null, notes: form.notes };
    const r = await submit.run(body);
    if (r) { list.reload(true); queue.reload(true); setForm((f) => ({ ...f, notes: "" })); }
  }
  async function decideSel(ok) { const r = await decide.run(picked, approver, ok); if (r) { setPicked([]); list.reload(true); } }
  const canSend = reviewer.trim().length >= 2 && (imageLevel || reg) && (form.action !== "correct_class" || form.corrected_class) && (form.action !== "set_tooth_number" || form.corrected_fdi);

  return (
    <section className="card card-pad space-y-4" aria-labelledby="rv" data-testid="region-review">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 border-b border-slate-100 pb-3">
        <h2 id="rv" className="h-section">Region review</h2>
        <p className="help max-w-4xl flex-1 basis-[28rem]">Pick an image, select a region, and record your decision. Each decision is saved with your name, a timestamp and the model output you saw, and keeps its history; a <b>different</b> named person must approve it. <b>Reviewer names are self-declared and are not identity-verified by the application.</b> Only approved reviews on pool/upload images can ever be used for training, and only through an explicit training option.</p>
      </div>
      <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <div>
          <h3 className="label">Awaiting review{queue.data ? ` (${queue.data.items.length})` : ""}</h3>
          {queue.loading ? <LoadingState inline /> : queue.error ? <ErrorState error={queue.error} compact onRetry={queue.reload} /> : queue.data.items.length === 0 ? (
            <p className="text-sm text-muted">Nothing in the queue. Analyze an image (X-ray Analysis) or score the pool (Active Learning) to create review tasks.</p>) : (
            <ul className="max-h-[32rem] space-y-1.5 overflow-auto pr-1 lg:max-h-[calc(100vh-18rem)]" data-testid="review-queue">
              {queue.data.items.map((q) => (
                <li key={q.analysis_id}><button className={`w-full rounded-lg border px-2.5 py-1.5 text-left text-xs ${open?.analysis_id === q.analysis_id ? "border-teal bg-teal-50" : "border-slate-200 hover:bg-slate-50"}`} onClick={() => setOpen({ image_id: q.image_id, analysis_id: q.analysis_id })}>
                  <span className="block font-mono">{q.image_id}</span><span className="text-muted">{q.n_regions_to_review}/{q.n_regions} regions to review · overall uncertainty {q.combined_score != null ? fmt(q.combined_score, 2) : "n/a"}</span>
                  <span className="mt-0.5 flex gap-1">{(() => { const mine = current.filter((r) => r.image_id === q.image_id); const ap = mine.filter((r) => r.status === "approved").length; return mine.length === 0 ? <StatusBadge tone="warn">Pending</StatusBadge> : <><StatusBadge tone="info">{mine.length} saved</StatusBadge>{ap > 0 && <StatusBadge tone="ok">{ap} approved</StatusBadge>}</>; })()}</span></button></li>))}
            </ul>)}
          {queue.data && <p className="mt-2 text-xs text-muted">{queue.data.ordering}</p>}
        </div>
        <div className="min-w-0">
          {!open ? <EmptyState compact icon={ClipboardCheck} title="No image selected" message="Choose an image from the queue on the left. Its flagged regions appear on the X-ray, with the review form beside it." /> : (analysis.loading || image.loading) ? <LoadingState /> : analysis.error ? <ErrorState error={analysis.error} compact /> : a && (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_290px]">
              <div className="min-w-0">
                <p className="mb-2 flex flex-wrap items-baseline gap-x-3 text-sm"><span className="font-mono font-semibold text-navy">{open.image_id}</span><span className="text-xs text-muted">Boxes are model predictions; select one to review it.</span></p>
                <DentalImageViewer src={image.data?.url} width={image.data?.width} height={image.data?.height} alt={`Radiograph ${open.image_id}`} onBackgroundClick={() => setSel(null)} fitViewport>
                  {(k) => <DetectionOverlay detections={detections} selected={sel} onSelect={setSel} showBoxes showIds showLabels={false} k={k} />}
                </DentalImageViewer>
                <p className="mt-1 text-xs text-muted">Models: {Object.entries(a.models).filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
              </div>
              <div className="space-y-3 text-sm">
                {reg ? (
                  <div className="rounded-lg border border-slate-200 p-2.5" data-testid="review-region">
                    <p className="font-medium">Region {reg.region_no} <span className="font-mono text-xs">id {reg.region_id.split(":")[1]}</span></p>
                    <p className="text-xs">Tooth: {reg.fdi ?? "unassigned"} ({reg.numbering_status.replace(/_/g, " ")})</p>
                    <p className="text-xs">{reg.candidate_class ? (reg.candidate_class.status === "abstained" ? <span className="text-warn">model abstained (too uncertain)</span> : <>Candidate: <b>{reg.candidate_class.label}</b> ({fmt(reg.candidate_class.score, 2)}, uncalibrated)</>) : "no classifier output"}</p>
                    <p className="text-xs text-muted">entropy {fmt(reg.uncertainty.entropy, 2)} · flip {fmt(reg.uncertainty.tta_disagreement, 2)} · mask {fmt(reg.uncertainty.mask_instability, 2)}</p>
                    <div className="mt-1 flex flex-wrap gap-1">{reg.flags.map((f) => <StatusBadge key={f} tone="warn">{FLAG_TEXT[f] || f}</StatusBadge>)}</div>
                  </div>) : <p className="text-xs text-muted">Click a region on the image (or flag the whole image below).</p>}
                <label className="block text-xs text-muted">Your name (recorded, self-declared) <input className="input mt-0.5" value={reviewer} onChange={(e) => setReviewer(e.target.value)} aria-label="Reviewer name" /></label>
                <label className="block text-xs text-muted">Decision
                  <select className="input mt-0.5" value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })} aria-label="Review action">
                    {Object.entries(ACTION_TEXT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                {form.action === "correct_class" && <label className="block text-xs text-muted">Correct class (no “healthy” label exists)
                  <select className="input mt-0.5" value={form.corrected_class} onChange={(e) => setForm({ ...form, corrected_class: e.target.value })}><option value="">Select…</option>{classes.map((c) => <option key={c}>{c}</option>)}</select></label>}
                {form.action === "set_tooth_number" && <label className="block text-xs text-muted">FDI tooth number
                  <input className="input mt-0.5" inputMode="numeric" value={form.corrected_fdi} onChange={(e) => setForm({ ...form, corrected_fdi: e.target.value })} placeholder="e.g. 36" /></label>}
                <label className="block text-xs text-muted">Notes (optional)<input className="input mt-0.5" maxLength={500} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
                <button className="btn-primary w-full" disabled={!canSend || submit.busy} onClick={send} data-testid="review-submit">{submit.busy ? "Saving…" : "Save review"}</button>
                {!canSend && <p className="text-xs text-muted" data-testid="review-hint">{reviewer.trim().length < 2 ? "Enter your name (at least 2 characters) to save." : !imageLevel && !reg ? "Select a region on the image first." : form.action === "correct_class" && !form.corrected_class ? "Choose the correct class." : "Enter the FDI tooth number."} The name is typed in and not identity-verified.</p>}
                {submit.error && <p className="text-xs text-bad" role="alert" data-testid="review-error">{submit.error.message}</p>}
                {submit.result && !submit.error && <p className="text-xs text-ok" role="status">Saved as revision {submit.result.revision}. Status: {submit.result.status === "submitted" ? "saved, waiting for approval by a second named person" : submit.result.status}.</p>}
                {hist.data?.items?.length > 0 && (
                  <div><h4 className="label">History of this region</h4>
                    <ul className="space-y-1 text-xs">{hist.data.items.map((h) => <li key={h.id} className="rounded border border-slate-200 p-1.5">r{h.revision} · {ACTION_TEXT[h.action]}{h.corrected_class ? ` → ${h.corrected_class}` : ""}{h.corrected_fdi ? ` → ${h.corrected_fdi}` : ""} · {h.reviewer} · {when(h.created)} · {h.status}{h.is_current ? "" : " (superseded)"}</li>)}</ul></div>)}
              </div>
            </div>)}
        </div>
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h3 className="label !mb-0">Saved reviews ({current.length} current)</h3>
          <a className="btn-ghost !py-1 text-xs" href={reviewsExportUrl("json")}><Download className="h-3.5 w-3.5" aria-hidden />Approved JSON</a>
          <a className="btn-ghost !py-1 text-xs" href={reviewsExportUrl("csv")}><Download className="h-3.5 w-3.5" aria-hidden />Approved CSV</a>
        </div>
        {current.length === 0 ? <p className="mt-2 text-sm text-muted">No reviews saved yet.</p> : (
          <>
            <div className="mt-2 overflow-x-auto"><table className="w-full text-sm" data-testid="review-table">
              <thead><tr>{["", "Image", "Region", "Decision", "Reviewer", "Status", "Split", "Training use"].map((h) => <th key={h} className="th">{h}</th>)}</tr></thead>
              <tbody>{current.map((r) => (
                <tr key={r.id}><td className="td">{r.status === "submitted" && <input type="checkbox" aria-label={`select ${r.id}`} checked={picked.includes(r.id)} onChange={() => setPicked((p) => (p.includes(r.id) ? p.filter((x) => x !== r.id) : [...p, r.id]))} />}</td>
                  <td className="td font-mono text-xs">{r.image_id}</td><td className="td font-mono text-xs">{r.region_id ? r.region_id.split(":")[1] : "whole image"}</td>
                  <td className="td">{ACTION_TEXT[r.action]}{r.corrected_class ? `: ${r.corrected_class}` : ""}{r.corrected_fdi ? `: ${r.corrected_fdi}` : ""}</td>
                  <td className="td">{r.reviewer}<span className="block text-xs text-muted">self-declared</span></td>
                  <td className="td"><StatusBadge tone={r.status === "approved" ? "ok" : r.status === "rejected" ? "bad" : "neutral"}>{r.status}</StatusBadge></td>
                  <td className="td text-xs">{r.split}</td><td className="td text-xs">{r.usable_for_training ? "eligible once approved" : "never (split/ action)"}</td></tr>))}</tbody></table></div>
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <label className="text-xs text-muted">Approver name (must differ from the reviewer) <input className="input mt-0.5 !w-56" value={approver} onChange={(e) => setApprover(e.target.value)} aria-label="Approver name" /></label>
              <button className="btn-teal" disabled={!picked.length || approver.trim().length < 2 || decide.busy} onClick={() => decideSel(true)}><Check className="h-4 w-4" aria-hidden />Approve selected</button>
              <button className="btn-ghost" disabled={!picked.length || approver.trim().length < 2 || decide.busy} onClick={() => decideSel(false)}><X className="h-4 w-4" aria-hidden />Reject selected</button>
            </div>
            {decide.error && <p className="mt-1 text-xs text-bad" role="alert">{decide.error.message}</p>}
          </>)}
      </div>
    </section>
  );
}
