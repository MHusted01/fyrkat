# Roadmap

Dependency-aware plan, with no dates. Effort is not estimated, because there is no evidence
to estimate from. Milestones are provisional and change as ADRs are decided.

## Maturity levels

Nothing may be described above the level it has actually reached.

| Level | Meaning |
|---|---|
| **Research** | Evidence gathered, nothing built |
| **Prototype** | Runs in a spike. Disposable, and not product code |
| **Validated** | Product code with acceptance criteria passing, under emulation |
| **Hardware validated** | Validated on physical hardware |
| **Production** | Hardware validated, reviewed, with a defined support policy |

**Today, every component is at Research or below.** The only running code is a boot spike
and test tooling.

## Dependency order

```text
M0 Engineering foundation
 └─ S1 Kernel foundation spike ── decides ADR 0004
     └─ M1 Boot path
         └─ M2 Kernel foundation
             └─ M3 Isolation and capabilities ── x86-64 port, verification pilot
                 └─ M4 System services ── needs an IOMMU path and a test machine
                     └─ M5 Developer environment
                         └─ Later: desktop, compatibility, storage and networking at scale
```

Research items R1 to R5 below run alongside these, and block the milestone named.

## M0: Engineering foundation

**Status: in progress.** Repository, CI, standards, agent setup, architecture documents and
decision records.

Exit criteria:

- A fresh clone passes `cargo xtask check`.
- CI runs on a real pull request, and a deliberately failing change is blocked.
- A direct push to `main` is rejected, and protections are confirmed through the API.
- ADRs 0001 to 0003 are ruled on, and the spike plan is approved.
- Project Claude Code configuration is confirmed working in a real session.
- The adversarial review is complete, with material findings fixed or tracked.

## S1: Kernel foundation spike

**Status: planned.** It is defined by the [spike plan](research/sel4-spike-plan.md), with
pre-registered pass and fail criteria.

- **Depends on:** M0 tooling.
- **Exit:** the owner decides ADR 0004. **M1 cannot be finalized before this.**

## M1: Boot path

The first implementation milestone. It was renamed from "Boot Foundation" because M1 cannot
demonstrate verified boot, and must not imply it.

**Common to both outcomes of ADR 0004:**

- Boots through the loader chosen under ADR 0003 on QEMU, for both architectures.
- Discovers the memory map, and reports it on a diagnostic console.
- Runs automated boot and shutdown tests in CI.
- Reports a clear failure rather than hanging.

**If seL4 is adopted:** a pinned kernel build reaches a Rust root server, with a reproducible
build, and `fyrkat-rt` exists as the only caller of seL4 interfaces.

**If a custom kernel is chosen:** the kernel reaches Rust code with a known exception level,
stack, and a tested panic path.

## M2: Kernel foundation

**If seL4 is adopted:** a root server with memory management, process lifecycle, fault
handling and a user-level pager.

**If a custom kernel is chosen:** physical and virtual memory management, exceptions,
interrupts and initial scheduling.

**Exit in both cases:** multicore boot, and memory and fault-handling tests passing under
emulation.

## M3: Isolation and capabilities

- Multiple isolated processes, with an IPC path measured against seL4 on the same hardware.
- Capability enforcement proven by negative tests, including use after revoke.
- **Full x86-64 support**, before any ABI is frozen, as ADR 0002 requires.
- **First physical test machine chosen**, based on verified IOMMU support.
- A verification pilot on one critical component, whichever kernel is used.

Isolation is shown by explicit negative tests, and never inferred from separate processes
appearing to run.

## M4: System services

- Driver framework with restart, shown by fault injection.
- DMA isolation enforced by an IOMMU, with negative tests.
- Service supervision and recovery.
- Storage and networking foundations.
- First hardware validation of isolation.

## M5: Developer environment

Shell, executable loading, tooling, and an initial application runtime.

## Later work

Unscheduled, because each depends on evidence that does not exist yet:

- Copy-on-write filesystem, encryption, snapshots and transactional updates.
- Secure and measured boot on hardware.
- Native graphics stack, compositor, and desktop.
- POSIX, Linux and WebAssembly compatibility.
- Virtualization and driver VMs for GPUs.
- Power management and suspend.
- Local AI inference, and permission-controlled agents.

## Research items

| Item | Question | Blocks |
|---|---|---|
| R1 | What is the GPU strategy, and what does a driver VM cost? | Desktop |
| R2 | Which physical machine has a working IOMMU, UEFI and PCIe? | M3 |
| R3 | How should heterogeneous cores be scheduled? | M4 |
| R4 | Which component should be verified first, and with which tools? | M3 |
| R5 | What is the policy for speculative side channels? | Running mutually distrusting code |
