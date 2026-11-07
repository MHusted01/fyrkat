# S1 decision package

- **Status:** Recommendations for the owner, prepared 2026-11-07. This file approves nothing and
  grants nothing. Nothing has been installed, built or run.
- **Goal:** let the owner approve the prerequisites and authorize the first S1 experiments without
  another round of broad research.
- **Inputs:** the [spike plan](sel4-spike-plan.md), the [prerequisites](sel4-spike-prerequisites.md),
  the [C1](../../spikes/sel4-feasibility/results/C1-method.md) and
  [C2](../../spikes/sel4-feasibility/results/C2-method.md) method files, the
  [prior-art review](dma-confinement-prior-art.md), the
  [AI-native requirements](ai-native-requirements.md) and the
  [comparator criteria](comparator-acceptance-criteria.md).

## Answer in one line

**Approve decisions 1 to 7 as recommended, and authorize Stage A through A4 (A1, A2a, A3, A4).**
A5 gets its own design and a separate authorization, because it is the experiment most likely to
falsify the hypothesis and it needs a design reviewed first.

## The eight decisions

Each shows the recommendation, the evidence, and what was rejected. Labels are as in AGENTS.md.

### 1. C1 and C2 method files: approve as drafted

- **Recommend:** approve every interpretation as drafted. For C1: the criterion applies to W1, the
  statistic is the median of 30 run medians, and the kernel is K2. For C2: the headline is cost per
  page touched, Linux keeps its shipped fault-around, the seL4 pager retypes one frame per fault, and
  the statistic is the median of 30 run medians.
- **Evidence:** the published baseline is now fixed in the C1 file. It is the sel4bench Cortex-A57
  row at 1.9 GHz: 419 plus 431 cycles, about 0.45 µs [Documented: `sel4.systems/performance.html`].
  A reviewer pass in a fresh context found the earlier gaps and they were fixed. The retype-per-fault
  choice is the harder one for seL4, which is why it is the headline. The sensitivity run shows the
  amortized case.
- **A2 consequence:** the counter option `KernelArmExportVCNTUser` is a build option on unmodified
  seL4, so the plan's gap classes make it **class B** in A2. It needs the same acceptance as every
  other class B cell, and no special decision.
- **Rejected:** applying the C1 criterion to the 4 KiB workloads. The plan says "round trip" without
  a payload, and W1 is the smallest. The owner can still widen it before the first run.
- **Reversible:** yes, until the first run. After that, only by Amendment.

### 2. Cross-compilers: Homebrew `aarch64-elf-gcc` now, x86-64 later

- **Recommend:** AArch64: `aarch64-elf-gcc` 16.2.0 from Homebrew. x86-64: `x86_64-elf-gcc` 16.2.0,
  installed only when A4 reaches x86-64, with `-DCROSS_COMPILER_PREFIX=x86_64-elf-`.
- **Evidence:** seL4's `gcc.cmake` accepts the prefix `aarch64-elf-` as the last of its five
  AArch64 candidates [Documented]. It looks for `x86_64-linux-gnu-` on macOS and does not search
  `x86_64-elf-`, so that prefix must be passed explicitly [Documented]. Both Homebrew formulae are
  bottled GCC 16.2.0 [Measured: `brew info`]. Arm's alternative is the cask `gcc-aarch64-embedded`,
  version 15.3.rel2 (GCC 15.3.1), whose binaries point into `/Applications/ArmGNUToolchain`
  [Documented: cask file]. Whether it needs administrator rights to install was not checked.
- **Risk, stated:** seL4's published benchmarks used GCC 14.2.0 [Documented]. Whether GCC 16.2.0
  builds seL4 17.0.0 cleanly is **not established**, and it is an A1 finding.
- **Fallback order, as three documented approaches:** the Arm cask, then a digest-pinned container
  (which makes A1 Conditional at best).
- **Rejected:** Nix, and a container first, because the A1 criteria ask for a native build.

### 3. rust-sel4: use `f631577`, and approve it as a dependency

- **Recommend:** adopt `f631577eb7def6fe6fb57fcaf7b8fd61bf144fcc` and its locked dependency tree as
  a git dependency of the spike workspace only. Use the system libclang for `bindgen`. Run
  `cargo deny` on the spike workspace with a spike-local policy that allows exactly the rust-sel4
  git source, and record the output in A1.
- **Evidence:** its `rust-toolchain.toml` pins `nightly-2026-10-28`, the nightly the plan names, so
  adopting it needs no Amendment [Documented]. The release `v6.0.0` pins `nightly-2026-08-21`, which
  would change a pinned input [Documented]. The cost is that `f631577` is 59 commits past the
  release, and A4 compares an unreleased loader [Measured].
- **Fallback:** `v6.0.0`, as a recorded approach with a pinned-input Amendment, if `f631577` does
  not build.
- **Rejected:** crates.io (not published there) and a vendored copy (it would copy upstream
  code into the repository).

### 4. Installation list: three tiers, nothing else

| Tier | When | Install | Where |
|---|---|---|---|
| 1 | Before A1 | rustup `nightly-2026-10-28` with a minimal profile, `rust-src`, `llvm-tools-preview`, `rustc-dev`, and target `aarch64-unknown-none`. Python venv with `sel4-deps==0.9.0` and its requirements pinned with hashes. Homebrew `aarch64-elf-gcc` | rustup home, `spikes/sel4-feasibility/.venv`, Homebrew prefix |
| 2 | Before A4 x86-64 and A5-x86 | Homebrew `x86_64-elf-gcc`, rustup target `x86_64-unknown-none` | Homebrew prefix, rustup home |
| 3 | Before Stage C | The Debian image (hash checked), rustup target `aarch64-unknown-linux-musl` | `spikes/sel4-feasibility/external/` |

- **Not needed:** `repo`, Nix, Docker (unless A1 goes Conditional), protobuf-compiler, `u-boot-tools`.
  Rule: any other missing package stops the work and is asked about.
- **`sel4test` without `repo`:** the `sel4test-manifest` tag `17.0.0` lists the exact revision of each
  project, and its kernel entry is `62e345c240a15671484530b4e6e069ce266c28d7`, the same commit the
  plan pins [Measured: `gh api`]. A3 can fetch those projects with plain `git` at those revisions.
  The manifest on `master` names a different kernel commit, so it must not be used.
- **Reversible:** yes. Everything but the rustup toolchain and Homebrew packages lives in ignored
  directories under `spikes/sel4-feasibility/`.

### 5. Spike workspace files: approve creating them

- **Recommend:** approve `spikes/sel4-feasibility/Cargo.toml` (its own `[workspace]` root),
  `Cargo.lock` and `rust-toolchain.toml` (the Tier 1 nightly). The root workspace and its
  `rust-toolchain.toml` stay unchanged.
- **Evidence:** AGENTS.md gates these files at any depth [Documented]. The existing `cargo xtask check`
  step "spike isolation" already enforces that nothing outside `spikes/` depends on them [Measured:
  the check passes today]. The plan requires the spike to be its own Cargo workspace [Documented].

### 6. Nightly policy: amend `toolchain.md` for spikes only

- **Recommend:** approve this addition to the "Nightly" section of `docs/standards/toolchain.md`:
  "A spike under `spikes/` may use a nightly compiler that its own `rust-toolchain.toml` pins by
  date, when a dependency requires it. Nothing outside `spikes/` may use it, and no shipped artefact
  may be built with it. A spike that needs nightly records which features force it."
- **Evidence:** the current text allows a date-pinned nightly "for analysis tools" and does not name
  this use [Documented]. The plan already treats "User space requires nightly Rust" as a finding
  that reopens the toolchain policy, and A1 records which features force it [Documented].

### 7. Homebrew tools: record versions, do not pin the spike

- **Recommend:** every spike results file records `--version` and the resolved path of CMake, Ninja,
  `dtc`, the cross GCC and QEMU. Extend the toolchain standard's "not pinned" exemption to these
  tools for spikes only. A1's two-clean-builds test runs on one machine in one session, where those
  versions cannot drift.
- **Evidence:** Homebrew cannot pin a version without extracting a formula into a private tap, which
  adds an unreviewed source [Inferred]. The existing standard already exempts QEMU, EDK2, shellcheck
  and actionlint on the same grounds [Documented].
- **Rejected:** hash-pinning builds from source for the spike. It is disproportionate before A1 shows
  whether a native workflow exists at all.

### 8. Execution: authorize Stage A through A4

- **Recommend:** authorize, under the plan and the method files: A1, A2a, A3, A4 (AArch64, then
  x86-64). Sonnet, one agent at a time, and a stop with a report at the end of the stage.
- **Hold:** A5 and everything after it. A5 needs a design (Opus) reviewed first, a Class 1/2/3
  classification of every piece of it, and the [prior-art findings](dma-confinement-prior-art.md)
  applied. Its authorization is a separate, short request. The design must settle how the root
  task's revoke power is handled (opportunity O1), who owns the DMA pool (O3), and how the P5 tests
  are shown to have power (O4). Revoke-while-mapped is the test most likely to decide A5-arm, and
  no published user-level answer exists.
- **Why this split:** A1 to A4 are build-and-boot work with clear pass criteria and no kernel
  change. A5 is where the hypothesis is most likely to fail, so it deserves a design gate.
- **Order and stop rules:** A1 first. If A1 is Fail or Blocked, stop and report, since that falsifies
  the hypothesis. A2a needs A1's preprocessed kernel. A3 needs A1's build. A4 needs A3's boot.

## Proposed Amendments, for the owner to approve or decline

1. Correct the plan's sentence "About 850 cycles is about 0.25 µs at 3.4 GHz". The 850 cycles is the
   Cortex-A57 sum at 1.9 GHz, about 0.45 µs. This is wording and changes no criterion.
2. Adopt the [comparator criteria](comparator-acceptance-criteria.md). Only if the owner wants a
   comparator to remain possible. They add no criterion to A1 to C3.

## Approval checklist

The owner can answer "approved as recommended", or name the numbers to change.

| # | Decision | Recommendation |
|---|---|---|
| 1 | C1 and C2 methods | Approve as drafted |
| 2 | Cross-compilers | `aarch64-elf-gcc` now, `x86_64-elf-gcc` at A4 |
| 3 | rust-sel4 | `f631577` as a dependency, with a spike-local `cargo deny` policy |
| 4 | Installation | Three tiers, Tier 1 now |
| 5 | Workspace files | Approve for `spikes/sel4-feasibility/` only |
| 6 | Nightly policy | Approve the `toolchain.md` addition |
| 7 | Homebrew pinning | Record versions, no pinning |
| 8 | Execution | Authorize A1, A2a, A3, A4 |
| A1 | Wording Amendment | Approve |
| A2 | Comparator criteria | Approve, or decline and keep the draft |

## What happens after approval

1. Merge the preparation PRs (which the owner does), then create the workspace and install Tier 1.
2. Run A1: configure and build seL4 17.0.0 for `qemu-arm-virt`, build the Rust root task, and build
   twice for the identical-output test. Record every command.
3. Report A1, then continue to A2a, A3 and A4 as authorized, and stop at the end of Stage A part 1.
