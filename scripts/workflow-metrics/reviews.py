#!/usr/bin/env python3
"""One line per review run: size, effort, context, and what the reviewer read.

"Intake" is the text tool results put into the reviewer's context, grouped by what was read.
It shows how much of a review goes to the change and how much to the plan and the records.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import transcripts as tr
import usage

# Order matters: the first pattern that matches names the category.
CATEGORIES = (
    ("plan", r"sel4-spike-plan|sel4-spike-amendments"),
    ("records and docs", r"deviations\.md|SESSION_HANDOFF|roadmap|docs/(adr|research|standards|development)|AGENTS\.md|CONTRIBUTING"),
    ("result prose", r"results/[A-Za-z0-9-]+\.md"),
    ("raw evidence", r"results/[A-Za-z0-9-]+/|results-raw|evidence-manifest"),
    ("diff", r"git (diff|show|log)"),
    ("upstream source", r"external/"),
    ("project source", r"\.(rs|py|sh|toml|yml|yaml|c|h|cmake)\b"),
    ("build and run", r"cargo|ninja|cmake|qemu|build-|run-.*evidence"),
)
OTHER = "other"


def category(text: str) -> str:
    for name, pattern in CATEGORIES:
        if re.search(pattern, text):
            return name
    return OTHER


def summarize(path: Path) -> dict:
    """Measure one review transcript."""
    calls = tr.api_calls(path)
    intake: collections.Counter = collections.Counter()
    pending: dict[str, tuple[str, bool]] = {}
    seen_paths: set[str] = set()
    tools: collections.Counter = collections.Counter()
    repeat = 0
    for record in tr.records(path):
        for block in tr.tool_uses(record):
            name, arguments = block.get("name", ""), block.get("input") or {}
            tools[name] += 1
            if name == "Read":
                target = arguments.get("file_path", "")
                pending[block["id"]] = (category(target), target in seen_paths)
                seen_paths.add(target)
            elif name == "Bash":
                pending[block["id"]] = (category(arguments.get("command", "")), False)
        for block in tr.tool_results(record):
            if block.get("tool_use_id") not in pending:
                continue
            group, again = pending[block["tool_use_id"]]
            length = tr.size(block.get("content"))
            intake[group] += length
            repeat += length if again else 0
    usages = [call["usage"] for call in calls.values()]
    stamps = sorted(call["timestamp"] for call in calls.values() if call["timestamp"])
    minutes = None
    if len(stamps) > 1:
        minutes = (tr.parse_time(stamps[-1]) - tr.parse_time(stamps[0])).total_seconds() / 60
    output = sum(u.get("output_tokens", 0) for u in usages)
    return {
        "calls": len(calls),
        "efforts": sorted({str(call["effort"]) for call in calls.values()}),
        "models": sorted({str(call["model"]) for call in calls.values()}),
        "output_tokens": output,
        "thinking_share": sum(tr.thinking_tokens(u) for u in usages) / max(output, 1),
        "cache_read_tokens": sum(u.get("cache_read_input_tokens", 0) for u in usages),
        "cache_write_tokens": sum(u.get("cache_creation_input_tokens", 0) for u in usages),
        "max_context_tokens": max((tr.context_tokens(u) for u in usages), default=0),
        "minutes": minutes,
        "tools": dict(tools),
        "intake_chars": dict(intake),
        "repeat_read_chars": repeat,
    }


def estimate(row: dict, weights: dict) -> float | None:
    if len(row["models"]) != 1:
        return None
    counts = collections.Counter(
        output=row["output_tokens"], cache_read=row["cache_read_tokens"], cache_write=row["cache_write_tokens"]
    )
    return usage.estimate(counts, row["models"][0], weights)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    tr.add_location_arguments(parser)
    parser.add_argument("--agent", default="reviewer", help="agent type prefix to report (default: reviewer)")
    parser.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = parser.parse_args()
    directory, weights = tr.resolve_dir(args), usage.load_weights()

    rows = []
    for path, meta in tr.subagent_transcripts(directory):
        if not str(meta.get("agentType", "")).startswith(args.agent):
            continue
        row = summarize(path)
        row["agent"] = meta.get("agentType")
        row["description"] = meta.get("description")
        row["estimate_usd"] = estimate(row, weights)
        rows.append(row)
    if args.json:
        print(json.dumps(rows, indent=1))
        return

    total: collections.Counter = collections.Counter()
    for index, row in enumerate(rows, start=1):
        cost = "n/a" if row["estimate_usd"] is None else f"${row['estimate_usd']:.1f}"
        took = "n/a" if row["minutes"] is None else f"{row['minutes']:.0f} min"
        print(
            f"R{index:<3} {row['agent']:<16} effort {','.join(row['efforts']):<6} calls {row['calls']:>4}"
            f"  out {row['output_tokens'] / 1e3:5.0f}k  thinking {row['thinking_share']:4.0%}"
            f"  max context {row['max_context_tokens'] / 1e3:4.0f}k  cache write {row['cache_write_tokens'] / 1e3:5.0f}k"
            f"  est {cost:>6}  {took:>8}  {row['description']}"
        )
        total.update(row["intake_chars"])
        total["(repeat reads)"] += row["repeat_read_chars"]
    read = sum(v for k, v in total.items() if k != "(repeat reads)")
    print(f"\nIntake over {len(rows)} run(s): {read / 1e6:.2f}M characters")
    for name, value in total.most_common():
        print(f"  {value / max(read, 1):6.1%}  {value / 1e3:8.0f}k  {name}")


if __name__ == "__main__":
    main()
