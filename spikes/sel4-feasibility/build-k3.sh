#!/usr/bin/env bash
# K3: build the SMMU server and client tasks and the K3 root task against one kernel configuration's interface, and a bootable
# image of the root task with seL4's own elfloader (through build-relk.sh's RELK_ROOT_ELF hook; no kernel, loader or dependency
# changes; nothing is installed).
#
#   spikes/sel4-feasibility/build-k3.sh K2|K2R [VARIANT]
#
#   VARIANT   design                      the design under test (default)
#             naive                       the control: the server accepts a frame donated by a caller
#             MUTANT                      one of skip-invalidate, reclaim-while-mapped, no-owner-check,
#                                         death-without-teardown, shared-address-space (design build with that bug)
#
# Needs external/relk-build/ID (build-relk.sh ID has been run: its kernel interface is what the tasks are built against) and
# external/relk-build/k2-smc-a5s2.dtb (run-a5-step2-evidence.sh made it). Output in the gitignored external/k3-build/ID-VARIANT:
# k3_server.elf, k3_client.elf, k3_root_task.elf, the image link (image), SHA256SUMS, build.log, BUILD_EXIT. Spike code.
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
ID="${1:-}"
VARIANT="${2:-design}"
case "$ID" in K2 | K2R) ;; *)
    echo "usage: build-k3.sh K2|K2R [design|naive|MUTANT]" >&2
    exit 1
    ;;
esac
MODE=design
MUTANT=""
case "$VARIANT" in
    design) ;;
    naive) MODE=naive ;;
    skip-invalidate | reclaim-while-mapped | no-owner-check | death-without-teardown | shared-address-space | shared-asid) MUTANT="$VARIANT" ;;
    *)
        echo "error: unknown variant '$VARIANT'" >&2
        exit 1
        ;;
esac
EXT="$(cd external && pwd -P)"
PREFIX="$EXT/relk-build/$ID/prefix/install"
DTB="$EXT/relk-build/k2-smc-a5s2.dtb"
for f in "$PREFIX/libsel4/include/kernel/gen_config.json" "$DTB"; do
    [ -f "$f" ] || { echo "error: $f is missing" >&2; exit 1; }
done
OUT="$EXT/k3-build/$ID-$VARIANT"
# One target directory per kernel, shared by its variants: the build directory's path is embedded in the binaries (panic locations), so
# the client, which is the same program in every variant, is then byte-identical in every variant.
TARGET="$EXT/k3-build/target-$ID"
rm -rf "$OUT"
mkdir -p "$OUT"

export RUSTUP_TOOLCHAIN=nightly-2026-08-21 RUSTUP_AUTO_INSTALL=0 PATH="$W/.venv/bin:$PATH"
export CC_aarch64_unknown_none=aarch64-elf-gcc AR_aarch64_unknown_none=aarch64-elf-ar RANLIB_aarch64_unknown_none=aarch64-elf-ranlib
export SEL4_PREFIX="$PREFIX" RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" RUSTFLAGS="-Zunstable-options"
unset K3_MODE K3_MUTANT K3_SERVER_ELF K3_CLIENT_ELF
export K3_MODE="$MODE"
[ -n "$MUTANT" ] && export K3_MUTANT="$MUTANT"

cargo_build() { # package bin
    cargo build --locked --release -p "$1" --bin "$2" \
        --target aarch64-sel4 -Z unstable-options -Z build-std=core,alloc,compiler_builtins \
        -Z build-std-features=compiler-builtins-mem --target-dir "$TARGET" --artifact-dir "$OUT"
}

status=0
{
    cargo_build e2-task k3_server &&
        cargo_build e2-task k3_client &&
        K3_SERVER_ELF="$OUT/k3_server.elf" K3_CLIENT_ELF="$OUT/k3_client.elf" cargo_build e2-root-task k3_root_task
} >"$OUT/build.log" 2>&1 || status=$?
if [ "$status" -eq 0 ]; then
    NAME="$ID-k3-$VARIANT"
    (RELK_ROOT_ELF="$OUT/k3_root_task.elf" RELK_NAME="$NAME" ./build-relk.sh "$ID" "$DTB") >>"$OUT/build.log" 2>&1 || status=$?
    [ "$status" -eq 0 ] && ln -sfn "$EXT/relk-build/$NAME/build/images/rust-root-task-image-arm-qemu-arm-virt" "$OUT/image"
fi
echo "$status" >"$OUT/BUILD_EXIT"
echo "k3 $ID $VARIANT: build exit $status"
if [ "$status" -ne 0 ]; then
    grep -n "^error" -A14 "$OUT/build.log" | head -80
    tail -5 "$OUT/build.log"
    exit "$status"
fi
(
    cd "$OUT"
    shasum -a 256 k3_server.elf k3_client.elf k3_root_task.elf | tee SHA256SUMS
)
