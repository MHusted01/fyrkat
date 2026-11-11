#!/usr/bin/env bash
# A5 step 0: build the probe root task and an image from it, on the kernel and loader of the E3 evidence build (the E1-H kernel:
# hypervisor-enabled, the Rust loader). Nothing in the kernel or loader changes; only the root task is new.
#
#   spikes/sel4-feasibility/build-a5-probe.sh [low|high]
#
#   low   the PCIe ECAM at 0x3f000000, for `-machine ...,highmem=off` (default)
#   high  the ECAM at 0x4010000000, for the machine's default `highmem=on`
#
# Output, in the gitignored external/a5-step0-build-low or -high: a5_probe_root_task.elf, image.elf, SHA256SUMS, build.log, BUILD_EXIT. Needs the
# E3 evidence build (external/e3-build: run-e3-evidence.sh) for the kernel prefix and the loader. Installs nothing. Spike code.
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
EXT="$(cd external && pwd -P)"
E3="$EXT/e3-build"
case "${1:-low}" in
    low) ECAM_MODE=low ;;
    high) ECAM_MODE=high ;;
    *) echo "usage: build-a5-probe.sh [low|high]" >&2; exit 1 ;;
esac
B="$EXT/a5-step0-build-$ECAM_MODE"
for f in "$E3/sel4-install/libsel4/include/kernel/gen_config.json" "$E3/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader" \
    "$E3/rust-sel4-host-target/release/sel4-kernel-loader-add-payload"; do
    [ -f "$f" ] || { echo "error: $f is missing: build the E3 evidence image first" >&2; exit 1; }
done
export RUSTUP_TOOLCHAIN=nightly-2026-08-21 RUSTUP_AUTO_INSTALL=0 PATH="$W/.venv/bin:$PATH"
export CC_aarch64_unknown_none=aarch64-elf-gcc AR_aarch64_unknown_none=aarch64-elf-ar RANLIB_aarch64_unknown_none=aarch64-elf-ranlib
unset A5_ECAM_HIGH
[ "$ECAM_MODE" = high ] && export A5_ECAM_HIGH=1
export SEL4_PREFIX="$E3/sel4-install" RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" RUSTFLAGS="-Zunstable-options"

rm -rf "$B"
mkdir -p "$B"
status=0
{
    cargo build --locked --release -p e2-root-task --bin a5_probe_root_task \
        --target aarch64-sel4 -Z unstable-options -Z build-std=core,alloc,compiler_builtins \
        -Z build-std-features=compiler-builtins-mem --target-dir "$B/target" --artifact-dir "$B" &&
        "$E3/rust-sel4-host-target/release/sel4-kernel-loader-add-payload" \
            --loader "$E3/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader" \
            --sel4-prefix "$SEL4_PREFIX" --app "$B/a5_probe_root_task.elf" -o "$B/image.elf"
} >"$B/build.log" 2>&1 || status=$?
echo "$status" >"$B/BUILD_EXIT"
echo "a5 probe: build exit $status"
if [ "$status" -ne 0 ]; then
    tail -25 "$B/build.log"
    exit "$status"
fi
(
    cd "$B"
    shasum -a 256 a5_probe_root_task.elf image.elf | tee SHA256SUMS
)
