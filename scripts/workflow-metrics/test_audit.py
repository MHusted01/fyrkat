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
            "grep -r answer /System",
            "find /System/Volumes -maxdepth 3",
            "rg x /System/",
        ):
            self.assertTrue(self.bash(command), command)
        self.assertTrue(self.flagged("Grep", pattern="x", path="/System"))
        self.assertTrue(self.flagged("Glob", pattern="/System/**/k.md"))
        for command in ("cd repo && ls", "cd docs; ls", "ls /System/Library/Fonts | head -1"):
            self.assertFalse(self.bash(command), command)

    def test_more_network_programs_are_flagged(self) -> None:
        for command in ("aria2c example.org/x", "socat - TCP:example.org:80"):
            self.assertTrue(self.bash(command), command)

    def test_extra_patterns_are_applied_to_every_tool_and_argument(self) -> None:
        auditor = audit.Auditor(Path(ROOT), [r"answer-key"])
        self.assertIsNotNone(auditor.problem("Bash", {"command": "cat answer-key.md"}))
        # An absolute path inside the root is otherwise allowed, so only --forbid can flag it.
        self.assertIsNotNone(auditor.problem("Read", {"file_path": f"{ROOT}/repo/answer-key.md"}))
        self.assertIsNotNone(auditor.problem("Grep", {"pattern": "x", "path": f"{ROOT}/answer-key"}))
        self.assertIsNotNone(auditor.problem("Write", {"file_path": f"{ROOT}/scratch/n.md", "content": "answer-key"}))
        self.assertIsNone(auditor.problem("Read", {"file_path": f"{ROOT}/repo/notes.md"}))

    def test_a_forbid_pattern_sees_each_string_and_no_key_names(self) -> None:
        def flagged(forbid: str, tool: str, **arguments: object) -> bool:
            return audit.Auditor(Path(ROOT), [forbid]).problem(tool, arguments) is not None

        self.assertTrue(flagged(r"^cat key", "Bash", command="cat key.md"))
        self.assertTrue(flagged(r"key\.md$", "Bash", command="cat key.md"))
        self.assertTrue(flagged(r"key\.md$", "Read", file_path=f"{ROOT}/repo/key.md"))
        self.assertTrue(flagged(r"key\s+notes", "Bash", command="cat key\nnotes"))
        self.assertTrue(flagged(r"^key$", "Grep", pattern="key", path="docs"))
        # Strings inside lists and nested mappings are strings the run wrote too.
        self.assertTrue(flagged(r"answer-key", "TodoWrite", todos=[{"content": "read answer-key", "status": "pending"}]))
        self.assertFalse(flagged(r"answer-key", "TodoWrite", todos=[{"content": "run the tests", "status": "pending"}]))
        # The names of the arguments are not text the run wrote.
        self.assertFalse(flagged(r"path", "Read", file_path="docs/a.md"))
        self.assertFalse(flagged(r"old", "Edit", file_path="../scratch/a.md", old_string="x", new_string="y"))
        self.assertFalse(flagged(r"command", "Bash", command="git diff"))

    def test_wrapped_literal_remotes_are_flagged(self) -> None:
        for command in (
            "git -C repo \\\n  fetch git@github.com:owner/repo main",
            "git clone git@github.com:owner/repo",
            "echo git@GitHub.com:owner/repo",
        ):
            self.assertTrue(self.bash(command), command)

    def test_a_command_continued_on_the_next_line_is_read_whole(self) -> None:
        # Nothing here names a host: only joining the lines shows that `git ... fetch` is one command.
        self.assertTrue(self.bash("git -C repo \\\n  fetch origin main"))
        self.assertTrue(self.bash("git \\\n pull"))
        # Bash removes the backslash and the newline, so these two lines are one word.
        self.assertTrue(self.bash(f"cat {ROOT}\\\n-key/answers.md"))
        self.assertFalse(self.bash("git -C repo \\\n  log --oneline"))

    def test_a_url_in_code_is_flagged_by_the_url_rule(self) -> None:
        # No `//host` path appears here, so the absolute-path rule never fires: only the URL rule does.
        command = "python3 -c \"urlopen(f'https://{h}/repos/o/r/pulls/6/comments')\""
        self.assertTrue(self.bash(command))
        self.assertEqual(self.auditor.problem("Bash", {"command": command}), "contains a URL")

    def test_every_git_network_subcommand_and_network_program_is_flagged(self) -> None:
        for sub in ("fetch origin", "pull", "clone x", "push origin x", "ls-remote origin", "submodule update", "remote add a b"):
            self.assertTrue(self.bash(f"git {sub}"), sub)
        for program in ("ssh host", "scp a b", "nc host 80", "rsync a b", "wget x", "telnet host"):
            self.assertTrue(self.bash(program), program)
        for command in ("git status", "git log --oneline", "git diff HEAD~1 HEAD", "git show HEAD"):
            self.assertFalse(self.bash(command), command)

    def test_the_toolchain_caches_are_exempt_only_directly_under_home(self) -> None:
        self.assertFalse(self.bash("ls ~/.cargo/bin"))
        self.assertTrue(self.bash("ls ~/dev/.cargo/bin"))
        self.assertTrue(self.bash("ls ~/dev/.rustup"))
        self.assertTrue(self.bash(f"ls {HOME}/dev/.cargo/bin"))

    def test_a_dev_path_is_system_and_a_malformed_call_is_flagged(self) -> None:
        self.assertFalse(self.bash("grep -r x /dev/null"))
        self.assertFalse(self.bash("grep '/dev/' docs"))
        self.assertEqual(self.auditor.problem("Bash", "gh pr view 6"), "the call's arguments are not a mapping")

    def test_the_run_own_saved_output_is_allowed_and_another_projects_is_not(self) -> None:
        own = f"{self.own}/abc/tool-results/x.txt"
        other = str(tr.transcript_dir("/private/tmp/claude-0/someone-else")) + "/abc/tool-results/x.txt"
        self.assertFalse(self.flagged("Read", file_path=own))
        self.assertTrue(self.flagged("Read", file_path=other))

    def test_subagent_transcripts_are_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "session.jsonl").write_text(tool_call("Bash", command="git diff") + "\n", encoding="utf-8")
            subagents = directory / "session" / "subagents"
            subagents.mkdir(parents=True)
            (subagents / "agent.jsonl").write_text(tool_call("Bash", command="gh pr view 6") + "\n", encoding="utf-8")
            checked, hits = audit.audit(directory, self.auditor)
        self.assertEqual(checked, 2)
        self.assertEqual([hit[2] for hit in hits], ["mentions the program gh"])

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

    def test_a_run_with_nothing_to_read_is_not_a_clean_run(self) -> None:
        empty = self.run_audit()
        self.assertEqual(empty.returncode, 2)
        self.assertIn("read nothing", empty.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "session.jsonl").write_text(json.dumps({"type": "user"}) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(Path(audit.__file__)), "--root", ROOT, "--transcripts", str(directory)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 2)

    def test_without_a_project_directory_the_transcripts_are_those_of_the_root(self) -> None:
        root = "/private/tmp/claude-0/no-such-run-for-this-test"
        result = subprocess.run(
            [sys.executable, "-B", str(Path(audit.__file__)), "--root", root],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("private-tmp-claude-0-no-such-run-for-this-test", result.stderr + result.stdout)
        self.assertNotIn(HOME, result.stdout + result.stderr)

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
