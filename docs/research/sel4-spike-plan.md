# seL4 feasibility spike plan

- **Status:** Draft, awaiting owner approval. Written on 2026-11-07, before any experiment
  was run. It becomes pre-registered only when the owner's approval is recorded under
  [Amendments](#amendments) with a date and the commit SHA of the approved text.
- **Supports:** [ADR 0004](../adr/0004-kernel-foundation.md).
- **Owner approval required for:** anything listed under [Scope limits](#scope-limits).

No experiment starts until that approval is recorded. Every results file must cite the
approved commit SHA. Once approved, criteria are fixed. Loosening a criterion after seeing
a result requires owner approval, and must be recorded under [Amendments](#amendments)
with the reason.

## Hypothesis

> For Fyrkat's first system, unmodified seL4 with Rust user-space services is a stronger
> foundation than a custom Rust kernel.

This is a working hypothesis, not an architectural commitment. The purpose of the spike
is to try to break it, so experiments run in the order most likely to do that.

## Labels

Every result carries one of these labels. Results must never imply proof coverage that
the label does not grant.

| Label | Meaning | Proof claims allowed |
|---|---|---|
| **V** | Unmodified seL4, built from a `configs/*_verified.cmake` file for that exact platform | Only what the verified configurations page states at the pinned commit |
| **U** | Unmodified seL4 in any other configuration | None |
| **M** | Any modified kernel, listing every changed file | None |
| **S** | A user-space component | None. seL4's proofs never cover user space |

**No QEMU run is ever V.** There is no verified configuration for `qemu-arm-virt`. Verified
AArch64 configurations target specific boards, such as `tx2`, `bcm2711` (Raspberry Pi 4)
and `bcm2712` (Raspberry Pi 5). SMP, IOMMU, VT-x, MCS on AArch64, and AArch64 builds
without hypervisor support are all U. V builds can be compiled and compared here, but
they cannot be run here.

## Pinned inputs

| Input | Value |
|---|---|
| seL4 | 17.0.0, commit `ab504cd497d239ed7341472b7f67b56f4c42dbe1` |
| rust-sel4 | Commit recorded at the start of A1 |
| Rust for rust-sel4 | `nightly-2026-10-28`, as its repository pins |
| QEMU | 11.1.3 |
| Host | Apple M2 Pro, 16 GB, macOS 27.2 |

## Outcomes

Every experiment ends with exactly one outcome. Apply these in order and stop at the first
that holds, so the outcomes cannot overlap.

1. **Fail:** a Fail clause of the experiment holds. Every Fail clause is a mandatory
   requirement. Nothing downgrades one: not a Conditional clause, not the owner's
   acceptance of a cost, and not an amendment made after results exist.
2. **Investigate:** no Fail clause holds, but the evidence cannot yet show that the Pass or
   Conditional criteria are met. The cause may be a result outside a target, an unexplained
   cause, a result that cannot be classified yet, or something that cannot be tested.
   Investigate is a **non-passing outcome**. It is never reported or summarised as Pass or
   Conditional, and it counts as an unmet target, which is a cost, in Stage D.
3. **Conditional:** no Fail clause holds and nothing needs investigating. Every mandatory
   requirement is met, with evidence, and one or more desirable properties are met only at
   a stated cost. The results file lists each cost and the evidence that the mandatory
   requirements still hold, and the owner records acceptance of each cost. A Conditional
   clause may relax only a desirable property. It can never waive a mandatory requirement.
4. **Pass:** every Pass criterion is met, with evidence, and none of the outcomes above
   applies.

A result that no criterion of the experiment covers is Investigate, never Pass.

**Evidence for any outcome** is a results file (see [Recording results](#recording-results))
that cites the approved plan commit SHA and, for C1 and C2, the commit of the method file.
An outcome stated without that evidence is Investigate.

**Blocked.** A failure caused by a bug in spike code does not count. The bug is fixed and
the experiment is rerun. An experiment that stays blocked after three distinct, documented
approaches is recorded as **Blocked**, and is treated as Fail with the consequence listed
for it under [Consequences](#consequences).

## Assurance matrix

A2 fills this matrix. It is defined here, before any experiment, so that acceptable and
unacceptable assurance gaps are fixed in advance.

### Required properties

Sources are the requirements in [ADR 0001](../adr/0001-kernel-architecture.md). "Required
evidence" lists the only tests that count as compensating evidence for a gap. Reading code,
review and upstream reputation do not count.

| ID | Required property | ADR 0001 source | Kernel code it depends on | Required evidence |
|---|---|---|---|---|
| P1 | **Address-space isolation:** a component cannot read or write memory it was not given | Requirement 1 | Address-space, page-table and untyped retype code | B3 isolation checks, and B4 wild-write injection with unrelated components unchanged |
| P2 | **Authority integrity:** no forged, amplified or ambient authority | Requirement 2 | Capability, CNode, mint, copy, mutate and badge code | B4 illegal capability use refused with no effect, and B3 cross-client read refused |
| P3 | **Complete revocation and reclamation:** nothing is usable after revoke or destroy, and memory returns to baseline | Requirements 2 and 4 | Derivation tree, revoke, delete, finalise and untyped code | B1 baseline checks and B2 revocation tests |
| P4 | **Kernel integrity:** no user action faults or corrupts the kernel | Requirement 1 | System call decoding and fault handling | B4 with 1,000 injected faults and no kernel fault, and B3 pager crash |
| P5 | **DMA confinement:** a device reaches only memory mapped for it, and teardown blocks device access before memory is reused | Requirement 5 and the IOMMU requirement | The IOMMU mechanism, user-level or in-kernel | A5 negative test and teardown-ordering test, per architecture |

"Kernel code it depends on" is a starting list. A2a completes it, per configuration, from
the proof documentation and the preprocessed source, naming functions and files.

**Out of scope, not required and not claimed:** timing and covert channels, side channels
such as speculative execution, and information-flow proofs.

### Configurations

| ID | Configuration | Label | Required | Runs here |
|---|---|---|---|---|
| K0 | `AARCH64_verified` for a verified board | V | Yes, as the reference | Compile and compare only |
| K1 | AArch64 `qemu-arm-virt`, no hypervisor support, 1 vCPU | U | Yes | Yes, under HVF |
| K2 | K1 with SMP, 4 vCPUs | U | Yes | Yes, under HVF |
| K3 | K2 plus DMA confinement by a user-level SMMUv3 server | U kernel, S server | One of K3 or K4 | Yes |
| K4 | K2 plus an in-kernel SMMUv3 driver | M | One of K3 or K4 | Only after a Class 2 approval |
| X1 | x86-64 `q35`, SMP, VT-d | U | Yes, for ADR 0002 | Yes, under TCG |

The record states whether each configuration is MCS or non-MCS, because AArch64 MCS proofs
are not complete.

### Gap classes

Each cell of the matrix, one property in one configuration, gets exactly one class.

| Class | Meaning | Acceptable? |
|---|---|---|
| **A, covered** | Every function the cell depends on is textually identical to K0 after preprocessing, and the assumptions on the verified-configurations page hold | Yes |
| **B, configuration difference** | The code is unmodified seL4 but differs from K0 because of build options, such as SMP, MCS, no hypervisor support, platform or IOMMU. Every differing function on the property's path is listed by name. The proofs do not cover it | Yes, but only as Conditional. Every required test for the property passed, and the owner recorded acceptance |
| **C, modified by Fyrkat** | The property's path includes a Class 1 change, or a Class 2 change that was approved before implementation | Yes, but only as Conditional, with the same conditions as B |
| **D, unacceptable** | Any one of: the cell depends on a Class 3 change; it depends on a Class 2 change that was not approved first; the property rests on code that is neither covered by proof nor exercised by a required test; it depends on a trusted component that the cell does not list; a change weakens a check or alters K0's output | **No.** It is a Fail and cannot be accepted |

Trusted components are listed per cell: the kernel, the root task, a loader or boot stub,
and an SMMU server where used. A component that a property depends on and the cell omits
makes the cell class D.

A class A, B or C cell can still fail: a required test that fails is a Fail, whatever the
class.

### Pre-registered expectations

These are [Inferred] and exist so that a surprise is visible. K1 and K2 are expected to be
class B for P1 to P4, because the hypervisor option differs from K0 and SMP is outside the
proofs. K3 is expected to be class B for P1 to P4, with the SMMU server as a listed trusted
component for P5. K4 is expected to be class C for P5. X1 is not predicted. Since every
runnable configuration is U, **A2 is expected to be Conditional at best.** That is a
recorded cost, not a defect in this plan.

## Stage A: compatibility blockers

No performance work happens until Stage A is complete.

### A1. Build on this Mac

Build the kernel and a Rust root task from a clean checkout.

- **Pass:** one documented command builds both natively, and two clean builds give
  identical output or a documented cause of difference.
- **Conditional:** this works only in a digest-pinned container. The reason native builds
  are impractical must be recorded.
- **Fail:** no reproducible workflow exists without a separate Linux machine.
- **Also record:** whether user space must use nightly Rust, and which features force it.

### A2. Assurance assessment

Fill the [assurance matrix](#assurance-matrix). The assessment is deterministic and needs no
boot. It is a classification with evidence, not a percentage.

Inputs: the preprocessed `kernel_all.c` from K0 and from every other configuration in the
matrix, the verified-configurations page and proof documentation at the pinned commit, and
every patch and trusted component that other experiments produce.

**A2 runs more than once.** A2a runs first, on unmodified configurations. A2b reruns at the
end of Stage A, after any kernel patch or trusted-component addition, and again at the end
of Stage B. The last run is **A2-final**, and its outcome is the one that counts. Earlier
runs are kept as results. Stage C needs A2-final to be Pass or Conditional.

For every cell record the code the property depends on (functions and files), its gap
class, the proof-applicability statement, the trusted components, the required tests and
their results.

- **Pass:** every cell for every required property in every required configuration is class
  A, and every required test passed.
- **Conditional:** no cell is class D, at least one cell is class B or C, every such cell
  lists its gap and its required tests, those tests passed, and the owner recorded
  acceptance of each gap before A2-final.
- **Investigate:** one or more cells cannot be classified yet, or a required test has not
  run yet.
- **Fail:** any cell is class D, or any required test for a cell failed.
- **Limit:** identical text does not mean proofs hold, because concurrency can invalidate
  sequential reasoning. A textual diff shows what reviewed code is shared, and nothing more.

### A3. EL1 and HVF compatibility

Run an AArch64 `qemu-arm-virt` build without hypervisor support, under HVF, with 1 and
4 vCPUs. Use the sel4test suite where it can run. Label: U.

- **Pass:** it boots and passes on both vCPU counts with no kernel patch.
- **Conditional:** only 1 vCPU works, or a Class 1 platform or timer patch of 50 lines or
  fewer is needed (label M).
- **Investigate:** a patch of more than 50 lines is needed. It is classified under the
  [Kernel modification policy](#kernel-modification-policy) first. A patch that is not
  Class 1 is not Conditional.
- **Fail:** it cannot run under HVF. This reopens ADR 0002, whose main argument is
  native execution, but does not falsify the hypothesis alone.

### A4. UEFI boot

Boot seL4 from EDK2 on QEMU, on AArch64 and on x86-64, using the smallest Rust stub that
works. Compare `sel4-kernel-loader`, seL4's own loader, and a thin UEFI stub. Record how
hardware description reaches the kernel and user space, given that seL4 platforms are
selected at compile time.

- **Pass:** both architectures reach the root task from EDK2 with no kernel patch.
- **Conditional:** only one architecture works, or a non-Rust loader is required.
- **Fail:** a kernel patch is required, or a usable boot path cannot be found. This reopens
  ADR 0003, but does not falsify the hypothesis alone.

### A5. SMMUv3 and DMA isolation

seL4's tree contains an SMMUv2 driver and no SMMUv3 driver, while QEMU `virt` offers only
SMMUv3. Both options below must be assessed for AArch64.

1. **User-level (K3):** a trusted server owns the SMMU registers and tables, with no kernel
   change. The critical question is whether the kernel can reuse memory that a device can
   still reach, and how teardown ordering prevents it.
2. **In-kernel (K4):** a driver modelled on the SMMUv2 support, in unverified C. SMMUv2
   adds capability types, so this is **Class 2 at least**, and needs approval before it is
   implemented. See the [Kernel modification policy](#kernel-modification-policy).

A5 is two experiments with separate outcomes.

#### A5-arm: AArch64, required

Run a negative test with `-machine virt,iommu=smmuv3`: a device must reach only its mapped
region, and DMA outside it must fault and be reported. Run a teardown-ordering test: after
a mapping is torn down and its memory reused, device DMA to it must fault. Labels: S or M.

- **Pass:** K3 passes both tests with no kernel change.
- **Conditional:** K4 passes both tests, as a Class 1 change or a Class 2 change approved
  before implementation. DMA confinement is met in full. The costs are growth of the
  trusted computing base and label M.
- **Investigate:** a test has not run, or its result is ambiguous.
- **Fail:** DMA confinement is not demonstrated by either option, or the only working option
  needs a Class 3 change or a Class 2 change that was not approved.

#### A5-x86: x86-64, run if feasible

At the start of A5-x86, check in one documented step that all three of these exist:

1. QEMU 11.1.3 `q35` with `-device intel-iommu`.
2. A device model that can be told to DMA to an address the test chooses, such as the `edu`
   device, or a virtio device with `iommu_platform=on`.
3. An observable fault signal, such as a QEMU `vtd_` trace event or a fault reported to the
   guest.

[Inferred] They probably exist. This has not been checked.

If all three exist, run the same negative and teardown tests against seL4's x86-64 VT-d
support, and apply the A5-arm criteria. If one is missing, the outcome is **Investigate**
with the cause "not testable", and the reason is recorded. x86-64 is never reported as
evidence for AArch64.

- **Also record:** the status of x86-64 VT-d, which lacks interrupt remapping.

## Stage B: semantics

Stage B runs on the most verified-like configuration that works, and must record its
label. The choice between MCS and non-MCS must be stated, because AArch64 MCS proofs are
not complete.

### B1. Process lifecycle and reclamation

A Rust root server creates and destroys processes, each with its own address space,
capability space, thread and IPC buffer. Run 1,000 processes, then a soak of 10,000
cycles. Some exit normally, and some are killed while blocked in IPC.

- **Pass:** free untyped memory and capability slots return to the exact baseline at every
  checkpoint, and any IPC partner of a killed process is released.
- **Conditional:** fragmentation appears, but it is bounded and does not grow in the soak.
- **Fail:** a leak traced to the kernel, or any kernel patch being needed.

### B2. Capability revocation

Test derivation trees up to depth 1,000, and a tree of 100,000 capabilities. Include
revocation during IPC, badge cancellation, reuse of memory after revocation, and
revocation while another core is using the capability.

- **Pass:** no descendant is usable once revoke returns, no object survives, and timer
  interrupts are not delayed by more than 1 ms during the large revocation.
- **Conditional:** a Fyrkat requirement needs user-level indirection, such as revoking one
  grant among many. List each gap.
- **Fail:** any use after revocation, or unbounded interrupt delay.

### B3. User-level pager

A Rust pager serves demand-zero, file-backed and copy-on-write memory, across a soak of
1,000,000 faults.

- **Pass:** data is correct throughout, a client cannot read another client's pages,
  and a pager crash does not crash the kernel and is reported to a supervisor.
- **Fail:** any kernel patch being needed, or any isolation breach.

### B4. Driver fault isolation and restart

A virtio driver runs in its own address space. Inject 1,000 faults: null dereference,
wild writes, illegal capability use, an infinite loop, and a kill during active I/O.

- **Pass:** no kernel fault, unrelated components keep running, memory returns to
  baseline, clients recover, and restart has a median of 500 ms or less and a worst case
  of 2 s or less under HVF.
- **Conditional:** clients need an explicit reconnect protocol, which must be described.
- **Investigate:** nothing reaches the kernel or an unrelated component, but the restart
  median or worst case is above the limits. Record the cause.
- **Fail:** any fault that reaches the kernel or an unrelated component.
- **Limit:** without A5, a driver can still damage memory through DMA. Results must say
  whether DMA isolation was active.

## Stage C: performance

Stage C runs only if Stages A and B produced no Fail, and A2-final is Pass or Conditional.
Timing uses the virtual counter and is U at best. Results are valid for this virtualized
host only.

**Method files come first.** Before the first measurement run of C1, `results/C1-method.md`
must be committed, and before the first run of C2, `results/C2-method.md`. Each results
file cites the method file's commit SHA. Changing a method after its first run is an
Amendment.

### C1. IPC

Same-core call and reply, cross-core IPC, and a chain through three servers with a 4 KiB
payload in shared memory.

**1 µs is a provisional target. It is not an automatic rejection threshold.** The method
file must fix:

- **Hardware:** the host (Apple M2 Pro under HVF) and the fact that the guest is
  virtualized. macOS does not let this project pin vCPUs to core types, so the core type
  each vCPU runs on is recorded as observed, and is not fixed in advance. Results are valid
  for that setup only.
- **Counter:** the guest's `CNTFRQ_EL0`, recorded. If it is 24 MHz, one tick is about
  42 ns, which is coarse for a sub-microsecond round trip. [Inferred]
- **Workload:** the exact call, reply and payload sizes (0 bytes in message registers, and
  4 KiB in shared memory), same-core and cross-core.
- **Method:** time batches of iterations, not single iterations, with a batch long enough
  that counter resolution is under 1% of the batch. State the warm-up, the batch size, the
  number of runs and the statistic. Report median, 99th percentile and spread across runs.
- **Baseline:** published seL4 round-trip figures with their hardware stated, and a
  same-VM Linux comparison such as a Unix-socket round trip. About 850 cycles is about
  0.25 µs at 3.4 GHz, and is a published figure, not a Fyrkat measurement.

- **Pass:** same-core round trip of 1 µs or less.
- **Investigate:** above 1 µs. Record the cause, separating virtualization overhead,
  hardware differences and seL4 behaviour. This is a non-passing outcome, and not a Fail.

### C2. Page faults against Linux

Compare page fault cost on the same VM configuration, using a pinned Linux guest. This is
the primary same-hardware comparison. The method file must fix the workload set, with all
four of these: first-touch anonymous faults, file-backed faults, copy-on-write faults, and
a mixed workload that touches a working set of stated size. It must also fix the number of
runs, and the reporting. Report each workload on its own. Do not pool workloads, and do
not drop one after seeing results.

**3 times and 5 times Linux are investigation thresholds until justified.** They are not
pass or fail lines. Adopting either as a criterion needs a written justification and an
amendment.

- **Pass:** every workload is within 3 times Linux.
- **Investigate:** any workload is above 3 times. Record the cause and any identified fix.
  Above 5 times, profile as well, and record whether the cost is inherent to the design, to
  the user-level pager, or to the virtualized setup.
- **Basis:** HongMeng reports 3.4 times Linux as a real problem it had to engineer around.
  That is a published figure from a different system, not a Fyrkat result.

### C3. Multicore scaling

Run independent client and server pairs on 1, 2, 4 and 8 vCPUs under HVF. Record the
mix of host performance and efficiency cores.

- **Pass:** at least 4 times single-core throughput at 8 vCPUs.
- **Conditional:** 2 to 4 times.
- **Fail:** below 2 times.
- **Fairness:** the withdrawn custom kernel proposed the same locking design. This result
  counts against the hypothesis only if a measured alternative does better.

## Stage D: comparison with a custom Rust kernel

Stage D uses Opus, and compares only evidence that exists.

| Evidence class | Meaning | How it counts |
|---|---|---|
| **Measured** | Built and measured by this project | Full weight |
| **Published** | Running code with published results, such as Atmosphere or Redox | Weight limited by method, and by who measured it |
| **Hypothetical** | Not built | **Counts as cost, never as capability** |

For every requirement in Stages A and B, the comparison states what exists today for the
custom path, and the work needed to reach parity, based on real systems: Atmosphere (6K
verified lines plus about 3,000 trusted), seL4 (about 12,600 SLOC on AArch64), and Redox
(under 40,000 lines). A column of hypothetical entries is a bill of work, not a result.

**Optional comparator prototype, which needs owner approval:** a minimal Rust kernel slice,
with an IPC fast path and fault reflection at EL1 under HVF, would give measured numbers on
the custom side. It is proposed only if results are mixed enough that the bill of work
cannot settle the question.

## Decision rules

### The hypothesis is falsified if any of these occurs

1. A1 is Fail.
2. An experiment needs a Class 3 kernel change, or a Class 2 change that the owner does not
   approve. See the [Kernel modification policy](#kernel-modification-policy).
3. B1 or B2 is Fail through a kernel leak or use after revocation.
4. B3 or B4 is Fail through an isolation failure in the kernel or in unrelated components.
5. A5-arm is Fail.
6. A2-final is Fail.

C1, C2 and C3 never falsify the hypothesis automatically. They are reported to the owner,
and Stage D weighs them.

### Consequences

Every non-Pass outcome has a defined consequence. "Stop and report" means the work stops
and the owner decides what happens next.

| Experiment and outcome | Consequence |
|---|---|
| A1 Fail or Blocked | Falsifies (rule 1) |
| A1 Conditional | Owner decides whether to accept the container-only workflow |
| A2-final Fail | Falsifies (rule 6) |
| A2 Blocked, meaning a cell cannot be classified after three approaches | Reopens the assurance argument in ADR 0004. Does not falsify. Stop and report |
| A2-final Conditional | Reopens the assurance argument in ADR 0004, with each gap listed |
| A2 Investigate | Work continues. Stage C cannot start until A2-final is Pass or Conditional |
| A3 Fail | Reopens ADR 0002. Stage C does not run. Stop and report |
| A3 Investigate | Classify the patch first. If it is not Class 1, it is a Fail for A3, and rule 2 applies if it is Class 3 |
| A4 Fail | Reopens ADR 0003. Stop and report |
| A4 Conditional | Owner decides |
| A5-arm Fail | Falsifies (rule 5) |
| A5-arm Conditional | Owner records acceptance of the trusted computing base growth, and A2 records the cell as class C |
| A5-arm Investigate | Work continues. Stage C cannot start until A5-arm is resolved |
| A5-x86 Fail | Reopens ADR 0002 |
| A5-x86 Investigate, "not testable" | ADR 0002 records x86-64 DMA confinement as unverified. Does not falsify |
| A5 passes only on x86-64 | Reopens ADR 0002 |
| B1 or B2 Fail through a leak or use after revocation | Falsifies (rule 3) |
| B1 or B3 Fail because a kernel patch is needed | Classify the patch. Class 3, or an unapproved Class 2, falsifies (rule 2) |
| B3 or B4 Fail through an isolation breach | Falsifies (rule 4) |
| B2 Conditional | Owner decides on each user-level indirection gap |
| B4 Investigate, restart time | Reported to the owner. Does not falsify. Counts as an unmet target in Stage D |
| C1 or C2 Investigate | Reopens the performance assumptions in ADR 0004 for owner review. Does not falsify |
| C3 Fail | Reported. Counts against the hypothesis only if a measured alternative does better |
| User space requires nightly Rust | Reopens the toolchain policy |
| Each board needs its own kernel build | Reopens ADR 0003 and the hardware strategy |
| Any other Blocked experiment | Treated as Fail, with that experiment's Fail consequence |

**Stage D runs** when every experiment is Pass, Conditional with the owner's acceptance
recorded, or Investigate with its cause recorded and acknowledged by the owner. An
Investigate is never counted as a pass. A Pass does not automatically accept seL4. The
owner decides.

## Blockers and regressions

Defined before any experiment, so that outcomes can be checked against them.

**Functional blockers.** Each is a Fail, with the consequence in the table above:

- No reproducible build workflow on this Mac (A1).
- A kernel leak, or any use after revocation (B1, B2).
- Any isolation breach by the kernel, a pager or a driver (B3, B4).
- DMA confinement that is not demonstrated on AArch64 (A5-arm).
- A required experiment that stays blocked after three distinct approaches.

**Unacceptable assurance regressions** are the class D cells of the
[assurance matrix](#assurance-matrix). Each is a Fail in A2, and cannot be accepted:

- A required feature needs a Class 3 kernel change.
- A Class 2 change was made without approval before implementation.
- A change alters K0's output, weakens an existing check, or disables a security feature.
- A required property rests on code that is neither covered by proof nor exercised by a
  required test.
- A required property depends on a trusted component that the cell does not list.

## Kernel modification policy

Any kernel change is label M. Every change falls into exactly one class. The owner decides
the class during the review below. **When the class is unclear it is Class 3 until the
owner rules otherwise.**

| Class | What it is | Rule |
|---|---|---|
| **0** | No kernel change | Allowed |
| **1** | A platform or timer fix, a board constant or a device-tree change, with no new capability or invocation and no change to the object model. A driver counts only if user space cannot reach or configure it | Allowed behind a configuration flag, label M |
| **2** | A **device-specific capability extension**: new capability or object types and invocations confined to one device, such as SMMUv3 stream-table and context objects, that leave unchanged the behaviour of every existing capability type, derivation, revocation, untyped retype and finalisation | **Not disqualifying by itself.** It needs the review below and the owner's written approval **before implementation begins** |
| **3** | Any change that affects capability authority, ownership, revocation, isolation or a core invariant. That includes any change to the behaviour of existing capability types, CNode operations, derivation, mint, badge, revoke, delete, finalise, untyped retype, endpoints, notifications, the scheduler, the IPC fast path or address-space isolation, any change that alters K0's output, and any change that weakens a check or disables a security feature | **Unacceptable in this spike at any size.** It needs a new architectural decision, recorded as an ADR, before it may even be attempted. An experiment that needs one is a Fail |

### Class 2 review

Before a Class 2 change is implemented, record `results/kernel-change-<n>.md` with:

1. The design: the new objects and invocations, and every file touched. That includes
   capability-structure definitions, object-type decoding and any address-space hook.
2. How each new capability type takes part in derivation, revocation, deletion and
   finalisation, and why no existing type changes.
3. The invariants it relies on, and which published proofs it touches.
4. A test that K0's output is byte-identical with the change's flag off.
5. The negative tests that show the new objects cannot be used to break P1 to P5.
6. The maintenance burden across seL4 releases.

The owner's approval is recorded in that file. It is a **result** of the experiment, with
label M, and it counts as a cost in Stage D. It is not an Amendment, and it changes no
criterion.

### Size

**1,550 lines is an investigation trigger, not a security acceptance criterion.** At the
pinned commit the four SMMUv2 files total 1,529 lines (645, 437, 412 and 35) [Measured].
The SMMUv2 support also touches capability-structure and object-type files that this count
does not include. Re-measure at the start of A5, including every touched file.

Passing the trigger stops work until a written evaluation is recorded. Size never makes a
change acceptable. Class decides that. Evaluate by:

- **Security impact:** what it can reach, and what it can break.
- **Complexity:** how hard it is to review and to reason about.
- **Proof implications:** which proofs it touches or invalidates.
- **Maintenance burden:** the cost of carrying it across seL4 releases.

## Reconsideration criteria after the spike

If the hypothesis survives, any of these reopens ADR 0004:

1. A required kernel patch is rejected upstream, or stays out of tree for two releases.
2. Keeping up with seL4 costs over 500 changed lines in `fyrkat-rt` in two consecutive
   releases.
3. A representative workload stays above a C2 investigation threshold after
   profiling-driven work, and the owner, having seen the C2 results, records that threshold
   as a criterion with its justification.
4. On physical hardware, kernel lock contention exceeds 20% of wall time at target core
   counts.
5. A Verus or similar proof of seL4-style derivation and revocation is demonstrated at a
   cost this project could plausibly bear.
6. More than two critical advisories per year hit the unverified paths Fyrkat depends on,
   for two consecutive years.
7. seL4 goes 18 months without a release, or its licence or governance changes materially.

## Recording results

Each experiment gets `spikes/sel4-feasibility/results/<id>.md`, containing:

- The outcome and label, and the approved plan commit SHA.
- For C1 and C2, the commit SHA of the method file.
- The commits, toolchain versions and host.
- The kernel configuration, stored as a file.
- The exact commands, and raw output or measurements.
- Sample sizes and spread for any measurement.
- Limitations and unresolved risks.
- Any kernel patch, stored as a `.patch` file, and its `kernel-change-<n>.md` record.
- For A2, the filled matrix with one row per cell.

## Isolation from production

- All spike code lives in `spikes/sel4-feasibility/`, as its own Cargo workspace.
- No crate outside `spikes/` may depend on it. `cargo xtask check` enforces this.
- seL4 is fetched at the pinned commit into a gitignored directory, so no GPL-licensed
  kernel code enters this repository.
- Nothing is promoted to production. Any later implementation is rewritten under a
  reviewed plan, and spike code is deleted once its results are recorded.

## Model and budget policy

- **Sonnet:** A1, A3, A4, B1 to B4, and C1 to C3.
- **Opus:** A2 interpretation, A5 design, Class 2 review preparation, security review, and
  Stage D.
- One agent at a time, with no parallel research agents.
- Work stops at the end of each stage, with a report on results and tokens used.

## Scope limits

These require owner approval first:

- Building the comparator prototype.
- Any Class 2 kernel change, which needs approval before implementation, and any Class 3
  change, which needs an ADR first.
- Buying hardware, including a Raspberry Pi to run V configurations.
- Installing global tools beyond those already approved.
- Publishing or upstreaming anything.
- Changing any accepted criterion.
- Starting any experiment before the owner's approval of this plan is recorded.

## Amendments

### 2026-11-07: Gate 2 revisions

Made before any experiment ran, so no result was seen. The owner's Gate 2 decision 4
required them.

| Item | Before | After |
|---|---|---|
| A2 | Pass at 90% identical functions, Fail below 70% | Assessment of proof applicability, configuration differences, TCB changes and unverified components |
| C1 | Pass at 1 µs or less, Conditional up to 3 µs with the cause understood, Fail over 3 µs with no explanation from virtualization | 1 µs is a provisional target. Hardware, workload, method and baseline are defined. Above 1 µs is not an automatic Fail |
| C2 | Pass at 3 times Linux or less, Conditional 3 to 5 times with a fix identified, Fail over 5 times with no identified fix | 3 and 5 times are investigation thresholds until justified. Representative workloads |
| Kernel patches | 1,550-line total budget, and exceeding it was an unacceptable modification | Investigation trigger, judged by security impact, complexity, proof implications and maintenance |
| A5 Conditional and Fail | In-kernel driver passes "within the patch budget"; Fail when neither option works "within the patch budget" | Refer to the Kernel modification policy. This loosened the numeric bound |
| Decision rule 5 | DMA isolation cannot be enforced "within the patch budget" | Cannot be enforced without an unacceptable kernel modification |
| Decision rule 6 | C2 fails | A2 finds an unacceptable assurance regression. C1 and C2 never falsify automatically |
| Reopen table | "A2 fails" reopens the assurance argument | "A2 is Conditional" reopens it, and a C1 or C2 row was added |
| Reconsideration criterion 3 | A representative workload exceeds the C2 Fail threshold | Stays above 5 times Linux after profiling-driven work |
| Scope limits | Patch "beyond a Conditional allowance" | Also "or one that passes the investigation trigger", and the start gate was added |
| Plan status | Pre-registered | Draft, awaiting owner approval, with a start gate |

### 2026-11-07: Draft 2, response to the adversarial review and owner decisions

Also made before any experiment ran. The owner reviewed the findings and decided the
direction. The owner has **not yet approved this draft**.

| Review finding | Change |
|---|---|
| H1: the policy had no outcome rule, and the IOMMU carve-out could conflict with the ban on capability code | Kernel changes now fall into Classes 0 to 3. Class 2, a device-specific capability extension, is not disqualifying but needs a review and the owner's approval before implementation. Class 3, anything affecting authority, ownership, revocation, isolation or core invariants, needs an ADR. An unclear class is Class 3. Approval is recorded as a result, not an amendment. The SMMUv2 footprint was re-measured as 1,529 lines, not 1,550, and the count is to be redone at the start of A5 |
| H2: A2 outcomes overlapped, and "solely" and "compensating evidence" were undefined | Added the assurance matrix: required properties P1 to P5, configurations K0 to K4 and X1, gap classes A to D, and the named tests that count as compensating evidence. Removed "solely". Outcomes now follow a fixed precedence, so they cannot overlap. Conditional cannot waive a mandatory requirement |
| H3: no start gate | Added in the previous draft. Kept |
| M1: DMA rule 5 could never fire | Split A5 into A5-arm, which is required, and A5-x86, which runs if a three-part feasibility check passes. Rule 5 now concerns AArch64 only. An untestable x86-64 result is Investigate and is recorded as unverified |
| M2: sequencing and dead ends | A2 reruns as A2a, A2b and A2-final, and Stage C needs A2-final. Added a Consequences table so that every non-Pass outcome has a defined result. A2 Blocked has its own row |
| M3: vocabulary | Defined Investigate as a non-passing outcome, with a fixed precedence among all four. C1 and C2 now use Pass and Investigate. Reconsideration criterion 3 no longer adopts 5 times Linux without a recorded justification |
| M4: methods left to the experimenter | C1 and C2 method files must be committed before the first measurement run, and results cite their SHA. Vague wording removed: batches replace single iterations, the counter frequency is recorded, observed core type is recorded and not pre-defined, and the C2 workload set is fixed |
| M5: the "Before" column was inexact | Corrected in the Gate 2 table above |
| L3: unclassified outcomes | Added A3 Investigate for a patch above 50 lines, and B4 Investigate for slow restart |

**Deliberate loosening, by owner decision.** The earlier text made any change to
capability, untyped, endpoint, notification, scheduler or fast-path code unacceptable at
any size. Class 2 now allows a device-specific capability extension, which adds new
capability types, if the owner approves it before implementation. Class 3 keeps the old ban
for everything that changes existing behaviour. The earlier V-build and weakened-check bans
are kept as Class 3.

Unchanged: A1, B1 to B3, C3, Stage D, and the V, U, M and S labels.
