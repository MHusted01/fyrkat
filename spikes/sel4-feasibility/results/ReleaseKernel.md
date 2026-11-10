# Release-kernel execution: do K1R and K2R boot and run Rust user code, with no kernel debug output?

**Not an experiment outcome and not a Stage B result.** Authorized by the owner on 2026-11-10 ("Implement, boot and test release-kernel configurations K1R and K2R"; "Do not execute the broader Stage B gate"). It establishes that the release rows of the Stage B matrix (plan Amendment of 2026-11-10) can be built, booted and observed, and it gives them a logging path. No kernel, loader, dependency or ADR was changed. Nothing here bears on formal-verification applicability. Labels as in AGENTS.md; [Measured] means checked by `verify_relk.py` (11 checks, a presence check and a well-formedness check; 18 self-test corruptions) against the evidence in [`ReleaseKernel/`](ReleaseKernel/).

## What was built

| | |
|---|---|
| Kernels | K1, K1R, K2, K2R as the matrix defines them: `qemu-arm-virt`, no hypervisor support, 1 or 4 nodes; the R rows add `KernelDebugBuild=OFF` and `KernelPrinting=OFF`. Built by [`build-relk.sh`](../build-relk.sh), which generates a project for seL4's own elfloader as `build-routei.sh` does |
| Logging | A user-level PL011 driver, [`pl011.rs`](../crates/e2-root-task/src/pl011.rs): polled transmit on the UART at `0x09000000`, which the kernel leaves to user level (it is inside a device untyped, and a kernel without printing does not map it). It also takes over the runtime's panic output |
| Root task | [`relk_root_task.rs`](../crates/e2-root-task/src/bin/relk_root_task.rs) with [`relk_tests.rs`](../crates/e2-root-task/src/relk_tests.rs): the same source built against each kernel's own interface. Its worker threads ([`relk_workers.rs`](../crates/e2-root-task/src/relk_workers.rs)) have no IPC buffer and no thread-local storage; they report to the root task by register-only `seL4_Call` ([`rawsys.rs`](../crates/e2-root-task/src/rawsys.rs)), and the root task attributes each report by the badge of the capability it arrived through |
| Machine | QEMU 11.1.3 TCG, `-machine virt,secure=off,gic-version=2` with 1 vCPU (K1, K1R); the same with `virtualization=on`, 4 vCPUs and a device tree whose PSCI method is `smc` (K2, K2R), as [Route I](RouteI.md) found necessary |
| Procedure | [`run-relk-evidence.sh`](../run-relk-evidence.sh), `sanitize-run.py ReleaseKernel`, `verify-evidence.py` |

No new dependency: the code is new files in the existing `e2-root-task` crate, and `Cargo.toml` and `Cargo.lock` are unchanged.

## Observed [Measured]

**The booted kernels are the recorded ones.** For each of K1, K1R, K2 and K2R, the `gen_config.json` of the image equals the one the root task was built against, and both it and the function table that `a2a-compare.py` extracts from the image's preprocessed kernel have the same SHA-256 as the published configuration and table of that ID in the [A2a](A2a.md) evidence (K1, K2) or the [A2a-variants](A2a-variants.md) evidence (K1R, K2R). So the kernels that ran here are, function for function, the ones whose comparison with K0 is on record. (This needed the kernel source named by its physical path in the generated project; through a link the tables differ in their path column.)

**K1R: 3 of 3 boots pass 7 tests. K2R: 3 of 3 boots pass 8 tests.** Each test prints what it observed, and the verifier reads those observations, not only the verdicts:

| Test | What the kernel has to do |
|---|---|
| `notification-badge` | retype, mint with a badge, signal through the badged capability, wait on the unbadged one: the badge arrives |
| `ipc-call-reply` | a worker thread's `Call` arrives with its badge and two message words; the reply reaches the worker |
| `vm-fault-delivery` | a worker reads an unmapped address: a VM fault with that address and a translation-fault status reaches the root task |
| `debug-syscall` | a worker issues system call -9 (`seL4_DebugPutChar` on a printing kernel): see below |
| `revoke-badged-copy` | a badged endpoint capability and a copy of it; after the root task revokes the first, a call through the copy is answered by the kernel with `seL4_InvalidCapability` and does not arrive; the revoked capability itself still works |
| `page-permission-and-unmap` | one frame mapped read-write and, through a copy of its capability, read-only: a worker reads the second view, its write to it is a permission fault and the frame is unchanged; after the copy is unmapped a read is a translation fault |
| `timer-preemption` | two workers of equal priority that never block each finish only after seeing the other make progress, which needs the kernel's timer interrupt to preempt them |
| `smp-other-cores` (K2, K2R) | a worker of lower priority than the root task, placed on core 1, 2 or 3, makes progress while the root task spins on core 0 without entering the kernel; the same worker placed on core 0 makes none in the same window; core 4 is refused |

**Nothing on the console comes from the kernel.** In all six release boots, every non-empty line after the elfloader's last line starts with the root task's prefix, and none of the kernel's boot lines appears. The kernel's own behaviour confirms that it has no printing: the worker's system call -9 is answered with an **unknown-syscall fault** naming that number, and nothing is printed between the brackets the root task prints around the attempt.

**Controls.**
- *The debug kernels.* The same root task built for and run on K1 and K2 passes the same tests; there the kernel's boot lines are on the console, the probe byte is printed by the kernel, and the system call returns. So the probe distinguishes a printing kernel from a non-printing one in both directions.
- *Two deliberately broken tests.* With the revocation left out (K1R) the revocation test fails and only it; with the second view mapped writable (K2R) the page-permission test fails and only it. Both runs end with `RELK_FAIL`, so a failing test is visible on a kernel without debug output.
- *Two mismatched pairings.* The root task built for K1, run on K1R, fails exactly the debug-syscall test (it expects the call to be accepted). The demo root task of A1 and Route I, which prints only through `seL4_DebugPutChar`, leaves the console empty on K1R after the loader: this is why a user-level console was needed.

## What this does and does not show

- **Shows:** K1R and K2R are executable configurations: they boot through seL4's elfloader under QEMU TCG and run Rust user code that exercises IPC, fault delivery, revocation, page permissions, timer preemption and, on K2R, three further cores, with results observable without any kernel debug facility. The release rows of the matrix can be used.
- **Does not show isolation.** The workers are threads of the root task and share its capability space; each test is a functional check of a kernel path. In a non-MCS kernel a thread can invoke its own fault capability, so the root task cannot tell a fault message from one the worker forged (the E2 finding); nothing here depends on that distinction being unforgeable.
- **Does not run E1 to E3 on these kernels**, and is not Stage B. The revocation test here revokes a badged capability with one copy in one capability space; E3's topology is different.
- **The multi-core test is about scheduling, not about parallelism or memory ordering.** TCG's vCPUs are host threads; nothing about timing, cache or cross-core races follows.
- **The UART driver is validated on QEMU only.** It leaves the baud-rate divisors alone, which QEMU ignores. Device pages are mapped without the cacheable attribute, which QEMU does not model.
- **K2R runs on a machine that exposes EL2** (`virtualization=on`) although its kernel does not use it, as the matrix notes for K2.
- Emulator only; an emulator pass is not evidence about hardware.

## Limits

- The same UART carries the elfloader's output; the elfloader is unchanged and still prints in a release image.
- A failure before the UART is mapped is silent on a release kernel (the run then ends at the harness's timeout without the marker).
- The root task's ELF embeds build-dependent data; the record publishes hashes, never binaries.
- `rawsys.rs` hard-codes the non-MCS system-call numbers; the matrix is non-MCS throughout.
- Reviewed independently before commit (the second review of this session): merge-ready, with text fixes that are made. The evidence was re-recorded afterwards, because the shared device-mapping helper changed in response to that review (the same observations; a third review found the helper's changes sound). The review confirmed from the kernel's source that the preemption and other-core tests cannot pass without preemption and without another core, and that the debug system call is number -9 on every non-MCS printing kernel. Its residual findings are addressed (the verifier checks the workers' iteration counts; the safety comment of the probe states what it relies on).
