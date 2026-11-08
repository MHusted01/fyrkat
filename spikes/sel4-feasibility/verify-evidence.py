#!/usr/bin/env python3
"""Re-check the A1 and A3 conclusions against the sanitized public evidence in results/.

    verify-evidence.py [--results DIR] [--lock FILE]

It reads the sanitized files (never results-raw/) and the spike's Cargo.lock, so anyone with a clone can run it. It checks
that the measurements the records rely on are present and consistent, that the manifest's hashes match
the files, and that no home path remains. The privacy check looks for any home-directory path under the macOS or
Linux users root, an encoded scratch-directory name, and the running user's own home path and host name. It checks the
running user's name only when it has at least six characters and is not a common service name, so it cannot
prove that some other person's name is absent: the sanitizer is what removes names. Exit code 0 when every
check passes. Spike code, stdlib only.
"""
import argparse
import getpass
import hashlib
import re
import socket
import sys
import tomllib
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


def section(text: str, header: str) -> str:
    """The lines under the first `## ` header that contains HEADER, up to the next `## ` header."""
    parts = re.split(r"(?m)^(?=## )", text)
    return next((p for p in parts if p.startswith("## ") and header in p.splitlines()[0]), "")


def config(text: str) -> dict[str, str]:
    """Parse `KEY = VALUE` and `KEY:TYPE=VALUE` lines of a config evidence file."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^(CONFIG_\w+) = (.*)$", line) or re.match(r"^(\w+):\w+=(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def smp_build_ok(text: str, nodes: str, smp: bool) -> bool:
    """A sel4test build's recorded config: non-hypervisor, qemu-arm-virt, the given node count and SMP flag."""
    c = config(text)
    return (c.get("CONFIG_MAX_NUM_NODES") == nodes and c.get("KernelMaxNumNodes") == nodes
            and c.get("CONFIG_ENABLE_SMP_SUPPORT") == str(smp) and c.get("SMP") == ("TRUE" if smp else "FALSE")
            and c.get("CONFIG_ARM_HYPERVISOR_SUPPORT") == "False" and c.get("KernelArmHypervisorSupport") == "OFF"
            and c.get("CONFIG_PLAT_QEMU_ARM_VIRT") == "True" and c.get("CONFIG_KERNEL_MCS") == "False"
            and c.get("CONFIG_ARM_CORTEX_A53") == "True" and c.get("KernelArmCPU") == "cortex-a53"
            and re.search(rf"(?m)^cpu nodes: {nodes}$", text) is not None
            and set(re.findall(r'method = "(\w+)";', text)) == {"hvc"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--results", default=str(Path(__file__).resolve().parent / "results"))
    ap.add_argument("--lock", default=str(Path(__file__).resolve().parent / "Cargo.lock"))
    ns = ap.parse_args()
    res, lock_path = Path(ns.results), Path(ns.lock)
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
    entries = [int(e, 16) for e in re.findall(r"Entry point address:\s+0x([0-9a-f]+)", rep)]
    check("A1 loader with cross ar/ranlib: 63,200 bytes, real (non-zero) entry",
          "size: 63200" in rep and len(entries) == 2 and entries[0] == 0 and entries[1] != 0)
    check("A1 cargo deny on the spike workspace: advisories, bans and sources ok",
          "advisories ok, bans ok, sources ok" in read(res, "A1/14-deny-spike-workspace.txt"))
    for rel in ("A1/11-deny-sel4-kernel-loader.txt", "A1/11-deny-sel4-kernel-loader-add-payload.txt"):
        ids = set(re.findall(r"RUSTSEC-\d{4}-\d{4}", read(res, rel)))
        check(f"A1 {rel}: the only advisory is RUSTSEC-2024-0449", ids == {"RUSTSEC-2024-0449"})
    path = read(res, "A1/19-unsafe-libyaml-path.txt")
    check("A1 unsafe-libyaml: no normal edge into the target loader, no symbol in it, and the build-time path "
          "is through sel4-platform-info",
          "warning: nothing to print" in section(path, "edges: normal, package sel4-kernel-loader,")
          and "sel4-platform-info" in section(path, "edges: all, package sel4-kernel-loader,")
          and "nm matches=0" in path and "strings matches=0" in path)
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

    # ---- A1 rerun with the corrected lock file (a separate, clearly identified result)
    r_sum1, r_sum2 = sums(read(res, "A1-rerun/04-sums-rerun1.txt")), sums(read(res, "A1-rerun/06-sums-rerun2.txt"))
    check("A1 rerun: kernel, loader and root task identical across its two clean builds, image different",
          set(r_sum1) == names and set(r_sum2) == names
          and all(r_sum1[n] == r_sum2[n] for n in names - {"image.elf"}) and r_sum1["image.elf"] != r_sum2["image.elf"])
    check("A1 rerun: kernel and loader equal the original run's; the root task differs from it",
          r_sum2["kernel.elf"] == s2["kernel.elf"] and r_sum2["sel4-kernel-loader.elf"] == s2["sel4-kernel-loader.elf"]
          and r_sum2["s1-root-task.elf"] != s2["s1-root-task.elf"])
    cmp_text = read(res, "A1-rerun/07-comparison-with-original.txt")
    check("A1 rerun: the comparison used the original hashes recorded in A1/",
          f"original {s2['s1-root-task.elf'][:16]}" in cmp_text and f"original {s2['image.elf'][:16]}" in cmp_text
          and f"rerun {r_sum2['s1-root-task.elf'][:16]}" in cmp_text)
    check("A1 rerun: every byte difference is accounted for (8 address instructions; 782 image bytes; seeds only)",
          "all differences accounted for: yes" in cmp_text
          and "instruction words: 4795 and 4795; differing: 8" in cmp_text
          and ".rodata: 763, .text: 18, ELF header e_shoff: 1" in cmp_text
          and "control: add-payload on the original inputs reproduces the original image: yes" in cmp_text
          and len(re.findall(r"(?m)device-tree properties that differ: kaslr-seed, rng-seed$", cmp_text)) == 2)
    wanted = ("Compiling cc v1.10.0", "Compiling log v0.4.34", "Compiling psm v0.1.24", "Compiling pest_stack_guard v1.0.0")
    unwanted = ("cc v1.11.0", "log v0.4.35", "psm v0.1.32", "pest_stack_guard v1.0.1", "ar_archive_writer", "object v0.39.1")
    logs = [read(res, f"A1-rerun/{n}") for n in ("03-build-rerun1.txt", "05-build-rerun2.txt")]
    check("A1 rerun: both build logs compiled the approved crate versions and none of the six original ones",
          all(all(w in lg for w in wanted) and not any(u in lg for u in unwanted) for lg in logs))
    corr = read(res, "A1-rerun/02-lock-correction.txt")
    m = re.search(r"original: (\w{64})\s+corrected: (\w{64})", corr)
    actual = hashlib.sha256(lock_path.read_bytes()).hexdigest() if lock_path.is_file() else ""
    check("A1 rerun: the lock file in the repository is the corrected one recorded in the evidence",
          m is not None and m.group(2) == actual and m.group(1) != actual and m.group(1).startswith("c92d1dca"))
    pkgs: dict[str, set[str]] = {}
    if lock_path.is_file():
        for pkg in tomllib.loads(lock_path.read_text(encoding="utf-8"))["package"]:
            pkgs.setdefault(pkg["name"], set()).add(pkg["version"])
    approved = {"cc": {"1.10.0"}, "log": {"0.4.34"}, "psm": {"0.1.24"}, "pest_stack_guard": {"1.0.0"}}
    check("A1 rerun: the lock file has the four approved versions and neither ar_archive_writer nor object",
          all(pkgs.get(k) == v for k, v in approved.items()) and "ar_archive_writer" not in pkgs and "object" not in pkgs)
    pre = read(res, "A1-rerun/01-preflight.txt")
    drift = read(res, "A1/04-brew-drift-summary.txt")
    after = re.search(r"'after' list:\s+([0-9a-f]{64})", drift)
    check("A1 rerun: the Homebrew inventory hash at the rerun equals A1's recorded after-state",
          after is not None and after.group(1) in pre and "386 formulae" in pre)

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
    cfg1, cfg4 = read(res, "A3/41-config-1cpu.txt"), read(res, "A3/42-config-4cpu.txt")
    check("A3 1-vCPU image: single-node, non-SMP, non-hypervisor qemu-arm-virt kernel, one cpu node",
          smp_build_ok(cfg1, "1", False))
    check("A3 4-vCPU image: a real 4-node SMP, non-hypervisor kernel with four cpu nodes",
          smp_build_ok(cfg4, "4", True))
    check("A3 the device trees name hvc as the only PSCI conduit, which the elfloader rejects",
          all(set(re.findall(r'method = "(\w+)";', t)) == {"hvc"} for t in (cfg1, cfg4)))

    # ---- integrity and privacy
    listed: set[str] = set()
    bad = []
    for line in read(res, "evidence-manifest.txt").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        _raw, clean, rel = line.split(None, 2)
        listed.add(rel)
        if hashlib.sha256((res / rel).read_bytes()).hexdigest() != clean:
            bad.append(rel)
    check("manifest: every sanitized file matches its recorded SHA-256", not bad)
    evidence = {p.relative_to(res).as_posix() for sub in ("A1", "A1-rerun", "A3") for p in (res / sub).rglob("*")
                if p.is_file() and p.as_posix() != (res / "A3/shim-era/README.md").as_posix()}
    check("manifest: it lists exactly the evidence files under A1/, A1-rerun/ and A3/ (one README note aside)",
          listed == evidence)
    texts = {p: p.read_text(encoding="utf-8", errors="replace") for p in res.rglob("*") if p.is_file()}
    home, user, host = str(Path.home()), getpass.getuser(), socket.gethostname()
    common = {"runner", "ubuntu", "github", "docker", "vagrant", "nobody", "daemon", "root"}
    plain = {n for n in (host, host.split(".")[0]) if len(n) >= 4} - {"localhost"}
    if home not in ("", "/"):
        plain.add(home)
    patterns = [r"(?:/Users|/home)/[A-Za-z0-9._-]+", r"-Users-[A-Za-z0-9._]+-", r"/var/folders",
                r"/private/tmp/claude-"]
    if len(user) >= 6 and user.lower() not in common:
        patterns.append(rf"(?<![A-Za-z0-9]){re.escape(user)}(?![A-Za-z0-9])")
    rx = re.compile("|".join(patterns), re.IGNORECASE)
    leaks = [str(p.relative_to(res)) for p, t in texts.items()
             if rx.search(t) or any(n.lower() in t.lower() for n in plain)]
    check("privacy: no home path, user name, host name or scratch path in results/", not leaks)

    width = max(len(n) for n, _ in results)
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}")
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
