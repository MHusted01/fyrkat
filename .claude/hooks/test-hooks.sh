#!/usr/bin/env bash
# Tests for the Claude Code hooks in this directory. Run by `cargo xtask check`.
# Needs bash, git and jq.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

passed=0
failed=0

# expect <allow|deny> <description> <hook> <json> [project_dir]
expect() {
  local want=$1 name=$2 hook=$3 json=$4 project=${5:-$tmp/feature}
  local code=0
  CLAUDE_PROJECT_DIR=$project "$here/$hook" <<<"$json" >/dev/null 2>&1 || code=$?
  local got=allow
  [[ $code -eq 2 ]] && got=deny
  if [[ $code -ne 0 && $code -ne 2 ]]; then got="error($code)"; fi
  if [[ "$got" == "$want" ]]; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
    echo "FAIL: $name (wanted $want, got $got)"
  fi
}

bash_json() { jq -n --arg c "$1" '{tool_name: "Bash", tool_input: {command: $c}}'; }
edit_json() { jq -n --arg f "$1" --arg s "$2" '{tool_name: "Edit", tool_input: {file_path: $f, new_string: $s}}'; }
write_json() { jq -n --arg f "$1" --arg s "$2" '{tool_name: "Write", tool_input: {file_path: $f, content: $s}}'; }

# Fixtures: one repo on a feature branch, one on main.
for pair in "feature:feature/x" "onmain:main"; do
  dir=$tmp/${pair%%:*}
  git init -q -b "${pair#*:}" "$dir"
done

push='block-main-push.sh'
expect allow "non-git command" $push "$(bash_json 'ls -la')"
expect allow "git status" $push "$(bash_json 'git status')"
expect allow "push of a feature branch" $push "$(bash_json 'git push -u origin m0/foundation')"
expect allow "commit message mentioning main" $push "$(bash_json 'git commit -m "docs: explain push to main"')"
expect deny "push to main" $push "$(bash_json 'git push origin main')"
expect deny "push HEAD to main" $push "$(bash_json 'git push origin HEAD:main')"
expect deny "push to master with -C" $push "$(bash_json 'git -C . push origin master')"
expect deny "force push" $push "$(bash_json 'git push --force origin feat')"
expect deny "short force push" $push "$(bash_json 'git push -f origin feat')"
expect deny "force with lease" $push "$(bash_json 'git push --force-with-lease origin feat')"
expect deny "plus refspec force" $push "$(bash_json 'git push origin +feat:feat')"
expect deny "bare push while on main" $push "$(bash_json 'git push')" "$tmp/onmain"
expect allow "bare push while on a feature branch" $push "$(bash_json 'git push')"

mkdir -p "$tmp/docs/adr"
adr=$tmp/docs/adr
printf '# ADR 0001\n\n- **Status:** Accepted\n' >"$adr/0001-accepted.md"
printf '# ADR 0002\n\n- **Status:** Proposed\n' >"$adr/0002-proposed.md"
printf '# ADR 0000\n\n- **Status:** Accepted\n' >"$adr/0000-template.md"
printf '# ADRs\n' >"$adr/README.md"

protect='protect-adr.sh'
expect deny "edit of an accepted ADR" $protect "$(edit_json "$adr/0001-accepted.md" 'text')"
expect allow "edit of a proposed ADR" $protect "$(edit_json "$adr/0002-proposed.md" 'new text')"
expect deny "accepting a proposed ADR (Edit)" $protect "$(edit_json "$adr/0002-proposed.md" '- **Status:** Accepted')"
expect deny "provisional status (Write)" $protect "$(write_json "$adr/0003-new.md" '- **Status:** Provisional')"
expect allow "new proposed ADR (Write)" $protect "$(write_json "$adr/0003-new.md" '- **Status:** Proposed')"
expect allow "ADR README" $protect "$(edit_json "$adr/README.md" '- **Status:** Accepted')"
expect allow "ADR template" $protect "$(edit_json "$adr/0000-template.md" 'x')"
expect allow "unrelated file" $protect "$(edit_json "$tmp/src/main.rs" 'fn main() {}')"
expect allow "tool call without a file path" $protect '{"tool_name":"Bash","tool_input":{"command":"ls"}}'

echo "hook tests: $passed passed, $failed failed"
[[ $failed -eq 0 ]]
