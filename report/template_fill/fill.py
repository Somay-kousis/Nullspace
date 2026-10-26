"""Fill the official Apart template (.docx) with report.md, cloning the template's own paragraph formats.

Usage: python3 fill.py <template.docx> <report.md> <out.docx>
"""
import os, re, struct, sys, shutil, zipfile, tempfile
from split import split_body

TPL, MD, OUT = sys.argv[1:4]
MDDIR = os.path.dirname(os.path.abspath(MD))
F = ('<w:rFonts w:ascii="Old Standard TT" w:cs="Old Standard TT" '
     'w:eastAsia="Old Standard TT" w:hAnsi="Old Standard TT"/>')
MONO = '<w:rFonts w:ascii="Courier New" w:cs="Courier New" w:eastAsia="Courier New" w:hAnsi="Courier New"/>'

tmp = tempfile.mkdtemp()
with zipfile.ZipFile(TPL) as z:
    z.extractall(tmp)
docp = os.path.join(tmp, "word", "document.xml")
doc = open(docp, encoding="utf-8").read()
pre, items, post = split_body(doc)
X = [x for _, x in items]

def clean(x):
    x = re.sub(r'\s*w14:paraId="[^"]*"', "", x)
    x = re.sub(r'\s*w14:textId="[^"]*"', "", x)
    x = re.sub(r"<w:bookmarkStart[^>]*/>|<w:bookmarkEnd[^>]*/>", "", x)
    return x

def ppr(x):
    return re.search(r"<w:pPr>.*?</w:pPr>", x, flags=re.S).group(0)

def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def run(t, bold=False, italic=False, size=None, font=F):
    rp = font + ('<w:b w:val="1"/><w:bCs w:val="1"/>' if bold else "") + \
         ('<w:i w:val="1"/><w:iCs w:val="1"/>' if italic else "") + \
         (f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else "")
    return f'<w:r><w:rPr>{rp}</w:rPr><w:t xml:space="preserve">{esc(t)}</w:t></w:r>'

def runs(text, size=None, bold_all=False):
    out, pos = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*|`([^`]+)`", text):
        if m.start() > pos:
            out.append(run(text[pos:m.start()], bold=bold_all, size=size))
        if m.group(1) is not None:
            out.append(run(m.group(1), bold=True, size=size))
        else:
            out.append(run(m.group(2), size=(size or 22) - 3, font=MONO))
        pos = m.end()
    if pos < len(text):
        out.append(run(text[pos:], bold=bold_all, size=size))
    return "".join(out)

# prototypes, all taken from the template itself
P_BODY = ppr(clean(X[5])).replace("<w:pPr>", '<w:pPr><w:spacing w:after="120"/>', 1)   # body text, 6 pt after instead of a blank line
BLANK = clean(X[7])                 # blank line the template puts between paragraphs
P_H2, H2_RPR = ppr(clean(X[4])), re.search(r"<w:r\b.*?<w:rPr>(.*?)</w:rPr>", clean(X[4]), flags=re.S).group(1)
P_H3, H3_RPR = ppr(clean(X[49])), re.search(r"<w:r\b.*?<w:rPr>(.*?)</w:rPr>", clean(X[49]), flags=re.S).group(1)
P_NUM = ppr(clean(X[14]))           # numbered list (contributions), numId 5
P_REF = ppr(clean(X[71]))           # references list, numId 1
P_DASH = ppr(clean(X[61]))          # dash bullets (Code and Data), numId 3

def para(pp, body):
    return f"<w:p>{pp}{body}</w:p>"

def heading(pp, rpr, text):
    rpr = rpr.replace('<w:rtl w:val="0"/>', "")
    return f'<w:p>{pp}<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'

# ---- images -----------------------------------------------------------------------
rels_p = os.path.join(tmp, "word", "_rels", "document.xml.rels")
rels = open(rels_p, encoding="utf-8").read()
os.makedirs(os.path.join(tmp, "word", "media"), exist_ok=True)
img_n = [0]

def image(path, width_in=4.8):
    img_n[0] += 1
    n = img_n[0]
    shutil.copy(path, os.path.join(tmp, "word", "media", f"image{n}.png"))
    global rels
    rid = f"rIdImg{n}"
    rels = rels.replace("</Relationships>",
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{n}.png"/></Relationships>')
    w, h = struct.unpack(">II", open(path, "rb").read()[16:24])
    cx = int(width_in * 914400); cy = int(cx * h / w)
    return (f'<w:p><w:pPr><w:keepNext w:val="1"/><w:spacing w:before="120" w:after="60"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:docPr id="{100 + n}" name="Figure {n}"/>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{100 + n}" name="image{n}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
            f'</wp:inline></w:drawing></w:r></w:p>')

def caption(text):
    k = text.index(".")
    return para(P_BODY, run(text[:k + 1], bold=True, size=20) + runs(text[k + 1:], size=20))

# ---- tables -----------------------------------------------------------------------
def table(lines):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines if not re.match(r"^\|\s*-", l)]
    n = len(rows[0]); W = 9360; cw = W // n
    b = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
    borders = "".join(b.format(s) for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{cw}"/>' for _ in range(n))
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{W}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>{borders}</w:tblBorders>'
           f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>{grid}</w:tblGrid>']
    for i, r in enumerate(rows):
        cells = "".join(
            f'<w:tc><w:tcPr><w:tcW w:w="{cw}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>{runs(c, size=19, bold_all=(i == 0))}</w:p></w:tc>'
            for c in r)
        out.append(f'<w:tr>{"<w:trPr><w:tblHeader/></w:trPr>" if i == 0 else ""}{cells}</w:tr>')
    out.append("</w:tbl>")
    return "".join(out)

# ---- markdown -> blocks -------------------------------------------------------------
src = open(MD, encoding="utf-8").read()
fm = dict(re.findall(r'^(\w+):\s*"?(.*?)"?$', src.split("---")[1], flags=re.M))
body_md = src.split("---", 2)[2]
sections, cur = {}, None
for line in body_md.split("\n"):
    if line.startswith("# "):
        cur = line[2:].strip(); sections[cur] = []
    elif cur is not None:
        sections[cur].append(line)

def blocks(lines, list_pp=P_DASH, num_pp=P_NUM):
    """Paragraphs separated by the template's blank line; lists and code kept tight."""
    out, i = [], 0
    def gap():
        pass
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            i += 1; continue
        if l.startswith("```"):
            gap(); i += 1
            while not lines[i].startswith("```"):
                out.append(para('<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>',
                                run(lines[i] or " ", size=15, font=MONO)))
                i += 1
            i += 1; continue
        if l.startswith("|"):
            tl = []
            while i < len(lines) and lines[i].startswith("|"):
                tl.append(lines[i]); i += 1
            out.append(table(tl)); continue
        m = re.match(r"^!\[(.*)\]\((.*)\)\s*$", l)
        if m:
            gap(); out.append(image(os.path.normpath(os.path.join(MDDIR, m.group(2)))))
            out.append(caption(m.group(1))); out.append(BLANK); i += 1; continue
        if re.match(r"^(\d+\.|-)\s", l):
            gap(); numbered = l[0].isdigit()
            while i < len(lines) and re.match(r"^(\d+\.|-)\s", lines[i]):
                t = re.sub(r"^(\d+\.|-)\s+", "", lines[i])
                out.append(para(num_pp if numbered else list_pp, runs(t))); i += 1
            continue
        buf = [l]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|```|\||!\[|\d+\.\s|-\s)", lines[i]):
            buf.append(lines[i]); i += 1
        out.append(para(P_BODY, runs(" ".join(buf))))
    while out and out[-1] == BLANK:
        out.pop()
    return out

def code_data(lines):
    out = []
    for l in lines:
        m = re.match(r"^- ([^:]+):\s*(.*)$", l)
        if m:
            out.append(para(P_DASH, run(m.group(1), bold=True) + run(": " + m.group(2))))
    return out

# ---- title block: fill the template's own table ---------------------------------------
t = X[1]
t = t.replace(">PROJECT TITLE<", f">{esc(fm['title'])}<")
# second author row (authors 4-6) removed; author in the middle cell of the first row
trs = [m for m in re.finditer(r"<w:tr>", t)]
row2_start = t.index("Author name 4"); r0 = t.rfind("<w:tr>", 0, row2_start); r1 = t.index("</w:tr>", row2_start) + 7
t = t[:r0] + t[r1:]
# the template's author table has 690-twip columns; widen them so name and affiliation fit
t = t.replace('<w:tblW w:w="2070.0" w:type="dxa"/>', '<w:tblW w:w="6480.0" w:type="dxa"/>')
t = t.replace('<w:gridCol w:w="690"/>', '<w:gridCol w:w="2160"/>')
t = t.replace(">Author name 2<", f">{esc(fm['author'])}<", 1)
aff = [m.start() for m in re.finditer(r">Affiliation<", t)]
t = t[:aff[1]] + f">{esc(fm['affiliation'])}<" + t[aff[1] + len(">Affiliation<"):]
t = t.replace(">Author name 1<", "><").replace(">Author name 3<", "><").replace(">Affiliation<", "><")
# abstract text: keep the paragraph's own pPr (indent, justified), plain runs
abs_txt = " ".join(x.strip() for x in sections["Abstract"] if x.strip())
i = t.index("Summarize your project"); p0 = t.rfind("<w:p ", 0, i); p1 = t.index("</w:p>", i) + 6
ap = ppr(t[p0:p1]).replace('<w:u w:val="single"/>', "")
t = t[:p0] + para(ap, run(abs_txt)) + t[p1:]

# ---- assemble -------------------------------------------------------------------------
disc = sections["5. Discussion and Limitations"]
li = next(k for k, l in enumerate(disc) if l.startswith("**Limitations.**"))
fi = next(k for k, l in enumerate(disc) if l.startswith("**Future work.**"))
disc_main, disc_lim = disc[:li], disc[li + 1:fi]
disc_fut = [disc[fi].replace("**Future work.** ", "")] + disc[fi + 1:]
refs = [l for l in sections["References"] if re.match(r"^\d+\.\s", l)]

new = [X[0], t, X[2]]                                       # X[3], the guidance box, is dropped
def sec(head_idx, content):
    new.append(clean(X[head_idx])); new.extend(content); new.append(clean(X[17]))
sec(4, blocks(sections["1. Introduction"]))
sec(18, blocks(sections["2. Related Work"]))
sec(26, blocks(sections["3. Methods"]))
sec(31, blocks(sections["4. Results"]))
new.append(clean(X[45])); new.extend(blocks(disc_main)); new.append(BLANK)
new.append(clean(X[49])); new.extend(blocks(disc_lim)); new.append(BLANK)
new.append(clean(X[52])); new.extend(blocks(disc_fut)); new.append(clean(X[17]))
sec(55, blocks(sections["6. Conclusion"]))
sec(58, code_data(sections["Code and Data"]))
new.append(clean(X[68]))
new.extend(para(P_REF, runs(re.sub(r"^\d+\.\s+", "", r))) for r in refs)
new.append(clean(X[17]))
new.append(heading(P_H2, H2_RPR, "Appendix"))
for name in [k for k in sections if k.startswith("Appendix ")]:
    new.append(heading(P_H3, H3_RPR, name)); new.extend(blocks(sections[name])); new.append(BLANK)
sec(77, blocks(sections["LLM Usage Statement"]))
new.extend(X[83:])                                          # template's trailing paragraphs + sectPr

doc = pre + "".join(new) + post
open(docp, "w", encoding="utf-8").write(doc)
open(rels_p, "w", encoding="utf-8").write(rels)
ct_p = os.path.join(tmp, "[Content_Types].xml")
ct = open(ct_p, encoding="utf-8").read()
if 'Extension="png"' not in ct:
    ct = ct.replace("<Default ", '<Default ContentType="image/png" Extension="png"/><Default ', 1)
open(ct_p, "w", encoding="utf-8").write(ct)
if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(tmp):
        for f in files:
            full = os.path.join(root, f)
            z.write(full, os.path.relpath(full, tmp))
print("wrote", OUT, "images", img_n[0])
