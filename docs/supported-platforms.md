# Supported platforms

**Nothing is supported.** Fyrkat has no kernel and no operating system, so there is no
platform to support. This page records only what the project's tooling is tested on.

## Development hosts

| Host | Status |
|---|---|
| macOS on Apple Silicon | The primary development machine. `cargo xtask check` and `cargo xtask boot` (TCG and HVF) have been run here. |
| Ubuntu 24.04, x86-64 and arm64 | Run by CI on 2026-11-07 (PR 1): `cargo xtask check` passed on x86-64, and `cargo xtask boot` passed on both x86-64 and arm64, with both guests under TCG. Firmware lookup worked on Ubuntu 24.04. Debian is untested. The runners have QEMU 8.2.2 from Ubuntu packages, not the 11.1.3 the spike plan pins, so CI results never substitute for spike results. `/dev/kvm` was present on the x86-64 runner and absent on arm64. Treat it as unavailable. |
| macOS in CI | A weekly scheduled workflow is written to run `check` and `boot`. It has not run yet, because schedules fire only from the default branch. |
| Windows | Not supported and not tested. |
| Other Linux distributions, Intel macOS | Not tested. Firmware path lookup includes some of them, but that is not a test. |

## What the boot test covers

`cargo xtask boot` builds `tests/boot-smoke`, a UEFI application that prints a marker and
shuts down, and runs it under QEMU with EDK2 firmware:

| Guest | Machine | Accelerator |
|---|---|---|
| AArch64 | QEMU `virt` | TCG; HVF on Apple Silicon |
| x86-64 | QEMU `q35` | TCG |

This verifies that the toolchain builds UEFI images and that QEMU and firmware boot them.
It says nothing about any kernel, and it is an emulation result, not evidence about real
hardware. No physical hardware has been tested.

The choice of CPU architectures and boot flow for Fyrkat itself belongs to
[ADR 0002](adr/0002-initial-cpu-architecture.md) and [ADR 0003](adr/0003-boot-strategy.md).
The existence of a test target here is not a decision.
