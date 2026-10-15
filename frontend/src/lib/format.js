export const fmt = (v, d = 3) => (v === null || v === undefined || Number.isNaN(v) ? "N/A" : Number(v).toFixed(d));
export const pct = (v, d = 0) => (v === null || v === undefined ? "N/A" : `${(v * 100).toFixed(d)}%`);
export const when = (iso) => { if (!iso) return "—"; const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(); };
export const mb = (bytes) => `${(bytes / 1048576).toFixed(1)} MB`;
export const ARRAY = (v) => (Array.isArray(v) ? v : []);

// Decode the backend RLE (row-major, runs alternate 0/1 starting with 0) to an RGBA canvas data-URL.
export function rleToDataUrl(rle, [r, g, b], alpha = 255) {
  const [h, w] = rle.size;
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d");
  const img = ctx.createImageData(w, h);
  let pos = 0, val = false;
  for (const run of rle.counts) {
    if (val) for (let i = pos; i < pos + run; i++) { const o = i * 4; img.data[o] = r; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = alpha; }
    pos += run; val = !val;
  }
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL("image/png");
}

export const PALETTE = [[15, 139, 141], [217, 119, 6], [124, 58, 237], [220, 76, 76], [22, 133, 107], [37, 99, 235], [219, 39, 119], [101, 163, 13]];
