#!/usr/bin/env bash
# Release-kernel execution: raw evidence in results-raw/ReleaseKernel (gitignored) that the release kernels K1R and K2R boot
# through seL4's elfloader and run the test root task, which logs through its own UART driver, with the debug kernels K1 and K2
# as controls, two deliberately broken tests, and two mismatched pairings. Then:
#
#   spikes/sel4-feasibility/run-relk-evidence.sh
#   python3 spikes/sel4-feasibility/sanitize-run.py ReleaseKernel
#   python3 spikes/sel4-feasibility/verify-evidence.py
#
# Images (build-relk.sh): K1, K1R, K2, K2R; K1R-skip-revoke and K2R-rw-alias (RELK_MUTANT); K1R-debug-root (the K1R kernel with
# the root task built for K1); K1R-putchar-demo (the K1R kernel with the A1 rerun's demo root task, which prints only through
# seL4_DebugPutChar). Needs the A1 rerun build (external/a1-rerun-build1) for that last control, and the A2a and A2a-variants
# evidence for the comparison of the kernels. Boots nothing but these images; installs nothing. Spike code.
set -uo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
EXT="$(cd external && pwd -P)"
R=results-raw/ReleaseKernel
RS=crates/e2-root-task/src
SOURCES=(build-relk.sh run-relk-evidence.sh boot-image.py a2a-compare.py "$RS/bin/relk_root_task.rs" "$RS/relk_tests.rs" "$RS/relk_workers.rs"
    "$RS/relk_spawn.rs" "$RS/slots.rs" "$RS/rawsys.rs" "$RS/pl011.rs" "$RS/a5_mmio.rs" "$RS/object_allocator.rs")
DEMO_ROOT="$EXT/a1-rerun-build1/s1-root-task.elf"
B="$EXT/relk-build"
export PATH="$W/.venv/bin:$PATH"

[ -f "$DEMO_ROOT" ] || { echo "error: $DEMO_ROOT is missing (the A1 rerun build)" >&2; exit 1; }
rm -rf "$R" "$B"
mkdir -p "$R" "$B"
record_sources() { for f in "${SOURCES[@]}"; do echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done; }
{
    echo "# Release-kernel execution preflight record, $(date -u +%Y-%m-%dT%H:%M:%SZ). Written before the builds."
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "qemu: $(qemu-system-aarch64 --version | head -1)"
    for repo in tools/seL4 projects/util_libs; do
        d="external/sel4test-workspace/$repo"
        echo "$repo HEAD: $(git -C "$d" rev-parse HEAD); dirty files: $(git -C "$d" status --porcelain | wc -l | tr -d ' ')"
    done
    echo "rust-sel4 HEAD: $(git -C external/rust-sel4 rev-parse HEAD); dirty files: $(git -C external/rust-sel4 status --porcelain | wc -l | tr -d ' ')"
    echo "Cargo.toml and Cargo.lock sha256: $(shasum -a 256 Cargo.toml Cargo.lock | cut -d' ' -f1 | tr '\n' ' ')"
    echo "demo root task sha256: $(shasum -a 256 "$DEMO_ROOT" | cut -d' ' -f1)"
    record_sources
} >"$R/00-preflight.txt"

# The device tree with the smc PSCI method for the 4-node kernels, from the QEMU that boots them (see results/RouteI.md).
DTB="$B/k2-smc.dtb"
qemu-system-aarch64 -machine virt,secure=off,virtualization=on,gic-version=2,dumpdtb="$DTB" -cpu cortex-a57 -smp 4 -m 1024 -nographic >/dev/null 2>&1
dtc -I dtb -O dts "$DTB" 2>/dev/null | grep -v "rng-seed\|kaslr-seed" >"$R/05-k2-smc.dts"

build() { # name id [dtb]; RELK_MUTANT and RELK_ROOT_ELF come from the caller's environment
    local name="$1" id="$2" dtb="${3:-}"
    RELK_NAME="$name" ./build-relk.sh "$id" ${dtb:+"$dtb"} >"$R/.b-$name.out" 2>&1 || { echo "build of $name failed"; tail -5 "$R/.b-$name.out"; exit 1; }
}
build K1 K1
build K1R K1R
build K2 K2 "$DTB"
build K2R K2R "$DTB"
RELK_MUTANT=skip-revoke build K1R-skip-revoke K1R
RELK_MUTANT=rw-alias build K2R-rw-alias K2R "$DTB"
RELK_ROOT_ELF="$B/K1/relk_root_task.elf" build K1R-debug-root K1R
RELK_ROOT_ELF="$DEMO_ROOT" build K1R-putchar-demo K1R
NAMES=(K1 K1R K2 K2R K1R-skip-revoke K2R-rw-alias K1R-debug-root K1R-putchar-demo)

cp "$B/K1/tools.txt" "$R/01-tools.txt"
{ for n in "${NAMES[@]}"; do echo "## $n"; cat "$B/$n/command.txt"; done; } >"$R/02-commands.txt"
for n in "${NAMES[@]}"; do
    { echo "## $n: build exit $(cat "$B/$n/BUILD_EXIT")"; cat "$B/$n/build.log"; } >"$R/03-build-$n.txt"
done
IMG() { echo "$B/$1/build/images/rust-root-task-image-arm-qemu-arm-virt"; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
{
    echo "# Hashes. Per image: the root task, the image, the kernel ELF, the kernel configuration of the image and of the interface the"
    echo "# root task was built against, and the function table a2a-compare.py extracts from the image's preprocessed kernel. Then the"
    echo "# recorded configurations and function tables of A2a (K1, K2) and A2a-variants (K1R, K2R) that they must equal."
    for n in "${NAMES[@]}"; do
        id="${n%%-*}"
        python3 -B a2a-compare.py extract "$id" --pp "$B/$n/build/kernel/kernel_all_pp.c" --sel4 external/seL4 \
            --build "$B/$n/build/kernel" --out "$B/$n/functions.tsv" >/dev/null || exit 1
        echo "root-task-$n $(sha "$B/$n/relk_root_task.elf")"
        echo "image-$n $(sha "$(IMG "$n")")"
        echo "kernel-$n $(sha "$B/$n/build/kernel/kernel.elf")"
        echo "gen_config-$n $(sha "$B/$n/build/kernel/gen_config/kernel/gen_config.json")"
        echo "prefix-gen_config-$n $(sha "$B/$n/prefix/install/libsel4/include/kernel/gen_config.json")"
        echo "functions-$n $(sha "$B/$n/functions.tsv")"
    done
    echo "k2-smc-dtb $(sha "$DTB")"
    for id in K1 K2; do
        echo "recorded-gen_config-$id $(sha "results/A2a/gen_config-$id.json")"
        echo "recorded-functions-$id $(sha "results/A2a/functions-$id.tsv")"
    done
    for id in K1R K2R; do
        echo "recorded-gen_config-$id $(sha "results/A2a-variants/gen_config-$id.json")"
        echo "recorded-functions-$id $(sha "results/A2a-variants/functions-$id.tsv")"
    done
} >"$R/04-sums.txt"

boot() { # label name marker timeout extra-args...
    local label="$1" name="$2" marker="$3" timeout="$4"; shift 4
    python3 -B boot-image.py "$@" --gic 2 --marker "$marker" --timeout "$timeout" "$(IMG "$name")" >"$R/$label.txt" 2>&1
    echo "$label exit $?"
}
for n in 1 2 3; do
    boot "10-boot-K1R-$n" K1R RELK_PASS 120 --smp 1
    boot "11-boot-K2R-$n" K2R RELK_PASS 180 --smp 4 --virt
done
boot "12-control-K1-debug" K1 RELK_PASS 120 --smp 1
boot "13-control-K2-debug" K2 RELK_PASS 180 --smp 4 --virt
boot "20-mutant-K1R-skip-revoke" K1R-skip-revoke RELK_FAIL 120 --smp 1
boot "21-mutant-K2R-rw-alias" K2R-rw-alias RELK_FAIL 180 --smp 4 --virt
boot "22-neg-K1R-with-debug-built-root-task" K1R-debug-root RELK_FAIL 120 --smp 1
boot "23-neg-K1R-with-debugputchar-demo" K1R-putchar-demo TEST_PASS 20 --smp 1
rm -f "$R"/.b-*.out

{
    echo "# Release-kernel execution post-run record, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 source tracked diff: $(git -C external/seL4 diff HEAD | wc -l | tr -d ' ') lines"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock crates/e2-root-task/Cargo.toml | wc -l | tr -d ' ') lines"
    record_sources
} >"$R/07-post-checks.txt"
echo ALL-DONE
