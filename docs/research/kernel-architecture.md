# Kernel architecture comparison

Research date: 2026-11-07. This document supports [ADR 0001](../adr/0001-kernel-architecture.md).
It gathers evidence and does not decide anything. It was corrected on 2026-11-07 after an
[adversarial review](sel4-adversarial-review.md) found errors, which are noted in place. Evidence labels are defined in the
[ADR README](../adr/README.md). Citations in brackets resolve to [Sources](#sources).

## Limits of this research

Read before relying on any conclusion below.

- **Read as full text:** the papers and seL4 documents marked "full text" in Sources.
  They were searched for specific claims, not read end to end.
- **Seen only through search summaries:** MINIX 3, Capsicum, DriverKit and LeVasseur.
  Their numbers need checking against the originals before anyone builds on them.
- **Not researched from primary sources:** Linux and FreeBSD kernel internals, the
  NT kernel, and any measurement of a capability microkernel running a full desktop.
- **Bias:** the two most-cited pro-microkernel sources [biggs][l4] come from the group
  that built seL4. The study in [biggs] maps CVEs onto a hypothetical design.
- **Author bias:** the first version of this document leaned toward building a new kernel,
  and an adversarial review found that its evidence was selected accordingly. Read it
  alongside that review.

## Findings

### Isolation: hardware boundary or language boundary

Two different mechanisms are often treated as interchangeable.

**Hardware isolation** puts components in separate address spaces. **Language
isolation** keeps them in one address space and relies on Rust's type system.

- Asterinas reports a memory-safety TCB of 14.0% of its codebase, against 43.8% for
  Tock, 62.4% for Theseus and 66.1% for RedLeaf [asterinas p3]. [Documented]
- Asterinas reports performance comparable to Linux, with a mean normalized LMbench
  score of 1.08 and 1.17, 1.31 and 0.85 on Nginx, Redis and SQLite [asterinas p3].
  Its authors warn that this does not show it is better optimized, because it lacks
  some Linux features [asterinas §evaluation]. [Documented]
- RedLeaf states it must trust the Rust compiler and the unsafe code in Rust core
  libraries [redleaf, Protection model]. [Documented]
- Language safety prevents memory corruption, but it does not limit authority. In a
  single address space, a logic error in a safe component still runs with the
  authority of the whole kernel. [Inferred]
- Language isolation cannot contain code that is not safe Rust. That rules out
  reused drivers from other systems, which matters for GPUs (see below). [Inferred]
- None of the framekernel or language-OS passages reviewed addressed speculative
  side channels. This is an absence in what was searched, not a finding that they
  are unaffected. [Inferred]

### IPC and context-switch cost

- seL4 publishes IPC call latency of 419 cycles on a Cortex-A57 and 744 cycles on a
  Skylake i7, the latter "without meltdown mitigation" [sel4-perf]. [Documented]
- L4 kernels reached IPC 10 to 20% above a defined hardware limit [l4 p6]. [Documented]
- Atmosphere, written in Rust and verified, reports call/reply of 1,058 cycles against
  1,026 for seL4, and page mapping of 1,984 against 2,650 [atmo Table 3, p11].
  So a verified Rust kernel can approach seL4 on this path. [Documented]
- These are best-case same-core figures. Mitigations for speculative attacks raise the
  cost, and a real file operation may cross several servers. [Inferred]
- **No source reviewed shows a capability microkernel matching a monolithic kernel on
  a full desktop workload.** This is the largest open performance question. Two sources
  bear on it. Sculpt has run on seL4 in preliminary form [sculpt], and HongMeng runs on
  tens of millions of devices while reporting that capability-mediated page faults were
  3.4 times slower than Linux before it changed its design [hongmeng]. [Documented]

### Verification

| System | Executable size | Proof effort | Concurrency |
|---|---|---|---|
| seL4 | About 12,600 SLOC on AArch64 [sel4-faq] | 200,000 lines of proof in 2009 [sel4-wp p13]; 11 person-years plus 9 for tools, as cited by [atmo p1] | Verified configurations exclude SMP |
| Atmosphere | 6K lines of Rust [atmo p3] | 20.1K lines, ratio 3.32:1, under 2.5 person-years, of which 1.5 on verification [atmo p1, p3] | Big lock [atmo p2] |

**seL4 proof coverage is narrower than its reputation suggests.** [Documented]

- The proof covers the functional behaviour of the C code, and "does not cover machine
  code, compiler, linker, boot code, cache or TLB management" [sel4-caveats].
- The proof assumes DMA is off [sel4-faq]. No verified configuration covers an IOMMU
  or SMMU [sel4-verified][sel4-caveats].
- SMP exists but is unverified, and is "not expected to satisfy strong intransitive
  non-interference" [sel4-caveats].
- MCS on AArch64 is in progress, and the verified x64 configuration excludes VT-x and
  VT-d [sel4-caveats].

**Consequence:** a general-purpose desktop needs SMP and DMA isolation, and no verified
seL4 configuration has either. A desktop seL4 would be mature and well-engineered, but
would not be the proven artefact. [Inferred]

Rust and Verus appear to reduce the cost substantially, but Atmosphere is one small
kernel under a big lock, and its effort figures come from its own authors. Whether this
holds at larger scale is unknown. [Inferred]

### Multicore scalability

- Concurrency presents "huge challenges for verification", so a verified multicore
  kernel means "either a big kernel lock or a multikernel approach" [l4 p22]. This is a
  2016 design statement by seL4's authors, not a settled limit. Atmosphere cites CertiKOS's
  verification work on fine-grained locking [atmo §7]. [Documented]
- For a microkernel with short system calls, a big lock is reasonable "at least for a
  small number of cores sharing a last-level cache" [l4 p22]. [Documented]
- The seL4 FAQ says its SMP kernel is "not meant to scale to many cores, where instead a
  multikernel is the right approach" [sel4-faq]. An earlier version of this document cut
  the second half of that sentence, which misrepresented it. [Documented]
- A clustered multikernel combines a big lock within a cache domain with separate
  kernel instances across domains [l4 p22]. seL4 lists static multikernel verification
  on its roadmap [sel4-caveats]. [Documented]
- The Multikernel paper proposes three principles: explicit inter-core communication,
  hardware-neutral structure, and replicated rather than shared state [multikernel p5].
  It reports performance comparable to a conventional OS on the machines tested
  [multikernel p1]. [Documented]

This is the central tension: the structure that makes verification tractable limits
in-kernel parallelism, and general-purpose machines have many cores. Keeping system
calls short and kernel state partitioned preserves both paths. [Inferred]

### Drivers, fault containment and recovery

- seL4, Redox and QNX run drivers in user mode [sel4-faq][redox][qnx]. Apple moved in
  the same direction with DriverKit, stating that user-space drivers cannot compromise
  the security or stability of macOS [driverkit]. [Documented]
- Without an IOMMU, DMA-capable drivers "need to be trusted" [sel4-faq]. A user-mode
  driver without DMA isolation is not actually isolated. [Documented]
- MINIX 3 slides report transparent network driver recovery with mean recovery of about
  0.36 s, and 1% to 25% overhead depending on crash rate [herder]. Older MINIX figures
  put user-mode driver overhead at 6 to 9% [herder]. [Documented, summary only]
- Redox describes restart as something a driver failure "could" allow. The pages read
  do not say it is implemented [redox]. [Documented]
- Biggs et al. estimate that 96% of critical Linux CVEs would no longer be critical in
  a microkernel design, 40% would be eliminated with a verified microkernel, and 29%
  even with an unverified one [biggs p2]. The 96% includes 38% that still violate
  confidentiality or integrity, and 57% reach low severity [biggs p7]. The method is a
  hypothetical mapping onto one bug-free application, and the authors list threats to
  validity [biggs p4-5]. [Documented]

### GPU drivers and hardware compatibility

- AMD's Linux kernel driver is reported at over six million lines. Most of that is
  generated headers, and a 2025 count gives about 666,000 lines of actual code. Intel's
  i915 and Xe together were about 509,000 [phoronix]. [Documented, secondary source]
- A new OS cannot plausibly write and maintain this for many GPU families. [Inferred]
- Running unmodified drivers in a VM cost 3 to 8% on network workloads in 2004, and
  isolated driver faults [levasseur]. That result does not establish acceptable GPU
  performance, and no GPU-specific evidence was found. [Documented, summary only]
- The likely path is therefore driver VMs, which makes virtualization support a
  structural requirement rather than a late feature. [Inferred]

### Memory management and scheduling

- seL4 has no kernel heap. All kernel objects live in memory supplied by user level
  through untyped capabilities [sel4-faq]. This removes a class of kernel allocation
  failures and makes kernel memory an accountable resource. [Documented] It descends
  from the exokernel idea of moving resource management out of the kernel [exokernel].
  [Inferred]
- L4 experience led to replacing thread IDs with IPC endpoints, abandoning long IPC
  and timeouts, and moving kernel memory under user-level control [l4 p4, p8-10].
  [Documented]
- QNX uses message-driven priority inheritance to avoid priority inversion [qnx].
  [Documented] A general-purpose system with user-level servers will need a similar
  answer. [Inferred]
- Scheduling for heterogeneous cores was not researched in depth. It is open.

### Authority models in deployed systems

- Zircon: handles with per-handle rights, moved through channels, with process creation
  gated by job handles [zircon]. The pages read do not use the word "capability".
- Redox: capability-like file descriptors and per-process namespaces, partly described
  as work in progress [redox].
- Capsicum: retrofits a capability mode onto FreeBSD by denying access to global
  namespaces [capsicum]. It shows capabilities can be added to UNIX, and also how much
  ambient authority a UNIX design must then remove. [Inferred]
- seL4: capabilities to all kernel objects, with kernel memory itself capability-managed
  [sel4-faq].

## Qualitative comparison

All cells are engineering judgement. [Inferred] The "Capability microkernel (new)" column
describes a design that does not exist, so its entries are aspirations, not capabilities.

| Criterion | Monolithic (Rust) | Framekernel | Hybrid | Message-passing microkernel | Capability microkernel (new) | seL4 adopted | Multikernel |
|---|---|---|---|---|---|---|---|
| Privileged code size | Largest | Medium | Large | Small | Small | Smallest | Small per core |
| Isolation of services | Language only | Language only | Partial | Hardware | Hardware | Hardware | Hardware |
| Authority confinement | Weak | Weak | Weak | Medium | Strong | Strong | Depends on base |
| Cost per service call | Lowest | Lowest | Low | Higher | Higher | Higher, best known | Higher |
| Fault containment | Poor | Poor to medium | Partial | Strong | Strong | Strong | Strong |
| Reusing foreign drivers | In kernel, unsafe | Not contained | In kernel | Via VM | Via VM | Via VM | Via VM |
| Verification today | Infeasible at scale | Partial | Infeasible | Possible | Possible, unproven here | Proven, narrow configs | Research |
| Multicore path | Mature | Unknown | Mature | Varies | Same big-lock design as seL4, unbuilt | Big lock, then multikernel | Designed for it |
| Effort to first boot | Medium | Medium | High | Medium | Medium | Lowest | High |
| Effort to full system | Lower | Lower | High | High | High | High | Highest |
| Control over evolution | Full | Full | Full | Full | Full | Shared with upstream | Full |

## Unresolved disagreements

- **AArch64 confidentiality in seL4 (resolved).** `CAVEATS.md` says in progress, but the
  verified configurations page and the roadmap, dated 24 August 2026, say the security
  proofs are complete. `CAVEATS.md` appears to be stale.
- **Multikernel verification status.** `CAVEATS.md` says "initial work begun" and the FAQ
  says "in progress".
- **Microkernel overhead on real workloads.** Redox calls performance "comparable", with
  no supporting data on the pages read. No measurement was found.

## Sources

Accessed 2026-11-07.

- [asterinas] Peng et al., "Asterinas: A Linux ABI-Compatible, Rust-Based Framekernel OS
  with a Small and Sound TCB", USENIX ATC 2025. Full text.
  <https://www.usenix.org/system/files/atc25-peng-yuke.pdf>
- [atmo] Chen, Li, Zhang, Narayanan, Burtsev, "Atmosphere: Practical Verified Kernels
  with Rust and Verus", SOSP 2025. Full text.
  <https://mars-research.github.io/doc/2025-sosp-atmo.pdf>
- [biggs] Biggs, Lee, Heiser, "The Jury Is In: Monolithic OS Design Is Flawed", APSys
  2018. Full text. <https://www.trustworthy.systems/publications/full_text/Biggs_LH_18.pdf>
- [capsicum] Watson, Anderson, Laurie, Kennaway, "Capsicum: practical capabilities for
  UNIX", USENIX Security 2010. Summary only.
  <https://www.usenix.org/conference/usenixsecurity10/capsicum-practical-capabilities-unix>
- [driverkit] Apple, DriverKit and system extensions. Summary only.
  <https://developer.apple.com/system-extensions/>,
  <https://developer.apple.com/support/kernel-extensions/>
- [exokernel] Engler, Kaashoek, O'Toole, "Exokernel: An Operating System Architecture for
  Application-Level Resource Management", SOSP 1995. Summary only.
  <https://courses.cs.duke.edu/spring15/cps210/readings/exokernel-sosp95.pdf>
- [hongmeng] Chen et al., "Microkernel Goes General: Performance and Compatibility in the
  HongMeng Production Microkernel", OSDI 2024. Full text.
- [herder] Herder et al., "Failure Resilience for Device Drivers", DSN 2007. Talk slides,
  summary only. <https://minix3.org/docs/jorrit-herder/dsn-dccs07-talk.pdf>
- [l4] Heiser, Elphinstone, "L4 Microkernels: The Lessons from 20 Years of Research and
  Deployment", ACM TOCS 34(1), 2016. Full text.
  <https://trustworthy.systems/publications/nicta_full_text/8988.pdf>
- [levasseur] LeVasseur et al., "Unmodified Device Driver Reuse and Improved System
  Dependability via Virtual Machines", OSDI 2004. Summary only.
  <https://www.usenix.org/conference/osdi-04/unmodified-device-driver-reuse-and-improved-system-dependability-virtual-machines>
- [multikernel] Baumann et al., "The Multikernel: A New OS Architecture for Scalable
  Multicore Systems", SOSP 2009. Full text.
  <https://www.sigops.org/s/conferences/sosp/2009/papers/baumann-sosp09.pdf>
- [phoronix] Larabel, Phoronix driver size reports, 2021 to 2026. Secondary source.
  <https://phoronix.com/news/AMD-Six-Million-Lines-Linux-7.0>,
  <https://www.phoronix.com/news/Linux-6.16-AMDGPU-Driver-Size>
- [qnx] QNX OS 8.0 System Architecture, microkernel and IPC chapters.
  <https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.sys_arch/topic/kernel.html>
- [redleaf] Narayanan et al., "RedLeaf: Isolation and Communication in a Safe Operating
  System", OSDI 2020. Full text.
  <https://www.usenix.org/system/files/osdi20-narayanan_vikram.pdf>
- [redox] The Redox book: microkernels, schemes, security, drivers.
  <https://doc.redox-os.org/book/microkernels.html>
- [sculpt] Böttcher, "Sculpt OS: a dynamic general-purpose OS powered by Genode on seL4",
  slides, September 2025. Text extraction only.
- [sel4-caveats] seL4 `CAVEATS.md`. <https://github.com/seL4/seL4/blob/master/CAVEATS.md>
- [sel4-faq] seL4 FAQ. <https://sel4.systems/About/FAQ.html>
- [sel4-perf] seL4 performance page. <https://sel4.systems/performance.html>
- [sel4-verified] seL4 verified configurations.
  <https://docs.sel4.systems/projects/sel4/verified-configurations.html>
- [sel4-wp] Heiser, "The seL4 Microkernel: An Introduction" (whitepaper). Full text.
  <https://sel4.systems/About/seL4-whitepaper.pdf>
- [theseus] Boos et al., "Theseus: an Experiment in Operating System Structure and State
  Management", OSDI 2020. Full text.
  <https://www.usenix.org/system/files/osdi20-boos.pdf>
- [zircon] Fuchsia kernel concepts and handles.
  <https://fuchsia.dev/fuchsia-src/concepts/kernel/concepts>
