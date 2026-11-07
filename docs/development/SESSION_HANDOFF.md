# Session handoff

Snapshot from 2026-11-07, written when the session that built M0 locally ended. This is a
status note, not a source of truth: decisions live in [ADRs](../adr/README.md), and repository
state lives in Git. Check this file against them. It records the owner's approvals below, and
grants none of its own.

## Current status, 2026-11-07 (supersedes the snapshot below)

The sections below were written before publication and are kept as history. Where they
conflict with this section, this section is right. Check it against Git and GitHub.

- **Published:** `MHusted01/fyrkat` is public. `main` is the first commit. PR 1 holds the
  foundation, and the owner merges it.
- **Name screening:** done on 2026-11-07 against TMview (EUIPO, DKPTO, USPTO) and web search.
  No software-related FYRKAT conflict. One live US mark, Pi-Design AG 79093756, covers
  classes 8, 11 and 21. WIPO Madrid and non-EU, non-US offices were not searched. This is
  not legal clearance.
- **History review:** done before publication. All commits are signed with one noreply
  identity. No secrets, no deleted files, no unreachable objects. One third-party address
  sits in a public mailing-list URL, covered by the owner-approved exception in `AGENTS.md`.
- **Plugins:** disabled at project level and confirmed in a fresh headless session.
- **CI on PR 1:** all three required checks passed. `/dev/kvm` was present on the x86-64
  runner and absent on arm64. Both boot jobs use TCG. The runners have QEMU 8.2.2.
- **Protection on `main`:** read back through the API: PR required, three named checks,
  conversations resolved, 0 approvals, admins enforced, linear history, no force pushes or
  deletion, squash only. A failing PR was blocked and its merge refused.
- **Not yet shown:** a direct push to `main` being rejected. The owner runs that test.
- **Review fixes (owner-authorized, on PR 1):** the push hook now parses `git push` forms and
  no longer trips on commit messages. The ADR hook applies each edit and compares status
  lines, and also covers `edits[]` payloads and shell writes. The sensitive-paths script handles
  non-ASCII names, `xtask/`, `.cargo/` and every `Cargo.toml` and `Cargo.lock`, and CI runs the
  base branch's copy of it where one exists. Both have regression tests in `cargo xtask check`.
  GitHub now has strict required checks, SHA pinning enforced, Actions limited to GitHub-owned
  actions, Dependabot alerts and security updates, and approval for all external contributors.
- **Spike plan:** Draft 2, **not approved**, and no experiment may start. It adds an assurance
  matrix, kernel change Classes 0 to 3, fixed outcome precedence, a consequences table, an
  A5-arm and A5-x86 split, and committed method files for C1 and C2. The owner reviews it
  before approving. Its Amendments section lists what changed and why.
- **Known limits, not fixable here:** the sensitive-paths check is a notice, because the workflow
  file comes from the PR. With one maintainer GitHub cannot require a second approver. A
  base-controlled `pull_request_target` check is a follow-up for after PR 1 merges, because it
  needs the workflow to exist on `main` first.
- **M0 is not complete.** Remaining: the owner's review of the spike plan, the direct-push test,
  and merging PR 1.

## Gate 2 decision

**Approved with conditions.** The owner decided this in a separate planning conversation and
relayed it on 2026-11-07. **Nothing has been published.** The session that wrote this file was
told to prepare this handoff only, so all of the following is still to do.

1. **Publication.** Approved: create the public `MHusted01/fyrkat` repository, push the approved
   foundation, configure branch protections, enable private vulnerability reporting, and verify
   enforcement. **Condition:** perform a final secrets, privacy and Git-history review before
   publishing.
2. **Name screening.** Before publication, perform a focused EUIPO/TMview, Danish trademark and
   USPTO screening for "Fyrkat" and "Fyrkat OS", especially software-related classifications.
   **Pause and report any material conflicts.** This is not legal clearance.
3. **Plugins.** Approved: disable irrelevant Claude Code plugins at the Fyrkat project level
   only. Do not change global settings. Verify the result in a fresh session.
4. **Spike criteria.** Revised, as set out under [Spike criteria](#spike-criteria).
5. **CI.** Validate actual GitHub Actions results, including Linux runner limitations and QEMU
   behaviour. Do not assume `/dev/kvm` is available.
6. **Final review.** Conduct the adversarial M0 review after CI is running, and resolve material
   findings before declaring M0 complete.

## M0 status

**In progress.** Local work is finished, and remote validation has not started.

| Exit criterion | Status |
|---|---|
| Fresh clone passes `cargo xtask check` | Done at commit `9f3721e`; rerun before publishing |
| CI runs on a real PR, and a failing change is blocked | Not started |
| Direct push to `main` rejected, protections confirmed through the API | Not started |
| ADRs 0001 to 0003 ruled on, spike plan approved | Ruled on at Gate 1; plan needs the Gate 2 revisions |
| Claude Code configuration confirmed in a real session | Partly done, see below |
| Adversarial review of the setup complete | Not started, runs after CI |

## Verified work

All run on 2026-11-07 against commit `9f3721e`, on an Apple M2 Pro with macOS 27.2.

| Check | Result |
|---|---|
| Fresh clone, tools built from scratch | Passed |
| `cargo xtask check` | 12 of 12 steps passed |
| Tests | 46 of 46 passed |
| `cargo xtask boot`, TCG | AArch64 and x86-64 passed |
| `cargo xtask boot --accel hvf` | AArch64 passed; x86-64 falls back to TCG |
| Action SHA pins | Match GitHub |
| Secret and personal data scan of files | None found |
| Headless Claude Code session in the repository | Sonnet default, 0 ECC agents or skills, project agents and skills load |
| Push hook in a headless session | Blocked `git push origin main` |

**Not verified:**

- Any CI run, including whether runners expose `/dev/kvm`.
- Firmware paths on Debian and Ubuntu.
- `rustup toolchain install` reading `rust-toolchain.toml` in CI.
- The ADR protection hook in a live session (its scripted tests pass).
- An interactive session: this needs workspace trust, which also activates `permissions.allow`.
- Git history: the file scan above did not cover commit metadata or history.

## Git state

- **Branch:** `m0/foundation`, at `9f3721e`.
- **`main`:** points to the first commit, `ee063e6`.
- **Remote:** none. Nothing has been pushed.
- **Commits:** 7, all signed and signed off:

```text
ee063e6 chore: add licences and ignore rules
fcae0cf docs: record architecture research and decisions
d4f7668 chore: add boot latency spike
a5f9c42 chore: add Cargo workspace, xtask and boot smoke test
9d099ce ci: add workflows, issue forms and dependency updates
c57df8d docs: add project documentation and engineering standards
9f3721e chore: add project Claude Code configuration
```

- **Uncommitted, deliberately:** this file, and the resuming note in `AGENTS.md`. `AGENTS.md` says
  agents commit only when asked. Gate 2 approves pushing the foundation, so committing this work
  for that push looks in scope, but that is an inference. Confirm it with the owner.
- **Local only:** SSH commit signing is in this clone's `.git/config`, so a new clone needs it
  set again. `.tools/` and `target/` are gitignored.

## ADR status

**No ADR is Accepted.**

| ADR | Topic | Status |
|---|---|---|
| 0001 Part A | Capability microkernel, hardware isolation | Provisional |
| 0001 Part B | Build a new Rust kernel instead of adopting seL4 | **Withdrawn** |
| 0002 | AArch64 first, x86-64 required second | Provisional, open seL4 conflicts |
| 0003 | UEFI with a minimal Rust loader | Provisional, open seL4 conflicts |
| 0004 | Kernel foundation | Proposed, working hypothesis only |

M1 is renamed "Boot path", and cannot be finalized until ADR 0004 is decided.

## seL4-first hypothesis and spike

> For Fyrkat's first system, unmodified seL4 with Rust user-space services is a stronger
> foundation than a custom Rust kernel.

This is not a commitment. The [review](../research/sel4-adversarial-review.md) explains why Part B
was withdrawn. No experiment has run.

**Stages:** A (blockers: build, assurance surface, EL1 under HVF, UEFI, SMMUv3), B (lifecycle,
revocation, pager, driver restart), C (performance), D (comparison, Opus). Stop and report after
each stage.

**Prerequisites:** `nightly-2026-10-28`, which rust-sel4 pins, is not installed. The rust-sel4
commit is not pinned yet. Docker, CMake, Ninja, dtc and QEMU are present. No cross GCC is
installed.

### Spike criteria

**Update, 2026-11-07:** the [spike plan](../research/sel4-spike-plan.md) was revised under Gate 2
decision 4 and the change is recorded under its Amendments section. The owner has not yet
reviewed the wording. The table below is the original brief, kept for comparison.

| Item | Text in the plan today | Gate 2 decision |
|---|---|---|
| A2 assurance | Pass at 90% function identity, Fail below 70% | **Remove.** Replace with an assessment of proof applicability, configuration differences, trusted computing base changes, and unverified components |
| C1 IPC | Pass at 1 µs or less, Fail over 3 µs | 1 µs or less stays a **provisional target, not an automatic rejection threshold.** Define hardware, workload, measurement method and baseline |
| C2 page faults | Pass at 3x Linux, Fail over 5x | Measure with reproducible, representative workloads. 3x and 5x are **investigation thresholds until justified** |
| Kernel patches | 1,550-line hard limit | **Investigation trigger, not a hard limit.** Evaluate by security impact, complexity, proof implications and maintenance burden |

**Also required by this decision:** preserve falsifiable acceptance criteria, and define concrete
functional blockers and unacceptable assurance regressions before experimentation.

**Passages in the plan that conflict and must change:**

- Decision rule 6, which makes a C2 failure falsify the hypothesis.
- "Exceeding it is treated as an unacceptable modification", under the kernel budget.
- The A2 Pass, Conditional and Fail criteria, and the "A2 fails" row in the reopening table.
- The C1 Fail criterion.

**Not addressed by Gate 2, so unchanged:** B1 reclamation, B2 revocation (1 ms timer delay), B3
pager, B4 driver restart (median 500 ms, worst 2 s), C3 scaling (4x and 2x at 8 vCPUs), the V, U,
M and S labels, and the list of kernel changes that are unacceptable at any size.

## Publication tasks

Approved under Gate 2 decision 1, once the preconditions in the next steps are met:

1. Create the public repository and push `main`, then `m0/foundation`.
2. Open `m0/foundation` as the first PR.
3. Enable private vulnerability reporting.
4. Apply protections to `main`: PR required, required CI, resolved conversations, 0 approvals,
   enforced on admins, no force pushes or deletion, linear history, squash merges.
5. Confirm each protection through the API. Do not claim one is active until it is confirmed.
6. Inspect actual CI results on both Linux runners, including QEMU behaviour and whether
   `/dev/kvm` exists. Treat a missing `/dev/kvm` as normal.
7. Prove that a failing PR is blocked and that a direct push to `main` is rejected.

Once public, the history and name are exposed, and deleting the repository may not remove every
copy.

## Remaining security and naming checks

- **Name screening:** not started. Only GitHub, crates.io and a general web search have been
  checked. One live FYRKAT mark is known, covering hand tools and housewares, not software. If a
  register cannot be queried with the available tools, say so rather than implying it was checked.
- **Final secrets, privacy and Git-history review:** not started. It must cover all commits,
  author identities and file contents, as well as the working tree.
- **Adversarial review of this setup:** not started. Use the `reviewer` agent after CI is running.
- **Independence:** AI review is not independent human review. There is no second maintainer, so
  security-sensitive changes have no independent human reviewer.
- **`researcher` and `reviewer` agents:** both have Bash, so neither is read-only by enforcement. See `.claude/agents/`.
- **Hooks:** they guard against mistakes and are not a security boundary.

## Decisions that still need owner approval

- Whether a material name conflict blocks publication. Pause and report any that appear.
- Committing work, unless the owner confirms it is covered by Gate 2.
- Security-sensitive changes beyond what Gate 2 approves, such as to `.github/`, `deny.toml`,
  `rust-toolchain.toml` or `Cargo.lock`. Plugin changes to `.claude/settings.json` are approved.
- Installing the pinned nightly, or any other new tool.
- The revised spike criteria, once drafted, before any experiment runs.
- Any spike expansion: comparator prototype, buying hardware, publishing or upstreaming anything.
- Loosening any spike criterion after results exist.
- The outcome of ADR 0004, and accepting any ADR.

## Next steps, in priority order

1. Start a session at the repository root, and trust the workspace.
2. Confirm that the model is Sonnet and that ECC is absent.
3. Check this file against `git status`, `git log` and the ADRs.
4. **Name screening.** Pause and report any material conflict before continuing.
5. **Revise the spike plan** under Gate 2 decision 4, using Opus, so outdated criteria are not
   published. Ask the owner to review the result.
6. **Disable irrelevant plugins** in `.claude/settings.json` only, and verify in a fresh session.
   Candidates from the headless test: `swift-lsp`, `postman`, `adhd-study-coach`, `engineering`,
   `design`, `data`, `learn-with-coursera` and `cowork-plugin-management`. Get exact identifiers
   from `claude plugin list`, and check the docs for synced plugins, which may use a `@synced`
   suffix.
7. With the owner's confirmation, commit the handoff, `AGENTS.md`, plan and settings changes.
8. **Final secrets, privacy and Git-history review**, then rerun `cargo xtask check`.
9. Carry out the [publication tasks](#publication-tasks).
10. Run the adversarial M0 review with real CI results, and resolve material findings.
11. Declare M0 complete only when every exit criterion above is met.
12. Start spike Stage A on Sonnet, beginning with A1 and the revised A2.

## Context not recorded elsewhere

- Session memory does not carry over. It is stored per launch directory, so nothing from the
  session that wrote this file is visible at the repository root.
- The HongMeng, TickTock and Sculpt PDFs were held in temporary storage and are gone. Their titles
  are in the review document.
- A one-word Sonnet reply cost about $0.11 in the headless test, because other global plugins load
  about 100 skills. That is the reason for Gate 2 decision 3.
