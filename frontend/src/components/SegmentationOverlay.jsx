import React, { useMemo } from "react";
import { PALETTE, rleToDataUrl } from "../lib/format";

/** Draws real per-instance masks (decoded from the backend RLE). Never fills boxes. */
export default function SegmentationOverlay({ detections = [], width, height, opacity = 0.5, selected, onSelect, only }) {
  const layers = useMemo(() => detections.map((d, i) => (d.mask_rle ? { i, url: rleToDataUrl(d.mask_rle, PALETTE[i % PALETTE.length]) } : null)).filter(Boolean), [detections]);
  return (
    <g style={{ pointerEvents: "none" }}>
      {layers.map(({ i, url }) => {
        if (only != null && only !== i) return null;
        const dim = selected != null && selected !== i;
        return <image key={i} href={url} x={0} y={0} width={width} height={height} opacity={(dim ? 0.35 : 1) * opacity} />;
      })}
    </g>
  );
}
