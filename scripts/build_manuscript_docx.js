// Build the journal manuscript (.docx) from its audited Markdown source.
//   NODE_PATH=<dir with the `docx` npm package> node scripts/build_manuscript_docx.js <source.md> <figures_dir> <output.docx>
// * Source tags (`[row-id]`, `[cv5:...]`, `[boot:...]`) are removed; numbers are copied verbatim from the audited source.
// * [CITE: a; b] becomes numbered citations in order of first appearance; reference texts are read from
//   documents/dentist-research-figures/build_paper.js (DOIs checked there against Crossref / DataCite).
// * Tables drop their "Source" column. Figures are embedded before their legends. A4, Times New Roman 12 pt, 1.5 spacing,
//   continuous line numbers, page numbers. Refuses to overwrite an existing output file.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType, HeadingLevel, WidthType,
  BorderStyle, Footer, PageNumber, LevelFormat, ShadingType, LineNumberRestartFormat, PageBreak,
} = require("docx");

const [SRC, FIG, OUT] = process.argv.slice(2);
if (!SRC || !FIG || !OUT) throw new Error("usage: build_manuscript_docx.js <source.md> <figures_dir> <output.docx>");
if (fs.existsSync(OUT)) throw new Error(`${OUT} exists: write a new version instead of overwriting`);
const ROOT = path.resolve(__dirname, "..");
const FONT = "Times New Roman";
const TEXT_W = 9026; // A4 width 11906 minus 2 x 1440 margins

// ---------------------------------------------------------------- references
const REFSRC = fs.readFileSync(path.join(ROOT, "documents", "dentist-research-figures", "build_paper.js"), "utf8");
const REFS = {};
for (const m of REFSRC.matchAll(/^\s{2}(\w+): \{ t: "((?:[^"\\]|\\.)*)"/gm)) REFS[m[1]] = JSON.parse(`"${m[2]}"`);
const order = [];
const cite = (keys) => keys.split(";").map((k) => k.trim()).map((k) => {
  if (!REFS[k]) throw new Error(`no reference text for key ${k}`);
  if (!order.includes(k)) order.push(k);
  return order.indexOf(k) + 1;
});
const fmtNums = (ns) => {
  ns = [...new Set(ns)].sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < ns.length; i++) {
    let j = i;
    while (j + 1 < ns.length && ns[j + 1] === ns[j] + 1) j++;
    out.push(j - i >= 2 ? `${ns[i]}–${ns[j]}` : ns.slice(i, j + 1).join(", "));
    i = j;
  }
  return `[${out.join(", ")}]`;
};

// ---------------------------------------------------------------- inline formatting
function clean(s) {
  return s.replace(/\s*`\[[^\]`]+\]`/g, "")                            // source tags
          .replace(/\[CITE:\s*([^\]]+)\]/g, (_, k) => fmtNums(cite(k)))
          .replace(/`([^`]*)`/g, "$1")
          .replace(/\s+([,.;:)])/g, "$1").replace(/\s{2,}/g, " ").trim();
}
function runs(s, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\{i\}.*?\{\/i\})/g;
  let last = 0;
  for (const m of s.matchAll(re)) {
    if (m.index > last) out.push(new TextRun({ text: s.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("{i}")) out.push(new TextRun({ text: t.slice(3, -4), italics: true, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < s.length) out.push(new TextRun({ text: s.slice(last), ...base }));
  return out;
}
const para = (s, opts = {}) => new Paragraph({ children: runs(clean(s)), spacing: { after: 120 }, ...opts });

// ---------------------------------------------------------------- tables
function table(lines) {
  const rows = lines.filter((l) => !/^\|\s*-/.test(l)).map((l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
  const keep = rows[0].map((h, i) => (h.toLowerCase() === "source" ? -1 : i)).filter((i) => i >= 0);
  const n = keep.length;
  const first = Math.round(TEXT_W * (n > 4 ? 0.22 : 0.3));
  const widths = keep.map((_, j) => (j === 0 ? first : Math.floor((TEXT_W - first) / (n - 1))));
  widths[n - 1] += TEXT_W - widths.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "808080" };
  return new Table({
    width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, ri) => new TableRow({
      tableHeader: ri === 0,
      children: keep.map((ci, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        borders: { top: border, bottom: border, left: border, right: border },
        shading: ri === 0 ? { type: ShadingType.CLEAR, fill: "E7EEF5", color: "auto" } : undefined,
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: [new Paragraph({ children: runs(clean(r[ci] || ""), { size: 18, bold: ri === 0 }), spacing: { line: 240 } })],
      })),
    })),
  });
}

// ---------------------------------------------------------------- figures
const figFiles = Object.fromEntries(fs.readdirSync(FIG).filter((f) => f.endsWith(".png")).map((f) => [f.match(/^fig(\d+)/)[1], f]));
function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function figure(n) {
  const buf = fs.readFileSync(path.join(FIG, figFiles[n]));
  const { w, h } = pngSize(buf);
  const width = Math.min(600, Math.round((w / 300) * 96 * 1.15)); // natural size (300 dpi source), slightly enlarged, max 6.25 in
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 240, after: 120 }, keepNext: true,
    children: [new ImageRun({ type: "png", data: buf, transformation: { width, height: Math.round((width * h) / w) } })] });
}

// ---------------------------------------------------------------- body
const src = fs.readFileSync(SRC, "utf8").split(/\r?\n/);
const body = [];
const numberingConfigs = [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
  alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }];
const REFS_MARKER = { refs: true };
let olCount = 0, inOl = false, title = "";
let i = 0;
while (i < src.length) {
  let line = src[i];
  const s = line.trim();
  if (!s) { inOl = false; i++; continue; }
  if (s.startsWith("**Source file")) { i++; continue; }                     // build note, not manuscript text
  if (s.startsWith("# ")) { title = clean(s.slice(2)); body.push(new Paragraph({ heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER,
    spacing: { after: 240 }, children: runs(title, { size: 32, bold: true }) })); i++; continue; }
  if (s.startsWith("## ")) {
    const h = clean(s.slice(3));
    if (["Abstract", "Figure legends", "Supplementary Material S1: reproducibility", "Declarations"].includes(h) ||
        h.startsWith("1. Introduction")) body.push(new Paragraph({ children: [new PageBreak()] }));
    if (h === "Title page") { i++; continue; }
    if (h === "Figure legends") body.splice(body.length - 1, 0, REFS_MARKER);   // references go after the declarations
    body.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: runs(h), spacing: { before: 240, after: 120 } }));
    i++; continue;
  }
  if (s.startsWith("### ")) { body.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: runs(clean(s.slice(4))),
    spacing: { before: 200, after: 100 } })); i++; continue; }
  if (s.startsWith("|")) { const t = []; while (i < src.length && src[i].trim().startsWith("|")) t.push(src[i++]); body.push(table(t));
    body.push(new Paragraph({ children: [], spacing: { after: 120 } })); continue; }
  // gather continuation lines
  const isItem = /^(\*|-)\s/.test(s) || /^\d+\.\s/.test(s);
  let text = s;
  i++;
  while (i < src.length && src[i].trim() && !/^(\*|-|\||#)\s?/.test(src[i].trim()) && !/^\d+\.\s/.test(src[i].trim()) &&
         !src[i].trim().startsWith("**") && (isItem ? /^\s+/.test(src[i]) : true)) text += " " + src[i++].trim();
  const fig = text.match(/^\*\*Figure (\d+)\.\*\*/);
  if (fig) body.push(figure(fig[1]));
  if (/^(\*|-)\s/.test(text)) {
    const indent = /^\s{2,}/.test(line) ? 1 : 0;
    body.push(new Paragraph({ numbering: { reference: "bullets", level: 0 }, indent: indent ? { left: 900, hanging: 270 } : undefined,
      children: runs(clean(text.replace(/^(\*|-)\s/, ""))), spacing: { after: 60 } }));
  } else if (/^\d+\.\s/.test(text)) {
    if (!inOl) { olCount++; inOl = true; numberingConfigs.push({ reference: `ol${olCount}`, levels: [{ level: 0, format: LevelFormat.DECIMAL,
      text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] }); }
    body.push(new Paragraph({ numbering: { reference: `ol${olCount}`, level: 0 }, children: runs(clean(text.replace(/^\d+\.\s/, ""))),
      spacing: { after: 60 } }));
  } else {
    inOl = false;
    body.push(para(text, fig ? { keepLines: true } : {}));
  }
}

// references after the declarations, before the figure legends
const refsParas = [new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("References")], spacing: { before: 240, after: 120 } }),
  ...order.map((k, n) => new Paragraph({ children: [new TextRun(`[${n + 1}] `), ...runs(REFS[k])], indent: { left: 540, hanging: 540 },
    spacing: { after: 80 } }))];
const at = body.indexOf(REFS_MARKER);
if (at < 0) throw new Error("no 'Figure legends' section: cannot place the references");
body.splice(at, 1, ...refsParas);

const doc = new Document({
  creator: "DentaMind AI authors", title,
  styles: {
    default: { document: { run: { font: FONT, size: 24 }, paragraph: { spacing: { line: 360 } } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", run: { font: FONT, size: 32, bold: true } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 26, bold: true },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, size: 24, bold: true, italics: true }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: numberingConfigs },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } },
      lineNumbers: { countBy: 1, restart: LineNumberRestartFormat.CONTINUOUS } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT] })] })] }) },
    children: body,
  }],
});
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf, { flag: "wx" });
  console.log(`wrote ${OUT}: ${order.length} references, ${Object.keys(figFiles).length} figures`);
});
