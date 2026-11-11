# A5 design proposal: user-level SMMUv3 confinement (K3)

- **Status:** Proposal for the owner, 2026-11-09. It decides nothing, executes nothing, and grants nothing. A5 stays blocked until the owner authorizes it ([plan](sel4-spike-plan.md), Amendments of 2026-11-08: "held for a reviewed design and its own authorization").
- **Builds on** the [prior-art note](dma-confinement-prior-art.md), which should be read first, and on the A2a result ([A2a](../../spikes/sel4-feasibility/results/A2a.md)).
- **Evidence labels** are as in AGENTS.md. [Measured] here means measured on this machine on 2026-11-09.

## 1. What has to be shown

The plan's P5: *a device reaches only memory mapped for it, and teardown blocks device access before memory is reused.* A5-arm needs K3 (a trusted user-level SMMUv3 server, **no kernel change**) to pass four tests: a negative test (DMA outside the mapping faults), cooperative teardown, **revoke-while-mapped** (memory reclaimed by revoke while the server still maps it) and driver-killed-during-DMA.
A5-arm **Fail** includes "DMA into reclaimed memory succeeded" and "the only working option needs a Class 3 change". A5-arm Fail falsifies the hypothesis (decision rule 5). K4, an in-kernel driver, is Class 3 and unavailable.

## 2. SMMU requirements for K3

What a server on QEMU `virt` with `iommu=smmuv3` has to do [Documented in the prior-art note: Arm IHI 0070 and QEMU's `hw/arm/smmuv3.c`; not re-read here]:
1. Reach the SMMU's MMIO registers and the event, command and stream-table memory as capabilities (device frames and ordinary frames of its own).
2. Build a stream table entry per device stream (the PCI requester ID), a context descriptor and stage-1 translation tables; issue `CMD_CFGI_*`, `CMD_TLBI_*` and `CMD_SYNC` on every change and wait for completion. An entry is updated by writing V=0, a barrier, the invalidation and the sync.
3. Read the event queue so that a faulting DMA is reported, and abort (not bypass) any stream with no mapping.
4. Never release a frame to the kernel's free pool until the stream's mapping is gone **and** the invalidation has completed.

QEMU 11.1.3 on this host [Measured]: `-machine virt,iommu=smmuv3` starts with a PCI device attached, and `edu`, `virtio-blk-pci`, `virtio-rng-pci` and `pci-testdev` exist for aarch64. `edu` can be told to DMA to an address the test chooses; it ignores DMA errors (so "target memory unchanged" is the check) and starts DMA from a timer after the trigger write [prior-art note].

## 3. What the pinned seL4 does and does not give

- **No SMMUv3 anywhere** in the tree; an SMMUv2 driver exists (`src/drivers/smmu`, `src/arch/arm/object/smmu.c`, `iospace.c`) [Measured]. `ARM_SMMU` is **off in K0, K1, K2 and E1H** [Measured: the four recorded configurations].
- The SMMUv2 support reaches into existing finalisation: `Arch_finaliseCap` for the VSpace capability calls `smmu_cb_delete_vspace`, with other `smmu_*` calls on the SMMU capability types (`src/arch/arm/64/object/objecttype.c`, lines 152 to 205, under `CONFIG_ARM_SMMU`) [Measured]. The plan classes such a hook as Class 3. K3 may not add one.
- **The kernel does not know what the SMMU maps.** Reclaiming memory is `Revoke` and then a retype of the untyped. In A2a, `cteRevoke`, `cteDelete`, `invokeUntyped_Retype` and `resetUntypedCap` are textually identical to K0's in K1, K2 and E1-H, and nothing in them can wait for a device [Measured text, Inferred behaviour]. But `finaliseCap`, `createObject` and `decodeUntypedInvocation` differ in all three, and `Arch_finaliseCap` (which unmaps frames) differs in K1 and K2, so the text of the reclamation path is **not** the same across them.
- **Proof coverage:** none. No verified configuration "take[s] into account address translation for devices", and the proof "assumes that DMA is off" [Documented: A2a, section 3]. The server is new, unverified, trusted code (label S) that the P5 cell must list.
- Whether the SMMU's registers are reachable as device untypeds, or claimed by the kernel: **measured on 2026-11-10 on the E1-H kernel (not K2)**: they are inside a device untyped and the kernel does not claim them (`ARM_SMMU` off); the root task reads the registers of QEMU's SMMUv3 model ([A5 step 0](../../spikes/sel4-feasibility/results/A5-step0.md)). Step 1 measured the same on K2R (the release variant of K2); the debug K2 was not used.

## 4. The crux, and the smallest meaningful falsification test

The crux is revoke-while-mapped: a party that can revoke a frame, or its untyped, takes the memory back and reuses it while the device can still write to it. Nothing in the kernel prevents that. So K3 can only work if **no untrusted party can reclaim memory a device still reaches**, by the shape of the authority tree and not by a kernel hook.

**The test (one stream, one page, one device).** A minimal server in a root-task variant (new code in the existing crates, no manifest change, as E3):
1. *Positive control:* map one 4 KiB frame F for `edu` and show a DMA into F changes F.
2. *Negative control:* a DMA to an unmapped IO address leaves its target unchanged and produces an event (or a QEMU trace).
3. *The falsifier* (to be run on K3 with a donor and a server in separate protection domains; the exploratory [A5 step 2](../../spikes/sel4-feasibility/results/A5-step2.md) of 2026-11-11, in which one root task plays every role, is **not** this test and its result is not an A5-arm outcome)*:* a donor that gave F to the server revokes it, the kernel retypes the reclaimed memory as another object, the stream is still mapped, and `edu` DMA is triggered. **If the DMA changes the reused memory, A5-arm is Fail under K3 with no kernel change.** If the design makes the reclaim impossible for an untrusted donor (for example: the DMA memory comes from an untyped that only the server and the trusted root task hold, and donors never keep a parent of it), the same test must show that the donor's revoke does not return the memory, and the claim becomes: *confinement holds against untrusted donors, and the root task is in the trusted base*.

I expect the naive design (the donor keeps the parent capability) to fail step 3, and the ownership design to survive it at the price of putting the root task in the P5 trusted base [Inferred]. (Since then, 2026-11-11: the naive arrangement has been run with one task in every role, and the device did reach the reused memory, see the A5 step 2 record; the ownership design has not been run.) The remaining two P5 tests (cooperative teardown, driver killed) follow from the same server and are cheaper.

## 5. What would be needed, and the one choice that blocks it

- **No new dependency and no new tool.** QEMU, the cross compiler, the loader and the Rust toolchain already in use suffice; the code is new Rust in the existing crates plus a QEMU command-line option.
- **Authorization:** A5 itself, with this design reviewed; and a decision on the kernel it runs on. K3 is defined as K2 (non-hypervisor, 4 vCPUs). The Rust loader cannot start a non-hypervisor kernel (A3, E1 specification), and A3 recorded that the 4-node kernel aborts in seL4's own elfloader under TCG too ("HVC is not supported for PSCI") and has not been shown to boot anywhere. **Correction, 2026-11-10:** seL4's own elfloader boots K2 (4 vCPUs) under QEMU TCG when its device tree says PSCI `smc` and QEMU runs with `virtualization=on` ([Route I](../../spikes/sel4-feasibility/results/RouteI.md)), so a loader for K2 is known; A5 itself has not been run on K2. The owner accepted the Stage B matrix Amendment as the working experimental plan on 2026-11-10; the design of K3 is still the owner's to choose.
- **A cheaper first probe** (step 0 ran on 2026-11-10: environment and reach only, SMMU never enabled. [Step 1](../../spikes/sel4-feasibility/results/A5-step1.md) then ran what steps 1 and 2 of section 4 describe, in one root task, on E1-H and on K2R. Step 3 has not run as described: see the note in section 4): run steps 1 to 3 on the existing E1-H kernel (the Rust loader boots it), labelled as informational and outside the matrix like E1 to E3. `invokeUntyped_Retype` and `resetUntypedCap` are identical across E1-H, K1, K2 and K0, but `finaliseCap` and `createObject` differ (A2a), so a result there bears on the crux only for the identical functions [Measured text, Inferred relevance]. It would not be A5 evidence: A5 needs K3.
- **Stop conditions to pre-register:** the SMMU registers are not reachable from user space; the kernel claims them (Blocked after three documented approaches is Fail by the plan); QEMU's SMMUv3 model cannot express the stream setup (not testable: Investigate).
- **Size:** a server of a few hundred lines (stream table, context descriptor, stage-1 tables (three levels, as step 1 built them), command queue with sync, event queue), a root-task variant, a verifier and a self-test. No estimate of time is given; there is no evidence to estimate from.
