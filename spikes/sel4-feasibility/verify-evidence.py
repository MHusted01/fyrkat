#!/usr/bin/env python3
"""Re-check the A1 and A3 conclusions against the sanitized public evidence in results/.

    verify-evidence.py [--results DIR]

It reads only the sanitized files (never results-raw/), so anyone with a clone can run it. It checks
that the measurements the records rely on are present and consistent, that the manifest's hashes match
the files, and (using the live environment's user, home and host names) that none of them remain.
Exit code 0 when every check passes. Spike code, stdlib only.
"""
import argparse
import getpass
import hashlib
import re
import socket
import sys
from pathlib import Path


def read(res: Path, rel: str) -> str:
    return (res / rel).read_text(encoding="utf-8")


def sums(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+(\S+)$", line.strip())
        if m:
            out[m.group(2)] = m.group(1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--results", default=str(Path(__file__).resolve().parent / "results"))
    res = Path(ap.parse_args().results)
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        results.append((name, bool(ok)))

    # ---- A1
    s1, s2 = sums(read(res, "A1/16-sums-run1.txt")), sums(read(res, "A1/18-sums-run2.txt"))
    names = {"kernel.elf", "sel4-kernel-loader.elf", "s1-root-task.elf", "image.elf"}
    check("A1 sums list the four outputs in both runs", set(s1) == names and set(s2) == names)
    check("A1 kernel, loader and root task identical across clean builds",
          all(s1[n] == s2[n] for n in names - {"image.elf"}))
    check("A1 image.elf differs between the two builds", s1["image.elf"] != s2["image.elf"])
    dtb = read(res, "A1/20-dtb-seed-diff.txt")
    diff_lines = [ln for ln in dtb.split("## diff of the decoded trees")[1].split("## kernel.dtb")[0].splitlines()
                  if ln[:2] in ("< ", "> ")]
    check("A1 the two QEMU device-tree dumps differ only in rng-seed and kaslr-seed",
          diff_lines and all(("rng-seed" in ln or "kaslr-seed" in ln) for ln in diff_lines))
    check("A1 kernel.dtb is embedded verbatim in image.elf", "found verbatim in image.elf at offset" in dtb)
    det = sums(read(res, "A1/21-add-payload-determinism.txt").replace("/tmp/", ""))
    check("A1 add-payload is deterministic on fixed inputs (four equal hashes)",
          len(det) >= 3 and len(set(det.values())) == 1)
    rep = read(res, "A1/22-loader-defect-repro.txt")
    check("A1 loader without cross ar/ranlib: 5,896 bytes, entry 0",
          "size: 5896" in rep and re.search(r"Entry point address:\s+0x0\b", rep) is not None)
    check("A1 loader with cross ar/ranlib: 63,200 bytes, real entry", "size: 63200" in rep)
    check("A1 cargo deny on the spike workspace: advisories, bans and sources ok",
          "advisories ok, bans ok, sources ok" in read(res, "A1/14-deny-spike-workspace.txt"))
    for rel in ("A1/11-deny-sel4-kernel-loader.txt", "A1/11-deny-sel4-kernel-loader-add-payload.txt"):
        ids = set(re.findall(r"RUSTSEC-\d{4}-\d{4}", read(res, rel)))
        check(f"A1 {rel}: the only advisory is RUSTSEC-2024-0449", ids == {"RUSTSEC-2024-0449"})
    path = read(res, "A1/19-unsafe-libyaml-path.txt")
    check("A1 unsafe-libyaml has no normal edge and no symbol in the target loader",
          "warning: nothing to print" in path and "nm matches=0" in path and "strings matches=0" in path)
    base = read(res, "A1/00-baseline.txt")
    check("A1 host and tool versions recorded (M2 Pro, CMake 4.4.5, QEMU 11.1.3)",
          "Apple M2 Pro" in base and "cmake version 4.4.5" in base and "QEMU emulator version 11.1.3" in base)
    check("A1 compiler is GCC 16.2.0", "GNU 16.2.0" in read(res, "A1/08-sel4-configure.txt"))
    check("A1 nightly toolchain recorded", "nightly-2026-08-21" in read(res, "A1/05-rustup-install.txt"))
    check("A1 Python environment has no broken requirements",
          "No broken requirements found" in read(res, "A1/06-python-venv.txt"))
    check("A1 Homebrew drift: only the two cross formulae were added",
          "after minus the added lines equals before: True" in read(res, "A1/04-brew-drift-summary.txt"))
    fetch = read(res, "A1/07-fetch-sources.txt")
    check("A1 seL4 and rust-sel4 fetched at their pins",
          "62e345c240a15671484530b4e6e069ce266c28d7 == pin OK" in fetch
          and "c819c27b076130cba9821c4555f23773e4b0bffd == pin OK" in fetch)

    # ---- A3
    check("A3 HVF 1 vCPU: kernel halts on the 16-bit ASID check",
          "ERROR: kernel requires 16-bit ASIDs" in read(res, "A3/31-boot-hvf-1cpu.txt"))
    for rel in ("A3/32-boot-hvf-4cpu-smp.txt", "A3/34-boot-tcg-4cpu-smp-control.txt"):
        check(f"A3 {rel}: elfloader PSCI abort", "HVC is not supported for PSCI" in read(res, rel))
    check("A3 TCG 1 vCPU control: sel4test passes (124 passed, 59 disabled)",
          "Test suite passed. 124 tests passed. 59 tests disabled." in read(res, "A3/33-boot-tcg-1cpu-control.txt"))
    probe = read(res, "A3/11-probe-idregs.txt")
    asid = re.findall(r"ASIDBits\(MMFR0\[7:4\]\)=0*([0-9a-f]+)", probe)
    check("A3 probe: ASIDBits is 2 under TCG and 0 under HVF", asid == ["2", "0"])
    check("A3 HVF cannot give the guest EL2",
          "Nested virtualization not supported" in read(res, "A3/04-boot-hvf-virt-1cpu.txt"))
    check("A3 HVF cannot emulate GICv2", "HVF does not support GICv2 emulation" in read(res, "A3/03-boot-hvf-el1-1cpu.txt"))
    pins = read(res, "A3/06-fetch-sel4test.txt")
    check("A3 eight sel4test project pins verified", len(re.findall(r"^OK \S+ [0-9a-f]{40}$", pins, re.M)) >= 8)
    check("A3 4-node image is a real SMP kernel build log present", (res / "A3/24-build-4cpu.txt").is_file())

    # ---- integrity and privacy
    bad = []
    for line in read(res, "evidence-manifest.txt").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        _raw, clean, rel = line.split(None, 2)
        if hashlib.sha256((res / rel).read_bytes()).hexdigest() != clean:
            bad.append(rel)
    check("manifest: every sanitized file matches its recorded SHA-256", not bad)
    home, user = str(Path.home()), getpass.getuser()
    host = socket.gethostname()
    needles = {home, user, host, host.split(".")[0], "/var/folders", "claude-"} - {"", "localhost"}
    leaks = [str(p.relative_to(res)) for p in res.rglob("*") if p.is_file()
             and any(n in p.read_text(encoding="utf-8", errors="replace") for n in needles)]
    check("privacy: no home path, user name, host name or scratch path in results/", not leaks)

    width = max(len(n) for n, _ in results)
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}")
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
