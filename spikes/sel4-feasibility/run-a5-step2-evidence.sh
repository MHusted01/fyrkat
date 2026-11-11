#!/usr/bin/env bash
# A5 step 2: raw evidence in results-raw/A5-step2 (gitignored) for the revoke-while-mapped experiment (results/A5-step2.md):
# with a device stream's stage-1 mapping of a frame in place, the frame's untyped is revoked and its memory handed out again.
# Run only after the experiment's design was reviewed. Then:
#
#   spikes/sel4-feasibility/run-a5-step2-evidence.sh
#   python3 spikes/sel4-feasibility/sanitize-run.py A5-step2
#   python3 spikes/sel4-feasibility/verify-evidence.py
#
# Two kernels, as step 1: the E1-H kernel with the Rust loader (needs external/e3-build) and K2R with seL4's elfloader
# (build-relk.sh). On each: the experiment three times. On E1-H also the mutant (the teardown of scenario B without its
# invalidation command), once. Same machine and trace as step 1. Emulator only; exploratory; not an A5 outcome. Installs
# nothing. Spike code.
set -uo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
EXT="$(cd external && pwd -P)"
R=results-raw/A5-step2
RS=crates/e2-root-task/src
SOURCES=(build-a5-e1h.sh build-relk.sh run-a5-step2-evidence.sh verify_a5_step2.py boot-a5.py a2a-compare.py "$RS/bin/a5_step2_root_task.rs" "$RS/a5_step2_tests.rs"
    "$RS/smmuv3.rs" "$RS/edu.rs" "$RS/slots.rs" "$RS/pl011.rs" "$RS/a5_mmio.rs" "$RS/object_allocator.rs")
E3="$EXT/e3-build"
MUTANTS=(teardown-without-invalidation)
TRACE=(--trace "smmuv3_translate_*" --trace smmuv3_propagate_event --trace "smmuv3_cmdq_cfgi_*" --trace smmuv3_cmdq_tlbi_nsnh --trace smmuv3_range_inval)
MACHINE=(--machine-extra "iommu=smmuv3,highmem=off" --device "edu,dma_mask=0xffffffffff" --device "edu,dma_mask=0xffffffffff")
export PATH="$W/.venv/bin:$PATH"

rm -rf "$R" "$EXT/a5-step2-build" "$EXT/relk-build/K2R-a5s2"
mkdir -p "$R" "$EXT/relk-build"
record_sources() { for f in "${SOURCES[@]}"; do echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
{
    echo "# A5 step 2 preflight record, $(date -u +%Y-%m-%dT%H:%M:%SZ). Written before the builds."
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "qemu: $(qemu-system-aarch64 --version | head -1)"
    for repo in tools/seL4 projects/util_libs; do
        d="external/sel4test-workspace/$repo"
        echo "$repo HEAD: $(git -C "$d" rev-parse HEAD); dirty files: $(git -C "$d" status --porcelain | wc -l | tr -d ' ')"
    done
    echo "rust-sel4 HEAD: $(git -C external/rust-sel4 rev-parse HEAD); dirty files: $(git -C external/rust-sel4 status --porcelain | wc -l | tr -d ' ')"
    echo "Cargo.toml and Cargo.lock sha256: $(shasum -a 256 Cargo.toml Cargo.lock | cut -d' ' -f1 | tr '\n' ' ')"
    # The E1-H kernel and loader the images are made from (the files build-a5-e1h.sh passes to the loader's add-payload tool).
    echo "e3 kernel.elf sha256: $(sha "$E3/sel4-install/bin/kernel.elf")"
    echo "e3 sel4-kernel-loader.elf sha256: $(sha "$E3/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader")"
    record_sources
} >"$R/00-preflight.txt"

for name in main "${MUTANTS[@]}"; do
    args=(step2)
    [ "$name" = main ] || args+=("$name")
    ./build-a5-e1h.sh "${args[@]}" >"$R/.b-$name.out" 2>&1 || { echo "build $name failed"; tail -5 "$R/.b-$name.out"; exit 1; }
    { echo "## e1h-$name: build exit $(cat "$EXT/a5-step2-build/$name/BUILD_EXIT")"; cat "$EXT/a5-step2-build/$name/build.log"; } >"$R/01-build-e1h-$name.txt"
done
DTB="$EXT/relk-build/k2-smc-a5s2.dtb"
qemu-system-aarch64 -machine virt,secure=off,virtualization=on,gic-version=2,dumpdtb="$DTB" -cpu cortex-a57 -smp 4 -m 1024 -nographic >/dev/null 2>&1
RELK_BIN=a5_step2_root_task RELK_NAME=K2R-a5s2 ./build-relk.sh K2R "$DTB" >"$R/.b-k2r.out" 2>&1 || { echo "build K2R failed"; tail -5 "$R/.b-k2r.out"; exit 1; }
K2R="$EXT/relk-build/K2R-a5s2"
{ echo "## k2r-main: build exit $(cat "$K2R/BUILD_EXIT")"; cat "$K2R/command.txt"; cat "$K2R/build.log"; } >"$R/01-build-k2r-main.txt"
python3 -B a2a-compare.py extract K2R --pp "$K2R/build/kernel/kernel_all_pp.c" --sel4 external/seL4 --build "$K2R/build/kernel" --out "$K2R/functions.tsv" >/dev/null || exit 1
K2R_IMAGE="$K2R/build/images/rust-root-task-image-arm-qemu-arm-virt"
{
    echo "# Hashes: the root task and image of each build; for K2R also the kernel configuration of the image and of the interface the"
    echo "# root task was built against, the function table extracted from the image's kernel, and the recorded K2R they must equal."
    for name in main "${MUTANTS[@]}"; do
        echo "root-task-e1h-$name $(sha "$EXT/a5-step2-build/$name/a5_step2_root_task.elf")"
        echo "image-e1h-$name $(sha "$EXT/a5-step2-build/$name/image.elf")"
    done
    echo "root-task-k2r-main $(sha "$K2R/relk_root_task.elf")"
    echo "image-k2r-main $(sha "$K2R_IMAGE")"
    echo "gen_config-k2r $(sha "$K2R/build/kernel/gen_config/kernel/gen_config.json")"
    echo "prefix-gen_config-k2r $(sha "$K2R/prefix/install/libsel4/include/kernel/gen_config.json")"
    echo "functions-k2r $(sha "$K2R/functions.tsv")"
    echo "recorded-gen_config-K2R $(sha results/A2a-variants/gen_config-K2R.json)"
    echo "recorded-functions-K2R $(sha results/A2a-variants/functions-K2R.tsv)"
    echo "k2-smc-dtb $(sha "$DTB")"
} >"$R/02-sums.txt"

run() { # label smp marker image
    python3 -B boot-a5.py --smp "$2" "${MACHINE[@]}" "${TRACE[@]}" --marker "$3" --timeout 180 "$4" >"$R/$1.txt" 2>&1
    echo "$1 exit $?"
}
for n in 1 2 3; do
    run "10-e1h-main-$n" 1 A5S2_DONE "$EXT/a5-step2-build/main/image.elf"
    run "11-k2r-main-$n" 4 A5S2_DONE "$K2R_IMAGE"
done
for m in "${MUTANTS[@]}"; do run "20-mutant-e1h-$m" 1 A5S2_DONE "$EXT/a5-step2-build/$m/image.elf"; done
rm -f "$R"/.b-*.out

{
    echo "# A5 step 2 post-run record, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 source tracked diff: $(git -C external/seL4 diff HEAD | wc -l | tr -d ' ') lines"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock crates/e2-root-task/Cargo.toml | wc -l | tr -d ' ') lines"
    record_sources
} >"$R/07-post-checks.txt"
echo ALL-DONE
