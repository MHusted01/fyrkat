#!/usr/bin/env bash
# Route I (Stage B preparation): raw evidence in results-raw/RouteI (gitignored) that the plan's K1 and K2 boot through seL4's own
# elfloader with a Rust root task under QEMU TCG, plus the negative controls that show why each choice is needed. Then:
#
#   spikes/sel4-feasibility/run-routei-evidence.sh
#   python3 spikes/sel4-feasibility/sanitize-run.py RouteI
#   python3 spikes/sel4-feasibility/verify-evidence.py
#
# K1: the kernel of build-a2a.sh with the elfloader and the A1 rerun's root task (the artifact whose hash the A1 rerun records).
# K2: K1 with 4 nodes; its root task is rebuilt against K2's own kernel prefix; its device tree is dumped from QEMU with
# virtualization=on so that the PSCI conduit is smc (the elfloader rejects hvc); it runs on `-machine virt,virtualization=on`.
# Negative controls: K2 with seL4's default device tree (hvc); K2 with the smc tree on a machine without virtualization;
# K2 with the K1-built root task. Boots nothing but these images; installs nothing. Spike code.
set -uo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
EXT="$(cd external && pwd -P)"
R=results-raw/RouteI
SOURCES=(build-routei.sh run-routei-evidence.sh boot-image.py a2a-compare.py)
K1_ROOT="$EXT/a1-rerun-build1/s1-root-task.elf"
K2P="$EXT/routei-k2-prefix"
export PATH="$W/.venv/bin:$PATH"

rm -rf "$R" "$EXT/routei-build" "$K2P"
mkdir -p "$R"
{
    echo "# Route I preflight record, $(date -u +%Y-%m-%dT%H:%M:%SZ). Written before the builds."
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "branch: $(git branch --show-current)"
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "qemu: $(qemu-system-aarch64 --version | head -1)"
    echo "Cargo.toml and Cargo.lock sha256: $(shasum -a 256 Cargo.toml Cargo.lock | cut -d' ' -f1 | tr '\n' ' ')"
    echo "K1 root task sha256: $(shasum -a 256 "$K1_ROOT" | cut -d' ' -f1)"
    for f in "${SOURCES[@]}"; do [ "$f" = run-routei-evidence.sh ] || echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done
} >"$R/00-preflight.txt"

# K2's kernel prefix (headers and configuration for the Rust crates) and a root task built against it.
{
    cmake -DCROSS_COMPILER_PREFIX=aarch64-elf- -DCMAKE_INSTALL_PREFIX="$K2P/install" -DKernelPlatform=qemu-arm-virt \
        -DKernelArmHypervisorSupport=OFF -DKernelVerificationBuild=OFF -DARM_CPU=cortex-a57 -DKernelMaxNumNodes=4 \
        -G Ninja -S "$EXT/seL4" -B "$K2P/sel4" &&
        ninja -C "$K2P/sel4" all && ninja -C "$K2P/sel4" install
} >"$R/.k2-prefix.log" 2>&1 || { echo "K2 prefix build failed"; tail -5 "$R/.k2-prefix.log"; exit 1; }
(
    export RUSTUP_TOOLCHAIN=nightly-2026-08-21 RUSTUP_AUTO_INSTALL=0 CC_aarch64_unknown_none=aarch64-elf-gcc \
        AR_aarch64_unknown_none=aarch64-elf-ar RANLIB_aarch64_unknown_none=aarch64-elf-ranlib
    export SEL4_PREFIX="$K2P/install" RUST_TARGET_PATH="$W/external/rust-sel4/support/targets" RUSTFLAGS="-Zunstable-options"
    cargo build --locked --release -p s1-root-task --target aarch64-sel4 -Z unstable-options \
        -Z build-std=core,alloc,compiler_builtins -Z build-std-features=compiler-builtins-mem \
        --target-dir "$K2P/root-task/target" --artifact-dir "$K2P/root-task"
) >"$R/.k2-root.log" 2>&1 || { echo "K2 root task build failed"; tail -5 "$R/.k2-root.log"; exit 1; }
K2_ROOT="$K2P/root-task/s1-root-task.elf"

# The device tree with the smc conduit, from the QEMU that seL4's CMake would use.
qemu-system-aarch64 -machine virt,secure=off,virtualization=on,gic-version=2,dumpdtb="$K2P/k2-smc.dtb" -cpu cortex-a57 -smp 4 -m 1024 -nographic >/dev/null 2>&1
dtc -I dtb -O dts "$K2P/k2-smc.dtb" 2>/dev/null | grep -v "rng-seed\|kaslr-seed" >"$R/05-k2-smc.dts"

./build-routei.sh K1 "$K1_ROOT" >"$R/.b-K1.out" 2>&1 || exit 1
./build-routei.sh K2 "$K2_ROOT" "$K2P/k2-smc.dtb" >"$R/.b-K2.out" 2>&1 || exit 1
./build-routei.sh K2H "$K2_ROOT" >"$R/.b-K2H.out" 2>&1 || exit 1
ROUTEI_NAME=K2M ./build-routei.sh K2 "$K1_ROOT" "$K2P/k2-smc.dtb" >"$R/.b-K2M.out" 2>&1 || exit 1   # control: K2 with the K1-built root task
cp "$EXT/routei-build/K1/tools.txt" "$R/01-tools.txt"
{ for id in K1 K2 K2H K2M; do echo "## $id"; cat "$EXT/routei-build/$id/command.txt"; done; } >"$R/02-commands.txt"
for id in K1 K2 K2H K2M; do
    { echo "## $id: build exit $(cat "$EXT/routei-build/$id/BUILD_EXIT")"; cat "$EXT/routei-build/$id/build.log"; } >"$R/03-build-$id.txt"
done
IMG() { echo "$EXT/routei-build/$1/build/images/rust-root-task-image-arm-qemu-arm-virt"; }

{
    echo "# Hashes. root tasks, images, the kernel configuration of each image, and the A2a kernel configuration it must equal."
    echo "k1-root-task $(shasum -a 256 "$K1_ROOT" | cut -d' ' -f1)"
    echo "k2-root-task $(shasum -a 256 "$K2_ROOT" | cut -d' ' -f1)"
    for id in K1 K2 K2H K2M; do
        echo "image-$id $(shasum -a 256 "$(IMG $id)" | cut -d' ' -f1)"
        echo "gen_config-$id $(shasum -a 256 "$EXT/routei-build/$id/build/kernel/gen_config/kernel/gen_config.json" | cut -d' ' -f1)"
    done
    echo "a2a-gen_config-K1 $(shasum -a 256 results/A2a/gen_config-K1.json | cut -d' ' -f1)"
    echo "a2a-gen_config-K2 $(shasum -a 256 results/A2a/gen_config-K2.json | cut -d' ' -f1)"
} >"$R/04-sums.txt"

boot() { # label image extra-args...
    local label="$1" img="$2"; shift 2
    python3 -B boot-image.py "$@" --gic 2 --marker TEST_PASS "$img" >"$R/$label.txt" 2>&1
    echo "$label exit $?"
}
for n in 1 2 3; do
    boot "10-boot-K1-$n" "$(IMG K1)" --smp 1 --timeout 30
    boot "11-boot-K2-$n" "$(IMG K2)" --smp 4 --virt --timeout 30
done
boot "20-neg-K2-default-dtb" "$(IMG K2H)" --smp 4 --virt --timeout 20
boot "21-neg-K2-smc-dtb-no-virtualization" "$(IMG K2)" --smp 4 --timeout 20
boot "22-neg-K2-with-k1-root-task" "$(IMG K2M)" --smp 4 --virt --timeout 20
rm -f "$R"/.b-*.out "$R"/.k2-*.log

{
    echo "# Route I post-run record, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 source tracked diff: $(git -C external/seL4 diff HEAD | wc -l | tr -d ' ') lines"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock | wc -l | tr -d ' ') lines"
    for f in "${SOURCES[@]}"; do [ "$f" = run-routei-evidence.sh ] || echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done
} >"$R/07-post-checks.txt"
echo ALL-DONE
