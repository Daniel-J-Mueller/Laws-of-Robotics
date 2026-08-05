#!/usr/bin/env python3
"""Fetch the source, build the interior PDF, then render it for review."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Laws-of-Robotics.txt"
PDF = ROOT / "The_Laws_of_Robotics_of_Daniel_Joseph_Mueller_First_Edition_Interior.pdf"
RENDER = ROOT / "review_render"


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "fetch_source.py"), "--output", str(SOURCE)], check=True)
    subprocess.run([
        sys.executable, str(ROOT / "build_laws_interior.py"),
        "--source", str(SOURCE), "--output", str(PDF)
    ], check=True)
    subprocess.run([
        sys.executable, str(ROOT / "review_pdf.py"), str(PDF), "--out-dir", str(RENDER)
    ], check=True)
    print(f"Finished: {PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
