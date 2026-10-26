// Build report.docx from report.md with the official Apart template's settings
// (Letter, 1" margins, 11 pt Arial at 1.15 lines, Old Standard TT title, 16 pt section headings).
// Usage: NODE_PATH=<dir with docx installed> node build_docx.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, LevelFormat, BorderStyle, FootnoteReferenceRun,
} = require("docx");

const HERE = __dirname;
const src = fs.readFileSync(path.join(HERE, "report.md"), "utf8");
const FONT = "Arial";
const BODY = 22;          // half-points: 11 pt, as in the official template
const PAGE_W = 12240, MARGIN = 1440, CONTENT_W = PAGE_W - 2 * MARGIN;

// ---- front matter -----------------------------------------------------------------------
const fm = {};
let body = src;
const m = src.match(/^---\n([\s\S]*?)\n---\n/);
if (m) {
  for (const line of m[1].split("\n")) {
    const mm = line.match(/^(\w+):\s*"?(.*?)"?$/);
    if (mm) fm[mm[1]] = mm[2];
  }
  body = src.slice(m[0].length);
}

// ---- inline: **bold**, `code` -------------------------------------------------------------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, mt;
  while ((mt = re.exec(text))) {
    if (mt.index > last) out.push(new TextRun({ text: text.slice(last, mt.index), font: FONT, size: BODY, ...base }));
    const tok = mt[0];
    if (tok.startsWith("**")) out.push(new TextRun({ text: tok.slice(2, -2), bold: true, font: FONT, size: BODY, ...base }));
    else out.push(new TextRun({ text: tok.slice(1, -1), font: "Courier New", size: BODY - 2, ...base }));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size: BODY, ...base }));
  return out;
}
const para = (text, opts = {}) => new Paragraph({ children: runs(text, opts.run || {}), spacing: { after: 120, line: 276 }, ...opts.p });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}

// ---- table --------------------------------------------------------------------------------
function table(lines) {
  const rows = lines.filter(l => !/^\|\s*-/.test(l)).map(l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()));
  const n = rows[0].length;
  const colW = Math.floor(CONTENT_W / n);
  const widths = Array(n).fill(colW);
  widths[n - 1] = CONTENT_W - colW * (n - 1);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB" };
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0,
      children: r.map((c, j) => new TableCell({
        width: { size: widths[j], type: WidthType.DXA },
        borders: { top: border, bottom: border, left: border, right: border },
        shading: i === 0 ? { type: ShadingType.CLEAR, fill: "EFEFEC", color: "auto" } : undefined,
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: [new Paragraph({ children: runs(c, { size: BODY - 3, bold: i === 0 }) })],
      })),
    })),
  });
}

// ---- body ---------------------------------------------------------------------------------
const children = [];
// Title + sprint footnote (template: footnote on the title)
children.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: fm.title || "PROJECT TITLE", bold: true, font: "Old Standard TT", size: 40 }),
             new FootnoteReferenceRun(1)],
}));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0 },
  children: [new TextRun({ text: fm.author || "", bold: true, font: FONT, size: BODY + 2 })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 },
  children: [new TextRun({ text: fm.affiliation || "", italics: true, font: FONT, size: BODY })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 },
  children: [new TextRun({ text: "With Apart Research", italics: true, font: FONT, size: BODY })] }));

const lines = body.split("\n");
let i = 0;
let listRef = 0;
while (i < lines.length) {
  const l = lines[i];
  if (!l.trim()) { i++; continue; }
  if (l.startsWith("# ")) {
    const t = l.slice(2).trim();
    const isAbstract = t === "Abstract";
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_2, keepNext: true, spacing: { before: isAbstract ? 120 : 360, after: 120 },
      alignment: isAbstract ? AlignmentType.LEFT : undefined,
      children: [new TextRun({ text: t, font: FONT, size: 32, color: "000000" })],
    }));
    i++; continue;
  }
  if (l.startsWith("```")) {
    i++;
    while (i < lines.length && !lines[i].startsWith("```")) {
      children.push(new Paragraph({ spacing: { after: 0 }, shading: { type: ShadingType.CLEAR, fill: "F4F4F2", color: "auto" },
        children: [new TextRun({ text: lines[i] || " ", font: "Courier New", size: 15 })] }));
      i++;
    }
    i++; children.push(new Paragraph({ children: [] })); continue;
  }
  if (l.startsWith("|")) {
    const tl = [];
    while (i < lines.length && lines[i].startsWith("|")) { tl.push(lines[i]); i++; }
    children.push(table(tl));
    children.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
    continue;
  }
  const img = l.match(/^!\[(.*)\]\((.*)\)\s*$/);
  if (img) {
    const file = path.resolve(HERE, img[2]);
    const { w, h, data } = pngSize(file);
    const outW = 450, outH = Math.round(outW * h / w);
    children.push(new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 },
      children: [new ImageRun({ type: "png", data, transformation: { width: outW, height: outH } })] }));
    const cap = img[1];
    const k = cap.indexOf(".");
    children.push(new Paragraph({ spacing: { after: 200 },
      children: [new TextRun({ text: cap.slice(0, k + 1), bold: true, font: FONT, size: BODY - 2 }),
                 new TextRun({ text: cap.slice(k + 1), font: FONT, size: BODY - 2 })] }));
    i++; continue;
  }
  if (/^\d+\.\s/.test(l) || /^- /.test(l)) {
    const numbered = /^\d+\.\s/.test(l);
    const ref = numbered ? `num${listRef++}` : "bullets";
    while (i < lines.length && (numbered ? /^\d+\.\s/.test(lines[i]) : /^- /.test(lines[i]))) {
      const text = lines[i].replace(/^(\d+\.|-)\s+/, "");
      children.push(new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 264 },
        children: runs(text) }));
      i++;
    }
    children.push(new Paragraph({ spacing: { after: 60 }, children: [] }));
    continue;
  }
  // paragraph: join consecutive non-empty plain lines
  const buf = [l];
  i++;
  while (i < lines.length && lines[i].trim() && !/^(# |```|\||!\[|- |\d+\.\s)/.test(lines[i])) { buf.push(lines[i]); i++; }
  children.push(para(buf.join(" ")));
}

const numConfigs = [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
  alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }];
for (let k = 0; k < listRef; k++) numConfigs.push({ reference: `num${k}`, levels: [{ level: 0, format: LevelFormat.DECIMAL,
  text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] });

const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: { config: numConfigs },
  footnotes: { 1: { children: [new Paragraph({ children: [new TextRun({
    text: "Research conducted at the AI Collusion Research Sprint, October 2026", font: FONT, size: 16 })] })] } },
  sections: [{ properties: { page: { size: { width: PAGE_W, height: 15840 },
    margin: { top: 1440, bottom: 1440, left: MARGIN, right: MARGIN } } }, children }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(path.join(HERE, "report.docx"), b); console.log("wrote report.docx"); });
