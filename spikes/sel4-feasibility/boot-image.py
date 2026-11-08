#!/usr/bin/env python3
"""Boot a seL4 image under QEMU and report whether a success marker appears on the serial console.

    boot-image.py [--accel tcg|hvf] [--cpu NAME] [--smp N] [--gic N] [--virt] [--mem MIB]
                  [--marker TEXT] [--timeout SECONDS] IMAGE

The QEMU machine arguments must match the ones seL4's CMake used to dump the device tree
(`virt,secure=off,gic-version=N`, 1024 MiB). Exit code: 0 marker seen, 1 marker not seen before the
timeout or QEMU exit, 2 usage or launch error. The whole serial output is printed. Spike code only.
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
    ap.add_argument("--accel", choices=["tcg", "hvf"], default="tcg")
    ap.add_argument("--cpu", default=None, help="default: cortex-a57 for tcg, host for hvf")
    ap.add_argument("--smp", type=int, default=1)
    ap.add_argument("--gic", type=int, default=2)
    ap.add_argument("--virt", action="store_true", help="virtualization=on: the guest starts at EL2")
    ap.add_argument("--mem", type=int, default=1024)
    ap.add_argument("--marker", default="TEST_PASS")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    qemu = shutil.which("qemu-system-aarch64")
    if qemu is None or not os.path.isfile(args.image):
        print("error: qemu-system-aarch64 or the image is missing", file=sys.stderr)
        return 2
    cpu = args.cpu or ("host" if args.accel == "hvf" else "cortex-a57")
    cmd = [
        qemu,
        "-machine", f"virt,secure=off,gic-version={args.gic}" + (",virtualization=on" if args.virt else ""),
        "-accel", args.accel,
        "-cpu", cpu,
        "-smp", str(args.smp),
        "-m", f"size={args.mem}M",
        "-nographic", "-monitor", "none", "-serial", "stdio",
        "-kernel", args.image,
    ]
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
    deadline = time.monotonic() + args.timeout
    start = time.monotonic()
    marker = args.marker.encode()
    while time.monotonic() < deadline and not seen:
        if proc.poll() is not None:
            out += proc.stdout.read() or b""
            break
        for _key, _ in sel.select(timeout=0.2):
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                break
            out += chunk
        seen = marker in out
    elapsed = time.monotonic() - start
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.stdout.write(out.decode("utf-8", errors="replace"))
    print(f"\n[boot-image] marker {args.marker!r} {'SEEN' if seen else 'NOT seen'} after {elapsed:.2f}s"
          f" (accel={args.accel} cpu={cpu} smp={args.smp} gic={args.gic} virt={args.virt})")
    return 0 if seen else 1


if __name__ == "__main__":
    sys.exit(main())
