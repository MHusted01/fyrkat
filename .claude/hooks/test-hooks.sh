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
edit_old_json() { jq -n --arg f "$1" --arg o "$2" --arg s "$3" --argjson a "${4:-false}" '{tool_name: "Edit", tool_input: {file_path: $f, old_string: $o, new_string: $s, replace_all: $a}}'; }
multi_json() { jq -n --arg f "$1" --arg o "$2" --arg s "$3" '{tool_name: "MultiEdit", tool_input: {file_path: $f, edits: [{old_string: "unrelated", new_string: "unrelated"}, {old_string: $o, new_string: $s}]}}'; }
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
expect deny "double-quoted HEAD:main" $push "$(bash_json 'git push origin "HEAD:main"')"
expect deny "single-quoted main" $push "$(bash_json "git push origin 'main'")"
expect deny "refspec followed by a semicolon" $push "$(bash_json 'git push origin HEAD:main; echo done')"
expect deny "full ref name" $push "$(bash_json 'git push origin HEAD:refs/heads/main')"
expect deny "delete main" $push "$(bash_json 'git push origin :main')"
expect deny "push every branch" $push "$(bash_json 'git push --all origin')"
expect deny "mirror push" $push "$(bash_json 'git push --mirror origin')"
# shellcheck disable=SC2016 # the $( is meant to reach the hook literally
expect deny "push inside a command substitution" $push "$(bash_json 'echo $(git push origin main)')"
expect deny "push after another command" $push "$(bash_json 'cargo xtask check && git push origin main')"
expect deny "push with a global option" $push "$(bash_json 'git -c push.default=current push origin main')"
expect deny "push with an env prefix" $push "$(bash_json 'GIT_TRACE=1 git push origin master')"
expect deny "clustered force flag" $push "$(bash_json 'git push -uf origin feat')"
expect allow "branch name containing main" $push "$(bash_json 'git push origin feature/main')"
expect allow "push of main to another branch" $push "$(bash_json 'git push origin main:scratch')"
expect allow "gh pr create with --base main" $push "$(bash_json 'gh pr create --base main --head m0/foundation')"
expect allow "git log mentioning push" $push "$(bash_json 'git log --grep="push to main"')"
expect allow "echo about a push" $push "$(bash_json 'echo git push origin main')"
expect allow "git commit with main in the message" $push "$(bash_json 'git commit -m "fix: push to main is blocked" && git status')"

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
# Narrow and multiline edits that rewrite only the status.
printf '# ADR 0004\n\n- **Status:** Proposed (working hypothesis)\n- **Date:** 2026-11-07\n\nBody text.\n' >"$adr/0004-narrow.md"
expect deny "narrow edit of only the status words" $protect "$(edit_old_json "$adr/0004-narrow.md" 'Proposed (working hypothesis)' 'Accepted')"
expect deny "narrow edit to Provisional" $protect "$(edit_old_json "$adr/0004-narrow.md" 'Proposed' 'Provisional')"
expect deny "multiline edit that includes the status" $protect "$(edit_old_json "$adr/0004-narrow.md" $'Proposed (working hypothesis)\n- **Date:**' $'Accepted\n- **Date:**')"
expect deny "replace_all that rewrites the status" $protect "$(edit_old_json "$adr/0004-narrow.md" 'Proposed' 'Accepted' true)"
expect deny "MultiEdit that rewrites the status" $protect "$(multi_json "$adr/0004-narrow.md" 'Proposed' 'Accepted')"
expect allow "narrow edit of the body" $protect "$(edit_old_json "$adr/0004-narrow.md" 'Body text.' 'Revised body text.')"
expect allow "edit that keeps the status line" $protect "$(edit_old_json "$adr/0004-narrow.md" '- **Date:** 2026-11-07' '- **Date:** 2026-11-08')"
expect allow "MultiEdit of the body" $protect "$(multi_json "$adr/0004-narrow.md" 'Body text.' 'Other text.')"
expect allow "downgrading the status to Proposed" $protect "$(edit_old_json "$adr/0004-narrow.md" 'Proposed (working hypothesis)' 'Proposed')"
expect deny "Write that rewrites the status of an existing ADR" $protect "$(write_json "$adr/0004-narrow.md" $'# ADR 0004\n\n- **Status:** Accepted\n')"
expect allow "Write that keeps the status of an existing ADR" $protect "$(write_json "$adr/0004-narrow.md" $'# ADR 0004\n\n- **Status:** Proposed (working hypothesis)\n- **Date:** 2026-11-07\n')"

# Provisional ADRs may be edited, but their status line may not change.
printf '# ADR 0005\n\n- **Status:** Provisional. The owner accepted this at Gate 1.\n\nBody.\n' >"$adr/0005-provisional.md"
printf '# ADR 0006\n\n- **Status:** Part A: Provisional. Part B: Withdrawn.\n\nBody.\n' >"$adr/0006-parts.md"
printf '# ADR 0007\n\n- **Status:** Part A: Accepted. Part B: Withdrawn.\n\nBody.\n' >"$adr/0007-parts-accepted.md"
expect allow "body edit of a Provisional ADR" $protect "$(edit_old_json "$adr/0005-provisional.md" 'Body.' 'New body.')"
expect deny "status edit of a Provisional ADR" $protect "$(edit_old_json "$adr/0005-provisional.md" 'at Gate 1' 'at Gate 2')"
expect allow "body edit of a Part A Provisional ADR" $protect "$(edit_old_json "$adr/0006-parts.md" 'Body.' 'New body.')"
expect deny "promoting Part A to Accepted" $protect "$(edit_old_json "$adr/0006-parts.md" 'Part A: Provisional' 'Part A: Accepted')"
expect deny "any edit of a Part A Accepted ADR" $protect "$(edit_old_json "$adr/0007-parts-accepted.md" 'Body.' 'New body.')"

# Shell commands that write to a numbered ADR are refused. Reads and other paths are not.
expect deny "sed -i on a numbered ADR" $protect "$(bash_json "sed -i '' 's/Proposed/Accepted/' docs/adr/0004-kernel-foundation.md")"
expect deny "perl -pi on a numbered ADR" $protect "$(bash_json "perl -pi -e 's/Proposed/Accepted/' docs/adr/0004-kernel-foundation.md")"
expect deny "redirect into a numbered ADR" $protect "$(bash_json 'echo "- **Status:** Accepted" >> docs/adr/0004-kernel-foundation.md')"
expect deny "tee into a numbered ADR" $protect "$(bash_json 'echo x | tee docs/adr/0004-kernel-foundation.md')"
expect deny "mv over a numbered ADR" $protect "$(bash_json 'mv /tmp/x.md docs/adr/0004-kernel-foundation.md')"
expect allow "reading a numbered ADR" $protect "$(bash_json 'grep Status docs/adr/0004-kernel-foundation.md')"
expect allow "sed -i on another file" $protect "$(bash_json "sed -i '' 's/a/b/' docs/roadmap.md")"
expect allow "git add of a numbered ADR" $protect "$(bash_json 'git add docs/adr/0004-kernel-foundation.md')"
expect allow "tool call without a file path" $protect '{"tool_name":"Bash","tool_input":{"command":"ls"}}'

echo "hook tests: $passed passed, $failed failed"
[[ $failed -eq 0 ]]
