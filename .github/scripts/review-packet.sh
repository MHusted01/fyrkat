#!/usr/bin/env bash
# Print the review packet for the change between two commits, as Markdown.
# Usage: review-packet.sh <base-sha> <head-sha> [--deep | --records-only]
#
# The packet is the brief a reviewer starts from. It is built from Git objects only, so the
# author adds no text of their own and it can be made for any two commits without a checkout.
# It names the review depth and the signals that set it. See docs/development/workflow.md.
#
# The depth printed here is a floor. The script sees impact signals in paths. It cannot see
# uncertainty or what a claim will be used for, so the author raises the depth with --deep
# when those call for it. Nothing lowers a depth the signals set: --records-only is refused
# unless the change is Markdown only, touches no sensitive path and adds no evidence label.
set -euo pipefail

usage() {
  echo "usage: $0 <base-sha> <head-sha> [--deep | --records-only]" >&2
  exit 64
}

[[ $# -ge 2 && $# -le 3 ]] || usage
base=$1
head=$2
flag=${3:-}
case "$flag" in
  "" | --deep | --records-only) ;;
  *) usage ;;
esac

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

git rev-parse --verify --quiet "$base^{commit}" >/dev/null || { echo "unknown commit: $base" >&2; exit 65; }
git rev-parse --verify --quiet "$head^{commit}" >/dev/null || { echo "unknown commit: $head" >&2; exit 65; }
base_sha=$(git rev-parse "$base^{commit}")
head_sha=$(git rev-parse "$head^{commit}")

# Extended regular expressions over repository-relative paths.
# Code that is compiled into a target image or runs with authority.
compiled='\.(rs|c|h|S|s|ld)$'
# Tools whose output decides whether evidence is accepted or published.
verifier='(^|/)(verify[-_][^/]*\.py|sanitize[-_][^/]*\.py|run-[^/]*-evidence\.sh|compare-[^/]*\.py|[^/]*-compare\.py)$'
# Text that fixes criteria in advance.
criteria='^docs/research/sel4-spike-plan\.md$'

# Keep a hostile file name from breaking a Markdown code span or a list.
safe() { printf '%s' "${1//[$'\n\r`']/?}"; }

files=()
while IFS= read -r -d '' path; do
  files+=("$path")
done < <(git -c core.quotePath=false diff --no-renames --name-only -z "$base_sha...$head_sha")

sensitive_report=$(bash "$here/sensitive-paths.sh" "$base_sha" "$head_sha")

deep_reasons=()
if ! grep -qx 'None\.' <<<"$sensitive_report"; then
  deep_reasons+=("a security-sensitive path changed")
fi
all_markdown=1
compiled_files=()
verifier_files=()
if [[ ${#files[@]} -gt 0 ]]; then
  for path in "${files[@]}"; do
    [[ "$path" == *.md ]] || all_markdown=0
    if [[ "$path" =~ $compiled ]]; then compiled_files+=("$path"); fi
    if [[ "$path" =~ $verifier ]]; then verifier_files+=("$path"); fi
    if [[ "$path" =~ $criteria ]]; then deep_reasons+=("the spike plan, which holds the fixed criteria, changed"); fi
  done
fi
if [[ ${#compiled_files[@]} -gt 0 ]]; then
  deep_reasons+=("compiled source changed (${#compiled_files[@]} file(s)): isolation, unsafe and device code are assumed until shown otherwise")
fi
if [[ ${#verifier_files[@]} -gt 0 ]]; then
  deep_reasons+=("an evidence verifier, sanitizer or evidence driver changed (${#verifier_files[@]} file(s))")
fi

# Lines the change adds that carry an evidence label, in Markdown files.
claims=$(git -c core.quotePath=false diff -U0 --no-renames "$base_sha...$head_sha" -- '*.md' |
  awk '
    /^\+\+\+ / { file = substr($0, 7); next }
    /^@@ /     { split($3, pos, ","); line = substr(pos[1], 2) + 0; next }
    /^\+/      { if ($0 ~ /\[(Measured|Documented|Inferred|Speculative)/) printf "%s:%d: %s\n", file, line, substr($0, 2, 200); line++ }
  ' || true)

if [[ "$flag" == --deep ]]; then
  deep_reasons+=("the author raised it: uncertainty or the use of a claim calls for it")
fi

if [[ ${#deep_reasons[@]} -gt 0 ]]; then
  depth=deep
elif [[ "$flag" == --records-only && $all_markdown -eq 1 && -z "$claims" && ${#files[@]} -gt 0 ]]; then
  depth=none
else
  depth=standard
fi

echo "# Review packet"
echo
echo "- Base: \`$base_sha\`"
echo "- Head: \`$head_sha\`"
echo "- Scope: \`git diff $base_sha...$head_sha\`"
echo "- **Depth: $depth**"
if [[ ${#deep_reasons[@]} -gt 0 ]]; then
  for reason in "${deep_reasons[@]}"; do echo "  - $reason"; done
fi
if [[ "$flag" == --records-only && "$depth" != none ]]; then
  echo "  - \`--records-only\` was refused: the change is not Markdown only, or it touches a sensitive path or adds an evidence label"
fi
echo
echo "## Changed files"
echo
echo '```'
git -c core.quotePath=false diff --no-renames --stat=120 "$base_sha...$head_sha" | tr -d '`'
echo '```'
echo
echo "$sensitive_report"
echo
echo "## Files that set the depth"
echo
if [[ ${#compiled_files[@]} -eq 0 && ${#verifier_files[@]} -eq 0 ]]; then
  echo "None by path."
else
  if [[ ${#compiled_files[@]} -gt 0 ]]; then
    for path in "${compiled_files[@]}"; do echo "- \`$(safe "$path")\` (compiled source)"; done
  fi
  if [[ ${#verifier_files[@]} -gt 0 ]]; then
    for path in "${verifier_files[@]}"; do echo "- \`$(safe "$path")\` (evidence tooling)"; done
  fi
fi
echo
echo "## Labelled claims the change adds"
echo
if [[ -z "$claims" ]]; then
  echo "None."
else
  echo '```'
  printf '%s\n' "$claims" | tr -d '`'
  echo '```'
fi
echo
echo "## Plan sections the change cites"
echo
anchors=$(git diff -U0 --no-renames "$base_sha...$head_sha" |
  grep -E '^\+' | grep -oE 'sel4-spike-(plan|amendments)\.md#[A-Za-z0-9_-]+' | sort -u || true)
if [[ -z "$anchors" ]]; then
  echo "None. Read the plan by section if a claim depends on it, not whole."
else
  while IFS= read -r anchor; do echo "- \`$anchor\`"; done <<<"$anchors"
fi
echo
echo "## Evidence drivers and verifiers that name a changed file"
echo
pinned=0
if [[ ${#files[@]} -gt 0 ]]; then
  for path in "${files[@]}"; do
    name=${path##*/}
    users=$(git grep -l -F -- "$name" "$head_sha" -- '*run-*-evidence.sh' '*verify*.py' 2>/dev/null |
      sed "s/^$head_sha://" | grep -v -F -x -- "$path" | sort -u || true)
    if [[ -n "$users" ]]; then
      pinned=1
      echo "- \`$(safe "$path")\` is named by: $(printf '%s' "$users" | tr '\n' ' ' | tr -d '`')"
    fi
  done
fi
if [[ $pinned -eq 0 ]]; then
  echo "None."
else
  echo
  echo "A recorded evidence set whose pinned source changed must be re-recorded before review."
fi
echo
echo "## Checks to run at the head commit"
echo
echo "- \`cargo xtask check\`"
if git cat-file -e "$head_sha:spikes/sel4-feasibility/verify-evidence.py" 2>/dev/null; then
  echo "- \`python3 -B verify-evidence.py\` and \`python3 -B verify-evidence.py --self-test\` in \`spikes/sel4-feasibility\`"
fi
