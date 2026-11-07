# Architecture overview

This is the initial architecture specification. **No kernel or operating system exists
yet.** It describes intent and constraints, not implemented behaviour. ADRs are the source
of truth for decisions, and this document links to them rather than restating them.

## Decision status

| Topic | Status | Source |
|---|---|---|
| Capability-based microkernel, hardware isolation | Provisional | [ADR 0001](../adr/0001-kernel-architecture.md) |
| seL4 or custom Rust kernel | **Open.** seL4-first is a working hypothesis | [ADR 0004](../adr/0004-kernel-foundation.md) |
| AArch64 first, x86-64 required second | Provisional | [ADR 0002](../adr/0002-initial-cpu-architecture.md) |
| UEFI boot with a minimal Rust loader | Provisional | [ADR 0003](../adr/0003-boot-strategy.md) |
| Everything else in this document | **Open** unless stated | This document |

Provisional decisions can be reopened by the results of the
[seL4 spike](../research/sel4-spike-plan.md).

## Goals

Fyrkat aims to be a general-purpose operating system with these properties, in priority
order when they conflict:

1. **Security:** least privilege by default, with authority that is explicit and confinable.
2. **Reliability:** faults stay contained, and failed services recover.
3. **Correctness:** behaviour is specified and tested, with critical parts verified.
4. **Performance:** measured against real workloads, not assumed.
5. **Maintainability:** decisions can be revisited over decades.
6. **User ownership:** no mandatory cloud account, advertising or telemetry.

## Non-goals

- Being a Linux distribution, or binary compatibility with any OS as a design driver.
- Running on Apple Silicon hardware. Macs are development hosts.
- Claiming assurance beyond what has been shown for the shipped configuration.
- Hard real-time guarantees, unless a later ADR adds them.
- Defending against the attacks listed as out of scope in the
  [threat model](threat-model.md).

## System structure

All of this is intended structure. None of it exists.

| Layer | Runs at | Intended contents |
|---|---|---|
| Firmware | Below Fyrkat | Platform firmware, which is outside Fyrkat's control and inside its TCB |
| Loader | Before the kernel | Minimal Rust loader (provisional) |
| Kernel | Privileged | Capabilities, address spaces, threads, IPC, interrupts |
| Root server | User mode | Initial authority, system bring-up, resource policy |
| System services | User mode | Memory, process, storage, network and device management |
| Drivers | User mode | Isolated, restartable, confined by an IOMMU for DMA |
| Applications | User mode | Hold only the capabilities they are granted |
| Guest VMs | Isolated | Foreign drivers and compatibility workloads |

## Kernel architecture candidates

Architecture classes were compared in the
[kernel architecture comparison](../research/kernel-architecture.md). The class is
provisional under ADR 0001. Which kernel fills it is open under ADR 0004.

## Privilege and capability model

**Provisional principle:** authority is held only through unforgeable capabilities, with
no ambient authority and no global namespace that grants access by default.

**Open:**

- The derivation and revocation model. seL4 provides a derivation tree with revocation,
  while Atmosphere deliberately prohibits fine-grained revocation. Which semantics Fyrkat
  needs is tested by experiment B2 in the spike.
- How capabilities surface to users and applications as understandable permissions.
- Whether revoking a single grant needs user-level indirection.

## Memory isolation

**Provisional principles:**

- Components run in separate hardware address spaces.
- Language safety is defence in depth, never the boundary between components.
- A DMA-capable driver is not treated as isolated without an IOMMU.

**Open:**

- Page-fault handling and pager design. HongMeng reports capability-mediated page faults at
  3.4 times Linux, so this needs measurement (experiment C2).
- How kernel memory is accounted for, which depends on ADR 0004.
- Copy-on-write, shared memory and memory pressure policy.

## IPC

**Open.** Nothing is decided beyond the need for a fast, capability-mediated primitive.

- Synchronous or asynchronous semantics, and how they combine with notifications.
- Payload transfer, and when shared memory is used instead.
- Priority inversion across servers. QNX uses message-driven priority inheritance.
- How often a typical operation crosses servers, which HongMeng identifies as a real cost.

Service protocols, not the kernel ABI, are where stability promises should be made. This
applies whichever kernel is chosen.

## Scheduling

**Open.** The requirements are SMP support and heterogeneous cores, as on modern laptops.

- Scheduling policy, and whether it lives in the kernel.
- Temporal isolation, and the use of MCS if seL4 is adopted.
- Scaling beyond one lock per cache domain.
- Heterogeneous-core scheduling has not been researched for either kernel option.

## Driver model

**Provisional principle:** drivers run in user mode, in separate address spaces, and can be
restarted.

**Open:**

- Driver framework and device protocols.
- Supervision and recovery protocol.
- **GPU strategy.** Writing native GPU drivers looks unrealistic. Driver VMs are the leading
  candidate, but no GPU performance evidence has been found.

## Hardware abstraction

**Provisional principle:** portable code must assume no memory model stronger than
AArch64's, and x86-64 must validate portability before any ABI is frozen.

**Open:** how hardware description, whether ACPI or devicetree, is consumed. seL4 selects
platforms at compile time, which limits how far this can be dynamic.

## Boot

UEFI with a minimal Rust loader is provisional under ADR 0003. M1 will not provide verified
boot. Secure and measured boot are later work, and platform firmware stays in the TCB.

## Verification strategy

The [testing standard](../standards/testing.md) covers the wider strategy. The architectural
points are:

- **Claims must match configurations.** seL4's proofs cover only its verified configurations
  at a stated commit. They do not cover SMP, IOMMU use, VT-x, QEMU builds, modifications or
  user space.
- **Targeted verification looks more reachable than whole-system verification.** Candidates
  are capability logic and memory management, in whichever component holds them.
- **Isolation is shown by negative tests**, not inferred because separation appears to work.
- **An emulator pass does not prove hardware correctness.**

## Portability

AArch64 and x86-64 are both required. RISC-V is a candidate for a later port. Architecture
code must stay separated from portable code, whichever kernel is chosen.

## Open architectural questions

1. Is seL4 or a custom Rust kernel the stronger foundation? (ADR 0004)
2. Can a capability microkernel run a full desktop at acceptable performance?
3. How will DMA isolation work on AArch64, given that seL4 has no SMMUv3 driver?
4. What is the GPU strategy, and what does it cost in performance?
5. What is the capability revocation model?
6. Which physical machine validates isolation on real hardware?
7. How do multicore limits affect real workloads?
8. How should heterogeneous cores be scheduled?
9. What should the POSIX and Linux compatibility boundary be?
10. Which components should be formally verified first, and with which tools?
