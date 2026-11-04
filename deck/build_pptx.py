#!/usr/bin/env python3
"""Build an editable .pptx (native text boxes + tables + speaker notes) from a slides .md and a notes .md,
using only the standard library. Import the result into Google Slides via File > Import slides, or upload to Drive.

Usage: python deck/build_pptx.py roleplay_4_slides roleplay_presenter_notes
"""
import math
import os
import re
import sys
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
EMU = 914400  # per inch
W, H = 13.333, 7.5
BLUE, NAVY, INK, MUTED, BAND = "1D4ED8", "0B1F4D", "0F172A", "64748B", "EEF2FF"
FONT = "Arial"

# ---------------------------------------------------------------- markdown -> slide model


def parse_slides(md: str):
    slides = []
    for chunk in re.split(r"\n---\n", md):
        title, blocks, lines = "", [], chunk.strip("\n").splitlines()
        i = 0
        while i < len(lines):
            l = lines[i]
            if l.startswith("## "):
                title = l[3:].strip()
            elif l.startswith("|"):
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                        rows.append(cells)
                    i += 1
                header = any(rows[0])
                blocks.append(("table", rows if header else rows[1:], header))
                continue
            elif l.startswith("- "):
                items = []
                while i < len(lines) and lines[i].startswith("- "):
                    items.append(lines[i][2:])
                    i += 1
                blocks.append(("bullets", items))
                continue
            elif l.strip():
                blocks.append(("para", l))
            i += 1
        slides.append({"title": title, "blocks": blocks})
    return slides


def parse_notes(md: str, n: int):
    parts = re.split(r"\n## Slide \d+[^\n]*\n", "\n" + md)
    notes = []
    for p in parts[1:n + 1]:
        p = p.split("\n---")[0].strip()
        p = re.sub(r"\*\*([^*]+)\*\*", r"\1", p)
        p = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", p)
        p = re.sub(r"^- ", "• ", p, flags=re.M)
        notes.append(p)
    return notes

# ---------------------------------------------------------------- DrawingML helpers


def emu(inches: float) -> int:
    return int(round(inches * EMU))


def runs(text: str, size: int, color: str = INK, bold_all: bool = False) -> str:
    """Inline **bold**, *italic* and `code` -> a:r runs."""
    out = []
    for tok in re.split(r"(\*\*[^*]+\*\*|`[^`]+`|(?<![*\w])\*[^*]+\*(?!\w))", text):
        if not tok:
            continue
        b, it, mono, col = bold_all, False, False, color
        if tok.startswith("**"):
            tok, b, col = tok[2:-2], True, NAVY if color == INK else color
        elif tok.startswith("`"):
            tok, mono = tok[1:-1], True
        elif tok.startswith("*"):
            tok, it = tok[1:-1], True
        font = "Courier New" if mono else FONT
        out.append(f'<a:r><a:rPr lang="en-US" sz="{size * 100}" b="{int(b)}" i="{int(it)}" dirty="0">'
                   f'<a:solidFill><a:srgbClr val="{col}"/></a:solidFill><a:latin typeface="{font}"/>'
                   f'<a:cs typeface="{font}"/></a:rPr><a:t>{escape(tok)}</a:t></a:r>')
    return "".join(out)


def para(text, size, color=INK, bullet=False, bold_all=False, space_after=6, align="l"):
    ppr = (f'<a:pPr marL="285750" indent="-285750" algn="{align}"><a:spcAft><a:spcPts val="{space_after * 100}"/></a:spcAft>'
           f'<a:buFont typeface="Arial"/><a:buChar char="&#8226;"/></a:pPr>' if bullet else
           f'<a:pPr algn="{align}"><a:spcAft><a:spcPts val="{space_after * 100}"/></a:spcAft><a:buNone/></a:pPr>')
    return f"<a:p>{ppr}{runs(text, size, color, bold_all)}</a:p>"


_id = [10]


def nid():
    _id[0] += 1
    return _id[0]


def textbox(x, y, w, h, paras_xml, name="Text", anchor="t"):
    i = nid()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="{name} {i}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0" anchor="{anchor}"><a:normAutofit/></a:bodyPr>'
            f'<a:lstStyle/>{paras_xml}</p:txBody></p:sp>')


def rect(x, y, w, h, color):
    i = nid()
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="Bar {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:ln><a:noFill/></a:ln></p:spPr></p:sp>')


def col_widths(rows, total):
    ncol = len(rows[0])
    if ncol == 2:
        return [total * 0.20, total * 0.80]
    if ncol == 3:
        lens = [max(len(r[c]) for r in rows) for c in range(3)]
        if lens[2] > 2 * max(lens[0], lens[1]):
            return [total * 0.13, total * 0.27, total * 0.60]
        return [total * 0.40, total * 0.25, total * 0.35]
    if ncol == 4:
        return [total * 0.36, total * 0.22, total * 0.24, total * 0.18]
    return [total / ncol] * ncol


def est_lines(text, width_in, size):
    plain = re.sub(r"[*`]", "", text)
    chars_per_line = max(8, width_in / (size * 0.0072))
    return max(1, math.ceil(len(plain) / chars_per_line))


def table(x, y, w, rows, header, size):
    widths = col_widths(rows, w)
    heights = []
    for ri, r in enumerate(rows):
        lines = max(est_lines(c, widths[ci] - 0.2, size) for ci, c in enumerate(r))
        heights.append(0.16 + lines * size * 0.0185)
    grid = "".join(f'<a:gridCol w="{emu(cw)}"/>' for cw in widths)
    trs = []
    for ri, r in enumerate(rows):
        is_head = header and ri == 0
        fill = BLUE if is_head else (BAND if ri % 2 == (0 if header else 1) else "FFFFFF")
        tcs = []
        for ci, c in enumerate(r):
            color = "FFFFFF" if is_head else (BLUE if ci == 0 and not header else INK)
            bold = is_head or (ci == 0 and not header)
            tcs.append(f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{para(c, size, color, bold_all=bold, space_after=0)}</a:txBody>'
                       f'<a:tcPr marL="91440" marR="91440" marT="54864" marB="54864" anchor="ctr">'
                       f'<a:lnL w="0"><a:noFill/></a:lnL><a:lnR w="0"><a:noFill/></a:lnR><a:lnT w="0"><a:noFill/></a:lnT>'
                       f'<a:lnB w="9525"><a:solidFill><a:srgbClr val="CBD5E1"/></a:solidFill></a:lnB>'
                       f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>')
        trs.append(f'<a:tr h="{emu(heights[ri])}">{"".join(tcs)}</a:tr>')
    i = nid()
    xml = (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{i}" name="Table {i}"/><p:cNvGraphicFramePr>'
           f'<a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>'
           f'<p:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(sum(heights))}"/></p:xfrm>'
           f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
           f'<a:tbl><a:tblPr firstRow="{int(header)}" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>{"".join(trs)}</a:tbl>'
           f'</a:graphicData></a:graphic></p:graphicFrame>')
    return xml, sum(heights)


def slide_xml(s, n, total):
    _id[0] = 10
    left, width = 0.7, W - 1.4
    shapes = [rect(0, 0, W, 0.12, BLUE),
              textbox(left, 0.42, width, 0.85, para(s["title"], 30, NAVY, bold_all=True, space_after=0), "Title", "b")]
    y = 1.45
    big = sum(len(b[1]) for b in s["blocks"] if b[0] == "table") > 6
    for b in s["blocks"]:
        if b[0] == "table":
            xml, h = table(left, y, width, b[1], b[2], 13 if big else 15)
            shapes.append(xml)
            y += h + 0.25
        else:
            items = b[1] if b[0] == "bullets" else [b[1]]
            size = 15 if b[0] == "bullets" else 15
            body = "".join(para(t, size, bullet=(b[0] == "bullets"), space_after=7) for t in items)
            est = sum(est_lines(t, width - 0.35, size) * size * 0.0175 + 0.1 for t in items)
            h = max(0.4, min(est + 0.1, H - 0.55 - y))
            shapes.append(textbox(left, y, width, h, body, "Body"))
            y += h + 0.12
    shapes.append(textbox(W - 5.2, H - 0.42, 4.5, 0.3,
                          para(f"Northstar Network Optimization · synthetic data · {n}/{total}", 10, MUTED, space_after=0, align="r"),
                          "Footer"))
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            f'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            f'<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
            f'<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f'{"".join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


def notes_xml(text):
    paras = "".join(f'<a:p><a:r><a:rPr lang="en-US" sz="1200" dirty="0"/><a:t>{escape(l)}</a:t></a:r></a:p>' if l.strip()
                    else '<a:p><a:endParaRPr lang="en-US" sz="1200"/></a:p>' for l in text.splitlines())
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree>'
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr>'
            '<p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
            '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
            f'<p:txBody><a:bodyPr/><a:lstStyle/>{paras}</p:txBody></p:sp></p:spTree></p:cSld>'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>')

# ---------------------------------------------------------------- package boilerplate

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CLRMAP = ('<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
          'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>')
EMPTY_TREE = ('<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
              '<p:grpSpPr/></p:spTree></p:cSld>')


def theme(name):
    colors = dict(dk1="000000", lt1="FFFFFF", dk2=NAVY, lt2="E2E8F0", accent1=BLUE, accent2="0EA5E9", accent3="22C55E",
                  accent4="F59E0B", accent5="EF4444", accent6="8B5CF6", hlink=BLUE, folHlink="7C3AED")
    clr = "".join(f'<a:{k}><a:srgbClr val="{v}"/></a:{k}>' for k, v in colors.items())
    fill = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    lns = "".join(f'<a:ln w="{w}">{fill}</a:ln>' for w in (9525, 25400, 38100))
    effects = "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
    return (f'{XML}<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="{name}"><a:themeElements>'
            f'<a:clrScheme name="Northstar">{clr}</a:clrScheme>'
            f'<a:fontScheme name="Northstar"><a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
            f'<a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
            f'<a:fmtScheme name="Northstar"><a:fillStyleLst>{fill * 3}</a:fillStyleLst>'
            f'<a:lnStyleLst>{lns}</a:lnStyleLst><a:effectStyleLst>{effects}</a:effectStyleLst>'
            f'<a:bgFillStyleLst>{fill * 3}</a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>')


def build(slides_name, notes_name):
    slides = parse_slides(open(os.path.join(HERE, f"{slides_name}.md")).read())
    notes = parse_notes(open(os.path.join(HERE, f"{notes_name}.md")).read(), len(slides))
    n = len(slides)
    out = os.path.join(HERE, f"{slides_name}.pptx")
    files = {}
    ct = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
          '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
          '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
          '<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"/>',
          '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
          '<Override PartName="/ppt/theme/theme2.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
          '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>']
    for i in range(1, n + 1):
        ct.append(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
        ct.append(f'<Override PartName="/ppt/notesSlides/notesSlide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>')
    files["[Content_Types].xml"] = f'{XML}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">{"".join(ct)}</Types>'
    files["_rels/.rels"] = (f'{XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                            f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="ppt/presentation.xml"/>'
                            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                            f'<Relationship Id="rId3" Type="{REL}/extended-properties" Target="docProps/app.xml"/></Relationships>')
    files["docProps/core.xml"] = (f'{XML}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                                  'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Northstar out-of-route freight - role play</dc:title>'
                                  '</cp:coreProperties>')
    files["docProps/app.xml"] = (f'{XML}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
                                 f'<Application>build_pptx.py</Application><Slides>{n}</Slides></Properties>')
    sld_ids = "".join(f'<p:sldId id="{256 + i}" r:id="rId{10 + i}"/>' for i in range(1, n + 1))
    files["ppt/presentation.xml"] = (f'{XML}<p:presentation {NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
                                     f'<p:notesMasterIdLst><p:notesMasterId r:id="rId3"/></p:notesMasterIdLst>'
                                     f'<p:sldIdLst>{sld_ids}</p:sldIdLst><p:sldSz cx="{emu(W)}" cy="{emu(H)}"/>'
                                     f'<p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
    prels = [f'<Relationship Id="rId1" Type="{REL}/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
             f'<Relationship Id="rId2" Type="{REL}/theme" Target="theme/theme1.xml"/>',
             f'<Relationship Id="rId3" Type="{REL}/notesMaster" Target="notesMasters/notesMaster1.xml"/>']
    prels += [f'<Relationship Id="rId{10 + i}" Type="{REL}/slide" Target="slides/slide{i}.xml"/>' for i in range(1, n + 1)]
    files["ppt/_rels/presentation.xml.rels"] = f'{XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(prels)}</Relationships>'
    files["ppt/theme/theme1.xml"] = theme("Northstar")
    files["ppt/theme/theme2.xml"] = theme("Northstar Notes")
    files["ppt/slideMasters/slideMaster1.xml"] = (f'{XML}<p:sldMaster {NS}>{EMPTY_TREE}{CLRMAP}'
                                                  '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>')
    files["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = (f'{XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                             f'<Relationship Id="rId1" Type="{REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
                                                             f'<Relationship Id="rId2" Type="{REL}/theme" Target="../theme/theme1.xml"/></Relationships>')
    layout_tree = EMPTY_TREE.replace("<p:cSld>", '<p:cSld name="Blank">')
    files["ppt/slideLayouts/slideLayout1.xml"] = (f'{XML}<p:sldLayout {NS} type="blank" preserve="1">'
                                                  f'{layout_tree}'
                                                  '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
    files["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = (f'{XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                             f'<Relationship Id="rId1" Type="{REL}/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>')
    files["ppt/notesMasters/notesMaster1.xml"] = f'{XML}<p:notesMaster {NS}>{EMPTY_TREE}{CLRMAP}</p:notesMaster>'
    files["ppt/notesMasters/_rels/notesMaster1.xml.rels"] = (f'{XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                             f'<Relationship Id="rId1" Type="{REL}/theme" Target="../theme/theme2.xml"/></Relationships>')
    for i, s in enumerate(slides, 1):
        files[f"ppt/slides/slide{i}.xml"] = slide_xml(s, i, n)
        files[f"ppt/slides/_rels/slide{i}.xml.rels"] = (f'{XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                        f'<Relationship Id="rId1" Type="{REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
                                                        f'<Relationship Id="rId2" Type="{REL}/notesSlide" Target="../notesSlides/notesSlide{i}.xml"/></Relationships>')
        files[f"ppt/notesSlides/notesSlide{i}.xml"] = notes_xml(notes[i - 1] if i - 1 < len(notes) else "")
        files[f"ppt/notesSlides/_rels/notesSlide{i}.xml.rels"] = (f'{XML}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                                  f'<Relationship Id="rId1" Type="{REL}/notesMaster" Target="../notesMasters/notesMaster1.xml"/>'
                                                                  f'<Relationship Id="rId2" Type="{REL}/slide" Target="../slides/slide{i}.xml"/></Relationships>')
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", files.pop("[Content_Types].xml"))
        for k, v in files.items():
            z.writestr(k, v)
    print(f"wrote {out} ({n} slides, notes on {sum(1 for x in notes if x)} slides)")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "roleplay_4_slides",
          sys.argv[2] if len(sys.argv) > 2 else "roleplay_presenter_notes")
