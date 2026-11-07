# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win
over it. It records approvals and grants none. The previous handoff described the state before the
S1 branches were pushed and is replaced entirely.

## Snapshot

- **Date:** 2026-11-08.
- **Written from:** branch `spike/s1-prerequisites`, whose HEAD before this file's commit is `a564869`,
  seven commits on top of `main` at `caf465d`. [Measured: git]
- **Other branch:** `docs/agents-research-section`, HEAD `6ef78c3`, three commits on top of `main`,
  touching only `AGENTS.md`. [Measured: git]
- **Remote:** both branches are pushed and track their upstream. `origin/main` is still `caf465d`.
  [Measured: `git ls-remote --heads origin`]
- **Pull requests:** 5 (`docs/agents-research-section`) and 6 (`spike/s1-prerequisites`) are OPEN and
  not merged. 1, 3 and 4 are MERGED, 2 is CLOSED. [Measured: `gh pr list --state all`]
- **CI:** on both PRs the three required checks passed at the heads first pushed (`6ef78c3` and `0be808e`). PR 6 has since received `a564869` and this file, and their CI result is not recorded here. The checks are: `check and boot (ubuntu
  x86-64)`, `boot (ubuntu arm64)` and `security-sensitive paths`. Both PRs report merge state CLEAN.
  [Measured: `gh pr checks`, `gh pr view`] This file's own commit is pushed afterwards and CI runs
  again on it. Its result is not recorded here.
- **Commits:** every commit this session carries a `Signed-off-by` line and a signature header.
  GitHub's "verified" display and branch-protection signature enforcement were not checked. The
  protection API reports `required_signatures` as disabled. [Measured: `git cat-file`, GitHub API]

## Milestone status

**M0 is complete** (owner declaration, 2026-11-07, `docs/roadmap.md`). **S1 is planned and not
started.** M1 cannot be finalized before ADR 0004 is decided. ADR statuses: 0001 Part A Provisional,
Part B Withdrawn. 0002 and 0003 Provisional. 0004 Proposed. None is Accepted. [Measured: grep]
The spike plan is approved for the text at `46a90fa`. It does not authorize any experiment.

## Done this session

- **Split:** the AGENTS.md research policy is PR 5, on its own. The S1 prerequisites, C1 and C2
  methods, research notes and decision package are PR 6. They stay one PR because they link to each
  other, and the markdown-link check would fail on a split.
- **Independent review** (`reviewer`, fresh context) of the corrected findings and method files:
  1 High, 9 Medium, 10 Low. The substantiated ones are fixed in `0be808e` (S1) and `6ef78c3`
  (AGENTS.md). The High finding was that the decision package recommended a looser reading of class D
  and of the A5-arm Pass without saying so. It now recommends no loosening, and the looser reading is
  proposed Amendment P5. A second finding was that choice 1a made W1 alone carry the C1 criterion,
  which the plan's wording does not support. It is now W1 and W2 both.
- **Re-review of those fixes** (second `reviewer`, narrow): 3 High, 4 Medium, 4 Low, mostly errors
  in the first round of fixes. Fixed in `a564869`: an off-by-one in the F4 shuffle; a false premise
  that the seL4 kernel zeroes on frame retype (it clears memory when an untyped is reset, checked
  against seL4 `62e345c` `objecttype.c` and `untyped.c`); the unspecified W2 fill and sum, now fixed
  before the first run; stopped-run rules; the two strict readings of the A5 question; and A1
  approach counting. **`a564869` has had no further independent review.**
- **Not changed:** any ADR, any plan criterion, the plan file, `.github/`, `xtask/`, `deny.toml`.

## Authorizations in force

Source: the owner's message of 2026-11-08 in this conversation, unless a document is named. The
spike plan's Amendments record only the plan approval. The authorizations below are recorded
nowhere else, so the owner may want them added to the plan's Amendments or to the acceptance record.

- **Spike plan approval** (plan and criteria only): the plan's Amendments, "Owner approval of the plan".
- **Document-only S1 preparation, local commits, and the `AGENTS.md` research section:** as in the
  previous handoff, on the owner's earlier messages.
- **This session:** split the work, review it, fix substantiated findings, commit this file, push the
  two branches, open their PRs and verify CI. Merging was **not** authorized.
- **Not authorized:** any experiment or spike execution. Installing a tool or dependency. A new
  dependency. Changing an Accepted ADR. Merging any PR. Class 3 kernel changes, including K4.
  Relaxing any criterion. Another broad research phase.

## Pending approvals

All are the owner's. Recommended defaults are in `docs/research/s1-decision-package.md`.

- **Merge PR 5 and PR 6.** `AGENTS.md` is a security-sensitive path, so PR 5 needs owner approval.
- **Decisions 1 to 8 and Amendments P1 to P5** in the decision package. Recommended: yes to 1 to 8,
  yes to P1 and P2, P3 at the owner's wish, decline P4 and P5 for now.
- **An interpretation before A5:** the looser reading of class D and the A5-arm Pass (P5). The
  default is no loosening. It is decided at the A5 design gate.

## Blockers and conflicts

- **None between this file, Git and the ADRs.**
- **Blocked:** spike execution is not authorized, and the method files are drafts. Stage C needs them
  on `main` first, so PR 6 has to merge before any C1 or C2 run.
- **Known issue in the approved plan:** the sentence "about 850 cycles is about 0.25 µs at 3.4 GHz"
  appears to mix an AArch64 cycle count with an x86 clock. Proposed as Amendment P2.
  [Inferred: the plan's source is not named. The 3.4 GHz clock is on the x86-64 rows of the
  performance page.]
- **Open follow-up from M0:** a base-controlled `pull_request_target` version of the
  security-sensitive paths check. The current job is a notice and not an access control, because the
  workflow file comes from the PR. [Documented: `m0-acceptance.md`, Known limits]
- **CI and the spike use different QEMU versions:** CI runners have QEMU 8.2.2 from Ubuntu packages.
  The spike plan pins 11.1.3 from Homebrew. [Measured: `m0-acceptance.md`, CI facts]

## Uncommitted changes

This file, until the owner's session commits it. Otherwise the working tree was clean.

## Verified results

| Check | Commit | Result |
|---|---|---|
| `cargo xtask check` | `0be808e` (S1 branch) | "check: all 12 steps passed", including markdown links and spike isolation. macOS arm64, local |
| `cargo xtask check` | `6ef78c3` (AGENTS.md branch) | "check: all 12 steps passed". macOS arm64, local |
| CI, PR 5 and PR 6 | `6ef78c3`, `0be808e` | The three required checks passed on each. `gh pr checks` |
| Independent review | `7833442` and `566d970` trees | 1 High, 9 Medium, 10 Low. Substantiated findings fixed |
| Independent re-review of the fixes | `0be808e`, `6ef78c3` | 3 High, 4 Medium, 4 Low, all in the S1 fixes. `6ef78c3` (AGENTS.md) had none. The review fetched seL4 sources read-only |
| `cargo xtask check` | `a564869` | "check: all 12 steps passed". macOS arm64, local |
| Review of `a564869` | | **Not done** |

**Not verified:**

- `cargo xtask boot` locally. Nothing here changes boot, firmware or CI. CI ran the boot jobs.
- Every external claim in the research notes that the reviewers could not check offline: the sel4bench
  page, the rust-sel4 README and lock file, QEMU `smmuv3.c`, the Debian image hash, the
  `sel4test-manifest` commit and most prior-art sources. The notes label these.
- Whether GCC 16, CMake 4 or Python 3.15 work with seL4 17.0.0. That is an A1 finding.
- GitHub's "verified" status for the commits, and branch-protection signature enforcement.

## Next actions

1. **Needs approval:** the owner answers the checklist in `docs/research/s1-decision-package.md`.
2. **Needs approval:** merge PR 5 and PR 6. Merge order does not matter. PR 6 is needed on `main`
   before any C1 or C2 run.
3. **After approval only:** apply P1 and P2 as Amendment entries in the plan (not inline edits),
   create the spike workspace files listed in decision 5, install Tier 1, run A1 following the
   approach order in decision 8, then A3, A4 and A2a, and stop with a report. A5 waits for a reviewed
   design and its own authorization.
4. If the owner changes a recommendation, update the package and the method files, and send the
   change to a fresh `reviewer` pass.

## Context not recorded elsewhere

- The owner's goal, stated in conversation, is a secure, modern, high-performance, AI-native OS that
  does not stop at existing solutions. The AGENTS.md section in PR 5 records the working rules.
  "AI-native" is not yet defined in the repository.
- The `reviewer` and `researcher` agents have Bash. A read-only rule is not enforced. Check
  `git status` after they run. Both reviews this session left the repository unchanged.
- Session memory is per launch directory. Start a fresh session at the repository root and run
  `/fyrkat-resume`.
