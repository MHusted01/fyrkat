---
name: handoff
description: Update docs/development/SESSION_HANDOFF.md from the actual Git state and repository documents, so a fresh session can resume safely. Use at the end of a session or before context runs out. Edits that one file only. Never commits, pushes, merges or switches branches.
disable-model-invocation: true
argument-hint: "[--no-check]"
allowed-tools: Read Grep Glob Bash(git status *) Bash(git diff *) Bash(git log *) Bash(git branch *) Bash(git show *) Bash(git rev-parse *) Bash(git ls-remote *) Bash(gh pr view *) Bash(gh pr checks *) Bash(gh run list *) Bash(cargo xtask check) Edit(docs/development/SESSION_HANDOFF.md) Write(docs/development/SESSION_HANDOFF.md)
---

Write a current handoff. The handoff is a snapshot for the next session. It is not a source of
truth: ADRs and Git are. Record only what you verified, and label the rest.

## Hard limits

- Edit `docs/development/SESSION_HANDOFF.md` and nothing else.
- Never run `git add`, `commit`, `push`, `merge`, `checkout`, `switch`, `reset`, `stash` or `rebase`,
  and never change a branch. The owner decides whether and when to commit the file.
- Never record an approval you cannot point to. An approval counts only if a repository document
  records it (the plan's Amendments, an ADR, the acceptance record) or the owner stated it in this
  conversation. Name the source for each one.
- No secrets and no personal email addresses. A public research-source URL is the only exception.

## Steps

1. **Git state.** Run `git status -sb`, `git rev-parse HEAD`, `git branch --show-current`,
   `git log --oneline -15`, `git diff --stat`, and list untracked files. Note the upstream branch and
   whether it is ahead or behind. If `gh` works, run `gh pr view` and `gh pr checks` for the open PR.
   If a command fails, write "not verified" with the reason. Do not guess.
2. **Documents.** Read `AGENTS.md`, the current `SESSION_HANDOFF.md`, `docs/roadmap.md`,
   `docs/development/m0-acceptance.md` if it exists, the Status line of every ADR in `docs/adr/`, and
   the Status line and Amendments tail of `docs/research/sel4-spike-plan.md`.
3. **Check the old handoff.** For each claim in it (branch, SHA, commit count, PR state, approvals,
   ADR statuses, what is blocked), compare it with step 1 and 2. Drop what is stale. Do not carry a
   claim forward unless you checked it. If the handoff conflicts with an ADR or Git, the ADR or Git
   wins, and you list the conflict under Blockers.
4. **Verify.** Run `cargo xtask check` and record the real result, unless the argument is `--no-check`
   or a check already ran on this exact commit in this session. Record the command, the commit, and
   the result as printed. If you did not run it, say so and say why.
5. **Write the file**, replacing its content. Git keeps the history. Use these sections, in order, and
   keep the whole file under about 120 lines:
   - **Snapshot:** date, branch, HEAD, upstream, open PR and its checks.
   - **Milestone status:** the current milestone and each exit criterion, from `docs/roadmap.md`.
   - **Completed since the last handoff.**
   - **Authorizations in force:** what the owner has authorized, with the source, and what is
     explicitly not authorized. Spike execution stays "not authorized" unless a document says otherwise.
   - **Pending approvals:** decisions that wait for the owner.
   - **Blockers and conflicts.**
   - **Uncommitted changes:** the output of step 1, including this file once written.
   - **Verified results:** command, commit, result. Then **Not verified.**
   - **Next actions:** exact and ordered, each marked as authorized or as needing approval.
   - **Context not recorded elsewhere:** only facts that no ADR, plan or doc holds.
6. **Report.** Show `git diff --stat`, state that the file is uncommitted, and list anything you could
   not verify. Do not commit it.
