#!/usr/bin/env bash
# A5 steps 1 and 2: build an SMMUv3 experiment's root task and an image from it, on the kernel and loader of the E3 evidence
# build (the E1-H kernel: hypervisor-enabled, the Rust loader), as build-a5-probe.sh does for step 0. Nothing in the kernel or
# loader changes; only the root task is new. (build-relk.sh builds the same root tasks for the K rows, with RELK_BIN.)
#
#   spikes/sel4-feasibility/build-a5-e1h.sh step1|step2 [MUTANT]
#
#   step1   crates/e2-root-task/src/bin/a5_step1_root_task.rs; MUTANT: skip-tlbi, skip-cfgi, map-unmapped, rw-readonly or
#           second-stream-configured
#   step2   crates/e2-root-task/src/bin/a5_step2_root_task.rs; MUTANT: teardown-without-invalidation
#
# Output, in the gitignored external/a5-STEP-build/NAME (NAME is `main` or the mutant): the root task's ELF, image.elf,
# SHA256SUMS, build.log, BUILD_EXIT. Needs external/e3-build (run-e3-evidence.sh). The image is for
# `-machine virt,...,iommu=smmuv3,highmem=off` with `edu` devices. Installs nothing. Spike code.
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
EXT="$(cd external && pwd -P)"
E3="$EXT/e3-build"
STEP="${1:-}"
MUTANT="${2:-}"
usage() {
    echo "usage: build-a5-e1h.sh step1 [skip-tlbi|skip-cfgi|map-unmapped|rw-readonly|second-stream-configured] | step2 [teardown-without-invalidation]" >&2
    exit 1
}
case "$STEP:$MUTANT" in
    step1: | step1:skip-tlbi | step1:skip-cfgi | step1:map-unmapped | step1:rw-readonly | step1:second-stream-configured) MUTANT_VAR=A5S1_MUTANT ;;
    step2: | step2:teardown-without-invalidation) MUTANT_VAR=A5S2_MUTANT ;;
    *) usage ;;
esac
BIN="a5_${STEP}_root_task"
B="$EXT/a5-$STEP-build/${MUTANT:-main}"
LOADER="$E3/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader"
ADD_PAYLOAD="$E3/rust-sel4-host-target/release/sel4-kernel-loader-add-payload"
for f in "$E3/sel4-install/libsel4/include/kernel/gen_config.json" "$LOADER" "$ADD_PAYLOAD"; do
    [ -f "$f" ] || { echo "error: $f is missing: build the E3 evidence image first" >&2; exit 1; }
done
export RUSTUP_TOOLCHAIN=nightly-2026-08-21 RUSTUP_AUTO_INSTALL=0 PATH="$W/.venv/bin:$PATH"
export CC_aarch64_unknown_none=aarch64-elf-gcc AR_aarch64_unknown_none=aarch64-elf-ar RANLIB_aarch64_unknown_none=aarch64-elf-ranlib
unset A5S1_MUTANT A5S2_MUTANT
[ -n "$MUTANT" ] && export "$MUTANT_VAR=$MUTANT"
export SEL4_PREFIX="$E3/sel4-install" RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" RUSTFLAGS="-Zunstable-options"

rm -rf "$B"
mkdir -p "$B"
status=0
{
    cargo build --locked --release -p e2-root-task --bin "$BIN" \
        --target aarch64-sel4 -Z unstable-options -Z build-std=core,alloc,compiler_builtins \
        -Z build-std-features=compiler-builtins-mem --target-dir "$B/target" --artifact-dir "$B" &&
        "$ADD_PAYLOAD" --loader "$LOADER" --sel4-prefix "$SEL4_PREFIX" --app "$B/$BIN.elf" -o "$B/image.elf"
} >"$B/build.log" 2>&1 || status=$?
echo "$status" >"$B/BUILD_EXIT"
echo "a5 $STEP (${MUTANT:-main}): build exit $status"
if [ "$status" -ne 0 ]; then
    grep -n "^error" -A12 "$B/build.log" | head -60
    exit "$status"
fi
(
    cd "$B"
    shasum -a 256 "$BIN.elf" image.elf | tee SHA256SUMS
)
