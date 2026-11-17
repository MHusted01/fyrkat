# DMA ownership: requirements, options, and what the evidence supports

- **Status:** research note by the agent, 2026-11-11. It decides nothing and changes no ADR. A **proposal** for anything not yet measured. Not a description of existing behaviour: no kernel exists in this project. Labels as in AGENTS.md.
- **Evidence it rests on:** [A5 step 1](../../spikes/sel4-feasibility/results/A5-step1.md), [A5 step 2](../../spikes/sel4-feasibility/results/A5-step2.md), [K3](../../spikes/sel4-feasibility/results/K3.md) (design, controls and mutants), and the earlier [prior-art note](dma-confinement-prior-art.md). Everything measured is **one emulated SMMUv3 model, one device model, TCG**.

## 1. The problem, as invariants

A device that can DMA is a second CPU that is outside the kernel's capability system. For a capability OS the question is which authority graph keeps it from reading or writing memory it should not. Four invariants, in order of how often systems break them:

- **D1 Confinement.** A device reaches only memory mapped for it.
- **D2 No stale reach.** No memory is handed to a new owner while any translation, cached or in a table, still names it. The device-side state (table entry, TLB, in-flight transfer) must be gone *and observed gone* before reuse.
- **D3 Reclaim is not blocked by the untrusted.** The system can always take memory back from a driver or client that is dead, stuck or hostile.
- **D4 Authority and mapping stay in step.** There is no way to hold mapping authority over memory without the authority that makes it yours, and none for the memory's reclaimer to be unaware of the mapping.

seL4 gives D3 and the CPU side of D4 (revoke is unilateral and immediate) and nothing for D1 to D2 on the device side: *the kernel does not know what an SMMU maps* ([A5 step 2](../../spikes/sel4-feasibility/results/A5-step2.md): [Measured] a translation survived the revocation of its frame, the kernel reused the page at once, and the device read and overwrote the new contents with no fault).

## 2. The options, compared on the same terms

| | 1. DMA pool, ancestors held by the server only | 2. Shadow (bounce) buffers | 3. Kernel binds mapping to capability | 4. Kernel defers reuse (pin) | 5. Hybrid: 1 for pool-allocated buffers, 2 for foreign memory |
|---|---|---|---|---|---|
| Kernel change | none | none | yes: hooks in finalise, unmap, TLB paths (Class 3) | yes: a check on the retype and reset path, a count (Class 3) | none |
| D1, D2 | by the server's rule (clear, invalidate, sync, then revoke) | by construction: mapped pages are never reclaimed in operation | by the kernel, for any authority graph | by the pin holder's rule; the kernel enforces *reuse* | as 1 and 2 |
| D3 | yes: the server revokes the page's untyped | yes | yes | **only if pins are bounded**: a pin holder that never releases holds the memory | yes |
| Who may hold ancestors of DMA memory | only the server (checked by the seed table) | only the server | anyone | anyone | only the server |
| Zero-copy from arbitrary client memory | no | no (copy) | yes | yes | for pool buffers |
| Trusted base added | server (unverified user code), initial task, elfloader | as 1 | unverified kernel code, a wait inside revoke | small kernel change that needs proof work, plus the server | as 1 |
| Cost per operation (structural, K3) | alloc: 0 SMMU commands. free: 2 commands, 1 sync, 1 revoke | copy per transfer; none to unmap | not measured | not measured | as 1 and 2 |
| Needs a new proof | no (but it is outside the proofs) | no | yes | yes | no |

[Inferred] 1 and 2 are the only designs available without a kernel change; 5 is what a real driver framework wants (allocate I/O buffers from the pool, copy only at the edge). 3 is the only one that is correct for *any* distribution of authority, which is the property that matters most when subsystems are written by different people. 4 keeps revoke unilateral and makes only reuse wait; it is the smallest kernel change that closes the hole and is, as far as the project's notes show, new for seL4 [Speculative].

## 3. What K3 adds to the evidence

All [Measured] under QEMU 11.1.3 TCG, on an unmodified kernel (K2 debug and K2R release, both non-hypervisor, 4 vCPUs), in the agent's recording of 2026-11-11; the record is [K3](../../spikes/sel4-feasibility/results/K3.md) and its evidence passes `verify-evidence.py` (174 of 174 checks, 191 of 191 corruptions caught). It is **the agent's measurement, not an accepted outcome**, and its limits are in K3 sections 9 to 11.

- **Option 1 held against hostile clients, in separate protection domains, from the moment the server enabled the SMMU (K3 section 2: the interval before it was not tested).** With the pool's untyped moved into the server's CSpace (so no ancestor exists elsewhere) and clients holding only copies of frame capabilities, a client's delete, revoke, unmap, probing of every slot, or death freed nothing; every device access outside a mapping, at any physical address tried (other clients', the memory owner's, the SMMU's own tables and queues), was refused with a fault record for the right stream; after a free or a death the reused page was untouched; a transfer running when its driver was killed faulted. 3 of 3 boots on each kernel.
- **The naive arrangement fails, across domains.** The same server accepting a donated frame (the donor keeps the parent) reproduced the failure of A5 step 2: after the memory manager reclaimed the donor's memory and gave it to another client, the first client's device read all 16 words of that client's secret and overwrote all 16, with no fault. So the invariant that matters is **who holds an ancestor of DMA-reachable memory**. [Inferred: that is a property of the capability graph, which the seed table printed by the trusted root task shows; it confines a device only once the SMMU is enabled with the server's tables (section 4, item 1).]
- **The tests can fail.** Six deliberate server bugs (skip the invalidation; reclaim while mapped; no owner check; no teardown on death; one address space for two streams; one ASID for two streams) were each detected on both kernels, at the sub-checks the design predicted for them plus the later ones that share their code.
- **Cost, structurally** (counts, not timings; TCG timings mean nothing): a new mapping needs 0 SMMU commands; a free needs 2 commands, 1 sync and 1 revoke per page. The batching suggestion of section 4 is therefore about bulk teardown, not the fast path.
- **What the evidence does not support:** anything about hardware (in-flight DMA, invalidation latency, the quiesce step); a hostile initial task (it holds the server's CNode, and it maps the SMMU registers itself, so it is wholly in the trusted base); the death of a client whose CNode and VSpace are destroyed; a client killed while blocked in a call; more than two streams; the interval before the server enables the SMMU. Option 5's bounce path and options 3 and 4 were not built.

## 4. Recommendation

**Build option 5 as Fyrkat's baseline DMA architecture, and run one falsifiable experiment on option 4 before deciding whether the kernel should take part.**

1. **Baseline (no kernel change):** a DMA server owns the IOMMU and a pool whose ancestors it alone holds; each device gets its own address space (own tables, own ASID) bound to its stream; clients receive frame copies and I/O addresses; buffers from the pool are zero-copy, foreign memory is copied. The pool is a boot-time carve of RAM untypeds that are *moved* (not copied) into the server's CSpace, so no ancestor exists elsewhere; the initial task, which holds the server's CNode, is the only party that could undo it, which is why it is wholly in the trusted base. **Precondition (found in K3's fourth review, K3 10d M1):** bus mastering of a device must stay off, or the SMMU's global bypass must be set to abort, until the server has enabled the SMMU with the stream table; K3 did not enforce this order: in its runs the test clients waited for the conductor's first step, which is sent after the server has enabled the SMMU (K3 section 2), and a hostile client would not wait [Measured: an SMMU at reset lets the device copy untranslated, A5 step 0; Inferred: the fix]. [Measured for hostile clients and a hostile memory owner in K3, from the moment the SMMU is enabled; Inferred for everything else.]
2. **Driver death:** a supervisor (the initial task today) tells the server a client died; the server tears down all its pages in the order clear, invalidate, sync, revoke. The server needs a *quiesce* step for real hardware (bus-master disable or function reset) before freeing; QEMU cannot test it. [Inferred: from Arm IHI 0070's invalidation commands and `CMD_SYNC`, with no section pinned yet, and from the general need of IOMMUs for a quiesce step.]
3. **Batching and scale:** per-page invalidation is 2 commands and a sync; for bulk teardown use `CMD_TLBI_NH_ASID` for the address space and one sync; use a two-level stream table beyond 64 streams; the single-threaded server is the serialization point, so one server per SMMU and per-device sub-domains are the scale-out path. [Inferred; not measured.]
4. **Experiment E-pin (proposal; not authorized, Class 3 under the plan's Kernel modification policy, outside S1's gates):** in a *copy* of the pinned seL4 (never the reference kernel), add an `Untyped_Pin`/`Unpin` pair and make a retype or reset of a pinned untyped fail with a distinct error while all capabilities are still revoked. Falsifier: the control N of K3, rebuilt with the server pinning donated memory, must come out REFUSED where it came out REACHED, and a pin holder that dies must be handled by the supervisor unpinning on its behalf. Success makes zero-copy DMA from arbitrary client memory safe without trusting the memory manager. Failure modes to look for: a leak when a pin holder dies, a hole in the kernel's untyped free-index logic, and the proof burden. It needs the owner's decision first (a new ADR and a plan amendment are required by the plan).

## 5. What to build next, and what to leave experimental

- **Reusable, kernel-independent, worth building as product code once the owner approves a new crate (a `Cargo.toml` change is a gate):** an SMMUv3 *format* library: stream-table-entry, context-descriptor and page-descriptor encoders, command builders, event parsers, as pure `no_std` functions with host unit tests and a cross-check against QEMU's own definitions. It has no OS dependency, serves any kernel Fyrkat picks, and removes the largest unsafe-free part of the spike's driver from the trusted base's review burden.
- **Reusable once the kernel is chosen:** the pool allocator's state machine (free, mapped, teardown) with its ownership rule, as a model that can be exhaustively checked in small sizes.
- **Stays experimental:** the spike's server, root task, scripts and checker. They encode one kernel's capability model and one emulator's behaviour.
- **Not to be built yet:** a general DMA framework, IOMMU abstraction layers for x86-64 (VT-d) or other Arm parts, ATS/PRI/stall support. No requirement demonstrates them.

## 6. Open questions, in order of value

1. Does the unmodified kernel's behaviour in K3 hold on real hardware with a real SMMU (cache behaviour, in-flight DMA, quiesce)? One board with an SMMUv3 would answer it; buying hardware is a gate.
2. E-pin (section 4).
3. Do the pool-only restriction and the copy at the edge cost enough in a real driver (network, storage) to matter? Needs a driver and a workload, neither of which exists.
4. How should the supervisor learn of a client's death (fault endpoint, a notification on TCB destruction, a lease)? K3 used the initial task; a real system needs a decision.
