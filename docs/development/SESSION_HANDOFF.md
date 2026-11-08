# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win
over it. It records approvals and grants none. The authoritative record of the owner's S1 decisions is
the last entries in the [spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-08.
- **Written from:** branch `spike/s1-prerequisites` (PR 6), before the PR is merged. Read `git log` and
  `gh pr view 6` for what happened after. [Measured: git]
- **Merged:** PR 5 (`AGENTS.md` research policy) as `a79c847` on `main`, by squash. PRs 1, 3 and 4
  are merged and 2 is closed. [Measured: `gh pr list --state all`]
- **CI:** the three required checks passed on PR 5 and on earlier PR 6 heads. They are re-run on each
  push. [Measured: `gh pr checks`]
- **Commits:** carry a `Signed-off-by` line and a signature header. GitHub's "verified" display was not
  checked, and branch protection does not require signatures. [Measured: `git cat-file`, GitHub API]

## Milestone status

**M0 is complete.** **S1 is planned and not started: nothing has been installed, built or run.** M1
cannot be finalized before ADR 0004 is decided. ADR statuses: 0001 Part A Provisional, Part B
Withdrawn. 0002 and 0003 Provisional. 0004 Proposed. None is Accepted. The spike plan is approved for
the text at `46a90fa`.

## Owner decisions of 2026-11-08 (recorded in the plan's Amendments)

- Approved: decisions 1 to 7, with choices 1a (W1 and W2 both carry the C1 criterion), 1b (the timing
  kernel is a measurement-only configuration outside the A2 matrix) and 1c (K0 is
  `AARCH64_verified.cmake`). Approved: P1 (rust-sel4 `v6.0.0`, `nightly-2026-08-21`) and P2 (the
  850-cycle wording correction).
- Decision 8 is authorized **conditionally**: A1, A3, A4 (Sonnet) and A2a (Opus). Conditions: the
  final independent review of PR 6 passes, PR 6 is merged, only Tier 1 is installed, and each
  experiment's entry criteria are confirmed first.
- P3 deferred to Stage D. P4 declined. P5 deferred to the A5 design gate. **A5, the comparator, and
  Tiers 2 and 3 are not authorized.**

## Answers recorded after the final review

- **`bindgen`:** the owner approved 0.72.1 as locked at `v6.0.0` (the tree locked at `c819c27`). The
  0.73.2 first written in decision 3 was the `main` version.
- **Member crates:** the owner approved member-crate `Cargo.toml` files under
  `spikes/sel4-feasibility/` only, each listed in the A1 results. `.cargo/config.toml` and `build.rs`
  still stop and ask.
- **Two C2 method changes from the final review** (explicit zero in F3, untyped reset before every
  timed phase) make the method stricter and change no criterion.
- **The A5 question** (class D or Investigate) stays open to the A5 design gate. Choosing Investigate
  where class D applies would itself need an Amendment.
- **If pip must build `pyyaml` or `pyfdt` from source,** their build tools are not on the approved
  list: the work stops and asks.

## Blockers and conflicts

- **None between this file, Git and the ADRs.**
- Follow-up from M0: a base-controlled `pull_request_target` version of the security-sensitive paths
  check. [Documented: `m0-acceptance.md`, Known limits]
- CI runners have QEMU 8.2.2. The spike plan pins 11.1.3 from Homebrew. [Measured: `m0-acceptance.md`]

## Verified results

| Check | Commit | Result |
|---|---|---|
| `cargo xtask check` | PR 6 head when written | "check: all 12 steps passed". macOS arm64, local |
| Independent reviews of PR 6 | `7833442` to `d61562c` | Five passes. The last two said NOT MERGE-READY (2 High, 4 Medium, 8 Low; then 2 Medium, 5 Low), all text fixes. **A final confirmation is required before merging PR 6** |

**Not verified:** `cargo xtask boot` locally; whether GCC 16, CMake 4 or Python 3.15 work with seL4
17.0.0 (that is an A1 finding); GitHub's "verified" status of commits.

## Next actions

1. Final confirmation of the PR 6 fixes, then merge PR 6 if it passes with no unresolved material finding.
2. Create the approved spike workspace files, install Tier 1 with the recorded pins and the Homebrew
   guards in decision 7, and run A1 following the approach order in decision 8. Raw evidence under
   `spikes/sel4-feasibility/results/`. Stop with a report. Then A3, A4 and A2a.
3. Anything outside the approved scope stops and asks.

## Context not recorded elsewhere

- The owner's goal is a secure, modern, high-performance, AI-native OS that does not stop at existing
  solutions. The `AGENTS.md` research section records the working rules.
- The `reviewer` and `researcher` agents have Bash. A read-only rule is not enforced. Check `git status`
  after they run.
- Start a fresh session at the repository root and run `/fyrkat-resume`.
