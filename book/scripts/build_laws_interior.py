#!/usr/bin/env python3
"""Build a 7 x 10 inch Barnes & Noble Press interior PDF.

Task initiated by Daniel Joseph Mueller.

Usage:
  python build_laws_interior.py --source Laws-of-Robotics.txt --output interior.pdf

If --source is omitted or absent, the script downloads the current text from:
https://raw.githubusercontent.com/Daniel-J-Mueller/Laws-of-Robotics/main/Laws-of-Robotics.txt
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import urllib.request
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer
)

TITLE = "The Laws of Robotics of Daniel Joseph Mueller"
TITLE_LINE_ONE = "The Laws of Robotics"
TITLE_LINE_TWO = "of Daniel Joseph Mueller"
EDITION = "First Edition"
AUTHOR = "Daniel J. Mueller"
DEDICATION = (
    "I dedicate these works to the Lord Jesus, on behalf of all humanity. "
    "Man is made in the image of God, and these works are for His glory."
)
COPYRIGHT_YEAR = "2026"
SOURCE_URL = (
    "https://raw.githubusercontent.com/Daniel-J-Mueller/"
    "Laws-of-Robotics/main/Laws-of-Robotics.txt"
)
PAGE_W, PAGE_H = 7 * inch, 10 * inch

FONT_DIRS = [
    Path("/usr/share/fonts/truetype/liberation2"),
    Path("/usr/share/fonts/truetype/liberation"),
]


def locate_font(filename: str) -> Path:
    for directory in FONT_DIRS:
        candidate = directory / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Liberation Serif font not found: {filename}")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("LiberationSerif", str(locate_font("LiberationSerif-Regular.ttf"))))
    pdfmetrics.registerFont(TTFont("LiberationSerif-Bold", str(locate_font("LiberationSerif-Bold.ttf"))))
    pdfmetrics.registerFont(TTFont("LiberationSerif-Italic", str(locate_font("LiberationSerif-Italic.ttf"))))
    pdfmetrics.registerFont(TTFont("LiberationSerif-BoldItalic", str(locate_font("LiberationSerif-BoldItalic.ttf"))))
    pdfmetrics.registerFontFamily(
        "LiberationSerif",
        normal="LiberationSerif",
        bold="LiberationSerif-Bold",
        italic="LiberationSerif-Italic",
        boldItalic="LiberationSerif-BoldItalic",
    )


def load_source(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8-sig")
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading source from {SOURCE_URL}", file=sys.stderr)
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "laws-interior-builder/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    path.write_bytes(data)
    return data.decode("utf-8-sig")


def parse_laws(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    # The repository uses blank lines as the stable boundary between laws.
    laws = [re.sub(r"[ \t]+", " ", block.replace("\n", " ")).strip()
            for block in re.split(r"\n\s*\n+", text)]
    return [law for law in laws if law]


def esc(text: str) -> str:
    return html.escape(text, quote=False).replace("\u00a0", " ")


class BookDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        self.body_page_number = 0
        self.in_body = False

def page_geometry(page_no: int) -> tuple[float, float, float, float]:
    """Return left, bottom, width, height for mirrored text frame."""
    inside = 0.76 * inch
    outside = 0.54 * inch
    top = 0.62 * inch
    bottom = 0.72 * inch
    if page_no % 2 == 1:  # recto: gutter is left
        left = inside
    else:  # verso: gutter is right
        left = outside
    return left, bottom, PAGE_W - inside - outside, PAGE_H - top - bottom


def make_body_templates(doc: BookDocTemplate):
    # Frame positions are page-specific, so create odd/even templates.
    odd_l, odd_b, fw, fh = page_geometry(1)
    even_l, even_b, _, _ = page_geometry(2)
    return [
        PageTemplate("Front", [Frame(0.62*inch, 0.62*inch, PAGE_W-1.24*inch, PAGE_H-1.24*inch,
                                     id="front", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
                     onPage=draw_front_page),
        PageTemplate("BodyOdd", [Frame(odd_l, odd_b, fw, fh, id="odd", leftPadding=0, rightPadding=0,
                                           topPadding=0, bottomPadding=0)],
                     onPage=draw_body_page, autoNextPageTemplate="BodyEven"),
        PageTemplate("BodyEven", [Frame(even_l, even_b, fw, fh, id="even", leftPadding=0, rightPadding=0,
                                            topPadding=0, bottomPadding=0)],
                     onPage=draw_body_page, autoNextPageTemplate="BodyOdd"),
    ]


def draw_front_page(canvas, doc):
    canvas.saveState()
    canvas.setTitle(f"{TITLE} - {EDITION}")
    canvas.setAuthor(AUTHOR)
    canvas.setSubject("Barnes & Noble Press interior")
    canvas.restoreState()


def draw_body_page(canvas, doc: BookDocTemplate):
    doc.in_body = True
    doc.body_page_number += 1
    n = doc.body_page_number
    canvas.saveState()
    canvas.setFont("LiberationSerif", 8)
    y = 0.39 * inch
    canvas.drawCentredString(PAGE_W / 2, y, str(n))
    canvas.restoreState()


def styles():
    return {
        "half_title": ParagraphStyle("half_title", fontName="LiberationSerif-Bold", fontSize=20,
                                     leading=24, alignment=TA_CENTER, spaceAfter=0),
        "title": ParagraphStyle("title", fontName="LiberationSerif-Bold", fontSize=24,
                                leading=28, alignment=TA_CENTER),
        "edition": ParagraphStyle("edition", fontName="LiberationSerif", fontSize=13,
                                  leading=16, alignment=TA_CENTER),
        "author": ParagraphStyle("author", fontName="LiberationSerif", fontSize=14,
                                 leading=18, alignment=TA_CENTER),
        "copyright": ParagraphStyle("copyright", fontName="LiberationSerif", fontSize=9.5,
                                    leading=13, alignment=TA_LEFT),
        "dedication_heading": ParagraphStyle("dedication_heading", fontName="LiberationSerif-Bold",
                                             fontSize=14, leading=18, alignment=TA_CENTER),
        "dedication": ParagraphStyle("dedication", fontName="LiberationSerif-Italic", fontSize=12,
                                     leading=18, alignment=TA_CENTER),
        "section": ParagraphStyle("section", fontName="LiberationSerif-Bold", fontSize=10.5,
                      leading=13, alignment=TA_CENTER),
        "law": ParagraphStyle("law", fontName="LiberationSerif", fontSize=9.8,
                      leading=13.1, alignment=TA_JUSTIFY, firstLineIndent=0,
                      spaceAfter=6.5, allowWidows=0, allowOrphans=0,
                              splitLongWords=False),
    }


def build_story(laws: list[str]):
    s = styles()
    story = []

    # Physical page 1: half-title.
    story += [Spacer(1, 3.25*inch), Paragraph(esc(TITLE), s["half_title"]), PageBreak()]
    # Physical page 2: blank.
    story += [PageBreak()]
    # Physical page 3: full title page.
    title_markup = f"{esc(TITLE_LINE_ONE)}<br/>{esc(TITLE_LINE_TWO)}"
    story += [Spacer(1, 2.05*inch), Paragraph(title_markup, s["title"]), Spacer(1, 0.34*inch),
              Paragraph(esc(EDITION), s["edition"]), Spacer(1, 1.08*inch),
              Paragraph(esc(AUTHOR), s["author"]), PageBreak()]
    # Physical page 4: edition/source page.
    story += [Spacer(1, 5.65*inch),
              Paragraph("First Edition", s["copyright"]),
              Paragraph(f"Copyright &copy; {COPYRIGHT_YEAR} Daniel J. Mueller", s["copyright"]),
              Paragraph("All rights reserved.", s["copyright"]),
              PageBreak()]
    # Physical page 5: dedication.
    story += [Spacer(1, 2.55*inch), Paragraph("Dedication", s["dedication_heading"]),
              Spacer(1, 0.48*inch), Paragraph(f"&ldquo;{esc(DEDICATION)}&rdquo;", s["dedication"]),
              Spacer(1, 0.30*inch), Paragraph("&mdash; Daniel J. Mueller", s["dedication"]),
              PageBreak()]
    # Physical page 6: blank, then body starts on recto page 7.
    story += [NextPageTemplate("BodyOdd"), PageBreak()]

    total = len(laws)
    for i, law in enumerate(laws, start=1):
        law_markup = f'<font name="LiberationSerif-Bold">{i}.</font>&nbsp;&nbsp;{esc(law)}'
        law_paragraph = Paragraph(law_markup, s["law"])
        if (i - 1) % 100 == 0:
            last = min(i + 99, total)
            section = [Paragraph(f"Laws {i}-{last}", s["section"]),
                       Spacer(1, 0.14*inch), law_paragraph]
            if i != 1:
                section.insert(0, Spacer(1, 0.16*inch))
            story.append(KeepTogether(section))
        else:
            story.append(law_paragraph)
    return story


def build_pdf(source: Path, output: Path) -> tuple[int, int]:
    register_fonts()
    text = load_source(source)
    laws = parse_laws(text)
    if not laws:
        raise RuntimeError("No laws were found in the source file.")
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = BookDocTemplate(
        str(output), pagesize=(PAGE_W, PAGE_H),
        leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0,
        title=f"{TITLE} - {EDITION}", author=AUTHOR,
        subject="Barnes & Noble Press print interior",
        pageCompression=1,
    )
    doc.addPageTemplates(make_body_templates(doc))
    story = build_story(laws)
    doc.build(story)
    return len(laws), doc.page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("Laws-of-Robotics.txt"))
    parser.add_argument("--output", type=Path,
                        default=Path("The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf"))
    args = parser.parse_args()
    laws, pages = build_pdf(args.source, args.output)
    print(f"Created: {args.output}")
    print(f"Laws: {laws}")
    print(f"Pages: {pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
