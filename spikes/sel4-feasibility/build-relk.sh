#!/usr/bin/env bash
# Release-kernel execution: build one kernel configuration of the Stage B matrix (K1, K1R, K2, K2R), the release-kernel
# test root task (crates/e2-root-task/src/bin/relk_root_task.rs) against that kernel's own interface, and a bootable image of
# both with seL4's own elfloader. The project is generated as build-routei.sh generates it (that script is left unchanged,
# because the Route I evidence records its hash); the only additions are the two release options and the test root task.
#
#   spikes/sel4-feasibility/build-relk.sh ID [QEMU_DTB]
#
#   ID        K1   non-hypervisor, 1 node, debug (the A2a recipe)
#             K1R  K1 with KernelDebugBuild=OFF and KernelPrinting=OFF
#             K2   K1 with 4 nodes
#             K2R  K2 with the two release options
#   QEMU_DTB  optional device tree in place of the one seL4's CMake dumps from QEMU. K2 and K2R need one whose PSCI method is
#             `smc` (see results/RouteI.md).
#
# Environment: RELK_BIN (optional) is the binary of the e2-root-task crate to build as the root task, default relk_root_task
# (the A5 step 1 experiment, a5_step1_root_task, is built this way to run on these kernels); RELK_MUTANT (optional) is passed to the root task's build and names a deliberately broken test; RELK_NAME
# (optional) is the output directory name, default ID; RELK_ROOT_ELF (optional) is a prebuilt root task to put in the image
# in place of building one, for the controls that pair a kernel with a root task built for another kernel. Output, in the gitignored external/relk-build/NAME: prefix/ (the
# kernel's installed interface), relk_root_task.elf, the generated project and its build tree, build.log, command.txt,
# tools.txt, SHA256SUMS, BUILD_EXIT. No kernel, elfloader or dependency is changed; nothing is installed. Spike code.
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
ID="${1:-}"
DTB="${2:-}"
NODES=1
RELEASE=0
case "$ID" in
    K1) ;;
    K1R) RELEASE=1 ;;
    K2) NODES=4 ;;
    K2R)
        NODES=4
        RELEASE=1
        ;;
    *)
        echo "usage: build-relk.sh K1|K1R|K2|K2R [QEMU_DTB]" >&2
        exit 1
        ;;
esac
EXT="$(cd "$W/external" && pwd -P)"
P="$EXT/relk-build/${RELK_NAME:-$ID}"
BIN="${RELK_BIN:-relk_root_task}"
SEL4_SHA=62e345c240a15671484530b4e6e069ce266c28d7
got="$(git -C "$EXT/seL4" rev-parse HEAD)"
if [ "$got" != "$SEL4_SHA" ] || [ -n "$(git -C "$EXT/seL4" status --porcelain)" ]; then
    echo "error: external/seL4 is at $got (or dirty), expected a clean $SEL4_SHA" >&2
    exit 1
fi
if [ -n "${RELK_ROOT_ELF:-}" ] && [ ! -f "$RELK_ROOT_ELF" ]; then
    echo "error: root task '$RELK_ROOT_ELF' not found" >&2
    exit 1
fi
if [ -n "$DTB" ] && [ ! -f "$DTB" ]; then
    echo "error: device tree '$DTB' not found" >&2
    exit 1
fi
export PATH="/opt/homebrew/opt/cpio/bin:$W/.venv/bin:$PATH"

rm -rf "$P"
mkdir -p "$P/projects/relk" "$P/build" "$P/prefix"

# The kernel options, once, for the prefix build (plain CMake) and the image build (seL4's init-build.sh).
KOPTS=(-DKernelPlatform=qemu-arm-virt -DKernelArmHypervisorSupport=OFF -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57)
[ "$NODES" -gt 1 ] && KOPTS+=("-DKernelMaxNumNodes=$NODES")
[ "$RELEASE" -eq 1 ] && KOPTS+=(-DKernelDebugBuild=OFF -DKernelPrinting=OFF)
ARGS=(-DPLATFORM=qemu-arm-virt -DAARCH64=1 -DCROSS_COMPILER_PREFIX=aarch64-elf- "-DRELK_RELEASE=$RELEASE")
[ "$NODES" -gt 1 ] && ARGS+=(-DSMP=TRUE "-DNUM_NODES=$NODES")
[ -n "$DTB" ] && ARGS+=("-DQEMU_DTB=$DTB")

# The kernel source is named by its physical path, not through a link in the project: the compiler records the path it is
# given, and a2a-compare.py (which extracts the kernel's function table for the comparison with the A2a variants) normalises the
# resolved one.
ln -s "$EXT/seL4" "$P/kernel"
echo "set(RELK_KERNEL_DIR \"$EXT/seL4\")" >"$P/projects/relk/paths.cmake"
ln -s "$EXT/sel4test-workspace/tools" "$P/tools"
ln -s tools/seL4/cmake-tool/init-build.sh "$P/init-build.sh"
ln -s tools/seL4/cmake-tool/griddle "$P/griddle"
ln -s projects/relk/easy-settings.cmake "$P/easy-settings.cmake"
ln -s "$EXT/sel4test-workspace/projects/util_libs" "$P/projects/util_libs"

cat >"$P/projects/relk/easy-settings.cmake" <<'CMAKE'
set(PLATFORM "qemu-arm-virt" CACHE STRING "Platform")
set(KernelSel4Arch "aarch64" CACHE STRING "")
set(SMP OFF CACHE BOOL "")
set(NUM_NODES "" CACHE STRING "")
set(RELK_RELEASE 0 CACHE STRING "1: build the kernel without debug facilities and without printing")
CMAKE
cat >"$P/projects/relk/settings.cmake" <<'CMAKE'
cmake_minimum_required(VERSION 3.16.0)
set(project_dir "${CMAKE_CURRENT_LIST_DIR}/../..")
include(${CMAKE_CURRENT_LIST_DIR}/paths.cmake)
list(APPEND CMAKE_MODULE_PATH ${RELK_KERNEL_DIR} ${project_dir}/tools/seL4/cmake-tool/helpers/
     ${project_dir}/tools/seL4/elfloader-tool/)
set(SEL4_CONFIG_DEFAULT_ADVANCED ON)
include(application_settings)
include(${CMAKE_CURRENT_LIST_DIR}/easy-settings.cmake)
correct_platform_strings()
find_package(seL4 REQUIRED)
sel4_configure_platform_settings()
# The options of build-a2a.sh's K1 and K2 and, for the release rows, the two options of build-a2a-variants.sh. Nothing else.
set(KernelArmHypervisorSupport OFF CACHE BOOL "" FORCE)
set(KernelVerificationBuild OFF CACHE BOOL "" FORCE)
set(ARM_CPU "cortex-a57" CACHE STRING "" FORCE)
if(SMP)
  set(KernelMaxNumNodes ${NUM_NODES} CACHE STRING "" FORCE)
endif()
if(RELK_RELEASE)
  set(KernelDebugBuild OFF CACHE BOOL "" FORCE)
  set(KernelPrinting OFF CACHE BOOL "" FORCE)
endif()
CMAKE
cat >"$P/projects/relk/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.16.0)
include(settings.cmake)
project(relk C CXX ASM)
find_package(seL4 REQUIRED)
find_package(elfloader-tool REQUIRED)
sel4_import_kernel()
sel4_import_libsel4()
ApplyData61ElfLoaderSettings(${KernelPlatform} ${KernelSel4Arch})
# The elfloader links util_libs' small cpio library.
add_subdirectory("${CMAKE_SOURCE_DIR}/../util_libs/libcpio" libcpio)
elfloader_import_project()
# The Rust root task is prebuilt. A dummy executable gives seL4's image machinery a real target; its output is replaced by
# the prebuilt ELF straight after linking.
file(WRITE "${CMAKE_BINARY_DIR}/dummy.c" "void _sel4_start(void) { for (;;) { } }\n")
add_executable(rust-root-task "${CMAKE_BINARY_DIR}/dummy.c")
target_link_options(rust-root-task PRIVATE -nostdlib -static)
add_custom_command(TARGET rust-root-task POST_BUILD
                   COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_SOURCE_DIR}/../../relk_root_task.elf" "$<TARGET_FILE:rust-root-task>")
include(rootserver)
DeclareRootserver(rust-root-task)
CMAKE

{
    echo "# $ID (${RELK_NAME:-$ID}), root task: $BIN, mutant: ${RELK_MUTANT:-${A5S1_MUTANT:-${A5S2_MUTANT:-none}}}, prebuilt root task: ${RELK_ROOT_ELF:-none}"
    echo "# 1. kernel interface (prefix), in $P/prefix"
    echo "cmake -DCROSS_COMPILER_PREFIX=aarch64-elf- -DCMAKE_INSTALL_PREFIX=$P/prefix/install ${KOPTS[*]} -G Ninja -S $EXT/seL4 -B $P/prefix/sel4"
    echo "ninja -C $P/prefix/sel4 all install"
    echo "# 2. root task, with SEL4_PREFIX=$P/prefix/install"
    echo "cargo build --locked --release -p e2-root-task --bin $BIN --target aarch64-sel4 ..."
    echo "# 3. image, in $P/build"
    echo "../init-build.sh ${ARGS[*]}"
    echo "ninja"
    echo "ninja kernel_all_pp_wrapper"
} >"$P/command.txt"
{
    echo "compiler: $(aarch64-elf-gcc --version | head -1)"
    echo "cmake: $(cmake --version | head -1)"
    echo "ninja: $(ninja --version)"
    echo "cpio: $(cpio --version | head -1)"
    echo "rustc: $(RUSTUP_TOOLCHAIN=nightly-2026-08-21 RUSTUP_AUTO_INSTALL=0 rustc --version)"
    echo "seL4 HEAD: $got; dirty files: 0"
} >"$P/tools.txt"

build_root_task() {
    if [ -n "${RELK_ROOT_ELF:-}" ]; then
        echo "using the prebuilt root task $RELK_ROOT_ELF"
        cp "$RELK_ROOT_ELF" "$P/relk_root_task.elf"
        return
    fi
    export RUSTUP_TOOLCHAIN=nightly-2026-08-21 RUSTUP_AUTO_INSTALL=0
    export CC_aarch64_unknown_none=aarch64-elf-gcc AR_aarch64_unknown_none=aarch64-elf-ar RANLIB_aarch64_unknown_none=aarch64-elf-ranlib
    export SEL4_PREFIX="$P/prefix/install" RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" RUSTFLAGS="-Zunstable-options"
    cargo build --locked --release -p e2-root-task --bin "$BIN" \
        --target aarch64-sel4 -Z unstable-options -Z build-std=core,alloc,compiler_builtins \
        -Z build-std-features=compiler-builtins-mem --target-dir "$P/target" --artifact-dir "$P" || return
    # The generated project copies the root task from this fixed name.
    [ "$BIN" = relk_root_task ] || cp "$P/$BIN.elf" "$P/relk_root_task.elf"
}

status=0
{
    cmake -DCROSS_COMPILER_PREFIX=aarch64-elf- -DCMAKE_INSTALL_PREFIX="$P/prefix/install" "${KOPTS[@]}" -G Ninja -S "$EXT/seL4" -B "$P/prefix/sel4" &&
        ninja -C "$P/prefix/sel4" all install &&
        (build_root_task) &&
        (cd "$P/build" && ../init-build.sh "${ARGS[@]}" && ninja && ninja kernel_all_pp_wrapper)
} >"$P/build.log" 2>&1 || status=$?
echo "$status" >"$P/BUILD_EXIT"
echo "${RELK_NAME:-$ID}: build exit $status"
if [ "$status" -ne 0 ]; then
    tail -25 "$P/build.log"
    exit "$status"
fi
(
    cd "$P"
    shasum -a 256 relk_root_task.elf build/images/rust-root-task-image-arm-qemu-arm-virt build/kernel/kernel.elf \
        build/kernel/gen_config/kernel/gen_config.json prefix/install/libsel4/include/kernel/gen_config.json >SHA256SUMS
)
cat "$P/SHA256SUMS"
