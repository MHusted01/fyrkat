# ADR 0004: Kernel foundation

- **Status:** Proposed (working hypothesis, not a commitment)
- **Date:** 2026-11-07
- **Deciders:** Project owner

This ADR replaces the withdrawn [ADR 0001 Part B](0001-kernel-architecture.md). It stays
Proposed until the [feasibility spike](../research/sel4-spike-plan.md) reports. Nothing may
treat seL4 as decided in the meantime.

## Context

Fyrkat has provisionally chosen a capability-based microkernel. The open question is
whether to use seL4 or build a custom Rust kernel. The original proposal to build was
withdrawn after an [adversarial review](../research/sel4-adversarial-review.md) showed that
it compared the real seL4 with an imagined verified Fyrkat kernel.

This must be settled before M1 is finalized, because M1 and M2 differ completely between
the two options.

## Requirements

1. Any kernel must support the isolation, authority and recovery requirements in ADR 0001.
2. DMA-capable drivers must not be treated as isolated without an IOMMU.
3. It must be practical to develop from the primary development machine.
4. Assurance claims must match what actually applies to the shipped configuration.
5. The choice must remain reversible at a cost the project can bear.
6. Long-term security, performance, reliability and maintainability outrank speed.

## Decision

**None yet.** The working hypothesis is:

> For Fyrkat's first system, unmodified seL4 with Rust user-space services is a stronger
> foundation than a custom Rust kernel.

If the hypothesis survives, the proposal would be a pinned seL4 release, a dynamic Rust root
server rather than Microkit, and a `fyrkat-rt` crate as the only caller of seL4 interfaces.

## Alternatives

**Custom Rust kernel.** The realistic alternative. It gives full control, Rust throughout,
and a design shaped by Fyrkat's needs. Today it has no code, no field history and no proofs.
The spike compares it through existing systems and a bill of work, because a hypothetical
kernel cannot be credited with capabilities it does not have.

**seL4 permanently, without a re-decision gate.** Rejected for now. The reviewer gave only
about 40% that seL4 stays the kernel for decades, and Fyrkat must be able to act on
evidence.

## Evidence

- No kernel, seL4 or new, has proofs covering SMP or an IOMMU. [Documented, Inferred]
- seL4's verified sequential core, maintained proofs and fast IPC exist today. [Documented]
- seL4's unverified SMP, IOMMU and VT-x paths have had serious bugs. [Documented]
- Verified configurations have also had serious bugs outside proof scope. [Documented]
- No QEMU run is a verified configuration. [Documented]
- seL4 has no SMMUv3 driver, and QEMU `virt` has only SMMUv3. [Documented, Measured]
- HongMeng reports real performance costs in capability-based general-purpose systems.
  [Documented, authors' own claims]
- Atmosphere supports feasibility for an expert team, not for this project. [Inferred]

## Security consequences

- seL4's proofs apply only to verified configurations at the stated commit. Fyrkat must never
  imply that they cover SMP, IOMMU, VT-x, MCS on AArch64, QEMU builds, kernel modifications,
  or any user-space code.
- Every result and claim must use the labels in the spike plan.

## Performance consequences

Unknown until the spike runs. seL4's published IPC is the fastest found, but the
general-purpose cost is unmeasured.

## Compatibility implications

If seL4 is adopted, ADRs 0002 and 0003 may need revision. Their open conflicts are listed in
those documents.

## Risks

- **"Own kernel later" may be fiction**, because kernel interfaces shape everything built
  above them.
- **Fyrkat could end up carrying a C fork** in unverified code, with neither proofs nor Rust.
- **The spike could mislead** if QEMU results are mistaken for hardware results.

## Reconsideration criteria

The hypothesis is falsifiable. The [spike plan](../research/sel4-spike-plan.md), whose
criteria the owner approved on 2026-11-07 at commit `46a90fa` (execution was authorized
conditionally on 2026-11-08, and S1 is stopped at the A3 gate, apart from one bounded experiment, E1, that the plan's
Amendments authorize only after the documentation pull request that records it is merged), defines the falsification rules, the
kernel modification policy, and the criteria that reopen this decision if the hypothesis survives.

## Update 2026-11-08: spike S1 evidence and owner direction

This update records evidence and an owner direction. **The status stays Proposed, the Decision above is
still "None yet", and seL4 is not decided.** The original text is unchanged except for the one
sentence above that said execution was not authorized.

**Two hypotheses must be kept apart.**

| | Statement | Evidence so far | Standing |
|---|---|---|---|
| **HVF-specific** | Unmodified seL4 boots and runs natively under HVF on the primary development machine | A3 ran on one Apple M2 Pro: the kernel halts at its 16-bit ASID check, and a real SMP kernel stops in the elfloader [Measured, label U]. A3 is a **Fail** by its original criteria | **Falsified for the tested configuration.** The owner ruled that decision rule 2 of the plan applies, because passing would need a prohibited Class 3 kernel change under the currently available options. Not generalized to other hosts |
| **Broader working hypothesis** | The one at the top of this ADR: unmodified seL4 with Rust user-space services is a stronger foundation than a custom Rust kernel | Not falsified by A3, and not supported by it either. A1 and its rerun are Pass (label U), limited to build reproducibility. A separate sel4test kernel (GICv3, Cortex-A53) passes the sel4test suite under TCG, as a control. The A1 kernel and root task have not booted | **Retained by the owner as a provisional working hypothesis.** Not an Accepted architecture decision |

**What the evidence does and does not show.**

- A1 (build on the Mac) is a **Pass, label U**. A rerun with the corrected dependency lock is also a
  **Pass, label U**, accepted by the owner and **limited to the tested build-reproducibility criterion**:
  two clean builds give an identical kernel, loader and root task, and the boot image differs only by
  QEMU's random device-tree seeds. The root-task hash changed between the two locks, so **a root-task
  hash must name the lock that produced it** [Measured; see the A1 rerun record].
- **No runtime or behavioural validation exists** for the Rust root task. The A1 image has never booted
  [Measured]. Nothing here claims otherwise.
- Not yet run: A2a, A4, A5, Stage B (B1 to B4) and Stage D (the comparison with a custom kernel).
  Stage C does not run under the A3 Fail consequence in the plan. The results not yet obtained could
  still falsify or support the broader hypothesis.

**Constraints that stay in force.** A5 is blocked. Any Class 3 kernel change is blocked, and this
ADR does not accept one. The Rust nightly `nightly-2026-08-21` is approved **for the isolated S1
experiment only**: A1 triggered the plan's consequence "user space requires nightly Rust: reopens the
toolchain policy", and the long-term toolchain policy is **unresolved**.

See [ADR 0002](0002-initial-cpu-architecture.md) for the CPU-architecture side of the same direction.
