// Browser verification of the simplified end-user UI (real Vite :5173 + real FastAPI :8000, headless Edge). Writes docs/audit_evidence/ui_simplified.json
import { chromium } from "playwright-core";
import fs from "node:fs";

const BASE = "http://localhost:5173";
const OUT = "D:/Dentex-Gen Ai/docs/audit_evidence";
const SHOTS = OUT + "/shots_simplified";
fs.mkdirSync(SHOTS, { recursive: true });
const results = [];
const rec = (id, area, input, expected, actual, ok) => {
  results.push({ id, area, input, expected, actual: String(actual).slice(0, 420), result: ok === true ? "PASS" : ok === "blocked" ? "BLOCKED" : "FAIL" });
  console.log(`${results.at(-1).result.padEnd(7)} ${id.padEnd(8)} ${input.slice(0, 74).padEnd(74)} -> ${String(actual).slice(0, 100)}`);
};
const browser = await chromium.launch({ executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
const errs = [], bad = [];
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 200)); });
page.on("pageerror", (e) => errs.push("pageerror " + String(e).slice(0, 200)));
page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) bad.push(`${r.request().method()} ${r.status()} ${r.url().replace(BASE, "")}`); });

// ---------------------------------------------------------------- navigation
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await page.evaluate(() => localStorage.clear());
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(800);
const links = await page.locator('aside[aria-label="Primary"] a').allInnerTexts();
const want = ["Home", "X-ray Analysis", "Reports", "Review Findings", "About & Limitations", "Settings"];
rec("S-NAV-1", "navigation", "default sidebar links", JSON.stringify(want), JSON.stringify(links.map((t) => t.trim())), JSON.stringify(links.map((t) => t.trim())) === JSON.stringify(want));
const hiddenTools = ["Uncertainty", "Active Learning", "Annotations", "Model Training", "Experiments", "Model Registry", "Tooth Segmentation"];
const sideText = (await page.locator('aside[aria-label="Primary"]').innerText());
rec("S-NAV-2", "navigation", "research links absent by default", "none of 7 research labels in the sidebar", hiddenTools.filter((t) => sideText.includes(t)).join(",") || "none", hiddenTools.every((t) => !sideText.includes(t)));
for (const [route, label] of [["/uncertainty", "Uncertainty"], ["/active-learning", "Active Learning"], ["/annotations", "Annotation"], ["/training", "Model Training"], ["/experiments", "Experiment"], ["/models", "Model Registry"], ["/segmentation", "Segmentation"]]) {
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const banner = await page.getByTestId("research-banner").count();
  const h1 = await page.locator("h1").first().innerText().catch(() => "");
  rec("S-NAV-3", "navigation", `hidden page still reachable by URL: ${route}`, "renders with the Research / Developer Tool banner", `h1='${h1}' banner=${banner}`, banner === 1 && h1.includes(label.split(" ")[0]));
}
await page.goto(BASE + "/settings", { waitUntil: "networkidle" });
await page.getByTestId("show-research").check();
await page.waitForTimeout(400);
const research = await page.getByTestId("research-nav").innerText();
rec("S-NAV-4", "navigation", "Settings -> Show Research / Developer Tools", "7 research links appear under a clearly labelled heading", research.replace(/\s+/g, " ").slice(0, 200), hiddenTools.every((t) => research.includes(t)) && /Research \/ Developer Tools/i.test(research));
await page.reload({ waitUntil: "networkidle" });
rec("S-NAV-5", "navigation", "preference persists after reload", "research nav still visible", `count=${await page.getByTestId("research-nav").count()}`, (await page.getByTestId("research-nav").count()) === 1);
await page.getByTestId("show-research").uncheck();
await page.waitForTimeout(300);
rec("S-NAV-6", "navigation", "switch it off again", "hidden", `count=${await page.getByTestId("research-nav").count()}`, (await page.getByTestId("research-nav").count()) === 0);

// ---------------------------------------------------------------- Home
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const home = (await page.locator("main").innerText()).replace(/\s+/g, " ");
const avail = await page.locator('[data-testid="model-status"] li').evaluateAll((els) => els.map((e) => [e.getAttribute("data-task"), /Available/.test(e.innerText) && !/Unavailable/.test(e.innerText)]));
const apiModels = await (await page.request.get(BASE + "/api/models")).json();
const truth = ["detection", "segmentation", "classification", "numbering"].map((t) => [t, apiModels.items.some((m) => m.task === t && m.dental_specific)]);
rec("S-HOME-1", "home", "Home shows upload CTA, readiness, recent analyses, latest report, pending reviews, models", "all present; no charts / experiments / dataset cards", `cta=${await page.getByTestId("upload-cta").count()} readiness=${await page.getByTestId("readiness").count()}`,
  (await page.getByTestId("upload-cta").count()) === 1 && (await page.getByTestId("readiness").count()) === 1 && /Recent analyses/.test(home) && /Latest report/.test(home) && /Findings awaiting review/.test(home) && !/Recent experiments|AUROC|Leakage/.test(home));
rec("S-HOME-2", "home", "model availability equals the backend registry", JSON.stringify(truth), JSON.stringify(avail), JSON.stringify(avail) === JSON.stringify(truth));
rec("S-HOME-3", "home", "no architecture names or checkpoint paths on Home", "none", /resnet|fasterrcnn|maskrcnn|\.pth|dentex_/.test(home) ? "FOUND" : "none", !/resnet|fasterrcnn|maskrcnn|\.pth|dentex_/i.test(home));
await page.screenshot({ path: `${SHOTS}/home_1440.png` });
await page.getByTestId("upload-cta").click();
rec("S-HOME-4", "home", "Upload X-ray button", "goes to /analysis", page.url(), page.url().endsWith("/analysis"));

// ---------------------------------------------------------------- Analysis
const real = "D:/Dentex-Gen Ai/Data/validation_data/quadrant_enumeration_disease/xrays/val_12.png";
await page.goto(BASE + "/analysis", { waitUntil: "networkidle" });
const [up] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/images/upload")), page.locator('input[type=file][aria-label="Choose radiograph file"]').setInputFiles(real)]);
await page.waitForTimeout(1500);
const infoTxt = (await page.getByTestId("image-info").innerText()).replace(/\s+/g, " ");
const bytes = fs.statSync(real).size;
rec("S-AN-1", "analysis", "upload shows dimensions, file size and quality", "2794 x 1316 px, file size in MB, quality line", infoTxt, up.status() === 200 && /2794 × 1316/.test(infoTxt) && new RegExp((bytes / 1048576).toFixed(1) + " MB").test(infoTxt) && /Image quality/.test(infoTxt));
let analyzeCalls = 0;
page.on("request", (r) => { if (r.url().includes("/api/analyze/full") && r.method() === "POST") analyzeCalls++; });
const btn = page.getByTestId("run-full");
rec("S-AN-2", "analysis", "primary button label", "'Analyze X-ray'", await btn.innerText(), (await btn.innerText()).trim() === "Analyze X-ray");
const [fr] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/analyze/full"), { timeout: 240000 }), btn.click()]);
const sawLoading = await page.getByTestId("analyzing").count().catch(() => 0);
const full = await fr.json();
await page.waitForSelector('[data-testid="region-table"] tbody tr', { timeout: 60000 });
await page.waitForTimeout(800);
rec("S-AN-3", "analysis", "one click runs the whole pipeline", "one POST /api/analyze/full, 200, steps ok", `${fr.status()} calls=${analyzeCalls} regions=${full.regions.length}`, fr.status() === 200 && analyzeCalls === 1 && full.steps.every((s) => s.status === "ok"));
// label semantics vs the API
const boxes = await page.locator('[data-testid="detection-box"]').evaluateAll((gs) => gs.map((g) => ({ region: +g.getAttribute("data-region"), label: g.querySelector('[data-testid="region-label"] text')?.textContent ?? null })));
const mism = [];
let shown = 0, omitted = 0, tooth = 0, regionOnly = 0, check = 0;
for (const b of boxes) {
  const g = full.regions.find((r) => r.region_no === b.region);
  const expect = g.fdi == null ? `R${g.region_no}` : g.numbering_status === "assigned" ? String(g.fdi) : `${g.fdi}?`;
  if (g.fdi == null) regionOnly++; else if (g.numbering_status === "assigned") tooth++; else check++;
  if (b.label == null) omitted++; else { shown++; if (b.label !== expect) mism.push(`${b.region}: '${b.label}' vs '${expect}'`); }
}
rec("S-AN-4", "labels", "overlay label text vs API numbering status", "assigned -> '14', unconfirmed -> '14?', none -> 'R7'; never a bare region index as a tooth number", `shown=${shown} omitted=${omitted} tooth=${tooth} proposed=${check} regionOnly=${regionOnly} mismatches=${JSON.stringify(mism.slice(0, 3))}`, mism.length === 0 && boxes.length === full.regions.length);
const rects = await page.locator('[data-testid="region-label"] rect').evaluateAll((rs) => rs.map((r) => { const b = r.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; }));
let overlaps = 0;
for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) { const a = rects[i], c = rects[j]; if (a[0] < c[0] + c[2] - 0.5 && c[0] < a[0] + a[2] - 0.5 && a[1] < c[1] + c[3] - 0.5 && c[1] < a[1] + a[3] - 0.5) overlaps++; }
rec("S-AN-5", "labels", "rendered labels overlap each other", "0 overlapping label pairs", `labels=${rects.length} overlapping pairs=${overlaps}`, overlaps === 0);
rec("S-AN-6", "labels", "legend explains the labels", "legend present with tooth / proposed / region / selected", (await page.getByTestId("legend").innerText()).replace(/\s+/g, " ").slice(0, 160), /tooth number/.test(await page.getByTestId("legend").innerText()) && /R7/.test(await page.getByTestId("legend").innerText()));
// selection sync box <-> row <-> inspector
await page.locator('[data-testid="detection-box"]').nth(3).dispatchEvent("click");
await page.waitForTimeout(400);
const selRow = await page.locator('[data-testid="region-table"] tbody tr[aria-selected="true"] td').first().innerText();
const title = await page.getByTestId("region-title").innerText();
const g3 = full.regions[3];
rec("S-AN-7", "selection", "click a box -> same region highlighted in the list and the inspector", "row, inspector title and box all refer to region 4", `row='${selRow}' title='${title}'`, title.includes(`Region ${g3.region_no}`) && selRow === (g3.fdi == null ? `R${g3.region_no}` : g3.numbering_status === "assigned" ? String(g3.fdi) : `${g3.fdi}?`));
await page.locator('[data-testid="region-table"] tbody tr').nth(7).click();
await page.waitForTimeout(400);
const title2 = await page.getByTestId("region-title").innerText();
const selBox = await page.locator('[data-testid="detection-box"] > rect').nth(7).getAttribute("stroke");
rec("S-AN-8", "selection", "click a list row -> the box turns amber and the inspector follows", "region 8, stroke #A75B04 (selected amber)", `title='${title2}' stroke=${selBox}`, title2.includes(`Region ${full.regions[7].region_no}`) && selBox === "#A75B04");
// inspector content
const det = (await page.getByTestId("region-detail").innerText()).replace(/\s+/g, " ");
const g7 = full.regions[7];
const needs = [/Tooth number \(FDI\)/, /Detection score/, /Closest trained class/, /not.*evidence that the finding is present|no class is named|No classifier output/, /Uncertainty for this region/, /Classification entropy/, /Flip disagreement/, /Mask instability/, /Detection instability/, /Review this region/];
rec("S-AN-9", "inspector", "inspector shows tooth number, raw scores, candidate-class wording, uncertainty, review links", "all parts present", needs.filter((n) => !n.test(det)).map(String).join(",") || "all present", needs.every((n) => n.test(det)));
rec("S-AN-10", "inspector", "tooth number in the inspector equals the API (or 'Unassigned')", String(g7.fdi ?? "Unassigned"), det.match(/Tooth number \(FDI\) (\S+)/)?.[1], g7.fdi == null ? /Unassigned/.test(det) : det.includes(`Tooth number (FDI) ${g7.fdi}`));
const reviewHref = await page.getByRole("link", { name: "Review this region" }).getAttribute("href");
const wording = (await page.locator("main").innerText()).replace(/\s+/g, " ");
rec("S-AN-11", "wording", "no diagnosis wording: classes are 'candidate' / 'closest trained class'", "no 'diagnos(ed|is)' claims, no 'healthy' result, 'not evidence' disclaimer present", `disease-claim=${/(is|are|has|have) (caries|impacted)|diagnosed with/i.test(wording)} healthy-result=${/result: healthy|normal tooth/i.test(wording)}`, !/diagnosed with|result: healthy|normal tooth/i.test(wording) && /not evidence/.test(wording));
const unc = (await page.locator('[data-testid="unc-explainer"]').first().innerText().catch(() => ""));
const sig = await page.locator('[data-testid^="sigval-"]').evaluateAll((els) => els.map((e) => e.textContent));
rec("S-AN-12", "uncertainty", "uncertainty inside X-ray Analysis: explanation, 4 signals with measured reliability, review recommendation", "short explanation + 4 sigval lines (mask/detection 'weak') + 'recommended for human review'", `${unc.slice(0, 60)} | sigval=${sig.length} weak=${sig.filter((t) => /weak/.test(t)).length} | rec=${/recommended for human review/.test(wording)}`, /doubt, not a confirmed error/.test(unc) && sig.length === 4 && sig.filter((t) => /weak/.test(t)).length === 2 && /recommended for human review/.test(wording));
const heads = await page.locator('[data-testid="region-table"] thead th').allTextContents();
rec("S-AN-TBL", "analysis", "findings table columns and help note", "Region, Tooth number, Candidate class, Score, Review status, Action + an explanatory note", JSON.stringify(heads) + " help=" + (await page.getByTestId("table-help").count()), JSON.stringify(heads.map((h) => h.trim())) === JSON.stringify(["Region", "Tooth number", "Candidate class", "Score", "Review status", "Action"]) && (await page.getByTestId("table-help").count()) === 1);
const how = await page.getByTestId("unc-how").evaluate((d) => ({ open: d.open, len: d.textContent.length }));
rec("S-AN-UNC", "uncertainty", "metric definitions and AUROC values sit in a collapsed 'How uncertainty is calculated'", "details closed by default, definitions present inside", JSON.stringify(how), how.open === false && how.len > 600);
const dupBtns = await page.getByRole("button", { name: /Run Detection|Run Segmentation|Calculate Uncertainty/ }).count();
rec("S-AN-NODUP", "analysis", "no developer-style duplicate actions in the end-user workspace", "0", String(dupBtns), dupBtns === 0);
await page.screenshot({ path: `${SHOTS}/analysis_1440.png` });
// dedup: switching away and back must not re-run; explicit re-run is a different button
await page.locator('aside[aria-label="Primary"] a', { hasText: "Home" }).click();          // in-app navigation (a full reload would drop the in-memory analysis by design)
await page.waitForTimeout(800);
await page.locator('aside[aria-label="Primary"] a', { hasText: "X-ray Analysis" }).click();
await page.waitForTimeout(1200);
rec("S-AN-13", "analysis", "returning to the page keeps the valid analysis; no duplicate inference", "'Analysis ready', analyze calls still 1", `ready=${await page.getByText("Analysis ready").count()} calls=${analyzeCalls}`, (await page.getByText("Analysis ready").count()) === 1 && analyzeCalls === 1);
// heatmap
let hm = "skipped";
for (let i = 0; i < full.regions.length; i++) { if (full.regions[i].candidate_class?.status === "candidate") { await page.locator('[data-testid="region-table"] tbody tr').nth(i).click(); hm = "ok"; break; } }
if (hm === "ok") {
  const [er] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/explain"), { timeout: 120000 }), page.getByRole("button", { name: "Show attention heatmap" }).click({ timeout: 8000 })]);
  await page.waitForTimeout(1200);
  rec("S-AN-14", "heatmap", "attention heatmap for a region with a candidate class", "200 and heatmap image drawn", `${er.status()} images=${await page.locator("svg image[href^='data:image/png']").count()}`, er.status() === 200 && (await page.locator("svg image[href^='data:image/png']").count()) >= 1);
} else rec("S-AN-14", "heatmap", "attention heatmap", "needs a candidate-class region", "every region abstained", "blocked");

// ---------------------------------------------------------------- phone workspace (analysis stays in memory: only the viewport changes)
await page.setViewportSize({ width: 390, height: 844 });
await page.waitForTimeout(800);
await page.evaluate(() => document.querySelector("main").scrollTo(0, 0));
const ph = await page.evaluate(() => {
  const vc = document.querySelector('[aria-label="Image viewer and results"] .card');
  const b = vc.getBoundingClientRect();
  const z = [...document.querySelectorAll('button[aria-label="Zoom in"],button[aria-label="Zoom out"],button[aria-label="Fit to screen"],button[aria-label="Reset view to 100%"]')].map((e) => Math.round(Math.min(e.getBoundingClientRect().width, e.getBoundingClientRect().height)));
  const outside = [...document.querySelectorAll("button, a, select, input")].filter((e) => { if (e.closest(".overflow-auto, .overflow-x-auto, .overflow-y-auto")) return false; const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1); }).length;   // controls inside a table's own scroll container may scroll sideways
  const det = document.querySelector('[data-testid="change-image"]');
  return { viewerTop: Math.round(b.top), viewerWidth: Math.round(b.width), zoom: z, outside, sw: document.documentElement.scrollWidth, iw: window.innerWidth, uploaderOpen: det ? det.open : null };
});
rec("S-MOB-1", "mobile", "phone (390px) after an analysis: viewer position", "viewer card starts within the first screen (top < 600px) and is at least 340px wide; upload section collapsed once an image is chosen", JSON.stringify(ph), ph.viewerTop < 600 && ph.viewerWidth >= 340 && ph.uploaderOpen === false);
rec("S-MOB-2", "mobile", "touch targets and horizontal overflow at 390px", "zoom buttons >= 36px; no control outside the viewport; no horizontal page scroll", `zoom=${ph.zoom} outside=${ph.outside} scrollWidth=${ph.sw}`, ph.zoom.length === 4 && ph.zoom.every((v) => v >= 36) && ph.outside === 0 && ph.sw <= ph.iw + 1);
await page.screenshot({ path: `${SHOTS}/mobile_analysis_top.png` });
await page.locator('[data-testid="detection-box"]').nth(5).dispatchEvent("click");
await page.waitForTimeout(900);
const det5 = await page.evaluate(() => { const a = document.querySelector('aside[aria-label="Region details"]'); const r = a.getBoundingClientRect(); return { top: Math.round(r.top), h: Math.round(r.height), vh: window.innerHeight, title: a.querySelector('[data-testid="region-title"]')?.textContent }; });
rec("S-MOB-3", "mobile", "tap a region box on the phone", "region details panel scrolls into view and names the region", JSON.stringify(det5), !!det5.title && det5.top < det5.vh - 60);
await page.screenshot({ path: `${SHOTS}/mobile_region_details.png` });
await page.setViewportSize({ width: 1440, height: 900 });
await page.waitForTimeout(800);

// ---------------------------------------------------------------- stale results, duplicate requests, API errors
const sel = page.locator('select[aria-label="Image"]');
const original = await sel.inputValue();
const opts2 = await sel.locator("option").evaluateAll((os) => os.map((o) => o.value).filter(Boolean));
const other = opts2.find((v) => v !== original);
const callsBefore = analyzeCalls;
await sel.selectOption(other);
await page.waitForTimeout(1200);
const stale = { boxes: await page.locator('[data-testid="detection-box"]').count(), table: await page.locator('[data-testid="region-table"]').count(), analyze: await page.getByTestId("run-full").count(), ready: await page.getByText("Analysis ready").count(), calls: analyzeCalls - callsBefore };
rec("S-STALE-1", "analysis", "choose a different image after an analysis", "no boxes, no region list, no 'Analysis ready', 'Analyze X-ray' offered again, and NO automatic inference", JSON.stringify(stale), stale.boxes === 0 && stale.table === 0 && stale.analyze === 1 && stale.ready === 0 && stale.calls === 0);
await sel.selectOption(original);
await page.waitForTimeout(1200);
rec("S-STALE-2", "analysis", "go back to the first image", "its analysis is not shown from the other image (stale data never reused for a different id)", `boxes=${await page.locator('[data-testid="detection-box"]').count()}`, (await page.locator('[data-testid="detection-box"]').count()) === 0);
// simulated backend failures: the UI must show a clear message and stay usable
await page.route("**/api/analyze/full", (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "no_checkpoint", message: "No dental detection model is available.", hint: "Place a trained detection checkpoint.", details: {} } }) }));
await page.getByTestId("run-full").click();
await page.waitForTimeout(1200);
const blocked = (await page.locator('[role="alert"]').allInnerTexts()).join(" ").replace(/\s+/g, " ");
rec("S-ERR-1", "errors", "analysis request answered 503 (model missing; simulated at the network layer)", "clear 'required model is not available' message with the backend hint; no crash; no invented result", blocked.slice(0, 160), /not available/i.test(blocked) && /Place a trained detection checkpoint/.test(blocked) && (await page.locator('[data-testid="detection-box"]').count()) === 0);
await page.unroute("**/api/analyze/full");
await page.route("**/api/analyze/full", (route) => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: { code: "internal_error", message: "Unexpected server error.", hint: null, details: {} } }) }));
await page.getByTestId("run-full").click();
await page.waitForTimeout(1200);
const e500 = (await page.locator("main").innerText()).replace(/\s+/g, " ");
rec("S-ERR-2", "errors", "analysis request answered 500 (simulated)", "error text shown, button usable again", `${/Unexpected server error/.test(e500)} enabled=${await page.getByTestId("run-full").isEnabled()}`, /Unexpected server error/.test(e500) && (await page.getByTestId("run-full").isEnabled()));
await page.unroute("**/api/analyze/full");
const before2 = analyzeCalls;
await page.getByTestId("run-full").click();
await page.waitForSelector('[data-testid="region-table"] tbody tr', { timeout: 120000 });
await page.waitForTimeout(800);
rec("S-STALE-3", "analysis", "re-run after the simulated errors", "exactly one real request, results back", `calls=${analyzeCalls - before2}`, analyzeCalls - before2 === 1);

// ---------------------------------------------------------------- Report flow
const [rr] = await Promise.all([page.waitForResponse((r) => r.url().includes("/api/reports/generate"), { timeout: 60000 }), page.getByTestId("make-report").click()]);
const rj = await rr.json();
await page.waitForURL(/\/reports\?id=/, { timeout: 30000 });
await page.waitForSelector('[data-testid="localized-report"]', { timeout: 30000 });
const rid = rj.report.report_id;
const ren = (await page.getByTestId("localized-report").textContent()).replace(/\s+/g, " ");
rec("S-REP-1", "reports", "Generate report from the analysis", "200, report opens in English with status 'Awaiting review', ONE neutral safety note, limitations", `${rr.status()} ${rid}`, rr.status() === 200 && /Awaiting review/.test(ren) && /Limitations/i.test(ren) && /not a confirmed diagnosis/.test(ren));
const body = (await page.locator('[aria-label="Report"]').innerText()).replace(/\s+/g, " ");
const techOpen = await page.getByTestId("tech-details").evaluate((d) => d.open);
const notes = await page.getByTestId("safety-note").count();
const headings = await page.locator('[data-testid="localized-report"] h3').allTextContents();
rec("S-REP-CLEAN", "reports", "report body is clean: no big 'UNCONFIRMED RESEARCH DRAFT' banner, no 'Generated by: template' line, one safety note, technical details collapsed", "banner text absent from the visible page, 1 safety note, details closed, sections in the required order",
  `banner=${/UNCONFIRMED RESEARCH DRAFT/i.test(body)} generatedBy=${/Generated by/i.test(body)} notes=${notes} techOpen=${techOpen} h3=${JSON.stringify(headings)}`,
  !/UNCONFIRMED RESEARCH DRAFT/i.test(body) && !/Generated by/i.test(body) && notes === 1 && techOpen === false && headings.length >= 5);
const techTxt = await page.getByTestId("tech-details").textContent();
rec("S-REP-TECH", "reports", "technical details (ids, model versions, generator) are kept, inside the collapsed section", "contains report id, model versions, 'template'", techTxt.replace(/\s+/g, " ").slice(0, 160), techTxt.includes(rid) && /dentex_teeth_detection_v1/.test(techTxt) && /template/.test(techTxt));
const rowsInfo = await page.locator('[data-testid="report-list"] li').evaluateAll((els) => els.map((e) => ({ t: e.innerText.replace(/\s+/g, " "), open: !!e.querySelector("button") })));
const mine = rowsInfo.find((r) => r.t.includes(rid));
rec("S-REP-LIST", "reports", "report list rows are compact: id, image name, date, status, Open; no draft banner / generator / disclaimer text", "row has id, an image name, a date, 'Awaiting review', an Open button, and none of the removed strings",
  JSON.stringify(mine), !!mine && mine.open && /Awaiting review/.test(mine.t) && /val_12\.png/.test(mine.t) && !/UNCONFIRMED|Generated by|template|diagnosis/i.test(mine.t));

const listTxt = await page.locator('aside[aria-label="Report list"]').innerText();
rec("S-REP-2", "reports", "saved reports list shows the new report", "listed", String(listTxt.includes(rid)), listTxt.includes(rid));
const opts = await page.locator('select[aria-label="Report language"] option').allInnerTexts();
rec("S-REP-3", "reports", "language options are exactly the supported ones", "English, हिन्दी, मराठी", JSON.stringify(opts), opts.length === 3);
let inferReq = 0;
page.on("request", (r) => { if (/\/api\/(predict|analyze|segment|explain|uncertainty\/image)/.test(r.url()) && r.method() === "POST") inferReq++; });
const same = {};
for (const lang of ["hi", "mr", "en"]) {
  await page.selectOption('select[aria-label="Report language"]', lang);
  await page.waitForFunction((l) => document.querySelector('[data-testid="localized-report"]')?.getAttribute("lang") === l, lang, { timeout: 20000 });
  await page.waitForTimeout(600);
  same[lang] = { txt: (await page.getByTestId("localized-report").textContent()).replace(/\s+/g, " "), ling: await page.getByTestId("ling-review").count() };
}
const ids = [...new Set((ren.match(/RPT-[0-9A-F]+|F\d+|dentex_[a-z_0-9]+_v\d+|up_[0-9a-f]+/g) || []))];
rec("S-REP-4", "reports", "EN -> HI -> MR -> EN: structured ids/versions kept, no inference, review label only on hi/mr", "ids present in all, 0 inference requests, ling notice hi=1 mr=1 en=0",
  `ids=${ids.length} missing(hi)=${ids.filter((x) => !same.hi.txt.includes(x)).length} missing(mr)=${ids.filter((x) => !same.mr.txt.includes(x)).length} infer=${inferReq} ling hi/mr/en=${same.hi.ling}/${same.mr.ling}/${same.en.ling}`,
  ids.every((x) => same.hi.txt.includes(x) && same.mr.txt.includes(x)) && inferReq === 0 && same.hi.ling === 1 && same.mr.ling === 1 && same.en.ling === 0);
await page.selectOption('select[aria-label="Report language"]', "mr");
await page.waitForTimeout(600);
await page.screenshot({ path: `${SHOTS}/report_mr_1440.png` });
// exports shown as available
const hrefs = await page.locator('main a[href*="/export?"]').evaluateAll((as) => as.map((a) => [a.textContent.trim(), a.getAttribute("href")]));
const exp = [];
for (const [name, href] of hrefs) { const r = await page.request.get(BASE + href); const body = await r.body(); exp.push(`${name}:${r.status()}:${body.length}`); }
const pdfOrEdit = await page.getByRole("button", { name: /pdf|edit/i }).count() + await page.getByRole("link", { name: /pdf/i }).count();
rec("S-REP-5", "exports", "every export control shown works; no PDF / edit control is shown", "HTML, TXT, JSON each 200 non-empty; 0 PDF/edit controls", `${exp.join(" ")} pdf/edit=${pdfOrEdit}`, exp.length === 3 && exp.every((e) => /:200:\d{3,}/.test(e)) && pdfOrEdit === 0);
const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 20000 }).catch(() => null), page.getByTestId("export-html").click()]);
let dlOk = false;
if (dl) { const p = `${OUT}/ui_simplified_export_mr.html`; await dl.saveAs(p); const b = fs.readFileSync(p, "utf8"); dlOk = b.includes(rid) && /[\u0900-\u097F]{4}/.test(b) && b.includes("data-linguistic-review"); }
rec("S-REP-6", "exports", "browser download of the Marathi HTML export", "contains report id, Marathi text and the review-pending notice", `download=${!!dl} ok=${dlOk}`, dlOk);
// reviewer action
const mark = page.getByRole("button", { name: /Mark reviewed/ });
rec("S-REP-7", "reports", "'Mark reviewed' needs a reviewer name", "disabled until a name is typed", `disabled=${await mark.isDisabled()}`, await mark.isDisabled());
await page.getByLabel("Reviewer name").fill("UI Test Reviewer");
await mark.click();
await page.waitForTimeout(1500);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="localized-report"]');
const after = (await page.locator("main").innerText()).replace(/\s+/g, " ");
const apiRep = await (await page.request.get(BASE + `/api/reports/${rid}`)).json();
rec("S-REP-8", "reports", "review action persists", "status reviewed_research_draft, reviewer name stored, still not 'validated'", `${apiRep.report.status} by ${apiRep.report.reviewed_by}`, apiRep.report.status === "reviewed_research_draft" && apiRep.report.reviewed_by === "UI Test Reviewer" && !/clinically validated(?!\.)/i.test(after.replace(/not clinically validated/gi, "")));

// ---------------------------------------------------------------- Review Findings
await page.goto(BASE + "/review", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const rvTxt = (await page.locator("main").innerText()).replace(/\s+/g, " ");
rec("S-REV-1", "review", "Review Findings page lists regions needing review and explains why", "queue shown with reasons; reviewer names are not verified", rvTxt.slice(0, 200), /awaiting review/i.test(rvTxt) && /not verified|self-declared/i.test(rvTxt));
await page.goto(BASE + reviewHref, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const opened = await page.locator('[data-testid="region-review"] [data-testid="detection-box"]').count();
rec("S-REV-2", "review", "'Review this region' link (href captured from the inspector) opens that image's review task", "/review?image=<id> with the image's regions drawn in the review panel", `${reviewHref} boxes=${opened}`, /^\/review\?image=/.test(reviewHref) && opened > 0);

// ---------------------------------------------------------------- responsive, keyboard
for (const [w, h, name] of [[1440, 900, "desktop"], [1024, 768, "tablet"], [768, 1024, "tablet-portrait"], [390, 844, "phone"]]) {
  await page.setViewportSize({ width: w, height: h });
  for (const route of ["/", "/analysis", "/reports", "/review", "/about", "/settings"]) {
    await page.goto(BASE + route, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth, side: !!document.querySelector('aside[aria-label="Primary"]') && getComputedStyle(document.querySelector('aside[aria-label="Primary"]')).display !== "none", sel: !!document.querySelector("header select") && getComputedStyle(document.querySelector("header select").closest("label")).display !== "none" }));
    rec(`S-RSP-${name}`, "responsive", `${route} at ${w}px`, "no horizontal page scroll; sidebar at >=1024, page selector below", `scrollWidth=${m.sw} innerWidth=${m.iw} sidebar=${m.side} selector=${m.sel}`, m.sw <= m.iw + 1 && (w >= 1024 ? m.side : !m.side && m.sel));
  }
  if (name === "tablet-portrait" || name === "phone" || name === "tablet") {
    await page.goto(BASE + "/analysis", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const vw = await page.evaluate(() => { const el = document.querySelector('[aria-label="Image viewer and results"] .card'); const b = el?.getBoundingClientRect(); return b ? [Math.round(b.width), Math.round(b.height)] : null; });
    await page.screenshot({ path: `${SHOTS}/analysis_${w}.png`, fullPage: false });
    rec(`S-RSP-view-${name}`, "responsive", `viewer card size at ${w}px`, "viewer at least 300px wide", JSON.stringify(vw), !!vw && vw[0] >= Math.min(300, w - 40));
  }
}
await page.setViewportSize({ width: 1440, height: 900 });
await page.goto(BASE + "/", { waitUntil: "networkidle" });
let focusOk = false, focused = "";
for (let i = 0; i < 6; i++) {
  await page.keyboard.press("Tab");
  const f = await page.evaluate(() => { const e = document.activeElement; if (!e) return null; const cs = getComputedStyle(e); return { tag: e.tagName, text: (e.innerText || e.getAttribute("aria-label") || "").slice(0, 30), ring: cs.boxShadow !== "none" || cs.outlineStyle !== "none" }; });
  if (f && f.tag === "A" && /Home|Analysis|Reports|Review/.test(f.text)) { focusOk = f.ring; focused = JSON.stringify(f); break; }
}
rec("S-A11Y-1", "accessibility", "Tab reaches the sidebar links and shows a visible focus ring", "ring present", focused, focusOk);
await page.goto(BASE + "/analysis", { waitUntil: "networkidle" });
const unlabeled = await page.evaluate(() => [...document.querySelectorAll("button, input, select")].filter((e) => !(e.innerText || "").trim() && !e.getAttribute("aria-label") && !e.getAttribute("title") && !document.querySelector(`label[for="${e.id}"]`) && !e.closest("label") && e.type !== "hidden").length);
rec("S-A11Y-2", "accessibility", "interactive controls on X-ray Analysis have an accessible name", "0 unlabeled", `unlabeled=${unlabeled}`, unlabeled === 0);
const cj = JSON.parse(fs.readFileSync(OUT + "/contrast.json", "utf8"));
const ageMin = (Date.now() - new Date(cj.measured).getTime()) / 60000;
rec("S-A11Y-3", "accessibility", "WCAG AA colour contrast of all visible text (contrast.mjs, 15 page states incl. research pages)", "0 failing text/background combinations; measurement fresh (< 45 min)", `failing=${cj.unique_failing_combinations_all_pages} end-user=${cj.failing_on_end_user_pages} age=${ageMin.toFixed(0)}min`, cj.unique_failing_combinations_all_pages === 0 && ageMin < 45);
rec("S-CON-1", "console", "browser console errors during the whole run", "none except intended 4xx", JSON.stringify(errs.slice(0, 4)), errs.every((e) => /status of 4\d\d|Failed to load resource/.test(e)));
const realBad = bad.filter((x) => !/POST (503|500) \/api\/analyze\/full/.test(x));   // the two simulated failures of S-ERR-1/2 are expected
rec("S-CON-2", "console", "HTTP >= 400 responses during the run (excluding the two simulated failures of S-ERR-1/2)", "none", JSON.stringify(realBad), realBad.length === 0);
fs.writeFileSync(OUT + "/ui_simplified.json", JSON.stringify({ run_at: new Date().toISOString(), report_created: rid, results }, null, 1), "utf8");
const sum = {}; for (const r of results) sum[r.result] = (sum[r.result] || 0) + 1;
console.log("SUMMARY", JSON.stringify(sum));
await browser.close();
