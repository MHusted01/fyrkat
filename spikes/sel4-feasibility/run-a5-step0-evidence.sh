#!/usr/bin/env bash
# A5 step 0: raw evidence in results-raw/A5-step0 (gitignored). An environment and feasibility probe, NOT the A5 experiment: it
# never enables the SMMU or builds a stream table. Then:
#
#   spikes/sel4-feasibility/run-a5-step0-evidence.sh
#   python3 spikes/sel4-feasibility/sanitize-run.py A5-step0
#   python3 spikes/sel4-feasibility/verify-evidence.py
#
# Needs the E3 evidence build (external/e3-build) for the kernel and loader. Builds the probe twice (ECAM at 0x3f000000 for
# highmem=off, at 0x4010000000 for the default highmem=on), dumps the device trees QEMU generates for the SMMUv3 arrangement, shows what
# the kernel's own tree contains, and boots: the primary arrangement (SMMUv3, a wide-mask edu) three times, the other cases once.
# Installs nothing. Spike code.
set -uo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
EXT="$(cd external && pwd -P)"
R=results-raw/A5-step0
SOURCES=(build-a5-probe.sh run-a5-step0-evidence.sh boot-a5.py crates/e2-root-task/src/bin/a5_probe_root_task.rs
    crates/e2-root-task/src/a5_mmio.rs crates/e2-root-task/src/object_allocator.rs)
E3="$EXT/e3-build"
TRACE=(--trace "smmuv3_translate_*")
rm -rf "$R"
mkdir -p "$R"
{
    echo "# A5 step 0 preflight record, $(date -u +%Y-%m-%dT%H:%M:%SZ). Written before the builds."
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "branch: $(git branch --show-current)"
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "qemu: $(qemu-system-aarch64 --version | head -1)"
    echo "Cargo.toml and Cargo.lock sha256: $(shasum -a 256 Cargo.toml Cargo.lock | cut -d' ' -f1 | tr '\n' ' ')"
    # The files the image is made from (build-a5-probe.sh passes these to the loader's add-payload tool), not copies of them.
    echo "e3 kernel.elf sha256: $(shasum -a 256 "$E3/sel4-install/bin/kernel.elf" | cut -d' ' -f1)"
    echo "e3 sel4-kernel-loader.elf sha256: $(shasum -a 256 "$E3/rust-sel4-target/aarch64-unknown-none/release/sel4-kernel-loader" | cut -d' ' -f1)"
    for f in "${SOURCES[@]}"; do echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done
} >"$R/00-preflight.txt"

for mode in low high; do
    ./build-a5-probe.sh "$mode" >"$R/.build-$mode.out" 2>&1 || { echo "build $mode failed"; tail -5 "$R/.build-$mode.out"; exit 1; }
    { echo "## $mode: build exit $(cat "$EXT/a5-step0-build-$mode/BUILD_EXIT")"; cat "$EXT/a5-step0-build-$mode/build.log"; } >"$R/01-build-$mode.txt"
done
{ for mode in low high; do echo "## $mode"; cat "$EXT/a5-step0-build-$mode/SHA256SUMS"; done; } >"$R/02-sums.txt"

# The trees QEMU generates for the arrangement, and what the kernel's own tree has.
dump() { # label machine-extra
    qemu-system-aarch64 -machine "virt,secure=off,gic-version=2,virtualization=on,$2,dumpdtb=$R/.$1.dtb" -cpu cortex-a57 -smp 1 -m 1024 -nographic -device edu >/dev/null 2>&1
    dtc -I dtb -O dts "$R/.$1.dtb" 2>/dev/null | grep -v "rng-seed\|kaslr-seed" >"$R/03-qemu-$1.dts"
    rm -f "$R/.$1.dtb"
}
dump highmem-off "iommu=smmuv3,highmem=off"
dump highmem-on "iommu=smmuv3"
{
    echo "# The device tree that seL4 builds in and the Rust loader passes to the root task (external/e3-build/sel4/kernel.dtb): counts of lines naming"
    for k in smmu iommu "pcie@" msi psci; do echo "$k: $(dtc -I dtb -O dts "$E3/sel4/kernel.dtb" 2>/dev/null | grep -ci "$k")"; done
    echo "pcie node reg: $(dtc -I dtb -O dts "$E3/sel4/kernel.dtb" 2>/dev/null | awk '/pcie@/{p=1} p&&/reg = /{print; exit}' | tr -d '\t')"
} >"$R/04-kernel-dtb.txt"

run() { # label image machine-extra device-spec
    local label="$1" img="$2" extra="$3" dev="$4"
    local opts=()
    [ -n "$extra" ] && opts+=(--machine-extra "$extra")
    python3 -B boot-a5.py "${opts[@]}" --device "$dev" "${TRACE[@]}" --timeout 40 "$img" >"$R/$label.txt" 2>&1
    echo "$label exit $?"
}
LOW="$EXT/a5-step0-build-low/image.elf"
HIGH="$EXT/a5-step0-build-high/image.elf"
WIDE="edu,dma_mask=0xffffffffff"
for n in 1 2 3; do run "10-primary-low-wide-$n" "$LOW" "iommu=smmuv3,highmem=off" "$WIDE"; done
run "11-low-default-mask" "$LOW" "iommu=smmuv3,highmem=off" "edu"
run "12-high-wide" "$HIGH" "iommu=smmuv3" "$WIDE"
run "13-high-default-mask" "$HIGH" "iommu=smmuv3" "edu"
run "20-neg-no-smmu" "$LOW" "highmem=off" "$WIDE"
run "21-neg-high-probe-on-highmem-off" "$HIGH" "iommu=smmuv3,highmem=off" "$WIDE"
run "22-neg-low-probe-on-highmem-on" "$LOW" "iommu=smmuv3" "$WIDE"

{
    echo "# A5 step 0 post-run record, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 source tracked diff: $(git -C external/seL4 diff HEAD | wc -l | tr -d ' ') lines"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock | wc -l | tr -d ' ') lines"
    for f in "${SOURCES[@]}"; do echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done
} >"$R/07-post-checks.txt"
rm -f "$R"/.build-*.out
echo ALL-DONE
