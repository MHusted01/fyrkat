#!/usr/bin/env bash
# PreToolUse hook for Edit, Write, MultiEdit and Bash. Two rules from docs/adr/README.md:
#   1. An Accepted ADR is not edited. Supersede it with a new ADR instead.
#   2. Only the owner moves an ADR to Accepted or Provisional, so agents may not write
#      those statuses.
# For file edits it applies the change to the current file in memory and compares the ADR's
# Status lines before and after, so a narrow edit that rewrites only the status is caught.
# Bash commands that write to a numbered ADR are refused: use the Edit tool, which is checked.
# Exit 2 blocks the call.
#
# This is a guard against mistakes, not a security boundary: a script, an editor or another
# program can still change a file. Git review and GitHub branch protection are the
# authoritative controls for what reaches main.
set -euo pipefail

input=$(cat)

block() {
  echo "BLOCKED: $1" >&2
  exit 2
}

# A path to a numbered ADR, but not the template (0000) or the README index.
is_numbered_adr() {
  case "$1" in
    */docs/adr/0000-*) return 1 ;;
    */docs/adr/[0-9][0-9][0-9][0-9]-*.md) return 0 ;;
    *) return 1 ;;
  esac
}

# Bash: refuse commands that write to a numbered ADR.
command=$(jq -r '.tool_input.command // empty' <<<"$input")
if [[ -n "$command" ]]; then
  adr_path='docs/adr/[0-9]{4}-'
  in_place='(^|[^[:alnum:]_])(sed|perl|ruby)[^|;&]*[[:space:]]-[A-Za-z]*i'
  writers='(^|[^[:alnum:]_])(tee|mv|cp|rm|truncate|install|dd)([[:space:]]|$)'
  redirect=">>?[[:space:]]*[^[:space:]]*${adr_path}"
  if grep -Eq "$adr_path" <<<"$command" &&
    { grep -Eq "$in_place" <<<"$command" || grep -Eq "$writers" <<<"$command" ||
      grep -Eq "$redirect" <<<"$command"; }; then
    block "A shell command writes to a numbered ADR. Use the Edit tool, which checks ADR status rules."
  fi
  exit 0
fi

file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ -n "$file" ]] || exit 0

case "$file" in
  /*) ;;
  *) file="${CLAUDE_PROJECT_DIR:-.}/$file" ;;
esac
is_numbered_adr "$file" || exit 0

current=""
if [[ -f "$file" ]]; then
  current=$(<"$file")
fi

# The file as it would be after the tool call.
result=$(jq -r --arg cur "$current" '
  def apply($old; $new; $all):
    if ($old | length) == 0 then . + "\n" + $new
    else
      (split($old)) as $parts
      | if ($parts | length) == 1 then .
        elif $all then ($parts | join($new))
        else $parts[0] + $new + ($parts[1:] | join($old))
        end
    end;
  .tool_input as $in
  | if $in.content != null then $in.content
    elif $in.edits != null then
      reduce $in.edits[] as $e ($cur;
        apply($e.old_string // ""; $e.new_string // ""; $e.replace_all // false))
    elif $in.new_string != null then
      $cur | apply($in.old_string // ""; $in.new_string; $in.replace_all // false)
    else $cur
    end
' <<<"$input")

status_lines() { grep -Ei '^[[:space:]>*-]*\**status\**:?\**[[:space:]]' || true; }
owner_status='[Ss]tatus[*:]*[[:space:]]*(Part [A-Za-z0-9]+:[[:space:]]*)?(Accepted|Provisional)'

before=$(status_lines <<<"$current")
after=$(status_lines <<<"$result")

if grep -Eq '[Ss]tatus[*:]*[[:space:]]*(Part [A-Za-z0-9]+:[[:space:]]*)?Accepted' <<<"$before"; then
  block "$file is Accepted. Do not edit it; write a new ADR that supersedes it. Only the owner changes accepted ADRs."
fi

if [[ "$before" != "$after" ]] && grep -Eq "$owner_status" <<<"$after"; then
  block "Only the owner moves an ADR to Accepted or Provisional, or edits the status of one. Draft it as Proposed."
fi
exit 0
