#!/usr/bin/env python3
"""Download the current Laws-of-Robotics.txt from GitHub."""
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/Daniel-J-Mueller/Laws-of-Robotics/main/Laws-of-Robotics.txt"
SCRIPT_DIR = Path(__file__).resolve().parent
BOOK_DIR = SCRIPT_DIR.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=BOOK_DIR / "Laws-of-Robotics.txt")
    args = parser.parse_args()
    req = urllib.request.Request(URL, headers={"User-Agent": "laws-of-robotics-book-builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    args.output.write_bytes(data)
    print(f"Downloaded {len(data):,} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
