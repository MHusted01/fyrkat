# C1 method: IPC latency

- **Status:** Draft for owner review. No run of C1 has happened, pilot or otherwise.
- **Plan:** [seL4 feasibility spike plan](../../../docs/research/sel4-spike-plan.md), experiment C1,
  approved at `46a90fa`.
- **Effect:** the plan requires this file to be committed before any C1 run. Once committed on
  `main`, changing it after the first run is an Amendment to the plan. Every C1 results file cites
  the commit SHA of this file as it exists on `main`.
- **Pilot rule:** a pilot may check that the harness works. Its numbers are not recorded as
  results and may not change this method.

This file fixes the method. It does not change any criterion. The plan's C1 criteria are
repeated in [Criterion](#criterion) only so the reader sees them next to the method.

## Criterion

From the plan, unchanged:

- **Pass:** same-core round trip of 1 µs or less.
- **Investigate:** above 1 µs. Record the cause, separating virtualization overhead, hardware
  differences and seL4 behaviour. This is not a Fail.

**Interpretation to confirm (owner).** The plan says "same-core round trip" without naming the
payload. This method applies the criterion to workload **W1** (empty message, same core), the
smallest round trip. W2 to W6 are reported in full and carry no threshold of their own. If the owner
wants the criterion to cover another workload, that is decided before the first run.

## Hardware and setup

- **Host:** Apple M2 Pro, 16 GB, macOS 27.2. 10 cores: 6 performance and 4 efficiency
  [Measured: `sysctl hw.perflevel0.physicalcpu hw.perflevel1.physicalcpu`, 2026-11-07].
- **Guest:** QEMU 11.1.3, `-accel hvf`, machine `virt`, 4 vCPUs, 2 GiB RAM, for every workload
  and for the Linux comparison. The guest is virtualized, so results are valid for this setup only.
- **Kernel:** the Stage B configuration (K2, SMP with 4 vCPUs). The results file states whether it
  is MCS or non-MCS, the kernel commit, the configuration file and the label (U, or M with a patch).
- **Core types:** macOS does not let this project pin vCPUs to core types, so none is fixed in
  advance. At the start of every run the harness times a fixed spin loop on each vCPU and records
  the four times. A vCPU more than 1.3 times slower than the fastest is labelled "slower class
  (inferred efficiency core)". The label is a record of what was observed. It never excludes a run.
- **Host state, recorded per series:** AC power, `pmset -g therm` output before and after, and
  that no other heavy process ran. A series with a thermal warning is kept and flagged. Runs are
  not discarded.
- **Counter:** the guest's `CNTFRQ_EL0` is read and recorded in every run. At 24 MHz one tick is
  about 41.7 ns [Inferred, to be replaced by the observed value].
- **Timing source:** the virtual counter (`CNTVCT_EL0`), read with an `isb` before and after each
  batch. Timing is U at best. It says nothing about hardware.

## Workloads

All use `seL4_Call` from the client and `seL4_ReplyRecv` from the server. The message register count
is the only payload unless stated. The shared region is one 4 KiB page mapped in both address
spaces, set up before timing.

| ID | Placement | Payload | What happens per iteration |
|---|---|---|---|
| W1 | Same core | 0 message registers | Client calls, server replies at once |
| W2 | Same core | 4 KiB in shared memory | Client fills the page, calls, server reads every byte (sum), replies with the sum |
| W2n | Same core | 4 KiB mapped, not touched | As W2 but neither side touches the page. This separates IPC cost from copy cost |
| W3 | Cross core | 0 message registers | Client on core 0, server on core 1 |
| W4 | Cross core | 4 KiB in shared memory | As W2, client on core 0, server on core 1 |
| W5 | Same core | 4 KiB in shared memory | Chain: client calls S1, S1 calls S2, S2 calls S3, each reads the page and replies. All four on core 0 |
| W6 | Cross core | 4 KiB in shared memory | As W5 with client on core 0 and S1, S2, S3 on cores 1, 2 and 3 |

A round trip is one call plus one reply. For W5 and W6 an iteration is the whole chain, and the
results file also reports the per-hop figure (iteration time divided by 4 call-reply pairs).
Threads are placed with `seL4_TCB_SetAffinity` before timing starts. The harness checks the
placement by reading the core number reported by the kernel from each thread.

## Measurement

- **Warm-up:** 100,000 iterations per workload, discarded.
- **Batch:** 10,000 iterations between two counter reads. The batch result is
  `(ticks_end - ticks_start) / 10,000`, converted with the recorded `CNTFRQ_EL0`.
- **Batches per run:** 1,000.
- **Resolution rule:** one counter tick must be under 1% of the batch duration, so a batch must
  last at least 100 ticks (about 4.2 µs at 24 MHz). With 10,000 iterations this holds for any
  per-iteration time above 0.42 ns. The harness checks the rule and aborts the run if a batch
  falls under 1,000 ticks, which would show a broken clock.
- **Runs:** 30 per workload. Every run is a fresh VM boot, so VM-to-VM variation and vCPU
  placement are inside the spread. Workloads run in the fixed order W1, W2, W2n, W3, W4, W5, W6
  inside each run.
- **No outlier removal.** Every batch is kept and enters the statistics.
- **Per-run statistics:** median, 99th percentile, minimum and maximum of the 1,000 batch results.
- **Reported across runs, per workload:** median of the 30 run medians (the headline figure), the
  minimum and maximum run median, the interquartile range of the run medians, and the median of
  the 30 run 99th percentiles. Raw batch results are stored.
- **Pass test:** the W1 headline figure (median of run medians) is 1 µs or less.

## Baseline

Baselines are context. They never set a threshold.

1. **Same-VM Linux:** the pinned Linux guest from the [C2 method](C2-method.md), the same QEMU
   command and the same 4 vCPUs. A Unix-domain socket ping-pong (`socketpair`, `SOCK_STREAM`) between
   two processes: 1-byte and 4 KiB messages, both processes pinned to one CPU and then to two,
   measured with the same warm-up, batch, run and statistics rules. Compiled from the same Rust
   harness crate where possible.
2. **Published seL4 figures:** cited in the results file with the hardware and kernel version
   each was measured on. The plan mentions about 850 cycles, about 0.25 µs at 3.4 GHz, as a published
   figure, not a Fyrkat measurement. The citation is found and recorded in the results file. No
   published figure is copied into a Fyrkat result.

## Cause analysis if W1 is above 1 µs

The results file separates, with evidence for each, and does not guess:

- **Virtualization:** compare W1 with the Linux socket baseline and with a trivial guest
  operation timed the same way (a loop of `svc` to the kernel's `seL4_Yield`, which has no IPC).
  The `svc` loop shows the cost of entering the kernel on this setup.
- **Hardware:** the recorded core types and the counter resolution.
- **seL4 behaviour:** kernel configuration (MCS or not, debug build or release, SMP), whether the
  fast path is taken, and the IPC path length where measurable.

## Records

Each C1 results file contains, in addition to the plan's list: this file's commit SHA, `CNTFRQ_EL0`
per run, the four spin-loop times per run, the host power and thermal output, the QEMU command, and
the raw batch data.

## Known limits

- HVF adds an unknown cost to every exception that leaves the guest. The `seL4_Yield` loop bounds
  the kernel-entry cost and does not remove it. [Inferred]
- Thirty runs show boot-to-boot spread on one machine. They do not show spread across machines.
- A 24 MHz counter is coarse, but the batch rule keeps its error under 1%. It does not remove
  jitter from the host scheduler.
- Cross-core results depend on which host cores the vCPUs land on, which this project cannot set.
