# Toolchain policy

Builds must be reproducible: the same commit builds with the same compiler and tools on every
machine and in CI.

## What is pinned

| Item | Where | How it is pinned |
|---|---|---|
| Rust compiler, components, targets | `rust-toolchain.toml` | Exact release, such as `1.99.1`. Never `stable` or `nightly`. |
| `cargo-nextest`, `cargo-deny` | `xtask/src/tools.rs` | Exact crate versions, installed with `cargo install --locked` into `.tools/`. `cargo xtask check` fails if the installed version differs. |
| Crate dependencies | `Cargo.lock` | Committed. Builds use the locked versions. |
| GitHub Actions | `.github/workflows/` | Full commit SHA, with the version in a comment. |
| Ubuntu and macOS runners | Workflows | A named image, not `latest`. |
| QEMU, EDK2 firmware, shellcheck, actionlint | Distribution packages | Not pinned. Their versions are printed in CI logs. A change that breaks `check` is investigated, not hidden. |

`rust-toolchain.toml` lists the UEFI and bare-metal targets the boot spike needs. That list
implies no architecture decision; ADR 0002 and ADR 0003 decide the real targets.

## Nightly

The product builds with stable only. A nightly compiler may be used for analysis tools that
require it, such as Miri, and only when pinned by date (for example `nightly-2026-11-01`),
installed on demand, and never used to produce a shipped artefact. No analysis tool needs it
today, so no nightly is configured at the repository root.

A spike under `spikes/` may use a nightly compiler that its own `rust-toolchain.toml` pins by date,
when a dependency requires it. Nothing outside `spikes/` may use it, and no shipped artefact may be
built with it. A spike that needs nightly records which features force it. The owner approved this
rule on 2026-11-08 (decision 6 of the S1 decision package).

## Updating the Rust toolchain

1. Read the release notes for new lints, changed defaults and removed features.
2. Change `channel` in `rust-toolchain.toml` in a PR that contains nothing else except the
   fixes the new compiler requires.
3. Update `rust-version` in the root `Cargo.toml` if the minimum changes.
4. Run `rustup toolchain install`, `cargo xtask tools` (tools must still build) and
   `cargo xtask check` and `cargo xtask boot`.
5. Review new clippy lints. Fix findings; do not blanket-allow them.
6. The owner approves, because `rust-toolchain.toml` is security-sensitive.

## Updating a pinned tool

Change the version in `xtask/src/tools.rs`. Confirm it installs on the pinned toolchain
(`cargo xtask tools`) and read the tool's changelog for changed defaults. Dependabot does not
update these pins.

## Dependabot

Dependabot proposes updates for GitHub Actions (SHA and version comment together) and Cargo
dependencies weekly. Each update is a normal PR with normal review.
