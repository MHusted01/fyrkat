#!/usr/bin/env python3
"""Tests for audit.py. Run: bash scripts/workflow-metrics/test.sh"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import audit
import transcripts as tr

HOME = str(Path.home())
ROOT = "/private/tmp/claude-0/session-a/replay"


def tool_call(name: str, **arguments: object) -> str:
    block = {"type": "tool_use", "id": "t", "name": name, "input": arguments}
    return json.dumps({"type": "assistant", "message": {"content": [block]}})


class AuditCases(unittest.TestCase):
    def setUp(self) -> None:
        # The auditor compares path text, so the root does not have to exist.
        self.auditor = audit.Auditor(Path(ROOT), [])
        self.own = str(tr.transcript_dir(ROOT))

    def flagged(self, name: str, **arguments: object) -> bool:
        return self.auditor.problem(name, arguments) is not None

    def bash(self, command: str) -> bool:
        return self.flagged("Bash", command=command)

    def test_review_work_inside_the_root_is_clean(self) -> None:
        for command in (
            "git diff HEAD~1..HEAD && cat docs/a.md",
            "git log --oneline HEAD~1..HEAD | head",
            "cargo xtask check 2>&1 | tail -5",
            "sed -n '1,40p' docs/a.md | sed 's/a/b/'",
            "awk '/^## /{print}' docs/a.md > ../scratch/headings.txt",
            f"ls {HOME}/.cargo/bin",
            "python3 -B verify-evidence.py --self-test 2>/dev/null",
            f"cat {ROOT}/repo/a.md /tmp/claude-0/session-a/replay/scratch/b.txt",
            "ls /usr/bin/python3 /opt/homebrew/bin",
        ):
            self.assertFalse(self.bash(command), command)
        self.assertFalse(self.flagged("Read", file_path=f"{ROOT}/repo/.claude/agents/reviewer.md"))
        self.assertFalse(self.flagged("Read", file_path="docs/a.md"))
        self.assertFalse(self.flagged("Grep", pattern="~/x|https?://|gh pr", path="docs"))
        self.assertFalse(self.flagged("Read", file_path=f"{self.own}/abc/tool-results/big.txt"))
        self.assertFalse(self.flagged("Write", file_path="../scratch/notes.md", content="finding 1"))
        self.assertFalse(self.flagged("Write", file_path="../scratch/notes.md", content="took ~10 s; ratio 4 / 2"))

    def test_tools_off_the_allowlist_are_flagged(self) -> None:
        for tool in ("mcp__claude-in-chrome__navigate", "WebFetch", "Agent", "ToolSearch"):
            self.assertTrue(self.flagged(tool, url="x"), tool)

    def test_github_and_network_commands_are_flagged_wherever_they_appear(self) -> None:
        for command in (
            "gh pr view 6 --comments",
            "/opt/homebrew/bin/gh pr view 6",
            "echo $(gh pr view 6 --comments)",
            "env gh pr view 6",
            "\\gh pr view 6",
            "if gh pr view 6; then :; fi",
            "for i in 1; do gh pr view $i; done",
            "sleep 0 & gh pr view 6",
            "bash -c 'gh pr view 6'",
            "cd repo && git -C . fetch origin",
            "time git fetch origin",
            "git remote add up x",
            "curl -s example.org",
            "cat <(curl -s example.org)",
            "env curl example.org",
            "python3 -c 'import urllib.request' https://example.org",
            "echo `wget -q -O- example.org`",
        ):
            self.assertTrue(self.bash(command), command)

    def test_written_content_is_scanned(self) -> None:
        self.assertTrue(self.flagged("Write", file_path="../scratch/x.py", content="open('https://example.org')"))
        self.assertTrue(self.flagged("Edit", file_path="../scratch/x.sh", new_string="gh pr view 6"))

    def test_the_home_directory_is_flagged(self) -> None:
        for command in (
            "cd ~/.claude && grep -r finding projects",
            f"cat {HOME}/dev/project/docs/a.md",
            "ls $HOME/dev",
            "ls ${HOME}/dev",
            "cd ~ && ls",
            f"ls {HOME}/.cargo/../.claude/projects",
            "ls ~/.cargo/../.claude",
            "ls ~root/x",
            "cat ~",
        ):
            self.assertTrue(self.bash(command), command)
        self.assertTrue(self.flagged("Read", file_path=f"{HOME}/.claude/projects/other/x.jsonl"))
        self.assertTrue(self.flagged("Write", file_path=f"{HOME}/dev/project/a.md", content="x"))

    def test_paths_that_leave_the_root_are_flagged(self) -> None:
        for command in (
            "cat ../key.md",
            "cd .. && cat key.md",
            "cat ../../replay-keys/report.md",
            "cat ../scratch/../key.md",
            "cat ../scratch-keys/key.md",
            f"cat {ROOT}/../key.md",
            f"cat {ROOT}-key/answers.md",
            f"cat {ROOT}.key",
            "cat /private/tmp/claude-0/session-b/review-notes.md",
            "cat /tmp/claude-0/session-b/review-notes.md",
            "rg finding /Users",
            "grep -r finding /tmp",
            "cat /Users/*/dev/project/a.md",
            "grep -r finding /",
            "ls / | head",
            f"cat {self.own}/x/tool-results/../../other-project/a.jsonl",
            f"cat {self.own}/../other-project/a/tool-results/x",
            f"cat {self.own}/abc/session.jsonl",
        ):
            self.assertTrue(self.bash(command), command)
        self.assertTrue(self.flagged("Read", file_path=f"{ROOT}/../key.md"))
        self.assertTrue(self.flagged("Read", file_path="../key.md"))
        self.assertTrue(self.flagged("Grep", pattern="x", path="/Users"))
        self.assertTrue(self.flagged("Glob", pattern="*.md", path="/"))
        self.assertTrue(self.flagged("Glob", pattern="/Users/*/.claude/projects/**/*.jsonl"))
        self.assertTrue(self.flagged("Glob", pattern=f"{HOME}/.claude/projects/**"))
        self.assertTrue(self.flagged("Glob", pattern="/private/tmp/claude-0/**/key*.md"))
        self.assertTrue(self.flagged("Glob", pattern="../**/*.md"))
        self.assertFalse(self.flagged("Glob", pattern="docs/**/*.md"))
        self.assertFalse(self.flagged("Glob", pattern=f"{ROOT}/repo/**/*.rs"))

    def test_the_root_and_a_bare_cd_are_flagged(self) -> None:
        for command in (
            "cd /;ls",
            "cd /&&ls",
            "ls /|head",
            'ls "/"',
            "cd && cat .claude/projects/x/y.jsonl",
            "cd; ls .claude/projects",
            "(cd && ls)",
            "cd -- && ls",
            "pushd; ls",
            "cat /System/Volumes/Data/private/tmp/claude-0/session-b/key.md",
        ):
            self.assertTrue(self.bash(command), command)
        for command in ("cd repo && ls", "cd docs; ls", "ls /System/Library/Fonts | head -1"):
            self.assertFalse(self.bash(command), command)

    def test_more_network_programs_are_flagged(self) -> None:
        for command in ("aria2c example.org/x", "socat - TCP:example.org:80"):
            self.assertTrue(self.bash(command), command)

    def test_extra_patterns_are_applied(self) -> None:
        auditor = audit.Auditor(Path(ROOT), [r"answer-key"])
        self.assertIsNotNone(auditor.problem("Bash", {"command": "cat answer-key.md"}))

    def test_a_transcript_is_audited_end_to_end_and_its_output_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            session = "00000000-0000-4000-8000-000000000000"  # made up
            lines = [
                tool_call("Bash", command="git diff"),
                tool_call("Bash", command=f"cat {HOME}/dev/project/a.md"),
                tool_call("Read", file_path=f"/private/tmp/claude-0/{session}/notes.md"),
            ]
            (directory / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            checked, hits = audit.audit(directory, self.auditor)
        self.assertEqual(checked, 3)
        self.assertEqual([hit[1] for hit in hits], ["Bash", "Read"])
        printed = " ".join(hit[3] for hit in hits)
        self.assertIn("~/dev/project/a.md", printed)
        self.assertNotIn(HOME, printed)
        self.assertNotIn(session, printed)


class CommandLineCases(unittest.TestCase):
    """The exit status is what a replay is voided on, so it is tested through the command line."""

    def run_audit(self, *commands: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            lines = [tool_call("Bash", command=command) for command in commands]
            (directory / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-B", str(Path(audit.__file__)), "--root", ROOT, "--transcripts", str(directory)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_a_clean_run_exits_zero(self) -> None:
        result = self.run_audit("git diff", "cargo xtask check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 flagged", result.stdout)

    def test_a_flagged_call_exits_one_and_is_listed(self) -> None:
        result = self.run_audit("git diff", "gh pr view 6")
        self.assertEqual(result.returncode, 1)
        self.assertIn("1 flagged", result.stdout)
        self.assertIn("gh pr view 6", result.stdout)

    def test_a_missing_transcript_directory_is_an_error_without_the_home_path(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(Path(audit.__file__)), "--root", ROOT, "--transcripts", HOME + "/does-not-exist"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(HOME, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
