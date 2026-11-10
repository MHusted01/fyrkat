"""Route I checks for verify-evidence.py: K1 and K2 booted through seL4's own elfloader with a Rust root task under QEMU TCG, and
the negative controls. Spike code, stdlib only. Loaded by verify-evidence.py by file path; `h` has `read`, `E1_PINS`.

What the checks establish: the images were built with the recorded commands from kernel configurations whose recorded
`gen_config.json` hashes equal the reviewed A2a K1 and K2; each boots to the root task's TEST_PASS in three of three boots with
the recorded QEMU arguments; and each negative control fails for the stated reason. They establish **functional execution under
emulation only**: nothing about verification applicability, timing, hardware or isolation.
"""
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCES = ("build-routei.sh", "boot-image.py", "a2a-compare.py")
BAD = re.compile(r"panicked|aborted|abort\(\)|Caught cap fault|fault|exception|assert", re.IGNORECASE)


def rb(path: Path) -> bytes:
    return path.read_bytes() if path.is_file() else b""


def section(text: str, ident: str) -> str:
    parts = re.split(r"(?m)^(?=## )", text)
    return next((p for p in parts if p.startswith(f"## {ident}\n") or p.startswith(f"## {ident}:")), "")


def guest(log: str) -> str:
    lines = log.replace("\r", "").split("\n")
    if lines and lines[0].startswith("+ "):
        lines = lines[1:]
    for i, line in enumerate(lines):
        if line.startswith("[boot-image]"):
            lines = lines[:i]
            break
    return "\n".join(lines)


def through(text: str) -> str:
    clean = text.replace("\r", "")
    return clean[: clean.find("TEST_PASS") + len("TEST_PASS")] if "TEST_PASS" in clean else clean


def in_order(text: str, needles: list[str]) -> bool:
    pos = 0
    for n in needles:
        pos = text.find(n, pos)
        if pos < 0:
            return False
        pos += len(n)
    return True


def verify_routei(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    try:
        _verify(res, check, h)
        check("Route I evidence files are present and well-formed", True)
    except (OSError, KeyError, ValueError, IndexError, TypeError) as err:
        check(f"Route I evidence files are present and well-formed (stopped at: {type(err).__name__})", False)


def _verify(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    rd = lambda rel: h.read(res, f"RouteI/{rel}")  # noqa: E731
    pre, post, tools, sums = rd("00-preflight.txt"), rd("07-post-checks.txt"), rd("01-tools.txt"), rd("04-sums.txt")
    pin = f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0"
    src = r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$"
    a = {m[2]: m[1] for m in re.finditer(src, pre)}
    b = {m[2]: m[1] for m in re.finditer(src, post)}
    check("Route I tools and inputs: GCC 16.2.0, CMake 4.4.5, Ninja 1.13.2, GNU cpio, the pinned clean seL4 and QEMU 11.1.3; no change to the seL4 source, Cargo.toml or Cargo.lock; build-routei.sh, boot-image.py and a2a-compare.py are the files the preflight and post-run record name",
          "compiler: aarch64-elf-gcc (GCC) 16.2.0" in tools and "cmake: cmake version 4.4.5" in tools and "ninja: 1.13.2" in tools and "cpio: " in tools
          and pin in tools and pin in pre and "QEMU emulator version 11.1.3" in pre and "seL4 source tracked diff: 0 lines" in post
          and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post and set(a) == set(SOURCES) and a == b
          and all(hashlib.sha256(rb(HERE / rel)).hexdigest() == sha for rel, sha in a.items()))
    k1_root = re.search(r"(?m)^k1-root-task ([0-9a-f]{64})$", sums)
    a1 = h.read(res, "A1-rerun/04-sums-rerun1.txt")
    check("Route I root tasks: K1's is the A1 rerun's accepted s1-root-task.elf (same SHA-256); K2's is a different binary built against K2's own kernel prefix",
          k1_root is not None and f"{k1_root[1]}  s1-root-task.elf" in a1 and k1_root[1] in pre
          and re.search(r"(?m)^k2-root-task ([0-9a-f]{64})$", sums) is not None
          and re.search(r"(?m)^k2-root-task (\S+)$", sums)[1] != k1_root[1])
    commands = rd("02-commands.txt")
    cmd = {i: section(commands, i) for i in ("K1", "K2", "K2H", "K2M")}
    builds = {i: rd(f"03-build-{i}.txt") for i in cmd}
    check("Route I builds: all four exit 0 with no error line; K1 has 1 node; K2, K2H and K2M have 4 nodes (SMP); only K2 and K2M are given the smc device tree",
          all(builds[i].startswith(f"## {i}: build exit 0") and not re.search(r"(?m)^(CMake )?Error|^FAILED|error:", builds[i]) for i in cmd)
          and "-DSMP" not in cmd["K1"] and "-DQEMU_DTB" not in cmd["K1"]
          and all("-DSMP=TRUE" in cmd[i] and "-DNUM_NODES=4" in cmd[i] for i in ("K2", "K2H", "K2M"))
          and all("-DQEMU_DTB=" in cmd[i] for i in ("K2", "K2M")) and "-DQEMU_DTB" not in cmd["K2H"])
    s = {m[1]: m[2] for m in re.finditer(r"(?m)^(\S+) ([0-9a-f]{64})$", sums)}
    a2a_k1 = hashlib.sha256(rb(res / "A2a/gen_config-K1.json")).hexdigest()
    a2a_k2 = hashlib.sha256(rb(res / "A2a/gen_config-K2.json")).hexdigest()
    check("Route I kernel configurations: the gen_config.json of the K1 image equals the reviewed A2a K1 (same SHA-256), and those of K2, K2H and K2M equal the reviewed A2a K2; the four images are distinct",
          a2a_k1 != hashlib.sha256(b"").hexdigest() and s.get("a2a-gen_config-K1") == a2a_k1 == s.get("gen_config-K1")
          and s.get("a2a-gen_config-K2") == a2a_k2 == s.get("gen_config-K2") == s.get("gen_config-K2H") == s.get("gen_config-K2M")
          and len({s.get(f"image-{i}") for i in ("K1", "K2", "K2H", "K2M")}) == 4)
    dts = rd("05-k2-smc.dts")
    check("Route I device tree: the K2 tree has the smc PSCI conduit and four CPUs that enable by PSCI",
          'method = "smc"' in dts and len(re.findall(r"enable-method = \"psci\"", dts)) == 4)

    def boots(prefix: str) -> list[str]:
        return [rd(f"{prefix}-{n}.txt") for n in (1, 2, 3)]

    def launched(log: str, image: str, smp: int, virt: bool) -> bool:
        """The run's recorded QEMU command line names this image directory, vCPU count and machine."""
        first = log.replace("\r", "").split("\n", 1)[0]
        machine = "virt,secure=off,gic-version=2" + (",virtualization=on" if virt else "")
        return (first.startswith("+ ") and f" -machine {machine} -accel tcg " in first and f" -smp {smp} " in first
                and first.endswith(f"/external/routei-build/{image}/build/images/rust-root-task-image-arm-qemu-arm-virt"))

    k1, k2 = boots("10-boot-K1"), boots("11-boot-K2")
    check("Route I launches: every boot's recorded QEMU command line names the image directory, the vCPU count and the machine its file name says (K1: 1 vCPU; K2 and the controls: 4 vCPUs; the no-virtualization control without `virtualization=on`; the controls use the K2H, K2 and K2M images)",
          all(launched(b, "K1", 1, False) for b in k1) and all(launched(b, "K2", 4, True) for b in k2)
          and launched(rd("20-neg-K2-default-dtb.txt"), "K2H", 4, True) and launched(rd("21-neg-K2-smc-dtb-no-virtualization.txt"), "K2", 4, False)
          and launched(rd("22-neg-K2-with-k1-root-task.txt"), "K2M", 4, True))
    seq1 = ["ELF-loader started", "Enabling MMU and jumping to entry point", "Bootstrapping kernel",
            "Booting all finished, dropped to user space", "Hello, World!", "badge = 0x1337", "TEST_PASS"]
    seq2 = ["ELF-loader started", "Core 1 is up with logic id 1", "Core 2 is up with logic id 2", "Core 3 is up with logic id 3",
            "Enabling MMU and jumping to entry point", "Bootstrapping kernel", "Booting all finished, dropped to user space",
            "Hello, World!", "badge = 0x1337", "TEST_PASS"]
    check("Route I K1: three of three boots through the elfloader reach the Rust root task's TEST_PASS on `-machine virt,secure=off,gic-version=2`, 1 vCPU, TCG, with no panic, abort or fault; the guest output is identical through TEST_PASS",
          all("-machine virt,secure=off,gic-version=2 -accel tcg" in b and "-smp 1" in b and "marker 'TEST_PASS' SEEN" in b
              and in_order(guest(b), seq1) and not BAD.search(guest(b)) for b in k1) and len({through(guest(b)) for b in k1}) == 1)
    check("Route I K2: three of three boots through the elfloader bring up all four cores and reach the Rust root task's TEST_PASS on `-machine virt,secure=off,gic-version=2,virtualization=on`, 4 vCPUs, TCG, with no panic, abort or fault; the guest output is identical through TEST_PASS",
          all("-machine virt,secure=off,gic-version=2,virtualization=on -accel tcg" in b and "-smp 4" in b and "marker 'TEST_PASS' SEEN" in b
              and in_order(guest(b), seq2) and not BAD.search(guest(b)) for b in k2) and len({through(guest(b)) for b in k2}) == 1)
    n1, n2, n3 = rd("20-neg-K2-default-dtb.txt"), rd("21-neg-K2-smc-dtb-no-virtualization.txt"), rd("22-neg-K2-with-k1-root-task.txt")
    check("Route I negative controls: K2 with seL4's default device tree aborts in the elfloader on the PSCI conduit; K2's smc tree on a machine without virtualization never brings up core 1; K2 with the K1-built root task boots all cores and then fails the root task's badge check (observed badge 0, expected 0x1337); none prints TEST_PASS",
          "HVC is not supported for PSCI!" in n1 and "abort() called" in n1 and "virtualization=on" in n1 and "marker 'TEST_PASS' NOT seen" in n1
          and "Boot cpu id" in n2 and "Core 1 is up" not in n2 and "virtualization=on" not in n2 and "marker 'TEST_PASS' NOT seen" in n2
          and "Core 3 is up with logic id 3" in n3 and "badge = 0x1337" in n3 and "crates/root-task/src/main.rs:62" in n3
          and "left: 0" in n3 and "right: 4919" in n3 and "marker 'TEST_PASS' NOT seen" in n3
          and all("TEST_PASS\n" not in guest(x) and "\nTEST_PASS" not in guest(x) for x in (n1, n2, n3)))


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    def r(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"RouteI/{path}", fn)

    return [
        ("a K1 boot lacks TEST_PASS", r("10-boot-K1-2.txt", lambda t: t.replace("TEST_PASS\n", "TEST_PAS\n").replace("SEEN", "NOT seen", 1)), "Route I K1"),
        ("a K2 boot misses a core", r("11-boot-K2-3.txt", lambda t: t.replace("Core 3 is up with logic id 3\n", "")), "Route I K2"),
        ("a K2 boot ran without virtualization", r("11-boot-K2-1.txt", lambda t: t.replace(",virtualization=on", "", 1)), "Route I K2"),
        ("the default-tree control no longer shows the PSCI abort", r("20-neg-K2-default-dtb.txt", lambda t: t.replace("HVC is not supported for PSCI!", "")), "Route I negative controls"),
        ("the K1-root-task control no longer shows the badge failure", r("22-neg-K2-with-k1-root-task.txt", lambda t: t.replace("right: 4919", "right: 1")), "Route I negative controls"),
        ("K2's kernel configuration differs from A2a's", r("04-sums.txt", lambda t: re.sub(r"(?m)^(gen_config-K2 )[0-9a-f]", r"\g<1>0", t, count=1)), "Route I kernel configurations"),
        ("K2's tree says hvc", r("05-k2-smc.dts", lambda t: t.replace('method = "smc"', 'method = "hvc"', 1)), "Route I device tree"),
        ("a build is recorded as failed", r("03-build-K2.txt", lambda t: t.replace("build exit 0", "build exit 2", 1)), "Route I builds"),
        ("K1's root task hash is not the A1 rerun's", r("04-sums.txt", lambda t: re.sub(r"(?m)^(k1-root-task )[0-9a-f]", r"\g<1>0", t, count=1)), "Route I root tasks"),
        ("a control was run with one vCPU", r("21-neg-K2-smc-dtb-no-virtualization.txt", lambda t: t.replace(" -smp 4 ", " -smp 1 ", 1)), "Route I launches"),
        ("a K2 boot was run from the control image", r("11-boot-K2-2.txt", lambda t: t.replace("/routei-build/K2/", "/routei-build/K2M/", 1)), "Route I launches"),
        ("a source hash differs between the records", r("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )[0-9a-f](?=[0-9a-f]{63}  build-routei.sh)", r"\g<1>0", t, count=1)), "Route I tools and inputs"),
    ]
