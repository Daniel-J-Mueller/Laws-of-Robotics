#!/usr/bin/env python3
"""Build fine-tuning resources from Laws-of-Robotics.txt without modifying it."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Laws-of-Robotics.txt"
OUT_DIR = ROOT / "generated"
TRAINING_FILE = OUT_DIR / "laws_of_robotics_sft.jsonl"
MANIFEST_FILE = OUT_DIR / "laws_of_robotics_sft_manifest.json"

SYSTEM_MESSAGE = (
    "You are being trained on The Laws of Robotics from Laws-of-Robotics.txt. "
    "When asked for a law excerpt, provide the exact source text and do not "
    "paraphrase, reinterpret, soften, summarize, or add commentary."
)


def split_blocks(source_text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in source_text.splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def make_examples(blocks: list[str]) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    total = len(blocks)
    for index, block in enumerate(blocks, start=1):
        examples.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {
                        "role": "user",
                        "content": (
                            f"Provide Laws-of-Robotics statement {index} of {total} exactly."
                        ),
                    },
                    {"role": "assistant", "content": block},
                ]
            }
        )
    return examples


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    source_bytes = SOURCE.read_bytes()
    source_text = source_bytes.decode("utf-8")
    blocks = split_blocks(source_text)
    examples = make_examples(blocks)

    with TRAINING_FILE.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_file": SOURCE.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "training_file": str(TRAINING_FILE.relative_to(ROOT)),
        "training_examples": len(examples),
        "construction": (
            "Each non-empty block from Laws-of-Robotics.txt is copied verbatim into "
            "one assistant target. No source wording is rewritten."
        ),
    }
    MANIFEST_FILE.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
