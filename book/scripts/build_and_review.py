#!/usr/bin/env python3
"""Fetch the source, build the interior PDF, then render it for review."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BOOK_DIR = SCRIPT_DIR.parent
REPO_DIR = BOOK_DIR.parent
SOURCE = REPO_DIR / "Laws-of-Robotics.txt"
COMPONENTS = BOOK_DIR / "book-components"
PDF = BOOK_DIR / "The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf"
RENDER = BOOK_DIR / "review" / "review_render"


def main() -> int:
    if not COMPONENTS.exists():
        subprocess.run([sys.executable, str(SCRIPT_DIR / "fetch_source.py"), "--output", str(SOURCE)], check=True)

    build_cmd = [
        sys.executable, str(SCRIPT_DIR / "build_laws_interior.py"),
        "--source", str(SOURCE), "--output", str(PDF),
    ]
    if COMPONENTS.exists():
        build_cmd.extend(["--components", str(COMPONENTS)])
    subprocess.run(build_cmd, check=True)

    subprocess.run([
        sys.executable, str(SCRIPT_DIR / "review_pdf.py"), str(PDF), "--out-dir", str(RENDER)
    ], check=True)
    print(f"Finished: {PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
