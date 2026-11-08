# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. The owner's S1 decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-08.
- **Branch:** `spike/s1-workspace-sanitized`, HEAD `5937762`, upstream `origin/spike/s1-workspace-sanitized`,
  0 ahead and 0 behind. `main` is `4fb92a1`. [Measured: `git status -sb`, `git rev-list`]
- **Open PR:** **PR 8**, not merged, merge state CLEAN. Its three required checks (`check and boot (ubuntu
  x86-64)`, `boot (ubuntu arm64)`, `security-sensitive paths`) passed on `5937762`. [Measured: `gh pr view 8`,
  `gh pr checks 8`]
- **Other PRs:** 1, 3, 4, 5, 6 merged. 2 and 7 closed. PR 7 held the same work with unredacted logs.
  [Measured: `gh pr list --state all`]
- **Remote branches:** only `main` and the PR 8 branch. [Measured: `git ls-remote --heads origin`]

## Milestone status

- **M0:** complete (owner declaration 2026-11-07, `docs/roadmap.md`).
- **S1 (roadmap exit: the owner decides ADR 0004; M1 cannot be finalized before it):** in progress and
  **stopped at the A3 gate**. Nothing else is decided.

| Experiment | Outcome | Record |
|---|---|---|
| A1 build on this Mac | **Pass**, label U. Accepted by the owner | `spikes/sel4-feasibility/results/A1.md` |
| A3 EL1 and HVF | **Fail** by the plan's clause, label U. Confirmed by the owner on a first report that held errors; **re-confirmation requested** | `results/A3.md` |
| A2a, A4, A5 | Not started | |

- **ADR statuses:** 0001 Part A Provisional, Part B Withdrawn. 0002 and 0003 Provisional. 0004 Proposed. None
  is Accepted. No ADR text was edited. [Measured: ADR Status lines]
- **A3 in one line:** unmodified non-hypervisor seL4 17.0.0 halts in kernel init under HVF on the M2 Pro with
  1 vCPU (the guest reports 8-bit ASIDs, the kernel needs 16-bit). It passes sel4test under TCG (124 passed,
  59 disabled). A real 4-node SMP kernel stops earlier in the elfloader (PSCI) under HVF and TCG. No nested
  virtualization. A kernel change would be Class 3. The plan: A3 Fail reopens ADR 0002, Stage C does not
  run, stop and report. The owner's reading: it does not automatically reject seL4.

## Completed since the last handoff

The last handoff (inside PR 8) was written before PR 8 was verified. Since then, at `5937762`: CI passed;
GitHub reports all three commits verified (valid), each with a DCO trailer; the evidence verifier passed
29 of 29 from a fresh clone of the remote branch; and a scan of the tracked tree found no user name, home
path or host name. The old local branch was renamed so it cannot be pushed by accident (see Context).

## Authorizations in force

Source: the owner's messages in this conversation, and the plan's 2026-11-08 Amendments.

- **Used:** merging PRs 5 and 6; pushing the spike branch and opening PR 7; the narrowly scoped replacement
  of PR 7 and its branch (not `main`, no other branch); opening PR 8.
- **Still in force:** the A3 stop condition. Decisions 1 to 7, P1 and P2 are approved; P3 deferred, P4 declined,
  P5 deferred to the A5 design gate.
- **Not authorized:** merging PR 8; A4; A2a; A5; the comparator; Tiers 2 and 3 (so no `x86_64-elf-gcc`); any
  kernel change; further tool installs; resuming experiments; any architecture change; relaxing a criterion;
  another history rewrite or any force-push; a GitHub Support request. **The tooling deviations are
  recorded for review, not approved.**

## Pending approvals (all the owner's)

1. Re-confirm A3 after the correction (the "4 vCPU" image was a single-node kernel).
2. What the A3 Fail means for ADR 0002 and the plan. The plan names no path that keeps HVF and unmodified
   seL4 on this host. Whether a newer Apple chip's HVF guest differs was not tested.
3. Merge PR 8, or not.
4. Review `results/deviations.md` (a locally built protoc 3.20.3, Homebrew installs with
   `--ignore-dependencies`, spike scripts and probes), and the `cargo deny` note (`RUSTSEC-2024-0449`,
   host-side only, policy unchanged).
5. Whether to ask GitHub Support to remove retained references to PR 7's original commits.
6. The A5 question (class D or Investigate), still open to the A5 design gate.

## Blockers and conflicts

- **A3 stop condition** blocks everything after A1.
- **Conflict: `docs/roadmap.md` is stale.** It says S1 is "planned" and execution "not yet authorized". The
  plan's Amendments and Git show A1 and A3 ran. Git and the plan win. Not edited here.
- **Remaining privacy exposure.** `refs/pull/7/head` still resolves to the original last commit `c99300d`, so
  the four original commits stay reachable by SHA, and in clones or forks made while public. PR 7's edit
  history may show its original text. This is not erasure. `main` never held it. [Measured: `git ls-remote`]
- The sanitization work had agent-run scans only, no independent review pass.
- Earlier open items: a base-controlled `pull_request_target` check (`m0-acceptance.md`); CI runners use
  QEMU 8.2.2 against the spike's pinned 11.1.3.

## Uncommitted changes

At the start of this step `git status -sb` printed only the branch line, and `git diff --stat` and the
untracked list were empty. This file is now modified and uncommitted. The owner decides about committing it.

## Verified results

| Command | Commit | Result |
|---|---|---|
| `cargo xtask check` | `5937762` | "check: all 12 steps passed" (46 tests; hook tests 80/0; sensitive-paths 28/0), macOS arm64 |
| `spikes/sel4-feasibility/verify-evidence.py` | `5937762` | 29 of 29 checks passed on the sanitized evidence |
| CI on PR 8 | `5937762` | three required checks passed |
| GitHub commit verification | the 3 PR 8 commits | all "true (valid)" |
| Tracked-tree scan | `5937762` | user name, home-directory path, host name: 0 files each |

**Not verified:** `cargo xtask boot` locally; any seL4 run on a host other than this M2 Pro; whether the
4-node SMP kernel boots under any machine setting; sel4test beyond the TCG 1-vCPU run; whether a GitHub
Support request would remove the retained references.

## Next actions

1. **Needs approval:** the owner re-confirms or contests A3.
2. **Needs approval:** the owner decides the ADR 0002 direction and whether PR 8 merges.
3. **Needs approval:** the owner reviews the deviations, and decides on a GitHub Support request.
4. **Authorized now:** read-only checks and answering questions only. Nothing that runs an experiment,
   installs a tool or changes Git state. If the owner lifts the A3 stop, A4's AArch64 half could run under
   TCG without Tier 2, A2a (Opus) needs A1's preprocessed kernel, and both need a fresh authorization.

## Context not recorded elsewhere

- **Unsanitized history is kept locally** on branch `local-only/s1-workspace-unsanitized` (no upstream).
  **Never push it.** Raw logs are in the gitignored `spikes/sel4-feasibility/results-raw/`, and a backup
  `fyrkat-s1-raw-evidence-2026-11-08.tar.gz` (SHA-256 `768af917…`) sits next to the repository directory.
- Stale local branches `spike/s1-prerequisites` and `docs/agents-research-section` are merged and can go.
- A global pre-commit hook outside this repo prints "Broken pipe" noise on commit. Commits still succeed.
- Never put the home path or user name in PR text, docs or logs. Sanitize with `sanitize-evidence.py` first.
- The `reviewer` and `researcher` agents have Bash, so "read-only" is not enforced. Check `git status` after
  they run. Start a fresh session at the repository root and run `/fyrkat-resume`.
