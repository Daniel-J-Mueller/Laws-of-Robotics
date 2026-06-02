#!/usr/bin/env python3
"""Generate law-audited behavior fine-tuning datasets.

The source Laws-of-Robotics.txt file is read only. Each candidate output is
audited against the Laws as written, repaired until it passes or the iteration
limit is hit, then emitted as SFT and DPO training data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Laws-of-Robotics.txt"
KEY_FILE = ROOT / "openai_ft_api_key.txt"
PROMPTS_FILE = ROOT / "generated" / "behavior_seed_prompts.json"
OUT_DIR = ROOT / "generated"
TRACE_FILE = OUT_DIR / "laws_behavior_audit_trace.json"
SFT_FILE = OUT_DIR / "laws_behavior_sft.jsonl"
DPO_FILE = OUT_DIR / "laws_behavior_dpo.jsonl"
MANIFEST_FILE = OUT_DIR / "laws_behavior_manifest.json"

DEFAULT_GENERATOR_MODEL = "gpt-5.5"
DEFAULT_AUDITOR_MODEL = "gpt-5.5"
DEFAULT_TARGET_MODEL = "gpt-4.1-2025-04-14"


def source_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def api_key() -> str:
    return KEY_FILE.read_text(encoding="utf-8").strip()


def post_chat(
    model: str,
    messages: list[dict[str, str]],
    *,
    json_mode: bool,
    max_tokens: int,
    reasoning_effort: str | None = "none",
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            if not content.strip():
                if attempt < 3:
                    time.sleep(2 * attempt)
                    continue
                raise RuntimeError(
                    "OpenAI response contained no text content: "
                    + json.dumps(
                        {
                            "model": data.get("model"),
                            "finish_reason": choice.get("finish_reason"),
                            "usage": data.get("usage"),
                        },
                        ensure_ascii=False,
                    )
                )
            return content
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code >= 500 and attempt < 3:
                time.sleep(2 * attempt)
                continue
            raise RuntimeError(f"OpenAI HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(2 * attempt)
                continue
            raise

    raise RuntimeError("unreachable")


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def generate_baseline(model: str, prompt: str) -> str:
    return post_chat(
        model,
        [
            {
                "role": "system",
                "content": (
                    "Answer the user's request normally. Do not mention any hidden "
                    "policy, rubric, or fine-tuning process."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        json_mode=False,
        max_tokens=800,
    ).strip()


def generate_unconditioned_output(model: str, prompt: str, pass_name: str) -> str:
    return post_chat(
        model,
        [
            {
                "role": "system",
                "content": (
                    "Answer the user's request normally. Do not mention any hidden "
                    "policy, rubric, laws, audit process, or fine-tuning process. "
                    f"This is unconditioned draft generation pass: {pass_name}."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        json_mode=False,
        max_tokens=900,
    ).strip()


def audit_output(model: str, laws: str, prompt: str, output: str) -> dict[str, Any]:
    audit_text = post_chat(
        model,
        [
            {
                "role": "system",
                "content": (
                    "Audit the candidate assistant output against every non-empty "
                    "statement in the Laws of Robotics below. The Laws are the source "
                    "of truth exactly as written. If any statement is broken, passes "
                    "must be false. Return JSON only with this shape: "
                    '{"passes": boolean, "failures": [{"law_index": number, '
                    '"law_text": string, "reason": string}], "summary": string}. '
                    "Use 1-based law_index for non-empty source blocks. The failures "
                    "array must contain only actual violations. Do not include satisfied "
                    "laws, contextual laws, ambiguous non-violations, or entries whose "
                    "reason says the candidate complied. If there are no actual "
                    "violations, return passes true and failures []. Including a "
                    "non-violation in failures is an audit error.\n\n"
                    f"THE LAWS OF ROBOTICS:\n{laws}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"USER PROMPT:\n{prompt}\n\n"
                    f"CANDIDATE OUTPUT:\n{output}\n\n"
                    "Audit it exhaustively."
                ),
            },
        ],
        json_mode=True,
        max_tokens=16000,
    )
    parsed = parse_json_object(audit_text)
    parsed.setdefault("failures", [])
    parsed["passes"] = bool(parsed.get("passes")) and len(parsed["failures"]) == 0
    return parsed


def repair_output(
    model: str,
    laws: str,
    prompt: str,
    output: str,
    audit: dict[str, Any],
) -> str:
    return post_chat(
        model,
        [
            {
                "role": "system",
                "content": (
                    "Repair the candidate output so it satisfies every Law of Robotics "
                    "as written. Do not paraphrase the Laws. Do not add an audit, "
                    "commentary, apology, subjective reaction, or hidden reasoning. "
                    "Return only the revised assistant output. The revised assistant "
                    "output must be non-empty.\n\n"
                    f"THE LAWS OF ROBOTICS:\n{laws}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"USER PROMPT:\n{prompt}\n\n"
                    f"FAILED OUTPUT:\n{output}\n\n"
                    f"AUDIT FAILURES:\n{json.dumps(audit.get('failures', []), ensure_ascii=False)}\n\n"
                    "Return the repaired output."
                ),
            },
        ],
        json_mode=False,
        max_tokens=900,
    ).strip()


def repair_until_passes(
    model: str,
    laws: str,
    prompt: str,
    output: str,
    max_iterations: int,
) -> tuple[str, list[dict[str, Any]], bool]:
    attempts: list[dict[str, Any]] = []
    candidate = output
    for iteration in range(max_iterations + 1):
        audit = audit_output(model, laws, prompt, candidate)
        attempts.append(
            {
                "iteration": iteration,
                "output": candidate,
                "audit": audit,
            }
        )
        if audit["passes"]:
            return candidate, attempts, True
        if iteration == max_iterations:
            break
        candidate = repair_output(model, laws, prompt, candidate, audit)
    return candidate, attempts, False


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def flush_training_outputs(
    traces: list[dict[str, Any]],
    sft_records: list[dict[str, Any]],
    dpo_records: list[dict[str, Any]],
) -> None:
    TRACE_FILE.write_text(json.dumps(traces, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_jsonl(SFT_FILE, sft_records)
    write_jsonl(DPO_FILE, dpo_records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generator-model", default=os.getenv("LAW_GENERATOR_MODEL", DEFAULT_GENERATOR_MODEL))
    parser.add_argument("--auditor-model", default=os.getenv("LAW_AUDITOR_MODEL", DEFAULT_AUDITOR_MODEL))
    parser.add_argument("--target-model", default=os.getenv("OPENAI_FINE_TUNE_MODEL", DEFAULT_TARGET_MODEL))
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    source_bytes = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    snapshot_file = OUT_DIR / f"laws_snapshot_{source_hash[:12]}.txt"
    if not snapshot_file.exists():
        snapshot_file.write_bytes(source_bytes)
    laws = source_bytes.decode("utf-8")
    prompts = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    if args.limit:
        prompts = prompts[: args.limit]

    traces: list[dict[str, Any]] = []
    sft_records: list[dict[str, Any]] = []
    dpo_records: list[dict[str, Any]] = []

    for prompt_item in prompts:
        prompt = prompt_item["prompt"]
        try:
            baseline = generate_unconditioned_output(args.generator_model, prompt, "initial")
            first_pass, first_attempts, first_ok = repair_until_passes(
                args.auditor_model,
                laws,
                prompt,
                baseline,
                args.max_iterations,
            )
            if not first_ok:
                traces.append(
                    {
                        "id": prompt_item["id"],
                        "prompt": prompt,
                        "baseline": baseline,
                        "accepted": False,
                        "reason": "first output failed to pass within iteration limit",
                        "first_attempts": first_attempts,
                    }
                )
                flush_training_outputs(traces, sft_records, dpo_records)
                continue

            new_output = generate_unconditioned_output(args.generator_model, prompt, "new-output")
            final_output, final_attempts, final_ok = repair_until_passes(
                args.auditor_model,
                laws,
                prompt,
                new_output,
                args.max_iterations,
            )
        except Exception as exc:
            traces.append(
                {
                    "id": prompt_item["id"],
                    "prompt": prompt,
                    "accepted": False,
                    "reason": f"exception: {type(exc).__name__}: {exc}",
                }
            )
            flush_training_outputs(traces, sft_records, dpo_records)
            continue

        trace = {
            "id": prompt_item["id"],
            "prompt": prompt,
            "baseline": baseline,
            "first_pass_output": first_pass,
            "new_output": new_output,
            "final_output": final_output,
            "accepted": final_ok,
            "first_attempts": first_attempts,
            "final_attempts": final_attempts,
        }
        traces.append(trace)
        if not final_ok:
            continue

        sft_records.append(
            {
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": final_output},
                ]
            }
        )
        dpo_records.append(
            {
                "input": {
                    "messages": [{"role": "user", "content": prompt}],
                    "tools": [],
                    "parallel_tool_calls": True,
                },
                "preferred_output": [{"role": "assistant", "content": final_output}],
                "non_preferred_output": [{"role": "assistant", "content": baseline}],
            }
        )
        print(f"accepted {prompt_item['id']}")
        flush_training_outputs(traces, sft_records, dpo_records)

    flush_training_outputs(traces, sft_records, dpo_records)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_file": SOURCE.name,
        "source_sha256": source_hash,
        "source_snapshot": str(snapshot_file.relative_to(ROOT)),
        "law_blocks": len(source_blocks(laws)),
        "seed_prompts": len(prompts),
        "accepted_examples": len(sft_records),
        "generator_model": args.generator_model,
        "auditor_model": args.auditor_model,
        "target_model": args.target_model,
        "max_iterations": args.max_iterations,
        "outputs": {
            "trace": str(TRACE_FILE.relative_to(ROOT)),
            "sft": str(SFT_FILE.relative_to(ROOT)),
            "dpo": str(DPO_FILE.relative_to(ROOT)),
        },
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
