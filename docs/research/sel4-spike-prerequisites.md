# seL4 spike prerequisites

- **Status:** Draft, prepared 2026-11-07 and revised after an independent review. Nothing in this
  file has been installed, built or run.
- **Plan:** [spike plan](sel4-spike-plan.md), approved at `46a90fa`. This file adds no criterion and
  changes none.
- **Purpose:** list what Stage A needs, propose pins for the inputs the plan leaves open, and name
  every decision the owner must make before the spike can start.
- **Authority:** this file grants nothing. Execution, tool installation and new global tools stay
  under the plan's [Scope limits](sel4-spike-plan.md#scope-limits).

Evidence labels are as in [AGENTS.md](../../AGENTS.md). Upstream file contents read at a named
commit are [Documented]. Query results are [Measured], and the commands are listed under
[Reproducing the queries](#reproducing-the-queries). "Present" means found on this Mac by a version
query on 2026-11-07. This work installed nothing.

## Pinned inputs

| Input | Value | Label |
|---|---|---|
| seL4 | `17.0.0`, commit `62e345c240a15671484530b4e6e069ce266c28d7` ("Release 17.0.0", 2026-10-30). The tag object is `ab504cd497d239ed7341472b7f67b56f4c42dbe1` | Measured |
| rust-sel4 (proposed) | `f631577eb7def6fe6fb57fcaf7b8fd61bf144fcc` ("nix: Update Verus", 2026-11-05), tip of `main`. `VERSION` says `6.0.0-dev`. Unsigned on GitHub. It is 59 commits after the release below | Measured |
| rust-sel4 (alternative) | Tag `v6.0.0`, commit `c819c27b076130cba9821c4555f23773e4b0bffd` (2026-10-30). Its `rust-toolchain.toml` pins `nightly-2026-08-21` | Measured, Documented |
| rust-sel4 toolchain at the proposed commit | `nightly-2026-10-28`, the nightly the plan names | Documented: upstream `rust-toolchain.toml` |
| rust-sel4 compatibility | "seL4 version 17.0.0" and "seL4 Microkit version 2.4.0", described as "at least" these versions | Documented: upstream README at the proposed commit |
| Root-task demo | `seL4/rust-root-task-demo` `c13bdae64a860dfe1d3064717f4096e63bb7dff2` ("Update everything", 2026-11-04). It depends on rust-sel4 `tag = "v6.0.0"` and pins `nightly-2026-08-21`. It is a reference for the **release**, not for the proposed commit | Documented, Measured |
| QEMU | `11.1.3`, from Homebrew, as the plan pins | Measured |
| Linux guest for C2 | Debian 13 `debian-13-nocloud-arm64-20261103-2651.qcow2`, SHA-512 `f99c23f0d4c18ba7512bae254a201b72dafe11ef0c69beac489a2daba4e128171ca5dcfcdc6d76c2b81a8aa17fc6da8ced2d0a3b9442c97358b3e99ed6668ca7`. Its manifest lists `linux-image-6.12.115+deb13.1-arm64`. Not downloaded, so the hash is not checked against a file. The checksum file is unsigned, so the hash rests on HTTPS | Documented: `SHA512SUMS` and the image `.json` manifest |

**The rust-sel4 choice.** The plan records the commit "at the start of A1". This file proposes one so
the owner can review it. The two candidates trade off as follows:

| | `f631577` (main) | `v6.0.0` (release) |
|---|---|---|
| Nightly | `nightly-2026-10-28`, matching the plan | `nightly-2026-08-21`, which differs from the plan's pin |
| Maturity | Unreleased, 59 commits after the release, with heavy `sel4-kernel-loader` changes and a toolchain bump | A tagged release |
| Demo | None matches | The root-task demo matches |
| A4 | The loader compared is the unreleased one | The released loader |

This file proposes `f631577`, because the plan names its nightly. The owner decides (see
[decisions](#decisions-for-the-owner)). If the choice later fails to build, switching is recorded as
an approach in the A1 results. Whether that counts toward the plan's three-approach Blocked rule is
the owner's call.

**Note on the plan's K0.** At the pinned seL4 commit `configs/` holds `AARCH64_verified.cmake` and
many board files such as `AARCH64_bcm2711_verified.cmake` and `AARCH64_bcm2712_verified.cmake`, and
`X64_verified.cmake`. The plan says K0 is a verified board, so A2a chooses the board file. That
choice is not made here.

## Tool list

| Tool | Needed for | Pin | State | Install needs approval |
|---|---|---|---|---|
| QEMU `qemu-system-aarch64` and `qemu-system-x86_64` | A3, A4, A5, Stage B and C | 11.1.3 | Present, Homebrew | No |
| EDK2 firmware `edk2-aarch64-code.fd`, `edk2-x86_64-code.fd` | A4 | Version not recorded | Present, in Homebrew's QEMU share | No. Record the version at A4 |
| CMake | seL4 build | seL4 asks for 3.16.0 or later [Documented: `CMakeLists.txt`] | 4.4.5 present. Whether seL4 17.0.0 configures under CMake 4 is **not tested** | No |
| Ninja, `dtc` | seL4 build | Homebrew cannot pin a version. See decision 7 | 1.13.2 and 1.8.1 present | No |
| `xmllint` | seL4 build [Documented: seL4 host-dependencies page] | System | Present | No |
| libclang | `bindgen` in the `sel4-sys` crate [Documented: `crates/sel4/sys/Cargo.toml` lists `bindgen` 0.73.2 as a build dependency] | Not decided | `/Library/Developer/CommandLineTools/usr/lib/libclang.dylib` exists. Not tested with `bindgen` | No, if that library is used |
| Other host packages named on seL4's host-dependencies page for Linux: `protobuf-compiler`, `xxd`, `u-boot-tools`, `ccache` | seL4 build | Not decided | Not checked. The page assumes a Linux host [Documented] | Probably, for any that are missing |
| Rust `nightly-2026-10-28` (or the nightly of the chosen release) with `rust-src`, `llvm-tools-preview`, `rustc-dev`, and targets `aarch64-unknown-none`, `x86_64-unknown-none`, `aarch64-unknown-linux-musl` | A1, A4, A5, B, C | Date-pinned | **Absent.** Only stable 1.99.1, 1.88 and a default `stable` are installed | **Yes.** Pending in the handoff |
| Python virtual environment with `sel4-deps` | seL4 build scripts | `sel4-deps==0.9.0` [Documented: PyPI]. Its 19 requirements need pins with hashes. `requires_python` is only `>=3`, and the host has Python 3.15.0, whose fit is **not tested** | **Absent** | **Yes**, a new environment and packages |
| AArch64 cross GCC | seL4 kernel build | See decision 2 | **Absent** | **Yes** |
| x86-64 cross GCC | X1 for A4 and A5-x86 | See decision 2 | **Absent.** On macOS seL4's `gcc.cmake` looks for `x86_64-linux-gnu-` and `x86_64-unknown-linux-gnu-` compilers [Documented: `gcc.cmake`, lines 90 to 101] | **Yes** |
| `sel4-kernel-loader` and `sel4-kernel-loader-add-payload` | A4 comparison, and the upstream boot path | Built from the rust-sel4 pin | Not built | Built by the spike. Covered by the owner's decision on rust-sel4 and the nightly, once given |
| seL4's own loader (`elfloader` in `seL4_tools`) | A4 comparison | Commit chosen at A4 start | Not fetched | Fetch is part of the spike. Confirm at the gate |
| `sel4test` and the `repo` tool | A3 | Commits chosen at A3 start | Not fetched. `repo` not checked | `repo` is a new tool, so yes |
| Docker | A1 Conditional path only | Image by digest, never a tag | 29.8.2 present | Only if A1 needs it |
| Linux guest image, as above | C1 baseline, C2 | SHA-512 above | Not downloaded | Yes, a new download |
| Nix | Upstream's own `hacking` route | | Absent | Not proposed |

**Cross-compiler prefixes.** For AArch64, seL4's `gcc.cmake` looks in order for `aarch64-linux-gnu-`,
`aarch64-unknown-linux-gnu-`, `aarch64-none-linux-gnu-`, `aarch64-none-elf-` and `aarch64-elf-`
[Documented]. The pinned seL4 does not name a source for any of them.

**Upstream build routes.** Two exist, and they differ:

- The **rust-sel4 repository's** `hacking/docker/Dockerfile` starts `FROM debian:bookworm`, a tag and
  not a digest, and installs Nix [Documented].
- The **root-task demo's** `docker/Dockerfile` also starts `FROM debian:bookworm`. It installs
  `gcc-aarch64-linux-gnu`, builds seL4 after `pip install tools/python-deps` with
  `-DCROSS_COMPILER_PREFIX=aarch64-linux-gnu-` and `-DKernelArmHypervisorSupport=ON`, and installs the
  loader from `tag="v6.0.0"`. It does not use Nix [Documented]. Its `Makefile` boots with
  `-machine virt,virtualization=on`. That is a hypervisor build and not K1 or K2, which have no
  hypervisor support, so the demo is a starting point only.

The A1 criteria ask for a native build on this Mac. Container use is the Conditional outcome, and
this file does not prejudge it.

**Harness language.** The C1 and C2 harnesses are Rust. The Linux-side harness is built as static
`aarch64-unknown-linux-musl`, so the Debian guest needs no compiler. Whether the musl target links
on macOS without an extra linker is **not tested**.

## Facts that affect the spike

- **Spike workspace files need approval.** AGENTS.md puts `Cargo.toml`, `Cargo.lock` and
  `rust-toolchain.toml` at any depth under owner approval. The plan puts the spike in its own Cargo
  workspace under `spikes/sel4-feasibility/`. Creating that workspace's manifest, lock file and
  toolchain file is therefore an owner decision, and this work created none. [Documented]
- **rust-sel4 is a new dependency.** AGENTS.md requires owner approval for a new dependency. It is a
  git source with unsigned commits, with its own crates.io tree and `bindgen` as a build dependency,
  which loads libclang. The root `deny.toml` denies unknown git sources, but `cargo deny` runs on
  the root workspace only, so a spike workspace gets no supply-chain check unless the owner directs
  one. [Documented, Inferred]
- **The nightly policy.** `docs/standards/toolchain.md` allows a date-pinned nightly "for analysis
  tools", installed on demand, and never for a shipped artefact. Spike code is never shipped. The
  policy does not cover this use by name, and the plan's Consequences table says that "User space
  requires nightly Rust" reopens the toolchain policy [Documented: both files]. The owner should
  confirm that the installation is covered.
- **Where fetched content goes.** The plan puts seL4 in a gitignored directory. This work adds
  `.gitignore` entries for `/spikes/sel4-feasibility/external/` (seL4, `seL4_tools`, `sel4test`,
  rust-sel4 checkouts and the Linux image), `/spikes/sel4-feasibility/build/` and
  `/spikes/sel4-feasibility/.venv/`, so an accidental `git add` cannot commit GPL-2.0 kernel code
  or build output, and so repository checks do not scan them. The convention is
  `external/<name>` for every fetched tree. Nothing is fetched yet. [Documented: `.gitignore`]
- **Core mix.** The host has 6 performance and 4 efficiency cores [Measured]. C3's 8-vCPU run uses
  most of them, and the plan already requires the mix to be recorded.
- **The C1 and C2 kernel needs specific options.** User access to the virtual counter is off by
  default, and thread placement needs a non-MCS SMP kernel. The method files fix the build. See the
  [C1 method](../../spikes/sel4-feasibility/results/C1-method.md#kernel-build-for-c1-and-c2).
- **Tooling gaps cannot be closed from here.** Whether a pinned nightly, a given GCC and the Python
  environment build seL4 17.0.0 on macOS arm64 is exactly what A1 measures. Nothing here claims it
  works.

## Missing for Stage A, as of this file

| Item | State |
|---|---|
| C1 and C2 method files | Drafted: [C1](../../spikes/sel4-feasibility/results/C1-method.md), [C2](../../spikes/sel4-feasibility/results/C2-method.md). Need owner review. C1 still lacks the published baseline figure |
| rust-sel4 pin | Proposed above. Needs the owner's choice |
| Nightly toolchain, cross GCC, Python environment, `repo`, Linux image | Not installed. Need owner approval |
| Spike workspace manifest, lock file, toolchain file | Not created. Need owner approval |
| Owner's authorization to execute | **Not given** |

## Decisions for the owner

1. **Review the C1 and C2 method files**, in particular the interpretations they list under
   "Interpretations to confirm". The C1 file cannot be frozen until the published seL4 baseline is
   cited in it. Edits before the first run are free. After it, they are Amendments.
2. **Choose the cross-compiler sources.** AArch64 candidates, each unverified against the pinned seL4
   on macOS: a Homebrew `aarch64-elf-gcc` formula, Arm's `aarch64-none-elf` toolchain, or the
   compiler inside a digest-pinned Linux container (which makes A1 Conditional at best). x86-64 needs
   a compiler with an `x86_64-linux-gnu-` prefix, and none is chosen.
3. **Choose the rust-sel4 version** (`f631577` or `v6.0.0`), and **approve rust-sel4 as a dependency**
   at that commit with its locked tree, including `bindgen` and libclang. Say whether `cargo deny`
   runs on the spike workspace.
4. **Approve the installation list:** the nightly, the Python environment, the cross compilers, the
   `repo` tool, any missing host packages, and the Debian image download. State where `cargo install`
   puts tools.
5. **Approve creating the spike workspace's `Cargo.toml`, `Cargo.lock` and `rust-toolchain.toml`.**
6. **Confirm that the nightly use is covered by the toolchain policy**, or direct an amendment to
   `docs/standards/toolchain.md`.
7. **Decide how Homebrew tools are pinned.** `docs/standards/toolchain.md` exempts only QEMU, EDK2,
   shellcheck and actionlint from pinning. CMake, Ninja and `dtc` are not exempt, and Homebrew cannot
   pin them.
8. **Authorize spike execution**, starting with Stage A, when the above are settled.

## Reproducing the queries

All run on 2026-11-07, read-only:

- `git ls-remote https://github.com/seL4/seL4 'refs/tags/17.0.0*'` and
  `git ls-remote https://github.com/seL4/rust-sel4 HEAD 'refs/tags/v6.0.0*'`
- `gh api repos/seL4/<repo>/contents/<path>?ref=<commit>` for each upstream file named above, and
  `gh api repos/seL4/rust-sel4/compare/c819c27...f631577 --jq .ahead_by`
- `curl https://cloud.debian.org/images/cloud/trixie/20261103-2651/SHA512SUMS` and the image's
  `.json` manifest
- `curl https://pypi.org/pypi/sel4-deps/json`
- `sysctl hw.perflevel0.physicalcpu hw.perflevel1.physicalcpu`, `rustup toolchain list`, and
  `<tool> --version` for each tool in the list
