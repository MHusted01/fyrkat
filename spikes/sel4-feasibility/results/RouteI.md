# Route I: do the non-hypervisor K1 and K2 boot under seL4's own elfloader?

**Not an experiment outcome and not a Stage B result.** Authorized by the owner on 2026-11-09 ("Investigate booting [K1 and K2] with seL4's elfloader"). It answers one question about the *loader*: whether the plan's K1 and K2 can be started at all, since the Rust `sel4-kernel-loader` boots only hypervisor-enabled (EL2) kernels. No kernel or loader source was changed, no dependency or ADR was touched, and nothing about formal-verification applicability follows. Labels as in AGENTS.md; [Measured] means checked by `verify_routei.py` against the committed evidence in [`RouteI/`](RouteI/).

## What was built

Kernel, seL4's elfloader and the rust-sel4 demo root task (`TEST_PASS` after a round trip that returns badge `0x1337`) for `qemu-arm-virt`, with the tools of A2a, by [`build-routei.sh`](../build-routei.sh) (a generated seL4 project that uses seL4's own `rootserver`/elfloader support and `util_libs/libcpio`; the Rust root task is built against the matching kernel prefix and replaces a placeholder after the build) and [`run-routei-evidence.sh`](../run-routei-evidence.sh):

| Image | Kernel configuration | Notes |
|---|---|---|
| **K1** | the A1 recipe: non-hypervisor, 1 vCPU, debug | default QEMU device tree |
| **K2** | K1 plus `SMP=TRUE`, `NUM_NODES=4` (seL4's `init-build.sh` options; the resulting `gen_config.json` has the same SHA-256 as A2a's K2, and K1's as A2a's K1: checked by the verifier) | device tree built from QEMU's own dump with `virtualization=on` (PSCI method `smc`) |
| K2H, K2M | K2H: K2 with seL4's default tree. K2M: K2 with the `smc` tree and the root task built for **K1** | negative controls; all three K2 images have the same `gen_config` hash, so the tree does not change it |

## Observed [Measured]

- **K1 boots through the elfloader under QEMU 11.1.3 TCG** (`-machine virt,secure=off,gic-version=2 -smp 1`): 3 of 3 runs print `badge = 0x1337` and `TEST_PASS`.
- **K2 boots through the elfloader with 4 vCPUs** (`-machine virt,secure=off,gic-version=2,virtualization=on -smp 4`): 3 of 3 runs bring up cores 1 to 3 and print `TEST_PASS`.
- **K2 needs three things together, and each is a negative control that fails:**
  1. *The device tree embedded at build time must say `smc` for PSCI.* With seL4's default dump (PSCI method `hvc`, taken from QEMU run without `virtualization=on`) the elfloader stops with "HVC is not supported for PSCI!" and "Failed to boot cpu 0x1". This is the failure A3 recorded, now explained [Inferred from the code path: seL4's CMake dumps QEMU's tree with `virtualization=on` only when the kernel has hypervisor support; the `QEMU_DTB` option overrides it].
  2. *QEMU must be run with `virtualization=on`.* With the `smc` tree and no `virtualization=on` the boot stops silently after "Boot cpu id" and the marker is not seen.
  3. *A root task built against K1 does not work under K2.* It boots all cores and then fails the demo's own assertion on the badge it received (`left: 0, right: 4919`; the line `badge = 0x1337` it prints before that is the constant, not the observation). That the cause is the kernel interface it was built against is [Inferred]: the mechanism was not identified.
- This is **a loader path for K1 and K2, not a verified configuration**: `virtualization=on` makes QEMU expose EL2 although the kernel does not use it, which is a property of the harness, and K2's DTB comes from a different QEMU invocation than the one that boots it.

## Not shown

- Boots K1 and K2 *debug* only. No release image was booted, and a release kernel has no `DebugPutChar`, so the demo's logging cannot be used there (see the Stage B matrix Amendment).
- TCG only. HVF is not retried (A3 recorded the failure; nothing here bears on it).
- Nothing about K1 or K2 under the E1 to E3 experiments: those ran on the E1-H kernel.
- The records name the `repo HEAD` and branch the run started from (`004bf9e` on a local branch, before PR 14 was squash-merged); the sources they hash are the files in this repository.

## Limits

The build script and the verifier were reviewed independently on 2026-11-10 (D26); the review reproduced no boot. These are generated projects, not A1's build directories.

**Provenance gaps the review found, which this evidence set does not close** [Measured by the reviewer]: the driver deletes the build logs of K2's kernel interface and root task and does not hash itself; the hash of the `smc` device tree and the commits of seL4_tools (the elfloader) and util_libs are not recorded (both checkouts are at their pins and clean now). So "K2's root task is built against K2's own interface" and "no loader source is changed" rest on state this record does not capture. And the generated project reaches the kernel through a link, so the kernels' embedded paths differ from A2a's and `a2a-compare.py` reports spurious differences against A2a's tables (87 functions for K2): the function-level identity of these kernels with A2a's K1 and K2 is **not** shown here. [ReleaseKernel](ReleaseKernel.md) repeats the **positive** K1 and K2 boots with all of this recorded and with function tables identical to A2a's; prefer it as the evidence that K1 and K2 boot through the elfloader. The three negative controls here (the default tree, no `virtualization=on`, the K1-built root task) were not repeated with the missing provenance, so they stand on this record alone.

The verifier now also checks each run's recorded image, vCPU count and machine options (10 checks and a well-formedness check, 12 self-test corruptions).
