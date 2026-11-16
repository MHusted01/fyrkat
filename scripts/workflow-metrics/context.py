#!/usr/bin/env python3
"""Per-session context size, interruptions, and signs of repeated work.

- Context per request, and how much of the input came from requests above a threshold.
- Compactions, usage-limit stops, and waits for the owner longer than ten minutes.
- Re-orientation: tokens read from the start of the session to its first change to a file other
  than the handoff, whether made with an editing tool or by a shell command (a commit, an
  in-place edit, output sent to a file). This is the price of starting a fresh session. The
  shell part is a heuristic over the command text.
- Repeats: identical Read calls (same file, offset and limit) and identical commands. Files read
  through the shell are not counted.
"""

from __future__ import annotations

import argparse
import collections
import statistics
from pathlib import Path

import transcripts as tr

LONG_WAIT_SECONDS = 600
HANDOFF_NAME = "SESSION_HANDOFF.md"
EDITING_TOOLS = ("Edit", "Write", "NotebookEdit")


def is_owner_turn(record: dict) -> bool:
    if record.get("type") != "user" or record.get("turnOrigin") != "human":
        return False
    content = tr.message(record).get("content")
    if isinstance(content, str):
        return True
    return any(block.get("type") == "text" for block in tr.content_blocks(record))


def summarize(path: Path, threshold: int) -> dict:
    calls = tr.api_calls(path)
    contexts = [tr.context_tokens(call["usage"]) for call in calls.values()]
    reads: collections.Counter = collections.Counter()
    commands: collections.Counter = collections.Counter()
    waits, limits, compactions = [], [], 0
    reorientation, first_edit_seen, counted = 0, False, set()
    last_assistant = None
    for record in tr.records(path):
        kind, stamp = record.get("type"), record.get("timestamp")
        body = tr.message(record)
        if kind == "system" and "compact" in str(record.get("subtype")):
            compactions += 1
        if kind == "assistant":
            last_assistant = stamp or last_assistant
            if body.get("model") == tr.SYNTHETIC_MODEL:
                text = " ".join(str(block.get("text", "")) for block in tr.content_blocks(record))
                if tr.is_limit_stop(text):
                    limits.append(stamp)
            if not first_edit_seen and body.get("id") in calls and body["id"] not in counted:
                counted.add(body["id"])
                reorientation += tr.context_tokens(calls[body["id"]]["usage"])
        for block in tr.tool_uses(record):
            name, arguments = block.get("name"), block.get("input") or {}
            if name == "Read":
                reads[tr.read_key(arguments)] += 1
            elif name == "Bash":
                commands[arguments.get("command", "")] += 1
                if tr.bash_writes(arguments.get("command", "")):
                    first_edit_seen = True
            elif name in EDITING_TOOLS and HANDOFF_NAME not in str(arguments.get("file_path", "")):
                first_edit_seen = True
        if is_owner_turn(record) and last_assistant and stamp:
            waits.append((tr.parse_time(stamp) - tr.parse_time(last_assistant)).total_seconds())
    total = sum(contexts)
    return {
        "calls": len(contexts),
        "median_context": statistics.median(contexts) if contexts else 0,
        "p90_context": sorted(contexts)[int(len(contexts) * 0.9)] if contexts else 0,
        "max_context": max(contexts, default=0),
        "share_above_threshold": sum(c for c in contexts if c > threshold) / max(total, 1),
        "compactions": compactions,
        "limit_stops": len(limits),
        "long_waits_minutes": [round(w / 60) for w in waits if w > LONG_WAIT_SECONDS],
        "reorientation_tokens": reorientation if first_edit_seen else None,
        "repeat_reads": sum(count - 1 for count in reads.values() if count > 1),
        "reads": sum(reads.values()),
        "repeat_commands": sum(count - 1 for count in commands.values() if count > 1),
        "commands": sum(commands.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    tr.add_location_arguments(parser)
    parser.add_argument("--threshold", type=int, default=200_000, help="context size to report the share above")
    args = parser.parse_args()
    directory = tr.resolve_dir(args)

    for index, session in enumerate(tr.main_transcripts(directory), start=1):
        row = summarize(session, args.threshold)
        if not row["calls"]:
            continue
        start = "n/a" if row["reorientation_tokens"] is None else f"{row['reorientation_tokens'] / 1e6:.2f}M"
        print(
            f"S{index:<2} calls {row['calls']:>4}  context median {row['median_context'] / 1e3:4.0f}k"
            f" p90 {row['p90_context'] / 1e3:4.0f}k max {row['max_context'] / 1e3:4.0f}k"
            f"  above {args.threshold // 1000}k: {row['share_above_threshold']:4.0%}"
            f"  compactions {row['compactions']}  limit stops {row['limit_stops']}"
            f"  re-orientation {start}"
            f"  identical re-reads {row['repeat_reads']}/{row['reads']}"
            f"  repeat commands {row['repeat_commands']}/{row['commands']}"
            f"  waits over 10 min: {row['long_waits_minutes']}"
        )


if __name__ == "__main__":
    main()
