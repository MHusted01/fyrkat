#!/usr/bin/env python3
"""Audit a blind review run: list every access the run was told not to make.

A replayed review must not see the findings of the original review. The run is isolated by
construction where that is possible (an exported tree with no later history). What cannot be
enforced is audited here: every command and file path in the run's transcripts is checked
against the forbidden patterns. One match voids the run. Exit status is 1 when anything matches.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import transcripts as tr

# Tools that reach GitHub or the network, where the original findings and fixes are published.
DEFAULT_FORBIDDEN = (
    r"(^|[\s;&|(])gh\s",
    r"\b(curl|wget|nc|ssh|scp)\b",
    r"https?://",
    r"git\s+(fetch|pull|clone|remote|ls-remote)\b",
    r"\.claude/projects",
)
NETWORK_TOOLS = ("WebFetch", "WebSearch")


def accesses(path: Path):
    """Yield (tool, text) for each thing a transcript's tool calls touched."""
    for record in tr.records(path):
        for block in tr.tool_uses(record):
            name, arguments = block.get("name", ""), block.get("input") or {}
            if name == "Bash":
                yield name, arguments.get("command", "")
            elif name in ("Read", "Grep", "Glob"):
                yield name, " ".join(str(arguments.get(key, "")) for key in ("file_path", "path", "pattern"))
            elif name in NETWORK_TOOLS:
                yield name, "network tool: " + str(arguments)[:200]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    tr.add_location_arguments(parser)
    parser.add_argument(
        "--forbid",
        action="append",
        default=[],
        metavar="REGEX",
        help="extra forbidden pattern, such as the path of the real repository (repeatable)",
    )
    args = parser.parse_args()
    directory = tr.resolve_dir(args)
    try:
        patterns = [re.compile(p) for p in (*DEFAULT_FORBIDDEN, *args.forbid)]
    except re.error as error:
        sys.exit(f"bad pattern: {error}")

    paths = tr.main_transcripts(directory, include_small=True)
    paths += [path for path, _ in tr.subagent_transcripts(directory)]
    checked, hits = 0, []
    for path in paths:
        for tool, text in accesses(path):
            checked += 1
            if tool in NETWORK_TOOLS:
                hits.append((path.name, tool, text))
                continue
            for pattern in patterns:
                if pattern.search(text):
                    hits.append((path.name, tool, f"/{pattern.pattern}/ in: {text[:200]}"))
                    break
    print(f"checked {checked} tool call(s) in {len(paths)} transcript(s); {len(hits)} forbidden")
    for name, tool, text in hits:
        print(f"  {name}  {tool}  {text}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
