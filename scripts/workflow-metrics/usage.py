#!/usr/bin/env python3
"""Tokens and estimated cost per session, split by role and model.

Roles are the main loop and each subagent type. The estimate uses weights.json and is for
comparing runs with each other. It is not a bill and not a measure of subscription usage.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import transcripts as tr

COMPONENTS = ("calls", "output", "thinking", "cache_read", "cache_write", "input")


def load_weights() -> dict:
    path = Path(__file__).with_name("weights.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))["models"]
    except (OSError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read {path.name}: {error}") from error


def totals(path: Path) -> dict[str, collections.Counter]:
    """Token totals per model for one transcript."""
    by_model: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for call in tr.api_calls(path).values():
        usage, counts = call["usage"], by_model[call["model"]]
        counts["calls"] += 1
        counts["output"] += usage.get("output_tokens", 0)
        counts["thinking"] += tr.thinking_tokens(usage)
        counts["cache_read"] += usage.get("cache_read_input_tokens", 0)
        counts["cache_write"] += usage.get("cache_creation_input_tokens", 0)
        counts["input"] += usage.get("input_tokens", 0)
    return by_model


def estimate(counts: collections.Counter, model: str, weights: dict) -> float | None:
    rates = weights.get(model)
    if rates is None:
        return None
    return sum(counts[name] / 1e6 * rates[name] for name in ("output", "cache_read", "cache_write"))


def session_rows(directory: Path, session: Path) -> list[dict]:
    rows = []
    for model, counts in totals(session).items():
        rows.append({"role": "main", "model": model, **counts})
    merged: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    runs: collections.Counter = collections.Counter()
    for path, meta in tr.subagent_transcripts(directory, session):
        role = meta.get("agentType", "unknown")
        runs[role] += 1
        for model, counts in totals(path).items():
            merged[(role, model)].update(counts)
    for (role, model), counts in merged.items():
        rows.append({"role": role, "model": model, "runs": runs[role], **counts})
    return rows


def describe(row: dict, weights: dict) -> str:
    counts = collections.Counter({name: row.get(name, 0) for name in COMPONENTS})
    cost = estimate(counts, row["model"], weights)
    calls = max(counts["calls"], 1)
    parts = [
        f"{row['role']:<10} {row['model']:<20}",
        f"calls {counts['calls']:>5}",
        f"out {counts['output'] / 1e6:6.2f}M",
        f"thinking {100 * counts['thinking'] / max(counts['output'], 1):3.0f}%",
        f"cache read {counts['cache_read'] / 1e6:7.1f}M",
        f"cache write {counts['cache_write'] / 1e6:5.2f}M",
        f"context/call {(counts['cache_read'] + counts['cache_write']) / calls / 1e3:4.0f}k",
        "est n/a" if cost is None else f"est ${cost:6.1f}",
    ]
    if row.get("runs"):
        parts.append(f"runs {row['runs']}")
    return "  ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    tr.add_location_arguments(parser)
    parser.add_argument("--all", action="store_true", help="include sessions with no work in them")
    parser.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = parser.parse_args()
    directory, weights = tr.resolve_dir(args), load_weights()

    grand: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    run_totals: dict[str, float] = {}
    output = []
    for index, session in enumerate(tr.main_transcripts(directory, args.all), start=1):
        rows = session_rows(directory, session)
        models_per_role = collections.Counter(row["role"] for row in rows)
        output.append({"session": f"S{index}", "rows": rows})
        if not args.json:
            print(f"\nS{index}")
        for row in rows:
            grand[(row["role"], row["model"])].update({k: row.get(k, 0) for k in COMPONENTS})
            if row.get("runs"):
                run_totals[row["role"]] = run_totals.get(row["role"], 0) + row["runs"] / models_per_role[row["role"]]
            if not args.json:
                print("  " + describe(row, weights))
    if args.json:
        print(json.dumps(output, indent=1))
        return
    print("\nAll sessions")
    for (role, model), counts in sorted(grand.items()):
        print("  " + describe({"role": role, "model": model, **counts}, weights))
    for role, runs in sorted(run_totals.items()):
        print(f"  {role}: {runs:.0f} run(s)")


if __name__ == "__main__":
    main()
