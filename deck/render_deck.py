#!/usr/bin/env python3
"""Render deck/*.md (slides separated by '---') to a 16:9 HTML deck, then to PDF with headless Chrome.
Usage: python deck/render_deck.py"""
import html
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "northstar_oor_freight_leakage_deck.md")
OUT_HTML = os.path.join(HERE, "northstar_oor_freight_leakage_deck.html")
OUT_PDF = os.path.join(HERE, "northstar_oor_freight_leakage_deck.pdf")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\w)", r"<i>\1</i>", t)
    return t


def block(lines: list[str]) -> str:
    out, i = [], 0
    while i < len(lines):
        l = lines[i]
        if l.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            th = "" if not any(head) else "<tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
            out.append(f"<table>{th}" + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</table>")
            continue
        if re.match(r"^\s*(- |\d+\. )", l):
            ordered = bool(re.match(r"^\s*\d+\. ", l))
            items = []
            while i < len(lines) and (re.match(r"^\s*(- |\d+\. )", lines[i]) or lines[i].startswith("  ")):
                if re.match(r"^\s*(- |\d+\. )", lines[i]):
                    items.append(re.sub(r"^\s*(- |\d+\. )", "", lines[i]))
                else:
                    items[-1] += "\x00" + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            def li(x):
                parts = x.split("\x00")
                first, rest = inline(parts[0]), parts[1:]
                for r in rest:
                    if r.startswith("> "):
                        first += f'<span class="q">{inline(r[2:])}</span>'
                    else:
                        first += "<br>" + inline(r)
                return first
            out.append(f"<{tag}>" + "".join(f"<li>{li(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if l.startswith("# "):
            out.append(f"<h1>{inline(l[2:])}</h1>")
        elif l.startswith("## "):
            out.append(f"<h2>{inline(l[3:])}</h2>")
        elif l.startswith("### "):
            out.append(f"<h3>{inline(l[4:])}</h3>")
        elif l.strip():
            out.append(f"<p>{inline(l)}</p>")
        i += 1
    return "\n".join(out)


def main():
    md = open(SRC).read()
    slides = [s.strip("\n") for s in re.split(r"\n---\n", md)]
    sections = []
    for n, s in enumerate(slides):
        lines = s.splitlines()
        body = block(lines)
        cls = "slide title" if n == 0 else "slide"
        sections.append(f'<section class="{cls}">{body}<div class="foot">Northstar Network Optimization · synthetic data · {n + 1}/{len(slides)}</div></section>')
    css = """
@page { size: 13.333in 7.5in; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; }
.slide { width: 13.333in; height: 7.5in; padding: 0.55in 0.75in 0.5in; position: relative; page-break-after: always; overflow: hidden;
         background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); border-top: 10px solid #1d4ed8; }
.slide.title { background: linear-gradient(135deg, #0b1220 0%, #1e3a8a 100%); color: #f8fafc; border-top: 0; padding-top: 1.6in; }
.slide.title h1 { font-size: 46px; line-height: 1.1; margin: 0 0 18px; max-width: 10.5in; }
.slide.title h3 { font-size: 22px; font-weight: 500; color: #bfdbfe; margin: 0 0 40px; }
.slide.title p { color: #cbd5e1; font-size: 15px; max-width: 10in; }
h2 { font-size: 34px; margin: 0 0 18px; color: #0b1f4d; letter-spacing: -0.3px; }
p, li { font-size: 20px; line-height: 1.42; }
ul, ol { margin: 6px 0 10px 4px; padding-left: 22px; } li { margin: 5px 0; }
b { color: #0b1f4d; } .title b { color: #fff; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 0.88em; background: #e2e8f0; padding: 1px 5px; border-radius: 4px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 14px; font-size: 18px; }
th { text-align: left; background: #1d4ed8; color: #fff; padding: 8px 10px; font-weight: 600; }
td { padding: 7px 10px; border-bottom: 1px solid #cbd5e1; vertical-align: top; }
tr:nth-child(even) td { background: #eef2ff; }
td:first-child b { font-size: 1.15em; color: #1d4ed8; white-space: nowrap; }
.q { display: block; margin: 6px 0 2px; padding: 8px 12px; border-left: 4px solid #1d4ed8; background: #eff6ff; font-style: italic; font-size: 17px; }
.foot { position: absolute; bottom: 0.22in; right: 0.75in; font-size: 11px; color: #64748b; }
.title .foot { color: #93c5fd; }
.title code { background: rgba(255,255,255,.15); color: #e0e7ff; }
"""
    with open(OUT_HTML, "w") as f:
        f.write(f"<!doctype html><html><head><meta charset='utf-8'><title>Northstar OOR freight leakage</title><style>{css}</style></head>"
                f"<body>{''.join(sections)}</body></html>")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={OUT_PDF}",
                    f"file://{OUT_HTML}"], check=True, capture_output=True)
    print(f"wrote {OUT_PDF} ({os.path.getsize(OUT_PDF) // 1024} KB, {len(slides)} slides)")


if __name__ == "__main__":
    main()
