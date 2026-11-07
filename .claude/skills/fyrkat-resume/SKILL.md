---
name: fyrkat-resume
description: Start or resume Fyrkat work safely. Loads the project instructions and the session handoff, checks them against Git and the ADRs, reports discrepancies, summarizes the state, and continues only work that is already authorized. Read-only.
disable-model-invocation: true
argument-hint: "[focus]"
allowed-tools: Read Grep Glob Bash(git status *) Bash(git diff *) Bash(git log *) Bash(git branch *) Bash(git show *) Bash(git rev-parse *) Bash(git cat-file *) Bash(git ls-remote *) Bash(gh pr view *) Bash(gh pr checks *)
---

Resume Fyrkat work. This skill only reads. It changes nothing until the verification is reported.

## Steps

1. **Load instructions.** Read `AGENTS.md` and `CLAUDE.md`, then `docs/development/SESSION_HANDOFF.md`.
   The handoff is a snapshot. It may be out of date.
2. **Read Git.** Run `git status -sb`, `git branch --show-current`, `git rev-parse HEAD`,
   `git log --oneline -10`, and `git diff --stat`. If `gh` works, run `gh pr view` for the open PR and
   `gh pr checks`. A command that fails is "not verified", with the reason.
3. **Read the decisions.** Read the Status line of each ADR in `docs/adr/`, `docs/roadmap.md`, and the
   Status line and Amendments tail of `docs/research/sel4-spike-plan.md`. If the handoff names an
   approved commit, confirm it exists with `git cat-file -t <sha>`.
4. **Find discrepancies.** Compare each checkable claim in the handoff with steps 2 and 3: branch,
   HEAD, working tree, PR state, ADR statuses, approvals, and what is authorized. List every mismatch
   as a table with the claim, the finding, and the source. Say plainly if there is none. If the handoff
   conflicts with an ADR or Git, the ADR or Git wins, and the owner is told.
5. **Summarize** in at most 15 lines: milestone, branch and HEAD, uncommitted changes, open PR and
   checks, pending approvals, blockers, and the next actions from the handoff.
6. **Say what is authorized.** Take the authorization only from the handoff's "Authorizations in force"
   section, or from the owner in this conversation, and confirm it against the documents. Name the
   source. If the next step needs approval, or is not authorized (the seL4 experiments are not unless a
   document says otherwise), stop and ask the owner. Do not infer authorization.
7. **Continue** only with work that is authorized, and honour `AGENTS.md`: no push, PR, merge or
   settings change without the owner, and no edits to an Accepted ADR. If a focus was given as an
   argument, apply it only within what is authorized.

Do not edit, commit, push, merge, switch branches or run experiments during steps 1 to 6.
