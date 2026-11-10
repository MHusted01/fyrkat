# A2a: assurance classification of unmodified configurations (no boot)

**Outcome: Investigate** (by the plan's own definition: cells cannot be classified yet and no required test has run). **Not Pass, not Conditional, not Fail.**
Label U for the builds; nothing here is a formal-verification claim. No cell is class A, C or D, and **no cell is yet classified**: the K1 and K2 cells for P1 to P4 are *expected* to be class **B** (as the plan pre-registered; the measurements are consistent with it), but the lists of code that each property depends on were not completed (see section 2), the trusted-component entry is open, and the P5 cell cannot be classified because the SMMU server does not exist.
The plan's A2 can never be Pass in this spike, and A2a cannot reach Conditional before Stage B has run the required tests. A2a only classifies, and lists the functions.

Authorization: the owner's message of 2026-11-09 ("I authorize A2a under the existing S1 plan and its original acceptance criteria"), recorded in the plan's [Amendments](../../../docs/research/sel4-spike-plan.md#amendments). The plan's criteria are not redefined or weakened here.
Scope as approved: build K0 and the pinned verified AArch64 configuration with GCC 16.2.0; K1 and K2 as defined; a reproducible comparison script; the E1 to E3 hypervisor-enabled kernel **as an informational row, outside the approved matrix**; the public seL4 verification documentation.
Not done, by instruction: any change to kernel or loader source, dependency pins, ADR statuses or the Stage B matrix; Stage B, A4, A5 implementation, the comparator.

## What was built

All four with `aarch64-elf-gcc (GCC) 16.2.0`, CMake 4.4.5, Ninja 1.13.2, the pinned seL4 `62e345c2…` (clean checkout, no change), the hash-pinned Python environment; kernel only, nothing booted [Measured: [01](A2a/01-tools.txt), [02](A2a/02-commands.txt)].

| ID | Meaning | Command, in short |
|---|---|---|
| **K0** | The plan's reference (decision 1c): `AARCH64_verified.cmake` | `cmake -C configs/AARCH64_verified.cmake`, `ninja kernel.elf`, `ninja kernel_all_pp_wrapper`. The page documents `cmake -P ../config/ARM_verified.cmake`, which runs the same `-C` and `ninja` steps internally (`tools/helpers.cmake`, `cmake_script_build_kernel`); this form was used so that the commands are recorded. Compile and compare only |
| **K1** | AArch64 `qemu-arm-virt`, no hypervisor support, 1 vCPU: A1's recipe | `-DKernelPlatform=qemu-arm-virt -DKernelArmHypervisorSupport=OFF -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57` |
| **K2** | K1 with 4 vCPUs | K1 plus `-DKernelMaxNumNodes=4`, nothing else |
| **E1H** (informational) | The kernel configuration of E1 to E3. **Not a matrix row** | K1 with `-DKernelArmHypervisorSupport=ON` |

The compared text is `kernel_all_pp.c`, the preprocessed single translation unit that seL4's verification toolchain starts from (it is the same text as `kernel_all.i`). It keeps comments; the comparison ignores them.

## 1. Build success (and nothing more)

All four builds exit 0, and a second clean build of each in a different directory also does [Measured: [03](A2a/), [04](A2a/04-sums.txt)]. The only warnings are the linker's "LOAD segment with RWX permissions" (all four, as in E1 to E3) and, for K0, a device-tree note about an `iommu` node's mapped size.
**This says that GCC 16.2.0 compiles these configurations, including the verified AArch64 file for `tx2`, which A1 had not shown. It says nothing about whether the compiler's output is correct or that any proof applies to it.**
The kernel binaries of K1, K2 and E1H differ between the two builds and K0's does not [Measured]; the likely cause is a build directory name that the debug builds embed [Inferred].

## 2. Configuration similarity (what the text and the keys show)

K0 is: hypervisor mode **on**, verification build on, release (no debug, no printing), platform `tx2`, 1 node, non-MCS, no SMMU, 16 domains, fastpath on [Measured: [gen_config-K0](A2a/gen_config-K0.json)]. K1 equals A1's recorded kernel configuration and E1H equals E1's [Measured]; K2 differs from K1 in `ENABLE_SMP_SUPPORT` and `MAX_NUM_NODES` only.

| Against K0 | Config keys that differ (of 157) | Functions identical | Functions that differ | Only in K0 | Only in the other |
|---|---|---|---|---|---|
| **E1H** (informational) | 17 | 554 | 322 | 7 | 84 |
| **K1** | 18 | 396 | 338 | 149 | 88 |
| **K2** | 20 | 339 | 389 | 155 | 130 |

Function counts in the preprocessed kernels: K0 883, K1 822, K2 858, E1H 960. The keys that differ for E1H are the platform (`tx2` against `qemu-arm-virt`: six keys), the **debug and printing** keys (`DEBUG_BUILD`, `PRINTING`, `COLOUR_PRINTING`, `IRQ_REPORTING`, `USER_STACK_TRACE_LENGTH`), `VERIFICATION_BUILD`, `ALLOW_SMC_CALLS`,
the domain count and schedule, the bootinfo untyped limit and the timer frequency. K1 and K2 add `ARM_HYPERVISOR_SUPPORT` (and K2 `ENABLE_SMP_SUPPORT`, `MAX_NUM_NODES`). **The hypervisor option is the one K0 and E1H share and K1 and K2 lack.**

Per required property: `identical / differs / only in K0 / only in the other`, over the functions in the files listed in `PROPERTY_FILES` of `a2a-compare.py` (the plan's starting list, mapped file by file). The lists were written before the first extraction ran and were not changed between the two runs; the first run's outputs were not kept (unlike E2's and E3's superseded runs), so the repository cannot show that no result had been seen
[Measured: [comparison.json](A2a/comparison.json), [property-functions.tsv](A2a/property-functions.tsv), one line per function]:

| Property | E1H (info) | K1 | K2 |
|---|---|---|---|
| P1 address-space isolation | 45 / 30 / 0 / 4 | 28 / 39 / 8 / 6 | 25 / 42 / 8 / 6 |
| P2 authority integrity | 59 / 26 / 0 / 0 | 57 / 28 / 0 / 0 | 52 / 33 / 0 / 0 |
| P3 revocation and reclamation | 51 / 20 / 0 / 0 | 49 / 22 / 0 / 0 | 46 / 25 / 0 / 0 |
| P4 kernel integrity | 15 / 18 / 0 / 3 | 12 / 20 / 1 / 3 | 8 / 24 / 1 / 3 |
| P5 kernel part (SMMU files plus P3's) | 51 / 20 / 0 / 0 | 49 / 22 / 0 / 0 | 46 / 25 / 0 / 0 |

Between the others (all functions): E1H and K1 differ in 213 functions, 142 exist only in E1H (hypervisor-only code) and 4 only in K1; K1 and K2 differ in 262, 42 exist only in K2 (SMP) [Measured].
**What the lists leave out [Measured, from the published tables].** Of the functions that differ from K0, those in **no** property file list: K1 259 of 338 (148 generated accessors, 43 in headers, 68 in other `.c` files), K2 299 of 389 (145, 54, 100), E1H 254 of 322 (159, 28, 67). Several are on the property paths: `cap_endpoint_cap_set_capEPBadge` (badges, P2) and `mdb_node_get_mdbNext` (the derivation tree, P3) in the generated accessors;
`decodeTCBInvocation` and `decodeSetSpace` in `src/object/tcb.c` (P1, P2, P4); `sanitiseRegister` (P4); `armv_contextSwitch` and `invalidateLocalTLB_ASID` (P1). **The plan says A2a "completes" the dependency lists "per configuration, from the proof documentation and the preprocessed source". A2a did not: it used the starting list.** That is a departure from the plan, recorded in the Amendments; the lists are to be completed in A2b, now that the proof documentation can be tied to the pinned release (section 3).
Until then the P1 to P4 cells of K1 and K2 are *expected* class B and not assigned one.

**Named path functions [Measured, against K0].** Identical in K1, K2 and E1H: `cteRevoke`, `cteDelete`, `isMDBParentOf`, `isCapRevocable`, `deriveCap`, `invokeUntyped_Retype`, `resetUntypedCap`. Different in all three: `cteInsert`, `cteDeleteOne`, `reduceZombie`, `finaliseCap`, `createObject`, `Arch_createObject`, `decodeUntypedInvocation`, `decodeTCBInvocation`, `decodeSetSpace`, `cap_endpoint_cap_set_capEPBadge`, `sanitiseRegister`, `invalidateLocalTLB_ASID`.
Different in K1 and K2 but identical in E1H: `Arch_finaliseCap`, `mdb_node_get_mdbNext`, `armv_contextSwitch`. Identical text of the first group says nothing about the second: `finaliseCap` and `createObject` are on every revoke and reclamation path.

**What the differences consist of [Measured on four sampled functions, not on all]:** `maskCapRights`, `cteMove`, `resolveAddressBits` and `finaliseCap` differ between K0 and E1H by **debug-build code only**: `_assert_fail(...)` and `_fail(...)` where K0 has a bare `;` or `halt()`, and `tcbDebugRemove`.
K0 is a release build and K1, K2 and E1H are debug builds, so a large part of the "differs" columns is probably the debug option and not the hypervisor option, the platform or SMP [Inferred]. **How large was not measured** here (the release variants are measured in a follow-up, not part of this record). Some differences change behaviour and not only add checks [Measured on two functions]: in `sanitiseRegister` the user's saved status register leaves SError unmasked in the debug builds (K0: `(1 << 8)`, K1: `0`; the source comment says "We cannot allow async aborts in the verified kernel"), and `createObject` writes debug thread names.
The hypervisor option changes behaviour too: `mdb_node_get_mdbNext` sign-extends pointers with `0xffff000000000000` in K1 and K2, and not in K0 or E1H.

## 3. Formal-verification applicability (what the public documentation covers)

Read on 2026-11-09 by a fetch agent from docs.sel4.systems and sel4.systems, then **re-fetched with `curl` by the independent reviewer (all four pages) and by me (the FAQ, the proofs, assumptions and configurations pages)**; the quotes below are verbatim, apart from the shortening marked by an ellipsis [Documented].
The first version of this section said the pages name no seL4 version and used an ellipsis that removed the sentence that says otherwise; the review found it.

| Point | What the pages say |
|---|---|
| Which configurations | Configurations page: "Configurations that start with `AARCH64` are verified configurations for the AArch64 architecture with hypervisor mode enabled. The seL4 kernel runs as hypervisor in EL2." Platforms include TX1/TX2. **QEMU virt is not listed.** All 16 `configs/AARCH64_*_verified.cmake` files of the pinned tree include `AARCH64_verified_include.cmake`, which sets `KernelArmHypervisorSupport ON` [Measured by the reviewer; K0's own configuration has it on] |
| Which version | The FAQ: "you can see the kernel revision the proof currently refers to in https://github.com/seL4/verification-manifest/blob/master/default.xml. This is usually the head of the master branch." In that repository, `17.0.0.xml` pins `seL4 revision="62e345c240a15671484530b4e6e069ce266c28d7"` (the pinned commit), `l4v` `12c300e75bb0…` and `Isabelle2025-2` [Documented; read by me and by the reviewer]. **So the release is tied to a proof revision.** The manifest does not by itself show which proof sessions (refinement, access control, information flow for AArch64) were built and checked for it; the reviewer found `AARCH64` directories under the l4v `crefine`, `access-control` and `infoflow` proof trees at that commit and none under `asmrefine`, which is consistent with the pages but is a directory listing, not a check |
| What is claimed for AArch64 | Configurations page: "C-level functional correctness, including fast path"; "integrity and availability (access control)"; "confidentiality (information flow)". FAQ: "For 64-bit Arm v8 and x86 there are functional-correctness proofs to C code, and for 64-bit RISC-V there are functional-correctness proofs to binary code as well as security proofs. Further verification of the 64-bit Arm v8 configuration (AArch64) is in progress." **The two pages differ on AArch64 security proofs** (the configurations page lists them, the FAQ credits security proofs to RISC-V); this is not resolved here. **Binary correctness is not claimed for AArch64** on either page |
| Compiler | Assumptions page: "Note that we do not need to trust the compiler and linker any more on architectures that are supported by our binary verification." AArch64 is not claimed to be one, so the compiler and linker (here GCC 16.2.0 and its binutils) are trusted components of any AArch64 cell [Inferred from what both pages say and do not say] |
| SMP | The proofs page names "multicore SMP" among "mature unverified configurations of the kernel". The FAQ: "Verification of the multicore kernel is in progress for static multikernel configurations". The configurations page does not say SMP is in the AArch64 verified configuration, and K0 has one node |
| MCS | "The proofs for AARCH64_MCS/ARM_MCS ... are in progress." |
| IOMMU, SMMU, DMA | "At present, none of our verified configurations take into account address translation for devices (System MMU or IOMMU), debug/profiling/printing interfaces, or the kernel startup at boot." FAQ: "The formal verification of seL4 assumes that the MMU has complete control over memory, which means the proof assumes that DMA is off." |
| Timing | Assumptions page: "in practice the proof covers all in-kernel storage channels but does not cover timing channels" |
| Not addressed | User space, the Rust root task, the loader |
| Assumptions | "about 340 lines of ARM assembly... For the proof, we assume this code is correct"; the hardware works; cache and TLB handling "implemented correctly in the assembly layer"; the boot code (about 1,200 lines) is outside the proof; the virtual-memory part: "the proof is not from first principles and there is potential for human error"; DMA: "we assume that the CPU and MMU are the only devices that access memory directly" |

**What this means for each configuration (the three things kept apart):**
- **K0** builds. It is the configuration the pages describe, for a listed platform. It is not run here, and building it proves nothing.
- **K1, K2, E1H** have *similar* text in part (section 2), but they are **not** verified configurations: the platform is not a listed one, they are debug builds with printing (explicitly outside the proofs), the verification flag is off, and K2 adds SMP, which the pages do not cover. Equal text of a function with K0 shows that the function is the same text. It does not show that a proof of that function holds here:
  the proof depends on the configuration, on the assumptions above and on the revision, and several of those fail even though the revision is now known for the release.
- **E1H** shares the hypervisor option with K0, which K1 and K2 do not. That is a fact about one option. It does not make E1H "closer to verified" in any sense the pages support.

## 4. Cell classification

Rules used, from the plan: A needs identical functions **and** the page's assumptions to hold; B is unmodified seL4 that differs from K0 because of build options, **with every differing function on the property's path named**; C is a Fyrkat change (none: the seL4 tree is clean); D is unacceptable (a Class 3 change, an unapproved Class 2 change, a required test that did not exercise the code,
an unlisted trusted component, or a weakened check). "Required tests" are the plan's, and none has run on a matrix configuration.

**No cell is assigned a class yet.** B requires every differing function on the path to be named, and the path lists were not completed (section 2); the trusted-component entry is open (below).

| Cell | State | Evidence | Required tests (plan) and state |
|---|---|---|---|
| P1 to P4 in K1, K2 | **not yet classifiable; expected B** | In the files of the starting lists 22 to 42 functions per property differ (section 2); many more differ outside the lists, some on the paths (section 2) | B3, B4 (P1, P4), B4 illegal-capability sub-tests (P2), B1 and B2 (P3): **not run on K1 or K2**. E2 and E3 ran on E1H, which is not a matrix row, so they do not count |
| P1 to P4 in K3 | **not yet classifiable; expected B** | The kernel part is K2's (the plan: "K3 is expected to be class B for P1 to P4") | as for K2 |
| P5 in K3 | **cannot be classified** | The kernel part is K2's (P3's files plus the SMMU files, which contribute no functions because `ARM_SMMU` is off everywhere); the SMMU server that the cell lists as a trusted component does not exist, and the cell depends on its design | A5 tests: **not run**; A5 is held for a reviewed design |
| P5 in K4 | not assessed | The plan expected class C. The owner's decision of 2026-11-07 that an in-kernel SMMUv3 driver is Class 3 and unavailable overtakes that expectation (the pinned tree has SMMUv2 only) | none |
| K0 | reference (V) | compile and compare only | n/a |

Trusted components of the K1, K2 and K3 cells, so that none is omitted (an omitted one makes a cell class D): the **kernel** (this analysis); the **compiler and linker** (GCC 16.2.0 and its binutils: AArch64 has no binary-verification claim); the **assembly** (about 340 lines, assumed correct by the proofs) and the **boot code** (outside them); the **Rust root task** (unverified, holds all authority);
the **hardware and the DMA assumption**; and a **loader or boot stub, which is not decided for K1 and K2**: `sel4-kernel-loader` v6.0.0 starts the kernel at EL2 only [Documented: A3, E1 specification], so it cannot start these non-hypervisor kernels, and seL4's own elfloader (C, unverified) would have to. The entry stays open until A2-final.

**Against the pre-registered expectations** (plan: K1 and K2 expected class B for P1 to P4, "because the hypervisor option differs from K0 and SMP is outside the proofs"): consistent, with every cell having differing functions and none a class A candidate. The stated reason is incomplete: debug and printing, the platform and the verification flag also change functions on every one of these paths, and they apply to E1H too.

## 5. Findings for the owner (none stops A2a)

1. **K1 and K2 do not say whether they are debug or release builds**, and A1's recipe, which became K1, is a debug build. That choice moves a large share of the function-level differences from K0 [Inferred; sampled]. Either the matrix should say which, or A2-final should classify both. This is an interpretation of the matrix, not a change of a criterion.
2. **Every AArch64 verified configuration is hypervisor-mode** (K0, and all 16 `AARCH64_*_verified` files of the pinned tree), and the Rust loader boots only hypervisor-enabled kernels. The plan's K1 and K2 (no hypervisor support) therefore differ from K0 in that option, and the E1H configuration that E1 to E3 ran on does not. This corrects an earlier handoff statement. It bears on the configuration decision before Stage B.
3. **The documentation does tie the pinned release to a proof revision** (the 17.0.0 verification manifest, section 3), which the first version of this record denied. A2-final should use it, and should also check which proof sessions exist for the AArch64 configuration.
4. **No loader is known to start K2** (and so K3). A3 recorded that the 4-node non-hypervisor kernel aborts in seL4's own elfloader under TCG too ("HVC is not supported for PSCI"), and that it "has not been shown to boot anywhere"; the Rust loader cannot start a non-hypervisor kernel. K1 has run only A3's sel4test userland under the elfloader (the A1 root task has never booted on it). The matrix's "Runs here: under HVF" for K1 and K2 contradicts A3's Fail; K1 runs under TCG.
5. **A2a did not complete the dependency lists** the plan asks it to complete (section 2). That is a departure, recorded in the Amendments, and A2b should do it.

## 6. Reproducibility and checking

- **Parser check, two ways.** (1) Every C function with code in each `kernel.elf`, from `nm`, is in the table; the 20 that are not are assembly-defined entry points and vectors, C constant data in the boot section (`kernel_device_frames`, `avail_p_regs`, `kernel_device_reserved_regions`) and a linker symbol (`ki_boot_end`) [Measured: [05](A2a/05-nm-crosscheck.txt)].
  (2) The independent reviewer extracted the functions a second way, from clang's AST and token locations: the same name sets (883, 822, 858, 960), the same source file for every function, and the same identical-or-different verdict for every function in the pairs tested [Measured by the reviewer]. For this data, removing comments and collapsing whitespace hides no difference and creates none.
- **Reproducibility:** the function table of every configuration is byte-identical from two clean builds in different directories, and the comparison and the matrix are identical when rerun [Measured: [06](A2a/06-reproducibility.txt)]. The reviewer rebuilt all four in a third directory and with the seL4 checkout in a different place, and reproduced the published tables, `comparison.json` and `property-functions.tsv` byte for byte.
  A first run found that the table's length column was not (it counted a path embedded by debug assertions); the script was fixed and the whole run repeated.
- **Verifier:** the A2a checks **recompute the comparison from the published tables and configurations** and require it to equal the published one; they also compare each table's hash and count with the reproducibility record, and the set of configurations with the expected four. `a2a-compare.py self-test` checks the parser on a sample (attributes, nested braces, braces in strings and comments, path independence).
  **What the verifier cannot do:** it does not link the tables to the kernels. The reviewer made seven consistent forgeries (tables edited, rows dropped, K1 and K2 swapped) that the first version of the verifier accepted; the checks above close some of them, and the rest are disclosed: the tables are tied to the kernels only by the author's `nm` record and by the reviewer's independent rebuild.
- The evidence is produced by [`run-a2a-evidence.sh`](../run-a2a-evidence.sh); the preflight and post-run records carry the SHA-256 of the scripts, which the verifier compares with the repository.

## 7. Limitations

- **Text, not semantics.** Only function definitions are compared. Types, global data, macros defined but not used, and the assembly are not. A function that is textually the same may behave differently through a changed type or macro.
- **The dependency lists are the plan's starting list, mapped file by file, and too narrow** (section 2): headers, generated bitfield accessors, `tcb.c`, `thread.c` and `interrupt.c` are outside every property. They were written before the first extraction and not changed, but the repository cannot show it.
- **QEMU is an undeclared build input.** For K1, K2 and E1H, CMake runs `qemu-system-aarch64` (11.1.3) to extract the device tree; the version is not in `01-tools.txt`. The extracted trees are not byte-reproducible (the reviewer's differ from mine, probably because of random seeds in them [Inferred]); the function tables are identical regardless. K0 needs no QEMU. Recording it in the script would change a hashed file, so it is disclosed here.
- **Debug against release** confounds every comparison with K0 (section 2); the release variants are a separate follow-up, not part of this record.
- **The parser is mine.** It fails closed on unbalanced input and agrees with an independent extraction on this data, but three latent edge cases exist that this data does not trigger: a function that returns a function pointer would be named "void", a block comment is removed without leaving a space (so tokens on either side could merge), and lines that start with `#` inside a function body are dropped. Fixing any of them changes a hashed script; they wait for A2b.
- **The ELF differences between builds** (K1, K2, E1H differ, K0 does not) are build paths embedded in the debug kernels: K1's ELF contains 11 build-path strings and K0's none [Measured by the reviewer].
- **K0 is not run.** It is `tx2` hardware only, and was built for comparison.
- **No required test has run on a matrix configuration,** so no cell can be Conditional, and no result here is evidence about isolation, authority or revocation on K1 or K2.
- **The final `-O2` of K0** is in `CMakeCache.txt`, which is not published, and not in `gen_config.json`.

## Evidence

[`A2a/`](A2a/): `00-preflight`, `01-tools`, `02-commands`, `03-build-*` (four logs), `04-sums`, `05-nm-crosscheck`, `06-reproducibility`, `07-post-checks`, `gen_config-*.json`, `functions-*.tsv`, `comparison.json`, `property-functions.tsv`. The `kernel_all_pp.c` files (about 0.7 to 1 MB each) are not published: they hold absolute build paths and the tables are derived from them reproducibly.

| Output (first build) | SHA-256 of `kernel.elf` |
|---|---|
| K0 | `e98c4f79043e3af7…` (the same in the second build) |
| K1 | `d709227d4c9f0c9b…` (second build differs: embedded build directory) |
| K2 | `68a30dabc28cc4d9…` (same remark) |
| E1H | `93b8053addb5c37c…` (same remark) |
