# seL4 spike prerequisites

- **Status:** Draft, prepared 2026-11-07. Nothing in this file has been installed, built or run.
- **Plan:** [spike plan](sel4-spike-plan.md), approved at `46a90fa`. This file adds no criterion and
  changes none.
- **Purpose:** list what Stage A needs, pin the inputs the plan leaves open, and name every
  decision the owner must make before the spike can start.
- **Authority:** this file grants nothing. Execution, tool installation and new global tools stay
  under the plan's [Scope limits](sel4-spike-plan.md#scope-limits).

Evidence labels are as in [AGENTS.md](../../AGENTS.md). "Present" means found on this Mac by a
version query on 2026-11-07. This work installed nothing.

## Pinned inputs

| Input | Value | Label |
|---|---|---|
| seL4 | `17.0.0`, commit `62e345c240a15671484530b4e6e069ce266c28d7` ("Release 17.0.0", 2026-10-30). The tag object is `ab504cd497d239ed7341472b7f67b56f4c42dbe1` | Measured: `git ls-remote`, GitHub API |
| rust-sel4 (proposed) | `f631577eb7def6fe6fb57fcaf7b8fd61bf144fcc` ("nix: Update Verus", 2026-11-05), tip of `main`. `VERSION` says `6.0.0-dev`. The commit is unsigned on GitHub | Measured: GitHub API |
| rust-sel4 toolchain | `nightly-2026-10-28`, from its `rust-toolchain.toml` at that commit. The same nightly the plan names | Documented: upstream file |
| rust-sel4 compatibility | "seL4 version 17.0.0" and "seL4 Microkit version 2.4.0" | Documented: upstream README at that commit |
| Root-task demo (reference for A1) | `seL4/rust-root-task-demo` `c13bdae64a860dfe1d3064717f4096e63bb7dff2` ("Update everything", 2026-11-04) | Measured: GitHub API |
| QEMU | `11.1.3`, from Homebrew, as the plan pins | Measured: `qemu-system-aarch64 --version` |
| Linux guest for C2 (candidate) | Debian 13 `debian-13-nocloud-arm64-20261103-2651.qcow2`, SHA-512 `f99c23f0d4c18ba7512bae254a201b72dafe11ef0c69beac489a2daba4e128171ca5dcfcdc6d76c2b81a8aa17fc6da8ced2d0a3b9442c97358b3e99ed6668ca7`, from `cloud.debian.org/images/cloud/trixie/20261103-2651/SHA512SUMS`. Not downloaded. Its kernel version is not known | Documented: upstream checksum file. Hash not yet checked against a downloaded file |

**How the rust-sel4 pin works.** The plan says the commit is "recorded at the start of A1". This
file proposes it now so the owner can review it. A1 adopts it by naming it in `A1.md`. If it fails
to build, the change to another commit is recorded as a documented approach, not made silently. The
pin is the commit hash. The branch tip will move on.

**Note on the plan's K0.** At the pinned seL4 commit `configs/` holds `AARCH64_verified.cmake`
and many board files such as `AARCH64_bcm2711_verified.cmake` and `AARCH64_bcm2712_verified.cmake`,
and `X64_verified.cmake` [Measured]. The plan says K0 is a verified board, so A2a chooses the board
file. That choice is not made here.

## Tool list

| Tool | Needed for | Pin | State | Install needs approval |
|---|---|---|---|---|
| QEMU `qemu-system-aarch64` and `qemu-system-x86_64` | A3, A4, A5, Stage B and C | 11.1.3 | Present, Homebrew | No |
| EDK2 firmware `edk2-aarch64-code.fd`, `edk2-x86_64-code.fd` | A4 | Version not recorded | Present, in Homebrew's QEMU share | No. Record the version at A4 |
| CMake | seL4 build | seL4 asks for 3.16.0 or later [Documented: `CMakeLists.txt`] | 4.4.5 present. Whether seL4 17.0.0 configures under CMake 4 is **not tested** | No |
| Ninja | seL4 build | None | 1.13.2 present | No |
| `dtc` | seL4 build | None | 1.8.1 present | No |
| `xmllint` | seL4 build [Documented: seL4 host-dependencies page] | System | Present | No |
| Rust `nightly-2026-10-28` with `rust-src`, `llvm-tools-preview`, `rustc-dev`, and targets `aarch64-unknown-none`, `x86_64-unknown-none`, `aarch64-unknown-linux-musl` | A1, A4, B, C | Date-pinned | **Absent.** Only stable 1.99.1, 1.88 and a default `stable` are installed | **Yes.** Pending in the handoff |
| Python virtual environment with `sel4-deps` | seL4 build scripts | `sel4-deps==0.9.0` [Documented: PyPI]. Its 19 requirements need pins with hashes. `requires_python` is only `>=3`, and the host has Python 3.15.0, whose fit is **not tested** | **Absent** | **Yes**, a new environment and packages |
| AArch64 cross GCC | seL4 kernel build | See open decision 2 | **Absent** | **Yes** |
| x86-64 cross GCC with an ELF target | X1 for A4 and A5-x86 | Not established | **Absent.** seL4's `gcc.cmake` searches prefixes only for ARM and RISC-V in the part read. How it builds x86-64 on macOS is not established | **Yes** |
| `sel4-kernel-loader` and `sel4-kernel-loader-add-payload` | A4 comparison, and the upstream boot path | Built from the rust-sel4 pin | Not built | Built by the spike, covered by the nightly approval |
| seL4's own loader (`elfloader` in `seL4_tools`) | A4 comparison | Commit chosen at A4 start | Not fetched | Fetch is part of the spike. Confirm at the gate |
| `sel4test` and the `repo` tool | A3 | Commits chosen at A3 start | Not fetched. `repo` not checked | `repo` is a new tool, so yes |
| Docker | A1 Conditional path only | Image by digest, never a tag | 29.8.2 present | Only if A1 needs it |
| Linux guest image, as above | C1 baseline, C2 | SHA-512 above | Not downloaded | Yes, a new download |
| Nix | Upstream's own route | | Absent | Not proposed. See below |

**Cross-compiler prefixes.** seL4's `gcc.cmake` at the pinned commit looks for, in order,
`aarch64-linux-gnu-`, `aarch64-unknown-linux-gnu-`, `aarch64-none-linux-gnu-`, `aarch64-none-elf-` and
`aarch64-elf-` [Measured: file read]. The pinned seL4 does not name a source for any of them.

**Upstream's build route.** The rust-sel4 repository and its demo build through Docker and Nix:
`hacking/docker/Dockerfile` starts `FROM debian:bookworm`, a tag, not a digest, and installs Nix. The
demo's `Makefile` boots with `-machine virt,virtualization=on`, a hypervisor build, which is not K1 and
K2. K1 and K2 have no hypervisor support, so the demo's QEMU command line is a starting point only
[Measured: file read]. The A1 criteria ask for a native build on this Mac. Container use is the
Conditional outcome, and this file does not prejudge it.

**Harness language.** C1 and C2 harnesses are Rust. The Linux-side harness is built as static
`aarch64-unknown-linux-musl`, so the Debian guest needs no compiler. Whether the musl target links
on macOS without an extra linker is **not tested**.

## Facts that affect the spike

- **Spike workspace files need approval.** AGENTS.md puts `Cargo.toml`, `Cargo.lock` and
  `rust-toolchain.toml` at any depth under owner approval. The plan puts the spike in its own Cargo
  workspace under `spikes/sel4-feasibility/`. Creating that workspace's manifest, lock file and
  toolchain file is therefore an owner decision, and this work created none. [Documented]
- **The nightly policy.** `docs/standards/toolchain.md` allows a date-pinned nightly "for analysis
  tools", installed on demand, and never for a shipped artefact. Spike code is never shipped. The
  policy does not cover this use by name, and the plan's Consequences table says that "User space
  requires nightly Rust" reopens the toolchain policy [Documented: both files]. The owner should
  confirm that the installation is covered.
- **The patch directory.** The plan puts seL4 in a gitignored directory. `.gitignore` has no entry
  for it yet. This work adds `/spikes/sel4-feasibility/sel4/` so an accidental `git add` cannot
  commit GPL-2.0 kernel code. [Measured: `.gitignore` before the change]
- **Core mix.** The host has 6 performance and 4 efficiency cores [Measured: `sysctl`]. C3's 8-vCPU
  run uses most of them, and the plan already requires the mix to be recorded.
- **Tooling gaps cannot be closed from here.** Whether a pinned nightly, a given GCC and the
  Python environment build seL4 17.0.0 on macOS arm64 is exactly what A1 measures. Nothing here
  claims it works.

## Missing for Stage A, as of this file

| Item | State |
|---|---|
| C1 and C2 method files | Drafted: [C1](../../spikes/sel4-feasibility/results/C1-method.md), [C2](../../spikes/sel4-feasibility/results/C2-method.md). Need owner review, then a merge to `main` |
| rust-sel4 pin | Proposed above. Adopted at A1 |
| Nightly toolchain, cross GCC, Python environment, `repo`, Linux image | Not installed. Need owner approval |
| Spike workspace manifest, lock file, toolchain file | Not created. Need owner approval |
| Owner's authorization to execute | **Not given** |

## Decisions for the owner

1. **Review the C1 and C2 method files**, in particular the three interpretations they mark: the
   C1 Pass test uses workload W1 only, C2's headline is cost per page touched, and the sizes, run
   counts and batch sizes. Merging them to `main` freezes them.
2. **Choose the AArch64 cross-compiler source.** Candidates, each unverified against the pinned seL4
   on macOS: a Homebrew `aarch64-elf-gcc` formula, Arm's `aarch64-none-elf` toolchain, or the
   compiler inside a digest-pinned Linux container (which makes A1 Conditional at best).
3. **Approve the installation list:** the nightly, the Python environment, the cross compilers, the
   `repo` tool, and the Debian image download.
4. **Approve creating the spike workspace's `Cargo.toml`, `Cargo.lock` and `rust-toolchain.toml`.**
5. **Confirm that the nightly use is covered by the toolchain policy**, or direct an amendment to
   `docs/standards/toolchain.md`.
6. **Authorize spike execution**, starting with Stage A, when the above are settled.
