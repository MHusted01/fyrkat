# C1 method: IPC latency

- **Status:** Draft for owner review. No run of C1 has happened, pilot or otherwise. Ready to
  freeze once the owner confirms the items under [Open before the first run](#open-before-the-first-run).
- **Plan:** [seL4 feasibility spike plan](../../../docs/research/sel4-spike-plan.md), experiment C1,
  approved at `46a90fa`.
- **Effect:** the plan requires this file to be committed before any C1 run. Edits before the first
  run are ordinary edits. Changing the method after the first run is an Amendment to the plan. Every
  C1 results file cites the commit SHA of this file as it exists on `main`.
- **Pilot rule:** a pilot may check that the harness works. Its numbers are not recorded as
  results and may not change this method.

This file fixes the method. It does not change any criterion.

## Criterion

From the plan, unchanged:

- **Pass:** same-core round trip of 1 µs or less.
- **Investigate:** above 1 µs. Record the cause, separating virtualization overhead, hardware
  differences and seL4 behaviour. This is a non-passing outcome, and not a Fail.

**Interpretations to confirm (owner).** The plan leaves these open. This draft chooses as follows,
and the owner confirms or changes each before the first run:

1. **Which workload carries the criterion:** W1 (empty message, same core), the smallest round trip.
   This is the reading most favourable to a Pass. The plan also lists 4 KiB same-core work, which is
   W2. W2 to W6 are reported in full and carry no threshold. Requiring W1 and W2 both is the
   stricter alternative.
2. **Which statistic:** the median of the 30 run medians of W1.
3. **Which kernel:** the 4-vCPU SMP kernel (K2), with W1 pinned to one core. K1 (1 vCPU) is not used
   for the criterion.

## Kernel build for C1 and C2

The timed kernel is fixed here, because the harness depends on these options.

| Option | Value | Reason |
|---|---|---|
| Base | K2: `qemu-arm-virt`, SMP 4 vCPUs, no hypervisor support | Plan configuration |
| `KernelIsMCS` | **OFF** | `seL4_TCB_SetAffinity` exists only when the kernel is non-MCS and SMP [Documented: `libsel4/include/interfaces/sel4.xml`, seL4 `62e345c`]. If Stage B ran MCS, C1 and C2 still use non-MCS and the results file says so |
| `KernelDebugBuild` | **OFF** (release) | A debug kernel adds checks and printing on the path being timed |
| `KernelArmExportVCNTUser` | **ON** | User access to `CNTVCT_EL0` and `CNTFRQ_EL0` is off by default [Documented: `src/drivers/timer/config.cmake`]. The option's own text warns that it opens a timing channel. That is a kernel configuration difference from K2 |
| Fast path, printing | Defaults for a release build, recorded | |

The results file records the full configuration file and lists every difference from the kernel that
Stage B and A2 used. Whether the A2 matrix needs a row for the timing-channel option is an owner
decision. This file does not decide it, and Stage C needs A2-final to be Pass or Conditional as the
plan says.

**Placement check.** The kernel call that reports a thread's core, `seL4_DebugGetThreadAffinity`,
exists only in debug SMP builds [Documented: `libsel4/include/api/syscall.xml`]. So placement is
verified in a separate, untimed boot of a debug build of the same kernel, with the same harness
binary. The timed release kernel does not report cores. Its placement relies on the checked return
code of `seL4_TCB_SetAffinity`. No debug-build number is ever reported as a result.

## Hardware and setup

- **Host:** Apple M2 Pro, 16 GB, macOS 27.2. 10 cores: 6 performance and 4 efficiency [Measured:
  `sysctl hw.perflevel0.physicalcpu hw.perflevel1.physicalcpu`, 2026-11-07].
- **Guest:** QEMU 11.1.3, `-accel hvf`, `-cpu host`, machine `virt` with the GIC version A3 selects
  (recorded in the A3 results), 4 vCPUs, 2 GiB RAM. The Linux comparison uses the same accelerator,
  CPU model, machine, GIC version, vCPU count and RAM. Devices that differ (the Linux disk and
  firmware) are listed in the results. The QEMU version and full command line are recorded per run.
  The guest is virtualized, so results are valid for this setup only.
- **Core types:** macOS does not let this project pin vCPUs to core types, so none is fixed in
  advance. At the start of every run the harness times a fixed spin loop on each vCPU and records
  the four times. A vCPU more than 1.3 times slower than the fastest is labelled "slower class
  (inferred efficiency core)". The label records what was observed. It never excludes a run.
- **Host state, per series:** AC power, `pmset -g therm` output before and after, and a process
  list snapshot taken before the series. A series with a thermal warning is kept and flagged.
- **Counter:** the guest's `CNTFRQ_EL0` is read and recorded in every run. At 24 MHz one tick is
  about 41.7 ns [Inferred, to be replaced by the observed value].
- **Timing source:** the virtual counter (`CNTVCT_EL0`), read with an `isb` before and after each
  batch. Timing is U at best. It says nothing about hardware.

## Workloads

All use `seL4_Call` from the client and `seL4_ReplyRecv` from the server. The message register count
is the only payload unless stated. The shared region is one 4 KiB page mapped in every address space
that uses it, set up before timing.

| ID | Placement | Payload | What happens per iteration |
|---|---|---|---|
| W1 | Same core | 0 message registers | Client calls, server replies at once |
| W2 | Same core | 4 KiB in shared memory | Client fills the page, calls, server reads every byte (sum), replies with the sum |
| W2n | Same core | 4 KiB mapped, not touched | As W2 but neither side touches the page. This separates IPC cost from the fill-and-sum cost |
| W3 | Cross core | 0 message registers | Client on core 0, server on core 1 |
| W4 | Cross core | 4 KiB in shared memory | As W2, client on core 0, server on core 1 |
| W5 | Same core | 4 KiB in shared memory | Chain: client calls S1, S1 calls S2, S2 calls S3, each reads the page and replies. All four on core 0 |
| W6 | Cross core | 4 KiB in shared memory | As W5 with client on core 0 and S1, S2, S3 on cores 1, 2 and 3 |

A round trip is one call plus one reply. For W5 and W6 an iteration is the whole chain, which has
**3 call-reply pairs** (client to S1, S1 to S2, S2 to S3). The results file also reports the
per-pair figure (iteration time divided by 3). Threads are placed with `seL4_TCB_SetAffinity`
before timing starts.

**If K2 is unavailable** because A3 found only 1 vCPU works, W3, W4 and W6 are recorded as not run,
with the A3 cause. W1, W2, W2n and W5 run on K1. No outcome rule is added by this sentence.

## Measurement

- **Warm-up:** 100,000 iterations per workload, discarded.
- **Batch:** 10,000 iterations between two counter reads. The batch result is
  `(ticks_end - ticks_start) / 10,000`, converted with the recorded `CNTFRQ_EL0`.
- **Batches per run:** 1,000 for the same-core workloads (W1, W2, W2n, W5). **200** for the
  cross-core workloads (W3, W4, W6), which cost more per iteration under HVF [Speculative], so that
  a series finishes in a bounded time.
- **Time limit:** a run that exceeds 30 minutes of wall time is stopped, recorded as timed out, and
  its data is kept and reported.
- **Resolution rule:** one counter tick must be under 1% of the batch duration, so a batch must last
  at least 100 ticks (about 4.2 µs at 24 MHz). The harness flags any batch under 1,000 ticks as a
  sign of a broken clock and stops the run. A stopped run is reported in the results file with its
  data and its cause. Statistics are given with it and without it, and the number of stopped runs is
  stated. Replacement runs are labelled as replacements.
- **Runs:** 30 per workload. Every run is a fresh VM boot, so VM-to-VM variation and vCPU
  placement are inside the spread. Workloads run in the fixed order W1, W2, W2n, W3, W4, W5, W6
  inside each run.
- **No dropping.** Every workload is reported, and every batch is kept. No batch or run is removed
  as an outlier.
- **Per-run statistics:** median, 99th percentile (nearest rank), minimum and maximum of the batch
  results. The 99th percentile is taken over **batch means** of 10,000 iterations. It shows tail
  behaviour between batches. It is not the tail latency of single calls, which this method does not
  measure.
- **Reported across runs, per workload:** the median of the 30 run medians (the headline figure),
  the minimum and maximum run median, the interquartile range of the run medians (Q3 minus Q1, linear
  interpolation), and the median of the 30 run 99th percentiles. Ratios are rounded to two significant
  figures. Raw batch results are stored.
- **Pass test:** the W1 headline figure is 1 µs or less.

## Baseline

Baselines are context. They never set a threshold.

1. **Same-VM Linux:** the pinned Linux guest from the [C2 method](C2-method.md). A Unix-domain
   socket ping-pong (`socketpair`, `SOCK_STREAM`) between two processes, with 1-byte and 4 KiB
   messages. Both processes are pinned to one CPU, then to two. It uses the same warm-up, batch, run
   and statistics rules.
2. **Published seL4 figures, fixed here.** Source: the seL4 Foundation performance page,
   `https://sel4.systems/performance.html`, which reports `sel4bench` results as mean (standard
   deviation) in cycles. Read on 2026-11-07 [Documented]. The page says it was generated on
   2026-11-07 for `sel4bench-manifest` commit `818079b1`. That is the provenance to cite, and it is
   not a seL4 release number.
   Its AArch64 row is the only one with the same architecture as the guest:

   | Board and core | Clock | Kernel build | IPC call | IPC reply | Sum |
   |---|---|---|---|---|---|
   | Jetson TX1, Cortex-A57 | 1.9 GHz | Non-MCS, `FASTPATH=TRUE`, GCC 14.2.0, `tx1` | 419 (0) | 431 (0) | 850 cycles, about 0.45 µs |
   | Jetson TX1, Cortex-A57 | 1.9 GHz | MCS, same flags | 434 (0) | 451 (0) | 885 cycles, about 0.47 µs |

   "IPC call" and "IPC reply" are measured separately on the same core, so their sum approximates a
   round trip and is not itself a published round-trip figure [Inferred]. This is a different core,
   a different clock, native hardware and a different kernel configuration. Results are compared as
   times, using the clock the page states, and never converted to cycles on the Apple core, whose
   clock this project does not control. The published figures are context only. No published
   figure is copied into a Fyrkat result.

## Cause analysis if W1 is above 1 µs

The results file separates the causes below, with evidence for each, and does not guess:

- **Kernel entry:** the cost of a bare `seL4_Yield` loop, timed the same way, as the floor for a
  system call on this setup. It stays inside the guest under HVF, so by itself it does not isolate
  virtualization cost [Inferred].
- **Virtualization:** the number of VM exits per batch, counted with QEMU trace events if HVF
  provides them, and otherwise stated as not counted. Cross-core results add inter-processor
  interrupts and wake-ups, which probably exit [Inferred].
- **Hardware:** the recorded core types and the counter resolution.
- **seL4 behaviour:** the kernel configuration above, whether the fast path is taken, and the IPC
  path length where measurable.

## Records

Each C1 results file contains, in addition to the plan's list: this file's commit SHA, the kernel
configuration and its differences from Stage B, the debug-boot placement check, `CNTFRQ_EL0` per run,
the four spin-loop times per run, the host power, thermal and process output, the QEMU version and
command, and the raw batch data.

## Open before the first run

- **A plan wording error.** The plan says "About 850 cycles is about 0.25 µs at 3.4 GHz" as a
  published figure. The 850 cycles equals the Cortex-A57 sum above, at 1.9 GHz, about 0.45 µs [Inferred: the plan does
  not name its source]. The 3.4 GHz
  clock belongs to the x86-64 rows. The plan's sentence is context and not a criterion, so this file
  does not rely on it. The owner may want it corrected by an Amendment.
- The three interpretations under [Criterion](#criterion).
- The A2 question under [Kernel build](#kernel-build-for-c1-and-c2).

## Known limits

- HVF adds an unknown cost to every guest exit. The `seL4_Yield` loop bounds the kernel-entry
  cost and does not remove the exit cost. [Inferred]
- Thirty runs show boot-to-boot spread on one machine. They do not show spread across machines.
- A 24 MHz counter is coarse, but the batch rule keeps its error under 1%. It does not remove
  jitter from the host scheduler.
- Cross-core results depend on which host cores the vCPUs land on, which this project cannot set.
- Placement in the timed release kernel is not observed directly. It rests on the checked return
  code of `seL4_TCB_SetAffinity` and on the debug-boot check of the same harness binary.
