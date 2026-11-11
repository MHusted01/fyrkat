# seL4 feasibility spike plan

- **Status:** Approved by the owner on 2026-11-07 for the text at commit
  `46a90fac7ec09865502de1059dc9a213fa3fcd9f` (`46a90fa`). Written before any experiment was run. The approval covers this
  plan and its acceptance criteria only. It does **not** authorize running any experiment,
  implementing a Class 3 kernel change, or relaxing a criterion. See
  [Amendments](#amendments).
- **Supports:** [ADR 0004](../adr/0004-kernel-foundation.md).
- **Owner approval required for:** anything listed under [Scope limits](#scope-limits).

No experiment starts until the owner separately authorizes execution, and approval of this
plan is not that authorization. Every results file must cite the approved commit SHA
`46a90fa`. The criteria are fixed. Later commits to this file may record approvals and
other Amendments, but may not change a criterion. Loosening a criterion after seeing a
result requires owner approval, and must be recorded under [Amendments](#amendments) with
the reason.

## Hypothesis

> For Fyrkat's first system, unmodified seL4 with Rust user-space services is a stronger
> foundation than a custom Rust kernel.

This is a working hypothesis, not an architectural commitment. The purpose of the spike
is to try to break it, so experiments run in the order most likely to do that.

"Unmodified" is the hypothesis. A surviving result that carries label M, such as a Class 1
patch in A3 or K4 in A5, means the hypothesis must be restated for that case, and reopens
ADR 0004. It is not a Pass of the hypothesis as written.

## Labels

Every result carries one of these labels. Results must never imply proof coverage that
the label does not grant.

| Label | Meaning | Proof claims allowed |
|---|---|---|
| **V** | Unmodified seL4, built from a `configs/*_verified.cmake` file for that exact platform, except that a MCS configuration is U while the AArch64 MCS proof is incomplete | Only what the verified configurations page states at the pinned commit |
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
| seL4 | 17.0.0. Tag object `ab504cd497d239ed7341472b7f67b56f4c42dbe1`, which resolves to commit `62e345c240a15671484530b4e6e069ce266c28d7` [Measured]. Pin the commit |
| rust-sel4 | Commit recorded at the start of A1 |
| Rust for rust-sel4 | `nightly-2026-10-28`, as its repository pins |
| QEMU | 11.1.3 |
| Host | Apple M2 Pro, 16 GB, macOS 27.2 |

## Outcomes

Every experiment ends with exactly one outcome. Apply these in order and stop at the first
that holds, so the outcomes cannot overlap.

1. **Fail:** a Fail clause of the experiment holds. Every Fail clause is a mandatory
   requirement, and every Fail clause is written as a positive observation, such as "a
   use after revocation was observed", never as the absence of evidence. Nothing downgrades
   the outcome: not a Conditional clause, not the owner's acceptance of a cost, and not an
   amendment made after results exist. The consequence of a Fail is set separately in the
   [Consequences](#consequences) table, and is not always falsification.
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
   **Conditional applies only when the result matches one of that experiment's own
   Conditional clauses.** The general description above never creates a Conditional that an
   experiment does not list. A result that fits none of an experiment's clauses is
   Investigate.
4. **Pass:** every Pass criterion is met, with evidence, and none of the outcomes above
   applies.

A result that no criterion of the experiment covers is Investigate, never Pass.

**Evidence.** A Pass or Conditional needs a results file (see
[Recording results](#recording-results)) that cites the approved plan commit SHA and, for C1
and C2, the commit of the method file. A Pass or Conditional stated without that evidence is
Investigate. A Fail observed is a Fail whether or not its results file is complete.

**Spike bugs.** A failure caused by a bug in spike code does not count, but calling it a
bug needs evidence: the fix commit, and a reproduction of the failure before the fix. A
failure that does not reproduce is Investigate, never discarded. A failure in a soak or a
multicore test cannot be dismissed as a bug without that reproduction.

**Blocked.** An experiment that stays blocked after three distinct, documented approaches
is recorded as **Blocked**, and is treated as Fail with the consequence listed for it under
[Consequences](#consequences).

**End of spike.** When the spike's last stage ends, an Investigate on any cell for P1 to P5,
or on A5-arm, becomes a Fail with that experiment's Fail consequence. Investigate never
stands as a final outcome for a mandatory property.

## Assurance matrix

A2 fills this matrix. It is defined here, before any experiment, so that acceptable and
unacceptable assurance gaps are fixed in advance.

### Required properties

Sources are the requirements in [ADR 0001](../adr/0001-kernel-architecture.md). "Required
evidence" lists the only tests that count as compensating evidence for a gap. Reading code,
review and upstream reputation do not count.

| ID | Required property | ADR 0001 source | Kernel code it depends on | Required evidence |
|---|---|---|---|---|
| P1 | **Address-space isolation:** a component cannot read or write memory it was not given | Requirement 1 | Address-space, page-table and untyped retype code | B3 cross-client read refused. B4 wild-write injection, after which a checksum of every unrelated component's memory is unchanged |
| P2 | **Authority integrity:** no forged, amplified or ambient authority | Requirement 2 | Capability, CNode, mint, copy, mutate and badge code | B4 illegal-capability sub-tests, each refused with no effect: invoke an empty slot, invoke a capability of the wrong type, amplify rights through mint, copy and mutate, and forge a badge |
| P3 | **Complete revocation and reclamation:** nothing is usable after revoke or destroy, and memory returns to baseline | Requirements 2 and 4 | Derivation tree, revoke, delete, finalise and untyped code | B1 baseline checks and every B2 revocation test |
| P4 | **Kernel integrity:** no user action faults or corrupts the kernel | Requirement 1 | System call decoding and fault handling | B4 with 1,000 injected faults and no kernel fault, and B3 pager crash with no kernel fault |
| P5 | **DMA confinement:** a device reaches only memory mapped for it, and teardown blocks device access before memory is reused | Requirement 5 and the IOMMU requirement | The IOMMU mechanism, user-level or in-kernel | A5 negative test, A5 cooperative teardown test, A5 revoke-while-mapped test (memory reclaimed by revoke while the SMMU server still maps it), and A5 driver-killed test (driver killed during DMA) |

A required test counts as passed only when the named sub-check passed in an experiment run
on that configuration, and that experiment is not Fail. A sub-check that was not run is not
passed. Whether an experiment's overall outcome is Conditional does not matter; the named
sub-check is what counts.

**Cell to experiment map.** P1 to P4 in K1 are tested by Stage B runs on K1, and in K2 and
K3 by Stage B runs on K2. Cross-core tests (B2 revocation while another core uses the
capability) run only on a configuration with 2 or more vCPUs, so they need K2. P5 in K3 and
K4 is tested by A5-arm. A cell with no experiment mapped to it cannot exist: every required
cell has at least one run, or the configuration is not required.

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
| K4 | K2 plus an in-kernel SMMUv3 driver | M | One of K3 or K4 | Only if the [Kernel modification policy](#kernel-modification-policy) allows it |
| X1 | x86-64 `q35`, SMP, VT-d | U | **No.** Not part of A2 | Yes, under TCG, for A4 and A5-x86 only |

**x86-64 is not assessed by A2.** This spike runs no Stage B tests on x86-64, so P1 to P4
cannot be tested there. ADR 0002 must record x86-64 assurance as **not assessed by this
spike**, and not as a pass. This does not remove x86-64 as a required future platform under
ADR 0002, and it does not imply that x86-64 assurance follows from any AArch64 result.
A5-x86 is the only x86-64 security test. `configs/X64_verified.cmake` exists at the pinned
commit [Measured], so an x86-64 reference could be added later by the owner as a scope
change.

The record states whether each configuration is MCS or non-MCS, because AArch64 MCS proofs
are not complete.

### Gap classes

Each cell of the matrix, one property in one configuration, gets exactly one class.

| Class | Meaning | Acceptable? |
|---|---|---|
| **A, covered** | Every function the cell depends on is textually identical to K0 after preprocessing, and the assumptions on the verified-configurations page hold | Yes |
| **B, configuration difference** | The code is unmodified seL4 but differs from K0 because of build options, such as SMP, MCS, no hypervisor support, platform or IOMMU. Every differing function on the property's path is listed by name. The proofs do not cover it | Yes, but only as Conditional. Every required test for the property passed, and the owner recorded acceptance |
| **C, modified by Fyrkat** | The property's path includes a Class 1 change, or a Class 2 change that was approved before implementation | Yes, but only as Conditional, with the same conditions as B |
| **D, unacceptable** | Any one of: the cell depends on a Class 3 change; it depends on a Class 2 change that was not approved first; a required test for the property ran on the configuration and did not exercise the code the property rests on, which is not covered by proof; it depends on a trusted component that the cell does not list; a change weakens a check or alters K0's output | **No.** It is a Fail and cannot be accepted |

Trusted components are listed per cell: the kernel, the root task, a loader or boot stub,
and an SMMU server where used. A component that a property depends on and the cell omits
makes the cell class D.

A class A, B or C cell can still fail: a required test that fails is a Fail, whatever the
class.

### Pre-registered expectations

These are [Inferred] and exist so that a surprise is visible. K1 and K2 are expected to be
class B for P1 to P4, because the hypervisor option differs from K0 and SMP is outside the
proofs. K3 is expected to be class B for P1 to P4, with the SMMU server as a listed trusted
component for P5. K4 is expected to be class C for P5. Every runnable configuration is U or M, so **A2 can never be Pass.** By definition the best
A2 outcome is Conditional, and an A2 Conditional always reopens the assurance argument in
ADR 0004. That is a recorded cost, not a defect in this plan.

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
  A, and every required test passed. Since no required configuration is V, this cannot
  occur in this spike. It is stated so that nobody reports it.
- **Conditional:** no cell is class D, at least one cell is class B or C, every such cell
  lists its gap and its required tests, those tests passed, and the owner has recorded
  acceptance of each gap. Acceptance of a gap found at A2-final is recorded at A2-final,
  and the outcome is Conditional only once it is.
- **Investigate:** one or more cells cannot be classified yet, or a required test has not
  run yet.
- **Fail:** a cell is class D, or a required test for a cell failed, or a cell is Blocked.
  A class D or failed-test Fail falsifies the hypothesis. A Blocked cell does not. See the
  Consequences table.
- **Limit:** identical text does not mean proofs hold, because concurrency can invalidate
  sequential reasoning. A textual diff shows what reviewed code is shared, and nothing more.

### A3. EL1 and HVF compatibility

Run an AArch64 `qemu-arm-virt` build without hypervisor support, under HVF, with 1 and
4 vCPUs. Use the sel4test suite where it can run. Label: U.

- **Pass:** it boots and passes on both vCPU counts with no kernel patch.
- **Conditional:** a Class 1 platform or timer patch of 50 lines or fewer is needed (label
  M), with the Class 1 record complete.
- **Investigate:** only 1 vCPU works. K2 is a required configuration, so this blocks the
  K2 assessment, the cross-core part of B2, and C3 until it is resolved. A patch of more
  than 50 lines is also Investigate. It is classified under the
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
2. **In-kernel (K4):** a driver modelled on the SMMUv2 support, in unverified C. At the
   pinned commit, seL4's SMMUv2 support does more than add new capability types [Measured]:
   it makes `finaliseCap` for the existing VSpace capability call `smmu_cb_delete_vspace`,
   it adds a field to the existing VSpace capability (`capVSMappedCB`) and to `asid_map`,
   and it adds SMMU invalidation to the existing TLB invalidation paths. A driver that makes
   teardown ordering hold needs the same kind of hook. Under the
   [Kernel modification policy](#kernel-modification-policy), a hook into existing
   finalisation, unmapping or TLB maintenance is **Class 3**, so K4 is **unavailable under
   this spike's authorization**. It is preserved as a separately gated future architectural
   option, described under the [Kernel modification policy](#kernel-modification-policy).

A5 is two experiments with separate outcomes.

#### A5-arm: AArch64, required

Run a negative test with `-machine virt,iommu=smmuv3`: a device must reach only its mapped
region, and DMA outside it must fault and be reported. Run a teardown-ordering test: after
a mapping is torn down and its memory reused, device DMA to it must fault. Labels: S or M.

- **Pass:** K3 passes all four P5 tests with no kernel change, and teardown provably
  blocks device access before memory is reused, shown by the revoke-while-mapped and
  driver-killed tests.
- **Conditional:** K4 passes all four P5 tests, and its change is of a kind the policy
  allows, with its record complete and the owner's approval given before implementation.
  DMA confinement is met in full. The costs are growth of the trusted computing base and
  label M. If the policy allows no K4 change, this clause cannot occur.
- **Investigate:** a P5 test has not run, or its result is ambiguous.
- **Fail:** a device reached memory outside its mapping, or DMA into reclaimed memory
  succeeded, or the only working option needs a Class 3 change or a change that was not
  approved first.

#### A5-x86: x86-64, run if feasible

At the start of A5-x86, check in one documented step that all three of these exist:

1. QEMU 11.1.3 `q35` with `-device intel-iommu`, with Caching Mode off. seL4 refuses VT-d
   when Caching Mode is on [Documented, seL4 source, `intel-vtd.c`].
2. A device model that can be told to DMA to an address the test chooses: the `edu` device.
3. An observable fault signal: a QEMU `vtd_dmar_fault` trace event.

On this host, QEMU 11.1.3 lists `edu`, `intel-iommu` with `caching-mode` off by default,
and the trace events `vtd_dmar_fault`, `vtd_fault_disabled` and `vtd_dmar_translate`
[Measured]. Not yet established: whether seL4's VT-d support confines `edu` DMA on `q35`
under TCG. seL4 reports VT-d faults only through kernel `printf`, so nothing reaches user
space [Documented, seL4 source], and `edu` may ignore DMA errors [Inferred], so the test
must use the trace output and a before-and-after comparison of the target memory.

If all three exist, run the tests below against seL4's x86-64 VT-d support, unmodified (U).
If one is missing, the outcome is **Investigate** with the cause "not testable", and the
reason is recorded. x86-64 is never reported as evidence for AArch64.

- **Pass:** DMA from the device to an address outside its IO mapping leaves the target
  memory unchanged and produces a `vtd_dmar_fault` event, DMA inside the mapping succeeds,
  and after the mapping is removed and the memory reused, DMA to it produces a fault event
  and leaves the memory unchanged.
- **Fail:** DMA outside the mapping changed the target memory, or produced no fault event
  while changing it.
- **Investigate:** not testable, or a result that fits neither clause.

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
  grant among many. List each gap. Every indirection component is a trusted component for
  P2 and P3, so it is added to the matrix and A2 is rerun.
- **Investigate:** an interrupt is delayed by more than 1 ms, with no growth in the delay
  as the number of revoked capabilities grows.
- **Fail:** any use after revocation, or an interrupt delay above 1 ms that grows with the
  number of capabilities revoked, measured at 1,000, 10,000 and 100,000.

### B3. User-level pager

A Rust pager serves demand-zero, file-backed and copy-on-write memory, across a soak of
1,000,000 faults.

- **Pass:** data is correct throughout, a client cannot read another client's pages,
  and a pager crash does not crash the kernel and is reported to a supervisor.
- **Fail:** any kernel patch being needed, any isolation breach, or a kernel fault or crash.

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

**Method files come first.** Before any run of C1, including a pilot, `results/C1-method.md`
must be committed, and before any run of C2, `results/C2-method.md`. Each results file
cites the method file's commit SHA. A pilot run is allowed only to check that the harness
works. Its numbers are not recorded as results and may not change the method. Changing a
method after the first run is an Amendment.

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
and the owner decides what happens next. **Falsification ends the spike.** A Conditional
that the owner declines is a Fail, with that experiment's Fail consequence.

| Experiment and outcome | Consequence |
|---|---|
| A1 Fail or Blocked | Falsifies (rule 1) |
| A1 Conditional | Owner decides whether to accept the container-only workflow |
| A2 Fail, a class D cell or a failed required test | Falsifies (rule 6) |
| A2 Fail, a cell Blocked | Reopens the assurance argument in ADR 0004. Does not falsify. Stop and report |
| A2-final Conditional | Reopens the assurance argument in ADR 0004, with each gap listed. This always applies, because A2 cannot be Pass |
| A2 Investigate | Work continues. Stage C cannot start until A2-final is Pass or Conditional. At the end of the spike it becomes Fail |
| A3 Fail | Reopens ADR 0002. Stage C does not run. Stop and report |
| A3 Conditional | Owner decides. Label M restates the hypothesis and reopens ADR 0004 |
| A3 Investigate | Resolve it first. It blocks the K2 assessment, the cross-core part of B2, and C3 |
| A4 Fail | Reopens ADR 0003. Stop and report |
| A4 Conditional | Owner decides |
| A5-arm Fail | Falsifies (rule 5) |
| A5-arm Conditional | Owner records acceptance of the trusted computing base growth. A2 records the cell as class C. Label M reopens ADR 0004 |
| A5-arm Investigate | Stages C and D cannot start until it is resolved. At the end of the spike it becomes Fail |
| A5-x86 Fail | Reopens ADR 0002. Does not stop Stage C or D, and counts as a cost in Stage D |
| A5-x86 Investigate, "not testable" | ADR 0002 records x86-64 DMA confinement as unverified. Does not stop Stage C or D |
| A5-arm Fail and A5-x86 Pass | Both apply: rule 5 falsifies, and ADR 0002 is reopened |
| B1 Fail through a leak | Falsifies (rule 3) |
| B1 or B3 Fail because a kernel patch is needed | Classify the patch. A Class 3, or a change that was not approved first, falsifies (rule 2). An approved Class 1 or Class 2 change is applied and the experiment is rerun, with label M |
| B1 Conditional | Owner decides |
| B2 Fail through use after revocation | Falsifies (rule 3) |
| B2 Fail through interrupt delay growth | Stop and report. The owner decides whether the latency is acceptable. Does not falsify automatically |
| B2 Conditional | Owner decides on each user-level indirection gap, and A2 is rerun |
| B2 Investigate | Reported to the owner. Resolve the cause. At the end of the spike it counts as an unmet target in Stage D |
| B3 Fail through an isolation breach or a kernel fault | Falsifies (rule 4) |
| B4 Fail | Falsifies (rule 4) |
| B4 Conditional | Owner decides |
| B4 Investigate, restart time | Reported to the owner. Does not falsify. Counts as an unmet target in Stage D |
| C1 or C2 Investigate | Reopens the performance assumptions in ADR 0004 for owner review. Does not falsify |
| C3 Conditional | Reported. Counts as a cost in Stage D |
| C3 Fail | Reported. Counts against the hypothesis only if a measured alternative does better. Does not falsify and does not stop Stage D |
| User space requires nightly Rust | Reopens the toolchain policy |
| Each board needs its own kernel build | Reopens ADR 0003 and the hardware strategy |
| Any other Blocked experiment | Treated as Fail, with that experiment's Fail consequence |

**Stage D runs** when A2-final and A5-arm are Pass or Conditional, and every other
experiment is one of: Pass; Conditional with the owner's acceptance recorded; Investigate
with its cause recorded and acknowledged by the owner; or a Fail whose consequence above
does not falsify and does not stop the spike. An Investigate is never counted as a pass. A
Pass does not automatically accept seL4. The owner decides.

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

Any kernel change is label M. Every change falls into exactly one class. **Test Class 3
first, then Class 2, then Class 1**, and a change that fits Class 3 is Class 3. When the
class is unclear it is Class 3 until the owner rules otherwise, and the ruling is written
into the change's record.

| Class | What it is | Rule |
|---|---|---|
| **0** | No kernel change | Allowed |
| **1** | A platform or timer fix, a board constant or a device-tree change, with no new capability or invocation, no change to the object model, and nothing user space can reach or configure | Allowed behind a configuration flag, label M. It needs a Class 1 record (files, line counts, the K0 identity test) and the owner's confirmation before a result uses it |
| **2** | A **device-specific capability extension** that is purely additive: new capability or object types and invocations confined to one device, such as SMMUv3 stream-table and context objects. It adds no field to an existing capability type, and it does not hook into the finalisation, deletion, unmapping, retype, revocation, derivation or TLB maintenance of any existing type | **Not disqualifying by itself.** It needs the review below and the owner's written approval **before implementation begins** |
| **3** | Anything that affects capability authority, ownership, revocation, isolation or a core invariant. That includes any change to the behaviour of existing capability types, CNode operations, derivation, mint, badge, revoke, delete, finalise, untyped retype, endpoints, notifications, the scheduler, the IPC fast path or address-space isolation. It includes any hook into the finalisation, unmapping or TLB maintenance of an existing VSpace, frame or other capability, and any added field in one. It includes any change that alters K0's output, weakens a check or disables a security feature | **Unacceptable in this spike at any size, and never attempted in it.** An experiment that needs one is a Fail. Accepting one would need a new ADR and an amendment of this plan |

**Owner decision, 2026-11-07: K4 stays Class 3 and is unavailable.** seL4's SMMUv2 support
is a Class 3 change by this text, because it hooks into VSpace finalisation and TLB
maintenance [Measured]. An in-kernel SMMUv3 driver that makes teardown ordering hold would
need the same. The owner does not pre-approve any modification of VSpace finalisation or
related capability or security-critical hooks.

**Recorded limitation.** In this spike A5-arm can pass only through K3, the user-level
design. If K3 cannot meet the P5 tests, A5-arm is Fail and the hypothesis is falsified
(rule 5). The spike will therefore not show whether an in-kernel IOMMU path would have
worked. A Fail of K3 does not show that no seL4-based design can confine DMA.

**K4 as a future option.** K4 is preserved as a separately gated future architectural
option, to be considered only if K3 proves insufficient. It would need a new ADR, a plan
amendment approved by the owner, and a security review of the exact hooks. Nothing in this
plan authorizes it.

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

**A fresh `reviewer` agent pass on the record is required before the owner decides.** The
owner's approval is recorded in the file. It is a **result** of the experiment, with label
M, and it counts as a cost in Stage D. It is not an Amendment, and it changes no criterion.

**Experimental seL4 patches stay separate from this repository for now.** They are kept in
the gitignored seL4 checkout. The record states the exact upstream commit, the patch's
SHA-256, the files it touches and the line counts per file, the configurations it was
built and run in, the toolchain versions, and the reproduction instructions. seL4 kernel
code is licensed GPL-2.0, and this plan does not claim that licence categorically prevents
publishing a patch. If reproducibility needs the patches to be distributed, propose a
separately licensed repository or another compliant approach to the owner for approval
first.

### Size

**1,550 lines is an investigation trigger, not a security acceptance criterion.** It counts
the lines changed in total across all kernel patches in the spike, in every touched file,
and it does not move when re-measured. At the pinned commit the four SMMUv2 files total
1,529 lines (645, 437, 412 and 35) [Measured]. The SMMUv2 support also changes about 227
lines in shared files, so a driver of that shape is about 1,756 lines [approximate count
from the review, to be re-measured at the start of A5]. A driver of that shape therefore
passes the trigger by design.

Passing the trigger stops work until a written evaluation is recorded and the owner
approves. Size never makes a change acceptable. Class decides that. Evaluate by:

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
- Any kernel change: its `kernel-change-<n>.md` record, and the patch's SHA-256, files and line counts. The patch itself is not committed.
- For A2, the filled matrix with one row per cell.

## Isolation from production

- All spike code lives in `spikes/sel4-feasibility/`, as its own Cargo workspace.
- No crate outside `spikes/` may depend on it. `cargo xtask check` enforces this.
- seL4 is fetched at the pinned commit into a gitignored directory, so seL4 kernel code and
  experimental patches stay out of this repository for now. See the patch rules under the
  [Kernel modification policy](#kernel-modification-policy).
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
- Any kernel patch beyond a Conditional allowance, or one that passes the investigation
  trigger.
- Any Class 1 change before use, any Class 2 change before implementation, and any change
  that is or may be Class 3.
- Buying hardware, including a Raspberry Pi to run V configurations.
- Installing global tools beyond those already approved.
- Publishing or upstreaming anything.
- Changing any accepted criterion.
- Starting any experiment before the owner separately authorizes execution. Approval of this
  plan does not authorize it.

## Amendments

### 2026-11-07: Gate 2 revisions

Made before any experiment ran, so no result was seen. The owner's Gate 2 decision 4
required them.

| Item | Before | After |
|---|---|---|
| A2 | Pass at 90% identical functions, Fail below 70% | Assessment of proof applicability, configuration differences, TCB changes and unverified components |
| C1 | Pass at 1 µs or less, Conditional up to 3 µs with the cause understood, Fail over 3 µs with no explanation from virtualization | 1 µs is a provisional target. Hardware, workload, method and baseline are defined. Above 1 µs is "Investigate", never an automatic Fail |
| C2 | Pass at 3 times Linux or less, Conditional 3 to 5 times with a fix identified, Fail over 5 times with no identified fix | 3 and 5 times are investigation thresholds until justified. Representative workloads. No Fail band |
| Kernel patches | 1,550-line total budget, and exceeding it was an unacceptable modification | Investigation trigger, judged by security impact, complexity, proof implications and maintenance. No stated outcome rule yet, see review finding H1 |
| A5 Conditional and Fail | In-kernel driver passes "within the patch budget"; Fail when neither option works "within the patch budget" | Refer to the Kernel modification policy. **This is a substantive loosening of the numeric bound, not only a wording change** |
| Decision rule 5 | DMA isolation cannot be enforced "within the patch budget" | Cannot be enforced "without an unacceptable kernel modification" |
| Decision rule 6 | C2 fails | A2 finds an unacceptable assurance regression. C1 and C2 never falsify automatically |
| Reopen table | "A2 fails" reopens the assurance argument | "A2 is Conditional" reopens it, and a C1 or C2 row was added |
| Reconsideration criterion 3 | A representative workload exceeds the C2 Fail threshold | Stays above 5 times Linux after profiling-driven work |
| Scope limits | Patch "beyond a Conditional allowance" | Also "or one that passes the investigation trigger", and the start gate was added |
| Plan status | Pre-registered | Draft, awaiting owner approval, with a start gate |

Added the Blockers and regressions section, which defines the functional blockers and the
unacceptable assurance regressions up front. A1, A3, A4, B1 to B4 and C3 are unchanged, as
are the V, U, M and S labels and the changes that are unacceptable at any size.

**Open review findings against this wording, not yet resolved.** An adversarial review on
2026-11-07 found these. They need owner decisions before approval:

- The kernel modification policy has no outcome rule past the trigger, and its IOMMU
  carve-out can conflict with the ban on capability code. seL4's SMMUv2 support adds
  capability types, so an SMMUv3 driver modelled on it may need the same.
- A2's Pass and Conditional criteria overlap, "solely" and "compensating evidence" are
  undefined, and the required properties and configurations are not listed.
- Decision rule 5 needs DMA to fail on both architectures, but only AArch64 has a negative
  test.
- A2 runs before the patches and TCB additions its Fail list refers to, and one A2 Fail
  clause has no defined consequence.
- "Investigate" is not in the Outcomes vocabulary, and criterion 3 adopts 5 times Linux
  without the justification the C2 text requires.
- C1 and C2 methods are not required to be committed before the run.

The open findings above were addressed in Draft 2, below.

### 2026-11-07: Draft 2, response to the adversarial reviews and owner decisions

Also made before any experiment ran. The owner decided the direction. The owner has **not
yet approved this draft**. Two adversarial reviews fed it.

**Correction.** An earlier commit (`d0dc042`) edited the Gate 2 entry above, softening one
sentence and deleting the open-findings note, and it described the Before-column fix
wrongly. That was wrong. The Gate 2 entry is restored verbatim from `7baa6c1`, and the
Before column was corrected in `7baa6c1`, not in `d0dc042`.

| Finding | Change |
|---|---|
| Kernel policy had no outcome rule, and the IOMMU carve-out conflicted with the ban on capability code | Classes 0 to 3, tested in the order 3, 2, 1. Class 2, a purely additive device-specific capability extension, is not disqualifying but needs review and the owner's approval before implementation. Class 3 covers anything affecting authority, ownership, revocation, isolation or core invariants, and is never attempted. An unclear class is Class 3. Approval is a result, not an amendment |
| An in-kernel IOMMU driver is Class 3 by that text | Measured: seL4's SMMUv2 support hooks `finaliseCap` for the VSpace capability, adds a field to it, and adds SMMU invalidation to TLB paths. The owner decided on 2026-11-07 that K4 stays Class 3 and unavailable, and is preserved as a separately gated future option. "Class 1" was removed from the A5-arm Conditional |
| A2 outcomes overlapped, and "solely" and "compensating evidence" were undefined | Assurance matrix with properties P1 to P5, configurations, gap classes A to D, named sub-tests, and a cell-to-experiment map. A2 can never be Pass, and always reopens ADR 0004 |
| The matrix required evidence no experiment produced | x86-64 is not assessed by A2, and ADR 0002 must record that. Owner-accepted on 2026-11-07, and this does not remove x86-64 as a required platform. Cross-core tests need K2 |
| Conditional could relax mandatory requirements | A3 "only 1 vCPU" is now Investigate, not Conditional. Conditional applies only to an experiment's own listed clauses. B2 indirection components become trusted components |
| Investigate could stand in for Fail | At the end of the spike, Investigate on a P1 to P5 cell or on A5-arm becomes Fail. Fail clauses are positive observations. A "spike bug" needs a fix commit and a reproduction. Stage D needs A2-final and A5-arm to be Pass or Conditional |
| DMA rule could never fire | A5-arm, which is required, and A5-x86, with explicit criteria and measured feasibility facts. Rule 5 concerns AArch64 only |
| Sequencing and incomplete consequences | A2a, A2b and A2-final. One consequences row per non-Pass outcome, including a declined Conditional. The A2 Blocked row is a separate Fail clause |
| Vague or unfireable criteria | B2 now has a numeric Fail rule. B3 Fail includes kernel faults. C1 and C2 method files come before any run, pilots included, and C1 uses batches and records the counter frequency |
| The hypothesis says "unmodified" | A surviving label M result restates the hypothesis and reopens ADR 0004 |
| seL4 pin was a tag object | Now records the commit `62e345c2…` as well |
| Licensing of patches | The owner decided on 2026-11-07: patches stay separate for now, with upstream commit, hashes, files, configurations, toolchains and reproduction instructions recorded. No claim that GPL-2.0 prevents publishing. Distribution needs a separately licensed repository or another approved compliant approach |

**Loosenings and tightenings in Draft 2, stated in full.**

- **Loosened by owner decision:** Class 2 allows a purely additive device-specific capability
  extension, which the old text banned at any size.
- **Tightened:** A3 "only 1 vCPU" was Conditional and is now Investigate. A3 was not
  addressed by Gate 2.
- **Restored:** a patch that passes the investigation trigger needs the owner's approval.
  The A5 Pass needs teardown shown to block device access, as the first draft said.
- **Kept as loosened in the Gate 2 entry:** the numeric kernel patch bound.

Unchanged: A1, B1, C3, Stage D, and the V, U, M and S labels, apart from the MCS note.

### 2026-11-07: Owner approval of the plan

The owner approved this plan as reviewed at commit `46a90fac7ec09865502de1059dc9a213fa3fcd9f` (`46a90fa`), the head of PR 1
at that time. Before recording the approval, the plan text at that commit was checked for
the owner's three decisions on K4, x86-64 assurance and kernel patches, and the plan file
was confirmed unchanged between that commit and the commit that records this approval,
apart from the Status line, the start-gate wording, the Scope limits line and this entry.

The approval covers the plan and its acceptance criteria only. It does **not** authorize:

- executing any experiment, which needs the owner's separate authorization;
- implementing any Class 3 kernel change, including K4;
- relaxing any criterion. Any such change needs an Amendment and the owner's approval.

The first-draft and Draft 2 entries above are history. Their statements that the owner had
not yet approved the plan were true when written.

### 2026-11-08: Owner decisions on the S1 decision package

Made before any experiment ran, so no result was seen. The source is the owner's message of
2026-11-08 in the working session, which answered the checklist in
[s1-decision-package.md](s1-decision-package.md). The original criteria and pinned-input rows above are
**not edited**. Where this entry changes a pinned input, this entry governs, and the original row stays
as history. **No criterion is changed or relaxed by this entry.**

| Item | Owner decision | Effect |
|---|---|---|
| Decision 1 | Approved: the C1 and C2 [method files](../../spikes/sel4-feasibility/results/C1-method.md). Choice 1a: W1 **and** W2 both carry the 1 µs criterion. Choice 1b: the timing kernel (release, non-MCS SMP, `KernelArmExportVCNTUser` on) is a **measurement-only configuration outside the A2 matrix**. Stage C numbers are U and carry no assurance claim, and A2-final is still taken on K2. Choice 1c: K0 is `AARCH64_verified.cmake`, with the platform it sets recorded in the A2 results | Fixes interpretations the plan left open. 1b and 1c do not change a criterion |
| Decision 2 | Approved: AArch64 cross compiler `aarch64-elf-gcc` (Homebrew). `x86_64-elf-gcc` only when A4 reaches x86-64 | Tool choice. Whether GCC 16.x builds seL4 17.0.0 is an A1 finding |
| Decision 3 | Approved: rust-sel4 `v6.0.0`, its six git origins (rust-sel4, `dafny`, `hashbrown`, `offset-allocator`, `ring`, `rust-embedded-fat`, all under `github.com/coliasgroup` except rust-sel4 itself), `bindgen` 0.73.2 with the system libclang, and a spike-local `cargo deny` policy | Supply-chain approval |
| **P1** | Approved: the pinned input "rust-sel4" is the tag `v6.0.0`, commit `c819c27b076130cba9821c4555f23773e4b0bffd`, and "Rust for rust-sel4" is `nightly-2026-08-21`. The root-task demo is `c13bdae64a860dfe1d3064717f4096e63bb7dff2` | Replaces the plan's `nightly-2026-10-28` (Pinned inputs table) and fills "commit recorded at the start of A1". A pinned input, not a criterion |
| **P2** | Approved: the plan's C1 sentence "About 850 cycles is about 0.25 µs at 3.4 GHz" is corrected. The 850 cycles equals the Cortex-A57 call plus reply sum (419 + 431) at 1.9 GHz, about 0.45 µs [Inferred: the plan does not name its source]. The 3.4 GHz clock belongs to the x86-64 rows of the sel4bench performance page [Documented] | The sentence was context, not a criterion. It is not edited above |
| Decision 4 | Approved: **Tier 1 installation only**: rustup `nightly-2026-08-21` with `rust-src`, `llvm-tools-preview`, `rustc-dev` and target `aarch64-unknown-none`; a Python virtual environment under `spikes/sel4-feasibility/.venv` with `sel4-deps==0.9.0` and requirements pinned with hashes; Homebrew `aarch64-elf-gcc`. Tiers 2 and 3 are **not** approved and are confirmed again at their own gates | Any other missing package stops the work and is asked about |
| Decision 5 | Approved: creating `spikes/sel4-feasibility/Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml` and `deny.toml`. Any `.cargo/config.toml` or `build.rs` is **not** approved | Gated files, owner-approved |
| Decision 6 | Approved: the spike nightly rule, added to `docs/standards/toolchain.md` | Policy text |
| Decision 7 | Approved: freeze with `brew pin`, record versions and resolved paths, and stop on drift | Procedure |
| Decision 8 | Authorized **conditionally**: A1, A3 and A4 (Sonnet) and the A2a interpretation (Opus), under this plan and the method files, one agent at a time, stopping with a report at the end of this part of Stage A. The A1 approach order and counting proposed in the decision package apply. Conditions: the independent review of the PR 6 head has passed with no unresolved material finding, PR 6 is merged to `main`, only Tier 1 is installed, and each experiment's entry criteria are confirmed before it starts | Execution scope. Nothing starts before the conditions hold |
| P3 | Deferred until Stage D | The comparator is not authorized |
| P4 | Declined as currently designed | B2 is unchanged |
| P5 | Deferred until the A5 design gate | The A5 question (class D, or Investigate) stays open. No loosening |
| A5 | **Not authorized** | Held for a reviewed design and its own authorization |

**Not authorized by this entry:** A5, the comparator or any custom-kernel prototype, Tier 2 or Tier 3
installation, any dependency or tool not listed above, a Class 3 kernel change including K4, and
relaxing any criterion. The first-draft, Draft 2 and earlier entries remain history.

### 2026-11-08: Correction to the bindgen version, and method corrections from the final review

Made before any experiment ran. An independent review of the PR 6 head found these. **No criterion
is changed.**

| Item | Correction | Effect |
|---|---|---|
| `bindgen` | The entry above and decision 3 said `bindgen` 0.73.2. That is the version on rust-sel4 `main`. At the approved `v6.0.0` (`c819c27`), `crates/sel4/sys/Cargo.toml` asks for 0.72.1 and the lock resolves 0.72.1 [Documented]. This entry does not edit the rows above. The owner's answer is in the next row | A different version of an approved dependency is not approved by default |
| `bindgen` owner answer | The owner approved `bindgen` 0.72.1 as locked at `v6.0.0`, that is the dependency tree locked at `c819c27`, on 2026-11-08. Versions that appear only in the demo's own lock are not covered, and any such difference stops the work and asks. The other options, 0.73.2 or the unreleased `f631577`, were not chosen | A1 may run cargo builds on that tree, under the guards below |
| Member crates | The owner approved creating member-crate `Cargo.toml` files under `spikes/sel4-feasibility/` only, each listed in the A1 results, on 2026-11-08. `.cargo/config.toml` and `build.rs` still stop and ask | Extends decision 5 to member crates |
| P5 and the A5 question | In the P5 row above, "No loosening" means this: choosing Investigate where the class D wording applies would itself need an Amendment with its reason | Clarification only |
| C2 F3 | The pinned Debian kernel is built with `CONFIG_INIT_ON_ALLOC_DEFAULT_ON=y` [Documented], so Linux is expected to zero a copy-on-write destination page [Inferred]. The seL4 headline pager now zeroes explicitly in F3 as well as F1, and the Linux command line and `init_on_alloc` state are recorded | Removes a bias towards a Pass. The method is stricter |
| C2 untyped reset | A retype from an untyped with no children resets it, and boot untypeds start with their free index at the end, so the first retype resets and clears the whole untyped [Documented: seL4 `boot.c` and `untyped.c`]. The pager does a throwaway retype before every timed phase, F1 included | Removes a hidden cost from the first timed batch |
| Rust builds | Builds in the rust-sel4 checkout set `RUSTUP_TOOLCHAIN=nightly-2026-08-21` and `RUSTUP_AUTO_INSTALL=0`, so that rustup does not install the checkout's extra targets (Tier 2 and 3 are not approved) | Enforces the Tier 1 limit |
| Homebrew | The install sets `HOMEBREW_NO_INSTALL_UPGRADE=1`, which only stops the named formula being upgraded. The control is pin-and-record: `brew list --versions` is compared before and after, and a dependency upgrade that cannot be prevented is recorded and reported | Enforces decision 7 |

### 2026-11-08: Owner confirmation of the A1 and A3 outcomes

Recorded after the experiments ran. It changes **no criterion** and relaxes nothing. The source is the
owner's message of 2026-11-08 in the working session.

| Item | Owner decision | Effect |
|---|---|---|
| A1 | Accepted as **Pass**, label U, with its documented reproducibility limitation (two clean builds on one machine and path, and a boot image that differs only by QEMU's random device-tree seeds). Record: [A1](../../spikes/sel4-feasibility/results/A1.md) | The A1 outcome stands |
| A3 | **Confirmed as Fail** under the approved plan, on the reported evidence: unmodified non-hypervisor seL4 does not boot under HVF with 1 or 4 vCPUs on the Apple M2 Pro because the guest reports 8-bit ASIDs. Record: [A3](../../spikes/sel4-feasibility/results/A3.md) | The A3 outcome stands. The Consequences row applies: it reopens the ADR 0002 architecture question, Stage C does not run, and work stops |
| Meaning of the A3 Fail | It reopens the architecture question in ADR 0002 (native execution on the Mac). **It does not automatically reject seL4 as Fyrkat's kernel candidate** | ADR 0002 and ADR 0004 are not edited by this entry |
| Push | The owner authorized pushing `spike/s1-workspace` and opening a pull request, after a focused independent review. **Merging is not authorized** | Preserves the evidence |
| Tooling deviations | To be documented as deviations requiring review. The message is **not retroactive blanket approval**. Record: [deviations](../../spikes/sel4-feasibility/results/deviations.md) | Nothing in that record is approved |
| `cargo deny` advisory | To be investigated for the dependency path and impact without weakening the policy or introducing a replacement | Path recorded in [A1 evidence 19](../../spikes/sel4-feasibility/results/A1/19-unsafe-libyaml-path.txt) |
| Stop condition | **Stays in force.** A4, A2a, A5, kernel modifications and additional tool installations are not authorized | The next step is an architecture decision by the owner |

### 2026-11-08: Record of earlier owner answers, and corrections after the evidence review

Recorded before the pull request for the A1 and A3 results. **No criterion is changed.** An independent
review of the results found that some owner answers given in the working session were in no Amendment, and
that parts of the A3 record were wrong. This entry records them. It does not edit the entries above.

| Item | Record | Effect |
|---|---|---|
| Python environment | During A1 the owner approved Homebrew Python 3.12.16 for the spike venv, and `setuptools` and `wheel` installed there only, pinned by version and SHA-256, in answer to a question that also proposed building `pyfdt` with `--no-build-isolation` (the build method was the agent's proposal). `packaging` was not named: it is `wheel`'s own dependency | Tier 1 detail. `packaging` is listed as a deviation |
| `protobuf` | During A3 the owner conditionally approved `protobuf` 7.36.2 in the spike venv only, with exact version and SHA-256 pinning, **only if** no compatible pinned protoc existed on Apple Silicon without Rosetta or a system install, and **only if** the override was isolated to nanopb. The second condition held: no other consumer imports `protobuf`. The first was **not tested as written**: the agent built protoc 3.20.3 locally from a pinned commit, a new tool the owner has not individually approved, and whether that counts as a practical compatible protoc is for the owner. **The override was not used** | The `sel4-deps` pin is intact. protoc 3.20.3 is listed as a deviation |
| Clarification | The earlier row "Nothing in that record is approved", for the deviations file, means that file is not itself an approval. It lists rows that record specific owner answers (marked owner-approved there) beside rows that are not approved | Wording only |
| Correction to the A3 record | The first A3 record said the kernel failed the ASID check under HVF "with 1 and 4 vCPUs". The "4 vCPU" image was a single-node kernel run with QEMU `-smp 4`. A repeat with a real 4-node SMP kernel stops earlier, in the elfloader (`HVC is not supported for PSCI`), under both HVF and TCG, so its ASID check was not reached. The 1-vCPU measurement stands. It was also wrongly recorded that sel4test had only started under TCG: it passed (124 tests, 59 disabled) | The 1-vCPU measurement stands, and **in the agent's assessment the A3 outcome is unchanged**. The owner's confirmation of A3 was given before this correction, and **is requested again** |
| Correction to the cpio deviation | A custom cpio stand-in was written on the wrong belief that GNU cpio was unavailable. GNU cpio 2.15 was already installed. The stand-in was removed and the builds repeated with GNU cpio | Fewer unapproved tools |

### 2026-11-08: Privacy review, and replacement of the published spike branch

Recorded with the sanitized replacement. **No criterion, outcome or method is changed.** The source is the
owner's messages of 2026-11-08 in the working session.

| Item | Record | Effect |
|---|---|---|
| Finding | The A1 and A3 raw logs were pushed (pull request 7, branch `spike/s1-workspace`) before a privacy review. They held the author's local home path and user name (about 720 times in 26 files), the full Homebrew inventory and three unrelated third-party tap names. No email address, token, key, host name or binary was found. `main` was never affected | Exposure in the old branch only |
| Owner decision | The owner chose to replace the published history, **narrowly**: only `spike/s1-workspace` and pull request 7, not `main` or any other branch, and no force-push of a protected branch | Authorization, not a blanket one |
| What was done | Pull request 7 was edited to remove the path, closed with an explanation, and its remote branch deleted. A replacement branch, `spike/s1-workspace-sanitized`, was built from `main` in three commits whose files are byte-identical to the reviewed tree, with the logs replaced by sanitized copies. The raw originals are kept only locally, outside Git. A new pull request was opened with a sanitized description | See [EVIDENCE-PRIVACY](../../spikes/sel4-feasibility/results/EVIDENCE-PRIVACY.md) |
| Evidence integrity | `verify-evidence.py` re-checks 29 conclusions from the public copies alone and passed from a clean checkout. A1 and A3 outcomes, measurements and methodology are unchanged | The A1 Pass and A3 Fail stand as recorded |
| **Remaining exposure** | The original commits may still be retrievable through GitHub's retained references for pull request 7, by commit SHA, and from existing clones or forks. Pull request 7's edit history may show its original text. **This is not a claim of complete erasure** | Removing retained references needs a GitHub Support request, which is the owner's decision |
| Stop condition | Unchanged. A4, A2a, A5, kernel modifications, further tool installs and any architecture change remain unauthorized | |

### 2026-11-08: Owner re-confirmation of A3, and the owner's direction on ADR 0002

Recorded after the correction entry above and after PR 8 reached `24634be`. It changes **no criterion**,
relaxes nothing and edits no ADR. The source is the owner's message of 2026-11-08 in the working session.

| Item | Owner decision | Effect |
|---|---|---|
| A3 | **Re-confirmed as Fail (label U)** for the tested configuration: unmodified non-hypervisor seL4 17.0.0 under HVF on the owner's Apple M2 Pro, 1 vCPU. The owner's condition: the mislabeled "4 vCPU" image **must not be presented as valid SMP evidence** (it was a single-node kernel run with QEMU `-smp 4`; a real 4-node SMP kernel stops earlier, in the elfloader, under HVF and TCG) | Supersedes the earlier "requested again" status. The A3 outcome stands as recorded in [A3](../../spikes/sel4-feasibility/results/A3.md) |
| ADR 0002 direction | **AArch64-first is retained as a provisional direction**, and **seL4-first as a working hypothesis**. QEMU TCG is acceptable for early development and testing, but **must not be represented as equivalent to hardware acceleration or to physical hardware validation** | An owner decision recorded here. **ADR 0002 and ADR 0004 are not edited, and neither is Accepted.** ADR 0002 stays Provisional and ADR 0004 stays Proposed. The A3 Fail has not been resolved into an ADR change; any edit to either ADR needs its own owner-approved change |
| Push | The owner authorized pushing `24634be` alone to PR 8's branch. That was done, and the three required checks passed on it | Authorization used |
| Review and merge | The owner authorized one focused independent review of PR 8, fixes to material findings within PR 8's scope, and a **conditional** merge of PR 8: only if the review explicitly returns MERGE-READY, all required checks pass on the final head, the evidence verifier passes, and no unresolved material security or correctness finding remains. If any condition fails, nothing is merged | Conditional authorization. Merging is not otherwise authorized |
| Stop condition | **Stays in force.** A2a, A4, A5, the comparator, new tool installations, kernel modifications and any criterion change are not authorized. S1 execution does not resume automatically after the merge | The next experiment needs its own authorization |
| PR 7 | No GitHub Support request at this time | Retained references stay as recorded in the privacy entry above |

### 2026-11-08: Owner rulings on the independent review of pull request 8

Recorded after the independent review of PR 8 returned NOT MERGE-READY. **No criterion is changed and no
outcome is changed.** The finding numbers (F1 to F18) are the review's. The source is the owner's message of
2026-11-08 in the working session.

| Item | Owner ruling | Effect |
|---|---|---|
| F1: decision rule 2 | **Decision rule 2 applies.** The tested HVF-specific configuration fails the approved A3 requirement, and passing it would need a prohibited Class 3 kernel change under the currently available options. The ruling is **not** generalized into a rejection of seL4 on TCG or on other hardware. seL4-first and AArch64-first are retained only as **provisional, broader hypotheses**, subject to the reopened architecture decision | Resolves the conflict between the Consequences row, the A3 clause ("does not falsify the hypothesis alone") and decision rule 2, which the A3 record had settled silently. The A3 record now states it. ADR 0002 stays Provisional and ADR 0004 stays Proposed. No ADR is edited |
| F2: six `Cargo.lock` differences | **Not approved.** Enumerate them: approved against resolved versions, dependency paths, reasons, advisories, and whether restoring the approved versions is feasible. **Preserve the original A1 lockfile and results** until the owner approves a resolution. A read-only investigation only: no A1 re-run, no regeneration of dependencies, no change to the lockfile | The investigation is recorded as [deviations D13](../../spikes/sel4-feasibility/results/deviations.md). The spike `Cargo.lock` and the A1 results are unchanged. **F2 is unresolved, and PR 8 is not to be merged while it is** |
| F7: nightly Rust | The owner **acknowledges that A1 triggered** the pre-registered consequence "User space requires nightly Rust: reopens the toolchain policy". The existing `nightly-2026-08-21` approval stays valid for the isolated S1 experiment. It **does not establish a permanent Fyrkat-wide nightly policy** | The trigger is recorded in A1. **The long-term toolchain decision is unresolved** and is not made here |
| F10: `unwrap` and `assert_eq!` | A **one-time exception** for the three existing `unwrap()` calls and one `assert_eq!` in the experimental A1 root task (`crates/root-task/src/main.rs`, lines 22, 30, 31 and 62). Acceptable because the code is disposable, isolated spike code. **It does not apply to production kernel or userspace code, or to any future experiment** | Recorded as deviation D11. AGENTS.md is unchanged |
| Documentation corrections | Authorized within PR 8's existing scope: F1, F3, F4, F5, F7, F8, F9 and F10, including sanitized configuration excerpts for claims the published evidence could not verify, and the lower-severity sanitizer and verifier fixes without changing experimental results. F3 must describe the branch-history replacement and the continued accessibility of the original commits accurately, and must not claim erasure. F5 must make the verifier check configuration contents | Done in PR 8 and listed in its description. No experimental result, lockfile or recorded outcome is changed |
| Push, review, merge | Committing and pushing the approved corrections, including `05c40b2`, to PR 8 is authorized, with signing, DCO, privacy and CI requirements. A focused independent **delta** review follows. The conditional merge authorization applies **only if every material finding, F2 included, is resolved and the reviewer explicitly returns MERGE-READY** | Merge is not authorized while F2 is unresolved |
| Stop condition | **Stays in force.** A2a, A4, A5, the comparator, new tool installations and kernel changes are not authorized | |

### 2026-11-08: Correction to the provenance statement in the privacy entry

Recorded after the delta review of pull request 8. **No criterion, outcome or method is changed.** The entry
"Privacy review, and replacement of the published spike branch" says the replacement commits' files are
"byte-identical to the reviewed tree". That is imprecise. They are identical to a local, unpublished commit
(`81a2ca7`) that had no independent review, and they differ from the reviewed but unsanitized `c99300d`
(36 files, including the sanitizer and verifier scripts, which `c99300d` did not have). The independent review of
pull request 8 then examined the sanitized files themselves. The entry above is not edited: Amendments are
append-only.

### 2026-11-08: Owner decisions on F2, F13 to F16 and F18, and the result of the A1 rerun

Recorded after the delta review of pull request 8 and after the rerun. **No criterion is changed and no earlier
outcome is changed.** The source of every row except "Rerun result" is the owner's message of 2026-11-08 in the working session. "Rerun result" is the agent's measurement, recorded for the owner's review, and is not an owner decision or an acceptance.

| Item | Owner decision | Effect |
|---|---|---|
| F2 | **Option 2:** restore the six `Cargo.lock` dependencies to the versions approved in rust-sel4 `v6.0.0`. The four offline `cargo update --precise` operations are authorized, provided they affect only the spike lock file and add no other dependency change. If an approved version cannot be restored without other changes, stop and report | Done. The four operations changed only `spikes/sel4-feasibility/Cargo.lock`: four downgrades and two removals, and every registry package of the result is, with the same version and checksum, in the approved lock. Deviation D13 is resolved |
| A1 rerun | **One narrowly scoped rerun** with the corrected lock, the same methodology and the same acceptance criteria. Preserve the original A1 evidence and hashes unchanged. Store the new run as a separate, clearly identified verification result. Compare the kernel, loader, root task and boot image with the original, accounting for the QEMU device-tree randomness. If the root task or another relevant output changes, document the difference and its implications and do not silently replace the original A1 result | Done as a separate result: [A1 rerun](../../spikes/sel4-feasibility/results/A1-rerun.md). Two clean builds were made, because the criterion compares two builds |
| Rerun result (the agent's measurement, **not an owner decision**) | *Not an owner decision; recorded for the owner's review. Source: [A1 rerun](../../spikes/sel4-feasibility/results/A1-rerun.md).* The acceptance criterion holds again (label U) in the agent's reading. The kernel and loader are identical to the original. **The root task differs** (`a7c6be9a…` to `64fcc25c…`): 8 of 4,795 instruction words differ, all address computations [Measured]. The cause is a hashed Cargo build-script directory name embedded in the binary, which depends on the dependency set [Inferred: Cargo's behaviour, not tested in isolation]. The image differs only by the root-task bytes and the device-tree seeds, and every differing byte is accounted for [Measured] | The original A1 result and evidence stand unchanged, and the owner has not yet accepted or rejected the rerun. A root-task hash must name its lock. No behavioural test exists, because the A1 image has never booted |
| F13 to F16 | Approved as documentation-only corrections, provided they change no experimental outcome, acceptance criterion or architecture decision | None did |
| F18 | Retain the original raw evidence and the local backup. Implement a narrowly scoped **local** safeguard against accidentally pushing the unsanitized branch or its original commits. Do not delete the backup, rewrite history, or modify global Git configuration | Done as deviation D16: a local, untracked pre-push hook behind a local `core.hooksPath`. The backup, the branch and the history are untouched, and global Git configuration is unchanged |
| Next steps | After the rerun: run the complete repository checks and the evidence verifier, update the evidence and deviations documentation, request a final independent delta review, push the reviewed corrections to PR 8 and verify CI on the final remote head. **Merge PR 8 only if** the reviewer explicitly returns MERGE-READY, all required checks pass, the evidence verifier passes, and no material finding remains. If any condition fails, stop and report. After merging, report the final `main` commit and stop for the next architectural decision | The conditional merge authorization from the earlier entry stands under these conditions |
| Stop condition | **Stays in force** for everything else: A2a, A4, A5, the comparator, new tool installations and kernel changes are not authorized | |

### 2026-11-08: Owner direction after the merge of pull request 8

Recorded after pull request 8 was merged as `07c35e2`. **No criterion is changed, no outcome is relabelled,
and no ADR is accepted.** The source of every row is the owner's message of 2026-11-08 in the working
session, except where a row says it is a request or a proposal.

| Item | Owner decision | Effect |
|---|---|---|
| A1 rerun | **Accepted as Pass (label U), limited to the tested build-reproducibility criterion.** The changed root-task hash must stay associated with its dependency lock. No runtime or behavioural validation is claimed | Supersedes the "not yet accepted" status in the entry on the A1 rerun above (that entry is not edited). The original A1 result and evidence are unchanged |
| A3 | **A3 Fail (label U) is confirmed under the original criteria.** Decision rule 2 applies to the tested HVF-specific hypothesis. A3 is not relabelled and its acceptance criteria are not weakened | No change to A3. It repeats the earlier ruling without widening it |
| ADR 0002 | **AArch64-first stays provisional**, with QEMU TCG as the initial local development backend. Document that unmodified seL4 17.0.0 did not boot under HVF on the tested M2 Pro configuration, and that this does not establish incompatibility on every Apple Silicon host | Recorded in [ADR 0002](../adr/0002-initial-cpu-architecture.md), which stays Provisional |
| ADR 0004 | **seL4-first stays a provisional working hypothesis**, not an Accepted architecture decision. The broader hypothesis is distinguished from the failed HVF-specific configuration | Recorded in [ADR 0004](../adr/0004-kernel-foundation.md), which stays Proposed |
| Toolchain | `nightly-2026-08-21` stays approved **for S1 only**. The long-term toolchain policy stays unresolved | No change |
| A5 and Class 3 | **A5 and any Class 3 kernel change stay blocked** | No change |
| Documentation | A narrowly scoped update to ADR 0002, ADR 0004, these Amendments, the roadmap and the handoff, preserving the ADRs' actual statuses and the original experiment outcomes | Done on a local branch. It is not pushed and not merged: new changes need explicit authorization |
| Review | Use a focused independent review for the documentation changes, then report the review outcome and the proposed experiment. Do not merge or push new changes without explicit authorization | The review is requested by the owner and is reported separately. Its findings are the reviewer's, not owner decisions |
| Deviations D1 to D16 | **Request:** a concise disposition matrix: each deviation's risk, whether it was already explicitly approved, and whether further owner approval is required. Blanket approval is not to be inferred | A proposal by the agent, for the owner's decisions. **Nothing is approved by it** |
| Next experiment | **Request:** propose one bounded experiment to boot the existing Rust root task under QEMU TCG, with success criteria, expected artifacts and stop conditions. **Do not execute it yet** | A proposal only. Not authorized |
| Objective | The objective is to reach a working Rust user-space component on seL4 as quickly as the evidence and the approved security constraints permit. Completed research is not to be reopened, and the planning phase is not to be extended unnecessarily | Guides the proposals. It grants no authority and changes no criterion |
| Stop condition | A2a, A4, A5, the comparator, new tooling and kernel modification are **not authorized** | In force |

### 2026-11-08: Owner decisions on the documentation PR, six deviations, PR 9 and E1 Route II

Recorded from the owner's later message of 2026-11-08 in the working session, which answered the requests in the entry
above. **No criterion is changed, no outcome is relabelled and no ADR is accepted.** Nothing here is a blanket approval
of future deviations. The disposition-matrix draft the owner refers to was not preserved in the repository, so the
limits below are those in [deviations.md](../../spikes/sel4-feasibility/results/deviations.md) and in the owner's words.

**Provenance of the E1 specification.** The E1 proposal the owner chose is section 2 of a session draft (`s1-proposals.md`,
"Revised after the independent review", written on 2026-11-08 in the scratchpad of an earlier session, outside Git). The parts of
it that apply to Route II are **quoted verbatim at the end of this entry as the baseline for "without weakening"**. The
specification above that quotation applies the baseline to Route II. Its differences from the baseline are these, and each one
states a fact or makes a check stricter, none makes one weaker: (1) the Route I items do not apply; (2) the boot banner is named
as two strings and `badge = 0x…` as `0x1337`, which the source fixes; (3) the Fail clause also names a loader exception or panic and
an abort reported by the loader or QEMU, which is how the failure in A3 log 02 appeared; (4) Investigate also covers any unmet
Pass condition, not only a missing marker; (5) "diagnostic boot" and "approach" are defined; (6) stop condition (g), a
configuration that differs from the table, is added; (7) the loader's hash may differ from A1's, a disclosure [Inferred]; (8) the
build recipe is the proposal's "a variant of `build.sh`", written as a separate script so that `build.sh` is unchanged; (9) the
consequence, the artifact list and the "does not mean" list carry additions, and stop (a) omits the elfloader, which belongs to
Route I. All of these are stricter or inapplicable, and "three clean boots" is read as "three boots of the same image, each from a
fresh QEMU start". **If the
specification and the quotation ever disagree, the stricter reading governs.**

| Item | Owner decision | Effect |
|---|---|---|
| Documentation update | Commit and push the update on `docs/s1-direction-record` after the independent reviewer checks the eight LOW wording edits made after the previous READY verdict. Address material findings, preserve every experiment outcome and ADR status, run `cargo xtask check` and the evidence verifier, use signed, DCO-compliant commits and open a PR. **Merge: conditionally authorized**, only after an explicit MERGE-READY verdict on the final head and all required CI checks pass | The update is the five files of the previous entry plus `deviations.md` (the owner asked for the D3 wording to be corrected) and this entry. If any condition fails, stop and report |
| PR 9 | **Do not merge and do not change dependencies yet.** Investigate the two high-severity `protobuf` alerts: affected dependency paths, whether the S1 tooling exercises the vulnerable code, and whether a compatible `protobuf<4` remediation exists. Report a concrete recommendation. Passing CI is not proof of compatibility | Investigation only. The report is made to the owner and records no decision here |
| D2 | **Approved for the isolated S1 research scope only.** The existing locally built `protoc` 3.20.3 is accepted for the historical evidence, with its missing source-archive hash documented | The missing hash stays documented. The approval covers the existing evidence only, not building other tools or any other use of this one |
| D3 | **Approved for S1 only:** the binutils install and the `--ignore-dependencies` option. Wording that implies broader prior authorization is to be corrected | Corrected in `deviations.md`: decisions 2 and 4 name only `aarch64-elf-gcc`, and none of the earlier decisions named the install option |
| D7 | **Approved for S1 only:** the additional `packaging` dependency, within the isolated Python environment | `setuptools` and `wheel` were already approved |
| D9 | **Approved:** the existing experimental `boot-image.py` and ID-register probe tooling, **including narrowly scoped reuse for E1** | No other new use is covered |
| D10 | **Approved for S1 research only:** the `GPL-2.0-only` loader. **No production licensing decision may be inferred** | The spike-local `deny.toml` is unchanged |
| D14(b) | **Approved as experimental evidence tooling:** the sanitizer and the verifier. Independent verification of their correctness continues | The reviewer keeps checking them. New output, such as E1's, counts as evidence only after that check. Evidence already reviewed (A1, A1 rerun, A3) keeps its status |
| Other deviations | Not addressed by this decision. D1, D5, D6, D8, D12, D14 (a, c, d), D15 and D16 stay exactly as `deviations.md` records them: this entry adds no approval to them (the approvals and owner requests that file already records for D5, D6 and D16 are unchanged), and the others stay not individually approved. D4, D11 and D13 stay settled as recorded | No change |
| E1 | **Route II chosen** and the plan Amendment below authorized. **E1 runs only after the documentation PR is merged.** Success criteria, three boots, sanitized evidence and stop conditions are used **without weakening**. No change to kernel, loader or root-task source; no new tool; no unrelated dependency change. If E1 needs an unapproved configuration, a source change, a tool installation or a broader architectural change, stop and report | Specified in the next section |
| Restrictions | A2a, A4, A5, the comparator and Class 3 kernel modifications **stay blocked**. After E1: record the results, request independent review, and **do not proceed to another experiment** | In force |

#### E1 specification (authorized by the owner's Route II decision; runs only after the documentation PR is merged)

**Purpose.** Show whether a hypervisor-enabled seL4 17.0.0, the pinned Rust loader and the existing Rust root task boot and
run to `TEST_PASS` on a software-emulated (TCG) AArch64 machine. **Functional validation only, label U.**

**Why this configuration.** The Rust loader enters the kernel at EL2 and has no AArch64 path to EL1 [Documented: rust-sel4
loader source and [A3](../../spikes/sel4-feasibility/results/A3.md), the finding "`sel4-kernel-loader` v6.0.0 supports only EL2 on AArch64"]. Under TCG with `virtualization=on` the A1
image (a kernel built without hypervisor support) took an instruction abort at `0xffffffffc0000000`, the non-hypervisor
kernel's high entry address [Measured: A3 log 02, where the loader's EL2 exception handler printed it]. The kernel and the loader
must therefore match, and the A1 binaries cannot be used [Inferred].

**Configuration "E1-H" (an experiment-only configuration).** It is **not** a row of the [Configurations](#configurations)
table, adds no cell to A2 and does not change K1, which stays "no hypervisor support". It is not a Class 1, 2 or 3 change
because the kernel source is unmodified; it is a build option.

| Input | Value |
|---|---|
| Kernel | seL4 17.0.0, commit `62e345c240a15671484530b4e6e069ce266c28d7`, unmodified. A1's CMake options **except** `-DKernelArmHypervisorSupport=ON`: `KernelPlatform=qemu-arm-virt`, `KernelVerificationBuild=OFF`, `ARM_CPU=cortex-a57`, 1 node, non-MCS, cross prefix `aarch64-elf-` |
| Loader and `add-payload` | rust-sel4 `v6.0.0` (`c819c27b076130cba9821c4555f23773e4b0bffd`), unchanged source, built from its own lock, as in A1. The loader's build reads the kernel install directory, so **its hash may also differ from A1's [Inferred]**; the loader's hash must stay tied to this configuration |
| Root task | The unchanged `crates/root-task` source and the unchanged `Cargo.lock` of the A1 rerun, rebuilt against the E1-H kernel prefix. **Its hash is expected to differ from A1's [Inferred]** and must stay tied to this configuration and lock |
| Toolchain, host | `nightly-2026-08-21` (approved for S1 only); the frozen Homebrew tools; Apple M2 Pro; QEMU 11.1.3 |
| Build recipe | A new spike-local script derived from `build.sh`, differing only in the hypervisor option and in writing to a separate build directory so that the existing `build/` outputs are not removed. `build.sh` itself is not changed. The script will be recorded as a new deviation in `deviations.md` when it is written |
| Run | `qemu-system-aarch64 -machine virt,secure=off,gic-version=2,virtualization=on -accel tcg -cpu cortex-a57 -smp 1 -m size=1024M`, through the existing `boot-image.py --virt`, marker `TEST_PASS`, 120 s timeout, **three boots** of the same image |

**Success (Pass, label U, functional only).** All four of the baseline's criteria, applied to Route II:

1. **Inputs.** The kernel is built from the pinned source with the configuration in the table above, the root task is built from the
   same source and the approved lock, and no kernel, loader or root-task source was changed.
2. **Serial output** contains, in order: the seL4 boot banner (the strings `Bootstrapping kernel` and `Booting all finished,
   dropped to user space` [Documented: seL4 `boot.c`; Measured: A3 log 33]), `Hello, World!`, `badge = 0x1337`, `TEST_PASS`. The
   `badge` line prints the expected constant *before* the assertion, so only `TEST_PASS` shows that the assertion held.
3. **3 of 3 boots pass** with no positive failure observation (a kernel fault or halt message, a loader exception or panic, or a
   root-task panic) before the marker, **and identical output apart from timing and addresses**.
4. **Evidence:** sanitized logs, a manifest entry and verifier checks for the hashes and markers.

**Outcomes (the plan's rules).** *Pass* = 1 to 4. *Fail* = an observed kernel fault or halt message, a loader exception or panic, an
instruction or data abort reported by seL4, the loader or QEMU, or a root-task panic or assertion failure, with unmodified inputs.
*Investigate* = no Fail observation, but `TEST_PASS` is not seen in all three boots within the timeout, or any other Pass condition is
unmet. *Blocked* = three distinct, documented approaches fail to reach a first boot; the plan treats Blocked as Fail. An *approach* is a
documented way of reaching a first boot that stays inside the table above; anything that would change the table is a stop and report,
not an approach. Unless a Fail clause holds, or the Kernel modification policy makes the need a Fail (a Class 3 change), a stop
before three approaches have been tried, including stop (g) below, is recorded as *Investigate*: it is non-passing and is not
resolved without the owner's authorization. A Fail is never downgraded. E1 lists **no Conditional clause**. The consequence of a Fail,
Investigate or Blocked E1 is set here: report and stop.
It falsifies the broader hypothesis only under [decision rule 2](#the-hypothesis-is-falsified-if-any-of-these-occurs), that is, if
passing needs a Class 3 change or a Class 2 change the owner does not approve.

**Stop and report if** (the baseline's list, plus the one marked): (a) a kernel, loader or root-task source change is needed; (b) any
tool or dependency not already installed or pinned is needed; (d) three distinct documented approaches reach no first boot (Blocked);
(e) a positive failure observation: one diagnostic boot, then stop, where a diagnostic boot is one extra boot of the same image
through the unchanged `boot-image.py` with its serial output kept (a change to the harness or extra QEMU flags is not covered by D9
and is a stop and report); (f) anything about authority is unclear; **and, added, (g) the configuration differs from the table
above.** (The baseline's item (c) concerns Route I only.) Logs are sanitized before anything is published. Nothing is pushed or merged.

**Expected artifacts.** `spikes/sel4-feasibility/results/E1.md` with the outcome, label, the plan commit SHA `46a90fa` and the commit
that adds this specification, commits, toolchain versions, host, the kernel configuration stored as a file, the exact commands, and
the limitations and unresolved risks; sanitized logs of the build and the three boots; a hash table (kernel, loader, root task and
image); the spike-local build files; new verifier checks and a manifest entry (authorized by E1 and subject to D14(b)'s continuing
independent verification); deviation rows for the new spike code; an Amendment entry recording the result; a handoff update; and
an independent review request.

**A Pass does not mean:** hardware validation, performance, SMP, HVF, formal or verified-configuration assurance, a test of the
broader hypothesis, evidence about any configuration other than E1-H, or progress on A2a, A4 or A5. An emulator pass is not evidence
about hardware.

#### The baseline for "without weakening": the owner-chosen proposal, quoted verbatim

Section 2 of the draft `s1-proposals.md` ("Revised after the independent review"), from the session scratchpad of the earlier
session of 2026-11-08, which is outside Git and may be deleted. The parts below are the common section and Route II. Route I is
not quoted because the owner did not choose it. **If this entry and the quotation ever disagree, the stricter reading governs.**

> ### Route II (needs an Amendment): a hypervisor-enabled kernel with the Rust loader
>
> - rust-sel4's own default (`default = el2`, hypervisor on, `virtualization=on`). It needs no CMake glue: a variant of `build.sh`.
> - **New configuration.** The plan's matrix (K0 to K4, X1) has no hypervisor-enabled, unverified `qemu-arm-virt` configuration, so an Amendment must add one first. (K1 itself is listed as running under HVF; Route I runs its configuration under TCG, which needs no new configuration.) It is a build-option
>   change with no source change, but it is not K1.
> - **The root task must be rebuilt** against that configuration's `libsel4` (the object-type numbers depend on the hypervisor option [Inferred]), from the same source and lock.
>   So it does not boot "the existing binary", only the existing source.
> - **A point in its favour [Inferred].** The plan *expects* K1 to be a class B configuration difference from K0, partly "because the hypervisor option differs from K0" (plan, Inferred). K0's include file sets
>   `KernelArmHypervisorSupport ON` [Documented]. With HVF out and TCG as the backend, EL2 is available, so a hypervisor-enabled kernel would remove that one difference. Others remain (platform `tx2`,
>   `KernelVerificationBuild ON`, printing off, 16 domains), and the kernel would still be label U. That is a decision for the owner, not for this proposal.
> - Likely the faster route to a first boot. It is a different thing to test than K1.
>
> ### Common to both routes
>
> **Run.** QEMU 11.1.3, `-machine virt,secure=off,gic-version=2 -accel tcg -cpu cortex-a57 -smp 1 -m 1024M -nographic` (Route II adds `,virtualization=on`), through the existing
> `boot-image.py`, marker `TEST_PASS`, timeout 120 s. Three clean boots.
>
> **Success criteria (fixed before the run; label U; functional only).**
>
> 1. **Inputs:** the kernel is built from the pinned source with its recorded configuration (Route I: `gen_config.json` equal to A1's), the root task is built from the same source and the approved
>    lock (Route I: its stripped payload equals `aarch64-elf-strip` of `64fcc25c…`), and no kernel, loader, elfloader or root-task source was changed.
> 2. **Serial output** contains, in order: the seL4 boot banner, `Hello, World!`, `badge = 0x…`, `TEST_PASS`. The `badge` line prints the expected constant *before* the assertion, so only
>    `TEST_PASS` shows that the assertion held.
> 3. **3 of 3 boots pass** with no positive failure observation (a kernel fault or halt message, or a root-task panic) before the marker, and identical output apart from timing and addresses.
> 4. **Evidence:** sanitized logs, a manifest entry and verifier checks for the hashes and markers.
>
> **Outcomes (the plan's rules).** *Pass* = 1 to 4. *Fail* = an observed kernel fault, halt message or root-task panic with unmodified inputs. *Investigate* = no marker and no positive failure
> observation. *Blocked* = three distinct, documented approaches fail to reach a first boot; the plan treats Blocked as Fail. The consequence of Fail or Blocked is set here: report and stop; it
> falsifies the broader hypothesis only under the plan's decision rule 2, that is, if passing needs a Class 3 change or a Class 2 change the owner does not approve.
>
> **What a Pass does not mean:** not hardware validation, not performance, not SMP, not HVF, not verified-configuration assurance, not a test of the broader hypothesis, and no progress on A2a, A4 or A5.
>
> **Expected artifacts:** `results/E1.md`; sanitized logs of the build and the three boots; a hash table; the spike-local build files; new verifier checks; deviation rows for the new spike code; an Amendment entry recording the result; a handoff update.
>
> **Stop conditions (all countable).** Stop and report if: (a) a kernel, loader, elfloader or root-task source change is needed; (b) any tool or dependency not already installed or pinned is needed;
> (c) Route I: the rebuilt kernel's `gen_config.json` differs from A1's; (d) three distinct documented approaches reach no first boot (Blocked); (e) a positive failure observation: one diagnostic boot, then stop;
> (f) anything about authority is unclear. Logs are sanitized before anything is published. Nothing is pushed or merged.
>
> **Agent recommendation [Inferred; the owner decides].** Route II. Neither route boots the existing *binaries* (both rebuild the kernel; Route II also rebuilds the root task from the same source and lock), so that
> advantage of Route I is gone. Route II is rust-sel4's own default, needs no new build glue, and has the fewest unknowns on the way to a first boot, which is the owner's stated objective. Its cost is one Amendment adding
> the configuration. Choose Route I instead if the plan's configuration matrix must not grow.

### 2026-11-08: E1 ran (Route II): the agent's measurement, for independent review and the owner's decision

Recorded after E1 ran, as authorized by the entry above and after pull request 10 merged as `09f5dd5`. **This is the agent's
measurement. It is not an owner decision or acceptance, no criterion is changed and no earlier outcome is relabelled.** A
fresh-context `reviewer` returned "acceptable with corrections" and judged Pass justified (not Investigate); its corrections are applied
in the record and the verifier. The full record is [E1](../../spikes/sel4-feasibility/results/E1.md).

| Item | Result |
|---|---|
| Outcome (agent's reading) | **Pass, label U, functional validation only**, against the entry's four success criteria: inputs as pinned with no source change; the two banner strings, `Hello, World!`, `badge = 0x1337` and `TEST_PASS` in order in 3 of 3 boots; no failure observation in any boot; sanitized logs, a manifest entry and verifier checks (55 of 55 pass, 15 for E1, and `verify-evidence.py --self-test` catches 7 of 7 targeted corruptions) [Measured] |
| Qualification on "identical output" | The output is identical through `TEST_PASS`. The raw files differ by 2 bytes: boots 1 and 2 captured the `\r\n` after `TEST_PASS` and boot 3 did not, because the harness stops reading at the marker. The agent reads this as timing, which the criterion excludes [Inferred from `boot-image.py`]. The reviewer agreed and reproduced one more boot with the same output through the marker [Measured by the independent reviewer; not reproducible from the repository]; the owner has not ruled on the reading |
| Configuration | Exactly one of 156 kernel config keys differs from the A1 rerun's: `ARM_HYPERVISOR_SUPPORT` [Measured]. The A3 log 02 failure (a non-hypervisor kernel entered at EL2) did not recur: `kernel_entry` is `0xffc0000000`, not `0xffffffffc0000000` [Measured]. **The option also moves the kernel and halves the RAM:** seL4's CMake adds a device-tree overlay that reserves `0x40000000` to `0x60000000` for a VM, so usable RAM is one 512 MiB region at `0x60000000` and the kernel's physical base is `0x60000000` (A1: `0x40000000`) [Documented: seL4 `config.cmake`; Measured: boot 1, `readelf`]. It follows from the authorized option with no source change, so it is not stop condition (g) |
| Hashes | Kernel `1fee1dd6…`, loader `8408ab23…`, root task `58e723f3…`, image `4487ab9b…` [Measured]. All differ from the A1 rerun's, as the entry disclosed. They name their configuration and lock. The root-task ELF also embeds its target-directory path, so its hash differs from A1's regardless of the kernel [Measured: `strings`] |
| Not shown | HVF, SMP, performance, hardware, formal or verified-configuration assurance, reproducibility of the E1 image (one build), the system staying up after `TEST_PASS`, and anything about the broader hypothesis. The kernel warning `Could not infer GIC interrupt target ID, assuming 0.` appeared in all three boots and is not a failure under the specification |
| New spike code | [D17](../../spikes/sel4-feasibility/results/deviations.md) (`build-e1.sh`) and D18 (the verifier's E1 checks and `--self-test`), neither individually approved. Nothing else changed: no kernel, loader or root-task source, no tool, no dependency [Measured: `git status`, pinned checkouts clean, `Cargo.lock` hash unchanged] |
| Next | Independent review of E1. **No further experiment is started.** A2a, A4, A5, the comparator and Class 3 kernel modifications stay blocked. Does E1's Pass change ADR 0002 or ADR 0004? That is the owner's decision, and neither status changes here |

### 2026-11-08: Owner decisions on E1, D17, D18, the E1 pull request and PR 9

Source: the owner's message of 2026-11-08 in the working session. **No criterion is changed, no earlier outcome is relabelled and no ADR is
accepted.**

| Item | Owner decision | Effect |
|---|---|---|
| E1 | **Conditionally accepted as Pass (label U)**, limited to functional execution under QEMU TCG, subject to a final independent review of the corrections. The missing trailing line terminator is acceptable as a read-boundary artifact if all required markers were captured and the reviewer confirms the evidence. **Do not claim byte-identical serial logs** | The record already says the logs are not byte-identical. The acceptance is final only if that review finds no material issue |
| D17, D18 | **Approved for S1 only.** Preserve the verifier self-tests and document the 512 MiB usable-memory limitation | Recorded in `deviations.md`. The limitation is in [E1](../../spikes/sel4-feasibility/results/E1.md) and the handoff |
| E1 pull request | Commit and push the E1 changes on `spike/e1-route-ii`. Run one focused independent review of the final corrections, resolve material findings, verify the final blobs, run the complete checks and open a PR. **Merge only after an explicit MERGE-READY verdict and all required CI checks pass.** After the merge, report the final commit and stop | Conditional merge authorization. If any condition fails, stop and report |
| PR 9 | **Do not merge it and do not dismiss its alerts.** Preserve the existing dependency pin while a compatible remediation is evaluated. **No additional `protobuf` experiments are authorized** | No change to `requirements.txt` or to the alerts |
| Next milestone | The owner's priority is two isolated Rust userspace tasks communicating through seL4 IPC, with a negative capability-isolation test. **Not to be implemented yet.** The agent is to identify the minimum existing S1 gates and propose the smallest executable scope, concisely, with no new documentation or approval cycle unless a real architectural or security boundary requires one | A proposal in the session only. Nothing is authorized to start |
| Stop condition | A2a, A4, A5, the comparator and Class 3 kernel modifications stay blocked. No experiment other than E1 is authorized | In force |

### 2026-11-09: E2 authorized and run (two isolated tasks over seL4 IPC), the agent's measurement, for independent review and the owner's decision

Source: the owner's messages of 2026-11-09 in the working session ("go ahead" in reply to the agent's proposal, then "Option 1, approve object"
in reply to the agent's correction that the proposal's recipe needs a new dependency). **No earlier criterion or outcome is changed and no ADR is
accepted.** E2 is a precursor, **not** Stage B, P1 or P2 evidence: A2a has not run.

| Item | Entry |
|---|---|
| Authorization | The proposal as stated to the owner (two isolated Rust tasks communicating through seL4 IPC, with negative capability-isolation checks; the smallest executable scope), the gated files `Cargo.toml` and `Cargo.lock`, and the new dependency `object` 0.40.0 (`read` feature only), for S1 only. Commit, push and PR were **not** authorized by these messages |
| Configuration | E1-H (hypervisor-enabled seL4 17.0.0, `qemu-arm-virt`, Cortex-A57, 1 node, non-MCS), label U; the same 156 kernel keys as E1 [Measured] |
| What ran | A root task builds a client and a server, each with its own address space, CNode, TCB and IPC buffer, one shared endpoint, and the root task as fault supervisor. The client makes a legitimate call, then invokes an empty slot, invokes a wrong-type capability, tries to forge a badge by minting, makes a second legitimate call, and reads a server-only address |
| Result | **Pass, label U, functional only: 3 of 3 boots** printed the full sequence and `E2_PASS`; each refusal returned the expected error code, no message reached the server from the refused attempts, and the root task received exactly one fault, the client's VM fault at the server's secret address [Measured]. Verifier 71 of 71 (16 for E2), `--self-test` 14 of 14. Two mutants (the client given the secret's mapping; the "empty" slot made live) each failed as they should. Record: [E2](../../spikes/sel4-feasibility/results/E2.md) |
| Departures from the proposal | Rights amplification through mint is **not tested** (mint masks rights, it does not reject, and seeing it needs a second fault round-trip); the tasks are two separate binaries, not one shared ELF; a positive control (the server reads its own secret) was added after a first, superseded run; the code is two crates, not one |
| New spike code | D19 (the two crates, `build-e2.sh`, `Cargo.toml`, `Cargo.lock`, `object`) and D20 (the verifier's E2 checks and its lock-aware checks), both in `deviations.md`; **D20 is not yet approved** |
| Not shown | HVF, SMP, performance, hardware, revocation, use after revoke, anything about untyped or IRQ authority, a second fault, side channels, reproducibility beyond one directory, formal assurance, or the broader hypothesis. The kernel is a debug build in which every task can print |
| Stop condition | Unchanged: A2a, A4, A5, the comparator and Class 3 kernel modifications stay blocked, and no experiment other than E1 and E2 is authorized. E2 stops here pending review |

### 2026-11-09 (later): E2 provisionally accepted as Pass (U); D19 and D20 approved for E2's scope; independent review authorized

Source: the owner's message of 2026-11-09 in the working session. The text below records what the owner decided; the agent's measurement is in the entry above and is not repeated as a decision.

| Item | Owner decision |
|---|---|
| E2 outcome | Provisionally accepted as **Pass (U)**, limited to the specific functional and security probes performed under QEMU TCG, subject to independent review |
| D19, D20 | Approved **for E2's experimental scope only**. They do not authorize broader dependency changes or future experiments. This covers D19's "two crates, not one" difference and D20's lock-aware verifier checks |
| Review | A focused independent review of E2 (implementation, evidence, build configuration, capability distribution, isolation tests, mutation tests, `Cargo.lock` changes, verifier changes). Material findings are addressed and the affected tests rerun; purely editorial findings do not start a new loop |
| After a MERGE-READY verdict on the final implementation | Run the complete checks, create signed DCO-compliant commits, push `spike/e2-ipc-isolation` and open a PR. Merging is **conditionally authorized** only if every required CI check passes on the final head, the evidence verifier passes and no material finding remains. Then report the final `main` commit and stop |
| Not authorized | Revocation, A2a, A4, A5 and the custom-kernel comparator. The next milestone gets a short technical recommendation only, not a planning PR |

### 2026-11-09 (after the independent review): corrections to the E2 entries above

Source: the agent, after the independent `reviewer` run the owner authorized. These are corrections to the agent's own wording and to a verifier defect. They change no criterion and no owner decision; the earlier entries stay as written.

| Item | Correction |
|---|---|
| "Four attempts to exceed its authority" | Two attempts to exceed authority (badge forgery, a read of the server's memory) and two invalid invocations (an empty slot; label 0 on the client's own CNode capability, which the kernel treats as an invalid CNode method). The empty-slot and CNode probes are not authority tests |
| "The root task received the client's VM fault" [Measured] | The root task's check establishes that a VM-fault-shaped message at the secret address arrived through the client's badged fault capability. The client holds a send capability to that endpoint (non-MCS requires it), so a forged message would pass; the reviewer built such a client and it produced `E2_PASS`. That a real fault occurred rests on the client source [Inferred]. The tasks' fault capability has write and grant-reply rights, not write-only |
| "Exactly one fault" | The root task waits for one fault message by design |
| D20, "strictness is kept" | Not true as first written: the verifier normalised line endings of `Cargo.lock`. Fixed (bytes are hashed); 5 new self-tests cover the lock; self-test is now 19 of 19 |
| E2.md on log identity | The `\r\n` difference described belonged to the superseded first run. In the evidence run, boots 2 and 3 are byte-identical and boot 1 differs only in the elapsed time |
| Source change after the evidence build | Doc comments only, in `crates/e2-root-task/src/main.rs` and `crates/e2-task/src/bin/client.rs`, with unchanged line counts; the binaries were not rebuilt. Known and left as is: the server prints "secret mapped and readable" even after a readback mismatch (its `E2_FAIL` line fails the verifier); there is no mutant for the mint test; the verifier does not check the kernel's reason lines |
| Dependency policy check | `cargo deny --frozen check advisories bans sources` passed offline against a local advisory database for the new `object` dependency [Measured by the reviewer] |

### 2026-11-09 (after the review): E2 finally accepted as Pass (U); E3 authorized

Source: the owner's message of 2026-11-09 in the working session. The text below records what the owner decided; the agent's measurement is in the next entry and is not repeated as a decision.

| Item | Owner decision |
|---|---|
| E2 outcome | **Finally accepted** as Pass (U), limited to its demonstrated functional and capability-isolation probes. It does not establish verified kernel-generated fault delivery |
| E3 | **Authorized**: the capability-revocation experiment, with the corrected recommendation in the session handoff as the baseline scope. Objective: demonstrate that `seL4_CNode_Revoke` removes previously usable derived capability authority while preserving the parent capability and unrelated capabilities |
| Required evidence | (1) a derived endpoint capability in the server's CNode that works before the revoke; (2) the same slot populated and usable before; (3) revoke from the correct ancestor held by the root task; (4) the derived capability unusable afterwards; (5) the original and an unrelated control capability still functional; (6) the relevant derived capability in the client's CNode also removed, where the derivation topology supports that; (7) a no-op-revoke mutation that fails the test; (8) the exact seL4 error behaviour verified experimentally, without requiring distinct codes for revoked and never-populated slots unless the API guarantees them |
| Implementation authority | A development branch from `origin/main`, preserving the uncommitted handoff; Rust userspace code; routine changes to scripts, verifier checks, tests and experiment documentation; the existing pinned toolchain and dependencies; QEMU TCG runs. Record deviations without weakening earlier checks |
| Not authorized | New dependencies, kernel or bootloader modifications, unapproved tools, changes to ADR statuses. A substantive security or architectural issue outside the approved scope: stop and report the smallest decision required |
| Quality and delivery | Positive controls, negative controls and mutation tests; three clean boots of the final image, the evidence verifier and `cargo xtask check`. Report results, deviations, limitations and decisions needed. **No push, PR or merge without further authorization** |

### 2026-11-09 (E3 run): the agent's measurement, for the owner's decision

Source: the agent. **No earlier criterion or outcome is changed and no ADR is accepted.** E3 is a precursor, **not** Stage B, P1 or P2 evidence: A2a has not run.

| Item | Entry |
|---|---|
| Configuration | E1-H (hypervisor-enabled seL4 17.0.0, `qemu-arm-virt`, Cortex-A57, 1 node, non-MCS), label U; the same 156 kernel keys as E1 [Measured] |
| What ran | A root task builds two identical tasks, each with its own address space and CNode and no capability to its own CNode. Each holds a badged mint of the root task's endpoint capability `P`, a copy of that mint, and a mint of an unrelated endpoint `Q`. Both are shown usable and populated; the root task calls `seL4_CNode_Revoke` on `P`; both are shown empty and refused while `P`, `Q`'s mints and a new mint of `P` work |
| Result | **Pass, label U, functional only: 3 of 3 boots** printed the full sequence and `E3_PASS`. Three mutants (a no-op instead of the revoke; a revoke of `Q`; a no-op with two probes left out) each fail as they should. Verifier 89 of 89 (18 for E3), `--self-test` 35 of 35. Record: [E3](../../spikes/sel4-feasibility/results/E3.md) |
| Error behaviour (required item 8) | After the revoke a call through a revoked slot returns label 2 (`InvalidCapability`), **the same as a call through a never-populated slot**; a root-side `Copy` from either fails with `FailedLookup`. The record does not rely on the codes being equal or distinct [Measured] |
| Departures from the recommendation | The two tasks are symmetric, each with a mint and a copy of it (the recommendation had a mint for the server and a copy for the client); the control `Q` is shared by both; the new mint of `P` after the revoke is tested for both tasks. Task events reach the root task through a notification bound to its TCB |
| New spike code | D21 (E3 binaries in the existing `e2-task` and `e2-root-task` crates, `build-e3.sh`; `Cargo.toml` and `Cargo.lock` unchanged) and D22 (`verify_e3.py`, `sanitize-run.py`), both in `deviations.md`, both under the owner's "routine" authority and not individually reviewed |
| Not shown | HVF, SMP, performance, hardware, revoking a badged child, revoking an untyped, a deeper chain, a thread blocked on the endpoint, other object types, a preempted revoke, a revoke by a task, side channels, formal assurance. The kernel is a debug build |
| Not done | **No independent review** (none was authorized). Nothing was committed, pushed or opened as a PR |
| Stop condition | Unchanged: A2a, A4, A5, the comparator and Class 3 kernel modifications stay blocked, and no experiment other than E1, E2 and E3 is authorized. E3 stops here pending the owner |

### 2026-11-09 (after the E3 report): E3 provisionally accepted as Pass (U); D21 and D22 approved for E3; independent review, PR and merge authorized with conditions

Source: the owner's message of 2026-11-09 in the working session. The text below records what the owner decided.

| Item | Owner decision |
|---|---|
| E3 outcome | Provisionally accepted as **Pass (U)**, limited to the tested capability-revocation behaviour under QEMU TCG, **pending independent review** |
| D21, D22 | Approved **for E3 only**. "Keep the existing crate organization. Separate crates are not required for this feasibility experiment" |
| Review | An independent review of E3, with emphasis on: (1) seL4 derivation and revocation semantics, including the two badged mints and their copies; (2) whether the pre-revoke and post-revoke controls show selective authority removal; (3) whether the mutants test the stated security properties and whether the recorded binaries and evidence are consistent; (4) the copied `unsafe extern` block and `static mut` (soundness, initialization, concurrency, safer alternatives); (5) whether the verifier can pass altered evidence, including regressions affecting A1, E1 and E2; (6) whether the claims, limitations, deviation records and acceptance labels reflect the evidence. Address all material findings; rebuild and rerun the affected evidence when implementation changes require it; no repeated review cycles for editorial issues |
| After a MERGE-READY verdict on the final implementation | Run the full evidence verifier, its self-tests and `cargo xtask check`; create signed, DCO-compliant commits; push `spike/e3-revocation` and open a PR that includes the updated `SESSION_HANDOFF.md`; **merge only when the required CI checks pass on the final reviewed head and no material finding remains**. Then report the resulting `main` commit, the remaining limitations and the outstanding S1 gates, and stop |
| Not authorized | Changing ADR statuses, changing dependencies, beginning another experiment. Stale local branches may be deleted only after verifying that they hold no unique commits or uncommitted work; unrelated untracked directories are not to be touched |

### 2026-11-09 (E3 review): the baseline recommendation as authorized, and corrections to the E3 entry above

Source: the agent, after the first independent `reviewer` run the owner authorized (verdict NOT MERGE-READY; its findings and their treatment are in [E3](../../spikes/sel4-feasibility/results/E3.md), "The independent review"). These are corrections to the agent's own wording and to its own evidence. They change no criterion and no owner decision; the E3 entry above stays as written.

**The baseline the owner authorized** ("using the corrected recommendation in SESSION_HANDOFF.md as the baseline scope", owner message of 2026-11-09). The review found this text had been overwritten in the working-tree handoff; it is quoted here as the handoff had it at the start of the session (it is the agent's recommendation, not an owner decision):

> 2. If E3 is authorized, the agent's recommendation [Inferred: nothing below has been run; exact error codes must be checked on the first run]. It reuses the E2 crates, with no kernel change and no new dependency.
>    - Setup: the root task keeps an unbadged endpoint capability `P` and mints a badged child `C` into the server's slot `s`. A control child `D` of a separate endpoint `Q` sits in slot `t`. Optionally a copy `C2` of `C` also goes in the client's CNode.
>    - Before: the server sends on `C` and the root receives it (positive control). The root `Copy`s the server's slot `s` into its own CNode, which succeeds (the root holds the server's CNode capability); it then deletes that copy.
>    - Revoke: the root revokes `P`. This deletes derived capabilities and keeps `P`.
>    - After: (a) the same root-side `Copy` from slot `s` now fails, so a slot that was live and copyable is empty; (b) the server's send on `s` returns an error and the root receives nothing; (c) `P` still works (the root mints a new child and a round trip succeeds); (d) `D` still works; (e) `C2`, if used, is gone too, which deleting the server's slot alone would not do.
>    - Distinguishing revocation from an invalid lookup: the post-revoke error for a revoked slot is probably the **same** error as E2's empty slot (label 2), so the error code alone proves nothing. The evidence is the before/after pair on the same slot, the surviving parent and control capabilities, and a mutant that replaces the revoke with a no-op, after which the post-revoke send must succeed and the test must fail. The server must hold no CNode capability, so it cannot have emptied the slot itself. The same debug-kernel caveat as E2 applies, and a fault message must not be used as evidence.
>    - Size: a few dozen lines in the E2 crates, plus verifier markers and a self-test. It still needs a deviation row for the new code and an independent review before a PR.

| Item | Correction |
|---|---|
| "Departures from the recommendation" | The tasks use `Call`, not `Send`, so that a refusal is visible as a reply label (a refused `Send` is silent); both tasks get a mint of `P` and a copy of that mint in their own CNode, rather than a mint for the server and a copy in the client's CNode, so the two CNodes' capabilities are siblings, not a chain; a mint of `P` after the revoke is tested for both tasks (the recommendation's (c)); the control `Q` is shared. Point (e), that the client's copy is gone and a removal in the server's CNode alone would not do it, is shown by the mutant that deletes only task 1's slots (M5) |
| "Three mutants", "89 of 89", "35 of 35" | Six mutants (a no-op, a revoke of `Q`, a no-op without two probes, a revoke of `P` and `Q`, a removal from task 1 only, a root task that answers the refused call); the verifier has 91 checks (20 for E3) and the self-test 46 corruptions. The detectors behind the control probe, the second task and the task's own refusal check are shown to fail |
| "No independent review" | A first review was done (NOT MERGE-READY); its findings were addressed and the evidence rerun; a second review of the final state returned MERGE-READY with no material finding. The owner's final acceptance is pending |
| "D21 and D22 ... not individually reviewed" | Approved by the owner for E3 only; reviewed by the `reviewer`. D23 (new) repairs `build-e2.sh`, which the E3 binaries had broken (E2's root-task build compiled `e3_root_task` too and failed): E2's evidence is unaffected, but the E2 build script's recorded hash is no longer the file's |
| E2 acceptance | The owner finally accepted E2 as Pass (U) (entry above). The E2 record is not otherwise changed; its build script now names the binaries it builds (D23) |

### 2026-11-09 (after the E3 merge): E3 finally accepted as Pass (U); D23 approved; the next S1 gates

Source: the owner's message of 2026-11-09 in the working session, after PR 13 was merged as `44d1d70`. The first two rows record what the owner decided; the third records the agent's analysis, which decides nothing.

| Item | Entry |
|---|---|
| E3 outcome | **Finally accepted as Pass (U)**, limited to the tested capability-revocation topology under single-vCPU QEMU TCG with the debug kernel. The owner asked that the disclosed limitations be preserved: the verifier changes made **after** the second review (the null-cap lines' thread attribution and the order of a mutant's stop and failure lines, with two self-test cases, and wording corrections), the forged-log gaps that remain in `verify_e3.py`, and the inaccurate `static mut` `SAFETY` comment in `e3_spawn.rs`. These do not invalidate the accepted functional result, but they **must not be represented as independently reviewed or production-ready** |
| D23 | **Approved**: the `build-e2.sh` repair that explicitly selects the E2 binaries. "No separate crates are required for this spike" |
| Direction | Prepare for the remaining S1 architectural decision gates: identify the prerequisites, acceptance criteria and blockers for A2a, A4 and A5; recommend the next executable gate, preferably A2a; identify any authorization or dependency change; check the cancelled macOS CI run; update the handoff and these records. Concise; no further planning-only PR; **no experiment, dependency change or ADR status change without authorization**. Priority: complete S1 and reach a defensible kernel decision |
| Agent's analysis (decides nothing) | In the [A2a record](../../spikes/sel4-feasibility/results/A2a.md), the [A5 design proposal](a5-design-proposal.md) and the handoff. In short: **A2a is the next executable gate** (no boot, no installation, no dependency change; its expected outcome is Investigate, since the required Stage B tests have not run); A2a, A4 and A5 are all still **not authorized** by the stop of 2026-11-08; A4's x86-64 half needs Tier 2 installation (not approved); A5 is held for a reviewed design and is the likeliest falsifier. One finding needs the owner before Stage B: the Rust loader boots only hypervisor-enabled kernels, so E1 to E3 ran on E1-H, which is not a matrix row, while K1 and K2 (where Stage B must run) are non-hypervisor kernels; and the matrix's "Runs here: under HVF" for K1 and K2 contradicts A3's Fail. The scheduled macOS CI run that showed `failure` was cancelled by GitHub with no step executed (a runner-capacity cancellation, not a code failure) |
| Stop condition | Unchanged: A2a, A4, A5, Stage B, the comparator and Class 3 kernel modifications stay blocked until the owner authorizes one |

### 2026-11-09 (A2a authorized): the owner's authorization

Source: the owner's message of 2026-11-09 in the working session, after the handoff's gate analysis. **No criterion is changed or redefined.**

| Item | Owner decision |
|---|---|
| A2a | **Authorized under the existing S1 plan and its original acceptance criteria.** Approved scope: (1) build K0 using the pinned verified AArch64 configuration and GCC 16.2.0 in a gitignored experiment directory, preserving the exact compiler version, configuration, command, output and relevant hashes; (2) investigate K1 and K2 using their existing defined configurations; (3) compare K0, K1 and K2 with a reproducible comparison script; (4) include the E1 to E3 hypervisor-enabled configuration as an **informational additional row, clearly separated from the approved matrix**; (5) read the public seL4 verified-configuration documentation and record precisely what its claims do and do not cover; (6) preserve the distinction between build success, configuration similarity and formal-verification applicability. "Do not interpret a successful build or matching configuration keys as proof of formal verification" |
| Tooling | Routine comparison and evidence tooling, the approved builds and tests, existing pinned dependencies and tools only |
| Not authorized | Changing kernel or loader source, dependency pins, ADR statuses or the approved Stage B matrix; Stage B, A4, A5 implementation, the custom-kernel comparator |
| Records | The uncommitted E3 final-acceptance records stay on the branch and accompany the next appropriate A2a implementation PR, not a documentation-only one |
| macOS CI | Run **one** manual macOS workflow to see whether the cancelled job can acquire a runner; do not modify the workflow unless a concrete defect is established and separately authorized; report the result independently of A2a |
| After A2a | Prepare a concise A5 design proposal (SMMU requirements, the pinned seL4 implementation's limitations, the smallest meaningful falsification test). **Do not execute A5 without authorization** |
| Delivery | Complete local execution and evidence verification first; report the outcome and any deviations **before pushing or opening a PR**. Stop on a substantive architectural or security issue outside the scope |

### 2026-11-09 (A2a run): the agent's measurement, for the owner's decision

Source: the agent. **No criterion is changed, no ADR is accepted.** Record: [A2a](../../spikes/sel4-feasibility/results/A2a.md). Label U for the builds; no formal-verification claim.

| Item | Entry |
|---|---|
| Outcome | **Investigate**, by the plan's definition: the P5 cell of K3 cannot be classified (the SMMU server does not exist) and no required Stage B test has run on a matrix configuration. The K1 and K2 cells for P1 to P4 are **expected** to be class B, as pre-registered, but are **not yet classified**: the dependency lists were not completed (see Departures) and the trusted-component entry is open. No cell is class A, C or D |
| Builds | K0 (`AARCH64_verified.cmake`, platform `tx2`), K1, K2 and the informational E1H all build with `aarch64-elf-gcc` 16.2.0, and again in a second directory. That is build success only |
| Comparison | Against K0: E1H 554 functions identical and 322 different, K1 396 and 338, K2 339 and 389. The function tables are identical across two clean builds, complete against `nm`, agree with an independent clang extraction (the reviewer), and the verifier recomputes the comparison from the published tables. Named path functions: `cteRevoke`, `cteDelete`, `isMDBParentOf`, `isCapRevocable`, `deriveCap`, `invokeUntyped_Retype` and `resetUntypedCap` are identical to K0 in all three; `cteInsert`, `cteDeleteOne`, `finaliseCap`, `createObject` and `decodeUntypedInvocation` are not |
| Findings for the owner | (1) **Every AArch64 verified configuration is a hypervisor-mode (EL2) configuration**, K0 among them. The plan's K1 and K2 (no hypervisor support) therefore differ from it in that option, and the E1H configuration that E1 to E3 ran on and that the Rust loader requires does not. This **corrects** the handoff's earlier statement that E1H was "probably further from K0". (2) K0 is a release build and K1, K2 and E1H are **debug** builds; much of the function-level difference is probably the debug option (not measured in this record), and some debug and hypervisor differences change behaviour (`sanitiseRegister`, `mdb_node_get_mdbNext`). The matrix does not say which build type K1 and K2 are. (3) **The documentation does tie the pinned release to a proof revision**: the FAQ points to the verification manifest, whose `17.0.0.xml` pins the pinned seL4 commit with l4v `12c300e7…` (the first version of this record said the documentation names no version; the independent review found the error). Which AArch64 proof sessions exist for it is not established. (4) The matrix's "Runs here: under HVF" for K1 and K2 contradicts A3. **No loader is known to start K2** (A3: the elfloader aborts on its PSCI conduit; the Rust loader is EL2-only) |
| Departures | **From the plan (not from the owner's approved scope): A2a did not complete the lists of code each property depends on**, which the plan says A2a completes "per configuration, from the proof documentation and the preprocessed source"; it used the plan's starting list, mapped file by file. Of the functions that differ from K0, 259 (K1), 299 (K2) and 254 (E1H) are in no listed file, some on the property paths. Class B needs every differing function on the path named, so the K1 and K2 cells are not yet classified. A2b is to complete the lists, now that the proof revision can be identified. The documentation was read by a fetch agent and then re-fetched by the reviewer and by me |
| New spike code | D24 in `deviations.md` (authorized as routine tooling; not independently reviewed) |
| Not done | Release variants of K1, K2 and E1H; any Stage B, A4 or A5 work; any push or PR |
| macOS CI (independent of A2a) | The scheduled run of 2026-11-09 13:52 UTC was cancelled by GitHub with no step executed ("The job was not acquired by Runner of type hosted even after multiple attempts", with a macOS arm64 capacity notice). The one manual run authorized (42674266306, 18:28 UTC) failed after 51 s with no job started and one annotation, "Internal server error" with a correlation ID: a GitHub-side error. **No defect in `macos.yml` is established** (it equals the copy GitHub holds, uses the same pinned GitHub-owned actions as `ci.yml`, and passes `actionlint`), so the workflow was not modified. The macOS path has still never run to completion |
| Stop condition | Unchanged: Stage B, A4, A5 and the comparator stay blocked until the owner authorizes one |

### 2026-11-09 (after the A2a report): the owner's decisions on A2a, the PR, Stage B preparation and A5 step 0

Source: the owner's message of 2026-11-09 in the working session. **No criterion is changed or relaxed, no ADR status is changed, no verification applicability is claimed.**

| Item | Owner decision |
|---|---|
| A2a outcome | The reported **Investigate** is accepted as the experiment's recorded result, **subject to normal independent review**. It does not establish formal-verification applicability or approve a kernel architecture |
| PR | Authorized to commit, push and open the `spike/a2a-assurance` PR (A2a implementation, tooling and evidence; the final E3 acceptance and D23 records; the A5 design proposal; relevant S1 documentation and handoff updates), following the repository's standards for commits, signatures, DCO, branch protection and CI. An independent technical review of D24 and of A2a's evidence and methodology is requested (material correctness, reproducibility, classification validity, unsupported security claims). Material findings are resolved before merging; the owner authorized merging when the review is satisfactory and the required checks pass, without a further approval if the changes stay within this authorization. The unresolved macOS CI infrastructure failures are recorded accurately and CI requirements are not modified or bypassed to obtain a green result. Unrelated local files and branches are preserved |
| Configuration and Stage B preparation | The existing K1 and K2 non-hypervisor configurations **remain legitimate experimental baselines** and are not to be replaced solely to accommodate the current Rust loader. Investigate booting them with seL4's elfloader. Investigate reproducible **release variants** of K1, K2 and E1-H to quantify the effect of debug instrumentation. Keep build reproducibility, configuration similarity, functional execution and verification applicability separate. **Amend the Stage B matrix** to define configurations, build types, loader paths, execution environments and evidence requirements, preserving the original intent and identifying any necessary change. Do not execute Stage B |
| A5 step 0 | Authorized: an initial environment and feasibility probe, using the E1-H baseline where appropriate (QEMU SMMUv3 and EDU support and start-up, whether the root task can identify and access the MMIO resources, the PCIe, device-tree, DMA-addressing, translation and memory-mapping constraints, what is needed to observe DMA traversing the SMMU, and which limits would prevent a meaningful A5). Primary sources and reproducible evidence; no inference of DMA isolation from device creation, MMIO access or configuration alone. **Not** the full DMA revocation experiment, no kernel change, no persistent dependency, no ADR change. If the design proves infeasible, report defensible alternatives. A5 experimental work stays separate from the A2a PR |
| Expectations | Independent and critical engineering; previous recommendations are hypotheses; novel approaches welcome where defensible; no unnecessary documentation-only work. The completion report must separate observed facts, inferences and hypotheses and must not claim a gate passed unless its criteria are met |

### 2026-11-10: configuration and loader results, A5 step 0, and the Stage B matrix defined in full (the agent's measurement and proposal, for the owner's decision)

Source: the agent, under the owner's message of 2026-11-09 ("Amend the Stage B matrix to define configurations, build types, loader paths, execution environments and evidence requirements, preserving its original intent and identifying any necessary changes"). **No criterion, outcome, gap class, property (P1 to P5) or decision rule is changed. No ADR status is changed. Nothing is claimed about formal-verification applicability.** Stage B has not been executed. The matrix below is the agent's proposal; it governs Stage B only if the owner starts Stage B with it, and the rows marked "outside the matrix" stay outside it unless the owner adds them by a further Amendment.

**Results the matrix rests on** (records: [A2a-variants](../../spikes/sel4-feasibility/results/A2a-variants.md), [RouteI](../../spikes/sel4-feasibility/results/RouteI.md), [A5-step0](../../spikes/sel4-feasibility/results/A5-step0.md); none is an experiment outcome):

| Item | Entry |
|---|---|
| Release variants [Measured: text of preprocessed kernels, nothing booted] | K1R, K2R, E1HR (debug and printing off, five keys) and K0Q (K0's own file on `qemu-arm-virt`) build twice with identical function tables. Functions differing from K0: E1-H 322 (debug) to 17 (release); K1 338 to 105; K2 389 to 210; K0Q 6. **The debug option explains nearly all of E1-H's difference from K0, about two thirds of K1's and about half of K2's;** what remains for K1R and K2R is dominated by the hypervisor option (100 functions differ, 142 exist only in the hypervisor build) and, for K2R, SMP. In K0Q every function on the capability, CNode, mint, revoke, untyped, endpoint and syscall paths of the A2a mapping is textually identical to K0's. **That is text, not execution and not a proof claim.** |
| Loader for K1 and K2 [Measured] | seL4's elfloader boots **K1** (3 of 3) and **K2 with 4 vCPUs** (3 of 3) under QEMU 11.1.3 TCG. K2 needs a device tree that says PSCI `smc`, `virtualization=on`, and a root task built against K2's own kernel prefix; each is a failing negative control. This **corrects** the earlier statements "no loader is known to start K2" (the A5 proposal, the handoff). That A3's K2 abort was a device-tree and machine-option mismatch and not an unbootable kernel is [Inferred]: A3's own image (a Cortex-A53 sel4test kernel) was not booted again; the code path supports it (seL4's CMake dumps QEMU's tree with `virtualization=on` only for hypervisor kernels). A3's recorded result (Fail (U) under HVF) is unchanged |
| A5 step 0 [Measured] | On the E1-H baseline, QEMU 11.1.3 starts with `iommu=smmuv3` and `edu`; the root task reaches the SMMU registers, the ECAM and edu through device untypeds with no kernel change; with edu's DMA mask widened, QEMU's trace shows edu's DMA reaching the SMMU model and the SMMU's global state deciding whether data moves. **The SMMU was never enabled: no translation and no confinement was observed.** Constraints and the next step are in the record |

**The Stage B matrix.** The plan's intent is that Stage B runs on the most verified-like configuration that works, records its label, and states MCS or non-MCS (here: **non-MCS** throughout, because AArch64 MCS proofs are incomplete). **Whether this matrix meets that intent is an open question for the owner, not something the matrix settles:** by the release-variant numbers above, the hypervisor-mode E1HR (17 functions differ from K0) and K0Q (6) are textually much nearer K0 than any row of the matrix (K1R 105, K2R 210), and E1-H already boots. The matrix keeps K1 and K2 because the owner directed that they remain the baselines; text is not proof applicability either way. IDs K1 to K4 keep their plan definitions; the new columns say how each runs.

| ID | Configuration | Build type | Loader | Machine (QEMU 11.1.3 TCG) | vCPUs | Logging | Status |
|---|---|---|---|---|---|---|---|
| K1 | AArch64 `qemu-arm-virt`, no hypervisor support | debug (the A1 and A2a recipe) | seL4 elfloader, default tree | `virt,secure=off,gic-version=2` | 1 | kernel `DebugPutChar` | **In the matrix, as defined** |
| K1R | K1, `KernelDebugBuild=OFF`, `KernelPrinting=OFF` | release | seL4 elfloader, default tree | as K1 | 1 | **user-level UART only** (a release kernel has no `DebugPutChar` [Inferred: not run]) | **Proposed build-type variant of K1** |
| K2 | K1 with SMP | debug | seL4 elfloader, **tree built with PSCI `smc`** | `virt,secure=off,gic-version=2,virtualization=on` | 4 | kernel `DebugPutChar` | **In the matrix, as defined** |
| K2R | K2, release | release | as K2 | as K2 | 4 | user-level UART only | **Proposed build-type variant of K2** |
| K3 | K2 plus a user-level SMMUv3 server | as K2 | as K2 | as K2 plus `iommu=smmuv3` and `edu` | 4 | as K2 | In the matrix, as defined; A5 step 0 ran on E1-H only, **K3 has not been run** |
| K4 | K2 plus an in-kernel SMMUv3 driver | n/a | n/a | n/a | n/a | n/a | Unavailable unless the Kernel modification policy allows it |
| K0 | `AARCH64_verified.cmake`, platform `tx2`, hypervisor mode, release | release | none | none | none | none | **Built, never booted** (`tx2` hardware is not part of this project); comparison base for A2 only |
| E1H, E1HR | K1's options with hypervisor support on | debug, release | Rust `sel4-kernel-loader` | `virt,secure=off,gic-version=2,virtualization=on` | 1 | E1H: `DebugPutChar`; E1HR: none yet | **Outside the matrix**, as E1 to E3. Informational baseline for experiments the Rust loader can start |
| K0Q | K0's file on `qemu-arm-virt` | release | not tried | not tried | n/a | none | **Outside the matrix.** Textually nearest to K0 (6 functions differ); a hypothesis for a baseline, not a classification. Whether it boots is not known |

**Necessary changes this makes visible (each decides nothing until the owner confirms):**
1. **Execution environment.** The plan's table marks K1 and K2 "Yes, under HVF". A3 recorded that HVF fails, so K1 and K2 run under **TCG**, which is slower and is not hardware evidence for timing, memory ordering or cross-core behaviour. This was already the practice for E1 to E3. Stage C numbers keep their own measurement-only configuration (Decision 1b of 2026-11-08).
2. **Loader path.** The Rust loader cannot start K1 or K2; **seL4's elfloader can** (above). K1 and K2 are therefore **not replaced** to suit the Rust loader, as the owner directed. The hypervisor rows keep the Rust loader.
3. **A build-type dimension.** The plan did not say whether Stage B runs a debug or a release kernel; A2a's K1 and K2 are debug, K0 is release. The proposal: run each Stage B functional test on **both** the debug build (for evidence, with kernel logging) and the release build (nearer K0), and record the A2b classification against the release variants as well as the debug ones. If the owner prefers one, K1/K2 as defined (debug) are the default and the release rows are dropped. A debug-only result must say so; it cannot be quoted for the release kernel without the release run.
4. **Logging on release.** A release kernel provides no `DebugPutChar`; evidence from K1R and K2R needs a user-level UART driver in the root task (the PL011 at `0x09000000` is inside a device untyped; A5 step 0 shows the mapping technique works for other devices, but printing through the UART has **not** been tried). This is new test code, not a kernel change.
5. **K2 runs on a machine that exposes EL2** (`virtualization=on`) although its kernel does not use it. This is a property of the harness, to be stated in every K2 record.
6. **The comparison tables.** A2b should complete the dependency lists (the departure A2a recorded) for K1, K1R, K2, K2R; the K0Q table is available if the owner wants a nearer base, but K0 stays the base.

**Evidence required for every Stage B run, on every row:** the configuration ID, build type and label (U, M or S); the `gen_config` hash; the SHA-256 of the kernel, loader (or elfloader image), root task and device tree; the QEMU version and exact command line; the root task's build prefix (it must be the one of the kernel run; a K1-built root task on K2 fails, above); two clean builds with identical function tables for the kernel; at least three identical boots per positive result; a negative control or mutant for every claim that a refusal or a removal happened; verifier checks that read the logs rather than look for a marker; and the A2 function-level comparison against K0 for the same build type. **A pass on K1, K2, K1R or K2R is not a claim about K0 or about any verified configuration;** the matrix says only what text and behaviour were found to be the same or different.

**Not done and not decided:** Stage B itself; whether K0Q or a hypervisor-mode row joins the matrix; whether to boot K1R and K2R (user-level logging first); ADR 0004. Smallest next implementation step: boot K1R and K2R under the elfloader with a user-level UART (no kernel change, existing tools), so that the release rows of the matrix are known to run before they are relied on.

### 2026-11-10 (later): the owner's authorizations for the engineering session

Source: the owner's message of 2026-11-10 that opened the session ("FYRKAT OS, High-Impact Engineering Session"). **No criterion, outcome definition, property or decision rule is changed. No ADR status is changed. No verification claim is changed.**

| Item | Owner decision |
|---|---|
| Stage B matrix | "Accept the proposed Stage B matrix amendment as the working experimental plan, without changing existing verification claims or ADR statuses." The matrix of the entry above is therefore the **working experimental plan**. It remains an Amendment, not an ADR, and the open question recorded in it (whether a hypervisor-mode row is nearer the plan's intent) stays open |
| D25 to D27 | "Complete and independently review the existing D25–D27 work." "Commit, push and open appropriately scoped PRs for completed work after resolving material findings." "Merge approved-scope PRs when independent review and required CI checks pass" |
| Release kernels | "Implement, boot and test release-kernel configurations K1R and K2R", with user-level UART logging "or a technically superior alternative that works without kernel debug-printing facilities"; exercise kernel functionality, repeated clean runs, negative controls |
| A5 step 1 | "Implement and execute A5 step 1, including actual SMMUv3 translation and isolation experiments": one configured stream, a 4 KiB region, a mapped and an unmapped address, evidence of both, and a mutant that omits a required invalidation |
| A5 step 2 (conditional) | "If A5 step 1 succeeds, you may proceed to a minimal exploratory revoke-while-mapped falsification experiment, provided its experimental design receives independent review and it remains entirely inside a disposable emulated environment." "Do not automatically select a root-task ownership model or any other solution." "Do not represent experimental behavior as a universal security property" |
| Also authorized | "Necessary experimental userspace, loader, harness and tooling development"; "technically justified alternative approaches when the original approach proves inadequate" |
| Not authorized | "Do not change the seL4 kernel, ABI, dependencies or ADR statuses without further authorization. Do not execute the broader Stage B gate." "Do not bypass repository security or CI requirements" |

**A conflict the independent review pointed out, for the owner to settle.** AGENTS.md says that agents "never push, force push or merge" and that "the owner merges"; its approval-gate table allows a remote action with the owner's approval first. The message recorded above authorizes pushing, opening pull requests and merging for this session, as the owner's messages of 2026-11-09 did for the E3 and A2a pull requests (entries above), which the agent then merged. This entry records that authorization as given for **this session's scope only**. It does not change AGENTS.md, and no agent should read it as standing permission: each later push or merge needs the owner's own word, and AGENTS.md either stays as it is (then the owner merges) or is amended by the owner.

### 2026-11-10 and 2026-11-11 (session results): review of D25 to D27, release-kernel execution, A5 steps 1 and 2 (the agent's measurement, for the owner)

Source: the agent, under the authorizations above. **Not experiment outcomes: no gate of the plan is claimed passed or failed.** Records: [ReleaseKernel](../../spikes/sel4-feasibility/results/ReleaseKernel.md), [A5-step1](../../spikes/sel4-feasibility/results/A5-step1.md), [A5-step2](../../spikes/sel4-feasibility/results/A5-step2.md), and the corrected [A2a-variants](../../spikes/sel4-feasibility/results/A2a-variants.md), [RouteI](../../spikes/sel4-feasibility/results/RouteI.md), [A5-step0](../../spikes/sel4-feasibility/results/A5-step0.md).

| Item | Entry |
|---|---|
| Independent review of D25 to D27 [Measured by the reviewer; fixes by the agent] | Verdict on first review: not merge-ready. One blocker (the agent's own later edit of the shared MMIO helper invalidated the recorded source hash of A5 step 0), four major findings (safe accessors that did not check what their safety comments assumed; device registers mapped with cacheable attributes and no barrier around DMA; the A5 step 0 verifier accepted altered evidence; the variants verifier did not tie the published tables to their recorded hashes) and wording and provenance findings. The numbers and observations of all three records were reproduced as sound. All blocker and major findings are fixed, the A5 step 0 evidence is re-recorded with the changed helper (same observations), and the corrections are listed in the records |
| Release kernels [Measured] | **K1R boots and passes 7 functional tests in 3 of 3 runs; K2R (4 vCPUs) passes 8 in 3 of 3**, through seL4's elfloader under QEMU TCG, logging only through a user-level PL011 driver. The kernels in the images have the same configuration and function-table hashes as the published K1R and K2R. The kernel's own answer to the debug system call (an unknown-syscall fault) shows it has no printing; the debug kernels, two deliberately broken tests and two mismatched pairings are the controls. Functional execution under emulation only; not Stage B |
| A5 step 1 [Measured] | With the SMMU **enabled** and one stream given a stage-1 address space, QEMU's SMMUv3 model translates that stream's DMA to the mapped page (whose physical address is not the address the device used), refuses unmapped and physical addresses, enforces a read-only mapping, refuses a second, unconfigured device at the address that works for the first, and stops honouring a removed mapping or stream once the invalidation command has completed (and not before: without the command the transfer still lands). Identical in 3 of 3 boots on the E1-H kernel and on K2R; five mutants each fail exactly one test; QEMU's own trace agrees. A second independent review (2026-11-11 local time) found the release-kernel work and step 1 merge-ready with text fixes (the evidence was re-recorded afterwards, after the changes that review asked for in the shared helper) and confirmed that the behaviour is stage-1 translation and permission checking, not global blocking. **One emulated model; the root task holds every capability; not an A5 outcome and not K3** |
| A5 step 2, exploratory [Measured; one task in every role; not an A5 outcome] | Run on 2026-11-11 after an independent review of its design ("OK to run after these changes": the verifier was made to require validity and consistency instead of the expected outcomes, and was fixed by hash before the first boot, an ownership scenario was dropped, "forgery" became "duplication" with a kernel-made copy as control). On the E1-H kernel and on K2R, 3 of 3 boots each: **with a stream's stage-1 mapping of a frame left in place, the frame's untyped is revoked and the kernel hands the same physical page out again; the device then reads all of the new owner's data and overwrites all of it, with no fault** (a copy of the frame capability held by the "server" is revoked with the original and pins nothing). With the mapping cleared, invalidated and synced before the revoke, both transfers are refused; with the entry cleared but not invalidated they are not (an invalidation without clearing was not tried). With the memory reused as a CNode, the device reads a raw capability out, and a capability it copied into an empty slot is accepted by the kernel when copied out of that slot, and that copy still works after the revocation that removes the kernel's own copies. A third review confirmed the pre-run hashes and the outcomes and corrected one overstated sentence of the write-up. **This is a finding about a naive arrangement on an unmodified kernel under one emulated SMMU model. It is not the proposal's falsifier (no separate donor or server, not K3), A5-arm is neither passed nor failed, and no design is selected**; the record sets out four options with their trusted base, correctness argument and cost ([A5-step2](../../spikes/sel4-feasibility/results/A5-step2.md)) |
| Changes to the matrix this makes visible | Change 4 of the entry above ("release kernels need a user-level UART, untried") is done. K3's status "has not been run" stands: what ran on K2R is an experiment's root task, not an SMMU server separate from its clients, and the debug K2 was not used |

