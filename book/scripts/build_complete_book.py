#!/usr/bin/env python3
"""Create a single 7 x 10 reading PDF with front cover, interior, and back cover."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import fitz

from build_hardcover_cover import AUTHOR, TITLE, build_reader_covers


def build_complete_book(interior: Path, output: Path) -> int:
    if not interior.exists():
        raise FileNotFoundError(interior)

    with tempfile.TemporaryDirectory() as temporary_directory:
        cover_pages = Path(temporary_directory) / "reader_covers.pdf"
        build_reader_covers(cover_pages)
        covers = fitz.open(cover_pages)
        interior_doc = fitz.open(interior)
        complete = fitz.open()
        complete.insert_pdf(covers, from_page=0, to_page=0)
        complete.insert_pdf(interior_doc)
        complete.insert_pdf(covers, from_page=1, to_page=1)
        complete.set_metadata({
            "title": TITLE,
            "author": AUTHOR,
            "subject": "Complete edition with front cover, interior, and back cover",
        })
        output.parent.mkdir(parents=True, exist_ok=True)
        complete.save(output, garbage=4, deflate=True)
        pages = len(complete)
        complete.close()
        covers.close()
        interior_doc.close()
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interior", type=Path,
                        default=Path("The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf"))
    parser.add_argument("--output", type=Path,
                        default=Path("The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_Complete.pdf"))
    args = parser.parse_args()
    pages = build_complete_book(args.interior, args.output)
    print(f"Created: {args.output}")
    print(f"Pages: {pages}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())