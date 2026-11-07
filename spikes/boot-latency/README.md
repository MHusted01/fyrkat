# Boot latency spike

Throwaway measurement code. It is not part of the product and is not in the Cargo
workspace. It exists to give [ADR 0002](../../docs/adr/0002-initial-cpu-architecture.md)
and [ADR 0003](../../docs/adr/0003-boot-strategy.md) measured evidence. Delete it once
the real boot tests replace it.

## What it does

- `src/bin/bare.rs`: a direct-boot AArch64 image for QEMU `virt`.
- `src/bin/uefi.rs`: one UEFI application that builds for AArch64 and x86-64. It runs a
  fixed workload chosen at build time, then shuts down.
- `run.py`: builds every case, times complete QEMU runs, and writes `results.json`.

| Workload | What it stresses |
|---|---|
| `alu` | Pure integer loop, the easiest case for an emulator |
| `mem` | Random read-modify-write over 64 MiB, which exercises a software MMU |
| `trap` | Same-level exception round trips, which approximate kernel entry cost |

## Running it

Requires QEMU from Homebrew and the targets in `rust-toolchain.toml`.

```sh
python3 run.py
```

## Results

Measured 2026-11-07 on an Apple M2 Pro with 16 GB, macOS 27.2, QEMU 11.1.3 and
rustc 1.99.1. Boot is a median of 9 runs and workloads are a median of 3. Boot time
covers the whole QEMU process, from launch to exit. Raw data is in `results.json`.

| Configuration | Boot median (min to max) | ALU ns/iter | Memory ns/iter | Trap ns/iter |
|---|---|---|---|---|
| AArch64 direct, HVF | 0.032 s (0.029 to 0.035) | not run | not run | not run |
| AArch64 direct, TCG | 0.033 s (0.032 to 0.034) | not run | not run | not run |
| AArch64 UEFI, HVF | 0.195 s (0.187 to 0.200) | 1.78 | 3.21 | 20.6 |
| AArch64 UEFI, TCG | 0.535 s (0.523 to 0.554) | 3.04 | 203.6 | 644 |
| x86-64 UEFI, TCG | 1.791 s (1.786 to 1.811) | 2.22 | 19.3 | 414 |

The same ALU loop built as a native macOS program runs at about 1.77 ns per iteration,
so HVF matches native speed on this workload.

## Pitfalls found

- **EDK2 waits about 5 seconds by default.** The first run showed UEFI taking 5.2 s
  under both HVF and TCG. This is a boot-menu timeout, not a cost of UEFI. Passing
  `-boot menu=on,splash-time=0` removes it.
- **The integer loop alone was misleading.** It suggested TCG is only about 1.7 times
  slower than native, while memory and trap workloads show 30 to 60 times on AArch64.
- **`-bios` fails for the x86-64 firmware.** It must be loaded as `pflash`.

## Limits

- **These numbers describe this host's development loop.** They say nothing about the
  relative merit of the architectures. x86-64 can only be emulated on this machine.
- TCG timing is not a performance measurement of any guest code.
- All runs use one vCPU, and workloads have only 3 samples each.
- **Unexplained:** AArch64 TCG is about 10 times slower than x86-64 TCG on the memory
  workload. Changing the TCG thread mode, translation cache size or CPU model made no
  difference. The cause may be how each firmware maps memory, which a real kernel would
  replace. Re-measure when Fyrkat has its own page tables.
