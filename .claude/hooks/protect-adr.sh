#!/usr/bin/env bash
# PreToolUse hook for Edit, Write, MultiEdit and Bash. Two rules from docs/adr/README.md:
#   1. An Accepted ADR is not edited. Supersede it with a new ADR instead.
#   2. Only the owner moves an ADR to or from Accepted or Provisional, so agents may not
#      change the Status of an ADR that is, or would become, one of those.
# For file edits it applies the change to the current file in memory and compares the ADR's
# Status lines before and after, so a narrow edit that rewrites only the status is caught.
# The path is normalised (. .. // and symlinks) and matched without regard to case.
# Bash commands that match COMMON patterns for writing to the ADR directory are refused:
# use the Edit tool, which is checked. This can also block a harmless copy of an ADR.
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

shopt -s nocasematch

# Collapse ".", ".." and repeated slashes in an absolute path, without touching the disk.
normalize_path() {
  local -a parts out=()
  local part
  IFS=/ read -ra parts <<<"$1"
  for part in "${parts[@]}"; do
    case "$part" in
      '' | .) ;;
      ..) if ((${#out[@]} > 0)); then unset "out[${#out[@]}-1]"; fi ;;
      *) out+=("$part") ;;
    esac
  done
  if ((${#out[@]} == 0)); then
    printf '/'
  else
    printf '/%s' "${out[@]}"
  fi
}

# A path to a numbered ADR, but not the template (0000) or the README index.
is_numbered_adr() {
  case "$1" in
    */docs/adr/0000-*) return 1 ;;
    */docs/adr/[0-9][0-9][0-9][0-9]-*.md) return 0 ;;
    *) return 1 ;;
  esac
}

# Bash: refuse commands that write to the ADR directory by a common route.
command=$(jq -r '.tool_input.command // empty' <<<"$input")
if [[ -n "$command" ]]; then
  adr_dir='docs/adr'
  in_place='(^|[^[:alnum:]_])(sed|perl|ruby)[^|;&]*[[:space:]](-[A-Za-z0-9]*i|--in-place)'
  writers='(^|[^[:alnum:]_])(tee|mv|cp|rm|truncate|install|dd)([[:space:]]|$)'
  redirect='>[>|]?[[:space:]]*[^[:space:]]*docs/adr'
  if grep -Eiq "$adr_dir" <<<"$command" &&
    { grep -Eiq "$in_place" <<<"$command" || grep -Eiq "$writers" <<<"$command" ||
      grep -Eiq "$redirect" <<<"$command"; }; then
    block "A shell command writes to the ADR directory. Use the Edit tool, which checks ADR status rules."
  fi
  exit 0
fi

file=$(jq -r '.tool_input.file_path // empty' <<<"$input")
[[ -n "$file" ]] || exit 0

case "$file" in
  /*) ;;
  *) file="${CLAUDE_PROJECT_DIR:-.}/$file" ;;
esac
file=$(normalize_path "$file")
# Follow a symlink to the file it really edits.
if [[ -e "$file" ]] && command -v realpath >/dev/null 2>&1; then
  file=$(realpath "$file" 2>/dev/null || printf '%s' "$file")
fi
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

# A Status value that starts with Accepted or Provisional, optionally after "Part X:" and
# with optional bold markers, in any letter case.
accepted='status[*:]*[[:space:]]*\**[[:space:]]*(Part [A-Za-z0-9]+:[[:space:]]*)?\**Accepted'
owner_status='status[*:]*[[:space:]]*\**[[:space:]]*(Part [A-Za-z0-9]+:[[:space:]]*)?\**(Accepted|Provisional)'

before=$(status_lines <<<"$current")
after=$(status_lines <<<"$result")

if grep -Eiq "$accepted" <<<"$before"; then
  block "$file is Accepted. Do not edit it; write a new ADR that supersedes it. Only the owner changes accepted ADRs."
fi

if [[ "$before" != "$after" ]] &&
  { grep -Eiq "$owner_status" <<<"$before" || grep -Eiq "$owner_status" <<<"$after"; }; then
  block "Only the owner moves an ADR to or from Accepted or Provisional, or edits the status of one. Draft it as Proposed."
fi
exit 0
