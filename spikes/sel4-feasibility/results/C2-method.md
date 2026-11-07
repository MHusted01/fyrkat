# C2 method: page faults against Linux

- **Status:** Draft for owner review. No run of C2 has happened, pilot or otherwise.
- **Plan:** [seL4 feasibility spike plan](../../../docs/research/sel4-spike-plan.md), experiment C2,
  approved at `46a90fa`.
- **Effect:** the plan requires this file to be committed before any C2 run. Edits before the first
  run are ordinary edits. Changing the method after the first run is an Amendment to the plan. Every
  C2 results file cites the commit SHA of this file as it exists on `main`.
- **Pilot rule:** a pilot may check that the harness works. Its numbers are not recorded as
  results and may not change this method.

This file fixes the method. It does not change any criterion.

## Criterion

From the plan, unchanged:

- **Pass:** every workload is within 3 times Linux.
- **Investigate:** any workload is above 3 times. Record the cause and any identified fix. Above 5
  times, profile as well, and record whether the cost is inherent to the design, to the user-level
  pager, or to the virtualized setup.

3 times and 5 times are investigation thresholds, not pass or fail lines. Each workload is reported
on its own. Workloads are not pooled, and none is dropped after results exist.

**Interpretations to confirm (owner).** The plan leaves these open. The owner confirms or changes
each before the first run:

1. **The headline is cost per page touched**, not cost per fault taken (see
   [Counting and reporting](#counting-and-reporting)).
2. **Linux keeps its shipped `fault_around_bytes`** for the headline. The one-page setting is a
   sensitivity result.
3. **The seL4 headline pager retypes one frame inside each fault**, so that its cost includes the
   zeroing that Linux does inside its fault.
4. **The statistic** is the median of 30 run medians.

## Setup

- **Host and virtual machine:** Apple M2 Pro under macOS 27.2. QEMU 11.1.3, `-accel hvf`,
  `-cpu host`, machine `virt` with the GIC version A3 selects, 4 vCPUs, 2 GiB RAM, for both systems.
  Guest RAM is preallocated, with `-object memory-backend-ram,prealloc=on` or the equivalent, so that
  the host's first-touch cost does not fall inside a timed batch. If QEMU 11.1.3 cannot preallocate
  under HVF on this host, that is reported to the owner before any run. No run proceeds with the
  first-touch cost uncontrolled.
- **Order:** the two systems run in alternating order (seL4, Linux, seL4, Linux), each run a fresh
  VM boot, so that host drift hits both. Core-type observation and the power, thermal and process
  records follow the [C1 method](C1-method.md#hardware-and-setup).
- **Linux guest, pinned here:** `debian-13-nocloud-arm64-20261103-2651.qcow2` from
  `cloud.debian.org/images/cloud/trixie/20261103-2651/`, SHA-512
  `f99c23f0d4c18ba7512bae254a201b72dafe11ef0c69beac489a2daba4e128171ca5dcfcdc6d76c2b81a8aa17fc6da8ced2d0a3b9442c97358b3e99ed6668ca7`
  [Documented: that directory's `SHA512SUMS`]. Its package manifest lists `linux-image-6.12.115+deb13.1-arm64`
  [Documented: the image's `.json` manifest]. The hash is checked against the downloaded file before
  use, and a mismatch stops the work. If the owner chooses another image, this section changes
  before the first run.
- **Linux runtime state:**
  - each boot uses QEMU `-snapshot`, so the base image stays unchanged and its hash stays valid;
  - the harness arrives on a second read-only virtio disk with a FAT filesystem made on the host.
    Whether the guest kernel mounts it is **not tested**. If it cannot, the delivery method changes
    before the first run;
  - transparent huge pages are turned off at runtime, by writing `never` to
    `/sys/kernel/mm/transparent_hugepage/enabled`, and the harness records the file afterwards;
  - default services only. The harness waits until the one-minute load average is under 0.05 before
    it starts, and records the value;
  - before each timed phase it runs `sync` and waits until `Dirty` in `/proc/meminfo` is under 1 MiB,
    so writeback does not run inside a batch;
  - the harness process is pinned to CPU 0 with `sched_setaffinity`.
- **seL4 side:** the kernel build in the [C1 method](C1-method.md#kernel-build-for-c1-and-c2). The
  B3 pager, at a commit recorded in the results file. The client and the pager are both pinned to
  core 0, so no inter-processor interrupt takes part. The headline pager maps **one page per fault**
  and retypes **one 4 KiB frame inside each fault**. Any other pager policy is a separate
  experiment with its own record and is never the headline. The pager commit and its build profile
  (release) are fixed before the first run.
- **Harness:** the same Rust crate, built in release mode for each target (static
  `aarch64-unknown-linux-musl` for Linux). The workload code is shared. Only the memory-mapping
  layer differs.
- **Page size:** 4 KiB on both.
- **Timing source and resolution:** the virtual counter, as in C1, with the same batch rule: one
  tick under 1% of a batch, so a batch lasts at least 100 ticks (about 4.2 µs at 24 MHz). A fault
  costs far more than 4 ns, so a real batch of 1,024 pages lasts far longer [Inferred]. The harness
  records the tick count of every batch and stops the run, as in C1, if a batch falls under 1,000
  ticks.

## Workloads

Each workload touches one byte per page, in the order stated, and times batches of 1,024 pages.

| ID | Workload | Region | Order | Setup before timing | Operation timed |
|---|---|---|---|---|---|
| F1 | First-touch anonymous | 128 MiB (32,768 pages), fresh mapping | Sequential | Mapping created, nothing touched | Write one byte to each page |
| F2 | File-backed read | 128 MiB file, fully resident | Sequential | File written, every page confirmed resident (`mincore` on Linux, the pager's residency table on seL4) | Read one byte from each page |
| F3 | Copy-on-write | Private mapping of the same 128 MiB file | Sequential | Mapping created and every page read, so each is mapped read-only | Write one byte to each page |
| F4 | Mixed | 64 MiB working set (16,384 pages) | One pass in a fixed random order (below) | As F1, F2 and F3 for their regions | 8,192 anonymous first-touch writes (50%), 4,096 file-backed reads (25%), 4,096 copy-on-write writes (25%) |

Notes:

- **F4 regions:** the anonymous region is 8,192 pages (32 MiB). The file-backed region is the first
  4,096 pages (16 MiB) of the 128 MiB file. The copy-on-write region is a private mapping of the
  next 4,096 pages (16 MiB) of the same file, read once beforehand. The three regions do not overlap.
- **F4 order:** the list of 16,384 (region, page) pairs is generated in region order, then shuffled
  with a Fisher–Yates shuffle. The random numbers come from `xorshift64*` with state shifts 12, 25 and
  27 and multiplier `0x2545F4914F6CDD1D`, seeded with `0x0F1A2B3C4D5E6F70`. Both systems get the same
  order. F4 has 16 batches of 1,024 pages.
- **F1 to F3** have 32 batches each. A fresh mapping is used for each workload and each run, so F2
  does not warm F3.
- **File:** on Linux it is a regular file on the guest's root filesystem, not tmpfs, because tmpfs
  uses a different fault path. On seL4 it is an in-memory store owned by the pager. The results file
  states this difference. Disk reads never happen in a timed phase.
- **Frame source on seL4:** the headline retypes one frame per fault inside the timed batch. The seL4
  kernel zeroes memory on retype, and the Linux kernel zeroes pages inside its fault, so both
  headlines include zeroing. As a sensitivity result the pager also runs with a retype of 64 frames at
  a time, inside the timed batch. The cost of the retypes is reported separately.

## Counting and reporting

- **Headline: cost per page touched**, which is total batch time divided by 1,024 pages. Both
  systems touch the same pages, so this is the same work. Linux may map several pages per fault
  because of fault-around.
- **Also reported: cost per fault taken**, with the fault count from `getrusage` (`ru_minflt`) on
  Linux and from the pager's counter on seL4. On Linux the count is the difference between a read
  taken immediately before the timed phase and one taken immediately after it. The two figures are
  reported side by side and never mixed.
- **Fault-around sensitivity:** for F2 and F4, which both include file-backed reads, Linux is run a
  second time with `fault_around_bytes` set to 4096 in the guest, so that one fault maps one page.
  This is a full 30-run series with fresh boots, reported next to the headline series. The
  3-times test uses the shipped setting.
- **Runs:** 30 per workload per system and setting, each in a fresh VM boot.
- **Batches:** every batch of every run is kept, including the first, because first-touch cost is
  the measurement. No batch or run is removed as an outlier. A stopped run is reported with its data
  and cause, as in C1.
- **Per-run statistics:** median and 99th percentile (nearest rank) of the batch results. With 16 or
  32 batches the 99th percentile is close to the maximum, and the results file says so.
- **Reported across runs:** the median of run medians (the headline), the minimum and maximum run
  median, the interquartile range (Q3 minus Q1, linear interpolation), and the median of run 99th
  percentiles, for each system and workload.
- **Ratio:** the seL4 headline divided by the Linux headline, per workload, rounded to two
  significant figures, with a range from the lowest seL4 run median over the highest Linux run
  median to the highest seL4 run median over the lowest Linux run median. The 3 times threshold is
  tested on the headline ratio.

## Cause analysis above 3 times

The results file does not guess at causes. For any workload above 3 times it records:

- **Where the time goes:** a split of the seL4 fault path into kernel fault delivery, pager handling
  and mapping calls, timed in the pager with the same counter.
- **Design versus setup:** the cost of a `seL4_Yield` loop and of a bare Linux syscall loop
  (`getppid`), and the number of VM exits per batch if QEMU trace events under HVF provide it. The
  two loops stay inside the guest, so they bound the kernel-entry cost and do not isolate
  virtualization cost [Inferred].
- **Fix candidates:** batching map calls, mapping several pages per fault, or a faster pager path.
  Each candidate is a separate experiment with its own record. It does not change this method.

Above 5 times the same record adds a profile and the classification the plan requires.

## Records

Each C2 results file contains, in addition to the plan's list: this file's commit SHA, the pager
commit, the kernel configuration, the Linux image hash and kernel version, the contents of the
transparent-huge-page and `fault_around_bytes` files, the load average and `Dirty` readings, the
QEMU version and command, `CNTFRQ_EL0` per run, the host power, thermal and process output, per-run
fault counts, and the raw batch data.

## Known limits

- HVF adds a cost to guest exits on both systems. It cancels in the ratio only if it is the same on
  both, which is not shown. [Inferred]
- The Linux guest has a general-purpose memory manager and the seL4 side has one purpose-built
  pager. The ratio compares those two designs and says nothing about a mature seL4 pager.
- One region size per workload. The result is not a scaling curve.
- Preallocation removes the host's first-touch cost from the timed batches. It does not make the
  guest's memory behave like cold memory on real hardware.
- The Debian kernel's defaults for transparent huge pages and `fault_around_bytes` were not checked
  when this file was written. They are recorded at run time.
