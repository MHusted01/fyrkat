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

- **Pass:** the requirement is met.
- **Conditional:** it works with a stated cost. The owner decides whether to accept it.
- **Fail:** the requirement is not met.

A failure caused by a bug in spike code does not count. The bug is fixed and the
experiment is rerun. An experiment that stays blocked after three distinct approaches is
recorded as **Blocked**, and is treated as a Fail for decision purposes.

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

### A2. Assurance surface

Measure how much of the verified kernel survives in the configurations Fyrkat needs. This
test is deterministic and needs no boot.

Compare the preprocessed `kernel_all.c` from a V build (`AARCH64_verified`) with a U build
adding SMP, and with a U build for `qemu-arm-virt`. The output is a written assessment, not
a percentage. It must cover, for each configuration Fyrkat needs:

1. **Proof applicability:** which kernel functions and properties the published proofs
   cover at the pinned commit, and which they do not, for capability, untyped, endpoint,
   notification and scheduler code.
2. **Configuration differences:** every configuration option that differs from V, and which
   code paths it adds, removes or changes. A per-function textual diff is evidence for this,
   not a score.
3. **Trusted computing base changes:** code Fyrkat would add to or rely on inside the
   kernel, such as an IOMMU driver, and code outside it that must be trusted, such as a
   user-level SMMU server.
4. **Unverified components:** every component on the path of a required isolation property
   that has no proof coverage, and what other evidence exists for it.

- **Pass:** the assessment is complete, and no required isolation property rests solely on
  code that is unverified and that Fyrkat would have to modify.
- **Conditional:** one or more required properties depend on unverified code or on a
  configuration the proofs do not cover. Each gap is listed with its compensating evidence,
  and the owner decides whether to accept it.
- **Fail:** an unacceptable assurance regression, as defined under
  [Blockers and regressions](#blockers-and-regressions), or the assessment cannot establish
  which code a required property depends on.
- **Limit:** identical text does not mean proofs hold, because concurrency can invalidate
  sequential reasoning. A textual diff shows what reviewed code is shared, and nothing more.

### A3. EL1 and HVF compatibility

Run an AArch64 `qemu-arm-virt` build without hypervisor support, under HVF, with 1 and
4 vCPUs. Use the sel4test suite where it can run. Label: U.

- **Pass:** it boots and passes on both vCPU counts with no kernel patch.
- **Conditional:** only 1 vCPU works, or a platform or timer patch of 50 lines or fewer is
  needed (label M).
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
SMMUv3. Both options below must be assessed.

1. **User-level:** a trusted server owns the SMMU registers and tables, with no kernel
   change. The critical question is whether the kernel can reuse memory that a device can
   still reach, and how teardown ordering prevents it.
2. **In-kernel:** a driver modelled on the SMMUv2 support, in unverified C.

Then run a negative test with `-machine virt,iommu=smmuv3`: a device must reach only its
mapped region, and DMA outside it must fault and be reported. Labels: S or M.

- **Pass:** the user-level design passes the negative test with no kernel patch, and
  teardown provably blocks device access before memory is reused.
- **Conditional:** an in-kernel driver passes, and its change is acceptable under
  [Kernel modification policy](#kernel-modification-policy).
- **Fail:** neither option works without a kernel change that policy makes unacceptable.
- **Also record:** the status of x86-64 VT-d, which lacks interrupt remapping. It does not
  count as a pass for AArch64.

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
- **Fail:** any fault that reaches the kernel or an unrelated component.
- **Limit:** without A5, a driver can still damage memory through DMA. Results must say
  whether DMA isolation was active.

## Stage C: performance

Stage C runs only if Stages A and B produced no Fail. Timing uses the virtual counter and
is U at best. Results are valid for this virtualized host only.

### C1. IPC

Same-core call and reply, cross-core IPC, and a chain through three servers with a 4 KiB
payload in shared memory.

**1 µs is a provisional target. It is not an automatic rejection threshold.** Before any
run, the experiment record must define:

- **Hardware:** the host (Apple M2 Pro under HVF), the core type each vCPU lands on, and
  the fact that the guest is virtualized. Results are valid for that setup only.
- **Workload:** the exact call, reply and payload sizes (0 bytes in message registers, and
  4 KiB in shared memory), same-core and cross-core.
- **Method:** the virtual counter, warm-up iterations, iteration count, number of runs,
  and the statistic reported. Report median, 99th percentile and spread across runs.
- **Baseline:** published seL4 round-trip figures with their hardware stated, and a
  same-VM Linux comparison such as a Unix-socket round trip. About 850 cycles is about
  0.25 µs at 3.4 GHz, and is a published figure, not a Fyrkat measurement.

- **Pass:** same-core round trip of 1 µs or less.
- **Investigate:** above 1 µs. Record the cause, separating virtualization overhead,
  hardware differences and seL4 behaviour. The result goes to the owner as an input, and is
  not a Fail on its own.

### C2. Page faults against Linux

Compare page fault cost on the same VM configuration, using a pinned Linux guest. This is
the primary same-hardware comparison. Use reproducible, representative workloads rather
than a single microbenchmark: first-touch anonymous faults, file-backed faults,
copy-on-write faults, and a mixed workload that touches a working set of stated size.
Record the method, sample sizes and spread as for C1.

**3 times and 5 times Linux are investigation thresholds until justified.** They are not
pass or fail lines. Adopting either as a criterion needs a written justification and an
amendment.

- **Within 3 times Linux:** no action needed.
- **3 to 5 times:** investigate and record the cause and any identified fix.
- **Over 5 times:** profile, and record whether the cost is inherent to the design, to the
  user-level pager, or to the virtualized setup. The owner decides what it means.
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

1. A1 fails.
2. Any experiment requires an unacceptable kernel modification, as defined under
   [Kernel modification policy](#kernel-modification-policy).
3. B1 or B2 fails through a kernel leak or use after revocation.
4. B3 or B4 shows an isolation failure in the kernel or in unrelated components.
5. DMA isolation cannot be enforced on either architecture without an unacceptable kernel
   modification.
6. A2 finds an unacceptable assurance regression.

C1 and C2 results never falsify the hypothesis automatically. They are reported to the
owner, and Stage D weighs them.

See [Blockers and regressions](#blockers-and-regressions) for the definitions.

### Results that reopen other decisions without falsifying it

| Result | Reopens |
|---|---|
| A3 fails | ADR 0002 |
| A4 fails | ADR 0003 |
| A5 passes only on x86-64 | ADR 0002 |
| User space requires nightly Rust | Toolchain policy |
| Each board needs its own kernel build | ADR 0003 and hardware strategy |
| A2 is Conditional | The assurance argument in ADR 0004, with each gap listed |
| C1 or C2 passes the investigation threshold | The performance assumptions in ADR 0004 |

If all of Stages A to C pass or are accepted as Conditional, Stage D decides. A pass does
not automatically accept seL4. The owner decides.

## Blockers and regressions

Defined before any experiment, so that the outcome can be checked against them.

**Functional blockers.** Each is a Fail, and falsifies the hypothesis where
[Decision rules](#decision-rules) say so:

- No reproducible build workflow on this Mac (A1).
- A kernel leak, or any use after revocation (B1, B2).
- Any isolation breach by the kernel, a pager or a driver (B3, B4).
- DMA isolation that cannot be enforced (A5).
- A required experiment that stays blocked after three distinct approaches.

**Unacceptable assurance regressions.** Each is a Fail in A2:

- A required feature needs a change to capability, untyped, endpoint, notification,
  scheduler or fast-path code.
- A change alters the V build's output.
- A change weakens an existing check or disables a security feature.
- A required isolation property depends solely on unverified code that Fyrkat would have to
  modify, with no compensating evidence.
- New code inside the kernel that handles capabilities or memory ownership, and that the
  owner has not accepted as part of the trusted computing base.

## Kernel modification policy

**Unacceptable, at any size:**

- Any change to capability, untyped, endpoint, notification, scheduler or fast-path code.
- Any change that alters the V build. Every patch must be behind a configuration flag, and
  the V build's output must stay byte-identical with the patch applied.
- Any change that weakens an existing check or disables a security feature.

**Acceptable, with label M:** platform and timer fixes, or a new IOMMU driver.

**Investigation trigger:** 1,550 lines in total, which matches the existing SMMUv2 support
(645, 431, 437 and 37 lines across four files). This is not a hard limit. Passing it starts
a written evaluation, and a small patch can still be unacceptable. Judge every patch by:

- **Security impact:** what it can reach, and what it can break.
- **Complexity:** how hard it is to review and to reason about.
- **Proof implications:** which proofs it touches or invalidates.
- **Maintenance burden:** the cost of carrying it across seL4 releases.

## Reconsideration criteria after the spike

If the hypothesis survives, any of these reopens ADR 0004:

1. A required kernel patch is rejected upstream, or stays out of tree for two releases.
2. Keeping up with seL4 costs over 500 changed lines in `fyrkat-rt` in two consecutive
   releases.
3. A representative workload stays above the C2 investigation threshold of 5 times Linux
   after profiling-driven work.
4. On physical hardware, kernel lock contention exceeds 20% of wall time at target core
   counts.
5. A Verus or similar proof of seL4-style derivation and revocation is demonstrated at a
   cost this project could plausibly bear.
6. More than two critical advisories per year hit the unverified paths Fyrkat depends on,
   for two consecutive years.
7. seL4 goes 18 months without a release, or its licence or governance changes materially.

## Recording results

Each experiment gets `spikes/sel4-feasibility/results/<id>.md`, containing:

- The outcome and label.
- The commits, toolchain versions and host.
- The kernel configuration, stored as a file.
- The exact commands, and raw output or measurements.
- Sample sizes and spread for any measurement.
- Limitations and unresolved risks.
- Any kernel patch, stored as a `.patch` file.

## Isolation from production

- All spike code lives in `spikes/sel4-feasibility/`, as its own Cargo workspace.
- No crate outside `spikes/` may depend on it. `cargo xtask check` enforces this.
- seL4 is fetched at the pinned commit into a gitignored directory, so no GPL-licensed
  kernel code enters this repository.
- Nothing is promoted to production. Any later implementation is rewritten under a
  reviewed plan, and spike code is deleted once its results are recorded.

## Model and budget policy

- **Sonnet:** A1, A3, A4, B1 to B4, and C1 to C3.
- **Opus:** A2 interpretation, A5 design, security review, and Stage D.
- One agent at a time, with no parallel research agents.
- Work stops at the end of each stage, with a report on results and tokens used.

## Scope limits

These require owner approval first:

- Building the comparator prototype.
- Any kernel patch beyond a Conditional allowance, or one that passes the investigation
  trigger.
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
