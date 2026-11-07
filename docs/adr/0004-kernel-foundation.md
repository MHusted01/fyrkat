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

The hypothesis is falsifiable. The [spike plan](../research/sel4-spike-plan.md) defines the
pre-registered falsification rules, the kernel modification policy, and the criteria that
reopen this decision if the hypothesis survives.
