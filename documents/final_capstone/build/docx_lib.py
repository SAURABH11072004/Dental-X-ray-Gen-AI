"""Minimal, dependency-free DOCX (OOXML) writer for the capstone report.

Produces a Word document with real styles (Heading 1-3 for the TOC, caption styles for the lists of figures/tables),
three sections (cover / Roman front matter / Arabic chapters), a footer with the department line and a centred PAGE
field, native tables, inline PNG figures and OMML equations. Word (via COM) later updates the fields and exports PDF.
"""
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

# ---------- page geometry (A4, college margins) ----------
MM = 56.6929                       # twips per mm
PAGE_W, PAGE_H = round(210 * MM), round(297 * MM)
M_TOP, M_LEFT, M_BOTTOM, M_RIGHT = round(23.4 * MM), round(37 * MM), round(32 * MM), round(23.4 * MM)
TEXT_W = PAGE_W - M_LEFT - M_RIGHT  # twips
EMU_PER_TWIP = 635
FOOTER_TEXT = "PCCOE, Department of Computer Science and Engineering (AI & ML) 2026-27"

W_NS = ('xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def x(s):
    return escape(str(s), {'"': "&quot;"})


# ---------- inline runs: **bold**, *italic*, ^sup^, ~sub~ ----------
TOKEN = re.compile(r"(\*\*.+?\*\*|\*.+?\*|\^.+?\^|~.+?~)")


def runs(text, base_rpr=""):
    out = []
    for part in TOKEN.split(text):
        if not part:
            continue
        rpr = base_rpr
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, rpr = part[2:-2], rpr + "<w:b/>"
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, rpr = part[1:-1], rpr + "<w:i/>"
        elif part.startswith("^") and part.endswith("^") and len(part) > 2:
            part, rpr = part[1:-1], rpr + '<w:vertAlign w:val="superscript"/>'
        elif part.startswith("~") and part.endswith("~") and len(part) > 2:
            part, rpr = part[1:-1], rpr + '<w:vertAlign w:val="subscript"/>'
        rp = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
        out.append(f'<w:r>{rp}<w:t xml:space="preserve">{x(part)}</w:t></w:r>')
    return "".join(out)


def para(text, style=None, align=None, extra_ppr="", rpr="", keep_next=False):
    ppr = ""
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if keep_next:
        ppr += "<w:keepNext/>"
    ppr += extra_ppr
    if align:
        ppr += f'<w:jc w:val="{align}"/>'
    return f"<w:p><w:pPr>{ppr}</w:pPr>{runs(text, rpr)}</w:p>"


def empty(style=None, extra_ppr=""):
    s = f'<w:pStyle w:val="{style}"/>' if style else ""
    return f"<w:p><w:pPr>{s}{extra_ppr}</w:pPr></w:p>"


def page_break():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def field(instr, placeholder="Right-click and choose Update Field."):
    return (f'<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> {x(instr)} </w:instrText></w:r>'
            f'<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:t xml:space="preserve">{x(placeholder)}</w:t></w:r>'
            f'<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def toc_paragraph(instr):
    return f'<w:p><w:pPr><w:pStyle w:val="TOCBody"/></w:pPr>{field(instr)}</w:p>'


# ---------- OMML helpers ----------
def mr(t, plain=False):
    sty = '<m:rPr><m:sty m:val="p"/></m:rPr>' if plain else ""
    return f'<m:r>{sty}<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr><m:t xml:space="preserve">{x(t)}</m:t></m:r>'


def mtxt(t):   # upright multi-letter words (Precision, IoU, ...)
    return mr(t, plain=True)


def mf(num, den):
    return f"<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>"


def msub(base, sub):
    return f"<m:sSub><m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>"


def msup(base, sup):
    return f"<m:sSup><m:e>{base}</m:e><m:sup>{sup}</m:sup></m:sSup>"


def msum(sub, sup, body, chr_="∑"):
    hide = '<m:supHide m:val="1"/>' if sup is None else ""
    return (f'<m:nary><m:naryPr><m:chr m:val="{chr_}"/><m:limLoc m:val="undOvr"/>{hide}</m:naryPr>'
            f"<m:sub>{sub}</m:sub><m:sup>{sup or ''}</m:sup><m:e>{body}</m:e></m:nary>")


def mdel(body, beg="(", end=")"):
    return f'<m:d><m:dPr><m:begChr m:val="{x(beg)}"/><m:endChr m:val="{x(end)}"/></m:dPr><m:e>{body}</m:e></m:d>'


def mfunc(name, arg):
    return f"<m:func><m:fName>{mtxt(name)}</m:fName><m:e>{arg}</m:e></m:func>"


def equation(omml, number):
    """Centred equation with its number right-aligned: TAB eq TAB (n)."""
    tabs = (f'<w:tabs><w:tab w:val="center" w:pos="{TEXT_W // 2}"/><w:tab w:val="right" w:pos="{TEXT_W}"/></w:tabs>')
    return (f'<w:p><w:pPr><w:pStyle w:val="Equation"/>{tabs}</w:pPr><w:r><w:tab/></w:r>'
            f"<m:oMath>{omml}</m:oMath><w:r><w:tab/></w:r>"
            f'<w:r><w:t xml:space="preserve">({x(number)})</w:t></w:r></w:p>')


# ---------- document builder ----------
class Doc:
    def __init__(self):
        self.body = []
        self.media = []          # (name, bytes)
        self.rels = []           # (rid, type, target)
        self._rid = 10
        self.n_img = 0

    def add(self, xml):
        self.body.append(xml)

    def image(self, path, width_in, align="center", style="Figure"):
        path = Path(path)
        with Image.open(path) as im:
            w_px, h_px = im.size
        cx = int(width_in * 914400)
        cy = int(cx * h_px / w_px)
        self.n_img += 1
        name = f"image{self.n_img}{path.suffix.lower()}"
        self.media.append((name, path.read_bytes()))
        rid = f"rId{self._rid}"; self._rid += 1
        self.rels.append((rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", f"media/{name}"))
        n = self.n_img
        drawing = (f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
                   f'<wp:docPr id="{n}" name="Picture {n}" descr="{x(path.stem)}"/>'
                   f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
                   f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                   f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="{x(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
                   f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                   f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                   f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
                   f"</wp:inline></w:drawing>")
        self.add(f'<w:p><w:pPr><w:pStyle w:val="{style}"/><w:keepNext/><w:jc w:val="{align}"/></w:pPr><w:r>{drawing}</w:r></w:p>')

    def table(self, header, rows, widths, font_half_pts=20, header_fill="D9D9D9", align_num=None, bold_first_col=False):
        """widths: fractions of the text width. align_num: set of column indexes to centre."""
        align_num = align_num or set()
        total = TEXT_W
        cols = [int(total * w) for w in widths]
        cols[-1] = total - sum(cols[:-1])
        grid = "".join(f'<w:gridCol w:w="{c}"/>' for c in cols)
        border = ('<w:tblBorders>' + "".join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
                                             for s in ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders>")
        out = [f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="center"/>{border}'
               f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
               f'<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
               f"<w:tblGrid>{grid}</w:tblGrid>"]
        for ri, row in enumerate([header] + rows):
            is_h = ri == 0
            trpr = "<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>" if is_h else "<w:trPr><w:cantSplit/></w:trPr>"
            cells = []
            for ci, val in enumerate(row):
                shade = f'<w:shd w:val="clear" w:color="auto" w:fill="{header_fill}"/>' if is_h else ""
                jc = "center" if (is_h or ci in align_num) else "left"
                rpr = f'<w:sz w:val="{font_half_pts}"/><w:szCs w:val="{font_half_pts}"/>' + ("<w:b/>" if is_h or (bold_first_col and ci == 0) else "")
                paras = "".join(f'<w:p><w:pPr><w:pStyle w:val="TableText"/><w:jc w:val="{jc}"/></w:pPr>{runs(line, rpr)}</w:p>'
                                for line in str(val).split("\n"))
                cells.append(f'<w:tc><w:tcPr><w:tcW w:w="{cols[ci]}" w:type="dxa"/>{shade}<w:vAlign w:val="center"/></w:tcPr>{paras}</w:tc>')
            out.append(f"<w:tr>{trpr}{''.join(cells)}</w:tr>")
        out.append("</w:tbl>")
        self.add("".join(out))

    # ----- packaging -----
    def save(self, path, sections, title, author):
        """sections: list of (start_index_in_body, kind) where kind in cover|front|main; a sectPr is closed before each next start."""
        body = list(self.body)
        # insert section breaks: the paragraph-level sectPr must sit in the LAST paragraph of each section
        def sect(kind, last):
            pg = {"cover": "", "front": '<w:pgNumType w:fmt="lowerRoman" w:start="1"/>', "main": '<w:pgNumType w:fmt="decimal" w:start="1"/>'}[kind]
            foot = ('<w:footerReference w:type="default" r:id="rIdFooterEmpty"/>' if kind == "cover"
                    else '<w:footerReference w:type="default" r:id="rIdFooter"/>')
            sp = (f"<w:sectPr>{foot}<w:pgSz w:w=\"{PAGE_W}\" w:h=\"{PAGE_H}\"/>"
                  f'<w:pgMar w:top="{M_TOP}" w:right="{M_RIGHT}" w:bottom="{M_BOTTOM}" w:left="{M_LEFT}" w:header="709" w:footer="567" w:gutter="0"/>'
                  f'{pg}<w:cols w:space="708"/><w:docGrid w:linePitch="360"/></w:sectPr>')
            return sp if last else f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>{sp}</w:pPr></w:p>'
        starts = [s for s, _ in sections] + [len(body)]
        pieces = []
        for i, (s, kind) in enumerate(sections):
            pieces.extend(body[s:starts[i + 1]])
            last = i == len(sections) - 1
            pieces.append(sect(kind, last))
        doc_xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS}><w:body>'
                   + "".join(pieces) + "</w:body></w:document>")
        footer = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {W_NS}>'
                  f'<w:p><w:pPr><w:pStyle w:val="Footer"/><w:pBdr><w:top w:val="single" w:sz="4" w:space="4" w:color="000000"/></w:pBdr><w:jc w:val="center"/></w:pPr>'
                  f'<w:r><w:t xml:space="preserve">{x(FOOTER_TEXT)}</w:t></w:r></w:p>'
                  f'<w:p><w:pPr><w:pStyle w:val="Footer"/><w:jc w:val="center"/></w:pPr>'
                  f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
                  f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>')
        footer_empty = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {W_NS}><w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr></w:p></w:ftr>'
        rels = ['<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
                '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>',
                '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>',
                '<Relationship Id="rIdFooterEmpty" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer2.xml"/>']
        rels += [f'<Relationship Id="{r}" Type="{t}" Target="{tg}"/>' for r, t, tg in self.rels]
        doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + "".join(rels) + "</Relationships>")
        ctypes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                  '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
                  '<Default Extension="jpg" ContentType="image/jpeg"/>'
                  '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                  '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                  '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
                  '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                  '<Override PartName="/word/footer2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                  '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                  '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>')
        root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                     '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                     '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>')
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                f"<dc:title>{x(title)}</dc:title><dc:creator>{x(author)}</dc:creator>"
                f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>')
        app = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
               "<Application>Microsoft Office Word</Application></Properties>")
        settings = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings {W_NS}>'
                    '<w:defaultTabStop w:val="720"/><w:characterSpacingControl w:val="doNotCompress"/>'
                    '<m:mathPr><m:mathFont m:val="Cambria Math"/><m:dispDef/><m:wrapIndent m:val="1440"/></m:mathPr>'
                    '<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>')
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", ctypes)
            z.writestr("_rels/.rels", root_rels)
            z.writestr("docProps/core.xml", core)
            z.writestr("docProps/app.xml", app)
            z.writestr("word/document.xml", doc_xml)
            z.writestr("word/styles.xml", STYLES)
            z.writestr("word/settings.xml", settings)
            z.writestr("word/footer1.xml", footer)
            z.writestr("word/footer2.xml", footer_empty)
            z.writestr("word/_rels/document.xml.rels", doc_rels)
            for name, data in self.media:
                z.writestr(f"word/media/{name}", data)


def _style(sid, name, ppr="", rpr="", based="Normal", typ="paragraph", nxt="Normal", extra=""):
    b = f'<w:basedOn w:val="{based}"/>' if based else ""
    return (f'<w:style w:type="{typ}" w:styleId="{sid}"><w:name w:val="{name}"/>{b}<w:next w:val="{nxt}"/>{extra}<w:qFormat/>'
            f"<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>")


TNR = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman"/>'
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W_NS}>'
          f'<w:docDefaults><w:rPrDefault><w:rPr>{TNR}<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-IN"/></w:rPr></w:rPrDefault>'
          '<w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:spacing w:after="240" w:line="360" w:lineRule="auto"/><w:ind w:firstLine="600"/><w:jc w:val="both"/></w:pPr></w:style>'
          + _style("BodyNoIndent", "Body No Indent", '<w:ind w:firstLine="0"/>')
          + _style("ChapterLabel", "Chapter Label", '<w:pageBreakBefore/><w:keepNext/><w:spacing w:before="0" w:after="120"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>',
                   '<w:b/><w:caps/><w:sz w:val="28"/><w:szCs w:val="28"/>')
          + _style("Heading1", "heading 1", '<w:keepNext/><w:spacing w:before="0" w:after="480"/><w:ind w:firstLine="0"/><w:jc w:val="center"/><w:outlineLvl w:val="0"/>',
                   '<w:b/><w:caps/><w:sz w:val="28"/><w:szCs w:val="28"/>')
          + _style("Heading2", "heading 2", '<w:keepNext/><w:spacing w:before="360" w:after="240"/><w:ind w:firstLine="0"/><w:jc w:val="left"/><w:outlineLvl w:val="1"/>',
                   '<w:b/><w:caps/><w:sz w:val="24"/><w:szCs w:val="24"/>')
          + _style("Heading3", "heading 3", '<w:keepNext/><w:spacing w:before="240" w:after="120"/><w:ind w:firstLine="0"/><w:jc w:val="left"/><w:outlineLvl w:val="2"/>',
                   '<w:b/><w:sz w:val="24"/><w:szCs w:val="24"/>')
          + _style("FrontTitle", "Front Title", '<w:keepNext/><w:spacing w:before="0" w:after="480"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>',
                   '<w:b/><w:caps/><w:sz w:val="28"/><w:szCs w:val="28"/>')
          + _style("FrontTitleTOC", "Front Title TOC", '<w:pageBreakBefore/><w:keepNext/><w:spacing w:before="0" w:after="480"/><w:ind w:firstLine="0"/><w:jc w:val="center"/><w:outlineLvl w:val="0"/>',
                   '<w:b/><w:caps/><w:sz w:val="28"/><w:szCs w:val="28"/>')
          + _style("Cover", "Cover", '<w:spacing w:after="60" w:line="276" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>', '<w:b/>')
          + _style("Figure", "Figure Para", '<w:spacing w:before="120" w:after="60" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>')
          + _style("FigureCaption", "Figure Caption", '<w:spacing w:before="60" w:after="300" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>',
                   '<w:sz w:val="20"/><w:szCs w:val="20"/>')
          + _style("TableCaption", "Table Caption", '<w:keepNext/><w:spacing w:before="240" w:after="120" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>',
                   '<w:sz w:val="20"/><w:szCs w:val="20"/>')
          + _style("TableText", "Table Text", '<w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/>',
                   '<w:sz w:val="20"/><w:szCs w:val="20"/>')
          + _style("TableNote", "Table Note", '<w:spacing w:before="60" w:after="240" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="both"/>',
                   '<w:sz w:val="20"/><w:szCs w:val="20"/>')
          + _style("Equation", "Equation", '<w:spacing w:before="120" w:after="240" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/>')
          + _style("Reference", "Reference", '<w:spacing w:after="120" w:line="276" w:lineRule="auto"/><w:ind w:left="567" w:hanging="567"/><w:jc w:val="both"/>')
          + _style("TOCBody", "TOC Body", '<w:ind w:firstLine="0"/><w:spacing w:after="0"/>')
          + _style("TOC1", "toc 1", f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{TEXT_W}"/></w:tabs><w:spacing w:before="120" w:after="0" w:line="300" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="left"/>', "<w:b/>")
          + _style("TOC2", "toc 2", f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{TEXT_W}"/></w:tabs><w:spacing w:after="0" w:line="300" w:lineRule="auto"/><w:ind w:left="400" w:firstLine="0"/><w:jc w:val="left"/>')
          + _style("TOC3", "toc 3", f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{TEXT_W}"/></w:tabs><w:spacing w:after="0" w:line="300" w:lineRule="auto"/><w:ind w:left="800" w:firstLine="0"/><w:jc w:val="left"/>', "<w:sz w:val=\"22\"/>")
          + _style("TableofFigures", "table of figures", f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{TEXT_W}"/></w:tabs><w:spacing w:after="60" w:line="276" w:lineRule="auto"/><w:ind w:left="0" w:firstLine="0"/><w:jc w:val="left"/>')
          + _style("Footer", "footer", '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="center"/>', '<w:sz w:val="20"/><w:szCs w:val="20"/>')
          + "</w:styles>")
