#!/usr/bin/env python3
"""Preflight and render the generated interior PDF for visual review."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path("/home/oai/skills/pdfs/scripts")
SCRIPT_DIR = Path(__file__).resolve().parent
BOOK_DIR = SCRIPT_DIR.parent


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out-dir", type=Path, default=BOOK_DIR / "review" / "review_render")
    parser.add_argument("--dpi", type=int, default=160)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise FileNotFoundError(args.pdf)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    inspect_script = SKILL_ROOT / "pdf_inspect.py"
    preflight_script = SKILL_ROOT / "pdf_preflight.py"
    render_script = SKILL_ROOT / "render_pdf.py"

    if SKILL_ROOT.exists():
        run([sys.executable, str(inspect_script), str(args.pdf)])
        run([sys.executable, str(preflight_script), str(args.pdf)])
        run([sys.executable, str(render_script), str(args.pdf), "--out_dir", str(args.out_dir), "--dpi", str(args.dpi)])
    else:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise RuntimeError("Install PyMuPDF to render locally: pip install pymupdf") from exc
        doc = fitz.open(args.pdf)
        scale = args.dpi / 72
        matrix = fitz.Matrix(scale, scale)
        for index, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(args.out_dir / f"page-{index + 1:04d}.png")
        print(f"Rendered {len(doc)} pages into {args.out_dir}")

    print("Review the first pages, every 100-law divider, and the final pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
