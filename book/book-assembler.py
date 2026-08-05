#!/usr/bin/env python3
"""Assemble the book interior and exterior cover PDFs into OUTPUT."""
from __future__ import annotations

import sys
from pathlib import Path

BOOK_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = BOOK_DIR / "scripts"
OUTPUT_DIR = BOOK_DIR / "OUTPUT"
SOURCE = BOOK_DIR / "Laws-of-Robotics.txt"
COMPONENTS = BOOK_DIR / "book-components"

INTERIOR_PDF = OUTPUT_DIR / "The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf"
EXTERIOR_COVER_PDF = OUTPUT_DIR / "The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_Hardcover_Cover.pdf"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_hardcover_cover import COVER_H, COVER_W, SPINE_W, build_cover
from build_laws_interior import build_pdf
from reportlab.lib.units import inch


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    laws, pages = build_pdf(SOURCE, INTERIOR_PDF, COMPONENTS)
    build_cover(EXTERIOR_COVER_PDF, COMPONENTS)

    print(f"Interior: {INTERIOR_PDF}")
    print(f"Laws: {laws}")
    print(f"Interior pages: {pages}")
    print(f"Exterior cover: {EXTERIOR_COVER_PDF}")
    print(f"Cover size: {COVER_W / inch:.3f} x {COVER_H / inch:.3f} inches")
    print(f"Spine width: {SPINE_W / inch:.3f} inches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
