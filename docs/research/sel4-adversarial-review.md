# Adversarial review of ADR 0001 Part B

Conducted 2026-11-07 at the project owner's request. It reviewed the original Part B, which
proposed building a new Rust kernel instead of adopting seL4. The result led the owner to
withdraw Part B, as recorded in [ADR 0001](../adr/0001-kernel-architecture.md) and
[ADR 0004](../adr/0004-kernel-foundation.md).

## Status of this document

- **Independence is partial.** The reviewer was a separate Opus session with no access to
  the author's reasoning, but it is the same kind of model as the author. It is not a
  substitute for review by a human expert.
- **The review is model output.** Verification results are listed below, and unconfirmed
  claims must not be treated as facts.
- This records the reviewer's position, not an accepted project position.

## Verification of the review

Checked by the author directly against sources on 2026-11-07.

**Confirmed:**

- seL4 `CHANGES.md`: an x86 crash from any thread, including verified configurations; a
  guest-triggered halt on Arm with hypervisor support; storage channels; a `restore_vmx()`
  VM escape on unverified VT-x; stale VT-d and SMMU state that left devices with DMA access
  to reallocated memory; and "HYP+SMP is not a verified configuration and is not thoroughly
  tested" (13.0.0).
- Four breaking seL4 releases between 2025-11-25 and 2026-10-30.
- The GPL syscall note in seL4's `LICENSE.md`.
- rust-sel4 supports seL4 17.0.0 and provides root task runtimes, a CapDL initializer and
  a kernel loader. Microkit targets static systems. libvmm x86 guests are single VCPU.
- seL4's tree contains an SMMUv2 driver only. Issue 1613, generic AArch64 support, is open.
- Biggs: 96% includes 38% that still violate confidentiality or integrity, and 57% reach
  low severity.
- Atmosphere's trust base, its prohibition of fine-grained revocation, and about 14 months
  of verified development across clean-slate rewrites.
- HongMeng's figures: 2x slower and 35% more memory from double bookkeeping, page faults
  3.4x slower from capabilities, over 7 years of work, and tens of millions of devices.
  These are the authors' own claims.
- TickTock: six isolation-breaking bugs, and 3.5K lines of annotations for 22K of Rust.
- Sculpt on seL4 lacks ACPI suspend and CPU power steering (as of its September 2025 slides).
- AArch64 security proofs are listed as complete on the seL4 roadmap (24 August 2026), so
  `CAVEATS.md` appears stale on this point.

**Not confirmed:**

- The reviewer stated that seL4 17.0.0 credits Anthropic with reporting issues. Neither
  "Anthropic" nor "Claude" appears in `CHANGES.md`. Disregard this, and the reviewer's
  suggestion that AI auditing may close the maturity gap, which rested on it.
- The multikernel verification date of Q3 2028 was not confirmed.
- The roadmap's silence on SMP verification is not fully settled: a 2022 Summit deck names
  SMP verification as an eventual goal.

**Added by the author after the review:**

- seL4's SMMUv2-only support and QEMU `virt`'s SMMUv3-only support do not overlap, so DMA
  isolation on Fyrkat's AArch64 target has no existing kernel path.
- Verified AArch64 needs EL2, which HVF refuses on the development machine. Unverified EL1
  builds may run under HVF, but this is untested.
- No verified configuration exists for `qemu-arm-virt`, so no QEMU run is ever verified.
- rust-sel4 pins `nightly-2026-10-28`, which may conflict with the stable toolchain policy.

## The reviewer's report

The report follows with minor formatting changes. Its evidence labels are the reviewer's.

**Recommendation:** do not accept Part B as written. Use seL4 as the kernel for the first
system (pinned release, a dynamic Rust root server, not Microkit) behind a narrow runtime
boundary, and re-decide on an own kernel at a measured gate.

**Confidence:** about 75% that this beats building now, about 90% that Part B's reasoning
is unsound, and only about 40% that seL4 remains the kernel for decades.

**Core flaw:** the ADR tests the real seL4 against an imagined verified Fyrkat kernel.
Compared like for like, its main objections disappear.

### 1. Strongest case for seL4

- **The objections apply equally to Fyrkat.** The FAQ describes a big-lock SMP kernel for
  cores sharing a cache, with a multikernel beyond that [Documented]. Part B proposed the
  same structure. "No SMP or IOMMU proofs" is also true of a new kernel. A proof base you
  cannot extend still beats having no proofs. [Inferred]
- **The kernel keeps improving without you.** Proofs are maintained on every kernel commit
  [Documented: whitepaper]. DARPA PROVERS funds the port of the MCS proof to 64-bit Arm
  [Documented: seL4 news]. A slow one-person kernel gets none of this. [Inferred]
- **Rust-first survives** through rust-sel4. [Documented]
- **A dynamic desktop on seL4 exists, in preliminary form.** Sculpt ran on seL4 with Intel
  graphics, WiFi, USB and a browser [Documented: Sculpt slides]. It sat on a mature
  framework, so it does not show one person could do the same. [Inferred]
- **Effort goes where Fyrkat differs:** services, driver isolation and compatibility, not
  re-earning kernel maturity. [Inferred]

### 2. Is unverified SMP and IOMMU riskier than a new kernel?

No, but Part B's maturity concession is too generous in specific areas.

- Immature paths are real: HYP+SMP, `restore_vmx()`, and VT-d invalidation. [Documented]
- Verified configurations also had serious bugs, all outside proof scope. The cause is an
  assumption: that hardware has no more registers than the model captures. [Documented]
- What survives is not quantifiable. Under a big lock, capability, untyped and IPC logic
  stay largely the sequential code, so value survives informally. It is lost for cross-core
  interactions, for strong non-interference, and wherever DMA exists. [Inferred]
- New-kernel base rates are thin. Verification of Rust-based Tock found six isolation
  bugs [Documented: TickTock]. Zircon has CVE-2022-0882, and Linux's first Rust CVE was an
  `unsafe` race [Documented: summaries only]. No Redox audit data was found.
- By layer: seL4 is far ahead on the capability core, moderately ahead on SMP, and only
  thinly ahead on IOMMU and VT-x. [Inferred]
- The 17.0.0 register, TLB and cache bugs are not memory-safety bugs, so Rust would not
  prevent that class. [Inferred]

### 3. Comparison

| | seL4 adopted | New Rust kernel |
|---|---|---|
| Assurance | Proven sequential core; SMP, IOMMU, VT-x unproven | None for years; memory safety outside `unsafe` |
| Performance | Fastest published IPC; desktop unproven | Unknown |
| Hardware | Compile-time platforms; SMMUv2 only | Nothing exists; UEFI/ACPI-native design possible |
| Driver isolation | User-mode drivers, sDDF; VT-d lacks interrupt remapping | Same design, unbuilt |
| Maintainability | Four breaking releases in 12 months; GPL fork possible | Full control; bus factor of one |
| Desktop | Sculpt lacks suspend and power steering; libvmm not production-ready | All open |
| First useful system | Rust services plus Linux VM on AArch64 [Speculative] | Booting IPC demo [Speculative] |
| If slow | Artefact stays secure and current | Kernel ages unaudited |

No evidence was found on heterogeneous-core scheduling for either option.

### 4. seL4 as a temporary or permanent foundation

Yes, with limits. "seL4 now, own kernel later if justified" is the right framing, and it
produces workload evidence that a kernel ABI should be designed from. [Inferred]

- Avoid Microkit as the core. Use a rust-sel4 root task. [Documented]
- MIT and Apache user space is unaffected by the GPL. Distributed kernel patches are
  GPL-2.0. A kernel translated from seL4's C with AI help risks being a derivative work.
  [Inferred; not legal advice]
- Rust-first costs a C kernel in the TCB, C and CMake tooling, and writing kernel
  extensions in C with no proof. [Inferred]
- Verification is not on the roadmap for Fyrkat's configuration. [Documented]
- Verified AArch64 runs at EL2, which HVF refuses on the owner's Mac. [Documented, Measured]

### 5. Atmosphere and Verus

They support "a verification-expert team can do this". They do not support "this project
can".

- **Proved:** refinement to a high-level specification, memory safety and leak freedom.
  Non-interference is shown for one three-container scenario. [Documented]
- **Trusted:** Verus, Z3, rustc, `core`, about 700 lines of axioms, setter functions, 172
  lines of assembly, about 3,000 lines of trusted Rust including 465 lines of IOMMU
  configuration, the boot loader, CPU and firmware. [Documented]
- **Weak transfer:** it prohibits fine-grained revocation, runs syscalls under one lock with
  interrupts disabled, and its hardware layer is x86-specific. [Documented, Inferred]
- **Team gap:** clean-slate rewrites and about 14 months on verified code, by authors with
  prior OS research. AI-assisted proof might narrow this. [Speculative]
- **Better use:** targeted verification looks reachable, as TickTock suggests, and Verus or
  Flux can be applied to Fyrkat's Rust servers under seL4. [Inferred]

### 6. Switching costs and optionality

**Expensive commitments:** untyped retype and memory donation, CSpace layout, badge
semantics, MCS versus non-MCS, explicit page-table objects, VCPU and fault-endpoint
protocols, capDL as a composition format, and Microkit's static model. [Inferred]

**Preserving optionality:**

- A `fyrkat-rt` crate as the only caller of seL4 APIs.
- Untyped, CNodes and badges confined to the root server.
- Stability promises at service protocols, never the kernel ABI.
- Negative isolation tests written against Fyrkat protocols.
- A host-side mock runtime.
- If an own kernel comes, a seL4-subset ABI in Rust first, with sel4test as a conformance
  suite.

**False economy:** a portable capability model spanning hypothetical kernels, abstracting
the VMM or root server, a second kernel "just in case", and avoiding seL4-specific
performance work. [Inferred]

### 7. Evidence gaps and bias

- **Cherry-picked:** "not meant to scale to many cores" drops "where instead a multikernel
  is the right approach".
- **Overstated:** the 96% figure, as confirmed above, and its threat model is one
  hypothetical bug-free application, not a desktop.
- **Overstated:** "verified multicore kernels point to a big lock or multikernel" is a 2016
  statement by seL4's authors, while Atmosphere cites CertiKOS's fine-grained locking work.
- **Omitted caveats:** Atmosphere's page mapping is "not strictly equivalent", and its
  figures were measured under KVM.
- **Structural bias:** reconsideration criterion 1 demanded proofs Fyrkat would not have
  either. The research table rated new-kernel multicore "Open" and seL4 "Limited" for the
  same design. The limits section flagged pro-microkernel bias but not bias toward the
  author's own conclusion.
- **Material omissions:** HongMeng, Sculpt, the seL4 changelog and ecosystem, Verus's trust
  base, SMMU coverage, and any cost estimate.

### 8. Recommendation

Replace Part B with seL4 for the first system, a Rust root server, and a re-decision gate
that opens only on measured evidence: unfixable overhead on a representative workload,
measured lock contention at desktop core counts, kernel fork pressure, or ABI churn.

**Strongest argument against this:** kernel interfaces shape everything, so "own kernel
later" may be fiction after years on seL4. HongMeng suggests general-purpose performance may
need changes to core seL4-style mechanisms. seL4's focus is largely embedded and static, so
Fyrkat could end up carrying a C fork in unverified code, with neither proofs nor Rust. A
15K-line kernel is small next to the whole system.

**Evidence that would change the answer:** a demonstrated Verus proof of seL4-style
derivation and revocation at low cost, upstream rejecting needed changes, a root-server
spike needing substantial kernel patches, or measured overhead beyond tolerance.

**Cheapest experiment:** the spike now specified in
[the spike plan](sel4-spike-plan.md).

## Sources

The reviewer consulted the documents above, plus these not cited elsewhere:

- Chen et al., "Microkernel Goes General: Performance and Compatibility in the HongMeng
  Production Microkernel", OSDI 2024.
- Rindisbacher et al., "TickTock: Verified Isolation in a Production Embedded OS", SOSP 2025.
- Böttcher, "Sculpt OS: a dynamic general-purpose OS powered by Genode on seL4", slides,
  September 2025.
- seL4 `CHANGES.md`: <https://github.com/seL4/seL4/blob/master/CHANGES.md>
- seL4 `LICENSE.md`: <https://github.com/seL4/seL4/blob/master/LICENSE.md>
- seL4 roadmap: <https://sel4.systems/roadmap.html>
- rust-sel4: <https://github.com/seL4/rust-sel4>
- Microkit: <https://github.com/seL4/microkit>
- libvmm: <https://github.com/au-ts/libvmm>
