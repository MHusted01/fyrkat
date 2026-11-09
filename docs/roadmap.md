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

**Status: complete.** The owner declared M0 complete on 2026-11-07, on the evidence in the
[M0 acceptance record](development/m0-acceptance.md), including its documented limits. Repository,
CI, standards, agent setup, architecture documents and decision records.

Exit criteria:

- A fresh clone passes `cargo xtask check`.
- CI runs on a real pull request, and a deliberately failing change is blocked.
- A direct push to `main` is rejected, and protections are confirmed through the API.
  The rejection was demonstrated on an identically protected throwaway branch, and `main`
  itself was deliberately not push-tested. See the
  [M0 acceptance record](development/m0-acceptance.md).
- ADRs 0001 to 0003 are ruled on, and the spike plan is approved.
- Project Claude Code configuration is confirmed working in a real session.
- The adversarial review is complete, with material findings fixed or tracked.

## S1: Kernel foundation spike

**Status: in progress, stopped at the A3 gate, apart from the bounded experiments E1, E2 and E3 below.** It is defined by the [spike plan](research/sel4-spike-plan.md),
with pre-registered pass and fail criteria. The owner approved the plan's text on 2026-11-07 and authorized A1,
A3, A4 and the A2a interpretation conditionally on 2026-11-08.

- **A1** ran and passed (label U), and a rerun with the approved dependency lock also passed (label U). The owner
  accepted the rerun **limited to build reproducibility**. No runtime validation exists: the A1 image has never
  booted.
- **A3** ran and failed (label U) for unmodified seL4 under HVF on one Apple M2 Pro, and the owner confirmed it.
  Decision rule 2 applies to that **HVF-specific** configuration. It does not establish incompatibility on every
  Apple Silicon host, and it does not reject seL4 on TCG.
- **Direction (owner, 2026-11-08):** [ADR 0002](adr/0002-initial-cpu-architecture.md) keeps AArch64-first as a
  provisional direction, with QEMU TCG as the initial local backend. [ADR 0004](adr/0004-kernel-foundation.md)
  keeps seL4-first as a provisional **working hypothesis**. Neither ADR is Accepted.
- **Blocked:** A5 and any Class 3 kernel change. A2a, A4 and the comparator are not authorized. The nightly
  toolchain is approved for S1 only.
- **E1 (owner-authorized, 2026-11-08; ran after that documentation was merged):** the Rust root task on a
  hypervisor-enabled seL4 17.0.0 with the pinned Rust loader under QEMU TCG (Route II), specified in the plan's
  [Amendments entry of the E1 decision](research/sel4-spike-plan.md#2026-11-08-owner-decisions-on-the-documentation-pr-six-deviations-pr-9-and-e1-route-ii).
  **The agent's reading is Pass, label U, functional only: 3 of 3 boots reached `TEST_PASS`** ([E1](../spikes/sel4-feasibility/results/E1.md)).
  An independent review found it acceptable with corrections (applied); the owner conditionally accepted it, subject to a final review of those corrections. It shows nothing about HVF, SMP, performance, hardware or assurance, and its kernel has half the RAM of A1's.
- **E2 (owner-authorized, 2026-11-09):** two isolated Rust tasks over seL4 IPC, with two invalid invocations and two refused attempts to exceed their authority (badge forgery, a read of the other task's memory), on the E1 kernel
  configuration. **Pass, label U, functional only: 3 of 3 boots** ([E2](../spikes/sel4-feasibility/results/E2.md)), **finally accepted by the owner** (after an independent review) as limited to its demonstrated
  functional and capability-isolation probes; it does not establish verified kernel-generated fault delivery. It is a precursor, not Stage B evidence (A2a has not run), and it does not test revocation, rights amplification, hardware or assurance.
- **E3 (owner-authorized, 2026-11-09):** capability revocation on the same configuration: after `seL4_CNode_Revoke` on the root task's endpoint capability, the mints of it and their copies in two tasks' CNodes are gone, while the ancestor, an unrelated control and a new mint work.
  **The agent's reading is Pass, label U, functional only: 3 of 3 boots, six mutants fail as they should** ([E3](../spikes/sel4-feasibility/results/E3.md)). **Provisionally accepted by the owner**, limited to the tested revocation behaviour under QEMU TCG, pending independent review (a first review found defects, since fixed and the evidence rerun; a second review of the final state returned MERGE-READY; the owner's final acceptance is pending).
  A call through a revoked slot returns the same error as one through a never-populated slot, so the error code is not evidence. It does not test revoking a badged child, an untyped, a deeper chain, or any other object type, and it is not Stage B evidence.
- **Next:** the E3 PR, then the owner's final acceptance of E3. No further experiment is authorized.
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
