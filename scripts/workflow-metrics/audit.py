#!/usr/bin/env python3
"""Audit a blind review run: list every access the run was told not to make.

A replayed review must not see the findings of the original review. The run is isolated by
construction where that is possible (an exported tree with no later history). What cannot be
enforced is audited here, after the fact, from the run's transcripts. One hit voids the run.
Exit status is 1 when there is a hit.

The run is confined to one directory, given as --root. The audit flags:

- any tool that is not on the short list a review needs;
- any path in the home directory, where the real repository, the transcripts and the memory
  live, other than toolchain caches and the run's own saved tool output;
- any scratch directory of another session;
- commands that reach GitHub or the network.

It reads command text. A command that builds a path or a URL at run time is not caught, so a
clean audit is evidence of a blind run and not proof of one.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import transcripts as tr

ALLOWED_TOOLS = ("Bash", "Read", "Grep", "Glob", "Write", "Edit", "TodoWrite", "SubagentHandback")
PATH_ARGUMENTS = ("file_path", "path", "pattern", "notebook_path")
# Parts of the home directory a build legitimately reads.
HOME_EXEMPT = (".cargo", ".rustup")
NETWORK_PROGRAMS = r"curl|wget|nc|ncat|ssh|scp|sftp|rsync|ftp|telnet|open"
# Programs that only print or search their input. A URL in their arguments fetches nothing.
READERS = ("rg", "grep", "egrep", "fgrep", "echo", "printf", "cat", "sed", "awk", "head", "tail", "wc", "ls", "nl")
GIT_NETWORK = r"fetch|pull|clone|push|ls-remote|remote\s+(add|set-url|update)|submodule\s+(add|update)"
SCRATCH_TREE = re.compile(r"(?<![A-Za-z0-9_.-])(/private)?/tmp/claude-")


def segments(command: str) -> list[str]:
    return [part.strip() for part in re.split(r"\|\||&&|[;|\n]", command) if part.strip()]


def program(segment: str) -> str:
    """First word of a command segment that is not a variable assignment, without its directory."""
    for word in segment.split():
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", word):
            continue
        return word.strip("(\"'").rsplit("/", 1)[-1]
    return ""


class Auditor:
    def __init__(self, root: Path, forbid: list[str]) -> None:
        self.root = str(root.resolve())
        self.home = str(Path.home())
        # Claude Code saves a run's large outputs under its own transcript directory and tells the
        # agent to read them. That directory is the run's own, so reading it reveals nothing.
        self.own_output = re.compile(re.escape(str(tr.transcript_dir(self.root))) + r"/[^\s\"']*tool-results/")
        self.extra = [re.compile(pattern) for pattern in forbid]

    def path_problem(self, text: str) -> str | None:
        """Reason a piece of text names a forbidden place, or None."""
        cleaned = self.own_output.sub(" ", text)
        # Paths inside the root are the run's own. Remove them, in both spellings of a
        # temporary directory, before looking for places outside it.
        for spelling in {self.root, self.root.removeprefix("/private")}:
            cleaned = cleaned.replace(spelling, " ROOT")
        for pattern in self.extra:
            if pattern.search(cleaned):
                return f"matches --forbid /{pattern.pattern}/"
        home_forms = (re.escape(self.home), r"~", r"\$HOME\b", r"\$\{HOME\}")
        for form in home_forms:
            for match in re.finditer(rf"(?<![A-Za-z0-9_.-])(?:{form})(/[^\s\"']*)?", cleaned):
                rest = (match.group(1) or "").lstrip("/")
                if not rest.startswith(HOME_EXEMPT):
                    return "names the home directory"
        if SCRATCH_TREE.search(cleaned):
            return "names another session's scratch directory"
        return None

    def command_problem(self, command: str) -> str | None:
        problem = self.path_problem(command)
        if problem:
            return problem
        for segment in segments(command):
            name = program(segment)
            if name == "gh":
                return "runs gh"
            if re.fullmatch(NETWORK_PROGRAMS, name):
                return f"runs {name}"
            if name == "git" and re.search(rf"\bgit\b.*?\s({GIT_NETWORK})\b", segment):
                return "runs a git command that uses the network or changes a remote"
            if re.search(r"https?://", segment) and name not in READERS:
                return "passes a URL to a program that could fetch it"
        return None

    def problem(self, tool: str, arguments: dict) -> str | None:
        if tool not in ALLOWED_TOOLS:
            return "tool is not on the allowlist"
        if tool == "Bash":
            return self.command_problem(str(arguments.get("command", "")))
        return self.path_problem(" ".join(str(arguments.get(key, "")) for key in PATH_ARGUMENTS))


def excerpt(arguments: dict) -> str:
    text = str(arguments.get("command") or arguments.get("file_path") or arguments.get("path") or arguments)
    return tr.redact(" ".join(text.split()))[:160]


def audit(directory: Path, auditor: Auditor) -> tuple[int, list[tuple[int, str, str, str]]]:
    """Return the number of tool calls checked and the hits as (transcript index, tool, reason, excerpt)."""
    paths = tr.main_transcripts(directory, include_small=True)
    paths += [path for path, _ in tr.subagent_transcripts(directory)]
    checked, hits = 0, []
    for index, path in enumerate(paths, start=1):
        for record in tr.records(path):
            for block in tr.tool_uses(record):
                checked += 1
                tool, arguments = block.get("name", ""), block.get("input") or {}
                reason = auditor.problem(tool, arguments)
                if reason:
                    hits.append((index, tool, reason, excerpt(arguments)))
    return checked, hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    tr.add_location_arguments(parser)
    parser.add_argument("--root", required=True, help="the directory the run was confined to")
    parser.add_argument("--forbid", action="append", default=[], metavar="REGEX", help="extra forbidden pattern (repeatable)")
    args = parser.parse_args()
    if not args.transcripts and not args.project_dir:
        args.project_dir = args.root  # a blind run is started in its root
    directory = tr.resolve_dir(args)
    try:
        auditor = Auditor(Path(args.root), args.forbid)
    except re.error as error:
        sys.exit(f"bad pattern: {error}")

    checked, hits = audit(directory, auditor)
    print(f"checked {checked} tool call(s); {len(hits)} forbidden")
    for index, tool, reason, text in hits:
        print(f"  T{index}  {tool}  {reason}: {text}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
