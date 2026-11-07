# M0 acceptance record

Evidence for the M0 exit criteria in the [roadmap](../roadmap.md), gathered on 2026-11-07.
It says what was shown, how, and what was not. The owner declares M0 complete, not this
file, and did so on 2026-11-07, accepting the limits listed below. The
[merged state](#merged-state) section records what actually landed on `main`.

## Exit criteria

| Criterion | Status | Evidence |
|---|---|---|
| A fresh clone passes `cargo xtask check` | Done | A fresh clone of `m0/foundation` at `46a90fa` built its tools and passed 12 of 12 steps on macOS arm64. CI runs the same command on a fresh checkout on Linux. [Measured] |
| CI runs on a real PR, and a failing change is blocked | Done | PR 1 ran all three required checks and passed. A throwaway PR 2 broke a Markdown link, failed `check and boot (ubuntu x86-64)`, showed `BLOCKED`, and `gh pr merge` was refused for the admin. It was closed unmerged. [Measured] |
| A direct push to `main` is rejected, and protections are confirmed through the API | Done by equivalent test, see below | Protection read back through the API. Rejection shown on an identically protected throwaway branch. `main` was not push-tested |
| ADRs 0001 to 0003 are ruled on, and the spike plan is approved | Done | Ruled on at Gate 1. The owner approved the plan at commit `46a90fac7ec09865502de1059dc9a213fa3fcd9f`, recorded in the plan's Amendments. Approval does not authorize running experiments |
| Claude Code configuration confirmed working in a real session | Done, with limits, see below | |
| The adversarial review is complete, with material findings fixed or tracked | Done | Two reviews by the `reviewer` agent. Findings are fixed or listed under Known limits |

## Direct-push rejection: what was and was not tested

- **Tested:** a throwaway branch `protection-test`, created from `main`'s commit, was given
  protection from the same payload used for `main`. The full protection JSON of the two
  branches was fetched through the API, with `url` fields removed, and compared. **They were
  identical** [Measured], including the three required checks bound to the GitHub Actions
  app, `strict`, `enforce_admins`, zero required approvals, linear history, conversation
  resolution, and no force pushes or deletions.
- A direct push of an empty commit to that branch, from the owner's admin account, was
  **rejected**: `GH006 Protected branch update failed`, "Changes must be made through a pull
  request", and "3 of 3 required status checks are expected". The remote branch did not
  move. The branch and its protection were then deleted.
- **Not tested:** a direct push to `main` itself. The owner decided not to run a push that
  could succeed. The evidence for `main` is therefore the identical configuration and the
  same enforcement mechanism, not a rejection of a push to `main`. [Inferred]
- The same API read-back of `main` shows the settings stated in the roadmap.

## Claude Code configuration: scripted tests against live checks

- **Scripted regression tests** run in `cargo xtask check` and CI: 80 for the hooks, and 28
  for the sensitive-paths script. They feed crafted JSON to the hook scripts. They prove the
  scripts' logic, not that Claude Code calls them. The tests fail against the earlier hook
  versions. [Measured]
- **Live checks** in a real Claude Code session at the repository root:
  - The push hook blocked a push to `main` and blocked its own false positives while it was
    being developed. The permission deny rule and hook were both in effect. [Measured]
  - The ADR hook, through the real `Edit` tool, blocked an attempt to change ADR 0004 from
    Proposed to Accepted. [Measured]
  - The ADR hook, through the real `Bash` tool, blocked a no-op `sed -i` aimed at an ADR. The
    `Bash` registration was added mid-session and was still honoured. [Measured]
  - These tests used ADR 0004, which is Proposed. **No ADR is Accepted**, so the hook's rule
    for editing an Accepted ADR has only been tested by the scripts, not live. It was not
    live-tested, because that would require an Accepted ADR.
- **Plugins:** disabling the unrelated plugins was verified in a fresh headless session,
  which ran on Sonnet and showed all ten disabled. The long-running session that did this
  work started before the change and still lists them. [Measured]
- **Not tested:** the first-run workspace trust prompt in an interactive session.

## CI facts

From run 42399915258 on PR 1 and later runs: `/dev/kvm` was present on the x86-64 runner and
absent on the arm64 runner. Both boot jobs use TCG. The runners have QEMU 8.2.2 from Ubuntu
packages, not the 11.1.3 the spike plan pins. Firmware lookup worked on Ubuntu 24.04. Debian
is untested. [Measured]

## Merged state

PR 1 was squash-merged into `main` on 2026-11-07, with the owner's explicit authorization, after
all three required checks passed on its final head `3d688f8` and GitHub reported it `CLEAN`.

| Fact | Value |
|---|---|
| Merge commit on `main` | `ae054be6c8dfb63886cebf08c8b193afd5595406`, message "chore: M0 foundation (#1)" |
| Parent | `ee063e6`, the first commit. `main` has two commits, so history is linear |
| Signature | Verified by GitHub (`valid`) |
| Tree | Identical to the PR head `3d688f8`: `35f34a5cf137f386ef743526bd3c8161aa369741` [Measured] |
| PR branch | Deleted on GitHub and locally. Remote refs are `main` and the closed PR heads |
| Protection on `main` after the merge | Unchanged: strict, the three named checks, admins enforced, 0 approvals, linear history, conversation resolution, no force pushes or deletions. Squash-only merges |
| CI on the push to `main` | Run 42414422734 on `ae054be` succeeded: `check and boot (ubuntu x86-64)` and `boot (ubuntu arm64)` passed. `security-sensitive paths` was skipped, because it runs only on pull requests |

The recorded plan approval is at commit `46a90fac7ec09865502de1059dc9a213fa3fcd9f`. After the squash
that commit is no longer on `main`, since the PR commits were collapsed, and it stays reachable
through the closed PR 1 (`refs/pull/1/head` is `3d688f8`, which descends from it). The
approved plan text is unchanged in `main`'s `docs/research/sel4-spike-plan.md`, apart from the
Status line, the start-gate wording, the Scope limits line and the approval entry, as the plan
records.

## Workflow skills

Two project skills were added to PR 1 before it merged: `/fyrkat-resume` (read-only, at session
start) and `/handoff` (rewrites the handoff file only, at session end). Both are
user-invoked. Each was tested in a fresh headless session:

- **`/fyrkat-resume`** ran for 9 turns on Sonnet at about $0.20. The repository's `git status` and
  HEAD were identical before and after. It listed real discrepancies between the old handoff and
  Git, named the sources of authorization, and stopped at the gate: it refused to start spike
  work, because execution is not authorized. [Measured]
- **`/handoff`** ran in a scratch copy of the repository for 21 turns at about $0.32. It changed only
  `docs/development/SESSION_HANDOFF.md`, made no commit, and did not change branch or HEAD. It
  labelled each claim Measured or Documented, and listed what it had not verified. [Measured]

## Known limits

- The hooks guard against mistakes and are not a security boundary. They can block a harmless
  message that contains a pushing command, or a harmless copy of an ADR.
- The sensitive-paths job is a notice, not an access control, because the workflow file comes
  from the PR. A base-controlled `pull_request_target` check is a follow-up after PR 1
  merges. With one maintainer, GitHub cannot require a second approver.
- AI review is not independent human review.
- `docs/standards/toolchain.md` still exempts QEMU, EDK2, shellcheck and actionlint from
  "pin everything". The CI QEMU version differs from the spike's pin, and CI results never
  substitute for spike results.
- The spike's C1 and C2 method files do not exist yet. The plan requires them before any run.
- Spike execution is not authorized.
