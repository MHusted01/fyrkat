#!/usr/bin/env bash
# Tests for review-packet.sh. Run by `cargo xtask check`. Needs bash and git.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
script=$here/review-packet.sh
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# The developer's own Git configuration must not change a result.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

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
lacks() { ! grep -q -F -- "$1" <<<"$2"; }
section() { awk -v title="## $1" '$0 == title { on = 1; next } /^## / { on = 0 } on' <<<"$2"; }
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

mkdir -p .github/scripts docs/development docs/research docs/sub spikes/sel4-feasibility/crates/t/src spikes/sel4-feasibility/results/E9 tools
# The base holds the review scripts under test, so the packet is "made by the base's copy".
cp "$here/review-packet.sh" "$here/sensitive-paths.sh" .github/scripts/
echo base >docs/development/SESSION_HANDOFF.md
printf 'intro\nOld claim. [Measured: log 1]\n' >docs/notes.md
echo base >docs/sub/deep.md
echo base >docs/research/sel4-spike-plan.md
echo base >docs/research/sel4-spike-amendments.md
echo "fn main() {}" >spikes/sel4-feasibility/crates/t/src/mmio.rs
echo "fn main() {}" >spikes/sel4-feasibility/crates/t/src/moved.rs
echo 'SOURCES = ["crates/t/src/mmio.rs"]' >spikes/sel4-feasibility/verify_t.py
echo "pinned: helper.py" >spikes/sel4-feasibility/results/E9/00-preflight.txt
echo base >spikes/sel4-feasibility/helper.py
echo base >spikes/sel4-feasibility/results/E9.md
echo base >tools/notes.py
git add -A
git commit -q -m base
base=$(git rev-parse HEAD)

n=0
# change <command...>: run the command on a fresh branch from base, commit, and set $head.
change() {
  n=$((n + 1))
  git checkout -q -b "case-$n" "$base"
  "$@"
  git add -A
  git commit -q --allow-empty -m change
  head=$(git rev-parse HEAD)
}
packet() { bash "$script" "$base" "$head" "$@"; }
append() { echo "$2" >>"$1"; }
create() { mkdir -p "$(dirname "$1")" && echo x >"$1"; }

# 1. Every change is reviewed: no change and no flag gives a depth below standard.
change append docs/development/SESSION_HANDOFF.md "next: nothing"
expect "the handoff alone is standard" depth_is standard "$(packet)"
change append docs/development/SESSION_HANDOFF.md "The owner authorized merging. [Measured: owner message]"
out=$(packet)
expect "a handoff that adds a claim is standard" depth_is standard "$out"
expect "a claim added to the handoff is listed" has "SESSION_HANDOFF.md:2: The owner authorized merging" "$out"
change append docs/notes.md "a typo fix"
out=$(packet)
expect "a document change is standard" depth_is standard "$out"
expect "no depth below standard is ever printed" lacks "Depth: none" "$out"
expect "there is no flag that lowers the depth" exits 64 bash "$script" "$base" "$head" --records-only
change true
expect "an empty change is standard" depth_is standard "$(packet)"

# 2. Labelled claims are listed however they are written and whatever Git is told to do.
for label in Measured Documented Inferred Speculative; do
  change append docs/notes.md "The device was refused. [$label: log 3]"
  expect "an added [$label] claim is listed with its line" has "docs/notes.md:3: The device was refused. [$label" "$(packet)"
done
change append docs/notes.md "lower case [measured] label"
expect "a label in lower case is listed" has "docs/notes.md:3: lower case [measured]" "$(packet)"
change append docs/notes.md "++ hidden [Measured] behind plus signs"
expect "a line that looks like a diff header is still listed" has "++ hidden [Measured]" "$(packet)"
change append docs/sub/deep.md "nested [Inferred] claim"
expect "a claim in a nested directory is listed" has "docs/sub/deep.md:2: nested [Inferred]" "$(packet)"
change append docs/notes.md "claim under odd settings [Measured]"
expect "forced colour does not hide a claim" has "claim under odd settings" "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=color.ui GIT_CONFIG_VALUE_0=always packet)"
expect "forced diff colour does not hide a claim" has "claim under odd settings" "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=color.diff GIT_CONFIG_VALUE_0=always packet)"
expect "an external diff program does not hide a claim" has "claim under odd settings" "$(GIT_EXTERNAL_DIFF=true packet)"
expect "running from a subdirectory does not hide a claim" has "claim under odd settings" "$(cd spikes && bash "$script" "$base" "$head")"
for variable in GIT_LITERAL_PATHSPECS GIT_GLOB_PATHSPECS GIT_NOGLOB_PATHSPECS; do
  expect "$variable does not hide a claim" has "claim under odd settings" "$(env "$variable=1" bash "$script" "$base" "$head")"
done
binary_attribute() { echo '*.md -diff' >.gitattributes; append docs/notes.md "claim in a file marked binary [Measured]"; }
change binary_attribute
expect "a no-diff attribute does not hide a claim" has "claim in a file marked binary" "$(packet)"
remove_claim() { echo intro >docs/notes.md; }
change remove_claim
out=$(packet)
expect "a removed claim is listed" has "docs/notes.md:2: Old claim. [Measured: log 1]" "$out"
expect "a removed claim is not listed as added" has "None." "$(section "Labelled claims the change adds" "$out")"
git checkout -q main
printf 'intro\n-- dashed [Inferred] claim\n' >docs/dashed.md
git add -A
git commit -q -m "a line that starts with dashes"
dashed_base=$(git rev-parse HEAD)
git checkout -q -b dashed "$dashed_base"
echo intro >docs/dashed.md
git add -A
git commit -q -m change
out=$(bash "$script" "$dashed_base" "$(git rev-parse HEAD)")
expect "a removed line that looks like a diff header is still listed" has "docs/dashed.md:2: -- dashed [Inferred] claim" "$out"
git checkout -q main
git reset -q --hard "$base"

# 3. Compiled and linked source is deep, by every extension, and a rename cannot hide it.
for extension in rs c h S s asm ld lds x cmake; do
  change create "boot/start.$extension"
  expect "a .$extension file is deep" depth_is deep "$(packet)"
done
change git mv spikes/sel4-feasibility/crates/t/src/moved.rs docs/moved.md
out=$(packet)
expect "renaming source to Markdown is still deep" depth_is deep "$out"
expect "the renamed source file is named" has 'moved.rs` (compiled or linked source)' "$out"

# 4. Spike material other than prose is deep. Spike prose is not, by path.
for file in build-e9.sh boot-e9.py fetch-tree.sh requirements.txt link-virt.cfg results/E9/01-log.txt; do
  change create "spikes/sel4-feasibility/$file"
  expect "spike file $file is deep" depth_is deep "$(packet)"
done
change append spikes/sel4-feasibility/results/E9.md "prose"
expect "spike prose is standard by path" depth_is standard "$(packet)"

# 5. Evidence tooling and dependency lists are deep wherever they live. Other tooling is not.
for file in verify_x.py verify-x.py sanitize-x.py sanitize_x.py run-x-evidence.sh compare-x.py x-compare.py; do
  change create "tools/$file"
  expect "evidence tool $file is deep" depth_is deep "$(packet)"
done
for file in requirements-build.txt poetry.lock .gitmodules; do
  change create "tools/$file"
  expect "dependency list $file is deep" depth_is deep "$(packet)"
done
change append tools/notes.py "# change"
out=$(packet)
expect "other tooling is standard" depth_is standard "$out"
expect "--deep raises the depth" depth_is deep "$(packet --deep)"
expect "a standard change names no depth-setting file" has "None by path." "$out"

# 6. Sensitive paths, the plan and its Amendments are deep.
change create .github/workflows/ci.yml
expect "a sensitive path is deep" depth_is deep "$(packet)"
change append docs/research/sel4-spike-plan.md criterion
expect "the spike plan is deep" depth_is deep "$(packet)"
change append docs/research/sel4-spike-amendments.md "### entry"
expect "the Amendments are deep" depth_is deep "$(packet)"

# 7. A packet made by scripts that differ from the base's copies says so and is deep.
change append tools/notes.py "# change"
mkdir -p "$tmp/edited"
cp "$here/review-packet.sh" "$here/sensitive-paths.sh" "$tmp/edited/"
echo "# an edit" >>"$tmp/edited/review-packet.sh"
out=$(bash "$tmp/edited/review-packet.sh" "$base" "$head")
expect "an edited script cannot produce a standard packet" depth_is deep "$out"
expect "the packet says its script differs from the base's" has "differs from the base commit's copy" "$out"
expect "the unedited script is reported as the base's copy" has "the base commit's copy" "$(packet)"
expect "an unedited pair gives a standard packet for ordinary tooling" depth_is standard "$(packet)"
mkdir -p "$tmp/edited-paths"
cp "$here/review-packet.sh" "$here/sensitive-paths.sh" "$tmp/edited-paths/"
echo "# an edit" >>"$tmp/edited-paths/sensitive-paths.sh"
out=$(bash "$tmp/edited-paths/review-packet.sh" "$base" "$head")
expect "an edited path list beside an unedited packet script is deep" depth_is deep "$out"
expect "the packet names the path list as differing" has 'sensitive-paths.sh' "$(grep -F 'differs from the base' <<<"$out")"
# A repository whose base commit holds no copy of the scripts: the change that introduces them.
bare=$tmp/no-scripts
git init -q -b main "$bare"
git -C "$bare" config user.name test
git -C "$bare" config user.email test@example.invalid
git -C "$bare" config commit.gpgsign false
echo base >"$bare/notes.txt"
git -C "$bare" add -A
git -C "$bare" commit -q -m base
echo change >>"$bare/notes.txt"
git -C "$bare" add -A
git -C "$bare" commit -q -m change
out=$(cd "$bare" && bash "$script" HEAD~1 HEAD)
expect "a base with no copy of the scripts is deep" depth_is deep "$out"
expect "the packet says the base has no copy" has "the base commit has no copy" "$out"

# 8. What the reviewer is pointed to.
change append docs/notes.md "See [x](research/sel4-spike-plan.md#decision-rules)."
expect "a cited plan section is listed" has 'sel4-spike-plan.md#decision-rules' "$(packet)"
change append spikes/sel4-feasibility/crates/t/src/mmio.rs "// change"
expect "a verifier that pins a changed file is named" has 'mmio.rs` is named by: spikes/sel4-feasibility/verify_t.py' "$(packet)"
change append tools/notes.py "# change"
expect "ordinary tooling names no evidence" has "None found." "$(packet)"
pin_then_change() { echo "pinned: notes.py" >>spikes/sel4-feasibility/results/E9/00-preflight.txt; }
git checkout -q main
pin_then_change
git add -A
git commit -q -m "pin notes.py"
pinned_base=$(git rev-parse HEAD)
git checkout -q -b pinned-change "$pinned_base"
echo "# change" >>tools/notes.py
git add -A
git commit -q -m change
out=$(bash "$script" "$pinned_base" "$(git rev-parse HEAD)")
expect "a change to a file that recorded evidence names is deep" depth_is deep "$out"
for variable in GIT_LITERAL_PATHSPECS GIT_GLOB_PATHSPECS GIT_NOGLOB_PATHSPECS; do
  expect "$variable does not hide an evidence record" depth_is deep "$(env "$variable=1" bash "$script" "$pinned_base" "$(git rev-parse HEAD)")"
done
expect "the pinning record is named" has 'notes.py` is named by: spikes/sel4-feasibility/results/E9/00-preflight.txt' "$out"
git checkout -q main
git reset -q --hard "$base"
change append spikes/sel4-feasibility/helper.py "# change"
expect "a preflight record that pins a changed file is named" has 'helper.py` is named by: spikes/sel4-feasibility/results/E9/00-preflight.txt' "$(packet)"
pin_in_manifest() { echo "sha256 tools/notes.py" >spikes/sel4-feasibility/results/evidence-manifest.txt; echo "cp tools/notes.py out/" >spikes/sel4-feasibility/run-e9-evidence.sh; append tools/notes.py "# change"; }
change pin_in_manifest
out=$(packet)
expect "a manifest that pins a changed file is named" has 'spikes/sel4-feasibility/results/evidence-manifest.txt' "$(grep -F 'notes.py` is named by' <<<"$out")"
expect "an evidence driver that names a changed file is named" has 'spikes/sel4-feasibility/run-e9-evidence.sh' "$(grep -F 'notes.py` is named by' <<<"$out")"
hostile() { echo x >'spikes/a`b.rs'; }
change hostile
expect "a backtick in a file name is neutralized" has 'spikes/a?b.rs` (compiled or linked source)' "$(packet)"
if [[ -x /bin/bash ]]; then
  expect "file names are printed under the system bash too" has 'spikes/a?b.rs` (compiled or linked source)' "$(/bin/bash "$script" "$base" "$head")"
fi
expect "a short name width does not cut file names" has "spikes/ab.rs" "$(section "Changed files" "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.statNameWidth GIT_CONFIG_VALUE_0=5 packet)")"

# 9. A submodule is a dependency. Anchors are read from documents only.
git checkout -q -b gitlink "$base"
git update-index --add --cacheinfo 160000,1111111111111111111111111111111111111111,vendor/lib
git commit -q -m "add a submodule"
head=$(git rev-parse HEAD)
expect "a submodule change is deep" depth_is deep "$(packet)"
expect "a submodule change is deep despite diff.ignoreSubmodules" depth_is deep "$(GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=diff.ignoreSubmodules GIT_CONFIG_VALUE_0=all packet)"
git reset -q --hard
# A submodule that .gitmodules says to ignore, then moved to another commit, then removed.
printf '[submodule "vendor/lib"]\n\tpath = vendor/lib\n\turl = ./lib\n\tignore = all\n' >.gitmodules
git add .gitmodules
git commit -q -m "ignore the submodule"
ignored_base=$(git rev-parse HEAD)
git update-index --cacheinfo 160000,2222222222222222222222222222222222222222,vendor/lib
git commit -q -m "move the submodule"
moved=$(git rev-parse HEAD)
out=$(bash "$script" "$ignored_base" "$moved")
expect "moving a submodule that .gitmodules ignores is deep" depth_is deep "$out"
expect "the moved submodule is counted" has "a submodule changed (1)" "$out"
git update-index --force-remove vendor/lib
git commit -q -m "remove the submodule"
expect "removing a submodule is deep" has "a submodule changed (1)" "$(bash "$script" "$moved" "$(git rev-parse HEAD)")"
git reset -q --hard
change append tools/notes.py "# see sel4-spike-plan.md#decision-rules"
expect "an anchor in a script is not a cited plan section" has "None. Read the plan by section" "$(packet)"

# 10. A failed Git step prints no depth.
git checkout -q --orphan unrelated
git rm -q -rf . >/dev/null
echo x >AGENTS.md
git add -A
git commit -q -m unrelated
unrelated=$(git rev-parse HEAD)
git checkout -q main
status=0
out=$(bash "$script" "$base" "$unrelated" 2>/dev/null) || status=$?
expect "commits with no shared history exit 65" test "$status" -eq 65
expect "commits with no shared history print no depth" lacks "Depth:" "$out"

# 11. The scope starts at the merge base when the base given is not an ancestor.
change append docs/notes.md "on a branch"
branch_head=$head
git checkout -q main
echo later >docs/later.md
git add -A
git commit -q -m later
out=$(bash "$script" "$(git rev-parse HEAD)" "$branch_head")
expect "a base that is not an ancestor is replaced by the merge base" has "The scope starts at their merge base" "$out"
expect "files changed only on the base branch are not in scope" lacks "docs/later.md" "$out"

# 12. Bad arguments.
expect "a missing argument exits 64" exits 64 bash "$script" "$base"
expect "an unknown flag exits 64" exits 64 bash "$script" "$base" "$branch_head" --lower
expect "an unknown commit exits 65" exits 65 bash "$script" "$base" 0000000000000000000000000000000000000000

echo "review-packet tests: $passed passed, $failed failed"
[[ $failed -eq 0 ]]
