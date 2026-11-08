# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. The owner's S1 decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

**Written before PR 8 was merged.** Whether it has merged depends on a final independent review that this file
cannot know. Run `gh pr view 8` and `git log -3 main` first. If PR 8 has merged, this file is on `main` and the
"Open PR" lines below are history.

## Snapshot

- **Date:** 2026-11-08.
- **Branch:** `spike/s1-workspace-sanitized`. `main` was `4fb92a1` when this was written. Check
  `git log main..HEAD` and `git status -sb` for the live state.
- **PR 8:** open when this was written. All three required checks (`check and boot (ubuntu x86-64)`, `boot
  (ubuntu arm64)`, `security-sensitive paths`) passed on `d1b0f46`. **CI on any later head is not recorded
  here**: run `gh pr checks 8`.
- **Other PRs:** 1, 3, 4, 5, 6 merged. 2 and 7 closed. PR 7 held the same work with unredacted logs.
- **Remote branches:** `main` and the PR 8 branch.

## Milestone status

- **M0:** complete (owner declaration 2026-11-07, `docs/roadmap.md`).
- **S1 (roadmap exit: the owner decides ADR 0004; M1 cannot be finalized before it):** in progress and
  **stopped at the A3 gate**. Nothing else is decided.

| Experiment | Outcome | Record |
|---|---|---|
| A1 build on this Mac | **Pass**, label U. Accepted by the owner | `spikes/sel4-feasibility/results/A1.md` |
| A1 rerun, corrected `Cargo.lock` | The criterion **holds again** (label U). Kernel and loader identical to the original, **root task differs**, accounted for byte by byte. A separate result that replaces nothing | `results/A1-rerun.md` |
| A3 EL1 and HVF | **Fail**, label U, for unmodified non-hypervisor seL4 17.0.0 under HVF on one Apple M2 Pro. Re-confirmed by the owner. The mislabeled "4 vCPU" image is not valid SMP evidence | `results/A3.md` |
| A2a, A4, A5 | Not started | |

- **ADR statuses:** 0001 Part A Provisional, Part B Withdrawn. 0002 and 0003 Provisional. 0004 Proposed. None
  is Accepted. No ADR text was edited. [Measured: ADR Status lines]
- **Owner rulings in the Amendments:** decision rule 2 **applies to the tested HVF configuration** and is
  **not** generalized to TCG or other hardware. AArch64-first stays a provisional direction and seL4-first a
  working hypothesis, subject to the reopened architecture decision. QEMU TCG is acceptable for early
  development and testing and is not equivalent to hardware acceleration or to physical validation. The
  nightly Rust trigger was acknowledged for this experiment only, and the long-term toolchain policy is
  **unresolved**.

## The A1 rerun in one paragraph

The spike `Cargo.lock` was the demo's newer lock and resolved six crates.io versions that the owner had not
approved (deviation D13). The owner chose to restore the approved versions. Four offline `cargo update
--precise` commands did that, and nothing else in the lock changed. Rerun result: kernel and loader hashes are
identical to the original. The root task is identical across the rerun's two builds but differs from the
original (`a7c6be9a…` to `64fcc25c…`): 8 of 4,795 instruction words differ, all address computations, because
Cargo's hashed build-script directory name, embedded in a panic-location string, depends on the dependency
set (inferred: Cargo's behaviour, measured only as a one-variable change of the lock). All 782 differing image bytes outside the device-tree seeds are root-task bytes. **A root-task hash is a
function of the lock file, so name the lock when quoting one.** No behavioural test exists, because the A1
image has never booted. The original lock and original build outputs are kept locally in the gitignored
`spikes/sel4-feasibility/external/a1-original-build/`, and the lock is in Git at `b563904`.

## Independent reviews of PR 8

Two reviews returned NOT MERGE-READY (F1 to F7, then F2 plus N1 and N2). The owner ruled on every finding
that needed a decision, and the corrections are in the PR. F2, the only one that needed new work, is resolved
by the rerun above. **A third, final delta review covers the rerun and the changes after `d1b0f46`.** Read
`gh pr view 8` and the review result before relying on any statement here that it passed. The conditional
merge authorization applies only if the reviewer explicitly returns MERGE-READY, all required checks pass on
the final head, the evidence verifier passes, and no material finding remains.

## Authorizations in force

Source: the owner's messages in this conversation, and the plan's 2026-11-08 Amendments.

- **Used:** merging PRs 5 and 6; pushing the spike branch and opening PR 7; the narrow replacement of PR 7
  and its branch; opening PR 8; pushing corrections to PR 8; restoring the six lock-file versions; one A1 rerun;
  a local push safeguard.
- **Conditional, may be unused:** merging PR 8, on the conditions above.
- **Still in force:** the A3 stop condition. Decisions 1 to 7, P1 and P2 are approved. P3 deferred, P4
  declined, P5 deferred to the A5 design gate.
- **Not authorized:** A2a, A4, A5, the comparator, Tiers 2 and 3, any kernel change, further tool installs,
  any further experiment or rerun, any architecture change, relaxing a criterion, another history rewrite or
  force-push, and a GitHub Support request (the owner declined for now).

## Pending approvals (all the owner's)

1. **The next architectural decision**, after the A3 Fail with decision rule 2: what it means for the text of
   ADR 0002 and ADR 0004 (no ADR was edited), and which bounded experiment or analysis comes next.
2. The long-term toolchain policy (nightly Rust).
3. Review of the tooling deviations in `results/deviations.md` (D1 to D16). Only rows marked owner-approved
   are approved. The `cargo deny` note (`RUSTSEC-2024-0449`, host-side only, policy unchanged) is part of it.
4. The A5 question (class D or Investigate), open to the A5 design gate.

## Blockers and conflicts

- **The A3 stop condition** blocks everything after A1 and the rerun.
- **Remaining privacy exposure.** `refs/pull/7/head` resolves to `c99300d`, and the original commits stay
  fetchable by SHA from the public repository, and in clones or forks made while public. This is not erasure.
  `main` never held it. [Measured: `git ls-remote`, `gh api`]
- Earlier open items: a base-controlled `pull_request_target` check (`m0-acceptance.md`); CI runners use QEMU
  8.2.2 against the spike's pinned 11.1.3.

## Verified results

| Command | Tree | Result |
|---|---|---|
| `cargo xtask check` | before the commit that holds this file | "check: all 12 steps passed", macOS arm64 |
| `spikes/sel4-feasibility/verify-evidence.py` | same | 40 of 40 passed, including checks against the repository's `Cargo.lock`. Mutation-tested: injected faults in the config, privacy, manifest and rerun checks were all caught |
| A1 rerun | corrected lock | two clean builds, 38.5 s and 39.4 s. See `A1-rerun.md` |
| Local push safeguard | this clone | 14 crafted cases and 3 `git push --dry-run` cases behaved as intended (see D16) |

**Not verified:** CI on any head after `d1b0f46`; `cargo xtask boot` locally; any seL4 run on a host other
than this M2 Pro; whether either root task runs (the A1 image has never booted); whether the 4-node SMP kernel
boots under any machine setting; cross-path and cross-machine reproducibility.

## Next actions

1. Run `gh pr view 8`, `gh pr checks 8` and `git log -3 main` to see whether PR 8 merged.
2. **Needs the owner:** the architectural decision above. Nothing further runs until then.
3. **Authorized now:** read-only checks and answering questions. Nothing that runs an experiment, installs a
   tool, changes the lock file or changes Git state beyond what the owner asks.

## Context not recorded elsewhere

- **Unsanitized history is kept locally** on branch `local-only/s1-workspace-unsanitized` (no upstream),
  retained on the owner's instruction. **Never push it.** Raw logs are in the gitignored
  `spikes/sel4-feasibility/results-raw/`, and a backup `fyrkat-s1-raw-evidence-2026-11-08.tar.gz` (SHA-256
  `768af917…`) sits next to the repository directory.
- **A local safeguard now guards that history** (deviation D16): this clone's local config sets
  `core.hooksPath` to the untracked `.git/fyrkat-hooks/`, whose `pre-push` refuses the five unsanitized commits
  and any `local-only/*` ref, then runs the global pre-push hook unchanged. Global Git configuration was not
  modified. It checks commit ancestry and ref names only: `git push --no-verify`, rewritten copies of the commits, pushes of raw tree or blob objects and other clones bypass it. Undo: `git config --local --unset core.hooksPath && rm -rf
  .git/fyrkat-hooks`. A fresh clone does not have it.
- The preserved original A1 run (binaries, lock) is in `spikes/sel4-feasibility/external/a1-original-build/`,
  and the rerun's first build in `external/a1-rerun-build1/`. Both are gitignored. The root-task ELF embeds the
  builder's absolute build path, so **never publish a root-task binary**, only its hash.
- The sanitizer reads the user, home and host names from the machine it runs on. Rerun it only there. It fails
  closed on an unterminated tap warning, and writes nothing unless every file sanitizes.
- Local branches `spike/s1-prerequisites` and `docs/agents-research-section` belong to squash-merged PRs, so Git does not list them as merged. They can go once the owner agrees.
- A global pre-commit hook outside this repo prints "Broken pipe" noise on commit. Commits still succeed.
- Never put the home path or user name in PR text, docs or logs. Sanitize with `sanitize-evidence.py` first.
- The `reviewer` and `researcher` agents have Bash, so "read-only" is not enforced. Check `git status` after
  they run. Start a fresh session at the repository root and run `/fyrkat-resume`.
