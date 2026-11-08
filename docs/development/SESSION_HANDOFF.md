# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win over it.
It records approvals and grants none. The owner's S1 decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-08.
- **Branch:** `spike/s1-workspace-sanitized`. `main` is `4fb92a1`. Commits above `main`, oldest first:
  `b563904`, `899d841`, `5937762`, `24634be` (on GitHub since the first push of this session), `05c40b2`,
  `6009f43`, then the commit that holds this file. Check `git log main..HEAD` and `git status -sb` for the
  live state. [Measured at the time of writing]
- **Open PR:** **PR 8**, not merged. On `24634be` all three required checks passed (`check and boot (ubuntu
  x86-64)`, `boot (ubuntu arm64)`, `security-sensitive paths`). **CI on the newer head is not recorded here**:
  run `gh pr checks 8`. [Measured: `gh pr checks 8` at `24634be`]
- **Other PRs:** 1, 3, 4, 5, 6 merged. 2 and 7 closed. PR 7 held the same work with unredacted logs.
- **Remote branches:** only `main` and the PR 8 branch.

## Milestone status

- **M0:** complete (owner declaration 2026-11-07, `docs/roadmap.md`).
- **S1 (roadmap exit: the owner decides ADR 0004; M1 cannot be finalized before it):** in progress and
  **stopped at the A3 gate**. Nothing else is decided.

| Experiment | Outcome | Record |
|---|---|---|
| A1 build on this Mac | **Pass**, label U. Accepted by the owner | `spikes/sel4-feasibility/results/A1.md` |
| A3 EL1 and HVF | **Fail**, label U, for unmodified non-hypervisor seL4 17.0.0 under HVF on one Apple M2 Pro. **Re-confirmed by the owner** after the SMP correction. The mislabeled "4 vCPU" image is not valid SMP evidence | `results/A3.md` |
| A2a, A4, A5 | Not started | |

- **ADR statuses:** 0001 Part A Provisional, Part B Withdrawn. 0002 and 0003 Provisional. 0004 Proposed. None
  is Accepted. No ADR text was edited. [Measured: ADR Status lines]
- **A3 in one line:** unmodified seL4 halts in kernel init under HVF with 1 vCPU (the guest reports 8-bit
  ASIDs, the kernel needs 16-bit). It passes sel4test under TCG (124 passed, 59 disabled). A real 4-node SMP
  kernel stops earlier in the elfloader (PSCI over HVC) under HVF and TCG, and has not booted anywhere.
- **Owner rulings recorded in the Amendments:** decision rule 2 **applies to the tested HVF configuration**
  (a pass would need a prohibited Class 3 change), and is **not** generalized to TCG or other hardware.
  AArch64-first stays a provisional direction and seL4-first a working hypothesis, subject to the reopened
  architecture decision. QEMU TCG is acceptable for early development and testing and is not equivalent to
  hardware acceleration or to physical validation.

## Independent review of PR 8

The review returned **NOT MERGE-READY**. Status of its findings:

| Finding | Status |
|---|---|
| F1 decision rule 2 | Owner ruled. Recorded in A3 and the Amendments |
| **F2 six `Cargo.lock` versions** | **Unresolved. Needs the owner's decision.** Investigated read-only in [deviations D13](../../spikes/sel4-feasibility/results/deviations.md). The original lock and A1 results are unchanged |
| F3 privacy wording | Fixed in `EVIDENCE-PRIVACY.md` and `deviations.md`: not erased, `c99300d` still resolves by SHA |
| F4 stale A3 status | Fixed |
| F5 unverifiable configuration claims | Fixed: sanitized excerpts `A3/41` and `A3/42`, and the verifier checks their contents |
| F6, F17 PR text | The PR description needs the two corrections. Check `gh pr view 8` |
| F7 nightly Rust | Owner acknowledged. Recorded in A1 and the Amendments. The long-term toolchain policy is **unresolved** |
| F8 this handoff | Refreshed here |
| F9 roadmap | Fixed |
| F10 `unwrap` and `assert_eq!` | One-time owner exception, deviation D11 |
| F11, F12 sanitizer and verifier | Fixed. The verifier now has 32 checks and was mutation-tested |
| F13 to F16 | Fixed or recorded (A1, A3, `A3/shim-era/README.md`, D14) |
| F18 the local unsanitized branch | Not changed. The owner's choice |

A **focused delta review** is required next. The conditional merge authorization applies only if every material
finding, F2 included, is resolved and the reviewer explicitly returns MERGE-READY.

## Authorizations in force

Source: the owner's messages in this conversation, and the plan's 2026-11-08 Amendments.

- **Used:** merging PRs 5 and 6; pushing the spike branch and opening PR 7; the narrow replacement of PR 7
  and its branch; opening PR 8; pushing `24634be` alone; the documentation, evidence and verifier corrections
  for the review, with committing and pushing them to PR 8.
- **Conditional, not yet met:** merging PR 8, only if the delta review explicitly returns MERGE-READY, all
  required checks pass on the final head, the evidence verifier passes, no material finding is unresolved,
  and **F2 is resolved**.
- **Still in force:** the A3 stop condition. Decisions 1 to 7, P1 and P2 are approved. P3 deferred, P4
  declined, P5 deferred to the A5 design gate.
- **Not authorized:** A2a, A4, A5, the comparator, Tiers 2 and 3, any kernel change, further tool installs,
  resuming experiments, an A1 re-run or any regeneration of dependencies or the lockfile, any architecture
  change, relaxing a criterion, another history rewrite or force-push, and **a GitHub Support request** (the
  owner declined for now).

## Pending approvals (all the owner's)

1. **F2:** approve the six resolved versions as they are, or restore the approved ones (which needs a new A1
   run and its own authorization). See deviations D13.
2. After the delta review: merge PR 8, or not.
3. Review the other tooling deviations (`deviations.md`, D1 to D14) and the `cargo deny` note
   (`RUSTSEC-2024-0449`, host-side only, policy unchanged).
4. The long-term toolchain policy (nightly Rust), and what the A3 Fail with rule 2 means for ADR 0002 and
   ADR 0004 text. No ADR was edited.
5. The A5 question (class D or Investigate), open to the A5 design gate.
6. Whether to keep the local unsanitized branch and the raw-evidence tarball (see Context).

## Blockers and conflicts

- **F2** blocks the merge.
- **The A3 stop condition** blocks everything after A1.
- **Remaining privacy exposure.** `refs/pull/7/head` resolves to `c99300d`, and the original commits stay
  fetchable by SHA from the public repository, and in clones or forks made while public. This is not erasure.
  `main` never held it. [Measured: `git ls-remote`, `gh api`]
- Earlier open items: a base-controlled `pull_request_target` check (`m0-acceptance.md`); CI runners use QEMU
  8.2.2 against the spike's pinned 11.1.3.

## Verified results

| Command | Tree | Result |
|---|---|---|
| `cargo xtask check` | before `6009f43` | "check: all 12 steps passed" (hook tests 80/0; sensitive-paths 28/0), macOS arm64 |
| `spikes/sel4-feasibility/verify-evidence.py` | before `6009f43` | 32 of 32 passed, as the author and with a CI-style user. Mutation test: 5 of 5 injected faults caught |
| `cargo deny` on the spike workspace | scratch copies | advisories, bans, sources ok with the original lock and with the restored lock |
| Local commit signatures | `24634be`, `05c40b2`, `6009f43` | each has a signature and a DCO trailer. GitHub's own verification is not re-read here |

**Not verified:** CI on any head after `24634be`; `cargo xtask boot` locally; any seL4 run on a host other
than this M2 Pro; whether restoring the approved lock changes the root-task binary; whether the 4-node SMP
kernel boots under any machine setting; whether a GitHub Support request would remove retained references.

## Next actions

1. Check `gh pr checks 8` on the pushed head and `gh pr view 8` for the PR text corrections.
2. Run the focused delta review (`reviewer` agent, fresh context). Then check `git status` for stray edits.
3. **Needs the owner:** decide F2. Nothing merges before that.
4. **Authorized now:** read-only checks and answering questions, plus the corrections the delta review finds
   within PR 8's scope. Nothing that runs an experiment, installs a tool, or changes the lockfile.

## Context not recorded elsewhere

- **Unsanitized history is kept locally** on branch `local-only/s1-workspace-unsanitized` (no upstream).
  **Never push it.** Raw logs are in the gitignored `spikes/sel4-feasibility/results-raw/`, and a backup
  `fyrkat-s1-raw-evidence-2026-11-08.tar.gz` (SHA-256 `768af917…`) sits next to the repository directory.
  The hooks block pushes to `main` only, so an accidental push of that branch would not be stopped.
- The sanitizer reads the user, home and host names from the machine it runs on. Rerun it only there. It
  now fails closed on an unterminated tap warning.
- Stale local branches `spike/s1-prerequisites` and `docs/agents-research-section` are merged and can go.
- A global pre-commit hook outside this repo prints "Broken pipe" noise on commit. Commits still succeed.
- Never put the home path or user name in PR text, docs or logs. Sanitize with `sanitize-evidence.py` first.
- The `reviewer` and `researcher` agents have Bash, so "read-only" is not enforced. Check `git status` after
  they run. Start a fresh session at the repository root and run `/fyrkat-resume`.
