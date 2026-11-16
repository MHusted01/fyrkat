"""Shared readers for Claude Code session transcripts. Standard library only.

A transcript is a JSON Lines file that Claude Code writes for each session, with one file per
subagent run beside it. These helpers find the files for a project directory and yield the
records the metric scripts need. Nothing here writes to a transcript or to the repository.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator

# Sessions smaller than this are startup probes with no work in them.
MIN_SESSION_BYTES = 1_000_000
SYNTHETIC_MODEL = "<synthetic>"


def transcript_dir(project_dir: str) -> Path:
    """Return the directory Claude Code uses for a project's transcripts.

    Claude Code names it after the absolute project path, with every character that is not a
    letter or digit replaced by a dash. The path is derived at run time, so no script holds it.
    """
    key = re.sub(r"[^A-Za-z0-9]", "-", str(Path(project_dir).resolve()))
    return Path.home() / ".claude" / "projects" / key


def add_location_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project-dir",
        default=None,
        help="project whose transcripts are read (default: the current directory)",
    )
    parser.add_argument(
        "--transcripts",
        help="transcript directory to read instead of the one derived from --project-dir",
    )


def redact(text: str) -> str:
    """Remove the home directory, and the form of it inside transcript directory names, from text."""
    home = str(Path.home())
    return text.replace(home, "~").replace(re.sub(r"[^A-Za-z0-9]", "-", home), "-HOME")


def resolve_dir(args: argparse.Namespace) -> Path:
    """Return the transcript directory named by the arguments, or exit with a clear message."""
    directory = Path(args.transcripts) if args.transcripts else transcript_dir(args.project_dir or os.getcwd())
    if not directory.is_dir():
        sys.exit(f"no transcript directory at {redact(str(directory))}")
    return directory


def records(path: Path) -> Iterator[dict]:
    """Yield each JSON record in a transcript. A line that is not JSON is skipped and counted."""
    skipped = 0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(record, dict):
                yield record
    if skipped:
        print(f"note: skipped {skipped} unreadable line(s) in one transcript", file=sys.stderr)


def started(path: Path) -> str:
    """Timestamp of the first dated record, so that order does not change when a session resumes."""
    for record in records(path):
        if record.get("timestamp"):
            return record["timestamp"]
    return ""


def main_transcripts(directory: Path, include_small: bool = False) -> list[Path]:
    """Return the main session transcripts, in the order the sessions started."""
    paths = sorted(directory.glob("*.jsonl"), key=started)
    if include_small:
        return paths
    return [p for p in paths if p.stat().st_size >= MIN_SESSION_BYTES]


def subagent_transcripts(directory: Path, session: Path | None = None) -> list[tuple[Path, dict]]:
    """Return (transcript, metadata) for subagent runs, oldest first.

    The metadata holds the agent type and the description the caller gave the run.
    """
    pattern = f"{session.stem}/subagents/*.jsonl" if session else "*/subagents/*.jsonl"
    found = []
    for path in sorted(directory.glob(pattern), key=started):
        meta_path = path.with_suffix(".meta.json")
        meta: dict = {}
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                print(f"note: unreadable metadata for one subagent run: {type(error).__name__}", file=sys.stderr)
        found.append((path, meta))
    return found


def message(record: dict) -> dict:
    value = record.get("message")
    return value if isinstance(value, dict) else {}


def content_blocks(record: dict) -> list[dict]:
    content = message(record).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def tool_uses(record: dict) -> Iterator[dict]:
    if record.get("type") != "assistant":
        return
    for block in content_blocks(record):
        if block.get("type") == "tool_use":
            yield block


def tool_results(record: dict) -> Iterator[dict]:
    if record.get("type") != "user":
        return
    for block in content_blocks(record):
        if block.get("type") == "tool_result":
            yield block


def api_calls(path: Path) -> dict[str, dict]:
    """Return one entry per model request: its model, usage, timestamp and effort.

    A request appears on several records, one per content block, each repeating the same usage.
    Keying by the message ID counts it once.
    """
    calls: dict[str, dict] = {}
    for record in records(path):
        if record.get("type") != "assistant":
            continue
        body = message(record)
        usage = body.get("usage")
        if not usage or not body.get("id") or body.get("model") == SYNTHETIC_MODEL:
            continue
        calls[body["id"]] = {
            "model": body.get("model"),
            "usage": usage,
            "timestamp": record.get("timestamp"),
            "effort": record.get("effort"),
        }
    return calls


def context_tokens(usage: dict) -> int:
    """Tokens the model read for one request: fresh input plus cached input."""
    return (
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )


def thinking_tokens(usage: dict) -> int:
    return (usage.get("output_tokens_details") or {}).get("thinking_tokens", 0)


def read_key(arguments: dict) -> tuple:
    """Identify one Read call. Reading the next part of a file is not a repeat of the first part."""
    return (arguments.get("file_path", ""), arguments.get("offset"), arguments.get("limit"))


# A Bash command that changes a file: a commit, an in-place edit, or output sent to a file that
# is not a device or a temporary directory. A heuristic: it reads the command text only.
_BASH_WRITE = re.compile(
    r"\bgit\s+(commit|apply|mv|rm)\b|\bsed\s+-i|\bwrite_text\(|\btee\s+[^-|]"
    r"|(?<![0-9&>])>>?\s*(?!/dev/|/tmp/|/private/tmp/|&)[\"']?[A-Za-z0-9_.$~/-]"
)


def bash_writes(command: str) -> bool:
    return bool(_BASH_WRITE.search(command))


def is_limit_stop(text: str) -> bool:
    """True for Claude Code's usage-limit message, and not for other messages about limits."""
    lowered = text.lower()
    return "hit your" in lowered and "limit" in lowered


def parse_time(stamp: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def size(value: object) -> int:
    """Characters a value adds to the conversation."""
    return len(value) if isinstance(value, str) else len(json.dumps(value, ensure_ascii=False))
