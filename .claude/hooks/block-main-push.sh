#!/usr/bin/env bash
# PreToolUse hook for Bash. Refuses git pushes to main or master, and force pushes.
# Exit 2 blocks the call and shows stderr to Claude. This is a guard against mistakes, not
# a security boundary: a shell command can always be written to avoid a pattern. The
# permission deny rules in .claude/settings.json and GitHub branch protection back it up.
set -euo pipefail

input=$(cat)
command=$(jq -r '.tool_input.command // empty' <<<"$input")

# Match `git push`, including `git -C dir push` and `git -c key=value push`.
if ! grep -Eq '(^|[^[:alnum:]_-])git([[:space:]].*)?[[:space:]]push([[:space:]]|$)' <<<"$command"; then
  exit 0
fi

block() {
  echo "BLOCKED: $1 Pushing to main or force pushing needs the owner's approval; ask the owner." >&2
  exit 2
}

if grep -Eq '(^|[[:space:]])(--force|--force-with-lease(=[^[:space:]]*)?|-[A-Za-z]*f[A-Za-z]*|\+[^[:space:]]+)([[:space:]]|$)' <<<"$command"; then
  block "Force pushes are not allowed."
fi

if grep -Eq '(^|[[:space:]:+])(refs/heads/)?(main|master)([[:space:]]|$)' <<<"$command"; then
  block "This push targets main."
fi

branch=$(git -C "${CLAUDE_PROJECT_DIR:-.}" symbolic-ref --short -q HEAD || true)
if [[ "$branch" == "main" || "$branch" == "master" ]]; then
  block "The current branch is $branch."
fi
exit 0
