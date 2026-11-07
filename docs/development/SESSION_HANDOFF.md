# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win
over it. It records approvals and grants none. The previous handoff named branch
`m0/post-merge-record` and HEAD `ae054be`. Both are stale, and the file is replaced entirely.

## Snapshot

- **Date:** 2026-11-07.
- **Written from:** branch `m0/complete`, on top of `aa8e40ff9b694f7c0c4942b7f83b14e577d78df4`
  (PR 3, which equalled `main` when this file was generated). This file is committed by the follow-up
  PR that also marks M0 complete. **Once that PR is merged, `main` is its squash commit, so the SHA is not
  written here. Check it with `git log -1 origin/main`.**
- **Upstream:** `m0/complete` was local until the PR was opened. [Measured: `git branch -vv`]
- **Remote:** `main` was its only branch when generated. [Measured: `git ls-remote --heads origin`]
- **Pull requests:** PR 1 (M0 foundation) and PR 3 (merged-state record) are MERGED, and the
  follow-up PR that carries this file was opened afterwards. PR 2
  (throwaway failing check) is CLOSED. [Measured: `gh pr list --state all`]
- **CI on `main`:** run 42415395227 on `aa8e40f` succeeded. `boot (ubuntu arm64)` and `check and boot
  (ubuntu x86-64)` passed. `security-sensitive paths` was skipped. [Measured: `gh run view`]

## Milestone status

**M0 Engineering foundation is complete.** The owner declared it complete on 2026-11-07, on the
evidence in the [acceptance record](m0-acceptance.md) and accepting its documented limits. Once the
follow-up PR is merged, `docs/roadmap.md` on `main` says so. [Documented]

| Exit criterion | Status in the acceptance record |
|---|---|
| Fresh clone passes `cargo xtask check` | Done (12 of 12 steps, macOS arm64) |
| CI on a real PR, failing change blocked | Done (PR 1 passed, PR 2 blocked) |
| Direct push to `main` rejected, protections via API | Done by equivalent test. `main` itself was not push-tested, by owner decision |
| ADRs 0001 to 0003 ruled on, spike plan approved | Done. Plan approved at `46a90fa`, which does not authorize execution |
| Claude Code configuration confirmed in a real session | Done, with limits. Workspace-trust prompt not tested |
| Adversarial review complete | Done. Two `reviewer` passes, findings fixed or listed as known limits |

S1 (kernel foundation spike) is planned and not started. M1 cannot be finalized before ADR 0004 is decided.

## Completed since the last handoff

- PR 3 was merged as `aa8e40f`: the "Merged state" and "Workflow skills" sections of the acceptance
  record, and the previous handoff. [Measured: `git show --stat`]
- The owner declared M0 complete. The follow-up PR records it in the roadmap and the acceptance record.

## Authorizations in force

- **Spike plan approval** (plan and criteria only): the plan's Amendments, "Owner approval of the plan".
- **Owner decisions on K4, x86-64 assurance and patch separation:** the same Amendments and the plan text.
- **M0 declared complete:** by the owner on 2026-11-07. Source, once merged: `docs/roadmap.md` and the
  acceptance record. The owner also authorized the follow-up PR that records it, and its merge.
- **Merge of PRs 1 and 3:** both merged on the owner's authorization. See the acceptance record.
- **Not authorized:** spike execution of any kind, including installing the pinned nightly or any other
  spike tool. Class 3 kernel changes, including K4. Relaxing any criterion. Accepting any ADR. Any push,
  PR or GitHub change not named above.

## Pending approvals

- Authorizing spike execution, which also needs the C1 and C2 method files committed first.
- Installing the pinned spike toolchain or any other new tool.
- Deciding ADR 0004. No ADR is Accepted.
- The `pull_request_target` follow-up for sensitive paths, which touches `.github/`.

## Blockers and conflicts

- **None between this file, Git and the ADRs** when the follow-up PR is merged. `/fyrkat-resume` checks it.
- **Blocked:** spike Stage A, because execution is not authorized. The C1 and C2 method files do not
  exist. [Measured: `find` for files named `*method*` found none]
- **Decision wait:** M1 waits on ADR 0004 and therefore on the spike.
- **Known limits** (from the acceptance record, not re-tested): the sensitive-paths job is only a
  notice. With one maintainer, GitHub cannot require a second approver. `docs/standards/toolchain.md`
  still exempts QEMU, EDK2, shellcheck and actionlint from pinning. CI has QEMU 8.2.2, and the spike
  pins 11.1.3.

## Uncommitted changes

When generated, the working tree held three edits: the roadmap, the acceptance record, and this file.
All three are committed by the follow-up PR. After it merges, the working tree should be clean.

## Verified results

| Check | Commit | Result |
|---|---|---|
| `cargo xtask check` | `aa8e40f` plus the uncommitted edits to `roadmap.md` and `m0-acceptance.md` | "check: all 12 steps passed". 46 of 46 tests. Hook tests 80 passed, 0 failed. Sensitive-paths tests 28 passed, 0 failed. cargo-deny, rustdoc, shellcheck, actionlint, markdown links and spike isolation PASS. Ran on macOS arm64 |
| `gh run view 42415395227` | `aa8e40f` | success. Jobs as in the Snapshot |
| `gh pr list --state all`, `git ls-remote --heads origin` | `aa8e40f` | PRs 1 and 3 MERGED, PR 2 CLOSED. `origin/main` equals local HEAD |
| ADR `Status:` lines (grep) | `aa8e40f` | 0001 Part A Provisional, Part B Withdrawn. 0002 and 0003 Provisional. 0004 Proposed |
| Spike plan `Status:` line | `aa8e40f` | Approved for the text at `46a90fa`. Does not authorize running any experiment |

The `check` run did not include this handoff file, which was written after it. It does not change code.

**Not verified:**

- Branch protection on `main`. It was last read back after PR 1 (see the acceptance record) and not
  rechecked after PR 3. Linux CI results are the CI runs above, not a local run.
- The `Amendments` text of the spike plan was not re-read in full. Only its tail and Status line were.
- Whether the spike prerequisites are still missing (pinned nightly, cross GCC, a pinned rust-sel4
  commit). Not rechecked.
- Debian firmware paths. The workspace-trust prompt in an interactive session.
- Commit signatures: `git log --format=%G?` prints `E` locally, because no allowed-signers file is
  configured. GitHub's verification of `aa8e40f` was not queried.

## Next actions

1. Run `git status -sb` and `git log -1 origin/main`. Expect a clean tree on `main`.
2. **Authorized, no execution:** draft the list of tools the plan needs, pin the rust-sel4 commit in a
   document, and draft the C1 and C2 method files. Do not install or run anything.
3. **Needs approval:** authorize spike Stage A, and any tool installation, before starting it.
4. **Needs approval:** the `pull_request_target` follow-up, which touches `.github/`.

## Context not recorded elsewhere

- Start a fresh session at the repository root and run `/fyrkat-resume`. Use Sonnet for routine work and
  stop at the end of each stage, per the spike plan's model policy.
- Session memory is stored per launch directory and does not carry over between sessions.
- The previous handoff recorded that the permission prompt refused two Bash calls: `gh api .../protection`
  and a compound command containing `HEAD^{tree}`. Another compound command with a shell variable was
  refused in this session. The cause is not investigated. Simpler calls ran.
- The HongMeng, TickTock and Sculpt PDFs used in the research are gone. Their titles are in
  `docs/research/sel4-adversarial-review.md`.
