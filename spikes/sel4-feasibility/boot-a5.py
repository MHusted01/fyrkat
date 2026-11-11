#!/usr/bin/env python3
"""Boot a seL4 image under QEMU with an SMMUv3 and PCI devices, and capture the serial output together with QEMU's trace events.

    boot-a5.py [--machine-extra OPTS] [--device SPEC]... [--trace PATTERN]... [--smp N] [--marker TEXT] [--timeout SECONDS] IMAGE

Like boot-image.py (which is left unchanged, because earlier evidence records its hash) but for A5 step 0: it adds machine options
(for example `iommu=smmuv3,highmem=off`), `-device` arguments and `-trace` patterns. QEMU's trace output (the `log` backend) goes to
its stderr, which is merged with the serial output, so the order of guest lines and SMMU events is the order in which they
occurred. The machine is the one of E1 to E3: `virt,secure=off,gic-version=2,virtualization=on`, Cortex-A57, 1 vCPU unless `--smp`
says otherwise, 1024 MiB, TCG.
Exit code: 0 marker seen, 1 not seen, 2 usage or launch error. The whole output is printed. Spike code only.
"""
import argparse
import os
import selectors
import shutil
import subprocess
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--machine-extra", default="", help="appended to -machine, comma separated, for example iommu=smmuv3,highmem=off")
    ap.add_argument("--device", action="append", default=[], help="a -device argument, for example edu or edu,dma_mask=0xffffffff")
    ap.add_argument("--trace", action="append", default=[], help="a -trace pattern, for example smmuv3_*")
    ap.add_argument("--smp", type=int, default=1, help="number of vCPUs (default 1)")
    ap.add_argument("--marker", default="A5P_DONE")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    qemu = shutil.which("qemu-system-aarch64")
    if qemu is None or not os.path.isfile(args.image):
        print("error: qemu-system-aarch64 or the image is missing", file=sys.stderr)
        return 2
    machine = "virt,secure=off,gic-version=2,virtualization=on" + (f",{args.machine_extra}" if args.machine_extra else "")
    cmd = [qemu, "-machine", machine, "-accel", "tcg", "-cpu", "cortex-a57", "-smp", str(args.smp), "-m", "size=1024M",
           "-nographic", "-monitor", "none", "-serial", "stdio", "-kernel", args.image]
    for dev in args.device:
        cmd += ["-device", dev]
    for pattern in args.trace:
        cmd += ["-trace", pattern]
    print("+", " ".join(cmd), flush=True)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as err:
        print(f"error: cannot start QEMU: {err}", file=sys.stderr)
        return 2

    out = b""
    seen = False
    sel = selectors.DefaultSelector()
    assert proc.stdout is not None
    sel.register(proc.stdout, selectors.EVENT_READ)
    start = time.monotonic()
    marker = args.marker.encode()
    eof = False
    while time.monotonic() - start < args.timeout and not seen and not eof:
        if proc.poll() is not None:
            out += proc.stdout.read() or b""
            break
        for _key, _ in sel.select(timeout=0.2):
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                eof = True
                break
            out += chunk
        seen = marker in out
    if seen:  # the marker is printed last; give QEMU a moment to flush the lines that follow
        time.sleep(0.3)
        for _key, _ in sel.select(timeout=0.2):
            out += os.read(proc.stdout.fileno(), 65536)
    elapsed = time.monotonic() - start
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.stdout.write(out.decode("utf-8", errors="replace"))
    print(f"\n[boot-a5] marker {args.marker!r} {'SEEN' if seen else 'NOT seen'} after {elapsed:.2f}s (machine={machine})")
    return 0 if seen else 1


if __name__ == "__main__":
    sys.exit(main())
