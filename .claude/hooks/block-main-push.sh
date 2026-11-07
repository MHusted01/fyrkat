#!/usr/bin/env bash
# PreToolUse hook for Bash. Refuses git pushes to main or master, force pushes, and pushes
# of every branch. Exit 2 blocks the call and shows stderr to Claude.
#
# This is a guard against mistakes, not a security boundary. It splits the command on
# ; & | ( ) and backticks, finds `git [options] push`, and reads the remaining words with
# their quotes removed. It does not look inside `bash -c "..."`, variables, aliases or
# scripts. GitHub branch protection on main is the authoritative control, and the
# permission deny rules in .claude/settings.json back this hook up.
set -euo pipefail

input=$(cat)
command=$(jq -r '.tool_input.command // empty' <<<"$input")

block() {
  echo "BLOCKED: $1 Pushing to main or force pushing needs the owner's approval; ask the owner." >&2
  exit 2
}

unquote() {
  local s=$1
  s=${s//\"/}
  s=${s//\'/}
  printf '%s' "$s"
}

# True for a refspec whose destination is main or master: main, HEAD:main, +x:main,
# :main (delete) and refs/heads/main.
targets_main() {
  local ref=$1
  ref=${ref#+}
  ref=${ref##*:}
  ref=${ref#refs/heads/}
  [[ "$ref" == "main" || "$ref" == "master" ]]
}

# Handle the words of one `git push`, given as arguments.
check_push_words() {
  local word
  for word in "$@"; do
    word=$(unquote "$word")
    case "$word" in
      --force | --force=* | --force-with-lease | --force-with-lease=* | --force-if-includes)
        block "Force pushes are not allowed." ;;
      --all | --mirror)
        block "Pushing every branch would include main." ;;
      --*) continue ;;
      -*f*)
        block "Force pushes are not allowed." ;;
      -*) continue ;;
      +*)
        block "A leading + forces the push." ;;
    esac
    if targets_main "$word"; then
      block "This push targets main."
    fi
  done
}

saw_push=0
while IFS= read -r segment; do
  read -ra words <<<"$segment" || true
  count=${#words[@]}
  index=0

  # Skip leading VAR=value words and common wrappers.
  while ((index < count)); do
    case "$(unquote "${words[index]}")" in
      *=* | env | command | time | sudo | exec | nohup) index=$((index + 1)) ;;
      *) break ;;
    esac
  done
  ((index < count)) || continue
  first=$(unquote "${words[index]}")
  [[ "${first##*/}" == "git" ]] || continue
  index=$((index + 1))

  # Skip git's global options to reach the subcommand.
  while ((index < count)); do
    option=$(unquote "${words[index]}")
    case "$option" in
      -C | -c | --git-dir | --work-tree | --namespace | --exec-path) index=$((index + 2)) ;;
      -*) index=$((index + 1)) ;;
      *) break ;;
    esac
  done
  ((index < count)) || continue
  [[ "$(unquote "${words[index]}")" == "push" ]] || continue

  saw_push=1
  check_push_words "${words[@]:index+1}"
done < <(tr ';&|()`' '\n' <<<"$command")

if ((saw_push)); then
  branch=$(git -C "${CLAUDE_PROJECT_DIR:-.}" symbolic-ref --short -q HEAD || true)
  if [[ "$branch" == "main" || "$branch" == "master" ]]; then
    block "The current branch is $branch."
  fi
fi
exit 0
