#!/usr/bin/env python3
"""Re-check the A1, A3, E1, E2, E3 and A2a conclusions against the sanitized public evidence in results/.

    verify-evidence.py [--results DIR] [--lock FILE] [--self-test]

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
import importlib.util
import json
import re
import socket
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace


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


E1_ORDER = ("Bootstrapping kernel", "Booting all finished, dropped to user space", "Hello, World!",
            "badge = 0x1337", "TEST_PASS")
E1_FAILURE = re.compile(r"fault|halt|panic|exception|abort|assert|!!!", re.IGNORECASE)
E1_PINS = {"seL4": "62e345c240a15671484530b4e6e069ce266c28d7",
           "rust-sel4": "c819c27b076130cba9821c4555f23773e4b0bffd"}


def in_order(text: str, needles: tuple[str, ...]) -> bool:
    """True when every needle occurs, each after the previous one."""
    pos = 0
    for needle in needles:
        pos = text.find(needle, pos)
        if pos < 0:
            return False
        pos += len(needle)
    return True


def guest_output(log: str) -> str:
    """The guest's serial output only: without the harness's own `+ command` line and `[boot-image]` footer.

    The footer contains the marker text, so a check that read the whole log could be satisfied by the footer."""
    lines = log.replace("\r", "").split("\n")
    if lines and lines[0].startswith("+ "):
        lines = lines[1:]
    for i, line in enumerate(lines):
        if line.startswith("[boot-image]"):
            lines = lines[:i]
            break
    return "\n".join(lines)


def through_marker(text: str) -> str:
    """The boot output up to and including the success marker, CRs removed.

    The harness stops reading as soon as the marker is in its buffer, so whether the line terminator after the
    marker was captured depends on timing. It is not part of the guest's output that is compared."""
    clean = text.replace("\r", "")
    return clean[: clean.find("TEST_PASS") + len("TEST_PASS")] if "TEST_PASS" in clean else clean


# E2 added exactly these three packages to Cargo.lock (the two new crates and the `object` crate, owner-approved
# 2026-11-09). The A1, A1-rerun and E1 checks about the lock are made against the lock without them.
E2_LOCK_ADDITIONS = {("e2-root-task", None), ("e2-task", None), ("object", "0.40.0")}
E2_OBJECT_CHECKSUM = "dd229a0361b9d0d4396176e02d65897f487eebeab7caa6d443855ee152ca0b9c"


def split_e2_lock(text: str) -> tuple[str, list[str]]:
    """Return the lock text without the E2 additions, and the removed blocks (each a whole [[package]] block)."""
    kept: list[str] = []
    removed: list[str] = []
    for block in re.split(r"(?m)^(?=\[\[package\]\]$)", text):
        name = re.search(r'(?m)^name = "([^"]+)"$', block)
        ver = re.search(r'(?m)^version = "([^"]+)"$', block)
        key = (name.group(1), ver.group(1)) if name and ver and block.startswith("[[package]]") else None
        if key is not None and ((key[0], None) in E2_LOCK_ADDITIONS or key in E2_LOCK_ADDITIONS):
            removed.append(block)
        else:
            kept.append(block)
    return "".join(kept), removed


E2_ORDER = ("Bootstrapping kernel", "Booting all finished, dropped to user space", "E2_ROOT start",
            "E2_SERVER secret mapped and readable", "E2_SERVER ready",
            "E2_SERVER got request=41 badge=0xa11ce served=1",
            "E2_CLIENT call ok reply=42 served=1 badge=0xa11ce", "E2_CLIENT empty-slot refused label=2",
            "E2_CLIENT wrong-type refused label=3", "E2_CLIENT badge-forge refused",
            "E2_SERVER got request=100 badge=0xa11ce served=2", "E2_CLIENT second call ok served=2",
            "E2_CLIENT reading server memory", "E2_ROOT client vm fault at 0x50000000, badge 1", "E2_PASS")
E2_FAILURE = re.compile(r"E2_FAIL|panic|halt|assert|abort|exception|!!!", re.IGNORECASE)


def through_e2_marker(text: str) -> str:
    """Boot output up to and including E2_PASS, CRs removed (same reason as `through_marker`)."""
    clean = text.replace("\r", "")
    return clean[: clean.find("E2_PASS") + len("E2_PASS")] if "E2_PASS" in clean else clean


def verify_e2(res: Path, lock_text: str, e1_post: str, check: Callable[[str, bool], None], e1_present: bool) -> None:
    """E2 checks. Reads only sanitized files in results/E2 (and E1's post-run record for comparison)."""
    cfg = json.loads(read(res, "E2/02-kernel-gen_config.json"))
    e1cfg = json.loads(read(res, "E1/02-kernel-gen_config.json")) if e1_present else None
    diff = read(res, "E2/05-config-diff-vs-e1.txt")
    check("E2 kernel config: byte-for-key identical to E1's (hypervisor support on, 156 keys, 0 differ)",
          cfg == e1cfg and cfg.get("ARM_HYPERVISOR_SUPPORT") is True
          and "156 keys in E1-H config, 156 in E2 config, 0 differ:" in diff)
    build = read(res, "E2/01-build.txt")
    post = read(res, "E2/04-post-checks.txt")
    pre = read(res, "E2/00-preflight.txt")
    check("E2 build: succeeded (exit 0) with no error line",
          "BUILD_EXIT=0" in build and not re.search(r"(?m)^error", build))
    base_text, added = split_e2_lock(lock_text)
    additions = sorted(re.search(r'name = "([^"]+)"', b).group(1) for b in added if re.search(r'name = "', b))
    check("E2 Cargo.lock: the repository lock is the E1-era lock plus exactly e2-root-task, e2-task and object 0.40.0 "
          "(checksum as in rust-sel4's own lock), purely additive",
          additions == ["e2-root-task", "e2-task", "object"]
          and any(E2_OBJECT_CHECKSUM in b for b in added)
          and "Cargo.lock diff vs HEAD: 29 0 (added, removed lines)" in post
          and f"Cargo.lock sha256: {hashlib.sha256(lock_text.encode()).hexdigest()}" in post)
    check("E2 inputs: seL4 and rust-sel4 at their pins and clean, crates/root-task unchanged, only Cargo.toml and "
          "Cargo.lock changed among tracked files",
          all(f"{n} HEAD: {sha}; dirty files: 0" in post for n, sha in E1_PINS.items())
          and "crates/root-task tracked diff vs HEAD: 0 lines" in post
          and "tracked files changed vs HEAD: 2 (spikes/sel4-feasibility/Cargo.lock spikes/sel4-feasibility/Cargo.toml )" in post)
    check("E2 toolchain and host recorded (QEMU 11.1.3, GCC 16.2.0, CMake 4.4.5, nightly-2026-08-21 rustc, arm64 host)",
          "QEMU emulator version 11.1.3" in pre and "aarch64-elf-gcc (GCC) 16.2.0" in pre
          and "cmake version 4.4.5" in pre and "8925ea358 2026-08-20" in pre and "arm64" in pre)
    built = sums(build)
    names = {"kernel.elf", "sel4-kernel-loader.elf", "e2-client.elf", "e2-server.elf", "e2-root-task.elf", "image.elf"}
    recorded = {m.group(2): m.group(1) for m in re.finditer(r"(?m)^e2 ([0-9a-f]{64})\s+(\S+)$", post)}
    e1_recorded = {m.group(2): m.group(1) for m in re.finditer(r"(?m)^e1 ([0-9a-f]{64})\s+(\S+)$", e1_post)}
    check("E2 hash table: the build log and the post-run record agree on the six outputs; the loader is E1's loader",
          set(built) == names and built == recorded
          and built["sel4-kernel-loader.elf"] == e1_recorded.get("sel4-kernel-loader.elf"))
    check("E2 hashes: the kernel and the image differ from E1's (the kernel embeds its build directory, which differs)",
          built["kernel.elf"] != e1_recorded.get("kernel.elf") and built["image.elf"] != e1_recorded.get("image.elf"))
    image_line = re.search(r"image used for the boots: \S+ ([0-9a-f]{64})", post)
    boots = [read(res, f"E2/10-boot-{n}.txt") for n in (1, 2, 3)]
    check("E2 boots: all three used the recorded image.elf",
          image_line is not None and image_line.group(1) == built["image.elf"])
    check("E2 boots: each run's command line and footer record virt,secure=off,gic-version=2,virtualization=on "
          "under TCG, Cortex-A57, 1 vCPU",
          all("-machine virt,secure=off,gic-version=2,virtualization=on -accel tcg -cpu cortex-a57 -smp 1" in b
              and "accel=tcg cpu=cortex-a57 smp=1 gic=2 virt=True" in b for b in boots))
    guests = [guest_output(b) for b in boots]
    check("E2 boots: in the guest output of all three, the whole E2 sequence appears in order, ending in an E2_PASS line",
          all(in_order(g, E2_ORDER) and re.search(r"(?m)^E2_PASS$", g) is not None for g in guests))
    check("E2 boots: in all three, the harness reports the marker SEEN",
          all("marker 'E2_PASS' SEEN" in b for b in boots))
    check("E2 boots: no E2_FAIL, panic, halt, assertion, abort, exception or '!!!' in the guest output of any of the three",
          not any(E2_FAILURE.search(g) for g in guests))
    check("E2 boots: the server served exactly two requests and the only line naming a fault is the root task's VM fault",
          all(len(re.findall(r"(?m)^E2_SERVER got request=", g)) == 2
              and [ln for ln in g.split("\n") if re.search("fault", ln, re.IGNORECASE)]
              == ["E2_ROOT client vm fault at 0x50000000, badge 1"] for g in guests))
    check("E2 boots: output through E2_PASS identical across the three (the line terminator after the marker "
          "depends on read timing and is excluded)",
          len({through_e2_marker(g) for g in guests}) == 1)
    mut = read(res, "E2/06-mutation-checks.txt")
    check("E2 mutation checks: both mutants were refused E2_PASS and each printed the E2_FAIL naming its check",
          mut.count("marker 'E2_PASS' NOT seen") == 2 and "marker 'E2_PASS' SEEN" not in mut
          and "E2_FAIL client: read of the server's secret did not fault" in mut
          and "E2_FAIL client: empty slot was not refused with InvalidCapability" in mut)


def load_e3() -> ModuleType:
    """The E3 checks (verify_e3.py, next to this file), loaded by path so that `python3 -I` works too."""
    path = Path(__file__).resolve().parent / "verify_e3.py"
    spec = importlib.util.spec_from_file_location("verify_e3", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_a2a() -> ModuleType:
    """The A2a checks (verify_a2a.py, next to this file), loaded by path like the E3 ones."""
    path = Path(__file__).resolve().parent / "verify_a2a.py"
    spec = importlib.util.spec_from_file_location("verify_a2a", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def e3_helpers() -> SimpleNamespace:
    return SimpleNamespace(read=read, sums=sums, in_order=in_order, guest_output=guest_output, section=section,
                           E1_PINS=E1_PINS)


def verify_e1(res: Path, lock_hash: str, a1rerun: dict[str, str], check: Callable[[str, bool], None]) -> None:
    """E1 checks. `check` records (name, ok). Reads only sanitized files in results/E1."""
    cfg = json.loads(read(res, "E1/02-kernel-gen_config.json"))
    check("E1 kernel config: hypervisor support on, qemu-arm-virt, Cortex-A57, 1 node, non-MCS, not a verification build",
          cfg.get("ARM_HYPERVISOR_SUPPORT") is True and cfg.get("PLAT_QEMU_ARM_VIRT") is True
          and cfg.get("ARM_CORTEX_A57") is True and cfg.get("MAX_NUM_NODES") == "1"
          and cfg.get("KERNEL_MCS") is False and cfg.get("VERIFICATION_BUILD") is False)
    a1cfg = json.loads(read(res, "A1/kernel-gen_config.json"))
    changed = {k for k in set(a1cfg) | set(cfg) if a1cfg.get(k) != cfg.get(k)}
    check("E1 kernel config differs from A1's published kernel config in exactly one key, ARM_HYPERVISOR_SUPPORT "
          "(False in A1, True in E1)",
          changed == {"ARM_HYPERVISOR_SUPPORT"} and a1cfg.get("ARM_HYPERVISOR_SUPPORT") is False
          and cfg.get("ARM_HYPERVISOR_SUPPORT") is True)
    diff = read(res, "E1/05-config-diff-vs-a1rerun.txt")
    check("E1 the recorded config comparison (the A1 rerun's build) agrees: 156 keys each, one differs",
          "156 keys in A1-rerun config, 156 in E1-H config, 1 differ:" in diff
          and "ARM_HYPERVISOR_SUPPORT: A1-rerun=False  E1-H=True" in diff
          and len(re.findall(r"(?m)^  \w+: A1-rerun=", diff)) == 1)
    build = read(res, "E1/01-build.txt")
    cache = read(res, "E1/03-kernel-cmake-cache.txt")
    check("E1 build: succeeded (exit 0) with no error line, and the recorded CMake cache has the hypervisor option on",
          "BUILD_EXIT=0" in build and not re.search(r"(?m)^error", build)
          and "KernelArmHypervisorSupport:BOOL=ON" in cache and "KernelVerificationBuild:BOOL=OFF" in cache
          and "KernelPlatform:STRING=qemu-arm-virt" in cache and "KernelMaxNumNodes:STRING=1" in cache)
    post = read(res, "E1/04-post-checks.txt")
    pre = read(res, "E1/00-preflight.txt")
    check("E1 inputs: seL4 and rust-sel4 at their pins and clean, no tracked file changed, Cargo.lock unchanged "
          "(compared without the three packages E2 added)",
          all(f"{n} HEAD: {sha}; dirty files: 0" in post for n, sha in E1_PINS.items())
          and "tracked files changed vs HEAD: 0" in post and "crates/root-task tracked diff vs HEAD: 0 lines" in post
          and f"Cargo.lock sha256: {lock_hash}" in post and f"Cargo.lock sha256: {lock_hash}" in pre)
    check("E1 toolchain and host recorded (QEMU 11.1.3, GCC 16.2.0, CMake 4.4.5, nightly-2026-08-21 rustc, arm64 host)",
          "QEMU emulator version 11.1.3" in pre and "aarch64-elf-gcc (GCC) 16.2.0" in pre
          and "cmake version 4.4.5" in pre and "8925ea358 2026-08-20" in pre and "arm64" in pre)
    built = sums(build)
    names = {"kernel.elf", "sel4-kernel-loader.elf", "s1-root-task.elf", "image.elf"}
    recorded = {m.group(2): m.group(1) for m in re.finditer(r"(?m)^e1 ([0-9a-f]{64})\s+(\S+)$", post)}
    check("E1 hash table: the build log and the post-run record agree on the four outputs",
          set(built) == names and built == recorded)
    check("E1 hashes are its own: kernel, loader, root task and image all differ from the A1 rerun's",
          all(built[n] != a1rerun[n] for n in names))
    image_line = re.search(r"image used for the boots: \S+ ([0-9a-f]{64})", post)
    boots = [read(res, f"E1/10-boot-{n}.txt") for n in (1, 2, 3)]
    check("E1 boots: all three used the recorded image.elf",
          image_line is not None and image_line.group(1) == built["image.elf"])
    check("E1 boots: each run's command line and footer record virt,secure=off,gic-version=2,virtualization=on "
          "under TCG, Cortex-A57, 1 vCPU",
          all("-machine virt,secure=off,gic-version=2,virtualization=on -accel tcg -cpu cortex-a57 -smp 1" in b
              and "accel=tcg cpu=cortex-a57 smp=1 gic=2 virt=True" in b for b in boots))
    guests = [guest_output(b) for b in boots]
    check("E1 boots: in the guest output of all three, the banner, Hello, World!, badge = 0x1337 and a TEST_PASS "
          "line appear in that order",
          all(in_order(g, E1_ORDER) and re.search(r"(?m)^TEST_PASS$", g) is not None for g in guests))
    check("E1 boots: in all three, the harness reports the marker SEEN",
          all("marker 'TEST_PASS' SEEN" in b for b in boots))
    check("E1 boots: no fault, halt, panic, exception, abort, assertion or '!!!' in the guest output of any of the three",
          not any(E1_FAILURE.search(g) for g in guests))
    check("E1 boots: output through TEST_PASS identical across the three (the line terminator after the marker "
          "depends on read timing and is excluded)",
          len({through_marker(g) for g in guests}) == 1)


def run_checks(res: Path, lock_path: Path) -> list[tuple[str, bool]]:
    """Run every check against RES and return (name, passed) pairs."""
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
    # bytes, not read_text(): universal newlines would make a CRLF or CR copy hash like the real file
    lock_text = lock_path.read_bytes().decode("utf-8") if lock_path.is_file() else ""
    base_lock, _added = split_e2_lock(lock_text)
    actual = hashlib.sha256(base_lock.encode()).hexdigest() if lock_text else ""
    check("A1 rerun: the lock file in the repository is the corrected one recorded in the evidence "
          "(compared without the three packages E2 added)",
          m is not None and m.group(2) == actual and m.group(1) != actual and m.group(1).startswith("c92d1dca"))
    pkgs: dict[str, set[str]] = {}
    if lock_text:
        for pkg in tomllib.loads(base_lock)["package"]:
            pkgs.setdefault(pkg["name"], set()).add(pkg["version"])
    approved = {"cc": {"1.10.0"}, "log": {"0.4.34"}, "psm": {"0.1.24"}, "pest_stack_guard": {"1.0.0"}}
    check("A1 rerun: the lock file has the four approved versions and neither ar_archive_writer nor object "
          "(without the three packages E2 added)",
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

    # ---- E1 (Route II): functional boot of a hypervisor-enabled kernel under TCG. Label U, functional only.
    check("E1 evidence directory is present", (res / "E1").is_dir())
    if (res / "E1").is_dir():
        verify_e1(res, actual, r_sum2, check)

    # ---- E2: two isolated tasks over seL4 IPC and four refused attempts to exceed their authority. Label U.
    check("E2 evidence directory is present", (res / "E2").is_dir())
    if (res / "E2").is_dir():
        e1_post = read(res, "E1/04-post-checks.txt") if (res / "E1/04-post-checks.txt").is_file() else ""
        e1cfg_ok = (res / "E1/02-kernel-gen_config.json").is_file()
        verify_e2(res, lock_text, e1_post, check, e1cfg_ok)

    # ---- E3: capability revocation. Label U.
    check("E3 evidence directory is present", (res / "E3").is_dir())
    if (res / "E3").is_dir():
        e1_post = read(res, "E1/04-post-checks.txt") if (res / "E1/04-post-checks.txt").is_file() else ""
        load_e3().verify_e3(res, lock_text, e1_post, check, (res / "E1/02-kernel-gen_config.json").is_file(), e3_helpers())

    # ---- A2a: assurance classification inputs (no boot). Label U for the builds, no formal-verification claim.
    check("A2a evidence directory is present", (res / "A2a").is_dir())
    if (res / "A2a").is_dir():
        load_a2a().verify_a2a(res, check, e3_helpers())

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
    evidence = {p.relative_to(res).as_posix() for sub in ("A1", "A1-rerun", "A3", "E1", "E2", "E3", "A2a") for p in (res / sub).rglob("*")
                if p.is_file() and p.as_posix() != (res / "A3/shim-era/README.md").as_posix()}
    check("manifest: it lists exactly the evidence files under A1/, A1-rerun/, A3/, E1/, E2/, E3/ and A2a/ (one README note aside)",
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

    return results


def rehash_manifest(res: Path) -> None:
    """Rewrite the sanitized-hash column of the manifest for the files that exist, and drop lines for missing ones."""
    path = res / "evidence-manifest.txt"
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            out.append(line)
            continue
        raw, _clean, rel = line.split(None, 2)
        target = res / rel
        if target.is_file():
            out.append(f"{raw}  {hashlib.sha256(target.read_bytes()).hexdigest()}  {rel}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def self_test(res: Path, lock_path: Path) -> int:
    """Corrupt a temporary copy of the evidence in targeted ways, keeping the manifest consistent, and require the
    named check to fail each time. The unmodified copy must pass every check. Nothing in RES is changed."""
    import shutil
    import tempfile

    def edit(rel: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        def apply(root: Path) -> None:
            f = root / rel
            f.write_text(fn(f.read_text(encoding="utf-8")), encoding="utf-8")
        return apply

    def every_boot(fn: Callable[[str], str], sub: str = "E1") -> Callable[[Path], None]:
        steps = [edit(f"{sub}/10-boot-{n}.txt", fn) for n in (1, 2, 3)]

        def apply(root: Path) -> None:
            for step in steps:
                step(root)
        return apply

    def drop_guest_marker(text: str) -> str:
        return "\n".join(ln for ln in text.split("\n") if ln.rstrip("\r") != "TEST_PASS")

    def marker_before_badge(text: str) -> str:
        lines = text.split("\n")
        i = next(n for n, ln in enumerate(lines) if ln.startswith("badge = "))
        j = next(n for n, ln in enumerate(lines) if ln.rstrip("\r") == "TEST_PASS")
        lines.insert(i, lines.pop(j))
        return "\n".join(lines)

    def remove_e1(root: Path) -> None:
        shutil.rmtree(root / "E1")

    def remove_e2(root: Path) -> None:
        shutil.rmtree(root / "E2")

    def remove_e3(root: Path) -> None:
        shutil.rmtree(root / "E3")

    def remove_a2a(root: Path) -> None:
        shutil.rmtree(root / "A2a")

    def drop_line(prefix: str) -> Callable[[str], str]:
        return lambda t: "\n".join(ln for ln in t.split("\n") if not ln.startswith(prefix))

    def stray_request(text: str) -> str:
        return text.replace("E2_CLIENT empty-slot refused",
                            "E2_SERVER got request=7 badge=0x0 served=2\nE2_CLIENT empty-slot refused", 1)

    cases: list[tuple[str, Callable[[Path], None], str]] = [
        ("the guest never prints TEST_PASS (the footer still names it)", every_boot(drop_guest_marker),
         "a TEST_PASS line appear in that order"),
        ("TEST_PASS printed before the badge line", every_boot(marker_before_badge),
         "a TEST_PASS line appear in that order"),
        ("a loader exception line in boot 2", edit("E1/10-boot-2.txt", lambda t: t.replace(
            "Booting all finished", "!!! Exception: instruction abort\nBooting all finished", 1)),
         "no fault, halt, panic"),
        ("a second kernel option differs from A1's", edit("E1/02-kernel-gen_config.json", lambda t: t.replace(
            '"PRINTING": true', '"PRINTING": false', 1)), "in exactly one key"),
        ("hypervisor support off in the E1 config", edit("E1/02-kernel-gen_config.json", lambda t: t.replace(
            '"ARM_HYPERVISOR_SUPPORT": true', '"ARM_HYPERVISOR_SUPPORT": false', 1)), "hypervisor support on"),
        ("a different image hash in the post-run record", edit("E1/04-post-checks.txt", lambda t: t.replace(
            "image used for the boots: external/e1-build/image.elf 4487", "image used for the boots: external/e1-build/image.elf 0000", 1)),
         "all three used the recorded image.elf"),
        ("the E1 evidence is removed", remove_e1, "E1 evidence directory is present"),
        ("the guest never prints E2_PASS (the footer still names it)",
         every_boot(drop_line("E2_PASS"), "E2"), "whole E2 sequence appears in order"),
        ("no VM fault line from the root task (the client's read of the server's memory is not shown to fault)",
         every_boot(drop_line("E2_ROOT client vm fault"), "E2"), "whole E2 sequence appears in order"),
        ("a stray request reaches the server during the refused attempts", every_boot(stray_request, "E2"),
         "the server served exactly two requests"),
        ("an E2_FAIL line in boot 2", edit("E2/10-boot-2.txt", lambda t: t.replace(
            "E2_CLIENT call ok", "E2_FAIL client: x\nE2_CLIENT call ok", 1)), "no E2_FAIL, panic"),
        ("hypervisor support off in the E2 config", edit("E2/02-kernel-gen_config.json", lambda t: t.replace(
            '"ARM_HYPERVISOR_SUPPORT": true', '"ARM_HYPERVISOR_SUPPORT": false', 1)), "byte-for-key identical to E1"),
        ("a mutant is recorded as having passed", edit("E2/06-mutation-checks.txt", lambda t: t.replace(
            "marker 'E2_PASS' NOT seen", "marker 'E2_PASS' SEEN", 1)), "both mutants were refused"),
        ("the E2 evidence is removed", remove_e2, "E2 evidence directory is present"),
        ("the E3 evidence is removed", remove_e3, "E3 evidence directory is present"),
        *load_e3().self_test_cases(edit, every_boot, drop_line),
        ("the A2a evidence is removed", remove_a2a, "A2a evidence directory is present"),
        *load_a2a().self_test_cases(edit),
    ]
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = [n for n, ok in run_checks(res, lock_path) if not ok]
        if base:
            print(f"self-test cannot start: {len(base)} check(s) already fail on the real evidence")
            return 2
        for label, mutate, expect in cases:
            work = Path(tmp) / "case"
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(res, work)
            mutate(work)
            rehash_manifest(work)
            failed = [n for n, ok in run_checks(work, lock_path) if not ok]
            hit = any(expect in n for n in failed)
            print(f"{'ok  ' if hit else 'MISS'}  {label}: failing checks = {len(failed)}")
            if not hit:
                failures.append(label)
        # Corruptions of the lock file itself (the evidence stays intact; a modified copy of the lock is passed in).
        def crlf(t: str) -> str:
            return t.replace("\n", "\r\n")

        def other_checksum(t: str) -> str:
            return t.replace(E2_OBJECT_CHECKSUM, "0" * 64, 1)

        def extra_package(t: str) -> str:
            return t + '\n[[package]]\nname = "extra"\nversion = "1.0.0"\n'

        def e2_task_extra_dep(t: str) -> str:
            head, sep, tail = t.partition('name = "e2-task"')
            return head + sep + tail.replace('dependencies = [', 'dependencies = [\n "memchr",', 1)

        lock_cases: list[tuple[str, Callable[[str], str], str]] = [
            ("the lock has CRLF line endings", crlf, "the lock file in the repository is the corrected one"),
            ("the lock has CRLF line endings (E2 lock check)", crlf, "E2 Cargo.lock"),
            ("the lock has an extra package", extra_package, "the lock file in the repository is the corrected one"),
            ("object's checksum in the lock is changed", other_checksum, "E2 Cargo.lock"),
            ("e2-task gains a dependency in the lock", e2_task_extra_dep, "E2 Cargo.lock"),
            ("the lock has an extra package (E3 inputs check: the lock is the one the E3 records name)", extra_package,
             "E3 inputs"),
        ]
        for label, mutate_lock, expect in lock_cases:
            bad_lock = Path(tmp) / "Cargo.lock"
            bad_lock.write_bytes(mutate_lock(lock_path.read_bytes().decode("utf-8")).encode("utf-8"))
            failed = [n for n, ok in run_checks(res, bad_lock) if not ok]
            hit = any(expect in n for n in failed)
            print(f"{'ok  ' if hit else 'MISS'}  {label}: failing checks = {len(failed)}")
            if not hit:
                failures.append(label)
    total = len(cases) + len(lock_cases)
    print(f"\nself-test: {total - len(failures)} of {total} corruptions were caught")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--results", default=str(Path(__file__).resolve().parent / "results"))
    ap.add_argument("--lock", default=str(Path(__file__).resolve().parent / "Cargo.lock"))
    ap.add_argument("--self-test", action="store_true",
                    help="corrupt a temporary copy of the evidence and require the E1, E2, E3 and A2a checks to fail")
    ns = ap.parse_args()
    res, lock_path = Path(ns.results), Path(ns.lock)
    if ns.self_test:
        return self_test(res, lock_path)
    results = run_checks(res, lock_path)
    width = max(len(n) for n, _ in results)
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{width}}")
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
