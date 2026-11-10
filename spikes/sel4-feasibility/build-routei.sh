#!/usr/bin/env bash
# Route I feasibility (Stage B preparation): build a kernel configuration of the plan's matrix (K1 or K2, non-hypervisor) together
# with seL4's own elfloader and a PREBUILT Rust root task into one bootable image, using seL4's cmake-tool as sel4test does.
#
#   spikes/sel4-feasibility/build-routei.sh ID ROOT_TASK_ELF [QEMU_DTB]
#
#   ID           K1 (1 node), K2 (4 nodes) or K2H (K2, but with seL4's default device tree: a negative control); the kernel options are those of build-a2a.sh, and the recorded gen_config.json
#                is compared with the A2a one.
#   ROOT_TASK_ELF  the Rust root task, built elsewhere against the matching kernel prefix (not rebuilt here).
#   QEMU_DTB     optional: a device tree to use in place of the one seL4's CMake extracts from QEMU (for K2, see the record).
#
# Output, in the gitignored external/routei-build/ID: the minimal project, the build tree, images/rust-root-task-image-arm-qemu-arm-virt,
# build.log, command.txt, tools.txt, SHA256SUMS. Needs GNU cpio (keg-only Homebrew formula, D1) as build-sel4test.sh does. No kernel,
# elfloader or root-task source is changed. Spike code (see the plan's Stage B preparation entry).
set -euo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
ID="${1:-}"
ROOT="${2:-}"
DTB="${3:-}"
case "$ID" in
    K1) NODES=1 ;;
    K2 | K2H) NODES=4 ;; # K2H: K2 with the device tree seL4's CMake extracts by default (PSCI conduit hvc): a negative control
    *)
        echo "usage: build-routei.sh K1|K2|K2H ROOT_TASK_ELF [QEMU_DTB]" >&2
        exit 1
        ;;
esac
[ -f "$ROOT" ] || { echo "error: root task ELF '$ROOT' not found" >&2; exit 1; }
EXT="$(cd "$W/external" && pwd -P)"
P="$EXT/routei-build/${ROUTEI_NAME:-$ID}" # ROUTEI_NAME: a directory name other than the ID, for controls
SEL4_SHA=62e345c240a15671484530b4e6e069ce266c28d7
got="$(git -C "$EXT/seL4" rev-parse HEAD)"
if [ "$got" != "$SEL4_SHA" ] || [ -n "$(git -C "$EXT/seL4" status --porcelain)" ]; then
    echo "error: external/seL4 is at $got (or dirty), expected a clean $SEL4_SHA" >&2
    exit 1
fi
export PATH="/opt/homebrew/opt/cpio/bin:$W/.venv/bin:$PATH"

rm -rf "$P"
mkdir -p "$P/projects/routei" "$P/build"
ln -s "$EXT/seL4" "$P/kernel"
ln -s "$EXT/sel4test-workspace/tools" "$P/tools"
ln -s tools/seL4/cmake-tool/init-build.sh "$P/init-build.sh"
ln -s tools/seL4/cmake-tool/griddle "$P/griddle"
ln -s projects/routei/easy-settings.cmake "$P/easy-settings.cmake"
ln -s "$EXT/sel4test-workspace/projects/util_libs" "$P/projects/util_libs"
cp "$ROOT" "$P/rust-root-task.elf"

cat >"$P/projects/routei/easy-settings.cmake" <<'CMAKE'
set(PLATFORM "qemu-arm-virt" CACHE STRING "Platform")
set(KernelSel4Arch "aarch64" CACHE STRING "")
set(SMP OFF CACHE BOOL "")
set(NUM_NODES "" CACHE STRING "")
CMAKE
cat >"$P/projects/routei/settings.cmake" <<'CMAKE'
cmake_minimum_required(VERSION 3.16.0)
set(project_dir "${CMAKE_CURRENT_LIST_DIR}/../..")
list(APPEND CMAKE_MODULE_PATH ${project_dir}/kernel ${project_dir}/tools/seL4/cmake-tool/helpers/
     ${project_dir}/tools/seL4/elfloader-tool/)
set(SEL4_CONFIG_DEFAULT_ADVANCED ON)
include(application_settings)
include(${CMAKE_CURRENT_LIST_DIR}/easy-settings.cmake)
correct_platform_strings()
find_package(seL4 REQUIRED)
sel4_configure_platform_settings()
# The options of build-a2a.sh's K1 and K2, and nothing else.
set(KernelArmHypervisorSupport OFF CACHE BOOL "" FORCE)
set(KernelVerificationBuild OFF CACHE BOOL "" FORCE)
set(ARM_CPU "cortex-a57" CACHE STRING "" FORCE)
if(SMP)
  set(KernelMaxNumNodes ${NUM_NODES} CACHE STRING "" FORCE)
endif()
CMAKE
cat >"$P/projects/routei/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.16.0)
include(settings.cmake)
project(routei C CXX ASM)
find_package(seL4 REQUIRED)
find_package(elfloader-tool REQUIRED)
sel4_import_kernel()
sel4_import_libsel4()
ApplyData61ElfLoaderSettings(${KernelPlatform} ${KernelSel4Arch})
# The elfloader links util_libs' small cpio library.
add_subdirectory("${CMAKE_SOURCE_DIR}/../util_libs/libcpio" libcpio)
elfloader_import_project()
# The Rust root task is prebuilt; seL4's image machinery only needs its path.
# A dummy executable gives the image machinery a real target; its output is replaced by the prebuilt ELF straight after linking.
file(WRITE "${CMAKE_BINARY_DIR}/dummy.c" "void _sel4_start(void) { for (;;) { } }\n")
add_executable(rust-root-task "${CMAKE_BINARY_DIR}/dummy.c")
target_link_options(rust-root-task PRIVATE -nostdlib -static)
add_custom_command(TARGET rust-root-task POST_BUILD
                   COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_SOURCE_DIR}/../../rust-root-task.elf" "$<TARGET_FILE:rust-root-task>")
include(rootserver)
DeclareRootserver(rust-root-task)
CMAKE

ARGS=(-DPLATFORM=qemu-arm-virt -DAARCH64=1 -DCROSS_COMPILER_PREFIX=aarch64-elf-)
[ "$NODES" -gt 1 ] && ARGS+=(-DSMP=TRUE "-DNUM_NODES=$NODES")
[ -n "$DTB" ] && ARGS+=("-DQEMU_DTB=$DTB")
{
    echo "# $ID: run in $P/build"
    echo "../init-build.sh ${ARGS[*]}"
    echo "ninja"
} >"$P/command.txt"
{
    echo "compiler: $(aarch64-elf-gcc --version | head -1)"
    echo "cmake: $(cmake --version | head -1)"
    echo "ninja: $(ninja --version)"
    echo "cpio: $(cpio --version | head -1)"
    echo "seL4 HEAD: $got; dirty files: 0"
} >"$P/tools.txt"

status=0
(
    cd "$P/build"
    ../init-build.sh "${ARGS[@]}" && ninja
) >"$P/build.log" 2>&1 || status=$?
echo "$status" >"$P/BUILD_EXIT"
echo "$ID: build exit $status"
if [ "$status" -ne 0 ]; then
    tail -20 "$P/build.log"
    exit "$status"
fi
(
    cd "$P/build"
    shasum -a 256 images/* kernel/gen_config/kernel/gen_config.json >"$P/SHA256SUMS" 2>/dev/null || shasum -a 256 images/* >"$P/SHA256SUMS"
)
cat "$P/SHA256SUMS"
