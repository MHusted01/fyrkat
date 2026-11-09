#!/usr/bin/env bash
# E3: produce the raw evidence in results-raw/E3 (gitignored): preflight, clean build, kernel config record, three boots
# of the final image, one boot of each mutant, post-run record. Then sanitize and check:
#
#   spikes/sel4-feasibility/run-e3-evidence.sh
#   python3 spikes/sel4-feasibility/sanitize-run.py E3
#   python3 spikes/sel4-feasibility/verify-evidence.py
#
# It removes results-raw/E3 and external/e3-build first, so move anything to keep. It builds with build-e3.sh, boots
# with boot-image.py, and installs nothing. Spike code (see the plan's E3 entry).
set -uo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
R=results-raw/E3
B=external/e3-build
MUTANTS=(noop-revoke revoke-wrong-ancestor noop-revoke-blind-probes revoke-too-much revoke-task-1-only serve-refused)
# The files the evidence depends on: recorded with their hashes before the build and after the last boot, and compared
# by the verifier with the files in the repository.
SOURCES=(
    crates/e2-root-task/src/bin/e3_root_task.rs crates/e2-root-task/src/e3_spawn.rs
    crates/e2-task/src/bin/e3_task.rs crates/e2-task/src/e3_abi.rs crates/e2-task/src/lib.rs
    build-e3.sh build-e2.sh boot-image.py
)
# The E2 files that E3 must not have changed (lib.rs gained one line, `pub mod e3_abi;`, and is not in this list).
E2_SOURCES=(
    crates/e2-task/src/abi.rs crates/e2-task/src/runtime.rs crates/e2-task/src/bin/client.rs
    crates/e2-task/src/bin/server.rs crates/e2-root-task/src/main.rs crates/e2-root-task/src/child_vspace.rs
    crates/e2-root-task/src/object_allocator.rs
)

record_sources() {
    for f in "${SOURCES[@]}"; do
        echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"
    done
}

rm -rf "$R"
mkdir -p "$R"

{
    echo "# E3 preflight record, $(date -u +%Y-%m-%dT%H:%M:%SZ). Written before the evidence build."
    echo "repo HEAD: $(git rev-parse HEAD)  (origin/main $(git rev-parse origin/main))"
    echo "branch: $(git branch --show-current)"
    echo "git status --short:"
    git status --short -- . | sed 's/^/ /'
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD)"
    echo "rust-sel4 HEAD: $(git -C external/rust-sel4 rev-parse HEAD)"
    echo "uname -m: $(uname -m)"
    echo "qemu: $(qemu-system-aarch64 --version | head -1)"
    echo "gcc: $(aarch64-elf-gcc --version | head -1)"
    echo "cmake: $(cmake --version | head -1)"
    echo "ninja: $(ninja --version)"
    echo "rustc: $(RUSTUP_TOOLCHAIN=nightly-2026-08-21 rustc --version)"
    echo "Cargo.toml sha256: $(shasum -a 256 Cargo.toml | cut -d' ' -f1)"
    echo "Cargo.lock sha256: $(shasum -a 256 Cargo.lock | cut -d' ' -f1)"
    record_sources
} >"$R/00-preflight.txt"

./build-e3.sh >"$R/01-build.txt" 2>&1
echo "BUILD_EXIT=$?" >>"$R/01-build.txt"
tail -3 "$R/01-build.txt"
grep -q "BUILD_EXIT=0" "$R/01-build.txt" || exit 1

cp "$B/sel4/gen_config/kernel/gen_config.json" "$R/02-kernel-gen_config.json"
{
    echo "# E3 kernel config versus E1-H's kernel config (external/e1-build), key by key"
    echo "# Command: python3 -I - with: load both gen_config.json files, take the union of keys, print every key whose value differs."
    python3 -I - external/e1-build/sel4/gen_config/kernel/gen_config.json "$B/sel4/gen_config/kernel/gen_config.json" <<'EOF'
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
print(f"{len(a)} keys in E1-H config, {len(b)} in E3 config, {len(diff)} differ:")
for k in diff:
    print(f"  {k}: E1-H={a.get(k)!r}  E3={b.get(k)!r}")
EOF
} >"$R/05-config-diff-vs-e1.txt"

for n in 1 2 3; do
    python3 boot-image.py --virt --marker E3_PASS --timeout 30 "$B/image.elf" >"$R/10-boot-$n.txt"
    echo "boot $n exit $?"
done

{
    echo "# E3 mutation checks: can the test fail? Run $(date -u +%Y-%m-%dT%H:%M:%SZ). Each mutant was built by ./build-e3.sh --mutant NAME, which reuses the evidence build's kernel, loader and task binary (byte for byte)"
    echo "# and rebuilds only the root task (with E3_MUTANT set at compile time) and the image. No source file was edited."
    echo "# M1 noop-revoke: no revoke. M2 revoke-wrong-ancestor: Revoke on Q, not P. M3 noop-revoke-blind-probes: no revoke, and two of the root task's probes after it are left out."
    echo "# M4 revoke-too-much: Revoke on P, then on Q. M5 revoke-task-1-only: task 1's slots 1 and 2 are deleted, no revoke. M6 serve-refused: no revoke, probes left out, and the root task answers the call."
    echo "# Expected: every check before the revoke passes; each mutant stops at the check it is meant to reach; E3_PASS is never printed."
} >"$R/06-mutation-checks.txt"
i=0
for name in "${MUTANTS[@]}"; do
    i=$((i + 1))
    ./build-e3.sh --mutant "$name" >"$R/.mutant-$i-build.log" 2>&1 || {
        echo "mutant $name build failed"
        tail -5 "$R/.mutant-$i-build.log"
        exit 1
    }
    M="external/e3-mutant-$name"
    {
        echo
        echo "## M$i $name"
        for f in kernel.elf sel4-kernel-loader.elf e3_task.elf e3_root_task.elf image.elf; do
            echo "# $f sha256: $(shasum -a 256 "$M/$f" | cut -d' ' -f1)"
        done
        python3 boot-image.py --virt --marker E3_PASS --timeout 15 "$M/image.elf"
    } >>"$R/06-mutation-checks.txt"
    echo "mutant $name: done"
done
mkdir -p external/e3-mutant-logs && mv "$R"/.mutant-*-build.log external/e3-mutant-logs/

{
    echo "# E3 post-run checks, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "git status --short (repo):"
    git status --short -- . | sed 's/^/ /'
    echo "tracked files changed vs HEAD: $(git diff HEAD --name-only -- . | wc -l | tr -d ' ') ($(git diff HEAD --name-only -- . | tr '\n' ' '))"
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "rust-sel4 HEAD: $(git -C external/rust-sel4 rev-parse HEAD); dirty files: $(git -C external/rust-sel4 status --porcelain | wc -l | tr -d ' ')"
    echo "Cargo.lock sha256: $(shasum -a 256 Cargo.lock | cut -d' ' -f1)"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock | wc -l | tr -d ' ') lines"
    echo "crates/root-task tracked diff vs HEAD: $(git diff HEAD -- crates/root-task | wc -l | tr -d ' ') lines"
    echo "crates/*/Cargo.toml tracked diff vs HEAD: $(git diff HEAD -- 'crates/*/Cargo.toml' | wc -l | tr -d ' ') lines"
    echo "E2 sources (${E2_SOURCES[*]}) tracked diff vs HEAD: $(git diff HEAD -- "${E2_SOURCES[@]}" | wc -l | tr -d ' ') lines"
    record_sources
    echo "image used for the boots: $B/image.elf $(shasum -a 256 "$B/image.elf" | cut -d' ' -f1)"
    for f in kernel.elf sel4-kernel-loader.elf e3_task.elf e3_root_task.elf image.elf; do
        echo "e3 $(shasum -a 256 "$B/$f" | cut -d' ' -f1)  $f"
    done
    echo "E1 hashes for comparison (results/E1.md): kernel 1fee1dd675a578b04153e8290fb58021d911656967f0da27d35ca12c885ca9d0, loader 8408ab23e7db94b549f49f609da260d26dbcab6d7e9d5a2f4d8acc12c9e88159"
} >"$R/04-post-checks.txt"
echo ALL-DONE
