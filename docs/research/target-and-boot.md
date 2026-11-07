# CPU target and boot strategy

Research date: 2026-11-07. This document supports
[ADR 0002](../adr/0002-initial-cpu-architecture.md) and
[ADR 0003](../adr/0003-boot-strategy.md). It gathers evidence and does not decide
anything. Both ADRs stay provisional where seL4 compatibility may matter, and their open
conflicts are listed in the ADRs themselves. Evidence labels are defined in the [ADR README](../adr/README.md).

## Limits of this research

- Measurements come from one machine and describe its development loop only. See the
  [spike README](../../spikes/boot-latency/README.md) for method and limits.
- Hardware availability findings come mostly from secondary sources and search
  summaries. No hardware was tested, and x86-64 machines were not surveyed.
- Whether GitHub's runners expose KVM is unknown and will be tested in CI.

## Development loop on this host

Full results are in the [spike README](../../spikes/boot-latency/README.md).

| Measure | AArch64 with HVF | AArch64 emulated | x86-64 emulated |
|---|---|---|---|
| Boot through UEFI | 0.195 s | 0.535 s | 1.791 s |
| Integer loop | 1.78 ns | 3.04 ns | 2.22 ns |
| Random memory access | 3.21 ns | 203.6 ns | 19.3 ns |
| Exception round trip | 20.6 ns | 644 ns | 414 ns |

What these numbers show: [Measured]

- HVF runs at native speed on the integer workload, and is 6 to 20 times faster than
  x86-64 emulation on memory and exceptions.
- **x86-64 emulation is entirely workable for functional testing.** It boots in under 2
  seconds. Speed alone does not justify choosing AArch64.
- AArch64 emulation is not faster than x86-64 emulation on this host, and is much slower
  on the memory workload for reasons not yet understood.

## What native execution provides beyond speed

- Only AArch64 can run natively on this machine, so only AArch64 can give meaningful
  performance data here. Emulator timing does not reflect guest performance. [Inferred]
- AArch64 is weakly ordered and x86-64 uses a stronger model. Code that is correct under
  weak ordering is also correct under the stronger one, but the reverse does not hold.
  Running first on the weaker model exposes missing barriers sooner. [Inferred]
- QEMU accepted x86-64 emulation with parallel vCPUs on this host, so parallelism alone
  is not an AArch64 advantage. [Measured]
- This host reports `FEAT_PAuth`, `FEAT_BTI`, `FEAT_LSE`, `FEAT_CSV2` and `FEAT_CSV3`,
  and no `FEAT_MTE`. [Measured] Whether HVF exposes these to guests is untested.

## Virtualization on this host

- HVF refuses EL2 on this machine: `-machine virt,virtualization=on -accel hvf` fails
  with `HV_NO_DEVICE`. [Measured]
- QEMU developers state that macOS supports nested virtualization only on M3 and later
  [qemu-hvf]. [Documented]
- TCG accepts the same machine setting, and the guest runs. The spike did not read
  `CurrentEL`, so the exception level was not confirmed. [Measured]
- Hypervisor work on this machine must therefore use emulation. x86-64 VT-x and SVM
  under TCG were not tested.

## Device isolation under emulation

QEMU provides an emulated IOMMU on both architectures, and UEFI still boots with each
one enabled. [Measured] This suggests DMA isolation can be tested without hardware.
[Inferred] The spike did not perform any DMA or exercise translation, so that remains
to be shown.

- AArch64: `-machine virt,iommu=smmuv3`, under HVF.
- x86-64: `-device intel-iommu`, under TCG.

## Physical hardware

Fyrkat needs a machine with UEFI, an IOMMU and PCIe. [ADR 0001](../adr/0001-kernel-architecture.md)
proposes that drivers cannot be treated as isolated without an IOMMU.

- **Apple Silicon:** no public platform documentation was found or sought. Treating
  this Mac as a Fyrkat target is out of scope. [Inferred]
- **Arm boards:** the Radxa Orion O6 is SystemReady SR certified, with a PCIe x16 slot
  [orion]. Whether its SMMU works is **unconfirmed**. One test used
  `arm-smmu-v3.disable_bypass=0 acpi=off` [orion-debian], and a CIX technical reference
  manual is published [cix-trm], but neither was read for this. [Documented, secondary]
- **x86-64:** a forum post says almost all x86 devices support an IOMMU and that no Arm
  board seemed to [radxa-forum]. This is a single informal source. [Documented, weak]
- **RISC-V:** RVA23 boards exist with the hypervisor extension mandated, but they are
  early. IOMMU, UEFI and PCIe status were not established [riscv]. [Documented, weak]

## Toolchain

- `aarch64-unknown-none-softfloat`, `aarch64-unknown-uefi`, `x86_64-unknown-none` and
  the UEFI targets are Tier 2 in the Rust project [rustc-tiers]. [Documented]
- All of the spike's targets built on pinned stable 1.99.1 without `build-std`.
  [Measured]
- Miri is not offered on stable, so it needs a pinned nightly. [Measured]
- Free arm64 Linux runners are available for public repositories [gh-arm]. [Documented]

## Boot options

- **UEFI:** one application source booted on both architectures, under HVF and TCG.
  [Measured] Boot cost was 0.195 s against 0.032 s for direct boot. [Measured]
- EBBR and BBR standardize UEFI on Arm, and both allow devicetree or ACPI [ebbr].
  [Documented]
- **Direct kernel load:** fastest, and specific to QEMU. It exercises a path that real
  hardware would not use. [Inferred]
- **Limine:** a request and response protocol [limine]. It adds a third-party
  bootloader to the boot chain. [Documented]
- **`uefi` crate:** version 0.41.0, updated 2026-09-21, with 8 required dependencies.
  [Measured] The spike needed none of it. Whether to adopt it is a later decision.
- `-machine virt,acpi=off` also boots, so both hardware description paths are available
  for testing. [Measured]

### Secure and measured boot testing

- Homebrew QEMU ships `edk2-x86_64-secure-code.fd`, and no AArch64 equivalent. [Measured]
- QEMU provides TPM devices on both architectures. `swtpm` is not installed, and
  version 0.10.2 is available. [Measured]
- Testing Secure Boot on AArch64 will need a separate firmware build. [Inferred]

## Open questions

1. Does the Radxa Orion O6, or any affordable Arm board, have a working SMMU?
2. Why is AArch64 TCG slow on the memory workload?
3. Do GitHub runners expose KVM?
4. Are PAC and BTI visible to guests under HVF?
5. How should the kernel consume ACPI and devicetree?

## Sources

Accessed 2026-11-07. All were seen through search summaries, not read in full.

- [cix-trm] <https://www.cnx-software.com/2025/12/13/cix-releases-p1-cpu-trm-and-developer-guides-for-gpu-ai-accelerator-os-and-firmware-bios/>
- [ebbr] Arm, Embedded Base Boot Requirements. <https://arm-software.github.io/ebbr>
- [gh-arm] <https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/>
- [limine] <https://github.com/limine-bootloader/limine-protocol/blob/fedf97facd1c473ee8720f8dfd5a71d03490d928/PROTOCOL.md>
- [orion] <https://www.cnx-software.com/2025/04/30/radxa-orion-o6-mini-itx-motherboard-gets-arm-systemready-sr-v2-5-certification/>,
  <https://docs.radxa.com/en/orion/o6/getting-started/introduction>
- [orion-debian] <https://www.cnx-software.com/2025/03/30/radxa-orion-o6-preview-debian-12-what-works-what-doesnt/?amp=1>
- [qemu-hvf] HVF nested virtualization patch series, v20.
  <https://patchew.org/QEMU/20260316130642.13246-1-mohamed@unpredictable.fr>
- [radxa-forum] <https://forum.radxa.com/t/does-radxa-have-a-board-that-supports-smmu-iommu/15673>
- [riscv] <https://www.cnx-software.com/2026/01/30/jupiter-2-an-rva23-compliant-sbc-powered-features-spacemit-k3-octa-core-risc-v-ai-soc-up-to-32gb-ram-256gb-ufs/>,
  <https://www.youngju.dev/blog/2026-07-16-riscv-rva23-profile-baseline-reality.en>
- [rustc-tiers] <https://doc.rust-lang.org/rustc/platform-support.html>
