# A5 step 0: can a seL4 root task reach QEMU's SMMUv3 and an `edu` device, and does DMA go through the SMMU?

**Not an A5 outcome and not a DMA-confinement result.** This is the environment and feasibility probe the owner authorized on 2026-11-09 ("using the existing E1-H baseline where appropriate"). The SMMU was never enabled, no stream table or translation table was built, and no kernel, loader, dependency or ADR was changed. **Nothing here shows that any DMA was confined.** A successful register read, a created device and an assigned BAR show only reach; they are reported as reach.
Evidence labels as in AGENTS.md. [Measured] means produced by the scripts named below, on this machine, and checked by `verify_a5_step0.py` (9 checks, a presence check and a well-formedness check; 21 self-test corruptions).

**Re-recorded on 2026-11-10 after the independent review.** The review found that the probe mapped device registers with the default (cacheable) attributes and ordered nothing around the DMA; that its safe register accessors did not check what their safety comments assumed; and that the verifier accepted altered evidence (a control launched with an SMMU, a transfer that timed out, missing trace events). The helper now maps device pages without the cacheable attribute, bounds every access to its page, and issues a barrier around each DMA; the verifier checks each run's command line, every transfer's completion flags and the exact number of trace events. The evidence in [`A5-step0/`](A5-step0/) is from the re-run with the changed helper; the observations are the same as in the first run (kept locally, superseded). QEMU does not model memory types, so the changed mapping attributes are **not validated by any run**.

## What was run

| | |
|---|---|
| Kernel and loader | The E1-H kernel and the Rust loader of the E3 evidence build (hypervisor support on, debug, 1 vCPU), unmodified; the verifier requires their SHA-256 to equal the E3 record's |
| New code | A root task, [`a5_probe_root_task.rs`](../crates/e2-root-task/src/bin/a5_probe_root_task.rs), and a device-mapping helper, [`a5_mmio.rs`](../crates/e2-root-task/src/a5_mmio.rs), in the existing `e2-root-task` crate (no manifest change, `Cargo.lock` unchanged); [`build-a5-probe.sh`](../build-a5-probe.sh), [`boot-a5.py`](../boot-a5.py), [`run-a5-step0-evidence.sh`](../run-a5-step0-evidence.sh) |
| Machine | QEMU 11.1.3 TCG, `-machine virt,secure=off,gic-version=2,virtualization=on,iommu=smmuv3[,highmem=off] -cpu cortex-a57 -smp 1 -m 1024 -device edu`, with `-trace "smmuv3_translate_*"` so QEMU prints each translation decision its SMMU model makes |
| Runs | The primary arrangement three times (`highmem=off`, `edu,dma_mask=0xffffffffff`); the default edu mask; the default `highmem=on` layout (wide and default mask); three negative controls |
| Evidence | [`A5-step0/`](A5-step0/) (sanitized); procedure: `run-a5-step0-evidence.sh`, `sanitize-run.py A5-step0`, `verify-evidence.py` |

## Observed facts [Measured]

**Start-up.** QEMU 11.1.3 starts with `iommu=smmuv3` and an `edu` device, and the unmodified E1-H kernel boots on it and reaches the root task.

**Reach (3 of 3 boots identical).**
- The root task's bootinfo has 52 untypeds, 27 of them device. The SMMU's registers (`0x09050000`), the ECAM (`0x3f000000`, or `0x4010000000` with `highmem=on`) and the PCI memory window (`0x10000000`) are each inside a device untyped (`0x09000000+0x1000000`, `0x20000000+0x20000000`, `0x4000000000+0x4000000000`, `0x10000000+0x10000000`). **The kernel does not claim the SMMU** (`ARM_SMMU` is off in this configuration), so no capability is withheld.
- The root task maps them and reads the identification registers of QEMU's SMMUv3 model: IDR0 `0x0d44101b`, IDR1 `0x02730010`, IDR5 `0x00000074`, AIDR `1`; decoded: stage 1 and stage 2 supported, 4 KiB granule, 44-bit output size, 16-bit stream ids, two-level stream tables supported, coherent access, **no MSI support** (IDR0.MSI is 0). At reset CR0 is 0 (SMMU disabled) and GBPA is `0x1000`.
- Through the ECAM it finds the host bridge (`1b36:0008`, 00:00.0), a virtio device (`1af4:1000`, 00:01.0) and **edu (`1234:11e8`, 00:02.0)**. It sizes BAR0 (1 MiB), assigns `0x10000000`, enables memory space and bus mastering, and reads edu's identification (`0x010000ed`) and liveness (`0xedcba987`, the complement of the value written) registers.

**DMA goes through the SMMU model, and the SMMU's state decides whether data moves.** The root task copies a 64-byte pattern from RAM page A into edu's internal buffer and from there into RAM page B, three times: in the reset state, with the SMMU's global abort bit (`GBPA.ABORT`) set, and after clearing it.
- With edu's DMA mask widened to 40 bits: the data moves (16 of 16 words), then does **not** move (0 of 16) while the abort bit is set, then moves again [3 of 3 boots, identical]. QEMU's trace shows, for stream id `0x10` (edu's requester id) at the pages' physical addresses (`0x70003000`, `0x70004000`): `translate_disable ... bypass (smmu disabled)` for the transfers in the reset and cleared states, and exactly 32 `translate_abort` events between the moment the bit is set and the root task's report of that state. There are no `translate_success` or `translate_bypass` events, because the SMMU was never enabled.
- With the **default** 28-bit mask: nothing moves in any state, and the SMMU sees only addresses below `0x10000000` (the page's address truncated: `0x70003000` is seen as `0x3000`). So with default settings edu cannot reach RAM above 256 MiB.
- The default `highmem=on` layout (ECAM at `0x4010000000`) gives the same results.

**Hazards (negative controls, all fail as stated).** (1) Without an SMMU in the machine, the first read of its address is a **fatal synchronous external abort of the root task** (`vm fault ... status 0x92000010`); nothing reads as zero. (2) A probe built for the wrong ECAM layout reads the SMMU fine and then takes the same abort at the ECAM. In both cases `A5P_DONE` is not reached.

**The root task cannot discover this arrangement.** The device tree it receives is the kernel's build-time tree: it has a PCIe node (ECAM `0x4010000000`) but **no SMMU or IOMMU node**, and a device untyped covers all non-RAM address space whether or not anything is there. The addresses and the layout are therefore fixed in the probe at build time (`build-a5-probe.sh low|high`). The tree QEMU generates for the machine does describe the SMMU (`smmuv3@9050000`, 0x20000 bytes, with a requester-to-stream identity map); it is not what the root task sees.

## What this does and does not show

- **Shows [Measured]:** the arrangement starts; a root task can reach the first page of the SMMU's registers, the ECAM and edu's BAR, with no kernel change (the SMMU's second register page, which holds the event-queue indices, and its interrupt were not tried here; step 1 maps the second page); QEMU's SMMU model sits on edu's DMA path (its decisions are printed and its global state changes whether data moves); the SMMU is architecturally capable of stage 1 and stage 2, with 4 KiB granules.
- **Does not show:** translation. The SMMU was disabled throughout, so the abort that stopped the data is the **global** bypass-or-abort behaviour of a disabled SMMU, not a per-stream or per-page decision. There was no stream table entry, context descriptor, translation table, command or event queue. Nothing here exercises mapping, unmapping, TLB invalidation, or revoke-while-mapped. **Do not read "DMA traversed the SMMU" as "DMA was confined".**
- **The observation channel is QEMU's own trace.** It is not independent of the model: it says what QEMU's SMMU model decided, not what hardware would. [Inferred] It is still a better observation than the data alone, because it names the stream, the address and the decision for every access.
- Emulator only (TCG, one vCPU); an emulator pass is not evidence about hardware.

## Constraints a real step 1 must respect [Inferred from the measurements; step 1 has not run]

1. **Layout is fixed at build time** (above), and a wrong guess kills the root task.
2. **edu's 28-bit mask is useful:** it forces every IOVA below 256 MiB, so with the SMMU enabled a stage-1 mapping from a low IOVA to a high RAM page can be tested without widening the mask; the unmapped-IOVA control is any other low address. (Widening it, `dma_mask=`, is a harness setting, not a kernel change.)
3. **Memory the SMMU reads by itself** (stream table, context descriptor, translation tables, command and event queues) must be ordinary RAM frames whose physical addresses the root task knows. The probe already obtains physical addresses of frames (`frame_get_address`).
4. **The SMMU advertises no MSI support**, so its event and global-error interrupts cannot be MSIs [Inferred from IDR0]. A step 1 can poll the event queue's producer index instead of taking an interrupt [Hypothesis: not tested].
5. **Enabling the SMMU turns the default from bypass to abort for every stream with no entry**, including streams other than edu's; the root task has no other DMA master, so this should be safe on this machine [Hypothesis].
6. **What step 1 should show before anything is called an A5 result:** with SMMUEN set, an edu transfer to a mapped IOVA changes the mapped page and QEMU prints `translate_success`; a transfer to an unmapped IOVA leaves its target unchanged, QEMU prints a translation fault, and the event queue records it; after the stream's mapping is removed and invalidated, the same transfer no longer lands. Each needs a before/after pair and a mutant that skips the invalidation.

## Alternatives if the full design proves infeasible [Hypothesis]

- If QEMU's SMMU model cannot express a stage-1 stream setup: stage 2 (the model advertises it), or the `virtio-iommu` device (different mechanism, not SMMUv3; it would test the revoke-while-mapped crux but not the SMMU server the plan calls K3).
- If a kernel without hypervisor support is required: the Route I result ([RouteI](RouteI.md)) shows K1 and K2 boot under seL4's own elfloader, but the probe has not been run on them.

## Smallest justified next step

A5 **step 1** on the same baseline: enable the SMMU with one stage-1 stream table entry for stream id `0x10`, one mapped IOVA page and one unmapped IOVA, with the verifier checks and mutants listed in point 6. It is new code of a few hundred lines in the existing crates, no dependency or kernel change. **Authorized by the owner on 2026-11-10 and run: [A5 step 1](A5-step1.md).**

## Limits of this record

The probe and its verifier were reviewed independently on 2026-11-10 and changed as described at the top; a second independent review (2026-11-11) checked those changes and found them merge-ready, with residual findings that were then addressed: a mapping of ordinary memory is now an `unsafe fn` with a stated contract, a second mapper cannot be created, out-of-range register offsets are counted and reported, and the verifier requires 16 abort events per page and the machine's memory size. A third review checked those last changes and found them sound. `verify_a5_step0.py` checks the logs against the claims above and that the corruptions listed in `--self-test` are caught; it recomputes nothing from QEMU's source. QEMU's SMMUv3 source was not read for this step (it was for step 1). The pinned QEMU is 11.1.3; CI uses 8.2.2, so the CI environment may behave differently and was not tested.
