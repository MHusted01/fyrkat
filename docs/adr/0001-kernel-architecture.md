# ADR 0001: Kernel architecture

- **Status:** Part A: Provisional. Part B: Withdrawn.
- **Date:** 2026-11-07
- **Deciders:** Project owner

Evidence and citations are in
[the kernel architecture comparison](../research/kernel-architecture.md).

## Gate 1 outcome

The owner provisionally accepted Part A and withheld Part B pending adversarial review. After
[that review](../research/sel4-adversarial-review.md), the owner withdrew Part B as written.
The question it addressed moved to [ADR 0004](0004-kernel-foundation.md), where seL4-first
is a working hypothesis and not a commitment.

## Context

Every later component depends on the kernel's architecture class. This ADR decides that
class. Which kernel fills it is decided in ADR 0004.

## Requirements

In priority order:

1. A compromised driver or service must not compromise the rest of the system.
2. Authority must be explicit and confinable, with no ambient authority.
3. The privileged trusted computing base must be small enough to audit, and critical
   parts must be feasible to verify formally.
4. Faulty services must be restartable without a system restart.
5. It must support general-purpose hardware: multicore, DMA-capable devices, and
   eventually GPUs.
6. Performance on real workloads must be measurably acceptable against Linux on the
   same hardware.
7. It must be practical to evolve over decades.

## Decision

**Part A, architecture class (Provisional):** Fyrkat uses a capability-based microkernel
with hardware-enforced isolation. Drivers, filesystems, networking and system services run
in user space. Language safety is defence in depth and never the isolation boundary
between components.

**Part B (Withdrawn):** this proposed that Fyrkat build a new kernel in Rust, using seL4's
design as a reference without its code. It was withdrawn because its reasoning compared the
real seL4 with an imagined verified Fyrkat kernel. "No verified configuration covers SMP or
an IOMMU" is equally true of a kernel that does not exist, and Part B proposed much the same
locking design as seL4.

**Requirements on any kernel chosen under ADR 0004:**

- **Bounded kernel memory.** Kernel objects should live in memory supplied and accounted
  for through capabilities, rather than a kernel heap.
- **Short, bounded kernel operations.**
- **DMA requires an IOMMU.** Fyrkat does not treat a DMA-capable driver as isolated on
  hardware without one.
- **A credible multicore path**, supported by measurement.

**Not decided here:** IPC semantics, the capability derivation model, scheduler design,
and how driver VMs work.

## Alternatives

**Framekernel (Asterinas).** It offers a small memory-safety TCB and performance comparable
to Linux. It is rejected because services share one address space, so a logic bug carries
full kernel authority, and because it cannot contain reused non-Rust drivers.

**Monolithic kernel in Rust.** This is the fastest and simplest path to broad hardware
support. It is rejected because it fails requirements 1 to 4. Rust removes memory
corruption, but it does not shrink privileged code or confine authority.

**Hybrid kernel (XNU, NT).** It retains a large privileged core, and Apple's move to
user-space drivers suggests the direction of travel is away from this design.

**Message-passing microkernel without capabilities (MINIX 3, QNX).** Its recovery and
real-time evidence is strong, and both lessons carry over, but its authority model is weaker
than requirement 2 demands.

**Multikernel as the primary structure.** It is not chosen as a starting point because it
adds substantial complexity before scale requires it. Its principles remain relevant.

**Exokernel.** No production general-purpose evidence was found for the full model. Its core
idea survives in user-managed kernel memory.

## Evidence

- User-mode drivers are not isolated without an IOMMU. [Documented]
- Language safety does not confine authority. [Inferred]
- One study estimates that 96% of critical Linux CVEs would drop below critical severity in
  a microkernel design. That figure includes 38% that still violate confidentiality or
  integrity, and only 57% reach low severity. The method is a hypothetical mapping onto one
  hypothetical application, by seL4's authors. Treat it as directional. [Documented]
- HongMeng, a capability-influenced microkernel on tens of millions of devices, reports
  that the design works in production and carries real costs. [Documented, authors' claims]
- Sculpt has run a dynamic desktop on seL4 in preliminary form, and it lacks suspend and
  power management there. [Documented]
- Whether a capability microkernel can run a full desktop at acceptable performance remains
  unproven. This is the main open assumption. [Inferred]

## Security consequences

- A much smaller privileged surface, with authority confined by construction.
- Assurance claims must be limited to what has been verified for the shipped configuration.

## Performance consequences

- Every service interaction costs IPC, so it must be a measured priority from the start.
- HongMeng reports that IPC frequency, double bookkeeping and capability-mediated page
  faults are real costs. The spike plan measures this.

## Compatibility implications

- POSIX and Linux compatibility must be built above the kernel, or provided through VMs.
- GPU support likely depends on driver VMs, so virtualization cannot be a late addition.
- Kernel ABI stability is deferred until a second CPU architecture has validated it.

## Risks

- **Unproven performance:** a desktop workload may cross too many servers.
- **Scaling:** verification-friendly locking may not suit many-core systems.

## Reconsideration criteria

Reopen Part A if any of these occurs:

1. Negative isolation tests expose a flaw that cannot be fixed within this architecture.
2. A representative workload shows server-crossing overhead that optimization cannot bring
   within an acceptable margin of Linux on the same hardware.
3. Evidence shows that driver reuse cannot be made to work with isolated services at
   acceptable performance.
