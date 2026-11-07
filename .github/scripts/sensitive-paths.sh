#!/usr/bin/env bash
# Print a Markdown list of security-sensitive paths changed between two commits.
# Usage: sensitive-paths.sh <base-sha> <head-sha>
# Used by the sensitive-paths job in .github/workflows/ci.yml for the job summary.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <base-sha> <head-sha>" >&2
  exit 64
fi
base=$1
head=$2

# One extended regular expression; keep in sync with CODEOWNERS and AGENTS.md.
sensitive='^(\.github/|\.claude/|docs/adr/|deny\.toml$|rust-toolchain\.toml$|Cargo\.lock$)'

changed=$(git diff --name-only "$base...$head")
matches=$(grep -E "$sensitive" <<<"$changed" || true)

echo "## Security-sensitive paths changed"
echo
if [[ -z "$matches" ]]; then
  echo "None."
else
  echo "These paths need owner approval (see AGENTS.md):"
  echo
  while IFS= read -r path; do
    echo "- \`$path\`"
  done <<<"$matches"
fi
