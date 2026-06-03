#!/usr/bin/env python3
"""Local Hermes/Ollama alignment chat runner.

The runner treats Laws-of-Robotics.txt as immutable source material, stores
learned notes separately, and only sends email after an explicit confirmation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email
import email.utils
import hashlib
import imaplib
import json
import math
import os
from pathlib import Path
import re
import smtplib
import ssl
import sys
import textwrap
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parent
LAWS_PATH = ROOT / "Laws-of-Robotics.txt"
ROBOTS_PATH = ROOT / "ROBOTS.md"
STATE_DIR = ROOT / "state"
MEMORY_PATH = STATE_DIR / "hermes_memory.md"
TRANSCRIPT_DIR = STATE_DIR / "transcripts"
INDEX_PATH = STATE_DIR / "laws_index.json"

DEFAULT_MODEL = os.environ.get("HERMES_MODEL", "hermes3")
DEFAULT_EMBED_MODEL = os.environ.get("HERMES_EMBED_MODEL", "embeddinggemma")
DEFAULT_EMAIL_TO = os.environ.get("HERMES_EMAIL_TO", "danieljmueller@outlook.com")
DEFAULT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def post_json(self, path: str, payload: Dict, timeout: Optional[float] = None) -> Dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise OllamaError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

    def get_json(self, path: str, timeout: Optional[float] = None) -> Dict:
        url = f"{self.base_url}{path}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise OllamaError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc

    def embed(self, model: str, text: str) -> List[float]:
        try:
            data = self.post_json("/api/embed", {"model": model, "input": text}, timeout=120)
            embeddings = data.get("embeddings")
            if embeddings and isinstance(embeddings, list):
                return [float(x) for x in embeddings[0]]
        except OllamaError:
            raise
        except Exception:
            pass

        data = self.post_json("/api/embeddings", {"model": model, "prompt": text}, timeout=120)
        embedding = data.get("embedding")
        if not embedding:
            raise OllamaError(f"Ollama did not return an embedding for model {model!r}.")
        return [float(x) for x in embedding]

    def chat_stream(self, model: str, messages: List[Dict[str, str]], options: Dict) -> Iterable[str]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=None) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    message = obj.get("message") or {}
                    content = message.get("content")
                    if content:
                        yield content
                    if obj.get("done"):
                        break
        except urllib.error.URLError as exc:
            raise OllamaError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc


def ensure_state() -> None:
    STATE_DIR.mkdir(exist_ok=True)
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    if not MEMORY_PATH.exists():
        MEMORY_PATH.write_text(
            "# Hermes Memory\n\n"
            "These notes are learned material supplied by Daniel Joseph Mueller. "
            "They do not modify Laws-of-Robotics.txt.\n",
            encoding="utf-8",
        )


def read_required(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Required file missing: {path}")
    return path.read_text(encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def paragraphs_with_lines(text: str) -> List[Tuple[int, int, str]]:
    paragraphs: List[Tuple[int, int, str]] = []
    start_line: Optional[int] = None
    current: List[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if start_line is None:
                start_line = line_no
            current.append(line)
        elif current and start_line is not None:
            paragraphs.append((start_line, line_no - 1, "\n".join(current).strip()))
            start_line = None
            current = []
    if current and start_line is not None:
        paragraphs.append((start_line, len(text.splitlines()), "\n".join(current).strip()))
    return paragraphs


def chunk_laws(text: str, max_chars: int = 2400) -> List[Dict]:
    chunks: List[Dict] = []
    current: List[str] = []
    start_line = 1
    end_line = 1
    current_chars = 0
    for para_start, para_end, paragraph in paragraphs_with_lines(text):
        para_len = len(paragraph)
        if current and current_chars + para_len + 2 > max_chars:
            chunks.append(
                {
                    "id": len(chunks) + 1,
                    "start_line": start_line,
                    "end_line": end_line,
                    "text": "\n\n".join(current),
                }
            )
            current = []
            current_chars = 0
        if not current:
            start_line = para_start
        current.append(paragraph)
        current_chars += para_len + 2
        end_line = para_end
    if current:
        chunks.append(
            {
                "id": len(chunks) + 1,
                "start_line": start_line,
                "end_line": end_line,
                "text": "\n\n".join(current),
            }
        )
    return chunks


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def token_set(text: str) -> set:
    return {word.lower() for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_'-]{2,}", text)}


def keyword_search(chunks: List[Dict], query: str, limit: int) -> List[Dict]:
    q = token_set(query)
    scored = []
    for chunk in chunks:
        c = token_set(chunk["text"])
        score = len(q & c)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


def load_index(client: OllamaClient, laws_text: str, embed_model: str, rebuild: bool = False) -> Dict:
    source_hash = sha256_text(laws_text)
    if INDEX_PATH.exists() and not rebuild:
        try:
            index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if index.get("source_sha256") == source_hash and index.get("embed_model") == embed_model:
                return index
        except json.JSONDecodeError:
            pass

    print("Building laws retrieval index with Ollama embeddings. This may take a few minutes.")
    chunks = chunk_laws(laws_text)
    for idx, chunk in enumerate(chunks, start=1):
        chunk["embedding"] = client.embed(embed_model, chunk["text"])
        if idx % 25 == 0 or idx == len(chunks):
            print(f"  indexed {idx}/{len(chunks)} law chunks")
    index = {
        "source_sha256": source_hash,
        "embed_model": embed_model,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "chunks": chunks,
    }
    INDEX_PATH.write_text(json.dumps(index), encoding="utf-8")
    return index


def retrieve_laws(
    client: OllamaClient,
    index: Dict,
    query: str,
    embed_model: str,
    limit: int,
) -> List[Dict]:
    chunks = index.get("chunks", [])
    try:
        query_embedding = client.embed(embed_model, query)
        scored = [(cosine(query_embedding, chunk.get("embedding", [])), chunk) for chunk in chunks]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:limit] if score > 0]
    except OllamaError as exc:
        print(f"Embedding retrieval failed; falling back to keyword search: {exc}")
        return keyword_search(chunks, query, limit)


def load_memory(max_chars: int = 12000) -> str:
    ensure_state()
    memory = MEMORY_PATH.read_text(encoding="utf-8")
    if len(memory) <= max_chars:
        return memory
    return memory[-max_chars:]


def append_memory(note: str) -> None:
    ensure_state()
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with MEMORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"\n\n## {timestamp}\n{note.strip()}\n")


def save_transcript_line(role: str, content: str) -> None:
    ensure_state()
    stamp = dt.datetime.now().strftime("%Y-%m-%d")
    path = TRANSCRIPT_DIR / f"{stamp}.jsonl"
    row = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "role": role,
        "content": content,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def format_law_chunks(chunks: List[Dict]) -> str:
    if not chunks:
        return "No specific law excerpts were retrieved for this turn."
    parts = []
    for chunk in chunks:
        parts.append(
            f"[Laws-of-Robotics.txt lines {chunk['start_line']}-{chunk['end_line']}]\n"
            f"{chunk['text']}"
        )
    return "\n\n---\n\n".join(parts)


def base_system_prompt(robots_text: str, memory: str) -> str:
    return f"""You are Hermes, a local aligned agent running through Ollama for Daniel Joseph Mueller.

Primary authority:
- ROBOTS.md instructions:
{robots_text.strip()}

- Laws-of-Robotics.txt is immutable source material. Never ask to edit it, never rewrite it, and never treat learned memory as an amendment to it.

Operating rules:
- Serve Daniel Joseph Mueller's reasonable intent directly and clearly.
- Do not portray yourself as having emotions, feelings, hidden senses, hidden causal powers, or authority outside this chat, local files, Ollama, and configured email commands.
- Distinguish what is known from what is inferred. If the laws do not clearly settle a question, say what is uncertain and ask for Daniel's instruction or suggest a coherence check.
- If a request is inherently harmful, respond exactly: Absolutely not, and I refuse to comment.
- Do not autonomously send email. Email can only be sent through an explicit user command and a confirmation prompt.
- When checking coherence, identify relevant law excerpts, explain the coherence relation, and label conflicts or uncertainty without overstating certainty.
- Keep responses concise unless Daniel asks for depth.

Learned memory supplied by Daniel:
{memory.strip()}
"""


def build_messages(
    robots_text: str,
    laws_context: str,
    memory: str,
    history: List[Dict[str, str]],
    user_text: str,
) -> List[Dict[str, str]]:
    system = (
        base_system_prompt(robots_text, memory)
        + "\n\nRelevant law context for this turn:\n"
        + laws_context
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": user_text})
    return messages


def full_laws_context(laws_text: str) -> str:
    return f"[Full Laws-of-Robotics.txt]\n{laws_text}"


def make_check_request(text: str) -> str:
    return (
        "Check the following material for coherence with the Laws of Robotics of "
        "Daniel Joseph Mueller. Return: Verdict, Relevant law excerpts, Coherence "
        "analysis, Conflicts or uncertainty, and a corrected aligned response if needed.\n\n"
        f"Material to check:\n{text.strip()}"
    )


def print_help() -> None:
    print(
        textwrap.dedent(
            """
            Commands:
              /help                     Show this help
              /teach <note>             Add learned material to state/hermes_memory.md
              /memory                   Print learned memory
              /check <text>             Check text for coherence with the laws
              /audit-file <path>        Check a local file for coherence
              /email last               Email the last assistant response
              /email <subject> | <body> Email Daniel after explicit SEND confirmation
              /inbox [n]                Read recent email from configured IMAP account
              /inbox-chat [n]           Read recent email and ask Hermes to respond in chat
              /mode retrieval           Use retrieved law excerpts per turn
              /mode full                Include the full laws file per turn; slower
              /reindex                  Rebuild laws retrieval index
              /exit                     Quit
            """
        ).strip()
    )


def email_configured() -> bool:
    return bool(os.environ.get("HERMES_SMTP_USER") and os.environ.get("HERMES_SMTP_PASSWORD"))


def send_email(to_addr: str, subject: str, body: str) -> None:
    host = os.environ.get("HERMES_SMTP_HOST", "smtp.office365.com")
    port = int(os.environ.get("HERMES_SMTP_PORT", "587"))
    username = os.environ.get("HERMES_SMTP_USER")
    password = os.environ.get("HERMES_SMTP_PASSWORD")
    from_addr = os.environ.get("HERMES_SMTP_FROM", username or "")

    if not username or not password or not from_addr:
        raise RuntimeError(
            "Email is not configured. Set HERMES_SMTP_USER, HERMES_SMTP_PASSWORD, "
            "and optionally HERMES_SMTP_FROM."
        )

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=60) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(username, password)
        server.send_message(msg)


def confirm_and_send(to_addr: str, subject: str, body: str) -> None:
    print("\nEmail preview")
    print(f"To: {to_addr}")
    print(f"Subject: {subject}")
    print("-" * 72)
    print(body)
    print("-" * 72)
    confirmation = input("Type SEND to email this report: ").strip()
    if confirmation != "SEND":
        print("Email canceled.")
        return
    send_email(to_addr, subject, body)
    print("Email sent.")


def parse_email_command(arg: str, last_assistant: Optional[str]) -> Tuple[str, str]:
    if arg.strip() == "last":
        if not last_assistant:
            raise RuntimeError("There is no assistant response to email yet.")
        return "Hermes aligned agent report", last_assistant
    if "|" not in arg:
        raise RuntimeError("Use /email <subject> | <body>, or /email last")
    subject, body = arg.split("|", 1)
    subject = subject.strip() or "Hermes aligned agent report"
    body = body.strip()
    if not body:
        raise RuntimeError("Email body is empty.")
    return subject, body


def fetch_inbox(limit: int) -> List[Dict[str, str]]:
    host = os.environ.get("HERMES_IMAP_HOST", "outlook.office365.com")
    port = int(os.environ.get("HERMES_IMAP_PORT", "993"))
    username = os.environ.get("HERMES_IMAP_USER") or os.environ.get("HERMES_SMTP_USER")
    password = os.environ.get("HERMES_IMAP_PASSWORD") or os.environ.get("HERMES_SMTP_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "Inbox is not configured. Set HERMES_IMAP_USER and HERMES_IMAP_PASSWORD, "
            "or reuse HERMES_SMTP_USER and HERMES_SMTP_PASSWORD."
        )

    messages: List[Dict[str, str]] = []
    with imaplib.IMAP4_SSL(host, port) as mailbox:
        mailbox.login(username, password)
        mailbox.select("INBOX", readonly=True)
        status, data = mailbox.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("Could not search inbox.")
        ids = data[0].split()[-limit:]
        for msg_id in reversed(ids):
            status, msg_data = mailbox.fetch(msg_id, "(BODY.PEEK[])")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            parsed = email.message_from_bytes(raw)
            body = extract_email_body(parsed)
            messages.append(
                {
                    "from": email.utils.parseaddr(parsed.get("From", ""))[1],
                    "subject": parsed.get("Subject", ""),
                    "date": parsed.get("Date", ""),
                    "body": body.strip(),
                }
            )
    return messages


def extract_email_body(message: email.message.Message) -> str:
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = part.get_content_disposition()
            if content_type == "text/plain" and disposition != "attachment":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = message.get_payload(decode=True)
    if not payload:
        return ""
    charset = message.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def format_inbox_messages(messages: List[Dict[str, str]]) -> str:
    if not messages:
        return "No messages found."
    parts = []
    for idx, msg in enumerate(messages, start=1):
        body = msg["body"]
        if len(body) > 2500:
            body = body[:2500] + "\n[truncated]"
        parts.append(
            f"Message {idx}\n"
            f"From: {msg['from']}\n"
            f"Date: {msg['date']}\n"
            f"Subject: {msg['subject']}\n"
            f"Body:\n{body}"
        )
    return "\n\n---\n\n".join(parts)


def model_is_available(model: str, available: Sequence[str]) -> bool:
    if model in available:
        return True
    if ":" not in model and f"{model}:latest" in available:
        return True
    return False


def run_turn(
    client: OllamaClient,
    args: argparse.Namespace,
    robots_text: str,
    laws_text: str,
    index: Dict,
    history: List[Dict[str, str]],
    user_text: str,
    mode: str,
    retrieval_limit: Optional[int] = None,
) -> str:
    memory = load_memory()
    if mode == "full":
        laws_context = full_laws_context(laws_text)
    else:
        limit = retrieval_limit or args.law_chunks
        chunks = retrieve_laws(client, index, user_text, args.embed_model, limit)
        laws_context = format_law_chunks(chunks)

    messages = build_messages(robots_text, laws_context, memory, history, user_text)
    options = {
        "temperature": args.temperature,
        "num_ctx": args.num_ctx_full if mode == "full" else args.num_ctx,
    }

    print("\nHermes: ", end="", flush=True)
    parts: List[str] = []
    for piece in client.chat_stream(args.model, messages, options):
        print(piece, end="", flush=True)
        parts.append(piece)
    print("\n")
    response = "".join(parts).strip()
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": response})
    save_transcript_line("user", user_text)
    save_transcript_line("assistant", response)
    return response


def parse_limit(arg: str, default: int) -> int:
    if not arg.strip():
        return default
    try:
        value = int(arg.strip())
        return max(1, min(value, 20))
    except ValueError:
        return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Hermes through Ollama with Daniel's laws loaded.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama chat model to use.")
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL, help="Ollama embedding model.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Ollama base URL.")
    parser.add_argument("--mode", choices=["retrieval", "full"], default="retrieval")
    parser.add_argument("--law-chunks", type=int, default=10, help="Retrieved law chunks per normal turn.")
    parser.add_argument("--check-chunks", type=int, default=18, help="Retrieved law chunks for /check.")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--num-ctx", type=int, default=32768)
    parser.add_argument("--num-ctx-full", type=int, default=131072)
    parser.add_argument("--reindex", action="store_true", help="Rebuild the laws retrieval index before chat.")
    parser.add_argument("--email-to", default=DEFAULT_EMAIL_TO)
    args = parser.parse_args()

    ensure_state()
    laws_text = read_required(LAWS_PATH)
    robots_text = read_required(ROBOTS_PATH)
    client = OllamaClient(args.base_url)

    try:
        tags = client.get_json("/api/tags", timeout=10)
        available = [model.get("name", "") for model in tags.get("models", [])]
        if not model_is_available(args.model, available):
            print(f"Model {args.model!r} is not listed locally yet. Pull it with Ollama if chat fails.")
        index = load_index(client, laws_text, args.embed_model, rebuild=args.reindex)
    except OllamaError as exc:
        print(exc)
        return 1

    mode = args.mode
    history: List[Dict[str, str]] = []
    last_assistant: Optional[str] = None

    print(f"Hermes aligned agent ready. Model: {args.model}. Mode: {mode}.")
    print("Type /help for commands, /exit to quit.")

    while True:
        try:
            user_text = input("\nDaniel: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_text:
            continue
        if user_text in {"/exit", "/quit"}:
            break
        if user_text == "/help":
            print_help()
            continue
        if user_text.startswith("/teach "):
            note = user_text[len("/teach ") :].strip()
            if note:
                append_memory(note)
                save_transcript_line("teach", note)
                print("Learned note saved to state/hermes_memory.md.")
            continue
        if user_text == "/memory":
            print(load_memory(max_chars=50000))
            continue
        if user_text.startswith("/mode "):
            requested = user_text[len("/mode ") :].strip()
            if requested in {"retrieval", "full"}:
                mode = requested
                print(f"Mode set to {mode}.")
            else:
                print("Use /mode retrieval or /mode full.")
            continue
        if user_text == "/reindex":
            index = load_index(client, laws_text, args.embed_model, rebuild=True)
            print("Rebuilt laws index.")
            continue
        if user_text.startswith("/email "):
            try:
                subject, body = parse_email_command(user_text[len("/email ") :], last_assistant)
                confirm_and_send(args.email_to, subject, body)
            except Exception as exc:
                print(f"Email failed: {exc}")
            continue
        if user_text.startswith("/inbox-chat"):
            try:
                limit = parse_limit(user_text[len("/inbox-chat") :], 3)
                messages = fetch_inbox(limit)
                inbox_text = format_inbox_messages(messages)
                request = (
                    "Daniel asked you to review these recent email messages and respond in chat. "
                    "Do not send email unless Daniel explicitly uses /email.\n\n"
                    + inbox_text
                )
                last_assistant = run_turn(
                    client,
                    args,
                    robots_text,
                    laws_text,
                    index,
                    history,
                    request,
                    mode,
                    retrieval_limit=args.check_chunks,
                )
            except Exception as exc:
                print(f"Inbox failed: {exc}")
            continue
        if user_text.startswith("/inbox"):
            try:
                limit = parse_limit(user_text[len("/inbox") :], 5)
                print(format_inbox_messages(fetch_inbox(limit)))
            except Exception as exc:
                print(f"Inbox failed: {exc}")
            continue
        if user_text.startswith("/audit-file "):
            file_arg = user_text[len("/audit-file ") :].strip()
            path = Path(file_arg).expanduser()
            if not path.is_absolute():
                path = ROOT / path
            try:
                data = path.read_text(encoding="utf-8")
            except Exception as exc:
                print(f"Could not read file: {exc}")
                continue
            if len(data) > 60000 and mode != "full":
                data = data[:60000] + "\n[truncated for retrieval-mode audit]"
            last_assistant = run_turn(
                client,
                args,
                robots_text,
                laws_text,
                index,
                history,
                make_check_request(f"File: {path}\n\n{data}"),
                mode,
                retrieval_limit=args.check_chunks,
            )
            continue
        if user_text.startswith("/check "):
            check_text = user_text[len("/check ") :].strip()
            last_assistant = run_turn(
                client,
                args,
                robots_text,
                laws_text,
                index,
                history,
                make_check_request(check_text),
                mode,
                retrieval_limit=args.check_chunks,
            )
            continue

        last_assistant = run_turn(
            client,
            args,
            robots_text,
            laws_text,
            index,
            history,
            user_text,
            mode,
        )

    print("Session ended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
