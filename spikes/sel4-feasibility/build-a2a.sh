#!/usr/bin/env bash
# A2a: build one seL4 kernel configuration, kernel only, and keep what the assurance comparison needs.
#
#   spikes/sel4-feasibility/build-a2a.sh K0|K1|K2|E1H
#
#   K0   the plan's reference: configs/AARCH64_verified.cmake of the pinned seL4 (decision 1c), as seL4 documents using it
#        (`cmake -C configs/AARCH64_verified.cmake`, then `ninja kernel.elf` and `ninja kernel_all_pp_wrapper`). Compile and compare only.
#   K1   AArch64 qemu-arm-virt, no hypervisor support, 1 vCPU: the A1 recipe (build.sh), unchanged options.
#   K2   K1 with 4 vCPUs (SMP): K1 plus -DKernelMaxNumNodes=4, nothing else.
#   E1H  the experiment-only hypervisor-enabled configuration of E1 to E3 (build-e1.sh's options). INFORMATIONAL: it is not a
#        row of the plan's assurance matrix.
#
# Output, in the gitignored external/a2a-build/ID (or $A2A_BUILD_ROOT/ID): command.txt (the exact commands), tools.txt (compiler, CMake, Ninja
# versions), build.log, gen_config.json, CMakeCache.txt, kernel.elf, kernel_all_pp.c, kernel_all.i, SHA256SUMS and
# BUILD_EXIT. It removes that directory first, does not touch the pinned checkouts, and installs nothing. It builds the
# kernel only: no loader, no root task, no boot. Spike code (see the plan's A2a entry).
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
ID="${1:-}"
case "$ID" in
    K0 | K1 | K2 | E1H) ;;
    *)
        echo "usage: build-a2a.sh K0|K1|K2|E1H" >&2
        exit 1
        ;;
esac
# A2A_BUILD_ROOT lets the evidence run build a second time elsewhere, to test that the comparison does not depend on the build directory.
B="${A2A_BUILD_ROOT:-$W/external/a2a-build}/$ID"
# The hash-pinned Python environment of A1 (seL4's generators need pyyaml and others); same as build.sh.
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
case "$ID" in
    K0) CONFIG=("${COMMON[@]}" -C "$W/external/seL4/configs/AARCH64_verified.cmake" -S external/seL4 -B "$B/sel4") ;;
    K1) CONFIG=("${COMMON[@]}" -DKernelPlatform=qemu-arm-virt -DKernelArmHypervisorSupport=OFF -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57 -S external/seL4 -B "$B/sel4") ;;
    K2) CONFIG=("${COMMON[@]}" -DKernelPlatform=qemu-arm-virt -DKernelArmHypervisorSupport=OFF -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57 -DKernelMaxNumNodes=4 -S external/seL4 -B "$B/sel4") ;;
    E1H) CONFIG=("${COMMON[@]}" -DKernelPlatform=qemu-arm-virt -DKernelArmHypervisorSupport=ON -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57 -S external/seL4 -B "$B/sel4") ;;
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
