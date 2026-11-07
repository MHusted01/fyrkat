# Development setup

Everything runs through `cargo xtask`. Nothing here builds a kernel, because none exists yet.
`cargo xtask boot` runs a tiny UEFI test application that checks the toolchain and firmware
pipeline.

## Prerequisites

| Tool | Used for |
|---|---|
| Git | Source control, and `cargo xtask check` lists files with it |
| rustup | Installs the toolchain pinned in `rust-toolchain.toml` |
| A C linker (`cc`) | Linking the host-side `xtask` |
| QEMU (`qemu-system-aarch64`, `qemu-system-x86_64`) | `cargo xtask boot` |
| EDK2 UEFI firmware for both architectures | `cargo xtask boot` |
| shellcheck | `cargo xtask check` |
| actionlint | `cargo xtask check` |
| jq | The Claude Code hook tests in `cargo xtask check` |
| Network access | `cargo-deny` fetches the RustSec advisory database |

`cargo-nextest` and `cargo-deny` are not installed by hand: `cargo xtask tools` builds pinned
versions into `.tools/`.

### macOS (Homebrew)

```sh
brew install rustup qemu shellcheck actionlint jq git
```

Homebrew's `qemu` ships the EDK2 firmware under `$(brew --prefix)/share/qemu`. Follow the
`rustup` caveats to put its proxies on your `PATH`. Xcode command line tools provide `cc`.

### Debian and Ubuntu

```sh
sudo apt-get install build-essential curl git jq shellcheck \
  qemu-system-arm qemu-system-x86 qemu-efi-aarch64 ovmf
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

`actionlint` is not in the Debian archive. Install a release binary from
<https://github.com/rhysd/actionlint/releases> and verify its checksum. CI's `ci.yml` shows
a pinned example.

## First run

```sh
rustup toolchain install   # reads rust-toolchain.toml; run once inside the repository
cargo xtask tools          # pinned cargo-nextest and cargo-deny into .tools/
cargo xtask check          # everything CI checks
cargo xtask boot           # boot-smoke under QEMU, AArch64 and x86-64
```

## Commands

| Command | What it does |
|---|---|
| `cargo xtask tools` | Install the pinned tools into `.tools/` (gitignored). Versions live in `xtask/src/tools.rs`. |
| `cargo xtask check` | Run rustfmt, clippy (host and both UEFI targets), nextest, rustdoc, cargo-deny, shellcheck, script tests (hooks and CI helper scripts), actionlint, Markdown link check, spike isolation check. Prints PASS or FAIL per step and fails if any failed. |
| `cargo xtask boot` | Build boot-smoke and boot it under QEMU. Fails unless the marker appears before the timeout. |
| `cargo test` | Host unit tests of `xtask` only. |

`boot` options: `--arch aarch64|x86_64|all`, `--accel tcg|hvf`, `--timeout <seconds>`.
The default is TCG (software emulation). `--accel hvf` works for AArch64 guests on Apple
Silicon hosts only, and x86-64 guests always use TCG.

Firmware is searched in Homebrew and Debian paths. To use another file, set
`FYRKAT_FIRMWARE_AARCH64` or `FYRKAT_FIRMWARE_X86_64`.

## Notes

- `tests/boot-smoke` is a workspace member but not a default member. It is `no_std` and needs
  a UEFI target, so a plain `cargo build --workspace` fails by design. Use `cargo xtask boot`.
- `spikes/` is not part of the workspace. Each spike is its own Cargo project.
- Missing tools produce an error naming the tool. Do not work around it by removing the check.
