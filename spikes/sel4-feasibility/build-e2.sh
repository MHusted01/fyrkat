#!/usr/bin/env bash
# E2: build a hypervisor-enabled seL4 17.0.0, the Rust loader and the E2 system (a root task plus two
# isolated tasks), as one bootable image.
#
#   spikes/sel4-feasibility/build-e2.sh
#
# Derived from build-e1.sh. The kernel and loader recipe is identical (same pins, same options); only the
# payload differs: the e2-task binaries (client, server) are built first, then the e2-root-task that embeds
# them, then the image. Everything is written to external/e2-build (gitignored), which is removed first.
# It does not touch the pinned checkouts or .venv, and installs nothing. Spike code (see the plan's E2 entry).
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W"
B="$W/external/e2-build"
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

# Same guards as build.sh (decisions 3 and 7; A1 finding 1).
export RUSTUP_TOOLCHAIN="$NIGHTLY"
export RUSTUP_AUTO_INSTALL=0
export PATH="$W/.venv/bin:$PATH"
export CC_aarch64_unknown_none=aarch64-elf-gcc
export AR_aarch64_unknown_none=aarch64-elf-ar
export RANLIB_aarch64_unknown_none=aarch64-elf-ranlib

rm -rf "$B"
mkdir -p "$B"

echo "== seL4 kernel (hypervisor support ON)"
cmake \
    -DCROSS_COMPILER_PREFIX=aarch64-elf- \
    -DCMAKE_INSTALL_PREFIX="$B/sel4-install" \
    -DKernelPlatform=qemu-arm-virt \
    -DKernelArmHypervisorSupport=ON \
    -DKernelVerificationBuild=OFF \
    -DARM_CPU=cortex-a57 \
    -G Ninja -S external/seL4 -B "$B/sel4"
ninja -C "$B/sel4" all
ninja -C "$B/sel4" install
export SEL4_PREFIX="$B/sel4-install"

echo "== kernel loader and add-payload (from the rust-sel4 checkout, with its own lock)"
(
    cd external/rust-sel4
    cargo build --locked --release -p sel4-kernel-loader \
        --target aarch64-unknown-none \
        -Z build-std=core,alloc,compiler_builtins \
        -Z build-std-features=compiler-builtins-mem \
        --target-dir "$B/rust-sel4-target"
    cargo build --locked --release -p sel4-kernel-loader-add-payload \
        --target-dir "$B/rust-sel4-host-target"
)
loader="$B/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader"
add_payload="$B/rust-sel4-host-target/release/sel4-kernel-loader-add-payload"

echo "== tasks (client and server, spike workspace, locked)"
RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" \
RUSTFLAGS="-Zunstable-options" \
cargo build --locked --release -p e2-task --bin e2-client --bin e2-server \
    --target aarch64-sel4 \
    -Z unstable-options \
    -Z build-std=core,alloc,compiler_builtins \
    -Z build-std-features=compiler-builtins-mem \
    --target-dir "$B/task-target" \
    --artifact-dir "$B"

echo "== root task (embeds the two task ELFs)"
E2_SERVER_ELF="$B/e2-server.elf" \
E2_CLIENT_ELF="$B/e2-client.elf" \
RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" \
RUSTFLAGS="-Zunstable-options" \
cargo build --locked --release -p e2-root-task --bin e2-root-task \
    --target aarch64-sel4 \
    -Z unstable-options \
    -Z build-std=core,alloc,compiler_builtins \
    -Z build-std-features=compiler-builtins-mem \
    --target-dir "$B/root-task-target" \
    --artifact-dir "$B"

echo "== image"
"$add_payload" \
    --loader "$loader" \
    --sel4-prefix "$SEL4_PREFIX" \
    --app "$B/e2-root-task.elf" \
    -o "$B/image.elf"

echo "== checksums"
(
    cd "$B"
    cp sel4-install/bin/kernel.elf kernel.elf
    cp "$loader" sel4-kernel-loader.elf
    shasum -a 256 kernel.elf sel4-kernel-loader.elf e2-client.elf e2-server.elf e2-root-task.elf image.elf | tee SHA256SUMS
)
