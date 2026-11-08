# seL4 spike prerequisites

- **Status:** Prepared 2026-11-07 and revised after independent reviews. The owner's decisions of 2026-11-08 are in the plan's [Amendments](sel4-spike-plan.md#amendments), and they win where this file still says draft or pending. Nothing in this
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
| rust-sel4 (candidate: tip of `main`) | `f631577eb7def6fe6fb57fcaf7b8fd61bf144fcc` ("nix: Update Verus", 2026-11-05), tip of `main`. `VERSION` says `6.0.0-dev`. Unsigned on GitHub. It is 59 commits after the release below | Measured |
| rust-sel4 (candidate: release, recommended in the [decision package](s1-decision-package.md)) | Tag `v6.0.0`, commit `c819c27b076130cba9821c4555f23773e4b0bffd` (2026-10-30). Its `rust-toolchain.toml` pins `nightly-2026-08-21` | Measured, Documented |
| rust-sel4 toolchain at `f631577` | `nightly-2026-10-28`, the nightly the plan names | Documented: upstream `rust-toolchain.toml` |
| rust-sel4 compatibility | "seL4 version 17.0.0" and "seL4 Microkit version 2.4.0", described as "at least" these versions | Documented: upstream README at `f631577`. The decision package cites the `v6.0.0` README for the release |
| Root-task demo | `seL4/rust-root-task-demo` `c13bdae64a860dfe1d3064717f4096e63bb7dff2` ("Update everything", 2026-11-04). It depends on rust-sel4 `tag = "v6.0.0"` and pins `nightly-2026-08-21`. It is a reference for the **release**, not for the proposed commit | Documented, Measured |
| QEMU | `11.1.3`, from Homebrew, as the plan pins | Measured |
| Linux guest for C2 | Debian 13 `debian-13-nocloud-arm64-20261103-2651.qcow2`, SHA-512 `f99c23f0d4c18ba7512bae254a201b72dafe11ef0c69beac489a2daba4e128171ca5dcfcdc6d76c2b81a8aa17fc6da8ced2d0a3b9442c97358b3e99ed6668ca7`. Its manifest lists `linux-image-6.12.115+deb13.1-arm64`. Not downloaded, so the hash is not checked against a file. The checksum file is unsigned, so the hash rests on HTTPS | Documented: `SHA512SUMS` and the image `.json` manifest |

**The rust-sel4 choice.** The plan records the commit "at the start of A1". This file sets out two
candidates so the owner can choose. The two candidates trade off as follows:

| | `f631577` (main) | `v6.0.0` (release) |
|---|---|---|
| Nightly | `nightly-2026-10-28`, matching the plan | `nightly-2026-08-21`, which differs from the plan's pin |
| Maturity | Unreleased, 59 commits after the release, with heavy `sel4-kernel-loader` changes and a toolchain bump | A tagged release |
| Demo | None matches | The root-task demo matches |
| A4 | The loader compared is the unreleased one | The released loader |

This file first proposed `f631577` because the plan names its nightly. The
[decision package](s1-decision-package.md) now recommends `v6.0.0` instead, with the evidence: it is a
release compatible with seL4 17.0.0, it has a known-good recipe, and both versions have the same git
footprint. That needs an Amendment to a pinned input. If the chosen version later fails to build,
switching is recorded as an approach in the A1 results. The order of approaches, and which of them
count toward the plan's three-approach Blocked rule, is proposed in decision 8 of the decision package
for the owner to fix before A1 starts, so that it is not interpreted after a failure.

**Note on the plan's K0.** At the pinned seL4 commit `configs/` holds `AARCH64_verified.cmake` and
many board files such as `AARCH64_bcm2711_verified.cmake` and `AARCH64_bcm2712_verified.cmake`, and
`X64_verified.cmake`. The plan says K0 is a verified board. Choice 1c of the decision package
recommends `AARCH64_verified.cmake`, fixed before A2a so that A2a cannot pick the file that suits its
result. The owner confirmed it on 2026-11-08.

## Tool list

| Tool | Needed for | Pin | State | Install needs approval |
|---|---|---|---|---|
| QEMU `qemu-system-aarch64` and `qemu-system-x86_64` | A3, A4, A5, Stage B and C | 11.1.3 | Present, Homebrew | No |
| EDK2 firmware `edk2-aarch64-code.fd`, `edk2-x86_64-code.fd` | A4 | Version not recorded | Present, in Homebrew's QEMU share | No. Record the version at A4 |
| CMake | seL4 build | seL4 asks for 3.16.0 or later [Documented: `CMakeLists.txt`] | 4.4.5 present. Whether seL4 17.0.0 configures under CMake 4 is **not tested** | No |
| Ninja, `dtc` | seL4 build | To be frozen with `brew pin` and versions recorded (decision 7 of the decision package). No pin exists yet | 1.13.2 and 1.8.1 present | No |
| `xmllint` | seL4 build [Documented: seL4 host-dependencies page] | System | Present | No |
| libclang | `bindgen` in the `sel4-sys` crate [Documented: `crates/sel4/sys/Cargo.toml` lists `bindgen` 0.72.1 at `v6.0.0` and 0.73.2 on `main`] | Not decided | `/Library/Developer/CommandLineTools/usr/lib/libclang.dylib` exists. Not tested with `bindgen` | No, if that library is used |
| Other host packages named on seL4's host-dependencies page for Linux: `protobuf-compiler`, `xxd`, `u-boot-tools`, `ccache` | seL4 build | Not decided | `protoc` and `xxd` are present and `ccache` is absent. `u-boot-tools` was not checked [Measured: `command -v`, 2026-11-08]. The page assumes a Linux host [Documented] | Probably, for any that are missing |
| Rust `nightly-2026-08-21` (P1, approved 2026-11-08) with `rust-src`, `llvm-tools-preview`, `rustc-dev`, and target `aarch64-unknown-none` (Tier 1; `x86_64-unknown-none` and `aarch64-unknown-linux-musl` are Tiers 2 and 3 and are not approved) | A1, A4, A5, B, C | Date-pinned | **Absent.** Only stable 1.99.1, 1.88 and a default `stable` are installed | Approved on 2026-11-08 (Tier 1) |
| Python virtual environment with `sel4-deps` | seL4 build scripts | `sel4-deps==0.9.0` [Documented: PyPI]. Its 19 requirements need pins with hashes. `requires_python` is only `>=3`, and the host has Python 3.15.0, whose fit is **not tested** | **Absent** | Approved on 2026-11-08 (Tier 1). Pins need the full transitive set with hashes. `pyyaml` 6.0.3 and `pyfdt` 0.3 have no cp315 wheel and build from source [Inferred], so their build tools are pinned with hashes too and the build uses `--no-build-isolation` |
| AArch64 cross GCC | seL4 kernel build | See decision 2 | **Absent** | **Yes** |
| x86-64 cross GCC | X1 for A4 and A5-x86 | See decision 2 | **Absent.** On macOS seL4's `gcc.cmake` looks for `x86_64-linux-gnu-` and `x86_64-unknown-linux-gnu-` compilers [Documented: `gcc.cmake`, lines 90 to 101] | **Yes** |
| `sel4-kernel-loader` and `sel4-kernel-loader-add-payload` | A4 comparison, and the upstream boot path | Built from the rust-sel4 pin | Not built | Built by the spike. Covered by the owner's decision on rust-sel4 and the nightly, once given |
| seL4's own loader (`elfloader` in `seL4_tools`) | A4 comparison | Commit chosen at A4 start | Not fetched | Fetch is part of the spike. Confirm at the gate |
| `sel4test` and its projects | A3 | Revisions from the `sel4test-manifest` tag `17.0.0` (decision 4 of the decision package) | Not fetched | Fetching with plain `git` is part of the spike. `repo` is not needed |
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
  toolchain file is therefore an owner decision, and this work created none. The same gate covers any
  `.cargo/config.toml`, `build.rs` or `deny.toml` the spike adds, and decision 5 of the decision
  package lists the files it asks for. [Documented]
- **rust-sel4 is a new dependency.** AGENTS.md requires owner approval for a new dependency. It is a
  git source with unsigned commits, with its own crates.io tree and `bindgen` as a build dependency,
  which loads libclang. The root `deny.toml` denies unknown git sources, but `cargo deny` runs on
  the root workspace only, so a spike workspace gets no supply-chain check unless the owner directs
  one. [Documented, Inferred]
- **The nightly policy.** `docs/standards/toolchain.md` allows a date-pinned nightly "for analysis
  tools", installed on demand, and never for a shipped artefact. Spike code is never shipped. The
  policy does not cover this use by name, and the plan's Consequences table says that "User space
  requires nightly Rust" reopens the toolchain policy [Documented: both files]. The owner approved the
  rule on 2026-11-08, and `toolchain.md` now states it.
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
| C1 and C2 method files | Drafted: [C1](../../spikes/sel4-feasibility/results/C1-method.md), [C2](../../spikes/sel4-feasibility/results/C2-method.md). Approved by the owner on 2026-11-08. The C1 published baseline is fixed in the file |
| rust-sel4 pin | `v6.0.0`, approved as P1 on 2026-11-08. `f631577` stays a documented alternative |
| Nightly toolchain, cross GCC, Python environment | Not installed. Tier 1 approved on 2026-11-08 |
| Linux image | Not downloaded. Tier 3 is not approved |
| Spike workspace manifest, lock file, toolchain file and spike-local `deny.toml` | Not created. Approved on 2026-11-08 |
| Owner's authorization to execute | Given conditionally on 2026-11-08 (decision 8). See the plan's Amendments |

## Decisions for the owner

The eight decisions (answered on 2026-11-08, recorded in the plan's Amendments), with a recommendation and the evidence for each, are in the
[S1 decision package](s1-decision-package.md). That file replaces the list that stood here.

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
