# ADR 0002: Initial CPU architecture

- **Status:** Provisional. The owner accepted this at Gate 1, and it stays provisional
  wherever seL4 compatibility may require reconsideration.
- **Date:** 2026-11-07
- **Deciders:** Project owner

Evidence is in [the target and boot research](../research/target-and-boot.md).

## Context

Kernel work needs a first target. This choice shapes early debugging, what can be
measured, and which assumptions leak into the kernel. It is not a statement about which
architecture matters most in the long term. Fyrkat needs both AArch64 and x86-64
eventually: x86-64 for desktop and gaming hardware, and Arm for efficient laptops.

## Requirements

1. Correct behaviour must be testable on the primary development machine.
2. Performance must be measurable, not only functionally testable.
3. Concurrency bugs should surface as early as possible.
4. Architecture-specific assumptions must not leak into portable kernel code.
5. A path must exist to real hardware with UEFI, an IOMMU and PCIe.

## Decision

1. **AArch64 is the first development target**, on QEMU `virt`, using HVF locally and
   emulation in CI.
2. **x86-64 is a required second architecture.** Its boot path builds and boots in CI
   from M1. The full kernel port lands before any ABI freeze, and no later than the end
   of M3.
3. **The first physical test machine is chosen at M3**, based on verified IOMMU support.
   If no suitable Arm board is confirmed, x86-64 is the first physical target.

This means development starts on AArch64, but real hardware validation may well come
first on x86-64. These are separate questions, and treating them as one would hide
that.

## Alternatives

**x86-64 first.** This is a serious option. Its hardware ecosystem is stronger, and
emulation boots in 1.8 s, so the development loop is workable. It is not chosen because
this machine could never run it natively, leaving no meaningful performance measurement,
and because a stronger memory model hides ordering bugs. Buying an x86-64 machine would
weaken both objections.

**Both architectures equally from the first day.** This gives the strongest portability
pressure, but doubles architecture work during the phase when kernel structure changes
most. Building and booting x86-64 from M1 captures much of the benefit at low cost.

**RISC-V first.** It is an open architecture with a weak memory model, and RVA23 mandates
the hypervisor extension. Hardware is early, IOMMU and UEFI status were not established,
and it cannot run natively here. It should be reconsidered as a later port.

## Evidence

- HVF matches native speed on an integer workload, and is 6 to 20 times faster than
  x86-64 emulation on memory and exceptions. [Measured]
- x86-64 emulation boots through UEFI in 1.8 s, so speed alone does not decide this.
  [Measured]
- Only AArch64 runs natively on this machine. [Measured]
- Code correct under weak ordering is also correct under a stronger model. [Inferred]
- UEFI boots with emulated SMMUv3 and Intel IOMMU devices enabled. [Measured] DMA
  isolation is therefore probably testable before hardware exists, though no DMA
  translation has been exercised yet. [Inferred]
- HVF refuses EL2 on this M2 Pro, so hypervisor work here requires emulation. [Measured]
- No Arm board with a confirmed working SMMU was found. [Documented, weak]

## Security consequences

- AArch64 offers PAC and BTI, and this host reports both. Guest visibility under HVF is
  untested. The host has no MTE, so MTE cannot be tested here. [Measured]
- Developing on one architecture risks mitigations tailored to it. The x86-64 port
  must have its own review of speculative-execution mitigations.

## Performance consequences

- Local performance measurements are valid only for AArch64 under HVF, and even those
  are virtualized. They do not replace measurements on physical hardware.
- Emulated CI runs are functional tests only and must never be reported as performance.

## Compatibility implications

- The portable kernel must not assume a memory model stronger than AArch64's.
- x86-64 boot in CI from M1 exposes architecture assumptions early.
- This Mac is a development host, not a Fyrkat target. Booting on Apple Silicon is out of
  scope.

## Risks

- **EL2 cannot run under HVF here**, and GPU support probably needs driver VMs. This
  design work must happen under emulation, or on other hardware.
- **Late x86-64 work may expose portability mistakes.** Requiring it before an ABI
  freeze limits the damage.
- **Physical hardware is unresolved.** Open question 1 in the research must be answered
  by M3.
- **AArch64 emulation is slow on memory-heavy tests**, for reasons not yet understood.

## Open conflicts with seL4

These are flagged by [ADR 0004](0004-kernel-foundation.md). None is resolved, and no
irreversible commitment may be made until the spike reports.

- **Verified AArch64 needs EL2, and HVF refuses EL2 on this machine.** HVF can only ever run
  unverified builds, and only if EL1 builds work at all, which is untested. If they do not,
  the main argument for AArch64 first (native execution) falls away. [Documented, Measured]
- **No QEMU run is a verified configuration.** The verified AArch64 configurations target
  boards such as `tx2`, `bcm2711` and `bcm2712`. [Documented]
- **seL4 has no SMMUv3 driver, and QEMU `virt` provides only SMMUv3.** If the spike finds
  DMA isolation is achievable only on x86-64, this ADR reopens. [Documented, Measured]
- **No generic AArch64 platform exists in seL4**, and issue 1613 requesting one is open.
  [Documented]

## Reconsideration criteria

Reopen this ADR if any of these occurs:

1. The primary development machine changes architecture, or an x86-64 machine with an
   IOMMU becomes the main test platform.
2. M3 arrives with no Arm board that has a confirmed working SMMU.
3. The x86-64 port reveals that AArch64-first shaped the kernel badly.
4. Work needing EL2 becomes blocked by emulation speed on this machine.
5. The seL4 spike produces any result that its plan lists as reopening this ADR.
