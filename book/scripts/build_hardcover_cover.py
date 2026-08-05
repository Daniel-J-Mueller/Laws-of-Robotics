#!/usr/bin/env python3
"""Build a white matte Barnes & Noble Press printed-case hardcover wrap."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from build_laws_interior import BookMetadata, load_metadata

TITLE = "The Laws of Robotics of Daniel Joseph Mueller"
EDITION = "First Edition"
AUTHOR = "Daniel J. Mueller"
SCRIPT_DIR = Path(__file__).resolve().parent
BOOK_DIR = SCRIPT_DIR.parent
DEFAULT_COMPONENTS_DIR = BOOK_DIR / "book-components"

# B&N printed-case template dimensions supplied for this 7 x 10 hardcover.
COVER_W = 16.389 * inch
COVER_H = 11.5 * inch
PANEL_W = 7.944 * inch
SPINE_W = 0.5 * inch
FRONT_X = PANEL_W + SPINE_W
READER_W = 7 * inch
READER_H = 10 * inch
INK = HexColor("#25231f")
FONT_DIRS = [
    Path("/usr/share/fonts/truetype/liberation2"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
]
FONT_NAMES = {
    "regular": "LiberationSerif",
    "bold": "LiberationSerif-Bold",
}


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
    except FileNotFoundError:
        FONT_NAMES.update({
            "regular": "Times-Roman",
            "bold": "Times-Bold",
        })


def font(kind: str) -> str:
    return FONT_NAMES[kind]


def cover_metadata(components_dir: Path | None = DEFAULT_COMPONENTS_DIR) -> BookMetadata:
    if components_dir is not None and components_dir.exists():
        return load_metadata(components_dir)
    return BookMetadata()


def centered_rule(canvas: Canvas, center_x: float, y: float, width: float) -> None:
    gap = 0.16 * inch
    diamond = 0.045 * inch
    canvas.setLineWidth(0.6)
    canvas.line(center_x - width / 2, y, center_x - gap, y)
    canvas.line(center_x + gap, y, center_x + width / 2, y)
    path = canvas.beginPath()
    path.moveTo(center_x, y + diamond)
    path.lineTo(center_x + diamond, y)
    path.lineTo(center_x, y - diamond)
    path.lineTo(center_x - diamond, y)
    path.close()
    canvas.drawPath(path, fill=1, stroke=0)


def framed_panel(canvas: Canvas, panel_x: float) -> None:
    inset = 0.67 * inch
    canvas.setLineWidth(0.7)
    canvas.rect(panel_x + inset, inset, PANEL_W - 2 * inset, COVER_H - 2 * inset, stroke=1, fill=0)
    canvas.setLineWidth(0.35)
    inner = inset + 0.09 * inch
    canvas.rect(panel_x + inner, inner, PANEL_W - 2 * inner, COVER_H - 2 * inner, stroke=1, fill=0)


def draw_front_cover(canvas: Canvas, metadata: BookMetadata) -> None:
    center_x = FRONT_X + PANEL_W / 2
    framed_panel(canvas, FRONT_X)
    centered_rule(canvas, center_x, 8.58 * inch, 3.9 * inch)
    canvas.setFont(font("bold"), 27)
    canvas.drawCentredString(center_x, 7.88 * inch, metadata.title_line_one.upper())
    canvas.setFont(font("regular"), 16)
    canvas.drawCentredString(center_x, 7.43 * inch, metadata.title_line_two.upper())
    centered_rule(canvas, center_x, 6.98 * inch, 3.9 * inch)
    canvas.setFont(font("regular"), 12)
    canvas.drawCentredString(center_x, 6.43 * inch, metadata.edition.upper())
    canvas.setFont(font("bold"), 15)
    canvas.drawCentredString(center_x, 3.02 * inch, metadata.author.upper())


def draw_back_cover(canvas: Canvas) -> None:
    center_x = PANEL_W / 2
    framed_panel(canvas, 0)
    centered_rule(canvas, center_x, 5.75 * inch, 2.7 * inch)


def draw_spine(canvas: Canvas, metadata: BookMetadata) -> None:
    center_x = PANEL_W + SPINE_W / 2
    title = f"{metadata.title.upper()}, {metadata.edition.upper()}"
    font_size = 15
    tracking = 1.1
    text_width = pdfmetrics.stringWidth(title, font("bold"), font_size)
    text_width += tracking * (len(title) - 1)
    canvas.saveState()
    canvas.translate(center_x, COVER_H / 2)
    canvas.rotate(90)
    canvas.setFillColor(INK)
    text = canvas.beginText()
    text.setTextOrigin(-text_width / 2, -font_size * 0.34)
    text.setFont(font("bold"), font_size)
    text.setCharSpace(tracking)
    text.textOut(title)
    canvas.drawText(text)
    canvas.restoreState()


def framed_reader_page(canvas: Canvas) -> None:
    inset = 0.43 * inch
    canvas.setLineWidth(0.7)
    canvas.rect(inset, inset, READER_W - 2 * inset, READER_H - 2 * inset, stroke=1, fill=0)
    canvas.setLineWidth(0.35)
    inner = inset + 0.08 * inch
    canvas.rect(inner, inner, READER_W - 2 * inner, READER_H - 2 * inner, stroke=1, fill=0)


def draw_reader_front_cover(canvas: Canvas, metadata: BookMetadata) -> None:
    center_x = READER_W / 2
    framed_reader_page(canvas)
    centered_rule(canvas, center_x, 7.63 * inch, 3.75 * inch)
    canvas.setFont(font("bold"), 25)
    canvas.drawCentredString(center_x, 6.96 * inch, metadata.title_line_one.upper())
    canvas.setFont(font("regular"), 14.5)
    canvas.drawCentredString(center_x, 6.54 * inch, metadata.title_line_two.upper())
    centered_rule(canvas, center_x, 6.12 * inch, 3.75 * inch)
    canvas.setFont(font("regular"), 11)
    canvas.drawCentredString(center_x, 5.63 * inch, metadata.edition.upper())
    canvas.setFont(font("bold"), 14)
    canvas.drawCentredString(center_x, 2.55 * inch, metadata.author.upper())


def draw_reader_back_cover(canvas: Canvas) -> None:
    framed_reader_page(canvas)
    centered_rule(canvas, READER_W / 2, READER_H / 2, 2.7 * inch)


def build_reader_covers(output: Path, components_dir: Path | None = DEFAULT_COMPONENTS_DIR) -> None:
    """Create separate 7 x 10 front and back cover pages for a complete PDF."""
    register_fonts()
    metadata = cover_metadata(components_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(output), pagesize=(READER_W, READER_H), pageCompression=1)
    canvas.setTitle(f"{metadata.title} - Complete PDF Covers")
    canvas.setAuthor(metadata.author)
    canvas.setSubject("Front and back cover pages for a complete reading PDF")
    for draw_page in (draw_reader_front_cover, draw_reader_back_cover):
        canvas.setFillColor(white)
        canvas.rect(0, 0, READER_W, READER_H, stroke=0, fill=1)
        canvas.setStrokeColor(INK)
        canvas.setFillColor(INK)
        if draw_page is draw_reader_front_cover:
            draw_page(canvas, metadata)
        else:
            draw_page(canvas)
        canvas.showPage()
    canvas.save()


def build_cover(output: Path, components_dir: Path | None = DEFAULT_COMPONENTS_DIR) -> None:
    register_fonts()
    metadata = cover_metadata(components_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(output), pagesize=(COVER_W, COVER_H), pageCompression=1)
    canvas.setTitle(f"{metadata.title} - Hardcover Cover")
    canvas.setAuthor(metadata.author)
    canvas.setSubject("Barnes & Noble Press printed-case hardcover wrap")
    canvas.setFillColor(white)
    canvas.rect(0, 0, COVER_W, COVER_H, stroke=0, fill=1)
    canvas.setStrokeColor(INK)
    canvas.setFillColor(INK)
    draw_back_cover(canvas)
    draw_front_cover(canvas, metadata)
    draw_spine(canvas, metadata)
    canvas.showPage()
    canvas.save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=BOOK_DIR / "The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_Hardcover_Cover.pdf")
    parser.add_argument("--components", type=Path, default=DEFAULT_COMPONENTS_DIR)
    args = parser.parse_args()
    build_cover(args.output, args.components)
    print(f"Created: {args.output}")
    print(f"Cover size: {COVER_W / inch:.3f} x {COVER_H / inch:.3f} inches")
    print(f"Spine width: {SPINE_W / inch:.3f} inches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
