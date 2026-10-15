// Browser-side performance on the real servers: largest dataset radiograph -> time to image decoded, time to full-analysis table, overlay drawn.
import { chromium } from "playwright-core";
import fs from "node:fs";
const BASE = "http://localhost:5173";
const API = "http://127.0.0.1:8000/api";
const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const items = [];
for (let off = 0; off < 3700; off += 1000) {
  const TOKEN = process.env.DENTAMIND_API_TOKEN || fs.readFileSync("D:/Dentex-Gen Ai/runtime/api_token.txt", "utf8").trim();
  const j = await (await fetch(`${API}/images?source=all&limit=1000&offset=${off}`, { headers: { Authorization: `Bearer ${TOKEN}` } })).json();
  items.push(...j.items);
  if (!j.items.length) break;
}
const biggest = items.filter((i) => i.width && i.height).sort((a, b) => b.width * b.height - a.width * a.height)[0];
const smallest = items.filter((i) => i.width && i.height).sort((a, b) => a.width * a.height - b.width * b.height)[0];
const out = { measured: new Date().toISOString(), images_considered: items.length, largest: { id: biggest.id, w: biggest.width, h: biggest.height }, smallest: { id: smallest.id, w: smallest.width, h: smallest.height } };
for (const [label, im] of [["largest", biggest], ["typical", items.find((i) => i.id === "val_12") || items[5]]]) {
  await page.goto(BASE + "/analysis", { waitUntil: "networkidle" });
  let tUploadMs = null;
  if (label === "largest") {
    // the selector only lists the first page of images: upload a copy of the largest radiograph through the real uploader
    const man = JSON.parse(fs.readFileSync("D:/Dentex-Gen Ai/Data/processed/manifest.json", "utf8"));
    const rows = Array.isArray(man) ? man : man.rows || man.items || [];
    const row = rows.find((r) => (r.image_id || r.id) === im.id);
    const fp = "D:/Dentex-Gen Ai/Data/" + (row.file_path || row.path);
    const tu = Date.now();
    const [up] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/images/upload"), { timeout: 120000 }), page.locator('input[type=file][aria-label="Choose radiograph file"]').setInputFiles(fp)]);
    tUploadMs = Date.now() - tu;
    out[label + "_upload"] = { status: up.status(), ms: tUploadMs, bytes: fs.statSync(fp).size };
    await page.waitForTimeout(1500);
  } else {
    await page.selectOption("#src", im.source === "upload" ? "uploads" : im.source === "test_data" ? "test_data" : "dataset");
    await page.waitForTimeout(1500);
    const opts = await page.locator('select[aria-label="Image"] option').evaluateAll((os) => os.map((o) => ({ v: o.value, t: o.textContent })));
    const target = opts.find((o) => o.v === im.id);
    if (!target) { out[label] = { error: "image not in the first page of the selector", id: im.id }; continue; }
    await page.locator('select[aria-label="Image"]').selectOption(target.v);
  }
  const t0 = Date.now();
  await page.waitForFunction(() => { const i = document.querySelector("img"); return i && i.complete && i.naturalWidth > 0; }, null, { timeout: 60000 });
  const tImg = Date.now() - t0;
  const dims = await page.evaluate(() => { const i = [...document.querySelectorAll("img")].find((x) => x.naturalWidth > 500); return i ? [i.naturalWidth, i.naturalHeight] : null; });
  const t1 = Date.now();
  const [fr] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/analyze/full"), { timeout: 240000 }), page.getByTestId("run-full").click()]);
  const tApi = Date.now() - t1;
  const body = await fr.body();
  await page.waitForSelector('[data-testid="region-table"] tbody tr', { timeout: 60000 });
  await page.waitForSelector('[data-testid="detection-box"]', { timeout: 60000 });
  const tUi = Date.now() - t1;
  const heap = await page.evaluate(() => (performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null));
  out[label] = { id: im.id, size: `${im.width}x${im.height}`, image_decoded_ms: tImg, natural_dims: dims, analyze_full_http_ms: tApi, response_kB: Math.round(body.length / 1024), table_and_overlay_visible_ms: tUi, js_heap_MB: heap, boxes: await page.locator('[data-testid="detection-box"]').count() };
}
fs.writeFileSync("D:/Dentex-Gen Ai/docs/audit_evidence/ui_perf.json", JSON.stringify(out, null, 1));
console.log(JSON.stringify(out));
await browser.close();
