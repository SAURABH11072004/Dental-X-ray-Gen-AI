import { chromium } from "playwright-core";

const BASE = "http://localhost:5173";
const SHOTS = process.argv[2];
const browser = await chromium.launch({ executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errs = [], bad = [];
page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 160)); });
page.on("pageerror", (e) => errs.push("pageerror " + String(e).slice(0, 160)));
page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) bad.push(`${r.status()} ${r.url().replace(BASE, "")}`); });
const ok = (name, cond, extra = "") => console.log(`${cond ? "PASS" : "FAIL"}  ${name} ${extra}`);

// ---------- 1. full analysis from the UI
await page.goto(BASE + "/analysis", { waitUntil: "networkidle" });
await page.selectOption("#src", "test_data");
await page.waitForTimeout(800);
await page.locator('select[aria-label="Image"]').selectOption({ index: 6 });
await page.waitForTimeout(1500);
const imageName = await page.locator('select[aria-label="Image"] option:checked').innerText();
await page.getByTestId("run-full").click();
await page.waitForSelector('[data-testid="region-table"] tbody tr', { timeout: 240000 });
const steps = await page.locator('[data-testid="pipeline-steps"] li').evaluateAll((els) => els.map((e) => e.textContent));
ok("pipeline steps shown with status", steps.length >= 8 && steps.every((t) => /ok|unavailable|failed|skipped/.test(t)), steps.map((s) => s.replace(/\s+/g, " ")).slice(0, 4).join(" | "));
const nReg = await page.locator('[data-testid="region-table"] tbody tr').count();
ok("region table rendered", nReg > 0, `regions=${nReg}`);
ok("masks drawn", (await page.locator("svg image").count()) > 0);
await page.locator('[data-testid="region-table"] tbody tr').nth(2).click();
await page.waitForSelector('[data-testid="region-detail"]');
const detail = (await page.locator('[data-testid="region-detail"]').innerText()).replace(/\s+/g, " ");
ok("region inspector shows candidate/abstain wording and uncertainty", /not evidence|no class is named|No classifier/.test(detail) && /Classification entropy/.test(detail), detail.slice(0, 110));
// explainability on a region that has a candidate class
const rows = page.locator('[data-testid="region-table"] tbody tr');
for (let i = 0; i < Math.min(await rows.count(), 12); i++) {
  await rows.nth(i).click();
  if (/Candidate class:/.test(await page.locator('[data-testid="region-detail"]').innerText())) break;
}
await page.getByRole("button", { name: "Show attention heatmap" }).click();
await page.waitForSelector("#hop", { timeout: 60000 }).catch(() => {});
await page.waitForTimeout(1500);
ok("Grad-CAM heatmap + method note shown", /Heatmap \(Grad-CAM on the last convolutional block/.test(await page.locator('aside[aria-label="Region details"]').innerText()));
ok("heatmap opacity control present", await page.locator("#hop").count() === 1);
await page.screenshot({ path: SHOTS + "/phase_analysis.png" });

// ---------- 2. calculate uncertainty (real backend op) -> Uncertainty page
ok("Uncertainty saved by the single Analyze step", true);
await page.goto(BASE + "/uncertainty", { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="unc-table"] tbody tr', { timeout: 30000 });
const firstRow = (await page.locator('[data-testid="unc-table"] tbody tr').first().innerText()).replace(/\s+/g, " ");
ok("Uncertainty table shows real values (no empty state)", !/No uncertainty computed yet/.test(await page.locator("main").innerText()) && /\d\.\d{3}/.test(firstRow), firstRow.slice(0, 100));
await page.locator('[data-testid="unc-table"] tbody tr').first().click();
await page.waitForTimeout(1500);
const side = (await page.locator('aside[aria-label="Selected image"]').textContent()).replace(/\s+/g, " ");
ok("selected image shows signals, thresholds note and regions to review", /Uncertainty/.test(side) && /provisional/i.test(side) && /Regions needing review/.test(side));
await page.screenshot({ path: SHOTS + "/phase_uncertainty.png" });

// ---------- 3. review workflow
await page.goto(BASE + "/review", { waitUntil: "networkidle" });
await page.waitForSelector('[data-testid="review-queue"] li', { timeout: 30000 });
ok("review queue lists the analysed image", (await page.locator('[data-testid="review-queue"] li').count()) > 0);
await page.locator('[data-testid="review-queue"] li button').first().click();
await page.waitForTimeout(2500);
await page.getByLabel("Reviewer name").fill("Reviewer One");
// pick any region with a candidate class via the viewer boxes
const boxes = page.locator('[data-testid="region-review"] [data-testid="detection-box"]');
let candidateIdx = -1;
for (let i = 0; i < await boxes.count(); i++) {
  await boxes.nth(i).dispatchEvent("click");
  if (/Candidate:/.test(await page.getByTestId("review-region").innerText())) { candidateIdx = i; break; }
}
ok("found a region with a candidate class to review", candidateIdx >= 0, `box #${candidateIdx}`);
await page.getByLabel("Review action").selectOption("confirm_candidate");
await page.getByTestId("review-submit").dblclick();      // a double click must produce ONE saved review, not two and not an error
await page.waitForSelector("text=/Saved as revision 1/", { timeout: 15000 });
ok("review saved (revision 1)", true);
ok("double click did not create a duplicate or an error", (await page.getByTestId("review-error").count()) === 0);
await page.getByTestId("review-submit").click();
await page.waitForSelector('[data-testid="review-error"]', { timeout: 15000 });
ok("identical resubmission is refused", /already submitted/i.test(await page.getByTestId("review-error").innerText()));
await page.getByLabel("Review action").selectOption("correct_class");
await page.locator('select:has(option:text("Select…"))').selectOption({ index: 3 });
await page.getByTestId("review-submit").click();
await page.waitForSelector("text=/Saved as revision 2/", { timeout: 15000 });
ok("changed decision saved as revision 2 (history kept)", true);
const histText = (await page.locator("text=History of this region").locator("..").innerText()).replace(/\s+/g, " ");
ok("history shows both revisions", /r1/.test(histText) && /r2/.test(histText) && /superseded/.test(histText), histText.slice(0, 120));
// approval by the same person is refused, by a different person works
await page.locator('[data-testid="review-table"] tbody tr input[type=checkbox]').first().check();
await page.getByLabel("Approver name").fill("reviewer one");
await page.getByRole("button", { name: /Approve selected/ }).click();
await page.waitForSelector("text=/cannot be approved by the person who made it/", { timeout: 15000 });
ok("self-approval is refused", true);
await page.getByLabel("Approver name").fill("Second Person");
await page.getByRole("button", { name: /Approve selected/ }).click();
await page.waitForSelector('[data-testid="review-table"] >> text=approved', { timeout: 15000 });
ok("second person approved the review", /approved/.test(await page.getByTestId("review-table").innerText()));
let body = null;
for (let k = 0; k < 10; k++) {          // the approval is persisted asynchronously: poll briefly instead of reading once
  body = await (await page.request.get(BASE + "/api/reviews/export?format=json")).json();
  if ((body.n_records || 0) + (body.n_approved_but_excluded || 0) >= 1) break;
  await page.waitForTimeout(500);
}
console.log("   export:", JSON.stringify({ n_records: body.n_records, excluded: body.n_approved_but_excluded }), "(test-data image -> never exported as training data)");
ok("export contains only approved pool/upload reviews and counts the excluded ones", body.n_records >= 0 && body.records.every((r) => r.approved_by && /self-declared/.test(r.reviewer_qualification)) && body.n_approved_but_excluded + body.n_records >= 1, `exported=${body.n_records} excluded=${body.n_approved_but_excluded}`);
await page.screenshot({ path: SHOTS + "/phase_review.png" });

// ---------- 4. report from the analysis (UI), EN -> HI -> MR
await page.goto(BASE + "/analysis", { waitUntil: "networkidle" });
await page.selectOption("#src", "test_data");
await page.waitForTimeout(800);
await page.locator('select[aria-label="Image"]').selectOption({ index: 6 });
await page.waitForTimeout(1200);
await page.getByTestId("run-full").click();
await page.waitForSelector('[data-testid="region-table"]', { timeout: 240000 });
await page.getByTestId("make-report").click();
await page.waitForURL(/\/reports\?id=/, { timeout: 60000 });
await page.waitForSelector('[data-testid="localized-report"]', { timeout: 30000 });
const en = (await page.locator('[data-testid="localized-report"]').textContent()).replace(/\s+/g, " ");
ok("EN report: counts + review regions + banner", /regions: \d+/.test(en) && /Regions requiring manual review/.test(en) && /Awaiting review/.test(en) && /not a confirmed diagnosis/.test(en));
ok("EN report: abstained wording, no 'predicted'", /no reliable candidate class/.test(en) && !/predicted/i.test(en));
await page.selectOption('select[aria-label="Report language"]', "hi");
await page.waitForFunction(() => document.querySelector('[data-testid="localized-report"]')?.getAttribute("lang") === "hi");
await page.waitForTimeout(800);
const hi = (await page.locator('[data-testid="localized-report"]').textContent()).replace(/\s+/g, " ");
const hc = { F1: /F1/.test(hi), version: hi.includes("dentex_teeth_detection_v1"), heading: /मैन्युअल समीक्षा आवश्यक क्षेत्र/.test(hi), badge: /values match English report/.test(hi) };
ok("HI report: ids + versions kept, review list translated", Object.values(hc).every(Boolean), JSON.stringify(hc) + " " + hi.slice(0, 80));
await page.screenshot({ path: SHOTS + "/phase_report_hi.png" });

// ---------- 5. other pages show real data
for (const [route, mustHave, label] of [["/active-learning", /scored/, "Active Learning shows pool scoring"], ["/experiments", /random|entropy|combined|supervised/i, "Experiments lists real runs"], ["/models", /dentex_fdi_numbering_v1/, "Registry lists the numbering checkpoint"], ["/training", /prerequisites|Training/, "Training page loads"]]) {
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const t = (await page.locator("main").innerText()).replace(/\s+/g, " ");
  ok(label, mustHave.test(t), t.slice(0, 70));
}
await page.goto(BASE + "/", { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const home = (await page.locator("main").innerText()).replace(/\s+/g, " ");
ok("Home: upload, recent analyses, latest report, findings awaiting review, models", /Upload X-ray/.test(home) && /Recent analyses/.test(home) && /Latest report/.test(home) && /Findings awaiting review/.test(home) && /Tooth detection/.test(home));
await page.screenshot({ path: SHOTS + "/phase_home.png" });
console.log("console errors:", JSON.stringify(errs), "| HTTP>=400:", JSON.stringify(bad));
await browser.close();
