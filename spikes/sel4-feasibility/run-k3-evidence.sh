#!/usr/bin/env bash
# K3: raw evidence in results-raw/K3 (gitignored) for the SMMU server in its own protection domain (results/K3.md). Run only after
# the design was reviewed and the sources below are fixed. Then:
#
#   spikes/sel4-feasibility/run-k3-evidence.sh
#   python3 spikes/sel4-feasibility/sanitize-run.py K3
#   python3 spikes/sel4-feasibility/verify-evidence.py
#
# On each of two kernels (K2: the matrix's K3 row, debug; K2R: the release variant; both non-hypervisor, 4 vCPUs, seL4's own
# elfloader): the design build three times; the naive control, and each of the six server mutants, once. Same machine as A5
# steps 1 and 2, plus QEMU's event trace as a channel that does not depend on the server. Emulator only. Installs nothing.
# Spike code.
set -uo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
EXT="$(cd external && pwd -P)"
R=results-raw/K3
RS=crates/e2-root-task/src
TS=crates/e2-task/src
SOURCES=(build-k3.sh build-relk.sh run-k3-evidence.sh verify_k3.py boot-a5.py a2a-compare.py
    "$TS/k3_abi.rs" "$TS/k3_mmio.rs" "$TS/k3_smmu.rs" "$TS/k3_runtime.rs" "$TS/bin/k3_server.rs" "$TS/bin/k3_client.rs"
    "$RS/bin/k3_root_task.rs" "$RS/k3_script.rs" "$RS/k3_spawn.rs" "$RS/k3_world.rs"
    "$RS/a5_mmio.rs" "$RS/child_vspace.rs" "$RS/edu.rs" "$RS/object_allocator.rs" "$RS/pl011.rs" "$RS/slots.rs")
MUTANTS=(skip-invalidate reclaim-while-mapped no-owner-check death-without-teardown shared-address-space shared-asid)
MACHINE=(--machine-extra "iommu=smmuv3,highmem=off" --device "edu,dma_mask=0xffffffffff" --device "edu,dma_mask=0xffffffffff")
TRACE=(--trace smmuv3_propagate_event)
export PATH="$W/.venv/bin:$PATH"

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
rm -rf "$R"
mkdir -p "$R"
{
    echo "# K3 preflight record, $(date -u +%Y-%m-%dT%H:%M:%SZ). Written before the builds."
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "qemu: $(qemu-system-aarch64 --version | head -1)"
    for repo in tools/seL4 projects/util_libs; do
        d="external/sel4test-workspace/$repo"
        echo "$repo HEAD: $(git -C "$d" rev-parse HEAD); dirty files: $(git -C "$d" status --porcelain | wc -l | tr -d ' ')"
    done
    echo "rust-sel4 HEAD: $(git -C external/rust-sel4 rev-parse HEAD); dirty files: $(git -C external/rust-sel4 status --porcelain | wc -l | tr -d ' ')"
    echo "Cargo.toml and Cargo.lock sha256: $(shasum -a 256 Cargo.toml Cargo.lock | cut -d' ' -f1 | tr '\n' ' ')"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock crates/e2-root-task/Cargo.toml crates/e2-task/Cargo.toml | wc -l | tr -d ' ') lines"
    for f in "${SOURCES[@]}"; do echo "src sha256: $(sha "$f")  $f"; done
} >"$R/00-preflight.txt"

run() { # label id variant
    python3 -B boot-a5.py --smp 4 "${MACHINE[@]}" "${TRACE[@]}" --marker K3_DONE --timeout 240 "$EXT/k3-build/$2-$3/image" >"$R/$1.txt" 2>&1
    echo "$1 exit $?"
}

: >"$R/02-sums.txt"
for ID in K2 K2R; do
    for v in design naive "${MUTANTS[@]}"; do
        ./build-k3.sh "$ID" "$v" >"$R/.b-$ID-$v.out" 2>&1 || { echo "build $ID $v failed"; tail -5 "$R/.b-$ID-$v.out"; exit 1; }
        B="$EXT/k3-build/$ID-$v"
        K="$EXT/relk-build/$ID-k3-$v"
        {
            echo "## $ID-$v: build exit $(cat "$B/BUILD_EXIT")"
            cat "$K/command.txt"
            cat "$B/build.log"
        } >"$R/01-build-$ID-$v.txt"
        {
            echo "k3-server-$ID-$v $(sha "$B/k3_server.elf")"
            echo "k3-client-$ID-$v $(sha "$B/k3_client.elf")"
            echo "k3-root-task-$ID-$v $(sha "$B/k3_root_task.elf")"
            echo "image-$ID-$v $(sha "$K/build/images/rust-root-task-image-arm-qemu-arm-virt")"
            echo "gen_config-$ID-$v $(sha "$K/build/kernel/gen_config/kernel/gen_config.json")"
            echo "prefix-gen_config-$ID-$v $(sha "$K/prefix/install/libsel4/include/kernel/gen_config.json")"
        } >>"$R/02-sums.txt"
    done
    # The kernel identity: the configuration and the function table of the design image's kernel, against the published ones.
    K="$EXT/relk-build/$ID-k3-design"
    python3 -B a2a-compare.py extract "$ID" --pp "$K/build/kernel/kernel_all_pp.c" --sel4 external/seL4 --build "$K/build/kernel" --out "$K/functions.tsv" >/dev/null || exit 1
    echo "functions-$ID $(sha "$K/functions.tsv")" >>"$R/02-sums.txt"
    if [ "$ID" = K2 ]; then rec=results/A2a; else rec=results/A2a-variants; fi
    echo "recorded-gen_config-$ID $(sha "$rec/gen_config-$ID.json")" >>"$R/02-sums.txt"
    echo "recorded-functions-$ID $(sha "$rec/functions-$ID.tsv")" >>"$R/02-sums.txt"
done
echo "k2-smc-dtb $(sha "$EXT/relk-build/k2-smc-a5s2.dtb")" >>"$R/02-sums.txt"

for ID in K2 K2R; do
    for n in 1 2 3; do run "10-$ID-design-$n" "$ID" design; done
    run "20-$ID-naive-1" "$ID" naive
    for m in "${MUTANTS[@]}"; do run "30-$ID-$m-1" "$ID" "$m"; done
done
rm -f "$R"/.b-*.out

{
    echo "# K3 post-run record, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 source tracked diff: $(git -C external/seL4 diff HEAD | wc -l | tr -d ' ') lines"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock crates/e2-root-task/Cargo.toml crates/e2-task/Cargo.toml | wc -l | tr -d ' ') lines"
    for f in "${SOURCES[@]}"; do echo "src sha256: $(sha "$f")  $f"; done
} >"$R/07-post-checks.txt"
echo ALL-DONE
