# M0 acceptance record

Evidence for the M0 exit criteria in the [roadmap](../roadmap.md), gathered on 2026-11-07.
It says what was shown, how, and what was not. The owner declares M0 complete, not this
file.

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
