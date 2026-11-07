# ADR 0003: Boot strategy

- **Status:** Provisional. The owner accepted this at Gate 1, and it stays provisional
  wherever seL4 compatibility may require reconsideration.
- **Date:** 2026-11-07
- **Deciders:** Project owner

Evidence is in [the target and boot research](../research/target-and-boot.md).

## Context

The boot path is the first code to run and the start of any chain of trust. M1 needs a
single answer for how the kernel is loaded, what it receives, and how this extends to
secure and measured boot on real hardware.

## Requirements

1. The same path must work on AArch64 and x86-64.
2. What is tested under emulation must be what runs on real hardware.
3. It must provide a route to verified and measured boot with owner-controlled keys.
4. Code in the boot chain must be small, auditable and memory safe where possible.
5. Boot must be fast enough for automated tests.

## Decision

1. **Fyrkat boots through UEFI on every architecture**, with a loader written in Rust
   and owned by this project.
2. **The loader is the only boot path.** QEMU's direct kernel load is not used, including
   for tests.
3. **The loader hands the kernel a versioned boot information structure.** The kernel
   does not call UEFI, and does not depend on which firmware loaded it.
4. **The loader is the place where kernel verification will happen.** It does not
   implement this at M1, and the design must not prevent it.

**Not decided here:** how the kernel consumes ACPI and devicetree, whether to depend on
the `uefi` crate, the signature scheme, and the key ownership model. M1 needs an answer
to the first two, and they belong in the M1 plan or a further ADR.

## Alternatives

**Direct kernel load (`-kernel`).** It is the simplest and fastest option at 0.03 s, but
it is specific to QEMU and exercises a path real hardware does not use. Its speed
advantage is 0.16 s under HVF, which does not justify a second boot path.

**Limine.** It would remove the need to write a loader. It adds a third-party bootloader
to the boot chain, and Fyrkat's verification story would depend on it. The spike reached
a working UEFI application in about 100 lines of Rust, so the saving looks small.

**U-Boot or vendor firmware directly.** U-Boot can provide the UEFI interface on boards
that use it, so a UEFI loader runs there without Fyrkat depending on U-Boot specifically.

**Custom firmware.** It is out of scope. It would replace platform firmware that Fyrkat
cannot realistically replace on commodity hardware.

## Evidence

- One UEFI application source booted on both architectures, under HVF and emulation.
  [Measured]
- UEFI boot took 0.195 s under HVF, 0.535 s under AArch64 emulation and 1.791 s under
  x86-64 emulation, once the firmware menu timeout was disabled. [Measured]
- EBBR and BBR standardize on UEFI for Arm systems. [Documented]
- Both devicetree and ACPI configurations of QEMU `virt` boot. [Measured]

## Security consequences

- **UEFI firmware is part of the trusted computing base**, and Fyrkat cannot remove it on
  commodity hardware. Claims about boot integrity must state this.
- Owning the loader keeps verification logic in Rust, under project review.
- M1 will not provide verified boot. It must not be described as verified, and
  the milestone should be renamed "Boot path".
- Secure Boot can be tested on x86-64 with the firmware Homebrew ships. AArch64 needs a
  separate firmware build, and measured boot testing needs `swtpm`.

## Performance consequences

- Under emulation, UEFI costs a fraction of a second, which suits automated tests.
- QEMU runs must disable the firmware boot menu, which otherwise adds about 5 seconds.
- Boot time on physical hardware has not been measured.

## Compatibility implications

- Systems without UEFI are unsupported unless a shim provides it.
- The boot information structure becomes an internal interface, and must be versioned.

## Risks

- **The loader becomes security-critical code that the project must maintain.**
- **Firmware quality varies on real hardware**, and QEMU will not reveal this.
- **The early kernel is harder to debug**, because a loader runs before it. Keeping the
  loader small and logging over the UEFI console reduces this.

## Open conflicts with seL4

These are flagged by [ADR 0004](0004-kernel-foundation.md). None is resolved, and no
irreversible commitment may be made until the spike reports.

- **seL4 platforms are selected at compile time.** A kernel built for one platform does not
  discover hardware from firmware the way this ADR's loader assumes. [Documented]
- **The boot information structure** would have to fit seL4's own boot interface, and the
  loader would hand over to it rather than to a Fyrkat kernel. [Inferred]
- **x86-64 may expect a different handoff** from a UEFI loader. This needs checking. [Inferred]
- **rust-sel4 already provides a kernel loader**, which may replace or inform a Fyrkat one.
  [Documented]

## Reconsideration criteria

Reopen this ADR if any of these occurs:

1. A required target platform cannot provide UEFI.
2. Loader complexity approaches that of an existing audited bootloader.
3. UEFI boot time makes automated testing impractical.
4. A verified-boot design shows that the loader must be structured differently.
5. The seL4 spike produces any result that its plan lists as reopening this ADR.
