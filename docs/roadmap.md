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

**Status: in progress, stopped at the A3 gate, apart from the bounded experiments E1, E2 and E3 and the no-boot A2a below.** It is defined by the [spike plan](research/sel4-spike-plan.md),
with pre-registered pass and fail criteria. The owner approved the plan's text on 2026-11-07 and authorized A1,
A3, A4 and the A2a interpretation conditionally on 2026-11-08; the owner's later stop that day held A2a and A4; A2a was authorized on 2026-11-09 and A4 has not been authorized.

- **A1** ran and passed (label U), and a rerun with the approved dependency lock also passed (label U). The owner
  accepted the rerun **limited to build reproducibility**. No runtime validation exists: the A1 image has never
  booted.
- **A3** ran and failed (label U) for unmodified seL4 under HVF on one Apple M2 Pro, and the owner confirmed it.
  Decision rule 2 applies to that **HVF-specific** configuration. It does not establish incompatibility on every
  Apple Silicon host, and it does not reject seL4 on TCG.
- **Direction (owner, 2026-11-08):** [ADR 0002](adr/0002-initial-cpu-architecture.md) keeps AArch64-first as a
  provisional direction, with QEMU TCG as the initial local backend. [ADR 0004](adr/0004-kernel-foundation.md)
  keeps seL4-first as a provisional **working hypothesis**. Neither ADR is Accepted.
- **Blocked:** A5 and any Class 3 kernel change. A4 and the comparator are not authorized (A2a ran on 2026-11-09, below). The nightly
  toolchain is approved for S1 only.
- **E1 (owner-authorized, 2026-11-08; ran after that documentation was merged):** the Rust root task on a
  hypervisor-enabled seL4 17.0.0 with the pinned Rust loader under QEMU TCG (Route II), specified in the plan's
  [Amendments entry of the E1 decision](research/sel4-spike-plan.md#2026-11-08-owner-decisions-on-the-documentation-pr-six-deviations-pr-9-and-e1-route-ii).
  **The agent's reading is Pass, label U, functional only: 3 of 3 boots reached `TEST_PASS`** ([E1](../spikes/sel4-feasibility/results/E1.md)).
  An independent review found it acceptable with corrections (applied); the owner conditionally accepted it, subject to a final review of those corrections. It shows nothing about HVF, SMP, performance, hardware or assurance, and its kernel has half the RAM of A1's.
- **E2 (owner-authorized, 2026-11-09):** two isolated Rust tasks over seL4 IPC, with two invalid invocations and two refused attempts to exceed their authority (badge forgery, a read of the other task's memory), on the E1 kernel
  configuration. **Pass, label U, functional only: 3 of 3 boots** ([E2](../spikes/sel4-feasibility/results/E2.md)), **finally accepted by the owner** (after an independent review) as limited to its demonstrated
  functional and capability-isolation probes; it does not establish verified kernel-generated fault delivery. It is a precursor, not Stage B evidence (E1H is not a matrix row), and it does not test revocation, rights amplification, hardware or assurance.
- **E3 (owner-authorized, 2026-11-09):** capability revocation on the same configuration: after `seL4_CNode_Revoke` on the root task's endpoint capability, the mints of it and their copies in two tasks' CNodes are gone, while the ancestor, an unrelated control and a new mint work.
  **The agent's reading is Pass, label U, functional only: 3 of 3 boots, six mutants fail as they should** ([E3](../spikes/sel4-feasibility/results/E3.md)). **Finally accepted by the owner** (2026-11-09), limited to the tested capability-revocation topology under single-vCPU QEMU TCG with the debug kernel, after two independent reviews (NOT MERGE-READY, then MERGE-READY on the evidence); the verifier changes made after the second review are not reviewed, and E3.md lists the forged-log gaps that remain. D21 to D23 approved.
  A call through a revoked slot returns the same error as one through a never-populated slot, so the error code is not evidence. It does not test revoking a badged child, an untyped, a deeper chain, or any other object type, and it is not Stage B evidence.
- **A2a (owner-authorized, 2026-11-09):** ran, **outcome Investigate** by the plan's definition (the P5 cell of K3 cannot be classified yet and no required Stage B test has run); the owner accepted it as the recorded result subject to independent review. The K1 and K2 cells for P1 to P4 are **expected** class B but **not yet classified**: the dependency lists were not completed, which the plan asks A2a to do, and the trusted-component entry is open ([A2a](../spikes/sel4-feasibility/results/A2a.md)).
  Build success, configuration similarity and formal-verification applicability are kept apart there. Findings: every AArch64 verified configuration, K0 included, is hypervisor-mode, so the hypervisor-enabled kernel of E1 to E3 shares that option with K0 and K1 and K2 do not; K1, K2 and the E1H kernel are debug builds against K0's release build; the documentation ties the pinned release to a proof revision through the 17.0.0 verification manifest, but which AArch64 proof sessions exist for it is not established; at the time of A2a no loader was known to start the 4-node K2 (corrected below).
- **Stage B preparation and A5 step 0 (owner-authorized, 2026-11-09; run 2026-11-10; local, not yet merged):** [Measured] release builds of K1, K2 and E1-H are reproducible and cut the function-level difference from K0 sharply (E1-H 322 to 17 functions, K1 338 to 105, K2 389 to 210); seL4's own elfloader boots K1 and the 4-vCPU K2 under QEMU TCG (K2 needs a device tree with PSCI `smc` and `virtualization=on`), so the plan's K1 and K2 need not be replaced to suit the Rust loader; on the E1-H baseline a root task reaches QEMU's SMMUv3 and an `edu` device and edu's DMA is seen reaching the SMMU model, **with the SMMU never enabled, so no confinement was observed** ([variants](../spikes/sel4-feasibility/results/A2a-variants.md), [Route I](../spikes/sel4-feasibility/results/RouteI.md), [A5 step 0](../spikes/sel4-feasibility/results/A5-step0.md)). The plan's Amendment of 2026-11-10 defines the Stage B matrix as a proposal for the owner. None of this is a gate result.
- **Release kernels and A5 step 1 (owner-authorized and run, 2026-11-10; not gate results):** [Measured] the release kernels K1R and K2R boot through seL4's elfloader and run Rust user code (7 and 8 functional tests, 3 of 3 runs each), logging through a user-level UART driver, and are function-for-function the recorded K1R and K2R ([ReleaseKernel](../spikes/sel4-feasibility/results/ReleaseKernel.md)). With QEMU's SMMUv3 enabled from a root task, one device stream's DMA is translated to the mapped page and refused at the unmapped and physical addresses tested, a read-only mapping is enforced and a second, unconfigured device is refused, on the E1-H kernel and on K2R; a removed mapping stops being honoured only once the invalidation command has completed ([A5 step 1](../spikes/sel4-feasibility/results/A5-step1.md)). One emulated model, the root task holding every capability: **not an A5 outcome**. The Stage B matrix of the plan's Amendment is the working experimental plan (owner, 2026-11-10).
- **A5 step 2, exploratory (owner-authorized; design reviewed before the run; run 2026-11-11; not a gate result):** [Measured] on an unmodified seL4, a stage-1 SMMU mapping survives the revocation of the frame it names, the kernel reuses the memory at once, and the device then reads and overwrites what the memory has become (a frame with new contents, or a kernel object); clearing the mapping, invalidating it and waiting for that before the revoke prevents this, and clearing without invalidating does not ([A5 step 2](../spikes/sel4-feasibility/results/A5-step2.md)). One task played every role, so this is not the A5 falsifier and A5-arm is neither passed nor failed; the record lists four ways to remove the exposure and selects none.
- **Next:** the owner's decision on the design of K3 (the options in the A5 step 2 record, against the [A5 design proposal](research/a5-design-proposal.md)), and on whether a hypervisor-mode row joins the Stage B matrix (the open question in the plan's Amendment). **Stage B, A4, the full A5 experiment (K3 and its four tests) and the comparator are not authorized.** A next experiment is proposed in the A5 step 2 record (K3 proper, with an SMMU server and a client in separate capability spaces and the four A5 tests); it presupposes the owner's choice among the options and is not authorized.
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
