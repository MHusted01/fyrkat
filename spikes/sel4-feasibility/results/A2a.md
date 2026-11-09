# A2a: assurance classification of unmodified configurations (no boot)

**Outcome: Investigate** (by the plan's own definition: cells cannot be classified yet and no required test has run). **Not Pass, not Conditional, not Fail.**
Label U for the builds; nothing here is a formal-verification claim. No cell is class A, D or C: the K1 and K2 cells for P1 to P4 are class **B**, as the plan pre-registered, and the P5 cell cannot be classified because the SMMU server does not exist.
The plan's A2 can never be Pass in this spike, and A2a cannot reach Conditional before Stage B has run the required tests. A2a only classifies, and lists the functions.

Authorization: the owner's message of 2026-11-09 ("I authorize A2a under the existing S1 plan and its original acceptance criteria"), recorded in the plan's [Amendments](../../../docs/research/sel4-spike-plan.md#amendments). The plan's criteria are not redefined or weakened here.
Scope as approved: build K0 and the pinned verified AArch64 configuration with GCC 16.2.0; K1 and K2 as defined; a reproducible comparison script; the E1 to E3 hypervisor-enabled kernel **as an informational row, outside the approved matrix**; the public seL4 verification documentation.
Not done, by instruction: any change to kernel or loader source, dependency pins, ADR statuses or the Stage B matrix; Stage B, A4, A5 implementation, the comparator.

## What was built

All four with `aarch64-elf-gcc (GCC) 16.2.0`, CMake 4.4.5, Ninja 1.13.2, the pinned seL4 `62e345c2…` (clean checkout, no change), the hash-pinned Python environment; kernel only, nothing booted [Measured: [01](A2a/01-tools.txt), [02](A2a/02-commands.txt)].

| ID | Meaning | Command, in short |
|---|---|---|
| **K0** | The plan's reference (decision 1c): `AARCH64_verified.cmake` | `cmake -C configs/AARCH64_verified.cmake`, `ninja kernel.elf`, `ninja kernel_all_pp_wrapper` (how seL4 documents using the file). Compile and compare only |
| **K1** | AArch64 `qemu-arm-virt`, no hypervisor support, 1 vCPU: A1's recipe | `-DKernelPlatform=qemu-arm-virt -DKernelArmHypervisorSupport=OFF -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57` |
| **K2** | K1 with 4 vCPUs | K1 plus `-DKernelMaxNumNodes=4`, nothing else |
| **E1H** (informational) | The kernel configuration of E1 to E3. **Not a matrix row** | K1 with `-DKernelArmHypervisorSupport=ON` |

The compared text is `kernel_all_pp.c`, the preprocessed single translation unit that seL4's verification toolchain starts from (it is the same text as `kernel_all.i`). It keeps comments; the comparison ignores them.

## 1. Build success (and nothing more)

All four builds exit 0, and a second clean build of each in a different directory also does [Measured: [03](A2a/), [04](A2a/04-sums.txt)]. The only warnings are the linker's "LOAD segment with RWX permissions" (all four, as in E1 to E3) and, for K0, a device-tree note about an `iommu` node's mapped size.
**This says that GCC 16.2.0 compiles these configurations, including the verified AArch64 file for `tx2`, which A1 had not shown. It says nothing about whether the compiler's output is correct or that any proof applies to it.**
The kernel binaries of K1, K2 and E1H differ between the two builds and K0's does not [Measured]; the likely cause is a build directory name that the debug builds embed [Inferred].

## 2. Configuration similarity (what the text and the keys show)

K0 is: hypervisor mode **on**, verification build on, release (no debug, no printing), platform `tx2`, 1 node, non-MCS, no SMMU, 16 domains, `-O2`, fastpath on [Measured: [gen_config-K0](A2a/gen_config-K0.json)]. K1 equals A1's recorded kernel configuration and E1H equals E1's [Measured]; K2 differs from K1 in `ENABLE_SMP_SUPPORT` and `MAX_NUM_NODES` only.

| Against K0 | Config keys that differ (of 157) | Functions identical | Functions that differ | Only in K0 | Only in the other |
|---|---|---|---|---|---|
| **E1H** (informational) | 17 | 554 | 322 | 7 | 84 |
| **K1** | 18 | 396 | 338 | 149 | 88 |
| **K2** | 20 | 339 | 389 | 155 | 130 |

Function counts in the preprocessed kernels: K0 883, K1 822, K2 858, E1H 960. The keys that differ for E1H are the platform (`tx2` against `qemu-arm-virt`: six keys), the **debug and printing** keys (`DEBUG_BUILD`, `PRINTING`, `COLOUR_PRINTING`, `IRQ_REPORTING`, `USER_STACK_TRACE_LENGTH`), `VERIFICATION_BUILD`, `ALLOW_SMC_CALLS`,
the domain count and schedule, the bootinfo untyped limit and the timer frequency. K1 and K2 add `ARM_HYPERVISOR_SUPPORT` (and K2 `ENABLE_SMP_SUPPORT`, `MAX_NUM_NODES`). **The hypervisor option is the one K0 and E1H share and K1 and K2 lack.**

Per required property: `identical / differs / only in K0 / only in the other`, over the functions of the files each property depends on. The file lists were **fixed in `a2a-compare.py` before any comparison was run**, from the plan's "kernel code it depends on" column
(a statement I can attest to, not one the repository can prove) [Measured: [comparison.json](A2a/comparison.json), [property-functions.tsv](A2a/property-functions.tsv), one line per function]:

| Property | E1H (info) | K1 | K2 |
|---|---|---|---|
| P1 address-space isolation | 45 / 30 / 0 / 4 | 28 / 39 / 8 / 6 | 25 / 42 / 8 / 6 |
| P2 authority integrity | 59 / 26 / 0 / 0 | 57 / 28 / 0 / 0 | 52 / 33 / 0 / 0 |
| P3 revocation and reclamation | 51 / 20 / 0 / 0 | 49 / 22 / 0 / 0 | 46 / 25 / 0 / 0 |
| P4 kernel integrity | 15 / 18 / 0 / 3 | 12 / 20 / 1 / 3 | 8 / 24 / 1 / 3 |
| P5 kernel part (SMMU files plus P3's) | 51 / 20 / 0 / 0 | 49 / 22 / 0 / 0 | 46 / 25 / 0 / 0 |

Between the others (all functions): E1H and K1 differ in 213 functions, 142 exist only in E1H (hypervisor-only code) and 4 only in K1; K1 and K2 differ in 262, 42 exist only in K2 (SMP) [Measured].
The functions that matter most for E2 and E3 are textually identical to K0 in all three: `cteRevoke`, `cteDelete`, `isMDBParentOf`, `isCapRevocable`, `deriveCap`. `cteInsert`, which the revoke path relies on, is not.

**What the differences consist of [Measured on four sampled functions, not on all]:** `maskCapRights`, `cteMove`, `resolveAddressBits` and `finaliseCap` differ between K0 and E1H by **debug-build code only**: `_assert_fail(...)` and `_fail(...)` where K0 has a bare `;` or `halt()`, and `tcbDebugRemove`.
K0 is a release build and K1, K2 and E1H are debug builds, so a large part of the "differs" columns is probably the debug option and not the hypervisor option, the platform or SMP [Inferred]. **How large was not measured**, and it needs a release variant of the same configurations to separate. That is the largest limit on reading these tables.

## 3. Formal-verification applicability (what the public documentation covers)

Read on 2026-11-09 by a fetch agent from docs.sel4.systems and sel4.systems; the quotes below are its verbatim quotes, **not re-fetched by me** [Documented, with that provenance]. None of the four pages read has a "last updated" line or a version or commit number.

| Point | What the pages say |
|---|---|
| Which configurations | verified-configurations page: "Configurations that start with `AARCH64` are verified configurations for the AArch64 architecture with hypervisor mode enabled. The seL4 kernel runs as hypervisor in EL2." Platforms listed include TX1/TX2. **QEMU virt is not listed** |
| Version | The pages do not name release 17.0.0, commit `62e345c2…` or any version. The FAQ says "The seL4 proofs are updated continuously... usually the head of the master branch" and names no release |
| What is claimed for AArch64 | "C-level functional correctness, including fast path"; "integrity and availability (access control)" and "confidentiality (information flow)"; "Further properties are under development." The FAQ: "Further verification of the 64-bit Arm v8 configuration (AArch64) is in progress." **Binary correctness is not listed for AArch64** on the configurations page (the FAQ's wording on binary proofs is ambiguous) |
| Compiler | "we do _not_ need to trust the compiler and linker any more on architectures that are supported by our binary verification." The pages do not say that AArch64 is one, so for AArch64 the compiler (here GCC 16.2.0) is a trusted component [Inferred from what the pages leave out] |
| SMP | The configurations page does not say whether SMP is in the AArch64 verified configuration (the fetch agent's finding, not a quotation). The FAQ: "Verification of the multicore kernel is in progress for static multikernel configurations" |
| MCS | "The proofs for AARCH64_MCS/ARM_MCS ... are in progress." |
| IOMMU, SMMU, DMA | "At present, none of our verified configurations take into account address translation for devices (System MMU or IOMMU)." "The proof assumes that DMA is off." |
| Not covered | "debug/profiling/printing interfaces, or the kernel startup at boot"; timing channels ("does not cover timing channels"); user space, the Rust root task and loader: not addressed |
| Assumptions | about 340 lines of assembly ("we assume this code is correct"); hardware correct; cache and TLB handling "implemented correctly in the assembly layer"; boot code (about 1,200 lines) excluded; the virtual-memory part ("the proof is not from first principles and there is potential for human error"); "the CPU and MMU are the only devices that access memory directly" |

**What this means for each configuration (the three things kept apart):**
- **K0** builds. It is the configuration the pages describe, for a listed platform. It is not run here, and building it proves nothing.
- **K1, K2, E1H** have *similar* text in part (section 2), but they are **not** verified configurations: the platform is not a listed one, they are debug builds with printing (explicitly outside the proofs), the verification flag is off, and K2 adds SMP, which the pages do not cover. Equal text of a function with K0 shows that the function is the same text. It does not show
  that a proof of that function holds here, because the proof depends on the configuration, the assumptions above and the version, and the pages name no version.
- **E1H** shares the hypervisor option with K0, which K1 and K2 do not. That is a fact about one option. It does not make E1H "closer to verified" in any sense the pages support.

## 4. Cell classification

Rules used, from the plan: A needs identical functions **and** the page's assumptions to hold; B is unmodified seL4 that differs from K0 because of build options, with every differing function named; C is a Fyrkat change (none: the seL4 tree is clean); D is unacceptable (a Class 3 change, an unapproved Class 2 change,
a required test that did not exercise the code, an unlisted trusted component, or a weakened check). "Required tests" are the plan's, and none has run on a matrix configuration.

| Cell | Class | Evidence | Required tests (plan) and state |
|---|---|---|---|
| P1 in K1, K2 | **B** | 39 and 42 functions on the path differ, 8 exist only in K0 (hypervisor code), 6 only in K1 and K2 | B3 cross-client read refused, B4 wild write: **not run** |
| P2 in K1, K2 | **B** | 28 and 33 differ | B4 illegal-capability sub-tests: **not run on K1 or K2**. E2 ran some on E1H, which is not a matrix row, so they do not count |
| P3 in K1, K2 | **B** | 22 and 25 differ; `cteRevoke` and `cteDelete` identical | B1 baseline, B2 revocation: **not run on K1 or K2**. E3 ran on E1H, so it does not count |
| P4 in K1, K2 | **B** | 20 and 24 differ, 1 only in K0, 3 only in the other | B4 1,000 injected faults, B3 pager crash: **not run** |
| P5 in K3 | **cannot be classified** | The kernel part is K2's (P3's files: class B); the SMMU server that the cell lists as a trusted component does not exist, and the cell depends on its design | A5 tests: **not run**; A5 is held for a reviewed design |
| P5 in K4 | not assessed | An in-kernel SMMUv3 driver is Class 3 and unavailable (the pinned tree has SMMUv2 only) | none |
| K0 | reference (V) | compile and compare only | n/a |

Trusted components of the K1 and K2 cells, so that none is omitted (an omitted one makes a cell class D): the kernel (this analysis); the Rust root task (unverified, holds all authority); and a loader or boot stub, **which is not yet decided for K1 and K2**: `sel4-kernel-loader` v6.0.0 starts the kernel at EL2 only [Documented: A3, E1 specification], so it cannot start these non-hypervisor kernels, and seL4's own elfloader (C, unverified) would have to.
The cells are therefore class B on the kernel text with an **open trusted-component entry**, to be settled before A2-final.

**Against the pre-registered expectations** (plan: K1 and K2 expected class B for P1 to P4, "because the hypervisor option differs from K0 and SMP is outside the proofs"): the class is as expected. The stated reason is incomplete: debug and printing, the platform and the verification flag also change functions on every one of these paths, and they apply to E1H too. No surprise in the class; a surprise in the reasons.

## 5. Findings for the owner (none stops A2a)

1. **K1 and K2 do not say whether they are debug or release builds**, and A1's recipe, which became K1, is a debug build. That choice moves a large share of the function-level differences from K0 [Inferred; sampled]. Either the matrix should say which (a release K1 and K2 would be closer to K0), or A2-final should classify both. This is an interpretation of the matrix, not a change of a criterion.
2. **The only verified AArch64 configurations are hypervisor-mode**, and the Rust loader boots only hypervisor-enabled kernels. The plan's K1 and K2 (no hypervisor support) are therefore the *farther* configurations from K0 in that option, and the configuration all of E1 to E3 ran on (E1H) is the nearer one. My earlier handoff text said the opposite, "probably further from K0
   [Inferred]". It was wrong and is corrected. This bears directly on the configuration decision before Stage B (add a hypervisor-enabled row by Amendment, or run Stage B on K1 and K2 with seL4's elfloader).
3. The documentation names no seL4 version. A2-final will have to say that the proofs' revision for the pinned release was **not established**, and it should not be assumed.
4. The matrix says K1 and K2 "run here: under HVF"; A3 showed they do not. They run under TCG only.

## 6. Reproducibility and checking

- **Parser check:** an independent measure: every C function with code in each `kernel.elf`, from `nm`, is in the table; the 20 that are not are the assembly-defined entry points, vectors and data labels (the roughly 340 lines of assembly the proofs assume) [Measured: [05](A2a/05-nm-crosscheck.txt)].
- **Reproducibility:** the function table of every configuration is byte-identical from two clean builds in different directories, and the comparison and the matrix are identical when rerun [Measured: [06](A2a/06-reproducibility.txt)]. A first run found that the table's length column was not (it counted a path embedded by debug assertions); the script was fixed and the whole run repeated.
- **Verifier:** 100 of 100 checks (9 for A2a), `--self-test` 60 of 60 corruptions caught (13 new on the A2a evidence and one for its removal). The A2a check **recomputes the comparison from the published tables and configurations** and requires it to equal the published one; `a2a-compare.py self-test` checks the parser on a sample (attributes, nested braces, braces in strings and comments, path independence).
- The evidence is produced by [`run-a2a-evidence.sh`](../run-a2a-evidence.sh); the preflight and post-run records carry the SHA-256 of the scripts, which the verifier compares with the repository.

## 7. Limitations

- **Text, not semantics.** Only function definitions are compared. Types, global data, macros defined but not used, and the assembly are not. A function that is textually the same may behave differently through a changed type or macro, and functions in headers that are not in a property's file list (including generated bitfield accessors) are counted in the totals but not in a property's row.
- **The file lists are mine,** a starting list in the plan's sense, fixed before the run but not independently checked. A2-final should complete them with the proof documentation.
- **The parser is mine** and fails closed (unbalanced input is an error), and its completeness was checked against `nm`, not against the compiler's own AST.
- **Debug against release** confounds every comparison with K0 (section 2). No release variant of K1, K2 or E1H was built, because it is outside the approved scope; it is the smallest addition that would separate the causes.
- **The documentation was read through a fetch agent,** not by me, and carries no version. Whether the proofs it describes cover the pinned release was not established.
- **K0 is not run.** It is `tx2` hardware only, and was built for comparison.
- **No required test has run on a matrix configuration,** so no cell can be Conditional, and no result here is evidence about isolation, authority or revocation on K1 or K2.

## Evidence

[`A2a/`](A2a/): `00-preflight`, `01-tools`, `02-commands`, `03-build-*` (four logs), `04-sums`, `05-nm-crosscheck`, `06-reproducibility`, `07-post-checks`, `gen_config-*.json`, `functions-*.tsv`, `comparison.json`, `property-functions.tsv`. The `kernel_all_pp.c` files (about 0.7 to 1 MB each) are not published: they hold absolute build paths and the tables are derived from them reproducibly.

| Output (first build) | SHA-256 of `kernel.elf` |
|---|---|
| K0 | `e98c4f79043e3af7…` (the same in the second build) |
| K1 | `d709227d4c9f0c9b…` (second build differs: embedded build directory) |
| K2 | `68a30dabc28cc4d9…` (same remark) |
| E1H | `93b8053addb5c37c…` (same remark) |
