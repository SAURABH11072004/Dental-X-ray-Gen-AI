import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Maximize2, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";

/**
 * Zoom/pan viewer. The overlay <svg> uses the image's own pixel coordinate system (viewBox = natural size) and sits in
 * the same transformed layer as the <img>, so boxes and masks stay aligned at every zoom level.
 * `children` may be a function receiving the current zoom factor (to keep label sizes constant on screen).
 */
export default function DentalImageViewer({ src, width, height, children, heightClass = "h-[540px]", autoHeight = true, alt = "Radiograph", onBackgroundClick, canvasRef,
  fitViewport = false, emptyContent = null }) {
  const wrap = useRef(null);
  const [view, setView] = useState({ k: 1, x: 0, y: 0 });
  const drag = useRef(null);
  const [boxH, setBoxH] = useState(null);

  // Container height follows the image's aspect ratio (panoramic X-rays are ~2:1), so the image fills the width instead of
  // floating in a tall dark box. Pixels are never stretched: the <img> keeps its natural aspect ratio at every zoom.
  // With `fitViewport`, the height is also capped by the room left below the viewer's top edge, so the whole X-ray is visible
  // without scrolling on laptop screens.
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!autoHeight || !el || !width || !height) { setBoxH(null); return undefined; }
    const calc = () => {
      const room = fitViewport ? window.innerHeight - Math.max(el.getBoundingClientRect().top, 0) - 96 : window.innerHeight * 0.72;
      setBoxH(Math.round(Math.min(Math.max((el.clientWidth * height) / width, 260), Math.max(room, 320), window.innerHeight * 0.78)));
    };
    calc();
    const ro = new ResizeObserver(calc);
    ro.observe(el);
    window.addEventListener("resize", calc);
    return () => { ro.disconnect(); window.removeEventListener("resize", calc); };
  }, [autoHeight, width, height, fitViewport]);

  const fit = useCallback(() => {
    const el = wrap.current;
    if (!el || !width || !height) return;
    const k = Math.min(el.clientWidth / width, el.clientHeight / height);
    setView({ k, x: (el.clientWidth - width * k) / 2, y: (el.clientHeight - height * k) / 2 });
  }, [width, height]);

  useEffect(() => { fit(); }, [fit, src, boxH]);
  useEffect(() => {
    const onResize = () => fit();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [fit]);

  const zoomAt = useCallback((factor, cx, cy) => {
    setView((v) => {
      const k = Math.min(Math.max(v.k * factor, 0.02), 12);
      const f = k / v.k;
      return { k, x: cx - (cx - v.x) * f, y: cy - (cy - v.y) * f };
    });
  }, []);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return undefined;
    const onWheel = (e) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt, src]);           // re-attach when the element changes (empty state -> image)

  const center = () => { const r = wrap.current.getBoundingClientRect(); return [r.width / 2, r.height / 2]; };
  if (!src && emptyContent) {
    // compact, light empty state instead of a large dark box when nothing is selected yet
    return <div ref={wrap} className="flex min-h-[260px] w-full items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6" role="img" aria-label={alt}>{emptyContent}</div>;
  }
  const btn = "rounded-md bg-white/90 p-2.5 lg:p-1.5 text-navy shadow hover:bg-white disabled:cursor-not-allowed disabled:opacity-50";
  const noImg = src ? undefined : "Select an image first";

  return (
    <div ref={wrap} className={`relative ${boxH ? "" : heightClass} w-full overflow-hidden rounded-xl bg-slate-900 select-none touch-none`}
      style={{ cursor: drag.current ? "grabbing" : "grab", ...(boxH ? { height: boxH } : {}) }}
      onPointerDown={(e) => { drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false }; }}
      onPointerMove={(e) => {
        const d = drag.current; if (!d) return;
        const dx = e.clientX - d.x, dy = e.clientY - d.y;
        // capture only once a real drag starts: capturing on pointer-down would retarget the click to this container,
        // so clicking a region box on the image could never select it
        if (!d.moved && Math.abs(dx) + Math.abs(dy) > 3) { d.moved = true; e.currentTarget.setPointerCapture?.(e.pointerId); }
        setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
      }}
      onPointerUp={(e) => {
        const d = drag.current; drag.current = null;
        // a plain click on empty image area clears the selection; a click on a region box is handled by the box itself
        if (d && !d.moved && !e.target.closest?.('[data-testid="detection-box"]')) onBackgroundClick?.();
      }}
      onPointerLeave={() => { if (drag.current && !drag.current.moved) drag.current = null; }}
      role="img" aria-label={alt}
    >
      {src ? (
        <div ref={canvasRef} style={{ position: "absolute", left: 0, top: 0, width, height, transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`, transformOrigin: "0 0" }}>
          <img src={src} width={width} height={height} alt="" draggable={false} style={{ display: "block", width, height, maxWidth: "none" }} />
          <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} style={{ position: "absolute", left: 0, top: 0 }}>
            {typeof children === "function" ? children(view.k) : children}
          </svg>
        </div>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">Select or upload a radiograph to begin</div>
      )}
      <div className="absolute right-3 top-3 flex flex-col gap-1.5" onPointerDown={(e) => e.stopPropagation()}>
        <button className={btn} disabled={!src} title={noImg || "Zoom in"} aria-label="Zoom in" onClick={() => zoomAt(1.3, ...center())}><ZoomIn className="h-4 w-4" /></button>
        <button className={btn} disabled={!src} title={noImg || "Zoom out"} aria-label="Zoom out" onClick={() => zoomAt(1 / 1.3, ...center())}><ZoomOut className="h-4 w-4" /></button>
        <button className={btn} disabled={!src} aria-label="Fit to screen" title={noImg || "Fit to screen"} onClick={fit}><Maximize2 className="h-4 w-4" /></button>
        <button className={btn} disabled={!src} aria-label="Reset view to 100%" title={noImg || "Reset to 100%"} onClick={() => setView({ k: 1, x: 0, y: 0 })}><RotateCcw className="h-4 w-4" /></button>
      </div>
      <div className="absolute bottom-2 left-3 rounded bg-black/50 px-2 py-0.5 text-xs text-white">{Math.round(view.k * 100)}%</div>
    </div>
  );
}
