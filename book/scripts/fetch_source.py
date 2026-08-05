#!/usr/bin/env python3
"""Download the current Laws-of-Robotics.txt from GitHub."""
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/Daniel-J-Mueller/Laws-of-Robotics/main/Laws-of-Robotics.txt"
SCRIPT_DIR = Path(__file__).resolve().parent
BOOK_DIR = SCRIPT_DIR.parent
REPO_DIR = BOOK_DIR.parent
DEFAULT_OUTPUT = REPO_DIR / "Laws-of-Robotics.txt"
DEPRECATED_BOOK_SOURCE = BOOK_DIR / "Laws-of-Robotics.txt"


def canonical_output(path: Path) -> Path:
    if path.expanduser().resolve() == DEPRECATED_BOOK_SOURCE.resolve():
        return DEFAULT_OUTPUT
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = canonical_output(args.output)
    req = urllib.request.Request(URL, headers={"User-Agent": "laws-of-robotics-book-builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    output.write_bytes(data)
    print(f"Downloaded {len(data):,} bytes to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
