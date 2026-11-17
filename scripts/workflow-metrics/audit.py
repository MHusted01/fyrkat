#!/usr/bin/env python3
"""Audit a blind review run: list every tool call that may have reached outside the run.

A replayed review must not see the findings of the original review. The run is isolated by
construction where that is possible (an exported tree with no later history, and the answer key
kept outside the run's directory tree). What cannot be enforced is audited here, after the
fact, from the run's transcripts. Exit status is 1 when anything is flagged.

The run is confined to one directory, given as --root. The audit flags a tool call when:

- the tool is not on the short list a review needs;
- it names an absolute path that is not inside the root, a system directory, a toolchain cache
  or the run's own saved tool output;
- it names the home directory, the filesystem root, or a parent directory (`..`) other than
  `../scratch`, or changes directory with no argument, which goes to the home directory;
- its text contains a program that reaches GitHub or the network, a git subcommand that does,
  or a URL, anywhere in the text, including inside a quoted or substituted command and inside
  the content of a file it writes.

It prefers a false alarm to a miss: `git grep fetch` and `rg 'https://'` are flagged. Every
flagged call is read by a person or an agent, and the run is void if one of them reached
material outside the root.

What this does not do. It reads text. A command that builds a path or a program name at run
time, or reaches out through an interpreter with no literal trace, is not caught. It is a check
on a reviewer that was told the rules and has no reason to evade them, not a defence against
one that tries. A clean audit is evidence of a blind run and not proof of one.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

import transcripts as tr

ALLOWED_TOOLS = ("Bash", "Read", "Grep", "Glob", "Write", "Edit", "TodoWrite", "SubagentHandback")
# Arguments that hold a path or a search location, and arguments that hold text a tool writes.
PATH_ARGUMENTS = ("file_path", "path", "notebook_path")
TEXT_ARGUMENTS = ("command", "content", "new_string")
# Absolute locations a build or a check legitimately reads.
SYSTEM_PREFIXES = ("/usr/", "/bin/", "/sbin/", "/opt/homebrew/", "/Library/", "/System/", "/dev/", "/nix/")
# Parts of the home directory a build legitimately reads.
HOME_EXEMPT = (".cargo/", ".rustup/")
ALLOWED_PARENT = "../scratch"

NOT_WORD = r"(?<![A-Za-z0-9_.-])"
END_WORD = r"(?![A-Za-z0-9_.-])"
NETWORK_PROGRAM = re.compile(
    NOT_WORD + r"(gh|curl|wget|aria2c|nc|ncat|socat|ssh|scp|sftp|rsync|ftp|telnet|lynx|w3m)" + END_WORD
)
GIT_NETWORK = re.compile(
    r"\bgit\b[^\n;|&]*?\b(fetch|pull|clone|push|ls-remote|remote\s+(add|set-url|update)|submodule)\b"
)
URL = re.compile(r"https?://")
# An SSH-style remote such as git@github.com:owner/repo carries no URL scheme and no path.
GITHUB_HOST = re.compile(r"github\.com", re.IGNORECASE)
# `~` is the home directory when it stands alone, starts a path or names a user. `~10 s` is not.
HOME_FORM = re.compile(
    r"(?<![A-Za-z0-9_])(~(?=/|[\s\"';|&)]|$|[A-Za-z_])[A-Za-z0-9_-]*|\$HOME\b|\$\{HOME\})(/[^\s\"'`;|&)<>]*)?"
)
PARENT = re.compile(r"(?<![A-Za-z0-9_.~$}-])\.\.(?:/[^\s\"'`;|&)<>]*)?(?![A-Za-z0-9_.])")
ABSOLUTE = re.compile(r"(?<![A-Za-z0-9_.~$}*-])/[A-Za-z0-9_.@+*?-][^\s\"'`;|&)<>]*")
# The filesystem root given as a whole word, as in `grep -r x /`, `cd /;ls` or `ls "/"`.
# A slash between numbers, as in `4 / 2`, is arithmetic in a note.
BARE_ROOT = re.compile(r"(?:^|(?<=[\s\"'(=]))(?<![0-9] )/(?=[\s\"';|&)]|$)")
# `cd` or `pushd` with no argument goes to the home directory.
BARE_CD = re.compile(r"(?:^|[;&|(\n])\s*(?:cd|pushd)(?:\s+--)?\s*(?:$|[;&|)\n])")
# A second route to every path on the machine, under an exempt prefix.
DATA_VOLUME = "/System/Volumes/"


class Auditor:
    def __init__(self, root: Path, forbid: list[str]) -> None:
        self.root = posixpath.normpath(str(root.resolve()))
        self.home = posixpath.normpath(str(Path.home()))
        # Claude Code saves a run's large outputs under the run's own transcript directory and
        # tells the agent to read them.
        self.own_transcripts = posixpath.normpath(str(tr.transcript_dir(self.root)))
        self.extra = [re.compile(pattern) for pattern in forbid]

    def inside(self, path: str, directory: str) -> bool:
        return path == directory or path.startswith(directory + "/")

    def absolute_problem(self, raw: str) -> str | None:
        """Reason an absolute path is outside what the run may touch, or None."""
        path = posixpath.normpath(raw)
        for spelling in {self.root, self.root.removeprefix("/private")}:
            if self.inside(path, spelling):
                return None
        if self.inside(path, self.own_transcripts) and "/tool-results/" in path + "/":
            return None
        if (path + "/").startswith(SYSTEM_PREFIXES) and not path.startswith(DATA_VOLUME):
            return None
        if self.inside(path, self.home):
            rest = path[len(self.home) :].lstrip("/") + "/"
            return None if rest.startswith(HOME_EXEMPT) else "names the home directory"
        return "names an absolute path outside the run"

    def path_problem(self, text: str) -> str | None:
        for match in HOME_FORM.finditer(text):
            rest = posixpath.normpath("/" + (match.group(2) or "")).lstrip("/") + "/"
            if not rest.startswith(HOME_EXEMPT):
                return "names the home directory"
        for match in PARENT.finditer(text):
            if not self.inside(posixpath.normpath(match.group(0)), ALLOWED_PARENT):
                return "names a parent directory"
        for match in ABSOLUTE.finditer(text):
            problem = self.absolute_problem(match.group(0))
            if problem:
                return problem
        if BARE_ROOT.search(text):
            return "names the filesystem root"
        if BARE_CD.search(text):
            return "changes directory with no argument, which goes to the home directory"
        return None

    def text_problem(self, text: str) -> str | None:
        # A backslash at the end of a line continues the command on the next one.
        text = re.sub(r"\\\n", " ", text)
        problem = self.path_problem(text)
        if problem:
            return problem
        match = NETWORK_PROGRAM.search(text)
        if match:
            return f"mentions the program {match.group(1)}"
        if GIT_NETWORK.search(text):
            return "mentions a git subcommand that uses the network or changes a remote"
        if URL.search(text):
            return "contains a URL"
        if GITHUB_HOST.search(text):
            return "names github.com"
        return None

    def problem(self, tool: str, arguments: object) -> str | None:
        if tool not in ALLOWED_TOOLS:
            return "tool is not on the allowlist"
        if not isinstance(arguments, dict):
            return "the call's arguments are not a mapping"
        # --forbid applies to every argument of every tool, absolute paths included.
        everything = json.dumps(arguments, ensure_ascii=False, default=str)
        for pattern in self.extra:
            if pattern.search(everything):
                return f"matches --forbid /{pattern.pattern}/"
        for key in PATH_ARGUMENTS:
            value = str(arguments.get(key) or "")
            if not value:
                continue
            # A bare relative path is inside the run. Anything else is checked as text.
            problem = self.absolute_problem(value) if value.startswith("/") else self.path_problem(value)
            if problem:
                return problem
        if tool == "Glob":
            # Glob searches from the directory part of an absolute pattern, whatever `path` says.
            # A Grep pattern is a regular expression and names no location.
            problem = self.path_problem(str(arguments.get("pattern") or ""))
            if problem:
                return problem
        for key in TEXT_ARGUMENTS:
            problem = self.text_problem(str(arguments.get(key) or ""))
            if problem:
                return problem
        return None


def excerpt(arguments: dict) -> str:
    text = str(arguments.get("command") or arguments.get("file_path") or arguments.get("path") or arguments)
    text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>", text)
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
                tool, arguments = block.get("name", ""), block.get("input")
                if arguments is None:
                    arguments = {}
                reason = auditor.problem(tool, arguments)
                if reason:
                    hits.append((index, tool, reason, excerpt(arguments if isinstance(arguments, dict) else {})))
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
    if checked == 0:
        # Nothing was read: a wrong directory or a changed transcript format. That is not a clean run.
        print("checked 0 tool calls: the audit read nothing, so it says nothing about the run", file=sys.stderr)
        sys.exit(2)
    print(f"checked {checked} tool call(s); {len(hits)} flagged for inspection")
    for index, tool, reason, text in hits:
        print(f"  T{index}  {tool}  {reason}: {text}")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
