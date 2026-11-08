#!/usr/bin/env bash
# A3: configure and build the sel4test suite for qemu-arm-virt, AArch64, without hypervisor support,
# with GICv3 (HVF cannot emulate GICv2), for 1 or 4 nodes. Needs fetch-sel4test.sh and build.sh's
# prerequisites (the hash-pinned .venv, aarch64-elf-gcc). Installs nothing.
#
#   spikes/sel4-feasibility/build-sel4test.sh 1|4
set -euo pipefail

nodes="${1:?usage: build-sel4test.sh 1|4}"
case "$nodes" in 1 | 4) ;; *) echo "error: nodes must be 1 or 4" >&2; exit 2 ;; esac

W="$(cd "$(dirname "$0")" && pwd)"
D="$W/external/sel4test-workspace"
B="$D/build-${nodes}cpu"

export RUSTUP_TOOLCHAIN=nightly-2026-08-21
export RUSTUP_AUTO_INSTALL=0
# protoc 3.20.3 (build-protoc.sh) must come first: it matches the venv's protobuf 3.20.3.
# tools/cpio is a GNU-cpio stand-in: macOS cpio lacks --append, --reproducible and --owner.
export PATH="$W/tools:$W/external/protoc-build:$W/.venv/bin:$PATH"

rm -rf "$B"
mkdir -p "$B"
cd "$B"
../init-build.sh \
    -DPLATFORM=qemu-arm-virt \
    -DAARCH64=1 \
    -DSIMULATION=TRUE \
    -DQEMU_GIC_VERSION=3 \
    -DNUM_NODES="$nodes" \
    -DCROSS_COMPILER_PREFIX=aarch64-elf-
ninja
ls -l images/
