#!/usr/bin/env bash
# Print a Markdown list of security-sensitive paths changed between two commits.
# Usage: sensitive-paths.sh <base-sha> <head-sha>
# Used by the sensitive-paths job in .github/workflows/ci.yml for the job summary, and by
# review-packet.sh.
#
# This is a notice to the reviewer, not an access control. It cannot stop a change, and the
# workflow that runs it comes from the pull request. Review by the owner and branch
# protection on main are the controls. See docs/standards/engineering.md.
#
# It fails closed: if either commit is unknown, or the two share no history, it prints nothing
# and exits with an error, so that a mistyped name is never reported as "None."
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <base-sha> <head-sha>" >&2
  exit 64
fi
# Resolve both names to commits before they reach any other Git command. A name that is not a
# commit, including one that looks like an option, stops here.
base=$(git rev-parse --verify --quiet --end-of-options "$1^{commit}") || { echo "unknown commit: $1" >&2; exit 65; }
head=$(git rev-parse --verify --quiet --end-of-options "$2^{commit}") || { echo "unknown commit: $2" >&2; exit 65; }
start=$(git merge-base "$base" "$head") || { echo "the commits share no history" >&2; exit 65; }

# One extended regular expression. Keep in sync with CODEOWNERS, AGENTS.md, CONTRIBUTING.md,
# docs/standards/engineering.md and .github/pull_request_template.md.
sensitive='^(\.github/|docs/adr/|xtask/|deny\.toml$|docs/development/workflow\.md$)|(^|/)(\.claude/|\.codex/|\.agents/|\.cargo/|rust-toolchain(\.toml)?$|\.mcp\.json$|AGENTS\.md$|AGENTS\.override\.md$|CLAUDE\.md$|build\.rs$|Cargo\.(lock|toml)$)'
# On a filesystem that ignores case, claude.md is CLAUDE.md. Match without regard to case.
shopt -s nocasematch

# The name list goes through a file because a failure inside a process substitution would go
# unseen. -z keeps non-ASCII names and names with spaces intact. --no-renames lists both the
# old and the new path, so moving a file out of a sensitive directory still shows up.
names=$(mktemp)
trap 'rm -f "$names"' EXIT
# --ignore-submodules=none: a submodule at a sensitive path is listed whatever the user's
# settings or a .gitmodules file say.
git -c core.quotePath=false diff --no-color --no-ext-diff --no-renames --ignore-submodules=none \
  --name-only -z "$start" "$head" >"$names"
matches=()
while IFS= read -r -d '' path; do
  if [[ "$path" =~ $sensitive ]]; then
    matches+=("$path")
  fi
done <"$names"

echo "## Security-sensitive paths changed"
echo
if [[ ${#matches[@]} -eq 0 ]]; then
  echo "None."
else
  echo "These paths need owner approval (see AGENTS.md):"
  echo
  for path in "${matches[@]}"; do
    # Keep a hostile file name from breaking the Markdown code span or the list.
    safe=${path//[$'\n\r`']/?}
    echo "- \`$safe\`"
  done
fi
