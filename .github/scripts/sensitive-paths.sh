#!/usr/bin/env bash
# Print a Markdown list of security-sensitive paths changed between two commits.
# Usage: sensitive-paths.sh <base-sha> <head-sha>
# Used by the sensitive-paths job in .github/workflows/ci.yml for the job summary.
#
# This is a notice to the reviewer, not an access control. It cannot stop a change, and the
# workflow that runs it comes from the pull request. Review by the owner and branch
# protection on main are the controls. See docs/standards/engineering.md.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <base-sha> <head-sha>" >&2
  exit 64
fi
base=$1
head=$2

# One extended regular expression. Keep in sync with CODEOWNERS, AGENTS.md, CONTRIBUTING.md,
# docs/standards/engineering.md and .github/pull_request_template.md.
sensitive='^(\.github/|\.claude/|\.cargo/|docs/adr/|xtask/|AGENTS\.md$|CLAUDE\.md$|deny\.toml$|rust-toolchain\.toml$)|(^|/)Cargo\.(lock|toml)$'

# -z keeps non-ASCII names and names with spaces intact. --no-renames lists both the old
# and the new path, so moving a file out of a sensitive directory still shows up.
matches=()
while IFS= read -r -d '' path; do
  if [[ "$path" =~ $sensitive ]]; then
    matches+=("$path")
  fi
done < <(git -c core.quotePath=false diff --no-renames --name-only -z "$base...$head")

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
