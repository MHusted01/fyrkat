---
name: handoff
description: Update docs/development/SESSION_HANDOFF.md with what the next session needs and no other file holds, so a fresh session can resume safely. Use before the last commit of a task, at the end of a session, or before context runs out. Edits that one file only. Never commits, pushes, merges or switches branches.
disable-model-invocation: true
argument-hint: "[--no-check]"
allowed-tools: Read Grep Glob Bash(git status *) Bash(git diff *) Bash(git log *) Bash(git branch *) Bash(git show *) Bash(git rev-parse *) Bash(git ls-remote *) Bash(gh pr view *) Bash(gh pr checks *) Bash(gh run list *) Bash(cargo xtask check) Edit(docs/development/SESSION_HANDOFF.md) Write(docs/development/SESSION_HANDOFF.md)
---

Write a current handoff. The handoff is a snapshot for the next session. It is not a source of
truth: ADRs and Git are. Record only what you verified, and label the rest.

Each fact has one home (docs/development/workflow.md, "Records"). The handoff links to a fact's
home and does not restate it.

## Hard limits

- Edit `docs/development/SESSION_HANDOFF.md` and nothing else.
- Never run `git add`, `commit`, `push`, `merge`, `checkout`, `switch`, `reset`, `stash` or `rebase`,
  and never change a branch. The file is committed with the task it describes, in that task's pull
  request, by whoever commits the task. It never gets a pull request of its own.
- Never record an approval you cannot point to. An approval counts only if a repository document
  records it (the plan's Amendments, an ADR, the acceptance record) or the owner stated it in this
  conversation. Name the source for each one.
- No secrets and no personal email addresses. A public research-source URL is the only exception.

## What does not go in the handoff

`/fyrkat-resume` reads these from Git and the documents every time, so a copy here can only go
stale: the branch, the head commit, the upstream, commit counts, the state of pull requests and
checks, the list of uncommitted files, ADR status lines, milestone status, and what a result file
or an Amendments entry already says.

## Steps

1. **Git state.** Run `git status -sb`, `git rev-parse HEAD`, `git branch --show-current`,
   `git log --oneline -15` and `git diff --stat`. If `gh` works, run `gh pr view` and
   `gh pr checks` for the open PR. You need these to write accurate next actions. You do not copy
   them into the file.
2. **Documents.** Read the current `SESSION_HANDOFF.md`, `docs/roadmap.md`, the Status line of every
   ADR in `docs/adr/`, the Status line of `docs/research/sel4-spike-plan.md`, and the last entries
   of `docs/research/sel4-spike-amendments.md`.
3. **Check the old handoff.** Compare each of its claims with steps 1 and 2. Drop what is stale or
   what another file now holds. Do not carry a claim forward unless you checked it. If the handoff
   conflicts with an ADR or Git, the ADR or Git wins, and you list the conflict under Blockers.
4. **Verify.** Run `cargo xtask check` and note the result, unless the argument is `--no-check` or a
   check already ran on this exact commit in this session.
5. **Write the file**, replacing its content. Describe the state as it will be once the task's pull
   request merges. Use these sections, in order, and keep the file under about 60 lines:
   - **Authorizations in force:** one line each, with a link to the entry that records it and the
     date it ends if it has one. Then what is explicitly not authorized.
   - **Waiting for the owner:** decisions only the owner can make, each with a link to where the
     question is set out.
   - **Blockers and open findings:** including any review finding left open, by ID.
   - **Local state that Git does not show:** gitignored directories that must be kept, branches
     that must never be pushed, and commands that must not be run here.
   - **Verified, and not verified:** only what CI does not already show for the commit.
   - **Next actions:** exact and ordered, each marked as authorized or as needing approval.
   - **Context not recorded elsewhere:** only facts that no ADR, plan, result or other document holds.
     If a fact belongs in one of those, put it there and link to it.
6. **Report.** Show `git diff --stat`, say that the file is uncommitted and which pull request it
   belongs in, and list anything you could not verify. Do not commit it.
