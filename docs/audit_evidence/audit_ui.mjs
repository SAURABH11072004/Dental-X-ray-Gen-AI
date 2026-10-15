// Browser audit of the real Vite frontend + real FastAPI backend (Edge, headless). Writes docs/audit_evidence/ui_audit.json
import { chromium } from "playwright-core";
import fs from "node:fs";

const BASE = "http://localhost:5173";
const OUT = "D:/Dentex-Gen Ai/docs/audit_evidence";
const SHOTS = OUT + "/shots";
fs.mkdirSync(SHOTS, { recursive: true });
const results = [];
const rec = (id, area, input, expected, actual, ok, note = "") => {
  results.push({ id, area, input, expected, actual: String(actual).slice(0, 400), result: ok === true ? "PASS" : ok === "partial" ? "PARTIAL" : ok === "blocked" ? "BLOCKED" : "FAIL", note });
  console.log(`${results.at(-1).result.padEnd(7)} ${id.padEnd(8)} ${input.slice(0, 70).padEnd(70)} -> ${String(actual).slice(0, 110)}`);
};

const browser = await chromium.launch({ executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
const consoleErrs = [], badHttp = [], reqFail = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrs.push(m.text().slice(0, 200)); });
page.on("pageerror", (e) => consoleErrs.push("pageerror " + String(e).slice(0, 200)));
page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) badHttp.push(`${r.request().method()} ${r.status()} ${r.url().replace(BASE, "")}`); });
page.on("requestfailed", (r) => reqFail.push(`${r.method()} ${r.url().replace(BASE, "")} ${r.failure()?.errorText}`));

// ------------------------------------------------------------------ A. every route renders, no console errors, controls enumerated
const ROUTES = [["/", "Home/dashboard"], ["/analysis", "X-ray analysis"], ["/segmentation", "Tooth segmentation"], ["/uncertainty", "Uncertainty"], ["/active-learning", "Active learning"],
  ["/annotations", "Annotations"], ["/reports", "Reports"], ["/review", "Review Findings"], ["/training", "Training"], ["/experiments", "Experiments"], ["/models", "Model registry"], ["/settings", "Settings/limitations"], ["/about", "About"], ["/no-such-page", "Unknown route"]];
const controls = {};
for (const [route, label] of ROUTES) {
  const e0 = consoleErrs.length, b0 = badHttp.length;
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const main = (await page.locator("main").innerText()).replace(/\s+/g, " ");
  const h1 = await page.locator("h1").first().innerText().catch(() => "");
  const nButtons = await page.locator("main button:visible").count();
  const nLinks = await page.locator("main a:visible").count();
  const nSel = await page.locator("main select:visible, main input:visible, main textarea:visible").count();
  controls[route] = { buttons: nButtons, links: nLinks, fields: nSel };
  await page.screenshot({ path: `${SHOTS}/route_${route.replace(/\W+/g, "_") || "home"}.png` });
  const stuckLoading = /loading…|Loading\.\.\./i.test(main) && main.length < 200;
  const errs = consoleErrs.slice(e0), bads = badHttp.slice(b0);
  rec(`UI-R-${label.slice(0, 8)}`, "routes", `open ${route}`, "page renders content, no console error, no HTTP>=400, not stuck on loading",
    `h1='${h1}' text=${main.length} chars, controls=${nButtons}b/${nLinks}a/${nSel}f, consoleErrors=${errs.length}, http>=400=${JSON.stringify(bads)}`,
    main.length > 80 && !errs.length && !bads.length && !stuckLoading || route === "/no-such-page" && /not found/i.test(main));
}

// ------------------------------------------------------------------ B. click every safe button; flag buttons with no observable effect
const SKIP = /start training|stop|cancel job|delete|remove|promote/i;   // everything else is clicked; non-GET API calls are aborted by the route above
const noEffect = [], clicked = [], skipped = [], blocked = [];
await page.route('**/api/**', (route) => { const m = route.request().method(); if (m === 'GET' || m === 'HEAD' || m === 'OPTIONS') return route.continue(); blocked.push(m + ' ' + route.request().url().replace(BASE, '')); return route.abort(); });
for (const [route, label] of ROUTES.slice(0, -1)) {
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  if (route === '/analysis' || route === '/segmentation') { await page.locator(route === '/segmentation' ? '#seg-img' : 'select[aria-label="Image"]').selectOption({ index: 1 }).catch(() => {}); await page.waitForTimeout(1200); }
  const names = await page.locator("main button:visible").evaluateAll((els) => els.map((e, i) => ({ i, text: (e.innerText || e.getAttribute("aria-label") || e.title || "").trim().replace(/\s+/g, " ").slice(0, 50), disabled: e.disabled })));
  for (const b of names) {
    if (!b.text) { continue; }
    if (b.disabled) { skipped.push(`${route} '${b.text}' (disabled: ${await page.locator("main button:visible").nth(b.i).getAttribute("title") || "no title"})`); continue; }
    if (SKIP.test(b.text)) { skipped.push(`${route} '${b.text}' (state-changing, covered by explicit workflow/API tests)`); continue; }
    await page.goto(BASE + route, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    if (route === '/analysis' || route === '/segmentation') { await page.locator(route === '/segmentation' ? '#seg-img' : 'select[aria-label="Image"]').selectOption({ index: 1 }).catch(() => {}); await page.waitForTimeout(1000); }
    const btn = page.locator("main button:visible").nth(b.i);
    if (!(await btn.isVisible().catch(() => false))) continue;
    if (/^(Fit to screen|Reset view)/.test(b.text)) { await page.getByRole('button', { name: 'Zoom in' }).first().click().catch(() => {}); await page.waitForTimeout(300); }
    if ((await btn.getAttribute('aria-current').catch(() => null)) === 'step') { clicked.push(`${route} '${b.text}': current wizard step (idempotent by design)`); continue; }
    const before = await page.locator("main").innerHTML();
    const url0 = page.url();
    let reqs = 0;
    const onreq = (r) => { if (r.url().includes("/api/")) reqs++; };
    page.on("request", onreq);
    let dialog = false;
    page.once("dialog", (d) => { dialog = true; d.dismiss(); });
    const fc = page.waitForEvent('filechooser', { timeout: 1500 }).then(() => { dialog = true; }).catch(() => {});
    await btn.click({ timeout: 4000 }).catch(() => {});
    await fc;
    await page.waitForTimeout(1500);
    page.off("request", onreq);
    const after = await page.locator("main").innerHTML().catch(() => before);
    const changed = after !== before || page.url() !== url0 || reqs > 0 || dialog;
    clicked.push(`${route} '${b.text}': dom=${after !== before} url=${page.url() !== url0} api=${reqs}`);
    if (!changed) noEffect.push(`${route} '${b.text}'`);
  }
}
await page.unroute('**/api/**');
rec("UI-B-000", "controls", "state-changing API calls attempted by the crawl (all aborted before reaching the server)", "the crawl itself must not change data", JSON.stringify(blocked), true);
rec("UI-B-001", "controls", "click every enabled button on 12 pages except Start training/Stop/Delete/Promote (non-GET API calls aborted)", "each click changes DOM, URL, or triggers an API call (never silently nothing)",
  `clicked=${clicked.length} no-effect=${JSON.stringify(noEffect)} skipped=${skipped.length}`, noEffect.length === 0);
fs.writeFileSync(OUT + "/ui_controls_clicked.txt", ["CLICKED", ...clicked, "", "NO EFFECT", ...noEffect, "", "SKIPPED (not clicked by the crawler)", ...skipped].join("\n"), "utf8");

// ------------------------------------------------------------------ C. disabled controls explain why
const disabledNoWhy = [];
for (const [route] of ROUTES.slice(0, -1)) {
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const dis = await page.locator("main button:disabled, main input:disabled, main select:disabled").evaluateAll((els) => els.map((e) => ({ text: (e.innerText || e.getAttribute("aria-label") || "").trim().slice(0, 40), title: e.title || e.closest("[title]")?.title || "", near: (e.closest("label,div")?.innerText || "").trim().slice(0, 100) })));
  for (const d of dis) if (!d.title && !/run|analy|calculat|generate|explain|mark reviewed|approve|submit|segment|choose|select|start|train|check|export|save|review/i.test(d.text + d.near)) disabledNoWhy.push(`${route}: ${d.text || d.near}`);
}
rec("UI-C-001", "controls", "disabled controls without a title/explanation", "every disabled control states a reason (title) or is an obvious precondition", JSON.stringify(disabledNoWhy), disabledNoWhy.length === 0, "heuristic: precondition-style buttons (Run/Analyze/Generate…) are accepted when the missing input is visible");

// ------------------------------------------------------------------ D. upload errors in the browser
await page.goto(BASE + "/analysis", { waitUntil: "networkidle" });
const fileInput = page.locator('input[type=file][aria-label="Choose radiograph file"]');
fs.writeFileSync("C:/Users/chand/AppData/Local/Temp/claude/D--Dentex-Gen-Ai/4ea330b0-be93-46cf-9a6a-7026331c2b93/scratchpad/corrupt.png", Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), Buffer.alloc(3000, 7)]));
fs.writeFileSync("C:/Users/chand/AppData/Local/Temp/claude/D--Dentex-Gen-Ai/4ea330b0-be93-46cf-9a6a-7026331c2b93/scratchpad/notes.txt", "not an image");
await fileInput.setInputFiles("C:/Users/chand/AppData/Local/Temp/claude/D--Dentex-Gen-Ai/4ea330b0-be93-46cf-9a6a-7026331c2b93/scratchpad/corrupt.png");
await page.waitForTimeout(2000);
let t = (await page.locator("main").innerText()).replace(/\s+/g, " ");
rec("UI-D-001", "upload", "browser upload of a corrupt PNG", "visible error text, no crash, no analysis started", (t.match(/(corrupt|unreadable|invalid|cannot|error)[^.]{0,100}/i) || ["(no error text)"])[0], /corrupt|unreadable|invalid|cannot/i.test(t));
await fileInput.setInputFiles("C:/Users/chand/AppData/Local/Temp/claude/D--Dentex-Gen-Ai/4ea330b0-be93-46cf-9a6a-7026331c2b93/scratchpad/notes.txt");
await page.waitForTimeout(1500);
t = (await page.locator("main").innerText()).replace(/\s+/g, " ");
rec("UI-D-002", "upload", "browser upload of a .txt file", "visible 'unsupported' error", (t.match(/(unsupported|png or jpeg|not a)[^.]{0,100}/i) || ["(no error text)"])[0], /unsupported|png or jpeg|not a/i.test(t));

// ------------------------------------------------------------------ E. real upload -> full analysis -> compare DOM to API response
const real = "D:/Dentex-Gen Ai/Data/validation_data/quadrant_enumeration_disease/xrays/val_12.png";
const realPath = fs.existsSync(real) ? real : null;
let fullResp = null, imageIdUp = null;
if (realPath) {
  const [upResp] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/images/upload")), fileInput.setInputFiles(realPath)]);
  const up = await upResp.json();
  imageIdUp = up.id;
  rec("UI-E-001", "upload", "browser upload of a real validation radiograph (val_12.png)", "200, image registered, shown selected", `${upResp.status()} id=${up.id} ${up.width}x${up.height} dup=${up.duplicate}`, upResp.status() === 200);
  await page.waitForTimeout(1500);
  const [fr] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/analyze/full"), { timeout: 240000 }), page.getByTestId("run-full").click()]);
  fullResp = await fr.json();
  await page.waitForSelector('[data-testid="region-table"] tbody tr', { timeout: 60000 });
  rec("UI-E-002", "inference", "click 'Analyze Image (full pipeline)'", "real POST /api/analyze/full (200) and steps rendered", `${fr.status()} regions=${fullResp.regions.length} secs=${fullResp.summary.seconds}`, fr.status() === 200);
  // (region table / labels / inspector are verified in ui_simplified.mjs)
  // overlay alignment in the DOM
  const geo = await page.evaluate(() => {
    const boxes = [...document.querySelectorAll('[data-testid="detection-box"] > rect')].map((r) => ({ x: +r.getAttribute("x"), y: +r.getAttribute("y"), w: +r.getAttribute("width"), h: +r.getAttribute("height") }));
    const svg = document.querySelector('[data-testid="detection-box"]')?.closest("svg");
    const img = svg?.parentElement?.querySelector("img");
    const vb = svg?.getAttribute("viewBox");
    const ir = img?.getBoundingClientRect(), sr = svg?.getBoundingClientRect();
    return { boxes, vb, nat: img ? [img.naturalWidth, img.naturalHeight] : null, imgRect: ir && [ir.x, ir.y, ir.width, ir.height], svgRect: sr && [sr.x, sr.y, sr.width, sr.height] };
  });
  const [W, H] = fullResp.image_size;
  const probs = [];
  if (!geo.nat || geo.nat[0] !== W || geo.nat[1] !== H) probs.push(`natural size ${geo.nat} != api ${W}x${H}`);
  if (geo.vb !== `0 0 ${W} ${H}`) probs.push(`viewBox ${geo.vb}`);
  if (geo.imgRect && geo.svgRect && geo.imgRect.some((v, i) => Math.abs(v - geo.svgRect[i]) > 1.5)) probs.push(`img rect ${geo.imgRect} != svg rect ${geo.svgRect}`);
  const drawn = geo.boxes.length;
  const near = (b, g) => Math.abs(b.x - g.box[0]) < 0.01 && Math.abs(b.y - g.box[1]) < 0.01 && Math.abs(b.w - (g.box[2] - g.box[0])) < 0.01 && Math.abs(b.h - (g.box[3] - g.box[1])) < 0.01;
  geo.boxes.forEach((b, i) => { if (!fullResp.regions.some((g) => near(b, g))) probs.push(`drawn rect ${i} matches no API box`); });
  const hidden = fullResp.regions.filter((g) => !geo.boxes.some((b) => near(b, g)));
  if (hidden.length) probs.push(`${hidden.length} API regions not drawn (scores: ${hidden.map((g) => g.detection_score.toFixed(2)).join(',')})`);
  rec("UI-E-004", "alignment", "SVG overlay vs API boxes and image natural size", "viewBox == natural size == API image size; every drawn rect == API box (original pixel coordinates); svg exactly covers <img>", probs.length ? JSON.stringify(probs.slice(0, 4)) : `${drawn} boxes exact, viewBox ${geo.vb}`, probs.length === 0);
  await page.screenshot({ path: `${SHOTS}/e2e_analysis.png` });
  // (uncertainty, heatmap and region inspector are verified in ui_simplified.mjs)
  // Report
  const [rr] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/reports/generate"), { timeout: 60000 }), page.getByTestId("make-report").click()]);
  const rj = await rr.json();
  await page.waitForURL(/\/reports\?id=/, { timeout: 30000 });
  await page.waitForSelector('[data-testid="localized-report"]', { timeout: 30000 });
  const repId = rj.report.report_id;
  const en = (await page.locator('[data-testid="localized-report"]').textContent()).replace(/\s+/g, " ");
  rec("UI-E-007", "reports", "Generate Draft Report from the analysis", "report created from analysis_id, shown in English with banner", `${rr.status()} id=${repId} analysis=${rj.report.analysis_id ?? "(n/a)"} status=${/Awaiting review/.test(en)}`, rr.status() === 200 && /Awaiting review/.test(en));
  fs.writeFileSync(OUT + "/ui_report_id.txt", repId);
  // language switching must not call inference
  const infer = [];
  const onreq2 = (r) => { const u = r.url(); if (/\/api\/(predict|analyze|segment|explain|uncertainty\/image)/.test(u) && r.method() === "POST") infer.push(u); };
  page.on("request", onreq2);
  const texts = { en };
  for (const lang of ["hi", "mr", "en"]) {
    await page.selectOption('select[aria-label="Report language"]', lang);
    await page.waitForFunction((l) => document.querySelector('[data-testid="localized-report"]')?.getAttribute("lang") === l, lang, { timeout: 20000 });
    await page.waitForTimeout(700);
    texts[lang + (lang === "en" ? "2" : "")] = (await page.locator('[data-testid="localized-report"]').textContent()).replace(/\s+/g, " ");
  }
  page.off("request", onreq2);
  const idsEn = [...new Set((en.match(/[a-z0-9_]+:[0-9a-f]{8}|RPT-[0-9A-F]+|F\d+|dentex_[a-z_0-9]+_v\d+/gi) || []))].sort();
  const missing = { hi: idsEn.filter((x) => !texts.hi.includes(x)), mr: idsEn.filter((x) => !texts.mr.includes(x)) };
  rec("UI-E-008", "i18n", "switch the displayed report EN -> HI -> MR -> EN", "ids/versions preserved in every language, Devanagari present, no inference request", `ids=${idsEn.length} missing=${JSON.stringify(missing)} devanagari(hi)=${/[\u0900-\u097F]{4}/.test(texts.hi)} devanagari(mr)=${/[\u0900-\u097F]{4}/.test(texts.mr)} inference-requests=${infer.length}`,
    !missing.hi.length && !missing.mr.length && /[\u0900-\u097F]{4}/.test(texts.hi) && /[\u0900-\u097F]{4}/.test(texts.mr) && infer.length === 0);
  await page.selectOption('select[aria-label="Report language"]', "mr");
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${SHOTS}/e2e_report_mr.png` });
  const lr = await page.getByTestId("ling-review").first().innerText().catch(() => "");
  rec("UI-N-001", "i18n", "Marathi report on screen: prominent 'awaiting linguistic review' notice (local + English text)", "visible near the top, includes the English sentence", lr.replace(/\s+/g, " ").slice(0, 200), /Awaiting linguistic review/.test(lr) && /[ऀ-ॿ]{4}/.test(lr));
  await page.selectOption('select[aria-label="Report language"]', "en");
  await page.waitForTimeout(700);
  rec("UI-N-002", "i18n", "English report on screen has no translation-review notice", "absent", `count=${await page.getByTestId("ling-review").count()}`, (await page.getByTestId("ling-review").count()) === 0);
  await page.selectOption('select[aria-label="Report language"]', "mr");   // back to Marathi for the export test below
  await page.waitForTimeout(700);
  // exports via the real links (download)
  for (const [testid, name] of [["export-html", "html"]]) {
    const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 20000 }).catch(() => null), page.getByTestId(testid).click()]);
    if (dl) { const p = OUT + "/ui_export_mr." + name; await dl.saveAs(p); const size = fs.statSync(p).size; const body = fs.readFileSync(p, "utf8"); rec("UI-E-009", "export", `click HTML export while language=mr`, "file downloads; contains Marathi text and the report id", `${dl.suggestedFilename()} ${size} B marathi=${/[\u0900-\u097F]{4}/.test(body)} id=${body.includes(repId)}`, size > 500 && body.includes(repId) && /[\u0900-\u097F]{4}/.test(body)); }
    else rec("UI-E-009", "export", "click HTML export", "download", "no download event (link may open in a tab)", "partial");
  }
  // persistence: reload & list
  await page.goto(BASE + "/reports", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const listTxt = (await page.locator('aside[aria-label="Report list"]').innerText()).replace(/\s+/g, " ");
  rec("UI-E-010", "persistence", "reload /reports and look for the new report in the list", "report is listed with its id", `listed=${listTxt.includes(repId)}`, listTxt.includes(repId));
  const pe0 = consoleErrs.length;
  await page.locator(`aside[aria-label="Report list"] button[aria-label="Open report ${repId}"]`).click();
  await page.waitForSelector('[data-testid="localized-report"]', { timeout: 30000 }).catch(() => {});
  rec("UI-E-010b", "reports", "click a report in the list while none is selected (regression for the null.report crash)", "report renders; no page error", `rendered=${await page.locator('[data-testid="localized-report"]').count() === 1} pageErrors=${consoleErrs.slice(pe0).filter((e) => e.startsWith("pageerror")).length}`, (await page.locator('[data-testid="localized-report"]').count()) === 1 && !consoleErrs.slice(pe0).some((e) => e.startsWith("pageerror")));
  await page.goto(BASE + `/reports?id=${repId}`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="localized-report"]', { timeout: 30000 });
  rec("UI-E-011", "persistence", "reopen /reports?id=<id> in a fresh navigation", "report renders from the database", "rendered", true);
  // reviewer validation
  const mark = page.getByRole("button", { name: /Mark reviewed/ });
  rec("UI-E-012", "reports", "'Mark reviewed' with an empty reviewer name", "button disabled", `disabled=${await mark.isDisabled()}`, await mark.isDisabled());
}
// Training page: the dry-run button talks to the real backend and starts nothing
await page.goto(BASE + "/training", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const jobsBefore = await (await page.request.get(BASE + "/api/training/jobs")).json();
const dryBtn = page.getByTestId("train-dry-run");
const dryEnabled = await dryBtn.isEnabled().catch(() => false);
let dryText = "";
if (dryEnabled) { const [dr] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/training/start"), { timeout: 60000 }), dryBtn.click()]); dryText = `${dr.status()} ` + (await page.getByTestId("dry-run-result").innerText().catch(() => "")); }
const jobsAfter = await (await page.request.get(BASE + "/api/training/jobs")).json();
rec("UI-N-003", "training", "'Validate only' on the Training page", "200, message names the checkpoint it would write, no job created", `enabled=${dryEnabled} ${dryText.replace(/\s+/g, " ").slice(0, 150)} jobs ${jobsBefore.length}->${jobsAfter.length}`, dryEnabled && /^200/.test(dryText) && /would write/.test(dryText) && jobsBefore.length === jobsAfter.length);
const tb = await page.getByTestId("tb-state").innerText().catch(() => "");
rec("UI-N-004", "training", "TensorBoard state on the Training page is truthful", "says it is not installed / no event files (no dead link)", tb, /not installed|No event files/.test(tb));
// Uncertainty page: measured validation next to each signal
await page.goto(BASE + "/uncertainty", { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="unc-table"] tbody tr', { timeout: 30000 }).catch(() => {});
await page.locator('[data-testid="unc-table"] tbody tr').first().click().catch(() => {});
await page.waitForTimeout(1500);
const sv = await page.locator('[data-testid^="sigval-"]').evaluateAll((els) => els.map((e) => e.textContent));
rec("UI-N-005", "uncertainty", "each signal shows what was measured about it", "4 lines; mask instability labelled weak/very weak", JSON.stringify(sv).slice(0, 330), sv.length >= 4 && /mask|AUROC/.test(sv.join(" ")) && sv.some((t) => /weak/.test(t)));
rec("UI-X-001", "console", "all console errors across the whole browser audit", "none unexpected (intended 4xx from deliberate invalid uploads are logged by Chromium as errors)", JSON.stringify(consoleErrs.slice(0, 6)), consoleErrs.every((e) => /status of 4\d\d|Failed to load resource|ERR_FAILED/.test(e)));
rec("UI-X-002", "network", "HTTP >= 400 responses during the audit", "only from the deliberate invalid uploads", JSON.stringify(badHttp), badHttp.every((b) => /upload/.test(b)));
const realFail = reqFail.filter((f) => !(f.startsWith("POST ") && /net::ERR_FAILED/.test(f)) && !(f.startsWith("GET ") && /\/export\?/.test(f) && /ERR_ABORTED/.test(f)));   // the crawl deliberately aborts every non-GET API call
rec("UI-X-003", "network", "failed requests other than the crawl's deliberately aborted POSTs", "none", JSON.stringify(realFail.slice(0, 5)), realFail.length === 0);
fs.writeFileSync(OUT + "/ui_audit.json", JSON.stringify({ run_at: new Date().toISOString(), base: BASE, controls, uploaded_image: imageIdUp, results }, null, 1), "utf8");
const sum = {}; for (const r of results) sum[r.result] = (sum[r.result] || 0) + 1;
console.log("SUMMARY", JSON.stringify(sum));
await browser.close();
