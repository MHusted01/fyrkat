# A5 step 1: does QEMU's SMMUv3, programmed from a seL4 root task, translate and confine one device stream?

**Not an A5 outcome.** Authorized by the owner on 2026-11-10 ("Implement and execute A5 step 1, including actual SMMUv3 translation and isolation experiments"). Step 0 showed reach and a global on/off effect and no translation. This step enables the SMMU and tests per-stream, per-page behaviour. No kernel, loader, dependency or ADR was changed. Labels as in AGENTS.md; [Measured] means checked by `verify_a5_step1.py` (7 checks, a presence check and a well-formedness check; 21 self-test corruptions) against the evidence in [`A5-step1/`](A5-step1/).

## What was built

| | |
|---|---|
| SMMU driver | [`smmuv3.rs`](../crates/e2-root-task/src/smmuv3.rs): a linear stream table, one context descriptor, a three-level stage-1 table of 4 KiB pages over one 2 MiB window of I/O virtual addresses, a command queue with `CMD_SYNC`, a polled event queue. Changing a structure and telling the SMMU about it are separate calls, so an experiment can omit the second |
| Device | [`edu.rs`](../crates/e2-root-task/src/edu.rs): QEMU's `edu`, found through the ECAM, as a DMA master that copies between its internal buffer and an address the test chooses. Two of them: stream `0x10` is configured, stream `0x18` never is |
| Experiment | [`a5_step1_root_task.rs`](../crates/e2-root-task/src/bin/a5_step1_root_task.rs), [`a5_step1_tests.rs`](../crates/e2-root-task/src/a5_step1_tests.rs). It logs through the user-level UART, so it runs on kernels without printing |
| Kernels | **E1-H** (hypervisor-enabled, debug, 1 vCPU, Rust loader: the step 0 baseline, [`build-a5-e1h.sh`](../build-a5-e1h.sh)) and **K2R** (no hypervisor support, 4 vCPUs, release, seL4's elfloader, `build-relk.sh`: the kernel the plan's K3 row is built on). K2R's configuration and function table have the same SHA-256 as the published K2R |
| Machine | QEMU 11.1.3 TCG `virt` with `iommu=smmuv3,highmem=off` and two `edu,dma_mask=0xffffffffff`, with QEMU's trace of its SMMU model |
| Procedure | [`run-a5-step1-evidence.sh`](../run-a5-step1-evidence.sh), `sanitize-run.py A5-step1`, `verify-evidence.py` |

Sources: Arm IHI 0070 for the formats; QEMU 11.1.3's `hw/arm/smmuv3.c`, `smmuv3-internal.h`, `smmu-common.c`, `include/hw/arm/smmuv3-common.h` and `hw/misc/edu.c`, read for this step, for what the model accepts and caches [Documented]. Two of its rules shaped the configuration: the context descriptor must set A and clear S, HA and HD, and the stream entry must clear S1STALLD and S1CDMax, or the model rejects them.

## Observed [Measured], identically in 3 of 3 boots on each kernel

The configuration: stream `0x10`, stage 1 only, one context descriptor (ASID 7, 39-bit input, 4 KiB granule); I/O virtual address `0x100000000` mapped read-write to page **P**; `0x100001000` mapped read-only to page **R**; `0x100002000` not mapped; a guard page **Q** mapped nowhere. P, Q and R are ordinary RAM at physical addresses between 1 and 2 GiB. The I/O virtual addresses are at 4 GiB, where this machine (`highmem=off`, 1 GiB of RAM) has neither RAM nor a device, so an address the device uses is never also the physical address of anything. (A first version of this experiment used a window at 128 MiB, which is the physical address of the machine's interrupt controller; the independent review caught it and the window was moved before this evidence was recorded.) Every transfer is 64 bytes; "events" are records the root task read from the SMMU's event queue.

| # | Test | In memory | In the event queue |
|---|---|---|---|
| 1 | SMMU enabled, no stream configured: the device writes to `0x100000000` and to P's physical address | P unchanged | 16 + 16 `C_BAD_STE`, stream `0x10` |
| 2 | **Mapped address:** P to the device's buffer and back | 16 of 16 words return | none |
| 3 | **Unmapped address:** write to `0x100002000` | Q and P unchanged | 16 `F_TRANSLATION`, write, page `0x100002000` |
| 4 | **Physical address:** write to Q's physical address | Q unchanged | 16 `F_TRANSLATION`, write, Q's page |
| 5 | **Read of unmapped memory:** read Q's physical address, then write the buffer to P | none of Q's content reaches P (the buffer reads as zero) | 16 `F_TRANSLATION`, read, Q's page |
| 6 | **Read-only mapping:** read R through `0x100001000`; then write to it | the read delivers R (16 of 16); R unchanged by the write | none; then 16 `F_PERMISSION`, write, page `0x100001000` |
| 7 | **Other stream:** the second device writes to `0x100000000`; then the first does its round trip | P unchanged by the second; the first's round trip works | 16 `C_BAD_STE`, stream `0x18`; then none |
| 8 | **Unmap:** table entry cleared; then `CMD_TLBI_NH_VA` and `CMD_SYNC` | before the command the write **still lands** (16 of 16); after it nothing lands | none; then 16 `F_TRANSLATION` |
| 9 | **Stream removal:** stream entry cleared; then `CMD_CFGI_STE` and `CMD_SYNC` | before the command the write **still lands**; after it nothing lands | none; then 16 `C_BAD_STE` |
| 10 | Global state at the end | | `CR0` still enabled, `GBPA.ABORT` never set, no global error |

**Is this translation and permission checking, or something else?** Four observations say it is the intended mechanism:
- The data in test 2 arrives in a page whose physical address (`0x7000a000` on E1-H, `0x6000a000` on K2R) is not the address the device used (`0x100000000`). With a bypassing or absent SMMU that address reaches no RAM (step 0).
- The refusals are per stream and per page, with different causes: an invalid stream entry (tests 1, 7, 9), a missing translation (3, 4, 5, 8), a write permission (6). The second device is refused at the address at which the first, in the same state of the SMMU, succeeds (test 7). `GBPA`, the global control step 0 used, is never touched.
- **QEMU's own trace agrees** [Measured, not independent of the model]: every translation it reports is `stage=1` for stream `0x10`, from `0x100000000` to P's physical address with read-write permission (11 times) or from `0x100001000` to R's with read-only permission (once); it reports no bypass, disable or abort decision at all; the events it reports are, by type and stream, exactly the 64 + 16 + 48 + 16 records the root task read; and it reports one page invalidation (ASID 7, `0x100000000`), two stream-entry invalidations and one context invalidation, where the root task issued them.
- **Five mutants each fail exactly one test** (E1-H, one boot each): without `CMD_TLBI_NH_VA` the write lands after the entry is cleared (and the trace has no page invalidation); without `CMD_CFGI_STE` it lands after the stream entry is cleared; with the "unmapped" address mapped to the guard page the write reaches Q; with the "read-only" page mapped writable the write changes R; with the second device's stream given the first one's address space, the second device's write reaches P. The other six tests have no mutant of their own: that they can fail is argued from the checks they make, not demonstrated.

**A removal is effective only once the invalidation has completed.** Tests 8 and 9 show a window: between clearing a table or stream entry and the completion of the invalidation command, QEMU's model keeps translating from its caches (its `smmu_iotlb_lookup` and its per-device configuration cache [Documented: `smmu-common.c`, `smmuv3.c`]). The mutants show that a teardown that omits the command is no teardown. (The converse, an invalidation without clearing the entry, was not tried; the model would simply walk the table again.) This is the property step 2 turns on.

## What this does and does not show

- **Shows:** from user level on unmodified seL4, on a hypervisor-mode debug kernel and on the non-hypervisor 4-node release kernel, a root task can enable QEMU's SMMUv3 and give one PCI function a stage-1 address space; the model then confines that function's DMA to the mapped pages with the mapped permissions, refuses an unconfigured function, and stops honouring removed mappings once the invalidation has completed. [Inferred] So a user-level SMMUv3 server looks possible to write against this model with no kernel change; what ran here is a driver inside the root task, not a server.
- **Does not show DMA confinement of a system.** The root task holds every capability and plays every role. What is confined here is the *device*, by a correctly programmed SMMU. Whether an untrusted party can make the programming wrong, or take memory back while it is mapped, is step 2's question and A5's.
- **One model, not hardware.** QEMU's SMMUv3 is an implementation of the architecture, with its own simplifications (the device's DMA is synchronous; a failed read leaves the device's buffer zero; one fault record per 4-byte access). Nothing follows for a hardware SMMU, its caches or its timing. An emulator pass is not evidence about hardware.
- **A missing `CMD_SYNC` cannot be detected here.** QEMU consumes commands inside the register write that advances the queue, so a teardown that issues the invalidation and does not wait for it would pass every test above; on hardware the wait is what closes the window. The mutants cover the two invalidation commands only (the prior-art note's O4 predicted this).
- **Not tested:** two configured streams with separate address spaces ("per stream" is shown as configured against unconfigured, and by the mutant that configures both alike); a mutant that omits `CMD_CFGI_CD`; anything but a single-page leaf invalidation; more than one core doing I/O (on K2R the root task runs on one core while three idle).
- **K2R's built-in device tree is not the machine's:** it is QEMU's dump without `iommu=smmuv3,highmem=off`. The kernel uses nothing that differs, and the root task takes its addresses from constants, not from the tree.
- **The tables and queues are ordinary cacheable memory with no cache maintenance.** That is right only because this SMMU reports coherent access (`IDR0.COHACC`), which the driver now checks before enabling.
- **Polled, no interrupts, no stage 2, no two-level stream table, no error recovery, one stream, three pages.** The model advertises no MSI; the event queue is read by polling.
- **The observation channels are the guest's own reads and the model's own trace.** They agree; neither is independent of the model.
- **Not K3 and not A5:** K3 is K2 with an SMMU *server* in the plan's sense (a component separate from its clients), and A5-arm needs its four tests. K2R is the release variant of K2; the debug K2 was not run with this experiment.

## Limits

- The driver has never run on hardware. It was written against the architecture's formats and checked against QEMU's definitions; where the two could differ on hardware (cacheability of tables and queues, barriers, the UART's baud rate) it follows the architecture as far as QEMU can show nothing wrong, which is not validation.
- Device registers and queue memory are reached with volatile accesses through `a5_mmio.rs`; its five `unsafe` blocks and two `unsafe fn` (`from_addr`, `map_ram`) carry `SAFETY` comments; an out-of-range register offset is counted and the count (0 in every run) is in each log's summary line.
- The machine must be started with `highmem=off`: the ECAM address is fixed in the code (step 0's constraint), and the I/O address window at 4 GiB is free of RAM and devices only then.
- Reviewed independently before commit (the second review of this session, 2026-11-11 local time): merge-ready with text corrections, which are made; the review confirmed that the behaviour is stage-1 translation and permission checking for one stream and not global blocking. The window move, the fifth mutant and the coherence check were made after that review, and the evidence was re-recorded with them; a third review checked those three changes against QEMU's source and the logs and found them sound.
