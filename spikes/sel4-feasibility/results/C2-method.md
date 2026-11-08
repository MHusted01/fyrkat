# C2 method: page faults against Linux

- **Status:** Approved by the owner on 2026-11-08 (decision 1, choices 1a to 1c), recorded in the
  plan's Amendments, subject to the independent review recorded there. Takes effect when merged to `main`. Edits after that and before the first run are ordinary, except one that loosens a criterion.
  No run of C2 has happened, pilot or otherwise.
- **Plan:** [seL4 feasibility spike plan](../../../docs/research/sel4-spike-plan.md), experiment C2,
  approved at `46a90fa`.
- **Effect:** the plan requires this file to be committed before any C2 run. Edits before the first
  run are ordinary edits, except an edit that loosens a criterion, which is an Amendment. Changing the
  method after the first run is an Amendment to the plan. Every
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

**Interpretations (confirmed by the owner on 2026-11-08).** The plan leaves these open. The owner
confirmed each:

1. **The headline is cost per page touched**, not cost per fault taken (see
   [Counting and reporting](#counting-and-reporting)).
2. **Linux keeps its shipped `fault_around_bytes`** for the headline. The one-page setting is a
   sensitivity result.
3. **The seL4 headline pager retypes one frame inside each fault that allocates** (F1, F3 and the
   allocating part of F4), and in F1 and F3 it also **zeroes the frame explicitly** inside the
   fault. The seL4 kernel does not zero on each retype: frame creation only cleans the cache, and
   memory is cleared when an untyped with no children is reset, which a retype from such an untyped
   triggers [Documented: seL4 `62e345c`, `objecttype.c` `Arch_createObject` and `untyped.c`
   `resetUntypedCap`]. Linux zeroes an anonymous page in its fault. The pinned Debian kernel is built
   with `CONFIG_INIT_ON_ALLOC_DEFAULT_ON=y` [Documented: Debian kernel-team `linux`,
   `debian/6.12.115-1`, `debian/config/config`], so it is expected to zero a copy-on-write
   destination page before copying into it [Inferred]. Without the explicit writes the seL4 side
   would skip work that Linux does, which favours a Pass. The variant without them is a sensitivity
   result. F2 maps an existing frame. See
   [Pager action per workload](#pager-action-per-workload-on-sel4).
4. **The statistic** is the median of 30 completed-run medians, with the rules under
   [Counting and reporting](#counting-and-reporting).
5. **The workload order and cleanup** within a boot (below).

## Setup

- **Host and virtual machine:** Apple M2 Pro under macOS 27.2. QEMU 11.1.3, `-accel hvf`,
  `-cpu host`, machine `virt` with the GIC version A3 selects, 4 vCPUs, 2 GiB RAM, for both systems.
  Guest RAM is preallocated, with `-object memory-backend-ram,prealloc=on` or the equivalent, so that
  the host's first-touch cost does not fall inside a timed batch. If QEMU 11.1.3 cannot preallocate
  under HVF on this host, that is reported to the owner before any recorded run. No run proceeds with
  the first-touch cost uncontrolled.
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
    Whether the guest kernel mounts it is **not tested**. A harness pilot, which the plan allows,
    checks it. If it cannot mount, the owner is told and the delivery method changes by an
    Amendment, because a pilot has then already run;
  - transparent huge pages are turned off at runtime, by writing `never` to
    `/sys/kernel/mm/transparent_hugepage/enabled` and to every
    `/sys/kernel/mm/transparent_hugepage/hugepages-*/enabled` that exists, and the harness records
    those files afterwards;
  - default services only. The harness waits up to 10 minutes for the one-minute load average to
    fall under 0.05 before it starts, and records the value. If it does not, the run is stopped and
    reported as a stopped run;
  - before each timed phase it runs `sync` and waits until `Dirty` in `/proc/meminfo` is under 1 MiB,
    so writeback does not run inside a batch;
  - the harness process is pinned to CPU 0 with `sched_setaffinity`.
- **seL4 side:** the kernel build in the [C1 method](C1-method.md#kernel-build-for-c1-and-c2). The
  B3 pager, at a commit recorded in the results file. The client and the pager are both pinned to
  core 0, so no inter-processor interrupt takes part. The headline pager maps **one page per fault**
  and retypes **one 4 KiB frame inside each fault that allocates**. Any other pager policy is a separate
  experiment with its own record and is never the headline. The pager commit and its build profile
  (release) are fixed before the first run.
- **Harness:** the same Rust crate, built in release mode for each target (static
  `aarch64-unknown-linux-musl` for Linux). The workload code is shared. Only the memory-mapping
  layer differs.
- **Page size:** 4 KiB on both.
- **Timing source and resolution:** the virtual counter, as in C1, with the same batch rule: one
  tick under 1% of a batch, so a batch lasts more than 100 ticks (about 4.2 µs at 24 MHz). A fault
  costs far more than 4 ns, so a real batch of 1,024 pages lasts far longer [Inferred]. The harness
  records the tick count of every batch. A batch of 100 ticks or fewer fails the 1% rule: the run stops,
  the owner is told, and the batch size is not changed afterwards. C2 does not use C1's 1,000-tick
  flag. With Linux fault-around, an F2 batch may need only about one fault per 16 pages, and its
  length in ticks is not known in advance [Inferred].

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
  with a Fisher–Yates shuffle: for `i` from 16,383 down to 1, take `j = x mod (i + 1)` where `x` is the
  next output, and swap positions `i` and `j`. The random numbers come from `xorshift64*`: `x ^= x >> 12; x ^= x << 25;
  x ^= x >> 27;` and the output is `x * 0x2545F4914F6CDD1D` modulo 2^64, seeded with `0x0F1A2B3C4D5E6F70`. Both
  systems get the same order. F4 has 16 batches of 1,024 pages.
- **Order within a boot, and cleanup:** F1, F2, F3, F4, each on a fresh mapping. After each workload,
  outside timing, the region is unmapped and on seL4 its frames are revoked. **Before every timed
  phase, F1 included,** the pager performs a throwaway retype from the untyped it will use and keeps
  that object until the phase ends. That forces any untyped reset, which can clear a large region
  (untypeds handed over at boot start with their free index at the end, so the first retype resets and clears the whole untyped [Documented: seL4 `boot.c`, `untyped.c`]), to happen
  outside timing, so that none falls inside a timed batch. On Linux the harness calls `munmap`, and
  the file's pages stay resident.
- **F1 to F3** have 32 batches each. A fresh mapping is used for each workload and each run, so F2
  does not warm F3.
- **File:** on Linux it is a regular file on the guest's root filesystem, not tmpfs, because tmpfs
  uses a different fault path. On seL4 it is an in-memory store owned by the pager. The results file
  states this difference. Disk reads never happen in a timed phase.

### Pager action per workload on seL4

The headline pager does the following, and any other action is a separate result:

- **F1:** retype one 4 KiB frame inside the fault, zero it with an explicit 4 KiB write of zeros,
  and map it read-write. Linux zeroes an anonymous page inside its fault [Inferred: Linux source not
  read this session].
- **F2:** the store's frame already exists and is resident. Map it read-only. No retype, copy or
  zeroing. Linux maps a page-cache page without zeroing, so none is expected on either side.
- **F3:** retype one frame, zero it with an explicit 4 KiB write of zeros, copy 4 KiB into it from
  the store's frame, and remap the page read-write. The zero matches the work Linux is expected to
  do with `init_on_alloc` on [Inferred]. The variant without the zero is a sensitivity result.
- **F4:** each access follows the action for its region.

Zeroing therefore sits in both headlines for F1 and F3, by the explicit write on seL4. As a sensitivity result the pager also runs
with a retype of 64 frames at a time, inside the timed batch, for F1, F3 and the allocating part of
F4. The cost of the retypes is reported separately.

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
- **Stopped runs:** a run is **completed** when one boot finishes F1 to F4 on one system and
  setting. A run is **stopped** by a batch of 100 ticks or fewer, a load average that never falls under
  0.05, a crash or hang, or a wall time over 30 minutes. Stopped runs are kept and reported in their
  own table with their data and cause. Each is replaced by a fresh, labelled run, up to 10 per system
  and setting, placed at the end of that system's alternating order. The headline statistics use the
  30 completed runs only. A sensitivity result includes the stopped runs' data. The 3 times test must
  hold with and without them to be reported as met. If 30 completed runs cannot be had, the outcome
  is Investigate, with the cause.
- **Per-run statistics:** median and 99th percentile (nearest rank) of the batch results. With 16 or
  32 batches the nearest-rank 99th percentile is the maximum batch, and the results file says so.
  The median of an even number of values is the mean of the two middle values.
- **Reported across runs:** the median of run medians (the headline), the minimum and maximum run
  median, the interquartile range (Q3 minus Q1, linear interpolation, the R-7 method), and the median of run 99th
  percentiles, for each system and workload.
- **Ratio:** the seL4 headline divided by the Linux headline, per workload, with a range from the
  lowest seL4 run median over the highest Linux run median to the highest seL4 run median over the
  lowest Linux run median. Ratios are rounded to two significant figures for display only. The 3
  times threshold is tested on the unrounded headline ratio.

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
transparent-huge-page and `fault_around_bytes` files, the Linux kernel command line (`/proc/cmdline`)
and the boot line that reports memory auto-initialisation (`init_on_alloc`), the load average and `Dirty` readings, the
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
