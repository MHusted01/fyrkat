# Session handoff

A snapshot for the next session, not a source of truth. [ADRs](../adr/README.md) and Git win
over it. It records approvals and grants none. The owner's S1 decisions are in the last entries of the
[spike plan's Amendments](../research/sel4-spike-plan.md#amendments).

## Snapshot

- **Date:** 2026-11-08.
- **Merged to `main`:** PR 5 (`AGENTS.md` research policy, `a79c847`) and PR 6 (S1 prerequisites, C1/C2
  methods, decision package and owner decisions, `4fb92a1`). [Measured: `gh pr list --state all`]
- **Open, not merged:** **PR 8** (`spike/s1-workspace-sanitized`): the spike workspace, the one-command A1
  build, the A3 boot work, the **sanitized** evidence, the deviations record and the Amendments recording
  the owner's confirmation. Check `gh pr checks 8` for its required checks. **The owner has not approved
  the merge.** PR 7, which held the same work with unredacted logs, is closed and its branch was deleted
  (see the privacy item below). [Measured: `gh pr list --state all`]
- **Commits:** carry a `Signed-off-by` line and a signature header. GitHub's "verified" display was not
  checked, and branch protection does not require signatures.

## Milestone status

**M0 complete. S1 is stopped at the A3 gate.** ADR statuses are unchanged: 0001 Part A Provisional, Part B
Withdrawn; 0002 and 0003 Provisional; 0004 Proposed. None is Accepted. No ADR text was edited.

| Experiment | Outcome | Record |
|---|---|---|
| A1 build on this Mac | **Pass**, label U. Accepted by the owner, with its reproducibility limitation | [A1](../../spikes/sel4-feasibility/results/A1.md) |
| A3 EL1 and HVF | **Fail** by the plan's clause, label U. Confirmed by the owner on the first report; **re-confirmation requested after a correction** (below) | [A3](../../spikes/sel4-feasibility/results/A3.md) |
| A2a, A4, A5 | Not started. The A3 stop condition stays in force | |

## The A3 failure and what it shows

Unmodified non-hypervisor seL4 17.0.0 **does not boot under HVF on this Apple M2 Pro with 1 vCPU**. The
guest reports 8-bit ASIDs (`ID_AA64MMFR0_EL1.ASIDBits=0`) and the kernel requires 16-bit. The same image
boots under TCG and passes sel4test (124 passed, 59 disabled). [Measured]

**Correction the owner has not yet seen.** The first report said the failure held "with 1 and 4 vCPUs". The
"4 vCPU" image was a single-node kernel. A real 4-node SMP kernel stops earlier, in the unmodified
elfloader (`HVC is not supported for PSCI`), under HVF **and** TCG, so the ASID check was never reached
there and the 4-node image has not booted anywhere. The 1-vCPU result and the Fail rest on the 1-vCPU run;
the agent's assessment is that the outcome is unchanged. The owner should re-confirm.

## Architectural implications (evidence only; the decision is the owner's)

- **ADR 0002's main argument, native execution on the Mac, is not met for seL4 on this host.** The plan
  reopens that question. The owner's reading: it does **not** automatically reject seL4 as the kernel
  candidate.
- **The two ways round the ASID check are closed on this host.** A kernel change is Class 3 under the plan
  and excluded. The hypervisor-mode kernel avoids the check but needs EL2, and QEMU reports "Nested
  virtualization not supported on this system".
- **Loader constraint (for A4):** `sel4-kernel-loader` v6.0.0 supports only EL2 entry on AArch64, so on an
  EL1-only guest only seL4's elfloader remains. HVF also cannot emulate GICv2 (GICv3 needed).
- **Unknowns that change the picture** [Speculative until tested]: whether a newer Apple chip's HVF guest
  presents 16-bit ASIDs or allows nested virtualization (one host was measured); whether the 8-bit value is
  the chip, Hypervisor.framework or QEMU; whether a different machine/device-tree setting makes the SMP
  kernel boot under TCG.
- **What still works:** seL4 runs correctly under TCG here, so semantic experiments (Stage B) are not
  blocked in principle. Stage C performance numbers would not be native, and the plan stops Stage C on an
  A3 Fail.

## The next decision gate (owner)

1. **Re-confirm A3** in light of the correction above.
2. **Decide what the A3 Fail means for ADR 0002** and the plan: for example which host or hosts the
   native-execution argument is tested on, and whether Stage B proceeds under TCG while Stage C waits. The
   plan names no path that keeps HVF and unmodified seL4 on this host. No option here is authorized.
3. **Rule on PR 8** (merge or not), and on the open review items below.

## Authorizations in force

Source: the owner's messages of 2026-11-08, recorded in the plan's Amendments.

- Decisions 1 to 7, P1 and P2 approved. Decision 8 authorized conditionally. P3 deferred, P4 declined, P5
  deferred to the A5 design gate.
- Owner answers: `bindgen` 0.72.1 as locked at `v6.0.0`; member-crate manifests inside the spike
  workspace; Python 3.12.16 with `setuptools` and `wheel` hash-pinned in the venv; `protobuf` 7.36.2
  conditionally (not used).
- Used: merging PRs 5 and 6; pushing the spike branch and opening PR 7; and the owner's narrowly scoped
  approval to replace PR 7 and its branch with sanitized ones (below). That approval covers only that
  branch and PR, not `main` or any other branch.
- **Not authorized:** merging PR 8, A4, A2a, A5, the comparator, Tiers 2 and 3 (so no `x86_64-elf-gcc`),
  any kernel change, further tool installs, relaxing any criterion. **This list is not a blanket approval of
  the tooling deviations.**

## Open items for the owner

1. **Tooling deviations** in [deviations](../../spikes/sel4-feasibility/results/deviations.md): a locally
   built protoc 3.20.3 (the agent's own choice), Homebrew installs with `--ignore-dependencies`, spike code
   (boot harness, probe, scripts) and others. Each has a status and an undo.
2. **Privacy (remaining exposure).** The raw logs were first pushed in PR 7's branch with the author's local
   home path and user name (about 720 times) and the full Homebrew inventory. At the owner's request PR 7
   was closed and edited, its remote branch deleted, and a sanitized replacement published as PR 8. The
   raw originals are kept only locally. **The original commits may still be retrievable**: through GitHub's
   retained pull-request references for PR 7, by commit SHA, and from clones or forks made while they were
   public. PR 7's edit history may also show its original text. Nothing here claims complete erasure. A
   GitHub Support request is the only way to ask for removal of retained references, and is the owner's
   call. `main` never contained any of this. Details: [EVIDENCE-PRIVACY](../../spikes/sel4-feasibility/results/EVIDENCE-PRIVACY.md).
3. **`cargo deny`:** one unmaintained-crate advisory (`RUSTSEC-2024-0449`), traced to host-side build code
   and the `add-payload` tool, absent from the target loader and the spike lock. Policy unchanged.
4. Still open from earlier: the A5 question (class D or Investigate); a base-controlled
   `pull_request_target` check; CI runners use QEMU 8.2.2 against the spike's pinned 11.1.3.

## Installed and changed on this machine (Tier 1, recorded in A1)

Homebrew `aarch64-elf-gcc` 16.2.0 and `aarch64-elf-binutils` 2.47 (installed with `--ignore-dependencies`),
and `brew pin` on qemu, cmake, ninja, dtc, lz4 and the two new formulas. Rustup `nightly-2026-08-21`
(approved components, target `aarch64-unknown-none`). A hash-pinned venv in `spikes/sel4-feasibility/.venv`.
Gitignored under `external/`: seL4, rust-sel4, the sel4test project set, a locally built protoc 3.20.3.

## Verified results

| Check | Result |
|---|---|
| `cargo xtask check` on the PR 8 head | "check: all 12 steps passed" locally |
| CI on PR 8 | See `gh pr checks 8`. Not recorded here because this file is part of the PR |
| A1 `build.sh`, two clean builds | kernel, loader, root task byte-identical; image differs only by QEMU's random device-tree seeds |
| Independent reviews of the evidence | Two passes. All material findings fixed; the last small fix commit had no third pass |

**Not verified:** `cargo xtask boot` locally; any seL4 run on a host other than this M2 Pro; whether
sel4test passes beyond the TCG 1-vCPU run; GitHub's "verified" status of commits.

## Context not recorded elsewhere

- The owner's goal is a secure, modern, high-performance, AI-native OS that does not stop at existing
  solutions. The `AGENTS.md` research section records the working rules.
- The `reviewer` and `researcher` agents have Bash. A read-only rule is not enforced. Check `git status`
  after they run.
- Start a fresh session at the repository root and run `/fyrkat-resume`.
