#!/usr/bin/env bash
# PreToolUse hook for Edit|Write. Two rules from docs/adr/README.md:
#   1. An Accepted ADR is not edited. Supersede it with a new ADR instead.
#   2. Only the owner moves an ADR to Accepted or Provisional, so agents may not write
#      those statuses.
# Exit 2 blocks the call. A Bash command such as sed can still edit a file, so this guards
# against mistakes and is not a security boundary.
set -euo pipefail

input=$(cat)
file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ -n "$file" ]] || exit 0

case "$file" in
  /*) ;;
  *) file="${CLAUDE_PROJECT_DIR:-.}/$file" ;;
esac

# Numbered ADR files only. The README index and the template are not decisions.
case "$file" in
  */docs/adr/[0-9][0-9][0-9][0-9]-*.md) ;;
  *) exit 0 ;;
esac
case "$file" in
  */docs/adr/0000-*) exit 0 ;;
esac

block() {
  echo "BLOCKED: $1" >&2
  exit 2
}

if [[ -f "$file" ]] && grep -Eq '^- \*\*Status:\*\* *Accepted' "$file"; then
  block "$file is Accepted. Do not edit it; write a new ADR that supersedes it. Only the owner changes accepted ADRs."
fi

new=$(jq -r '.tool_input.content // .tool_input.new_string // empty' <<<"$input")
if grep -Eq '\*\*Status:\*\* *(Accepted|Provisional)' <<<"$new"; then
  block "Only the owner moves an ADR to Accepted or Provisional. Draft it as Proposed."
fi
exit 0
