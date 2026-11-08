# shim-era: first-run logs, kept as history

These are the first A3 logs. **Do not use them as evidence of an SMP result.**

- Their "4 vCPU" image (`13-boot-sel4test-hvf-4cpu.txt` and its siblings) was a **single-node kernel**
  (`KernelMaxNumNodes=1`) run with QEMU `-smp 4`. sel4test ignores `NUM_NODES` unless `SMP=TRUE`.
- Their archives were made with a custom cpio stand-in, not GNU cpio.

The corrected runs are `A3/31` to `A3/34`, with the images' recorded configuration in `A3/41` and `A3/42`.
See [A3.md](../../A3.md) and [deviations](../../deviations.md), D1.
