# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win
over it. It records approvals and grants none. The owner's S1 decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-08.
- **Merged to `main`:** PR 5 (`AGENTS.md` research policy, `a79c847`) and PR 6 (S1 prerequisites, C1/C2
  methods, decision package and owner decisions, `4fb92a1`). [Measured: `gh pr list --state all`]
- **Local branch, not pushed:** `spike/s1-workspace`, from `4fb92a1`. It holds the spike workspace,
  `build.sh`, the A3 scripts, and the A1 and A3 results. **No push or PR was authorized for it.**
  [Measured: git]
- **Commits:** carry a `Signed-off-by` line and a signature header. GitHub's "verified" display was not
  checked, and branch protection does not require signatures.

## Milestone status

**M0 complete. S1 is in progress: A1 Pass, A3 Fail.** ADR statuses are unchanged: 0001 Part A
Provisional, Part B Withdrawn; 0002 and 0003 Provisional; 0004 Proposed. None is Accepted.

| Experiment | Outcome | Record |
|---|---|---|
| A1 build on this Mac | **Pass**, label U | [A1](../../spikes/sel4-feasibility/results/A1.md) |
| A3 EL1 and HVF | **Fail** by the plan's clause, label U. **Owner to confirm** | [A3](../../spikes/sel4-feasibility/results/A3.md) |
| A2a, A4 | Not started. The plan's A3 Fail row says "Stop and report" | |

## The decisive finding

Unmodified non-hypervisor seL4 17.0.0 **does not boot under HVF on this Apple M2 Pro**, with 1 or 4
vCPUs: the guest reports 8-bit ASIDs (`ID_AA64MMFR0_EL1.ASIDBits = 0`), and the kernel requires 16-bit.
The same image boots under TCG (Cortex-A57). The hypervisor-mode kernel needs EL2, and this host reports
"Nested virtualization not supported". Any kernel change that would get past it is Class 3 under the
plan. Per the plan this **reopens ADR 0002** and Stage C does not run. Also: `sel4-kernel-loader` v6.0.0
on AArch64 supports only EL2 entry, and HVF cannot emulate GICv2.

## Authorizations in force

Source: the owner's messages of 2026-11-08 in the working session, recorded in the plan's Amendments.

- Decisions 1 to 7 and P1, P2 approved. Decision 8 (A1, A3, A4 with Sonnet, A2a with Opus) authorized
  conditionally. P3 deferred to Stage D, P4 declined, P5 deferred to the A5 design gate.
- Owner answers: `bindgen` 0.72.1 as locked at `v6.0.0`; member-crate `Cargo.toml` files inside the spike
  workspace; `setuptools`, `wheel` (and `packaging`) hash-pinned in the venv; Python 3.12.16.
- Merging PRs 5 and 6 after review and CI: used.
- **Not authorized:** A5, the comparator, Tiers 2 and 3 (so no `x86_64-elf-gcc`, which A4's x86-64 half
  needs), pushing `spike/s1-workspace`, any kernel change, relaxing any criterion.

## Installed and changed on this machine (Tier 1, recorded in A1)

Homebrew `aarch64-elf-gcc` 16.2.0 and `aarch64-elf-binutils` 2.47 (installed with
`--ignore-dependencies` to avoid an `lz4` upgrade), and `brew pin` on qemu, cmake, ninja, dtc, lz4 and the
two new formulas. Rustup `nightly-2026-08-21` (approved components, target `aarch64-unknown-none`). A
hash-pinned venv in `spikes/sel4-feasibility/.venv`. Gitignored under `external/`: seL4, rust-sel4, the
sel4test project set and a locally built protoc 3.20.3.

## Open items for the owner

1. **Confirm or contest A3 Fail**, and decide what it means for ADR 0002 and the plan. The plan names no
   path that keeps HVF and unmodified seL4 on this host. Other Apple chips were not tested.
2. **Review agent-made spike tooling that was not individually approved:** `tools/cpio` (a GNU-cpio
   stand-in), `build-protoc.sh` (protoc 3.20.3 built from source at a pinned commit; this replaced the
   conditionally approved `protobuf` 7.36.2 override, which was not used), and `--ignore-dependencies`.
3. **`cargo deny`:** the loader's tree has one unmaintained-crate advisory (`RUSTSEC-2024-0449`,
   `unsafe-libyaml`, in a host-side tool) and first-party "wildcard" bans. The policy was not weakened.
4. **Push `spike/s1-workspace` and open a PR?** Not authorized yet.
5. Still open: the A5 question (class D or Investigate), and the M0 follow-up of a base-controlled
   `pull_request_target` check. CI runners have QEMU 8.2.2 against the spike's pinned 11.1.3.

## Verified results

| Check | Result |
|---|---|
| `cargo xtask check` on `spike/s1-workspace` | "check: all 12 steps passed" |
| A1 `build.sh`, two clean builds | kernel, loader and root task byte-identical; image differs only by QEMU's random `rng-seed` and `kaslr-seed` in the embedded device tree |
| A3 | see the table above and the A3 record |

**Not verified:** `cargo xtask boot` locally; CI on the new branch (not pushed); any seL4 run on a
host other than this M2 Pro; whether sel4test passes under TCG (started only).

## Next actions

1. The owner rules on A3 and ADR 0002. The plan says stop and report.
2. If the plan continues, A4's AArch64 half could run under TCG without Tier 2. Its x86-64 half needs
   `x86_64-elf-gcc`, which is not approved. A2a (Opus) needs A1's preprocessed kernel, which exists.
3. Anything outside the approved scope stops and asks.

## Context not recorded elsewhere

- The owner's goal is a secure, modern, high-performance, AI-native OS that does not stop at existing
  solutions. The `AGENTS.md` research section records the working rules.
- The `reviewer` and `researcher` agents have Bash. A read-only rule is not enforced. Check `git status`
  after they run.
- Start a fresh session at the repository root and run `/fyrkat-resume`.
