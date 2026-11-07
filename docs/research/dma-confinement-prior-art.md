# Prior art: DMA confinement, user-level IOMMU management and safe teardown

- **Status:** Draft research note, 2026-11-07. It decides nothing and adds no criterion to the
  [spike plan](sel4-spike-plan.md).
- **Question:** what exists for confining DMA through a user-level SMMUv3 server with no seL4
  kernel change (the plan's K3), how does it fare against the four P5 tests, and where could Fyrkat
  invent something?
- **How it was made:** a `researcher` agent read the sources in one session and reported. I
  re-checked the seL4 source claims marked "re-checked" against the pinned commit
  `62e345c240a15671484530b4e6e069ce266c28d7`. Everything else is the agent's report and has **not**
  been re-read by me. Fetched pages were treated as data.

**Evidence marks.** "Read" means the agent read the document text. "Summary" means it saw the source
only through a page summariser, so quotes are unverified. "Re-checked" means I confirmed it.

## The short answer

1. **[Documented, re-checked]** The pinned seL4 tree has an SMMUv2 driver (`src/drivers/smmu/` holds
   `config.cmake` and `smmuv2.c`) and no SMMUv3 file anywhere.
2. **[Inferred]** Every working seL4 or hypervisor SMMUv3 design found puts the logic in the kernel or
   hypervisor. No published user-level SMMUv3 management on seL4 was found. This is a generalisation
   over the sources below and a negative search result, so it may be wrong.
3. **[Inferred]** Systems that handle revoke-while-mapped appear to do it with a kernel-held pin or a
   kernel-owned mapping. The Fuchsia evidence is a summary only. seL4 has no such hook, and the spike
   policy forbids adding one.
4. **[Inferred]** So revoke-while-mapped is the hard P5 test under K3, and the least-explored one.

## Existing approaches

| Approach | What it does | Source and mark | Limit against P5 |
|---|---|---|---|
| Arm SMMUv3 architecture (IHI 0070 D.a) | STE `Config=0b000` aborts and reports to the device. Updating an STE or context descriptor is: write V=0, DSB, `CMD_CFGI_*`, `CMD_SYNC`, wait. Events for terminated transactions need not be visible before a `CMD_SYNC`. Translated ATS traffic can bypass unless `ATSCHK` and `STE.EATS` restrict it | Arm document, §3.21.3, §3.9.1.2, §4.6.3. Read | Gives the command order and no revocation story |
| QEMU 11.1.3 SMMUv3 model | One machine-wide SMMU. Stage 1 by default. Caches STE/CD and IOTLB entries and flushes on CFGI and TLBI. Commands complete inside the MMIO write. Aborted streams record no event | `hw/arm/smmuv3.c`, `smmu-common.c`. Read | Cannot show completion latency, so a missing `CMD_SYNC` may pass. Stall and PRI are not implemented |
| QEMU `edu` device | Ignores DMA return values. Clamps the DMA address to 28 bits by default. Starts DMA from a timer 100 ms after the trigger write | `hw/misc/edu.c`. Read | Faults must be seen through the event queue, traces or unchanged target memory |
| seL4 17.0.0 SMMUv2 | `finaliseCap` for the VSpace capability calls `smmu_cb_delete_vspace`. TLB invalidation paths call the SMMU invalidations | Pinned source. Read, partly re-checked | In-kernel. A Class 3 hook by the plan |
| Horizon Robotics SMMUv3 for seL4 (Summit 2023) | In-kernel SMMUv3 driver with new `seL4_ARMSID` and `seL4_ARMCB` capabilities and a field added to the PUD capability. Verified on an FVP model only. No code found | `sel4.systems/Summit/2023/slides/day2-12-mao.pdf`. Read | In-kernel. Revoke-while-mapped and driver-kill not described. The slides say "without new kernel object and cap" and then add both |
| sDDF, LionsOS, Microkit | IOMMU support is future work in the Summit 2024 and 2025 slides. The LionsOS paper says the whole region "must be mapped to the device by the IOMMU" | arXiv 2501.06234 §4.1.3, Summit slides. Read | Static mappings only. The four tests are unaddressed |
| Fuchsia BTI, PMT, quarantine | A pinned memory token keeps pages alive. Releasing it without unpin quarantines the pages until `zx_bti_release_quarantine` | `fuchsia.dev` reference pages (`bus_transaction_initiator`, `zx_bti_pin`, `zx_pmt_unpin`, `zx_bti_release_quarantine`). **Summary only** | Kernel-enforced. Revoke while pinned is impossible by design |
| Genode (release 23.11) | The platform driver manages Intel DMA-remapping tables in user space, one domain per session, charged to the session quota | `genode.org/documentation/release-notes/23.11`. **Summary only** | Intel only. Client death and invalidation are not described |
| NOVA | In-kernel SMMUv3 driver with a documented STE state machine: a 512-bit STE "cannot be configured atomically" | FOSDEM 2026 slides. Read, one source | In-kernel |
| Linux iommufd and VFIO | After `iommufd_device_detach` the device returns to blocked DMA translation | `docs.kernel.org/userspace-api/iommufd.html` and `docs.kernel.org/driver-api/vfio.html`. **Summary only** | Nothing on reset-versus-unmap order or in-flight DMA |
| SeKVM / KCore (IEEE S&P 2021) | A verified EL2 hypervisor owns the SMMU and its page tables. The proofs cover the SMMU page-table and hypercall layers | Columbia paper. Read | In the hypervisor. Whether IOTLB invalidation is verified could not be told |
| Markuze et al. (ASPLOS 2016) and Thunderclap (NDSS 2019, abstract only) | Deferred invalidation leaves a window in which an unmapped, reused buffer is still reachable. Shadow buffers are the fix | `cs.tau.ac.il/~mad/publications/asplos2016-iommu.pdf`. Read. Thunderclap: summary only | Describes the hazard P5 tests for |
| seL4 verified-configurations page | States that no verified configuration accounts for address translation for devices | `docs.sel4.systems/projects/sel4/verified-configurations.html`. **Summary only** | Suggests DMA confinement carries no proof coverage. Re-read it before relying on it |

**Not investigated:** Hubris, Theseus, Redox, CHERI revocation, Hafnium and pKVM SMMUv3, PCIe
function-level reset in a primary source, L4Re (`Dma_space`, `L4::Iommu::bind`: search snippets only, not read), and any seL4 mailing-list or
GitHub SMMUv3 thread. The UNSW sDDF IOMMU project page returned 404.

## What this means for the four P5 tests

| Test | Under K3 | Rating |
|---|---|---|
| Negative: DMA outside the mapping faults | The server sets the STE and tables. `edu` ignores errors, so the check is "target memory unchanged" plus an event or trace | [Inferred] Feasible |
| Cooperative teardown, then reuse | The server aborts the stream, issues CFGI and SYNC, and only then releases the frame | [Inferred] Feasible. QEMU will not expose a missing SYNC |
| Revoke while mapped | The kernel reclaims memory without telling the device side. The agent read `cteRevoke` as finalising children with no device notification | [Inferred] **The crux.** The agent found no seL4 statement of it |
| Driver killed during DMA | Deleting the driver's TCB does not touch the SMMU configuration | [Inferred] Feasible if frames are not owned by the driver |

## Opportunities for invention

All are user space only and respect the K3 constraint. Each is a hypothesis with a falsifiable
experiment. None is authorized, and each belongs to the A5 design, not to S1 Stage A part 1.

**O1. Revoke canary.**
- *Limitation:* no kernel notification when DMA memory is revoked.
- *Prior art:* none found.
- *Mechanism:* allocate a canary endpoint from the same untyped as the DMA frames, with a helper
  thread blocked in `Recv` on it. Revoking the untyped finalises the last endpoint capability, which
  calls `cancelAllIPC` [re-checked]. The helper restarts, re-executes `Recv`, takes a capability
  fault, and its fault handler (the SMMU server) sets the stream to abort and issues CFGI and SYNC.
- *Alternatives:* poll frame addresses; a lease with a sweep; making the SMMU server the only holder
  of the DMA untyped.
- *Benefit:* narrows the window when the revoker is not hostile. It does **not** work without
  trusting the revoker: a root task that holds the helper's or server's TCB, CSpace or priority
  control can suspend the helper first, so finalisation wakes nobody, and then revoke silently.
- *Conditions for the one-core prediction:* the helper's priority is strictly above every thread
  that can retype the untyped or its ancestors, and the helper's TCB and CNode do not come from the
  untyped being revoked. The agent's review of the kernel path found it sound under these conditions
  in non-MCS [Inferred]. Order matters: `cteRevoke` finalises the newest object first, so the canary
  is finalised before or after the frames depending on retype order. Memory is not reused inside the
  revoke itself, and reuse needs a later retype.
- *Risks:* **K3 runs on 4 vCPUs, where O1 makes no prediction**, and A5-arm fails on a single
  observed DMA into reclaimed memory. So O1 may reduce the window and cannot, on its own, make
  A5-arm pass on K2. It adds a trusted helper, depends on kernel ordering that is outside the proofs
  for this configuration, and the MCS behaviour was not read.
- *Experiment:* arm an `edu` DMA for 100 ms, revoke the untyped inside that window, retype at once
  and write a sentinel. **Positive control:** a run with the canary disabled must show corruption
  within the window, or an intact sentinel means nothing (the DMA may never have landed, for example
  through the 28-bit address clamp). The prediction on 1 vCPU with the conditions above is an intact
  sentinel in 1,000 of 1,000 runs. Any corrupted sentinel falsifies it. On 4 vCPUs the failure rate
  is measured and no prediction is made.
- *Marks:* [Inferred] on one core, [Speculative] under MCS.

**O2. Fail-closed default with a bounded lease.**
- *Limitation:* unbounded exposure after an undetected revoke.
- *Mechanism:* streams rest at `Config=0b000`. A mapping is enabled for a lease of T ms and then
  re-validated by a capability check.
- *Benefit:* the exposure is bounded by T plus the service time, and it is measurable.
- *Risks:* re-enabling costs performance, and the lease protects nothing against a malicious root
  task. **It cannot pass revoke-while-mapped**: a bounded window still allows DMA into reclaimed
  memory, which is an A5-arm Fail clause. Streams resting at `Config=0b000` also record no event, and
  the plan wants a fault "reported". O2 reduces exposure and does not meet the test.
- *Experiment:* with T = 10 ms, revoke at random offsets and record how long a freed frame stays
  reachable. Falsified if any frame is reachable longer than T plus the measured service time.

**O3. User-level quarantine.**
- *Limitation:* the driver-killed test.
- *Prior art:* Fuchsia PMT quarantine (summary only) and ASPLOS 2016 shadow buffers.
- *Mechanism:* DMA frames sit in the SMMU server's CSpace, allocated from a pool untyped that the
  driver never holds. Killing the driver cannot free them. The server reuses a frame only after the
  stream is aborted and CFGI and SYNC have completed.
- *Risks:* pool exhaustion if a device never quiesces. The `edu` setup has no function-level reset
  step to model.
- *Experiment:* arm `edu` DMA and kill the driver mid-flight. The sentinel must be intact, and the
  frame must not be reallocated before the server finishes. Falsified if the kernel frees any frame
  before the server releases it.
- *Note:* the root task still holds the parent capability and can revoke. The plan already lists the
  root task as a trusted component, and O1 addresses the case where it does.

**O4. Mutation testing of the SMMU server.**
- *Limitation:* an emulator may make the tests too weak to mean anything.
- *Mechanism:* run each P5 test against deliberately broken servers: no TLBI, no CFGI, no SYNC,
  SMMUEN set before `GBPA.ABORT=1`.
- *Benefit:* shows the tests have power, which the plan requires ("a required test that did not
  exercise the code the property rests on" is class D).
- *Risks:* QEMU completes commands inside the MMIO write, so a missing SYNC may pass, and ordering
  can never be evidenced there.
- *Experiment:* every mutant must fail at least one P5 test. **One surviving mutant for a mandatory
  step is already a finding**, not a partial success: it marks the test as unable to see that step,
  and the result is reported. The experiment is falsified in its aim if the mutants that QEMU should
  expose (no CFGI, no TLBI, SMMUEN set before abort) all pass.

## Evidence summary

- **[Documented, re-checked]** No SMMUv3 in the pinned seL4 tree. Endpoint finalisation calls
  `cancelAllIPC`. The SMMUv2 hooks the plan cites.
- **[Documented, read by the agent]** The Arm and QEMU facts, the Horizon, LionsOS and Summit slides,
  the ASPLOS and SeKVM papers, and the NOVA slides.
- **Secondhand (summary or snippet only):** Fuchsia, Genode, iommufd and VFIO, L4Re, Thunderclap, and
  the verified-configurations page scope statement.
- **[Inferred]** The seL4 kernel gives no device notification on revoke. A priority-ordered
  single-core canary closes the window. QEMU's synchronous SYNC hides ordering bugs. The Horizon
  design is incomplete for revoke-while-mapped.
- **[Speculative]** O1 under MCS. `edu` placed behind the SMMU on `virt`: nobody has run it.

## Consequence for the spike

A5-arm can pass only through K3, and revoke-while-mapped is the test most likely to decide it.
**Open interpretation (the owner's to settle before A5 runs):** the plan makes a required test that "did
not exercise the code the property rests on" a class D cell. QEMU completes SMMU commands inside the
MMIO write, so a server that omits `CMD_SYNC` could pass every P5 test [Documented: `smmuv3.c`, read
and not run. The consequence is Inferred]. If that counts as "did not exercise", the K3 cell for P5 is
class D on this host and A2 is a Fail whatever the design. The decision package recommends no
loosening: under the plan as written an untestable mandatory step leaves A5-arm at Investigate, which
becomes Fail at the end of the spike. A looser reading is a proposed Amendment (P5) for the A5 design
gate. The
A5 design gate should therefore settle three things before any code: how the root task's revoke
power is handled (trusted and constrained, or detected by O1), who owns the DMA pool (O3), and how
the tests are shown to have power (O4). If K3 cannot meet the tests, A5-arm is a Fail and the
hypothesis is falsified (rule 5). That is the plan working as designed.
