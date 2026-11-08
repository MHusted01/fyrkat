#!/usr/bin/env bash
# A3: build probes/idregs.c with the cross compiler and run it under QEMU TCG (Cortex-A57) and HVF
# (-cpu host), printing the ID registers each guest sees. Installs nothing.
set -euo pipefail
W="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$W/build"
aarch64-elf-gcc -O1 -ffreestanding -nostdlib -mgeneral-regs-only \
    -Wl,-Ttext=0x40000000 -Wl,--build-id=none \
    -o "$W/build/idregs.elf" "$W/probes/idregs.c"
run() { # accel cpu
    echo "== accel=$1 cpu=$2"
    python3 -I "$W/boot-image.py" --accel "$1" --cpu "$2" --gic 3 --smp 1 \
        --marker PROBE-END --timeout 15 "$W/build/idregs.elf" | grep -E '^(CurrentEL|MIDR|ID_AA64|ASIDBits|PROBE|\[boot-image\])'
}
run tcg cortex-a57
run hvf host
