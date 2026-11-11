#!/usr/bin/env bash
# A2a follow-up: kernel-only builds of release variants, to separate the effect of debug instrumentation from the
# effects of the hypervisor option, the platform, SMP and the verification-build options on the A2a comparison.
#
#   spikes/sel4-feasibility/build-a2a-variants.sh K1R|K2R|E1HR|K0Q
#
#   K1R   K1 (build-a2a.sh) with -DKernelDebugBuild=OFF -DKernelPrinting=OFF: a release build, everything else as K1.
#   K2R   K2 with the same two options.
#   E1HR  E1H (the experiment-only hypervisor-enabled kernel of E1 to E3) with the same two options.
#   K0Q   EXTRA, informational: K0's own configuration (configs/AARCH64_verified.cmake) on the qemu-arm-virt platform
#         (-DKernelPlatform=qemu-arm-virt -DARM_CPU=cortex-a57 placed before the file, so they win). Differs from K0 in the
#         platform only; from E1HR in the verification-build options only. It exists to separate those two effects.
#
# None of these is a row of the plan's assurance matrix, and none is a verified configuration. Output, in the
# gitignored $A2A_BUILD_ROOT/ID (default external/a2a-variants-build/ID): command.txt, tools.txt, build.log, gen_config.json,
# CMakeCache.txt, kernel.elf, kernel_all_pp.c, kernel_all.i, SHA256SUMS, BUILD_EXIT. Same recipe, tools and pinned checkout
# as build-a2a.sh. Kernel only: no loader, no root task, no boot. Spike code (see the plan's A2a follow-up entry).
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
ID="${1:-}"
case "$ID" in
    K1R | K2R | E1HR | K0Q) ;;
    *)
        echo "usage: build-a2a-variants.sh K1R|K2R|E1HR|K0Q" >&2
        exit 1
        ;;
esac
# Physical paths: the compiler records the path it was given in its line markers, and a2a-compare.py normalises the resolved
# one, so a symlinked external/ would leave the build directory in the function table's file column.
EXT="$(cd "$W/external" && pwd -P)"
B="${A2A_BUILD_ROOT:-$EXT/a2a-variants-build}/$ID"
export PATH="$W/.venv/bin:$PATH"
SEL4_SHA=62e345c240a15671484530b4e6e069ce266c28d7
got="$(git -C external/seL4 rev-parse HEAD)"
if [ "$got" != "$SEL4_SHA" ] || [ -n "$(git -C external/seL4 status --porcelain)" ]; then
    echo "error: external/seL4 is at $got (or dirty), expected a clean $SEL4_SHA" >&2
    exit 1
fi

rm -rf "$B"
mkdir -p "$B/sel4"

COMMON=(-DCROSS_COMPILER_PREFIX=aarch64-elf- -G Ninja)
RELEASE=(-DKernelDebugBuild=OFF -DKernelPrinting=OFF)
QEMU=(-DKernelPlatform=qemu-arm-virt -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57)
case "$ID" in
    K1R) CONFIG=("${COMMON[@]}" "${QEMU[@]}" -DKernelArmHypervisorSupport=OFF "${RELEASE[@]}" -S "$EXT/seL4" -B "$B/sel4") ;;
    K2R) CONFIG=("${COMMON[@]}" "${QEMU[@]}" -DKernelArmHypervisorSupport=OFF -DKernelMaxNumNodes=4 "${RELEASE[@]}" -S "$EXT/seL4" -B "$B/sel4") ;;
    E1HR) CONFIG=("${COMMON[@]}" "${QEMU[@]}" -DKernelArmHypervisorSupport=ON "${RELEASE[@]}" -S "$EXT/seL4" -B "$B/sel4") ;;
    K0Q) CONFIG=("${COMMON[@]}" -DKernelPlatform=qemu-arm-virt -DARM_CPU=cortex-a57 -C "$EXT/seL4/configs/AARCH64_verified.cmake" -S "$EXT/seL4" -B "$B/sel4") ;;
esac

{
    echo "# $ID: run from $W"
    echo "cmake ${CONFIG[*]}"
    echo "ninja -C $B/sel4 kernel.elf"
    echo "ninja -C $B/sel4 kernel_all_pp_wrapper"
} >"$B/command.txt"
{
    echo "compiler: $(aarch64-elf-gcc --version | head -1)"
    echo "compiler path: $(command -v aarch64-elf-gcc)"
    echo "cmake: $(cmake --version | head -1)"
    echo "ninja: $(ninja --version)"
    echo "python: $(python3 --version) at $(command -v python3)"
    echo "seL4 HEAD: $got; dirty files: 0"
} >"$B/tools.txt"

status=0
{
    cmake "${CONFIG[@]}" &&
        ninja -C "$B/sel4" kernel.elf &&
        ninja -C "$B/sel4" kernel_all_pp_wrapper
} >"$B/build.log" 2>&1 || status=$?
echo "$status" >"$B/BUILD_EXIT"
echo "$ID: build exit $status"
if [ "$status" -ne 0 ]; then
    tail -15 "$B/build.log"
    exit "$status"
fi

cp "$B/sel4/gen_config/kernel/gen_config.json" "$B/gen_config.json"
cp "$B/sel4/CMakeCache.txt" "$B/CMakeCache.txt"
cp "$B/sel4/kernel.elf" "$B/kernel.elf"
cp "$B/sel4/kernel_all_pp.c" "$B/kernel_all_pp.c"
cp "$B/sel4/kernel_all.i" "$B/kernel_all.i"
(
    cd "$B"
    shasum -a 256 gen_config.json kernel.elf kernel_all_pp.c kernel_all.i >SHA256SUMS
)
cat "$B/SHA256SUMS"
