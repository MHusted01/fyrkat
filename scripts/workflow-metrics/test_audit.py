#!/usr/bin/env python3
"""Tests for audit.py and the shared helpers. Run: python3 -B scripts/workflow-metrics/test_audit.py"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import audit
import transcripts as tr

HOME = str(Path.home())


def tool_call(name: str, **arguments: object) -> str:
    block = {"type": "tool_use", "id": "t", "name": name, "input": arguments}
    return json.dumps({"type": "assistant", "message": {"content": [block]}})


class AuditCases(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        # The auditor compares path text, so the root does not have to exist.
        self.root = Path("/private/tmp/claude-0/session-a/replay")
        self.auditor = audit.Auditor(self.root, [])
        self.own = str(tr.transcript_dir(str(self.root)))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def flagged(self, name: str, **arguments: object) -> bool:
        return self.auditor.problem(name, arguments) is not None

    def test_review_work_inside_the_root_is_clean(self) -> None:
        self.assertFalse(self.flagged("Bash", command="git diff HEAD~1 && cat docs/a.md"))
        self.assertFalse(self.flagged("Read", file_path=f"{self.root}/repo/.claude/agents/reviewer.md"))
        self.assertFalse(self.flagged("Bash", command="cargo xtask check"))
        self.assertFalse(self.flagged("Bash", command=f"ls {HOME}/.cargo/bin"))

    def test_harmless_lookalikes_are_clean(self) -> None:
        self.assertFalse(self.flagged("Bash", command="git remote -v"))
        self.assertFalse(self.flagged("Bash", command="rg 'https://' docs"))
        self.assertFalse(self.flagged("Bash", command="grep -n high docs/a.md"))
        self.assertFalse(self.flagged("Read", file_path=f"{self.own}/abc/tool-results/big.txt"))

    def test_tools_off_the_allowlist_are_flagged(self) -> None:
        self.assertTrue(self.flagged("mcp__claude-in-chrome__navigate", url="x"))
        self.assertTrue(self.flagged("WebFetch", url="x"))
        self.assertTrue(self.flagged("Agent", prompt="x"))

    def test_github_and_network_commands_are_flagged(self) -> None:
        self.assertTrue(self.flagged("Bash", command="gh pr view 6 --comments"))
        self.assertTrue(self.flagged("Bash", command="/opt/homebrew/bin/gh pr view 6"))
        self.assertTrue(self.flagged("Bash", command="cd repo && git -C . fetch origin"))
        self.assertTrue(self.flagged("Bash", command="git remote add up x"))
        self.assertTrue(self.flagged("Bash", command="curl -s example.org"))
        self.assertTrue(self.flagged("Bash", command="python3 -c 'import urllib' https://example.org"))

    def test_the_home_directory_is_flagged(self) -> None:
        self.assertTrue(self.flagged("Bash", command="cd ~/.claude && grep -r finding projects"))
        self.assertTrue(self.flagged("Bash", command=f"cat {HOME}/dev/project/docs/a.md"))
        self.assertTrue(self.flagged("Bash", command="ls $HOME/dev"))
        self.assertTrue(self.flagged("Read", file_path=f"{HOME}/.claude/projects/other/x.jsonl"))
        self.assertTrue(self.flagged("Write", file_path=f"{HOME}/dev/project/a.md", content="x"))
        self.assertTrue(self.flagged("Read", file_path=f"{self.own}/abc/def.jsonl"))

    def test_another_scratch_directory_is_flagged(self) -> None:
        other = "/private/tmp/claude-0/session-b/review-notes.md"
        self.assertTrue(self.flagged("Read", file_path="/tmp/claude-0/session-b/review-notes.md"))
        self.assertFalse(self.flagged("Read", file_path="/tmp/claude-0/session-a/replay/repo/a.md"))
        self.assertTrue(self.flagged("Read", file_path=other))
        self.assertTrue(self.flagged("Bash", command=f"cat {other}"))

    def test_extra_patterns_are_applied(self) -> None:
        auditor = audit.Auditor(self.root, [r"answer-key"])
        self.assertIsNotNone(auditor.problem("Bash", {"command": "cat ../answer-key.md"}))

    def test_a_transcript_is_audited_end_to_end(self) -> None:
        directory = Path(self.tmp.name) / "transcripts"
        directory.mkdir()
        lines = [tool_call("Bash", command="git diff"), tool_call("Bash", command="gh pr view 6")]
        (directory / "session.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        checked, hits = audit.audit(directory, self.auditor)
        self.assertEqual(checked, 2)
        self.assertEqual([(hit[1], hit[2]) for hit in hits], [("Bash", "runs gh")])
        self.assertNotIn(HOME, " ".join(hit[3] for hit in hits))


class HelperCases(unittest.TestCase):
    def test_reading_the_next_part_of_a_file_is_not_a_repeat(self) -> None:
        first = tr.read_key({"file_path": "a.md", "offset": 1, "limit": 100})
        self.assertNotEqual(first, tr.read_key({"file_path": "a.md", "offset": 101, "limit": 100}))
        self.assertEqual(first, tr.read_key({"file_path": "a.md", "offset": 1, "limit": 100}))

    def test_shell_edits_are_recognised(self) -> None:
        for command in ("cat >> docs/plan.md <<'EOF'", "git commit -m x", "sed -i '' s/a/b/ f", "echo x > out.txt"):
            self.assertTrue(tr.bash_writes(command), command)
        for command in ("git diff", "cargo build 2>&1 | tail", "ls > /dev/null", "grep x f >/tmp/scratch.txt", "test 3 -gt 2"):
            self.assertFalse(tr.bash_writes(command), command)

    def test_only_the_usage_limit_message_is_a_limit_stop(self) -> None:
        self.assertTrue(tr.is_limit_stop("You've hit your 5-hour limit"))
        self.assertFalse(tr.is_limit_stop("API Error: rate limit, retrying"))

    def test_redaction_removes_the_home_directory(self) -> None:
        self.assertNotIn(HOME, tr.redact(f"{HOME}/dev/x and {tr.transcript_dir(HOME + '/dev/x')}"))


if __name__ == "__main__":
    unittest.main()
