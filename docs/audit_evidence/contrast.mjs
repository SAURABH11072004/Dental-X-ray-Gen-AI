// WCAG 2.x contrast measurement of every visible text element (real DOM, real computed colours). Writes docs/audit_evidence/contrast.json
import { chromium } from "playwright-core";
import fs from "node:fs";
const BASE = "http://localhost:5173";
const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();

const measure = () => page.evaluate(() => {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(",").map((x) => parseFloat(x)); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const over = (f, b) => ({ r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 });
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (el) => { let stack = []; for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e); const c = parse(cs.backgroundColor); if (cs.backgroundImage !== "none") return null; if (c && c.a > 0) { stack.push(c); if (c.a === 1) break; } } let base = { r: 255, g: 255, b: 255, a: 1 }; for (const c of stack.reverse()) base = over(c, base); return base; };
  const out = new Map();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = n.textContent.trim(); if (!t) continue;
    const el = n.parentElement; if (!el || el.closest("svg, script, style, option")) continue;
    const cs = getComputedStyle(el); if (cs.visibility === "hidden" || cs.display === "none" || +cs.opacity === 0) continue;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
    let fg = parse(cs.color); const bg = bgOf(el); if (!fg || !bg) continue;
    let o = 1; for (let e = el; e; e = e.parentElement) o *= +getComputedStyle(e).opacity; fg = over({ ...fg, a: fg.a * o }, bg);
    const L1 = lum(fg), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700; const large = px >= 24 || (px >= 18.66 && bold);
    const need = large ? 3 : 4.5;
    const disabled = el.closest("[disabled], [aria-disabled=true]") != null;
    if (ratio < need && !disabled) { const key = `${cs.color}|${JSON.stringify(bg)}|${px}`; if (!out.has(key)) out.set(key, { ratio: +ratio.toFixed(2), need, color: cs.color, bg: `rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`, px, sample: t.slice(0, 40), cls: (el.className || "").toString().slice(0, 70), tag: el.tagName }); }
  }
  return [...out.values()];
});

const all = {};
const visit = async (name, fn) => { await fn(); await page.waitForTimeout(900); all[name] = await measure(); console.log(name.padEnd(22), all[name].length, "failing combinations"); };
await visit("home", () => page.goto(BASE + "/", { waitUntil: "networkidle" }));
await visit("analysis-empty", () => page.goto(BASE + "/analysis", { waitUntil: "networkidle" }));
await visit("analysis-results", async () => {
  await page.locator('input[type=file][aria-label="Choose radiograph file"]').setInputFiles("D:/Dentex-Gen Ai/Data/validation_data/quadrant_enumeration_disease/xrays/val_12.png");
  await page.waitForTimeout(1500); await page.getByTestId("run-full").click();
  await page.waitForSelector('[data-testid="region-table"] tbody tr', { timeout: 120000 });
  await page.locator('[data-testid="region-table"] tbody tr').nth(2).click();
});
await visit("report", async () => {
  await page.getByTestId("make-report").click(); await page.waitForSelector('[data-testid="localized-report"]', { timeout: 60000 });
  await page.selectOption('select[aria-label="Report language"]', "hi");
});
await visit("reports-list", () => page.goto(BASE + "/reports", { waitUntil: "networkidle" }));
await visit("review", () => page.goto(BASE + "/review", { waitUntil: "networkidle" }));
await visit("about", () => page.goto(BASE + "/about", { waitUntil: "networkidle" }));
await visit("settings", () => page.goto(BASE + "/settings", { waitUntil: "networkidle" }));
for (const r of ["/uncertainty", "/active-learning", "/annotations", "/training", "/experiments", "/models", "/segmentation"]) await visit("research" + r, () => page.goto(BASE + r, { waitUntil: "networkidle" }));
const flat = Object.entries(all).flatMap(([p, l]) => l.map((x) => ({ page: p, ...x })));
const dedup = new Map(); for (const f of flat) { const k = `${f.color}|${f.bg}|${f.px}`; if (!dedup.has(k)) dedup.set(k, { ...f, pages: [f.page] }); else dedup.get(k).pages.push(f.page); }
const summary = [...dedup.values()].sort((a, b) => a.ratio - b.ratio);
const enduser = summary.filter((s) => s.pages.some((p) => !p.startsWith("research")));
fs.writeFileSync("D:/Dentex-Gen Ai/docs/audit_evidence/contrast.json", JSON.stringify({ measured: new Date().toISOString(), rule: "WCAG 2.x AA: 4.5:1 normal text, 3:1 large text (>=24px or >=18.66px bold); disabled controls exempt", unique_failing_combinations_all_pages: summary.length, failing_on_end_user_pages: enduser.length, failures: summary }, null, 1));
console.log("TOTAL unique failing combinations:", summary.length, "| on end-user pages:", enduser.length);
for (const s of summary.slice(0, 25)) console.log(`${s.ratio} (need ${s.need}) ${s.color} on ${s.bg} ${s.px}px '${s.sample}' <${s.tag} ${s.cls}> pages=${[...new Set(s.pages)].join(",")}`);
await browser.close();
