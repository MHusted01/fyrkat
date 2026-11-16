#!/usr/bin/env python3
"""Tests for the shared transcript helpers. Run: bash scripts/workflow-metrics/test.sh"""

from __future__ import annotations

import unittest
from pathlib import Path

import transcripts as tr

HOME = str(Path.home())


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
