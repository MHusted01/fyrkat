#!/usr/bin/env bash
# Tests for review-packet.sh. Run by `cargo xtask check`. Needs bash and git.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
script=$here/review-packet.sh
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

passed=0
failed=0

expect() { # expect <description> <command...>: the command must succeed
  local description=$1
  shift
  if "$@"; then
    passed=$((passed + 1))
  else
    failed=$((failed + 1))
    echo "FAIL: $description"
  fi
}
depth_is() { [[ $(grep -m1 -o 'Depth: [a-z]*' <<<"$2" || true) == "Depth: $1" ]]; }
has() { grep -q -F -- "$1" <<<"$2"; }
exits() { # exits <status> <command...>
  local want=$1 status=0
  shift
  "$@" >/dev/null 2>&1 || status=$?
  [[ $status -eq $want ]]
}

repo=$tmp/repo
git init -q -b main "$repo"
cd "$repo"
git config user.name test
git config user.email test@example.invalid
git config commit.gpgsign false

mkdir -p docs/development docs/research spikes/sel4-feasibility/crates/t/src
echo base >docs/development/SESSION_HANDOFF.md
echo base >docs/notes.md
echo base >docs/research/sel4-spike-plan.md
echo "fn main() {}" >spikes/sel4-feasibility/crates/t/src/mmio.rs
echo 'SOURCES = ["crates/t/src/mmio.rs"]' >spikes/sel4-feasibility/verify_t.py
echo base >spikes/sel4-feasibility/helper.py
git add -A
git commit -q -m base
base=$(git rev-parse HEAD)

# commit_on <branch> : commit the working tree on a fresh branch from base and print its SHA.
commit_on() {
  git checkout -q -b "$1" "$base"
  shift
  "$@"
  git add -A
  git commit -q -m change
  git rev-parse HEAD
}

# 1. Handoff only: standard by default, none only when the author asserts records-only.
edit_handoff() { echo "next: nothing" >>docs/development/SESSION_HANDOFF.md; }
handoff=$(commit_on handoff edit_handoff)
out=$(bash "$script" "$base" "$handoff")
expect "a records change is standard by default" depth_is standard "$out"
out=$(bash "$script" "$base" "$handoff" --records-only)
expect "records-only is accepted for Markdown with no label" depth_is none "$out"

# 2. A document that adds an evidence label: records-only is refused and the claim is listed.
edit_claim() { echo "The device was refused. [Measured: log 3]" >>docs/notes.md; }
claim=$(commit_on claim edit_claim)
out=$(bash "$script" "$base" "$claim" --records-only)
expect "records-only is refused when a label is added" depth_is standard "$out"
expect "the refusal is stated" has 'records-only` was refused' "$out"
expect "the added claim is listed with its line" has 'docs/notes.md:2: The device was refused' "$out"

# 3. Compiled source is deep, and cannot be lowered.
edit_rust() { echo "// change" >>spikes/sel4-feasibility/crates/t/src/mmio.rs; }
rust=$(commit_on rust edit_rust)
out=$(bash "$script" "$base" "$rust" --records-only)
expect "compiled source is deep even with records-only" depth_is deep "$out"
expect "the compiled file is named" has 'mmio.rs` (compiled source)' "$out"
expect "a verifier that pins the file is named" has 'mmio.rs` is named by: spikes/sel4-feasibility/verify_t.py' "$out"

# 4. A security-sensitive path is deep.
edit_ci() { mkdir -p .github/workflows; echo x >.github/workflows/ci.yml; }
ci=$(commit_on ci edit_ci)
expect "a sensitive path is deep" depth_is deep "$(bash "$script" "$base" "$ci")"

# 5. Evidence tooling is deep; other Python is not.
edit_verifier() { echo "# change" >>spikes/sel4-feasibility/verify_t.py; }
verifier=$(commit_on verifier edit_verifier)
expect "a verifier is deep" depth_is deep "$(bash "$script" "$base" "$verifier")"
edit_helper() { echo "# change" >>spikes/sel4-feasibility/helper.py; }
helper=$(commit_on helper edit_helper)
expect "other tooling is standard" depth_is standard "$(bash "$script" "$base" "$helper")"

# 6. The plan's criteria are deep. The author can raise any change to deep.
edit_plan() { echo "criterion" >>docs/research/sel4-spike-plan.md; }
plan=$(commit_on plan edit_plan)
expect "the spike plan is deep" depth_is deep "$(bash "$script" "$base" "$plan")"
expect "--deep raises the depth" depth_is deep "$(bash "$script" "$base" "$helper" --deep)"

# 7. A cited plan section is listed.
edit_cite() { echo "See [x](research/sel4-spike-plan.md#decision-rules)." >>docs/notes.md; }
cite=$(commit_on cite edit_cite)
expect "a cited plan section is listed" has 'sel4-spike-plan.md#decision-rules' "$(bash "$script" "$base" "$cite")"

# 8. A hostile file name cannot break the Markdown.
edit_hostile() { echo x >'spikes/a`b.rs'; }
hostile=$(commit_on hostile edit_hostile)
out=$(bash "$script" "$base" "$hostile")
expect "a backtick in a file name is neutralized" has 'spikes/a?b.rs` (compiled source)' "$out"

# 9. Bad arguments.
expect "a missing argument exits 64" exits 64 bash "$script" "$base"
expect "an unknown flag exits 64" exits 64 bash "$script" "$base" "$helper" --lower
expect "an unknown commit exits 65" exits 65 bash "$script" "$base" 0000000000000000000000000000000000000000

echo "review-packet tests: $passed passed, $failed failed"
[[ $failed -eq 0 ]]
