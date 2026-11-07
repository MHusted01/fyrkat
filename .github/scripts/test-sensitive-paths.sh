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
echo x >deny.toml
echo x >src/other.rs
echo x >xtask-notes.md
echo x >docs/cargo.toml.md
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
lacks 'src/other.rs'
check "ordinary source is not listed" $?
lacks 'xtask-notes.md'
check "xtask-notes.md is not mistaken for xtask/" $?
lacks 'docs/cargo.toml.md'
check "docs/cargo.toml.md is not mistaken for Cargo.toml" $?
lacks 'docs/notes.md'
check "ordinary docs are not listed" $?
has_path '.github/tick?name.md'
check "a backtick in a name cannot break the code span" $?

none=$("$script" "$head" "$head")
grep -qF 'None.' <<<"$none"
check "no change prints None." $?

code=0
"$script" >/dev/null 2>&1 || code=$?
[[ $code -eq 64 ]]
check "wrong argument count exits 64" $?

echo "sensitive-paths tests: $passed passed, $failed failed"
[[ $failed -eq 0 ]]
