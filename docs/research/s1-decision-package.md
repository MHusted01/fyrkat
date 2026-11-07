# S1 decision package

- **Status:** Recommendations for the owner, prepared 2026-11-07 and revised after an independent
  review. This file approves nothing and grants nothing. Nothing has been installed, built or run.
- **Goal:** let the owner approve the prerequisites and authorize the first S1 experiments without
  another round of broad research.
- **Inputs:** the [spike plan](sel4-spike-plan.md), the [prerequisites](sel4-spike-prerequisites.md),
  the [C1](../../spikes/sel4-feasibility/results/C1-method.md) and
  [C2](../../spikes/sel4-feasibility/results/C2-method.md) method files, the
  [prior-art note](dma-confinement-prior-art.md), the
  [AI-native requirements](ai-native-requirements.md) and the
  [comparator criteria](comparator-acceptance-criteria.md).
- **Evidence labels** are as in AGENTS.md. [Measured] means a query run on 2026-11-07. The commands
  are listed in the prerequisites file.

## Answer in one line

**Answer decisions 1 to 8 one by one. The recommended answer is "yes" to each, with the choices
marked below, and the recommended authorization is Stage A through A4 (A1, A2a, A3, A4).** A5 gets
its own design gate and a separate authorization, because it is the experiment most likely to
falsify the hypothesis.

## The eight decisions

### 1. C1 and C2 method files: approve, with three choices to confirm

- **Recommend:** approve both files. They fix everything the plan asks them to fix, and the
  published baseline is now in the C1 file.
- **Choice 1a, which C1 workload carries the 1 µs criterion.** Recommended: W1, the empty
  same-core message. **This is the reading most favourable to a Pass.** The plan also lists
  4 KiB same-core work, and W2 is reported in full beside W1. The alternative is to require both
  W1 and W2. The plan says only "same-core round trip", which is why W1 is recommended.
- **Choice 1b, the timing kernel.** C1 and C2 need a release, non-MCS SMP kernel with
  `KernelArmExportVCNTUser` on, because user access to the counter is off by default [Documented:
  `config.cmake`]. The plan's gap class B requires every required test to have passed on that
  configuration [Documented], and no Stage B run is planned on it. Options: **(a, recommended)**
  declare it a **measurement-only configuration outside the A2 matrix**. Stage C numbers are U,
  carry no assurance claim, and A2-final is still taken on K2 as the plan says. **(b)** run the
  Stage B tests on it too, at the cost of one more configuration.
- **Choice 1c, K0.** The plan's K0 row reads "`AARCH64_verified` for a verified board". Recommended,
  and fixed now so that A2a cannot pick the file that suits the result: `AARCH64_verified.cmake`,
  with the platform it sets recorded in the A2 results. Board files such as
  `AARCH64_bcm2711_verified.cmake` are compared as secondary references.
- **Reversible:** until the first run, by ordinary edit. After it, only by Amendment.

### 2. Cross-compilers: Homebrew `aarch64-elf-gcc` now, x86-64 later

- **Recommend:** AArch64: `aarch64-elf-gcc` 16.2.0. x86-64: `x86_64-elf-gcc` 16.2.0, installed only
  when A4 reaches x86-64, with `-DCROSS_COMPILER_PREFIX=x86_64-elf-`.
- **Evidence:** seL4's `gcc.cmake` lists `aarch64-elf-` as the last of five AArch64 prefixes
  [Documented]. On macOS it searches only `x86_64-linux-gnu-` and `x86_64-unknown-linux-gnu-` for
  x86-64, so `x86_64-elf-` must be passed explicitly [Documented]. Both formulae are bottled GCC
  16.2.0 [Measured]. Arm's cask `gcc-aarch64-embedded` is 15.3.rel2 (GCC 15.3.1) and installs from
  a `.pkg` under `/Applications/ArmGNUToolchain`, so it probably needs administrator rights
  [Inferred].
- **Risk, stated:** seL4's published benchmarks used GCC 14.2.0 [Documented]. Whether GCC 16.2.0
  builds seL4 17.0.0 cleanly is **not established**. It is an A1 finding.
- **Fallback, as recorded approaches:** the Arm cask, then a digest-pinned container (A1 Conditional
  at best).

### 3. rust-sel4: use the release `v6.0.0`, and approve its supply chain

- **Recommend:** adopt rust-sel4 tag `v6.0.0` (`c819c27b076130cba9821c4555f23773e4b0bffd`), with the
  root-task demo `c13bdae64a860dfe1d3064717f4096e63bb7dff2` as the known-good recipe, and
  `nightly-2026-08-21`.
- **Why the release now:**
  - `v6.0.0` states compatibility with seL4 17.0.0 [Documented: README, line 37].
  - It is a tagged release, and the demo and its Docker recipe build against exactly that tag
    [Documented].
  - `f631577` is 59 commits later, mostly `sel4-kernel-loader` refactors [Measured]. A4 would then
    evaluate an unreleased loader and the decision would rest on it.
  - Both versions have the same git footprint [Measured]. Choosing `f631577` buys nothing in supply
    chain terms.
- **Cost:** the plan names `nightly-2026-10-28`. Using `v6.0.0` changes a **pinned input** and no
  criterion, so it needs an Amendment (item P1 below). Both nightlies are still downloadable
  [Measured: HTTP 200]. **The no-Amendment alternative is `f631577` with `nightly-2026-10-28`.**
- **What the dependency really is.** Cargo uses the consuming workspace's lock file and `[patch]`
  tables and ignores those of a git dependency [Documented: Cargo Book, not re-fetched this
  session]. rust-sel4 patches `hashbrown` and `ring` to forks, so the spike workspace must replicate
  both patches and seed its lock from upstream. The upstream lock names five git origins besides
  rust-sel4 itself, all under `github.com/coliasgroup`: `dafny`, `hashbrown`, `offset-allocator`,
  `ring` and `rust-embedded-fat` [Measured]. The approval therefore covers **these six git origins**
  (rust-sel4 and those five) and `bindgen` 0.73.2 with the system libclang.
- **Building:** the loader and `sel4-kernel-loader-add-payload` are built from a checkout of
  rust-sel4 at the pin, under `external/`, with its own lock (`--locked`). The spike root task lives
  in the spike workspace, with a seeded lock and the replicated patches.
- **Supply-chain check:** run `cargo deny` with a spike-local policy that allows exactly the six
  origins, on both the spike workspace and the loader checkout, and record the output in A1.
  Root `deny.toml` is not touched.

### 4. Installation: three tiers, and no standing approval for later tiers

| Tier | When | Install |
|---|---|---|
| 1 | Before A1 | rustup `nightly-2026-08-21` with `rust-src`, `llvm-tools-preview`, `rustc-dev`, and target `aarch64-unknown-none`. A Python venv under `spikes/sel4-feasibility/.venv` with `sel4-deps==0.9.0` and its requirements pinned with hashes. Homebrew `aarch64-elf-gcc` |
| 2 | Before x86-64 work in A4 | Homebrew `x86_64-elf-gcc`, rustup target `x86_64-unknown-none` |
| 3 | Before Stage C | The Debian image with its hash checked, rustup target `aarch64-unknown-linux-musl` |

- **Approving this table approves Tier 1 now.** Tiers 2 and 3 are confirmed again at their own gates
  and carry no standing approval.
- **`protobuf`:** probably needed for A3 [Inferred]. The `sel4test` apps link `sel4rpc`, which is
  built with nanopb, and nanopb's CMake needs a working `protoc`. `sel4-deps` 0.9.0 requires only the
  Python `protobuf<4`. If A3 stops on it, the work stops and asks. It is not approved in advance.
- **Not needed:** `repo`, Nix, Docker (unless A1 goes Conditional), `u-boot-tools`.
- **`sel4test` without `repo`:** the `sel4test-manifest` tag `17.0.0` lists each project's revision,
  and its kernel entry is `62e345c240a15671484530b4e6e069ce266c28d7`, the plan's pin [Measured].
  The tag is lightweight, so pin the commit `655b1f2a67de058571b5f653688aa55440745192`. A3 fetches
  the projects with plain `git` at those revisions and recreates the manifest's linkfiles. The
  `master` manifest names a different kernel commit and must not be used.

### 5. Spike workspace files: approve creating them

- **Recommend:** approve `spikes/sel4-feasibility/Cargo.toml` (its own `[workspace]` root),
  `Cargo.lock` and `rust-toolchain.toml` (the Tier 1 nightly). The root workspace and its
  `rust-toolchain.toml` are unchanged.
- **Evidence:** AGENTS.md gates these files at any depth [Documented]. The "spike isolation" step of
  `cargo xtask check` enforces that nothing outside `spikes/` depends on them, and it passes today
  [Measured]. The plan requires the spike to be its own workspace [Documented].
- **Note:** running `cargo xtask` from inside the spike directory would pick up its nightly
  toolchain file. CI does not.

### 6. Nightly policy: amend `toolchain.md` for spikes only

- **Recommend:** approve this addition to the "Nightly" section of `docs/standards/toolchain.md`:
  "A spike under `spikes/` may use a nightly compiler that its own `rust-toolchain.toml` pins by
  date, when a dependency requires it. Nothing outside `spikes/` may use it, and no shipped artefact
  may be built with it. A spike that needs nightly records which features force it."
- **Evidence:** the current text allows a date-pinned nightly "for analysis tools" and does not name
  this use [Documented]. The plan treats "User space requires nightly Rust" as a finding that
  reopens the toolchain policy [Documented].

### 7. Homebrew tools: freeze them, record them, and stop on drift

- **Recommend:** this is stricter than "record versions", because the review showed that installing
  a cross compiler pulls in libraries and could move other tools. Before A1:
  1. Set `HOMEBREW_NO_AUTO_UPDATE=1` and `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1` in the spike
     scripts.
  2. `brew pin` QEMU (a plan-pinned input at 11.1.3, currently **not** pinned [Measured]), the cross
     GCC and its binutils, CMake, Ninja and `dtc`. `brew pin` freezes an installed formula against
     upgrades. It does not choose a version.
  3. Every results file records `--version` and the resolved path of each tool, and the libclang
     version, which follows macOS updates.
  4. If a recorded version changes between A2-final and Stage C, the work stops and the owner is
     told.
- **Why not the toolchain standard's exemption:** the standard exempts QEMU, EDK2, shellcheck and
  actionlint because they do not produce build output. A cross GCC does, and a change in it alters
  the preprocessed `kernel_all.c` that A2 compares [Inferred]. So the compiler is frozen and
  recorded, and the standard is not widened to cover it.
- **Rejected:** hash-pinning builds from source for the spike. It is disproportionate before A1
  shows whether a native workflow exists at all.

### 8. Execution: authorize A1, A3 and A4 with Sonnet, and A2a with Opus

- **Recommend:** authorize, under the plan and the method files: **A1, A3 and A4 (Sonnet), and the
  A2a interpretation (Opus)**, as the plan's model policy assigns them. One agent at a time, and a
  stop with a report at the end of this part of Stage A.
- **Hold A5 and everything after it.** A5 needs a design (Opus), reviewed first, with every piece
  classified as Class 1, 2 or 3, and the [prior-art findings](dma-confinement-prior-art.md) applied.
  The design must settle: how the root task's revoke power is handled, who owns the DMA pool, and
  how the P5 tests are shown to have power.
- **A question the owner must settle before A5 runs** (found by the review). The plan makes a test
  that "did not exercise the code the property rests on" a class D cell, and class D is a Fail that
  falsifies the hypothesis. QEMU completes SMMU commands inside the MMIO write, so a server that
  omits `CMD_SYNC` can pass every P5 test [Measured: `smmuv3.c`]. If that counts as "did not
  exercise", the K3 cell for P5 is class D on this host, whatever the design. **Recommended
  reading:** a test exercises the code if a mutant that omits the step is *detected where QEMU
  models its effect*, and a step whose effect QEMU does not model (completion latency) is
  recorded as an emulator limit that only hardware can close. That reading must be the owner's,
  and it is stated here so that it is not decided by whoever runs A5.
- **Order and stop rules:** A1 first. If A1 is Fail or Blocked, stop and report, because that
  falsifies the hypothesis. A2a needs A1's preprocessed kernel. A3 needs A1's build. A4 needs A3's
  boot.

## Proposed Amendments, for the owner to approve or decline separately

| ID | Amendment | Effect |
|---|---|---|
| P1 | Change the pinned rust-sel4 input to `v6.0.0` with `nightly-2026-08-21` (decision 3). Add it as an Amendment entry, and do not edit the plan inline | Changes a pinned input and no criterion |
| P2 | Correct the plan's sentence "About 850 cycles is about 0.25 µs at 3.4 GHz". The 850 cycles equals the Cortex-A57 sum at 1.9 GHz, about 0.45 µs [Inferred: the plan's source is not named]. The 3.4 GHz clock belongs to the x86-64 rows [Measured: performance page] | Wording only |
| P3 | Adopt the [comparator criteria](comparator-acceptance-criteria.md). This adds rules to Stage D, which the plan treats as fixed. Decline it if no comparator is wanted | A Stage D rule. No criterion in A1 to C3 |
| P4 | Add to B2 the measurement "revoke 1 of 1,000 sibling grants, then count the survivors" (see the [AI-native note](ai-native-requirements.md)) | If it shows a gap, it selects B2's Conditional clause and forces an A2 rerun |

## Approval checklist

Answer each row with "yes" or the change you want. Rows are independent.

| # | Decision | Recommended answer |
|---|---|---|
| 1 | C1 and C2 methods, and choices 1a, 1b (a), 1c | Yes |
| 2 | Cross-compilers | `aarch64-elf-gcc` now, `x86_64-elf-gcc` at A4 |
| 3 | rust-sel4 `v6.0.0`, six git origins, `bindgen`, spike-local `cargo deny` | Yes, with P1 |
| 4 | Tier 1 installation now | Yes. Tiers 2 and 3 later |
| 5 | Workspace files | Yes, for `spikes/sel4-feasibility/` only |
| 6 | Nightly policy text | Yes |
| 7 | Freeze, record and stop on drift | Yes |
| 8 | Authorize A1, A3, A4 (Sonnet) and A2a (Opus). Hold A5 | Yes |
| P1 to P4 | Amendments | P1 and P2 yes. P3 and P4 at the owner's wish |

## What happens after approval

1. The owner decides on pushing and on opening PRs for the preparation branches, since a push or PR
   is a remote action. Nothing here pushes. The method files must be on `main` before any C1 or C2
   run, and A1 to A4 do not depend on that.
2. Create the spike workspace and install Tier 1.
3. Run A1: configure and build seL4 17.0.0 for `qemu-arm-virt`, build the Rust root task, and build
   twice for the identical-output test. Record every command.
4. Report A1, then continue to A3, A4 and A2a as authorized, and stop at the end of this part.
