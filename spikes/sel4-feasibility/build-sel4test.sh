#!/usr/bin/env bash
# A3: configure and build the sel4test suite for qemu-arm-virt, AArch64, without hypervisor support,
# with GICv3 (HVF cannot emulate GICv2), for 1 or 4 nodes (a real SMP kernel for 4: sel4test ignores NUM_NODES unless SMP is on). Needs fetch-sel4test.sh and build.sh's
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
# seL4 cmake-tool needs GNU cpio (--append, --reproducible, --owner). macOS cpio lacks them. GNU cpio
# 2.15 is already installed as the keg-only Homebrew formula "cpio", so it is only put on PATH here.
export PATH="/opt/homebrew/opt/cpio/bin:$W/external/protoc-build:$W/.venv/bin:$PATH"

smp=FALSE
if [ "$nodes" -gt 1 ]; then smp=TRUE; fi
rm -rf "$B"
mkdir -p "$B"
cd "$B"
../init-build.sh \
    -DPLATFORM=qemu-arm-virt \
    -DAARCH64=1 \
    -DSIMULATION=TRUE \
    -DQEMU_GIC_VERSION=3 \
    -DNUM_NODES="$nodes" \
    -DSMP="$smp" \
    -DCROSS_COMPILER_PREFIX=aarch64-elf-
ninja
ls -l images/
