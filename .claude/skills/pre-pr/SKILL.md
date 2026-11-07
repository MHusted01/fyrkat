---
name: pre-pr
description: Run the full verification before a pull request and fill in the PR template's verification section with real results. Use when work is ready for review.
disable-model-invocation: true
allowed-tools: Bash(cargo xtask *) Bash(git status *) Bash(git diff *) Bash(git log *)
---

Prepare the verification section of the PR. Report only what you ran.

1. `git status` and `git diff --stat` against the base branch. Note any uncommitted or untracked files.
2. Run `cargo xtask check`. Record each step's result as printed. Do not summarize a failure as a pass.
3. Run `cargo xtask boot` if boot-smoke, xtask, firmware handling or CI changed. Record the accelerator used.
4. Fill in the "Verification" section of `.github/pull_request_template.md` with: the exact commands, the result of each, what was not run and why, and which claims rest on emulation only.
5. If any security-sensitive path changed (`.github/`, `deny.toml`, `rust-toolchain.toml`, `.claude/`, `Cargo.lock`, `docs/adr/`), say so in the PR text.
6. Output the completed section for the author to paste. Do not push, open the PR, or commit. Those need the owner's approval.
