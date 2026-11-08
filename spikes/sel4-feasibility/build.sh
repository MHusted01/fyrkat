#!/usr/bin/env bash
# A1: one command that cleanly builds seL4 17.0.0 and a Rust root task, natively on macOS arm64.
#
#   spikes/sel4-feasibility/build.sh
#
# It removes build/ first, so every run is a clean build. It does not touch external/ (the pinned
# seL4 and rust-sel4 checkouts) or .venv (the hash-pinned Python environment). It installs nothing.
# Output: build/image.elf (loader + kernel + root task) and build/SHA256SUMS.
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W"

SEL4_SHA=62e345c240a15671484530b4e6e069ce266c28d7
RUST_SEL4_SHA=c819c27b076130cba9821c4555f23773e4b0bffd
NIGHTLY=nightly-2026-08-21

# The pinned inputs must be the ones checked out.
for pin in "seL4:$SEL4_SHA" "rust-sel4:$RUST_SEL4_SHA"; do
    name="${pin%%:*}"
    want="${pin##*:}"
    got="$(git -C "external/$name" rev-parse HEAD)"
    if [ "$got" != "$want" ]; then
        echo "error: external/$name is at $got, expected $want" >&2
        exit 1
    fi
done

# Guards (decisions 3 and 7): never let rustup install more than the approved Tier 1 toolchain,
# use the hash-pinned venv, and use the cross binutils for C objects built by the cc crate. Without
# AR and RANLIB the cc crate uses macOS's own ar and ranlib on AArch64 ELF objects and loses the
# loader's assembly (A1 finding 1).
export RUSTUP_TOOLCHAIN="$NIGHTLY"
export RUSTUP_AUTO_INSTALL=0
export PATH="$W/.venv/bin:$PATH"
export CC_aarch64_unknown_none=aarch64-elf-gcc
export AR_aarch64_unknown_none=aarch64-elf-ar
export RANLIB_aarch64_unknown_none=aarch64-elf-ranlib

rm -rf build
mkdir -p build

echo "== seL4 kernel"
cmake \
    -DCROSS_COMPILER_PREFIX=aarch64-elf- \
    -DCMAKE_INSTALL_PREFIX="$W/build/sel4-install" \
    -DKernelPlatform=qemu-arm-virt \
    -DKernelArmHypervisorSupport=OFF \
    -DKernelVerificationBuild=OFF \
    -DARM_CPU=cortex-a57 \
    -G Ninja -S external/seL4 -B build/sel4
ninja -C build/sel4 all
ninja -C build/sel4 install
export SEL4_PREFIX="$W/build/sel4-install"

echo "== kernel loader and add-payload (from the rust-sel4 checkout, with its own lock)"
(
    cd external/rust-sel4
    cargo build --locked --release -p sel4-kernel-loader \
        --target aarch64-unknown-none \
        -Z build-std=core,alloc,compiler_builtins \
        -Z build-std-features=compiler-builtins-mem \
        --target-dir "$W/build/rust-sel4-target"
    cargo build --locked --release -p sel4-kernel-loader-add-payload \
        --target-dir "$W/build/rust-sel4-host-target"
)
loader="$W/build/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader"
add_payload="$W/build/rust-sel4-host-target/release/sel4-kernel-loader-add-payload"

echo "== root task (spike workspace, with its seeded lock)"
# The demo keeps these settings in .cargo/config.toml, which the owner has not approved, so they are
# passed here instead.
RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" \
RUSTFLAGS="-Zunstable-options" \
cargo build --locked --release -p s1-root-task \
    --target aarch64-sel4 \
    -Z unstable-options \
    -Z build-std=core,alloc,compiler_builtins \
    -Z build-std-features=compiler-builtins-mem \
    --target-dir build/root-task-target \
    --artifact-dir build

echo "== image"
"$add_payload" \
    --loader "$loader" \
    --sel4-prefix "$SEL4_PREFIX" \
    --app build/s1-root-task.elf \
    -o build/image.elf

echo "== checksums"
(
    cd build
    cp sel4-install/bin/kernel.elf kernel.elf
    cp "$loader" sel4-kernel-loader.elf
    shasum -a 256 kernel.elf sel4-kernel-loader.elf s1-root-task.elf image.elf | tee SHA256SUMS
)
