#!/usr/bin/env bash
# Tests for sensitive-paths.sh. Run by `cargo xtask check`. Needs bash and git.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
script=$here/sensitive-paths.sh
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

passed=0
failed=0

check() { # check <description> <condition-exit-code>
  if [[ $2 -eq 0 ]]; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
    echo "FAIL: $1"
  fi
}

repo=$tmp/repo
git init -q -b main "$repo"
cd "$repo"
git config user.name test
git config user.email test@example.invalid
git config commit.gpgsign false

mkdir -p docs/adr docs/notes src
echo base >src/lib.rs
echo base >docs/adr/0001-moved-out.md
echo base >docs/notes.md
git add -A
git commit -q -m base
base=$(git rev-parse HEAD)

mkdir -p .github/workflows .cargo xtask/src spikes/x crates/a
echo x >".github/workflows/évil.yml"
echo x >.cargo/config.toml
echo x >xtask/src/check.rs
echo x >spikes/x/Cargo.lock
echo x >crates/a/Cargo.toml
echo x >docs/adr/0005-new.md
echo x >"docs/adr/with space.md"
echo x >AGENTS.md
mkdir -p .claude spikes/y/.cargo sub
echo x >.claude/settings.json
echo x >CLAUDE.md
echo x >rust-toolchain.toml
echo x >Cargo.lock
echo x >.mcp.json
echo x >spikes/y/.cargo/config.toml
echo x >spikes/y/rust-toolchain.toml
echo x >spikes/y/rust-toolchain
echo x >crates/a/build.rs
echo x >sub/CLAUDE.md
echo x >docs/my-CLAUDE.md
echo x >deny.toml
echo x >src/other.rs
echo x >xtask-notes.md
echo x >docs/cargo.toml.md
mkdir -p docs/development sub/docs/development
echo x >docs/development/workflow.md
echo x >docs/development/workflow-notes.md
echo x >sub/docs/development/workflow.md
mkdir -p .codex/hooks sub/.agents/skills/x lower
echo x >.codex/hooks/pre.sh
echo x >sub/.agents/skills/x/SKILL.md
echo x >AGENTS.override.md
echo x >lower/claude.md
echo x >docs/agents-notes.md
printf 'x' >".github/tick\`name.md"
git mv docs/adr/0001-moved-out.md docs/notes/0001-moved-out.md
echo changed >docs/notes.md
git add -A
git commit -q -m change
head=$(git rev-parse HEAD)

out=$("$script" "$base" "$head")

has() { grep -qF -- "$1" <<<"$out"; }
has_path() { has "\`$1\`"; }
lacks() { ! grep -qF -- "$1" <<<"$out"; }

has_path '.github/workflows/évil.yml'
check "non-ASCII path under .github/" $?
has_path '.cargo/config.toml'
check ".cargo/ is listed" $?
has_path 'xtask/src/check.rs'
check "xtask/ is listed" $?
has_path 'spikes/x/Cargo.lock'
check "a nested Cargo.lock is listed" $?
has_path 'crates/a/Cargo.toml'
check "a crate Cargo.toml is listed" $?
has_path 'docs/adr/0005-new.md'
check "a new ADR is listed" $?
has_path 'docs/adr/with space.md'
check "a path with a space is listed" $?
has_path 'docs/adr/0001-moved-out.md'
check "a file moved out of docs/adr/ is still listed" $?
has_path 'AGENTS.md'
check "AGENTS.md is listed" $?
has_path 'deny.toml'
check "deny.toml is listed" $?
has_path '.claude/settings.json'
check ".claude/ is listed" $?
has_path 'CLAUDE.md'
check "root CLAUDE.md is listed" $?
has_path 'rust-toolchain.toml'
check "root rust-toolchain.toml is listed" $?
has_path 'Cargo.lock'
check "root Cargo.lock is listed" $?
has_path '.mcp.json'
check ".mcp.json is listed" $?
has_path 'spikes/y/.cargo/config.toml'
check "a nested .cargo/ is listed" $?
has_path 'spikes/y/rust-toolchain.toml'
check "a nested rust-toolchain.toml is listed" $?
has_path 'spikes/y/rust-toolchain'
check "a legacy rust-toolchain file is listed" $?
has_path 'crates/a/build.rs'
check "build.rs is listed" $?
has_path 'sub/CLAUDE.md'
check "a nested CLAUDE.md is listed" $?
lacks 'docs/my-CLAUDE.md'
check "my-CLAUDE.md is not mistaken for CLAUDE.md" $?
lacks 'src/other.rs'
check "ordinary source is not listed" $?
lacks 'xtask-notes.md'
check "xtask-notes.md is not mistaken for xtask/" $?
lacks 'docs/cargo.toml.md'
check "docs/cargo.toml.md is not mistaken for Cargo.toml" $?
lacks 'docs/notes.md'
check "ordinary docs are not listed" $?
has_path 'docs/development/workflow.md'
check "the workflow document is listed" $?
lacks 'docs/development/workflow-notes.md'
check "workflow-notes.md is not mistaken for workflow.md" $?
lacks 'sub/docs/development/workflow.md'
check "only the root workflow document is listed" $?
has_path '.codex/hooks/pre.sh'
check ".codex/ is listed" $?
has_path 'sub/.agents/skills/x/SKILL.md'
check "a nested .agents/ is listed" $?
has_path 'AGENTS.override.md'
check "AGENTS.override.md is listed" $?
has_path 'lower/claude.md'
check "claude.md in another case is listed" $?
lacks 'docs/agents-notes.md'
check "agents-notes.md is not mistaken for an agent file" $?
has_path '.github/tick?name.md'
check "a backtick in a name cannot break the code span" $?

none=$("$script" "$head" "$head")
grep -qF 'None.' <<<"$none"
check "no change prints None." $?

# assert <description> <command...>: the command must succeed. Unlike a bare condition, a
# failure here is counted and reported, and the remaining tests still run.
assert() {
  local description=$1
  shift
  if "$@"; then check "$description" 0; else check "$description" 1; fi
}

code=0
"$script" >/dev/null 2>&1 || code=$?
assert "wrong argument count exits 64" test "$code" -eq 64

# A mistyped or hostile name must fail, and must never be reported as "None."
code=0
typo=$("$script" mian "$head" 2>"$tmp/stderr") || code=$?
assert "an unknown base exits 65" test "$code" -eq 65
assert "an unknown base prints nothing" test -z "$typo"
assert "an unknown base is named as the cause" grep -q "unknown commit: mian" "$tmp/stderr"
code=0
"$script" "$base" "--output=$tmp/written" >/dev/null 2>"$tmp/stderr" || code=$?
assert "an option in place of a commit exits 65" test "$code" -eq 65
assert "an option in place of a commit is refused as a commit name" grep -q "unknown commit: --output" "$tmp/stderr"
assert "an option in place of a commit writes no file" test -z "$(find "$tmp" -maxdepth 1 -name 'written*')"
# A submodule at a sensitive path is listed even when the user tells Git to ignore submodules.
git checkout -q -b gitlink "$head"
git update-index --add --cacheinfo 160000,1111111111111111111111111111111111111111,xtask/vendor
git commit -q -m "add a submodule"
added=$(git rev-parse HEAD)
git update-index --cacheinfo 160000,2222222222222222222222222222222222222222,xtask/vendor
git commit -q -m "move the submodule to another commit"
gitlink=$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.ignoreSubmodules GIT_CONFIG_VALUE_0=all "$script" "$added" "$(git rev-parse HEAD)")
assert "a moved submodule at a sensitive path is listed despite diff.ignoreSubmodules" grep -qF 'xtask/vendor' <<<"$gitlink"
git reset -q --hard

# Run from a subdirectory with diff.relative set, the whole repository is still listed.
relative=$(cd docs && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.relative GIT_CONFIG_VALUE_0=true "$script" "$base" "$head")
assert "diff.relative from a subdirectory does not hide AGENTS.md" grep -qxF -- "- \`AGENTS.md\`" <<<"$relative"
if [[ -x /bin/bash ]]; then
  system=$(/bin/bash "$script" "$base" "$head")
  assert "a backtick in a name is neutralized under the system bash too" grep -qF '.github/tick?name.md' <<<"$system"
fi

git checkout -q --orphan unrelated
git rm -q -rf . >/dev/null
echo x >AGENTS.md
git add -A
git commit -q -m unrelated
code=0
unrelated=$("$script" "$base" "$(git rev-parse HEAD)" 2>/dev/null) || code=$?
assert "commits with no shared history exit 65" test "$code" -eq 65
assert "commits with no shared history print nothing" test -z "$unrelated"

echo "sensitive-paths tests: $passed passed, $failed failed"
[[ $failed -eq 0 ]]
