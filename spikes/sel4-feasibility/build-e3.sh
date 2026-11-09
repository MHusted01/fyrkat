#!/usr/bin/env bash
# E3: build a hypervisor-enabled seL4 17.0.0, the Rust loader and the E3 system (a root task plus one task
# binary that it starts twice), as one bootable image. With --mutant NAME, build only a mutant of the root task
# against the kernel and loader of the evidence build.
#
#   spikes/sel4-feasibility/build-e3.sh
#   spikes/sel4-feasibility/build-e3.sh --mutant NAME   (noop-revoke, revoke-wrong-ancestor, noop-revoke-blind-probes,
#                                                        revoke-too-much, revoke-task-1-only or serve-refused)
#
# Derived from build-e2.sh. The kernel and loader recipe is identical (same pins, same options); only the
# payload differs. The evidence build is written to external/e3-build and a mutant to external/e3-mutant-NAME
# (both gitignored, removed first). It does not touch the pinned checkouts or .venv, and installs nothing.
# Spike code (see the plan's E3 entry).
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W"
SEL4_SHA=62e345c240a15671484530b4e6e069ce266c28d7
RUST_SEL4_SHA=c819c27b076130cba9821c4555f23773e4b0bffd
NIGHTLY=nightly-2026-08-21
EVIDENCE="$W/external/e3-build"

MUTANT=""
case "${1:-}" in
    "") ;;
    --mutant)
        MUTANT="${2:-}"
        case "$MUTANT" in
            noop-revoke | revoke-wrong-ancestor | noop-revoke-blind-probes | revoke-too-much | revoke-task-1-only | serve-refused) ;;
            *)
                echo "error: unknown mutant '$MUTANT'" >&2
                exit 1
                ;;
        esac
        ;;
    *)
        echo "usage: build-e3.sh [--mutant NAME]; the names are in the case statement above" >&2
        exit 1
        ;;
esac
if [ -n "$MUTANT" ]; then
    B="$W/external/e3-mutant-$MUTANT"
else
    B="$EVIDENCE"
fi

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
# Only the root-task build below may see a mutant, and only when asked for one.
unset E3_MUTANT

rm -rf "$B"
mkdir -p "$B"

if [ -z "$MUTANT" ]; then
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
    LOADER="$B/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader"
    ADD_PAYLOAD="$B/rust-sel4-host-target/release/sel4-kernel-loader-add-payload"
else
    echo "== reusing the kernel, loader and add-payload of the evidence build ($EVIDENCE)"
    export SEL4_PREFIX="$EVIDENCE/sel4-install"
    LOADER="$EVIDENCE/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader"
    ADD_PAYLOAD="$EVIDENCE/rust-sel4-host-target/release/sel4-kernel-loader-add-payload"
    for f in "$SEL4_PREFIX/bin/kernel.elf" "$LOADER" "$ADD_PAYLOAD"; do
        if [ ! -f "$f" ]; then
            echo "error: $f is missing: build the evidence image first" >&2
            exit 1
        fi
    done
fi

if [ -z "$MUTANT" ]; then
    echo "== task (one binary, started twice by the root task; spike workspace, locked)"
    RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" \
    RUSTFLAGS="-Zunstable-options" \
    cargo build --locked --release -p e2-task --bin e3_task \
        --target aarch64-sel4 \
        -Z unstable-options \
        -Z build-std=core,alloc,compiler_builtins \
        -Z build-std-features=compiler-builtins-mem \
        --target-dir "$B/task-target" \
        --artifact-dir "$B"
else
    # A rebuild in another directory gives different symbol-hash suffixes in the task ELF: use the evidence build's file.
    echo "== task (the evidence build's binary, byte for byte)"
    cp "$EVIDENCE/e3_task.elf" "$B/e3_task.elf"
fi

echo "== root task (embeds the task ELF${MUTANT:+; mutant $MUTANT})"
if [ -n "$MUTANT" ]; then
    export E3_MUTANT="$MUTANT"
fi
E3_TASK_ELF="$B/e3_task.elf" \
RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" \
RUSTFLAGS="-Zunstable-options" \
cargo build --locked --release -p e2-root-task --bin e3_root_task \
    --target aarch64-sel4 \
    -Z unstable-options \
    -Z build-std=core,alloc,compiler_builtins \
    -Z build-std-features=compiler-builtins-mem \
    --target-dir "$B/root-task-target" \
    --artifact-dir "$B"

echo "== image"
"$ADD_PAYLOAD" \
    --loader "$LOADER" \
    --sel4-prefix "$SEL4_PREFIX" \
    --app "$B/e3_root_task.elf" \
    -o "$B/image.elf"

echo "== checksums"
(
    cd "$B"
    cp "$SEL4_PREFIX/bin/kernel.elf" kernel.elf
    cp "$LOADER" sel4-kernel-loader.elf
    shasum -a 256 kernel.elf sel4-kernel-loader.elf e3_task.elf e3_root_task.elf image.elf | tee SHA256SUMS
)
