# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win
over it. It records approvals and grants none. The previous handoff described the state before
publication (branch `m0/foundation`, nothing pushed). It was stale and is replaced entirely.

## Snapshot

- **Date:** 2026-11-07.
- **Branch:** `m0/post-merge-record`, local only. **HEAD:** `ae054be6c8dfb63886cebf08c8b193afd5595406`,
  the same commit as `main` and `origin/main`.
- **Upstream:** none for this branch. `main` tracks `origin/main` and is level with it.
- **Remote:** `https://github.com/MHusted01/fyrkat.git`. Its only branch is `main`.
- **Pull requests:** none open. PR 1 (M0 foundation) is MERGED. PR 2 (throwaway failing check) is CLOSED.
  [Measured: `gh pr list --state all`]
- **CI on `main`:** run 42414422734 on `ae054be` succeeded. `boot (ubuntu arm64)` and `check and boot
  (ubuntu x86-64)` passed. `security-sensitive paths` was skipped. [Measured: `gh run view`]

## Milestone status

M0 Engineering foundation. `docs/roadmap.md` still says **in progress**. The owner declares it
complete, and nothing in the repository or in this conversation records that. The
[acceptance record](m0-acceptance.md) (its uncommitted edit included) lists every exit criterion as Done:

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

- PR 1 was squash-merged into `main` as `ae054be`. Its tree `35f34a5cf137f386ef743526bd3c8161aa369741`
  equals the tree of PR head `3d688f8`. [Measured: `git rev-parse` on both]
- Skills `/fyrkat-resume` and `/handoff` landed with PR 1. Both exist in `.claude/skills/`.
- The branch `m0/post-merge-record` carries one uncommitted edit to `m0-acceptance.md`: a "Merged state"
  section and a "Workflow skills" section.

## Authorizations in force

- **PR 1 merge:** the owner authorized it in the session that merged it (2026-11-07). Source: the
  acceptance record's "Merged state" section, which is uncommitted. A fresh session cannot see that
  conversation, so treat the acceptance record as the evidence.
- **Spike plan approval** (plan and criteria only): the plan's Amendments, "Owner approval of the plan".
- **Owner decisions on K4, x86-64 assurance and patch separation:** the same Amendments and the plan text.
- **Not authorized:** spike execution of any kind. Class 3 kernel changes, including K4. Relaxing any
  criterion. Accepting any ADR. Any push, PR or GitHub change not named above.

## Pending approvals

- Declaring M0 complete (owner only), and the matching roadmap status change.
- Committing the `m0-acceptance.md` edit and this file, and any push or PR for them.
- Authorizing spike execution, which also needs the C1 and C2 method files committed first.
- Installing the pinned spike toolchain or any other new tool.
- Deciding ADR 0004. No ADR is Accepted.

## Blockers and conflicts

- **No conflicts** between this file's claims and Git or the ADRs, as checked above.
- **Blocked:** spike Stage A, because execution is not authorized. The C1 and C2 method files do not exist yet.
- **Decision wait:** M1 waits on ADR 0004 and therefore on the spike.
- **Known limits** (from the acceptance record, not re-tested): the sensitive-paths job is only a
  notice. A base-controlled `pull_request_target` check is a follow-up after PR 1. With one maintainer,
  GitHub cannot require a second approver. `docs/standards/toolchain.md` still exempts QEMU, EDK2,
  shellcheck and actionlint from pinning. CI has QEMU 8.2.2, and the spike pins 11.1.3.

## Uncommitted changes

`git status -sb` at the time of writing, before this file was written:

```text
## m0/post-merge-record
 M docs/development/m0-acceptance.md
```

`git diff --stat`: `docs/development/m0-acceptance.md | 38 +++++++++++++++++++++++++++++++++++++-`
(37 insertions, 1 deletion). No untracked files. This file is also uncommitted now. Nothing was staged or committed.

## Verified results

| Check | Commit | Result |
|---|---|---|
| `cargo xtask check` | `ae054be` plus the uncommitted `m0-acceptance.md` edit | "check: all 12 steps passed". 46 of 46 tests; hook tests 80 passed, 0 failed; sensitive-paths tests 28 passed, 0 failed. cargo-deny, shellcheck, actionlint, markdown links and spike isolation all PASS |
| `gh run view 42414422734` | `ae054be` | success, with job results as in the Snapshot |
| `git rev-parse` of both trees | `ae054be`, `3d688f8` | Both `35f34a5cf137f386ef743526bd3c8161aa369741` |
| `git merge-base --is-ancestor 46a90fa 3d688f8` | | True: the approved plan commit is in PR 1's history |
| ADR `Status:` lines | `ae054be` | 0001 Part A Provisional, Part B Withdrawn. 0002 and 0003 Provisional. 0004 Proposed |

The `check` run ran after the `m0-acceptance.md` edit, and only on this exact tree. It ran on macOS arm64.

**Not verified:**

- Nothing from the earlier list is open here, except the spike prerequisites below.
  Verified later in the interactive session, after this file was generated [Measured]: branch
  protection on `main` after the merge is unchanged (strict, three named checks, admins enforced, 0
  approvals, linear history, conversation resolution, no force pushes or deletions). GitHub reports
  `ae054be` as a verified signature. The plan on `main` differs from the approved `46a90fa` text only
  at four hunks, matching the Amendments: the Status line, the start-gate wording, one Scope limits
  line, and the approval entry. (`git log --format=%G?` prints `E` locally, because no allowed-signers
  file is configured here.)
- Whether the spike prerequisites are still missing (pinned nightly, cross GCC, a pinned rust-sel4 commit).
  The old handoff said so, and it was not rechecked.
- Debian firmware paths. The workspace-trust prompt in an interactive session.

## Next actions

1. **Needs the owner:** review the uncommitted `m0-acceptance.md` edit and this file, then decide whether
   to commit them. Agents commit locally only when asked.
2. **Needs the owner:** push the branch and open a PR for them, since `main` is protected. Any remote action
   needs approval first.
3. **Needs the owner:** declare M0 complete, or name what is missing. Then update the roadmap status.
4. Done in the interactive session: the `main` protection was re-read after the merge (see Not verified).
5. **Needs approval:** the follow-up `pull_request_target` check for sensitive paths, which touches `.github/`.
6. **Needs approval:** write the C1 and C2 method files, then ask the owner to authorize spike Stage A.
   Do not start Stage A without that.

## Starting the spike session

After the post-merge PR is merged, start a fresh Claude Code session at the repository root on `main`
and run `/fyrkat-resume`. Preparation that needs no execution authorization: drafting the C1 and C2
method files, pinning the rust-sel4 commit, and listing the tools the plan needs. Running any
experiment, and installing the pinned nightly or any other tool, needs the owner's separate approval.
Use Sonnet for routine work and stop at the end of each stage. See the spike plan's model policy.

## Context not recorded elsewhere

- Session memory is stored per launch directory and does not carry over between sessions.
- In this session the permission prompt refused two Bash calls: the protection read-back
  (`gh api .../protection`) and one compound command containing `HEAD^{tree}`. Simpler calls ran.
  The cause was not investigated.
- The HongMeng, TickTock and Sculpt PDFs used in the research are gone. Their titles are in
  `docs/research/sel4-adversarial-review.md`.
