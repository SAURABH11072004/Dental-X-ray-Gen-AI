import React, { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { api } from "../services/api";
import { mb } from "../lib/format";
import ErrorState from "./ErrorState";
import LoadingState from "./LoadingState";

const OK_TYPES = ["image/png", "image/jpeg"];

export default function ImageUploader({ onUploaded, maxMb = 25, showInfo = true }) {
  const input = useRef(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);

  async function handle(file) {
    setError(null);
    if (!file) return;
    if (!OK_TYPES.includes(file.type)) { setError(new Error("Unsupported file type. Please choose a PNG or JPEG radiograph.")); return; }
    if (file.size > maxMb * 1048576) { setError(new Error(`File is ${mb(file.size)}; the limit is ${maxMb} MB.`)); return; }
    setBusy(true);
    try {
      const rec = await api.upload(file);
      setInfo({ ...rec, bytes: file.size });
      onUploaded?.(rec);
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files?.[0]); }}
        className={`flex items-center gap-3 rounded-xl border-2 border-dashed p-3 text-left transition-colors ${drag ? "border-teal bg-teal-50" : "border-slate-300 bg-white"}`}
      >
        <UploadCloud className="h-7 w-7 shrink-0 text-teal" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-navy">Drop a panoramic X-ray here</p>
          <p className="text-xs text-muted">PNG or JPEG · up to {maxMb} MB</p>
        </div>
        <button className="btn-ghost shrink-0 !px-3 !py-1.5" onClick={() => input.current?.click()} disabled={busy}>Browse</button>
        <input ref={input} type="file" accept="image/png,image/jpeg" className="hidden" aria-label="Choose radiograph file" onChange={(e) => handle(e.target.files?.[0])} />
      </div>
      {busy && <div className="mt-3"><LoadingState inline label="Uploading and validating…" /></div>}
      {error && <div className="mt-3"><ErrorState error={error} compact /></div>}
      {showInfo && info && !busy && (
        <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          <dt className="text-muted">Dimensions</dt><dd className="text-right">{info.width} × {info.height} px</dd>
          <dt className="text-muted">File size</dt><dd className="text-right">{mb(info.bytes)}</dd>
          <dt className="text-muted">Quality</dt>
          <dd className="text-right">{info.quality?.flags?.length ? <span className="text-warn">{info.quality.flags.join(", ").replace(/_/g, " ")}</span> : <span className="text-ok">no warnings</span>}</dd>
          {info.duplicate && <><dt className="text-muted">Note</dt><dd className="text-right">already uploaded</dd></>}
        </dl>
      )}
    </div>
  );
}
