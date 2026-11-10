# A2a follow-up: release variants, and what the debug build did to the A2a comparison

**Not an experiment outcome.** This extends the A2a record ([A2a](A2a.md), outcome Investigate, unchanged) with four more kernel builds, to answer one question the A2a record could only guess at: how much of the function-level difference from K0 is the debug build, and how much is the hypervisor option, SMP or the platform.
Authorization: the owner's message of 2026-11-09 ("investigate reproducible release variants of K1, K2 and E1-H to quantify the effect of debug instrumentation"). **No row of the assurance matrix is changed or added.** Nothing was booted. Nothing here is a formal-verification claim.

## What was built

All with the A2a tools (GCC 16.2.0, CMake 4.4.5, Ninja 1.13.2, the pinned clean seL4 `62e345c2…`), kernel only, each twice in different directories [Measured: [01](A2a-variants/01-tools.txt), [02](A2a-variants/02-commands.txt)]:

| ID | Meaning | Differs from its parent in |
|---|---|---|
| **K1R, K2R, E1HR** | K1, K2 and E1H as release builds: `-DKernelDebugBuild=OFF -DKernelPrinting=OFF` | exactly five keys: `DEBUG_BUILD`, `PRINTING`, `COLOUR_PRINTING`, `IRQ_REPORTING`, `USER_STACK_TRACE_LENGTH` |
| **K0Q** (extra, informational) | K0's own file `AARCH64_verified.cmake` on the `qemu-arm-virt` platform (`-DKernelPlatform=qemu-arm-virt -DARM_CPU=cortex-a57` before the file) | K0 in exactly seven keys: the platform and timer-frequency keys |

None is a matrix row and none is a verified configuration. K0Q is mine, not the owner's request: it exists to separate the platform effect from the verification-style build options.

## 1. Build reproducibility

All eight builds exit 0. The function table of each variant is byte-identical from the two builds, the comparison and the matrix are identical when rerun, and every C function with code in each `kernel.elf` is in its table (the symbols that are not are the 19 or 20 assembly-defined entry points and data labels) [Measured: [04](A2a-variants/04-sums.txt), [05](A2a-variants/05-nm-crosscheck.txt), [06](A2a-variants/06-reproducibility.txt)].
The tables of K0, K1, K2 and E1H are copied from the reviewed A2a evidence and the verifier requires them to be byte-identical to it.
A first run of this procedure was not reproducible: the build directory leaked into the table because `external/` is a symlink in the worktree where it ran (the compiler records the unresolved path, the comparison normalises the resolved one). The variants script now configures CMake with physical paths and the run was repeated.
`a2a-compare.py` itself was not changed, because the A2a evidence records its hash. **It does depend on the build having been configured with physical paths**, which A2a satisfied.

## 2. Configuration similarity: the effect ladder [Measured, text only]

Against K0 (functions identical / differ / only in K0 / only in the other), with the A2a rows for comparison:

| | Debug build | Release build |
|---|---|---|
| **E1-H** (hypervisor, qemu, the E1 to E3 kernel) | 554 / 322 / 7 / 84 | **859 / 17 / 7 / 0** |
| **K1** (no hypervisor, 1 vCPU) | 396 / 338 / 149 / 88 | 629 / 105 / 149 / 4 |
| **K2** (no hypervisor, 4 vCPUs) | 339 / 389 / 155 / 130 | 518 / 210 / 155 / 45 |
| **K0Q** (K0's configuration, qemu platform) | n/a | **877 / 6 / 0 / 0** |

What each option does on its own (pairs of builds that differ in that option only, plus the noted knobs):

| Effect | Pair | Identical | Differ | Only in the first | Only in the second |
|---|---|---|---|---|---|
| Debug instrumentation | K1 to K1R | 463 | 275 | 84 | 0 |
| | K2 to K2R | 492 | 281 | 85 | 0 |
| | E1H to E1HR | 565 | 311 | 84 | 0 |
| Hypervisor option (release, qemu) | K1R to E1HR | 634 | 100 | 4 | 142 |
| SMP, 4 vCPUs (release, no hypervisor) | K1R to K2R | 598 | 134 | 6 | 41 |
| K0's other build knobs (verification build on, 16 domains and their schedule length, SMC calls on, the bootinfo untyped limit) | E1HR to K0Q | 864 | 12 | 0 | 7 |
| Platform (`tx2` to `qemu-arm-virt`) | K0 to K0Q | 877 | 6 | 0 | 0 |

Per required property (`identical / differs / only in K0 / only in the other`, over the files of the A2a mapping):

| Property | K1 | K1R | K2 | K2R | E1H | E1HR | K0Q |
|---|---|---|---|---|---|---|---|
| P1 address-space isolation | 28/39/8/6 | 40/27/8/2 | 25/42/8/6 | 35/32/8/2 | 45/30/0/4 | 70/5/0/0 | 74/1/0/0 |
| P2 authority integrity | 57/28/0/0 | 77/8/0/0 | 52/33/0/0 | 66/19/0/0 | 59/26/0/0 | 81/4/0/0 | 85/0/0/0 |
| P3 revocation and reclamation | 49/22/0/0 | 63/8/0/0 | 46/25/0/0 | 54/17/0/0 | 51/20/0/0 | 67/4/0/0 | 71/0/0/0 |
| P4 kernel integrity | 12/20/1/3 | 27/5/1/0 | 8/24/1/3 | 13/19/1/0 | 15/18/0/3 | 33/0/0/0 | 33/0/0/0 |
| P5 kernel part | 49/22/0/0 | 63/8/0/0 | 46/25/0/0 | 54/17/0/0 | 51/20/0/0 | 67/4/0/0 | 71/0/0/0 |

**Readings (each is about text):**
1. **Debug instrumentation accounts for nearly all of E1-H's difference from K0:** 322 differing functions fall to 17 in the release build. In K1 it accounts for about two thirds (338 to 105) and in K2 for about half (389 to 210). The A2a record's guess that "much of the function-level difference is probably the debug option" is confirmed and quantified.
2. **What is left for the release E1-H is small and nameable:** the 17 are eight architecture-capability functions (six `Arch_*` and two `cap_get_arch*`), three boot functions and six platform functions (GICv2 and timer initialisation, `physBase`); the 7 functions only in K0 are the SMC functions. That the capability functions differ because K0 has the SMC capability type (`ALLOW_SMC_CALLS`) and E1HR does not is [Inferred]; the configuration keys and the function names are [Measured]. With K0's other knobs set (K0Q) the remainder is the 6 platform functions
   (`cpu_iface_init`, `dist_init`, `initGenericTimer`, `resetTimer`, `map_kernel_elf_image`, `physBase`).
3. **In K0Q, every function on the capability, CNode, mint, revoke, untyped, endpoint and syscall paths of the A2a mapping is textually identical to K0** (P2, P3 and P4 fully, P1 with one differing function). That is a statement about text.
4. **The hypervisor option is the largest single remaining difference for the non-hypervisor kernels:** 100 functions differ and 142 exist only in the hypervisor build.

## 3. What this does not show

- **Functional execution:** nothing was booted. Whether any variant runs is not known. K0Q and E1HR have no kernel printing, so a root task cannot use `DebugPutChar` on them, and the E1 to E3 logging path does not work there.
- **Verification applicability:** unchanged from A2a. K0Q is textually near K0 but it is not a verified configuration: the platform is not one the documentation lists (the 17.0.0 verification manifest does tie the pinned seL4 commit to a proof revision, [A2a](A2a.md) section 3, but that is for the listed configurations). Equal text of a function does not mean a proof of it holds here. **K0Q is a hypothesis for a baseline, not a classification.**
- **Release is not "verification build".** K1R, K2R and E1HR keep `VERIFICATION_BUILD` off, and the knobs that K0 sets (16 domains, SMC calls, bootinfo limits) at their defaults.
- Text only, function definitions only, with the A2a mapping and its limits.

## Evidence

[`A2a-variants/`](A2a-variants/): the same kinds of files as A2a, for the four variants, plus the copied tables of K0, K1, K2 and E1H. Produced by [`run-a2a-variants-evidence.sh`](../run-a2a-variants-evidence.sh) and [`build-a2a-variants.sh`](../build-a2a-variants.sh); checked by `verify_a2a_variants.py` (8 checks, a presence check and a well-formedness check; they recompute the comparison from the published tables of all eight configurations and require each variant's published table to be the one whose hash and count the reproducibility record names; 12 self-test corruptions and the removal of the directory).

**Corrections after the independent review of 2026-11-10:** the row "K1R to E1HR" had its last two columns swapped (4 functions exist only in K1R and 142 only in E1HR; the prose was right); "timer settings" was wrongly listed among K0's knobs (no timer key differs between E1HR and K0Q); the verifier did not tie the variant tables to their recorded hashes, and crashed on a missing or truncated file instead of failing a check. All four are fixed. **Since then the K1R and K2R kernels have been booted** ([ReleaseKernel](ReleaseKernel.md)); "nothing was booted" above describes this record's own runs.
