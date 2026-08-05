#!/usr/bin/env python3
"""Build a 7 x 10 inch Barnes & Noble Press interior PDF.

Task initiated by Daniel Joseph Mueller.

Usage:
  python build_laws_interior.py --source ../Laws-of-Robotics.txt --output interior.pdf

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
from dataclasses import dataclass
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
from reportlab.platypus.doctemplate import ActionFlowable

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
SCRIPT_DIR = Path(__file__).resolve().parent
BOOK_DIR = SCRIPT_DIR.parent
REPO_DIR = BOOK_DIR.parent
DEFAULT_SOURCE = REPO_DIR / "Laws-of-Robotics.txt"
DEPRECATED_BOOK_SOURCE = BOOK_DIR / "Laws-of-Robotics.txt"
DEFAULT_COMPONENTS_DIR = BOOK_DIR / "book-components"

FONT_DIRS = [
    Path("/usr/share/fonts/truetype/liberation2"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
]
FONT_NAMES = {
    "regular": "LiberationSerif",
    "bold": "LiberationSerif-Bold",
    "italic": "LiberationSerif-Italic",
    "bold_italic": "LiberationSerif-BoldItalic",
}


@dataclass
class BookMetadata:
    title: str = TITLE
    title_line_one: str = TITLE_LINE_ONE
    title_line_two: str = TITLE_LINE_TWO
    edition: str = EDITION
    author: str = AUTHOR
    copyright_year: str = COPYRIGHT_YEAR


@dataclass
class Chapter:
    title: str | None
    laws: list[str]


def locate_font(filename: str) -> Path:
    for directory in FONT_DIRS:
        candidate = directory / filename
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Liberation Serif font not found: {filename}")


def register_fonts() -> None:
    try:
        pdfmetrics.registerFont(TTFont("LiberationSerif", str(locate_font("LiberationSerif-Regular.ttf"))))
        pdfmetrics.registerFont(TTFont("LiberationSerif-Bold", str(locate_font("LiberationSerif-Bold.ttf"))))
        pdfmetrics.registerFont(TTFont("LiberationSerif-Italic", str(locate_font("LiberationSerif-Italic.ttf"))))
        pdfmetrics.registerFont(TTFont("LiberationSerif-BoldItalic", str(locate_font("LiberationSerif-BoldItalic.ttf"))))
    except FileNotFoundError:
        # ReportLab includes Times on every install. Keep the style names dynamic so
        # local Windows builds can still render even when Liberation Serif is absent.
        FONT_NAMES.update({
            "regular": "Times-Roman",
            "bold": "Times-Bold",
            "italic": "Times-Italic",
            "bold_italic": "Times-BoldItalic",
        })
        return
    pdfmetrics.registerFontFamily(
        "LiberationSerif",
        normal="LiberationSerif",
        bold="LiberationSerif-Bold",
        italic="LiberationSerif-Italic",
        boldItalic="LiberationSerif-BoldItalic",
    )


def load_source(path: Path) -> str:
    path = canonical_source(path)
    if path.exists():
        return path.read_text(encoding="utf-8-sig")
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading source from {SOURCE_URL}", file=sys.stderr)
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "laws-interior-builder/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    path.write_bytes(data)
    return data.decode("utf-8-sig")


def canonical_source(path: Path) -> Path:
    if path.expanduser().resolve() == DEPRECATED_BOOK_SOURCE.resolve():
        return DEFAULT_SOURCE
    return path


def remove_author_note_lines(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # Lines beginning with !!! are author notes, not book text.
    return "\n".join(
        line for line in normalized.split("\n")
        if not line.lstrip().startswith("!!!")
    )


def parse_laws(text: str) -> list[str]:
    text = remove_author_note_lines(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    # The repository uses blank lines as the stable boundary between laws.
    laws = [re.sub(r"[ \t]+", " ", block.replace("\n", " ")).strip()
            for block in re.split(r"\n\s*\n+", text)]
    return [law for law in laws if law]


def esc(text: str) -> str:
    return html.escape(text, quote=False).replace("\u00a0", " ")


def font(kind: str) -> str:
    return FONT_NAMES[kind]


ATTR_RE = re.compile(r"""([A-Za-z_][\w-]*)\s*=\s*(['"])(.*?)\2""")
BLOCK_TAG_RE = re.compile(r"^<([A-Za-z][\w-]*)([^>]*)>(.*)</\1>$", re.DOTALL)
SELF_TAG_RE = re.compile(r"^<([A-Za-z][\w-]*)([^>]*)/>$", re.DOTALL)
INLINE_TAG_RE = re.compile(
    r"(<\/?(?:italic|bold|term)>|<(?:linebreak|br)\s*/>)",
    re.IGNORECASE,
)
METADATA_TOKEN_RE = re.compile(r"\{\{([A-Za-z_][\w-]*)\}\}")
INLINE_TAGS = {
    "<italic>": "<i>",
    "</italic>": "</i>",
    "<bold>": "<b>",
    "</bold>": "</b>",
    "<term>": "<b>",
    "</term>": "</b>",
    "<linebreak/>": "<br/>",
    "<br/>": "<br/>",
}
COMPONENT_STYLE_TAGS = {
    "half-title": "half_title",
    "title": "title",
    "edition": "edition",
    "author": "author",
    "copyright": "copyright",
    "dedication-heading": "dedication_heading",
    "dedication": "dedication",
    "section-heading": "preface_heading",
    "preface": "preface",
    "paragraph": "front_left",
    "center": "front_center",
}


def parse_attrs(raw_attrs: str) -> dict[str, str]:
    return {key: value for key, _, value in ATTR_RE.findall(raw_attrs)}


def strip_component_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def split_component_blocks(text: str) -> list[str]:
    text = strip_component_comments(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    return [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]


def first_component_block(text: str) -> str | None:
    blocks = split_component_blocks(text)
    return blocks[0].strip().lower() if blocks else None


def normalize_paragraph_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text.replace("\n", " ")).strip()


def component_markup(text: str) -> str:
    text = normalize_paragraph_text(text)
    pieces = []
    for piece in INLINE_TAG_RE.split(text):
        if not piece:
            continue
        tag = re.sub(r"\s+", "", piece.lower())
        if tag in INLINE_TAGS:
            pieces.append(INLINE_TAGS[tag])
        else:
            pieces.append(esc(piece))
    return "".join(pieces)


def expand_includes(text: str, components_dir: Path) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        match = SELF_TAG_RE.match(line.strip())
        if match and match.group(1).lower() == "include":
            attrs = parse_attrs(match.group(2))
            if "path" not in attrs:
                raise ValueError("<include/> requires a path attribute.")
            include_path = canonical_source(components_dir / attrs["path"]).resolve()
            if not include_path.exists() and include_path.name == "Laws-of-Robotics.txt":
                load_source(include_path)
            if not include_path.exists():
                raise FileNotFoundError(include_path)
            lines.append(include_path.read_text(encoding="utf-8-sig"))
        else:
            lines.append(line)
    return "\n".join(lines)


def load_metadata(components_dir: Path) -> BookMetadata:
    metadata = BookMetadata()
    path = components_dir / "metadata.txt"
    if not path.exists():
        return metadata
    values = metadata.__dict__.copy()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValueError(f"Metadata line must use 'key: value': {line}")
        key, value = stripped.split(":", 1)
        key = key.strip().replace("-", "_")
        if key not in values:
            raise ValueError(f"Unknown metadata key: {key}")
        values[key] = value.strip()
    return BookMetadata(**values)


def apply_metadata_tokens(text: str, metadata: BookMetadata) -> str:
    values = metadata.__dict__

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in values:
            raise ValueError(f"Unknown metadata token: {{{{{key}}}}}")
        return values[key]

    return METADATA_TOKEN_RE.sub(replace, text)


def title_from_filename(path: Path) -> str:
    title = re.sub(r"^\d+[-_\s]*", "", path.stem)
    title = title.replace("-", " ").replace("_", " ").strip()
    return title.title() if title else path.stem


def load_chapter(path: Path, components_dir: Path) -> Chapter | None:
    text = path.read_text(encoding="utf-8-sig")
    if first_component_block(text) == "<skip/>":
        return None
    text = expand_includes(text, components_dir)
    body_lines = []
    title = None
    for line in text.splitlines():
        stripped = line.strip()
        match = SELF_TAG_RE.match(stripped)
        if match and match.group(1).lower() == "chapter":
            attrs = parse_attrs(match.group(2))
            title = attrs.get("title", "").strip() or None
            continue
        body_lines.append(line)
    laws = parse_laws("\n".join(body_lines))
    if not laws:
        return None
    return Chapter(title=title or title_from_filename(path), laws=laws)


def load_chapters(components_dir: Path) -> list[Chapter]:
    chapters_dir = components_dir / "chapters"
    if not chapters_dir.exists():
        return []
    chapters = []
    for path in sorted(chapters_dir.glob("*.txt")):
        chapter = load_chapter(path, components_dir)
        if chapter is not None:
            chapters.append(chapter)
    return chapters


def render_component_file(path: Path, style_map: dict[str, ParagraphStyle],
                          metadata: BookMetadata,
                          default_style: str = "front_left"):
    if not path.exists():
        return []
    raw_text = path.read_text(encoding="utf-8-sig")
    if first_component_block(raw_text) == "<skip/>":
        return []
    raw_text = apply_metadata_tokens(expand_includes(raw_text, path.parent.parent), metadata)
    flowables = []
    for block in split_component_blocks(raw_text):
        lowered = block.lower()
        if lowered == "<skip/>":
            return []
        self_match = SELF_TAG_RE.match(block)
        if self_match:
            tag = self_match.group(1).lower()
            attrs = parse_attrs(self_match.group(2))
            if tag == "spacer":
                flowables.append(Spacer(1, float(attrs.get("height", "0")) * inch))
            elif tag == "pagebreak":
                flowables.append(PageBreak())
            elif tag == "section":
                title = attrs.get("title", "")
                if title:
                    flowables.append(Paragraph(component_markup(title), style_map["preface_heading"]))
            else:
                raise ValueError(f"Unsupported self-closing tag in {path}: <{tag}/>")
            continue

        block_match = BLOCK_TAG_RE.match(block)
        if block_match:
            tag = block_match.group(1).lower()
            attrs = parse_attrs(block_match.group(2))
            content = block_match.group(3)
            if tag == "definition":
                term = attrs.get("term", "").strip()
                term_markup = f"<b>{esc(term)}</b> " if term else ""
                flowables.append(Paragraph(term_markup + component_markup(content), style_map["definition"]))
                continue
            if tag == "italic":
                content = f"<italic>{content}</italic>"
                style_name = default_style
            elif tag == "bold":
                content = f"<bold>{content}</bold>"
                style_name = default_style
            elif tag in COMPONENT_STYLE_TAGS:
                style_name = COMPONENT_STYLE_TAGS[tag]
            else:
                raise ValueError(f"Unsupported block tag in {path}: <{tag}>")
            flowables.append(Paragraph(component_markup(content), style_map[style_name]))
        else:
            flowables.append(Paragraph(component_markup(block), style_map[default_style]))
    return flowables


class StartOnOddPage(ActionFlowable):
    def __init__(self, template_name: str):
        super().__init__(())
        self.template_name = template_name

    def apply(self, doc):
        if doc.page % 2 == 1:
            doc.handle_pageBreak()
        doc.handle_nextPageTemplate(self.template_name)
        doc.handle_pageBreak()


class BookDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, metadata: BookMetadata, **kwargs):
        super().__init__(filename, **kwargs)
        self.metadata = metadata
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
    canvas.setTitle(f"{doc.metadata.title} - {doc.metadata.edition}")
    canvas.setAuthor(doc.metadata.author)
    canvas.setSubject("Barnes & Noble Press interior")
    canvas.restoreState()


def draw_body_page(canvas, doc: BookDocTemplate):
    doc.in_body = True
    doc.body_page_number += 1
    n = doc.body_page_number
    canvas.saveState()
    canvas.setFont(font("regular"), 8)
    y = 0.39 * inch
    canvas.drawCentredString(PAGE_W / 2, y, str(n))
    canvas.restoreState()


def styles():
    return {
        "half_title": ParagraphStyle("half_title", fontName=font("bold"), fontSize=20,
                                     leading=24, alignment=TA_CENTER, spaceAfter=0),
        "title": ParagraphStyle("title", fontName=font("bold"), fontSize=24,
                                leading=28, alignment=TA_CENTER),
        "edition": ParagraphStyle("edition", fontName=font("regular"), fontSize=13,
                                  leading=16, alignment=TA_CENTER),
        "author": ParagraphStyle("author", fontName=font("regular"), fontSize=14,
                                 leading=18, alignment=TA_CENTER),
        "copyright": ParagraphStyle("copyright", fontName=font("regular"), fontSize=9.5,
                                    leading=13, alignment=TA_LEFT),
        "dedication_heading": ParagraphStyle("dedication_heading", fontName=font("bold"),
                                             fontSize=14, leading=18, alignment=TA_CENTER),
        "dedication": ParagraphStyle("dedication", fontName=font("italic"), fontSize=12,
                                     leading=18, alignment=TA_CENTER),
        "section": ParagraphStyle("section", fontName=font("bold"), fontSize=10.5,
                      leading=13, alignment=TA_CENTER),
        "law": ParagraphStyle("law", fontName=font("regular"), fontSize=9.8,
                      leading=13.1, alignment=TA_JUSTIFY, firstLineIndent=0,
                      spaceAfter=6.5, allowWidows=0, allowOrphans=0,
                              splitLongWords=False),
        "chapter_heading": ParagraphStyle("chapter_heading", fontName=font("bold"), fontSize=15,
                                          leading=19, alignment=TA_CENTER, spaceAfter=0),
        "preface_heading": ParagraphStyle("preface_heading", fontName=font("bold"), fontSize=15,
                                          leading=19, alignment=TA_CENTER, spaceAfter=18),
        "preface": ParagraphStyle("preface", fontName=font("regular"), fontSize=10.5,
                                  leading=15, alignment=TA_JUSTIFY, spaceAfter=7,
                                  splitLongWords=False),
        "definition": ParagraphStyle("definition", fontName=font("regular"), fontSize=10.5,
                                     leading=15, alignment=TA_LEFT, leftIndent=0.18*inch,
                                     firstLineIndent=-0.18*inch, spaceAfter=7,
                                     splitLongWords=False),
        "front_left": ParagraphStyle("front_left", fontName=font("regular"), fontSize=10.5,
                                     leading=14, alignment=TA_LEFT, spaceAfter=7),
        "front_center": ParagraphStyle("front_center", fontName=font("regular"), fontSize=10.5,
                                       leading=14, alignment=TA_CENTER, spaceAfter=7),
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
        law_markup = f'<font name="{font("bold")}">{i}.</font>&nbsp;&nbsp;{esc(law)}'
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


def add_chapter_laws(story: list, chapter: Chapter, style_map: dict[str, ParagraphStyle],
                     first_law_number: int, total_laws: int) -> int:
    if chapter.title:
        story.extend([
            Spacer(1, 0.48 * inch),
            Paragraph(component_markup(chapter.title), style_map["chapter_heading"]),
            Spacer(1, 0.25 * inch),
        ])

    law_number = first_law_number
    for law in chapter.laws:
        law_markup = (
            f'<font name="{font("bold")}">{law_number}.</font>'
            f'&nbsp;&nbsp;{component_markup(law)}'
        )
        law_paragraph = Paragraph(law_markup, style_map["law"])
        if (law_number - 1) % 100 == 0:
            last = min(law_number + 99, total_laws)
            section = [
                Paragraph(f"Laws {law_number}-{last}", style_map["section"]),
                Spacer(1, 0.14 * inch),
                law_paragraph,
            ]
            if law_number != 1:
                section.insert(0, Spacer(1, 0.16 * inch))
            story.append(KeepTogether(section))
        else:
            story.append(law_paragraph)
        law_number += 1
    return law_number


def build_component_story(components_dir: Path, source: Path) -> tuple[list, int, BookMetadata]:
    metadata = load_metadata(components_dir)
    style_map = styles()
    front_matter = [
        components_dir / "front-matter" / "half-title.txt",
        components_dir / "front-matter" / "title-page.txt",
        components_dir / "front-matter" / "copyright.txt",
        components_dir / "front-matter" / "dedication.txt",
    ]

    story = []
    for path in front_matter:
        story.extend(render_component_file(path, style_map, metadata))

    front_sections = [
        components_dir / "front-matter" / "definitions.txt",
        components_dir / "front-matter" / "preface.txt",
    ]
    for path in front_sections:
        section = render_component_file(path, style_map, metadata, default_style="preface")
        if section:
            story.append(StartOnOddPage("Front"))
            story.extend(section)

    chapters = load_chapters(components_dir)
    if not chapters:
        chapters = [Chapter(title=None, laws=parse_laws(load_source(source)))]
    total_laws = sum(len(chapter.laws) for chapter in chapters)
    if total_laws == 0:
        raise RuntimeError("No laws were found in the component chapters.")

    story.append(StartOnOddPage("BodyOdd"))
    next_law_number = 1
    for index, chapter in enumerate(chapters):
        if index > 0:
            story.append(StartOnOddPage("BodyOdd"))
        next_law_number = add_chapter_laws(
            story, chapter, style_map, next_law_number, total_laws
        )
    return story, total_laws, metadata


def build_pdf(source: Path, output: Path, components: Path | None = DEFAULT_COMPONENTS_DIR) -> tuple[int, int]:
    source = canonical_source(source)
    register_fonts()
    metadata = BookMetadata()
    if components is not None and components.exists():
        story, law_count, metadata = build_component_story(components, source)
    else:
        text = load_source(source)
        laws = parse_laws(text)
        if not laws:
            raise RuntimeError("No laws were found in the source file.")
        story = build_story(laws)
        law_count = len(laws)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = BookDocTemplate(
        str(output), metadata=metadata, pagesize=(PAGE_W, PAGE_H),
        leftMargin=0, rightMargin=0, topMargin=0, bottomMargin=0,
        title=f"{metadata.title} - {metadata.edition}", author=metadata.author,
        subject="Barnes & Noble Press print interior",
        pageCompression=1,
    )
    doc.addPageTemplates(make_body_templates(doc))
    doc.build(story)
    return law_count, doc.page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--components", type=Path, default=DEFAULT_COMPONENTS_DIR,
                        help="Directory of editable book component .txt files.")
    parser.add_argument("--output", type=Path,
                        default=BOOK_DIR / "The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf")
    args = parser.parse_args()
    laws, pages = build_pdf(args.source, args.output, args.components)
    print(f"Created: {args.output}")
    print(f"Laws: {laws}")
    print(f"Pages: {pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
