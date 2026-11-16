---
name: pre-pr
description: Run the full verification before a pull request and fill in the PR template's verification section with real results. Use when work is ready for review.
disable-model-invocation: true
allowed-tools: Bash(cargo xtask *) Bash(git status *) Bash(git diff *) Bash(git log *) Bash(bash .github/scripts/sensitive-paths.sh *) Bash(bash .github/scripts/review-packet.sh *)
---

Prepare the verification section of the PR. Report only what you ran.

1. `git status` and `git diff --stat` against the base branch. Note any uncommitted or untracked files.
2. Run `cargo xtask check`. Record each step's result as printed. Do not summarize a failure as a pass.
3. Run `cargo xtask boot` if boot-smoke, xtask, firmware handling or CI changed. Record the accelerator used.
4. Fill in the "Verification" section of `.github/pull_request_template.md` with: the exact commands, the result of each, what was not run and why, and which claims rest on emulation only.
5. Run `bash .github/scripts/sensitive-paths.sh <base> HEAD`, where `<base>` is the commit on `main` the branch started from (`git merge-base origin/main HEAD`). If it lists any path, say so in the PR text. If it exits with an error, fix the commit name: an error is not "None." The list of security-sensitive paths is in AGENTS.md.
6. Run `bash .github/scripts/review-packet.sh <base> HEAD` on the committed change and put the depth it prints in the PR text. Review follows docs/development/workflow.md.
7. Output the completed section for the author to paste. Do not push or open the PR: those need the owner's authorization. A local commit on the branch is allowed (AGENTS.md), and step 6 needs one.
