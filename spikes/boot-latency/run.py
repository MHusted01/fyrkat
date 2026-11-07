#!/usr/bin/env python3
"""Measure QEMU boot latency and workload throughput for the Fyrkat boot spike.

Results describe the development loop on the host that ran this script. They say
nothing about the relative merit of the CPU architectures themselves.
"""
import json, os, pathlib, platform, shutil, statistics, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "target" / "spike"
FIRMWARE = pathlib.Path(subprocess.check_output(["brew", "--prefix", "qemu"], text=True).strip()) / "share/qemu"
WORKLOADS = {"alu": 2_000_000_000, "mem": 200_000_000, "trap": 20_000_000}
BOOT_RUNS = int(os.environ.get("SPIKE_BOOT_RUNS", "9"))
WORK_RUNS = int(os.environ.get("SPIKE_WORK_RUNS", "3"))
TIMEOUT = 280
COMMON = ["-m", "512M", "-nographic", "-monitor", "none", "-serial", "stdio", "-no-reboot"]
# Without this, EDK2 waits out a fixed ~5 s boot-menu timeout.
NO_MENU = ["-boot", "menu=on,splash-time=0"]


def build(target, binary, kind, spin):
    env = {**os.environ, "SPIKE_SPIN": str(spin), "SPIKE_KIND": kind}
    subprocess.run(["cargo", "clean", "--release", "--quiet", "--target", target], cwd=ROOT, check=False)
    subprocess.run(["cargo", "build", "--release", "--quiet", "--bin", binary, "--target", target],
                   cwd=ROOT, env=env, check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if binary == "bare":
        path = OUT / f"bare-{spin}"
        shutil.copy(ROOT / "target" / target / "release" / "bare", path)
        return path
    name = "BOOTAA64.EFI" if target.startswith("aarch64") else "BOOTX64.EFI"
    esp = OUT / f"esp-{target}-{kind}-{spin}"
    (esp / "EFI/BOOT").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "target" / target / "release" / "uefi.efi", esp / "EFI/BOOT" / name)
    return esp


def aarch64(accel, extra):
    cpu = ["-cpu", "host"] if accel == "hvf" else ["-cpu", "cortex-a76"]
    return ["qemu-system-aarch64", "-machine", "virt", "-accel", accel, *cpu, *COMMON, *extra]


def aarch64_uefi(accel, esp):
    return aarch64(accel, ["-bios", str(FIRMWARE / "edk2-aarch64-code.fd"),
                           "-drive", f"format=raw,file=fat:rw:{esp}", *NO_MENU])


def x86_uefi(esp):
    return ["qemu-system-x86_64", "-machine", "q35", "-accel", "tcg", *COMMON,
            "-drive", f"if=pflash,format=raw,readonly=on,file={FIRMWARE / 'edk2-x86_64-code.fd'}",
            "-drive", f"format=raw,file=fat:rw:{esp}", *NO_MENU]


def timed(command):
    start = time.perf_counter()
    done = subprocess.run(command, capture_output=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    elapsed = time.perf_counter() - start
    output = done.stdout.decode(errors="replace")
    if done.returncode != 0 or "FYRKAT-SPIKE done" not in output:
        raise RuntimeError(f"rc={done.returncode} out={output[-200:]!r} err={done.stderr.decode(errors='replace')[-200:]!r}")
    return elapsed


def summary(samples):
    return {"median_s": round(statistics.median(samples), 3), "min_s": round(min(samples), 3),
            "max_s": round(max(samples), 3), "n": len(samples)}


def main():
    bare = build("aarch64-unknown-none-softfloat", "bare", "alu", 0)
    a64 = {(k, s): build("aarch64-unknown-uefi", "uefi", k, s) for k, n in WORKLOADS.items() for s in (0, n)}
    x64 = {(k, s): build("x86_64-unknown-uefi", "uefi", k, s) for k, n in WORKLOADS.items() for s in (0, n)}
    configs = {
        "aarch64 UEFI, HVF": lambda k, s: aarch64_uefi("hvf", a64[(k, s)]),
        "aarch64 UEFI, TCG": lambda k, s: aarch64_uefi("tcg", a64[(k, s)]),
        "x86-64 UEFI, TCG": lambda k, s: x86_uefi(x64[(k, s)]),
    }
    rows = []
    for accel in ("hvf", "tcg"):
        row = {"case": f"aarch64 direct, {accel.upper()}",
               "boot": summary([timed(aarch64(accel, ["-kernel", str(bare)])) for _ in range(BOOT_RUNS)])}
        print(json.dumps(row), flush=True)
        rows.append(row)
    for name, make in configs.items():
        row = {"case": name}
        try:
            row["boot"] = summary([timed(make("alu", 0)) for _ in range(BOOT_RUNS)])
            for kind, count in WORKLOADS.items():
                idle = statistics.median([timed(make(kind, 0)) for _ in range(WORK_RUNS)])
                busy = [timed(make(kind, count)) - idle for _ in range(WORK_RUNS)]
                row[kind] = {**summary(busy), "ns_per_iter": round(statistics.median(busy) / count * 1e9, 2)}
        except (RuntimeError, subprocess.TimeoutExpired) as error:
            row["error"] = str(error)[:300]
        print(json.dumps(row), flush=True)
        rows.append(row)
    meta = {"host": platform.platform(), "cpu": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
            "qemu": subprocess.check_output(["qemu-system-aarch64", "--version"], text=True).splitlines()[0],
            "rustc": subprocess.check_output(["rustc", "-V"], text=True, cwd=ROOT).strip(),
            "workloads": WORKLOADS, "boot_runs": BOOT_RUNS, "work_runs": WORK_RUNS,
            "date": time.strftime("%Y-%m-%d")}
    (ROOT / "results.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    sys.exit(main())
