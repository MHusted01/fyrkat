"""Release-kernel execution checks for verify-evidence.py: the release kernels K1R and K2R boot through seL4's elfloader and run a
Rust root task that logs through its own UART driver, with the debug kernels, two broken tests and two mismatched pairings as
controls. Spike code, stdlib only. Loaded by verify-evidence.py by file path; `h` has `read`, `E1_PINS`.

What the checks establish: each image's kernel has the configuration and the function table recorded for that ID in the A2a
and A2a-variants evidence; K1R and K2R run every test of the root task to `RELK_PASS` in three of three boots, with nothing on
the console after the loader that the root task did not print; the debug system call is refused on the release kernels and
accepted on the debug ones; and each control fails in exactly the stated test. They establish **functional execution under one
emulator only**: nothing about verification applicability, hardware, timing, or isolation (the test's worker threads share
the root task's capability space). Not Stage B evidence.
"""
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RS = "crates/e2-root-task/src"
SOURCES = ("build-relk.sh", "run-relk-evidence.sh", "boot-image.py", "a2a-compare.py", f"{RS}/bin/relk_root_task.rs", f"{RS}/relk_tests.rs",
           f"{RS}/relk_workers.rs", f"{RS}/relk_spawn.rs", f"{RS}/slots.rs", f"{RS}/rawsys.rs", f"{RS}/pl011.rs", f"{RS}/a5_mmio.rs", f"{RS}/object_allocator.rs")
NAMES = ("K1", "K1R", "K2", "K2R", "K1R-skip-revoke", "K2R-rw-alias", "K1R-debug-root", "K1R-putchar-demo")
TESTS = ["notification-badge", "ipc-call-reply", "vm-fault-delivery", "debug-syscall", "revoke-badged-copy", "page-permission-and-unmap",
         "timer-preemption"]
SMP_TEST = "smp-other-cores"
LOADER_LAST = "Enabling MMU and jumping to entry point..."
KERNEL_LINES = ("Bootstrapping kernel", "Booting all finished", "<<seL4", "seL4(CPU")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def rb(path: Path) -> bytes:
    return path.read_bytes() if path.is_file() else b""


def section(text: str, ident: str) -> str:
    parts = re.split(r"(?m)^(?=## )", text)
    return next((p for p in parts if p.startswith(f"## {ident}\n") or p.startswith(f"## {ident}:")), "")


def guest(log: str) -> list[str]:
    """The guest's console lines: without boot-image.py's first (command) line and its footer, and without colour codes."""
    lines = ANSI.sub("", log.replace("\r", "")).split("\n")
    if lines and lines[0].startswith("+ "):
        lines = lines[1:]
    end = next((i for i, ln in enumerate(lines) if ln.startswith("[boot-image]")), len(lines))
    return lines[:end]


def after_loader(log: str) -> list[str] | None:
    """The non-empty console lines after the elfloader's last line, or None if the loader never got there."""
    lines = guest(log)
    at = next((i for i, ln in enumerate(lines) if ln.startswith(LOADER_LAST)), None)
    return None if at is None else [ln for ln in lines[at + 1:] if ln.strip()]


def verdicts(lines: list[str]) -> list[tuple[str, str]]:
    return [(m[1], m[2]) for ln in lines if (m := re.fullmatch(r"RELK test=(\S+) result=(PASS|FAIL)", ln))]


def launched(log: str, name: str, smp: int, virt: bool, marker: str, seen: bool) -> bool:
    first = log.replace("\r", "").split("\n", 1)[0]
    machine = "virt,secure=off,gic-version=2" + (",virtualization=on" if virt else "")
    return (first.startswith("+ ") and f" -machine {machine} -accel tcg -cpu cortex-a57 -smp {smp} " in first
            and first.endswith(f"/external/relk-build/{name}/build/images/rust-root-task-image-arm-qemu-arm-virt")
            and f"[boot-image] marker '{marker}' {'SEEN' if seen else 'NOT seen'} after" in log)


def run_ok(log: str, *, printing: bool, nodes: int, mutant: str, failing: tuple[str, ...]) -> bool:
    """One run of the test root task: the configuration it reports, the verdict of every test in order, and its last lines."""
    lines = after_loader(log)
    if lines is None:
        return False
    relk = [ln for ln in lines if ln.startswith("RELK")]
    expected = TESTS + ([SMP_TEST] if nodes > 1 else [])
    want = [(t, "FAIL" if t in failing else "PASS") for t in expected]
    p = "true" if printing else "false"
    last = "RELK_FAIL" if failing else "RELK_PASS"
    return (f"RELK built-for: PRINTING={p} DEBUG_BUILD={p} MAX_NUM_NODES={nodes} ARM_HYPERVISOR_SUPPORT=false KERNEL_MCS=false mutant={mutant}" in relk
            and any(ln.startswith(f"RELK kernel-reports: nodes={nodes} node_id=0 ") and "uart_device_untyped=Some((9000000, 1000000))" in ln for ln in relk)
            and "RELK start: user-level PL011 console at 0x9000000, control register 0x101" in relk
            and verdicts(relk) == want and len(relk) >= 2 and relk[-1] == last
            and relk[-2] == f"RELK summary passed={len(want) - len(failing)} failed={len(failing)} console_bytes_dropped=0 mmio_range_errors=0")


def release_console(log: str) -> bool:
    """On a release kernel every line after the loader's last is the root task's, and the kernel printed nothing for the probe."""
    lines = after_loader(log)
    return (lines is not None and len(lines) > 0 and all(ln.startswith("RELK") for ln in lines)
            and not any(k in ln for ln in guest(log) for k in KERNEL_LINES)
            and "RELK debug-syscall: what the kernel prints for the probe byte is between the brackets: []" in lines
            and any("UnknownSyscall" in ln and "Syscall: fffffffffffffff7" in ln for ln in lines)
            and "RELK debug-syscall: kernel_accepts_debug_putchar=Some(false) expected_from_build_configuration=false" in lines)


def debug_console(log: str) -> bool:
    """On a debug kernel the kernel's own boot lines are there and it prints the probe byte."""
    lines = after_loader(log) or []
    return ("Bootstrapping kernel" in lines and "Booting all finished, dropped to user space" in lines
            and "RELK debug-syscall: what the kernel prints for the probe byte is between the brackets: [#]" in lines
            and "RELK debug-syscall: kernel_accepts_debug_putchar=Some(true) expected_from_build_configuration=true" in lines
            and not any("UnknownSyscall" in ln for ln in lines))


def details_ok(log: str) -> bool:
    """The observations behind the verdicts of a passing run, read from the log rather than from the verdict lines."""
    lines = after_loader(log) or []
    text = "\n".join(lines)
    pair = [m for ln in lines if (m := re.fullmatch(r"RELK   got report badge=0x[78] label=0x105 mr=\[([0-9a-f]+), ([0-9a-f]+), 0, 0\]", ln))]
    return ("RELK notification: signalled through badge 0x1337, wait returned badge 0x1337" in lines
            and "mr=[1111222233334444, f0ff0f055aaaa55, 0, 0]" in text and "mr=[1, a5a4cd33dc229b2a, 102, 0]" in text
            and re.search(r"got fault from worker 0x2: VmFault\(.*Addr: 60000abc, PrefetchFault: 0, FSR: 9200000[4-7] ", text) is not None
            and "RELK revoke: revoked the badged parent capability" in lines
            and "RELK revoke: second call reached the root task=false kernel answered InvalidCapability(2)=true parent still usable=true" in lines
            and "RELK page-permission: write through the second view refused=true frame still holds the pattern=true" in lines
            and re.search(r"got fault from worker 0x5: VmFault\(.*PrefetchFault: 0, FSR: 9200004[c-f] ", text) is not None
            and "RELK page-permission: read after unmapping the second view faults=true" in lines
            and len(pair) == 2 and all(int(m[2], 16) >= 1000 and int(m[1], 16) < 2_000_000_000 for m in pair))


def smp_ok(log: str) -> bool:
    lines = after_loader(log) or []
    guest_text = "\n".join(guest(log))
    seen = [m[1] for ln in lines if (m := re.fullmatch(r"RELK smp: core (\d): worker progress seen after Some\(\d+\) spins of the root task \(None: never\), final report received=true", ln))]
    return (all(f"Core {c} is up with logic id {c}" in guest_text for c in (1, 2, 3)) and seen == ["1", "2", "3"]
            and "RELK smp: control on core 0: progress seen=None (expected None), counter after suspending it=0" in lines
            and "RELK smp: placing a thread on core 4 (one past the last): Err(Sel4(IllegalOperation))" in lines)


def verify_relk(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    try:
        _verify(res, check, h)
        check("Release-kernel evidence files are present and well-formed", True)
    except (OSError, KeyError, ValueError, IndexError, TypeError) as err:
        check(f"Release-kernel evidence files are present and well-formed (stopped at: {type(err).__name__})", False)


def _verify(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    rd = lambda rel: h.read(res, f"ReleaseKernel/{rel}")  # noqa: E731
    pre, post, tools, sums = rd("00-preflight.txt"), rd("07-post-checks.txt"), rd("01-tools.txt"), rd("04-sums.txt")
    pin = f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0"
    src = r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$"
    a = {m[2]: m[1] for m in re.finditer(src, pre)}
    b = {m[2]: m[1] for m in re.finditer(src, post)}
    check("Release-kernel tools and inputs: GCC 16.2.0, CMake 4.4.5, Ninja 1.13.2, the pinned nightly, the pinned clean seL4, clean seL4_tools, util_libs and rust-sel4 checkouts, QEMU 11.1.3; no change to the seL4 source, Cargo.toml or Cargo.lock; the scripts and the root task's sources are the repository files the preflight and post-run record name",
          "compiler: aarch64-elf-gcc (GCC) 16.2.0" in tools and "cmake: cmake version 4.4.5" in tools and "ninja: 1.13.2" in tools
          and "cpio: " in tools and re.search(r"(?m)^rustc: rustc \S+-nightly \(\S+ 2026-08-2\d\)$", tools) is not None and pin in tools
          and pin in pre and "QEMU emulator version 11.1.3" in pre
          and all(re.search(rf"(?m)^{re.escape(r)} HEAD: [0-9a-f]{{40}}; dirty files: 0$", pre) for r in ("tools/seL4", "projects/util_libs", "rust-sel4"))
          and "seL4 source tracked diff: 0 lines" in post and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post
          and set(a) == set(SOURCES) and a == b
          and all(hashlib.sha256(rb(HERE / rel)).hexdigest() == sha for rel, sha in a.items()))
    commands = rd("02-commands.txt")
    cmd = {n: section(commands, n) for n in NAMES}
    builds = {n: rd(f"03-build-{n}.txt") for n in NAMES}
    release = [n for n in NAMES if n.split("-")[0].endswith("R")]
    smp = [n for n in NAMES if n.startswith("K2")]
    check("Release-kernel builds: all eight exit 0 with no error line; exactly the K1R and K2R images are built with KernelDebugBuild=OFF and KernelPrinting=OFF, in both the kernel interface the root task is built against and the image; exactly the K2 and K2R images have 4 nodes and the smc device tree; only the two mutants name a mutation and only the two mismatched controls use a prebuilt root task",
          all(builds[n].startswith(f"## {n}: build exit 0") and not re.search(r"(?m)^(CMake )?Error|^FAILED|^error", builds[n]) for n in NAMES)
          and all(("-DKernelDebugBuild=OFF -DKernelPrinting=OFF" in cmd[n]) == (n in release) and ("-DRELK_RELEASE=1" in cmd[n]) == (n in release)
                  and ("-DRELK_RELEASE=0" in cmd[n]) == (n not in release) for n in NAMES)
          and all(("-DKernelMaxNumNodes=4" in cmd[n]) == (n in smp) == ("-DSMP=TRUE -DNUM_NODES=4" in cmd[n]) == ("-DQEMU_DTB=" in cmd[n]) for n in NAMES)
          and all("-DKernelArmHypervisorSupport=OFF" in cmd[n] and "-DKernelVerificationBuild=OFF" in cmd[n] for n in NAMES)
          and "mutant: skip-revoke," in cmd["K1R-skip-revoke"] and "mutant: rw-alias," in cmd["K2R-rw-alias"]
          and all(("mutant: none," in cmd[n]) == (n not in ("K1R-skip-revoke", "K2R-rw-alias")) for n in NAMES)
          and all(("prebuilt root task: none" in cmd[n]) == (n not in ("K1R-debug-root", "K1R-putchar-demo")) for n in NAMES))
    s = {m[1]: m[2] for m in re.finditer(r"(?m)^(\S+) ([0-9a-f]{64})$", sums)}
    recorded = {"K1": "A2a", "K2": "A2a", "K1R": "A2a-variants", "K2R": "A2a-variants"}
    empty = hashlib.sha256(b"").hexdigest()
    check("Release-kernel kernel identity: for every image the kernel configuration of the image equals the one its root task's interface was built from, and both it and the function table extracted from the image's preprocessed kernel equal (same SHA-256) the published configuration and function table of that ID in the A2a evidence (K1, K2) or the A2a-variants evidence (K1R, K2R)",
          all((want := hashlib.sha256(rb(res / f"{d}/gen_config-{i}.json")).hexdigest()) != empty and s.get(f"recorded-gen_config-{i}") == want
              and (table := hashlib.sha256(rb(res / f"{d}/functions-{i}.tsv")).hexdigest()) != empty and s.get(f"recorded-functions-{i}") == table
              for i, d in recorded.items())
          and all(s.get(f"gen_config-{n}") == s.get(f"prefix-gen_config-{n}") == s.get(f"recorded-gen_config-{n.split('-')[0]}")
                  and s.get(f"functions-{n}") == s.get(f"recorded-functions-{n.split('-')[0]}") for n in NAMES)
          and len({s.get(f"recorded-functions-{i}") for i in recorded}) == 4)
    check("Release-kernel images: the eight images are distinct; the two mismatched controls contain the root task built for K1 and the A1 rerun's demo root task (same SHA-256 as recorded there); the mutants' root tasks differ from the unmutated ones",
          len({s.get(f"image-{n}") for n in NAMES}) == 8 and None not in {s.get(f"image-{n}") for n in NAMES}
          and s.get("root-task-K1R-debug-root") == s.get("root-task-K1") != s.get("root-task-K1R")
          and s.get("root-task-K1R-putchar-demo") is not None and f"{s.get('root-task-K1R-putchar-demo')}  s1-root-task.elf" in h.read(res, "A1-rerun/04-sums-rerun1.txt")
          and s.get("root-task-K1R-skip-revoke") != s.get("root-task-K1R") and s.get("root-task-K2R-rw-alias") != s.get("root-task-K2R"))
    dts = rd("05-k2-smc.dts")
    check("Release-kernel device tree: the tree given to the 4-node kernels has the smc PSCI method and four CPUs that enable by PSCI",
          'method = "smc"' in dts and len(re.findall(r"enable-method = \"psci\"", dts)) == 4)

    k1r = [rd(f"10-boot-K1R-{n}.txt") for n in (1, 2, 3)]
    k2r = [rd(f"11-boot-K2R-{n}.txt") for n in (1, 2, 3)]
    check("Release-kernel K1R (three of three boots, `-machine virt,secure=off,gic-version=2`, 1 vCPU, TCG): the root task reports a kernel without printing and without the debug build, passes all seven tests in order and ends with RELK_PASS; the observations behind the verdicts are in the log",
          all(launched(x, "K1R", 1, False, "RELK_PASS", True) and run_ok(x, printing=False, nodes=1, mutant="none", failing=()) and details_ok(x) for x in k1r))
    check("Release-kernel K2R (three of three boots, `-machine virt,secure=off,gic-version=2,virtualization=on`, 4 vCPUs, TCG): as K1R with four nodes and the eighth test: a worker on each of cores 1 to 3 makes progress while the root task spins, the same worker on core 0 makes none, and core 4 is refused",
          all(launched(x, "K2R", 4, True, "RELK_PASS", True) and run_ok(x, printing=False, nodes=4, mutant="none", failing=()) and details_ok(x) and smp_ok(x) for x in k2r))
    check("Release-kernel console: in all six release boots every non-empty console line after the elfloader's last line is the root task's (it starts with RELK), no kernel boot line or kernel message appears, the kernel prints nothing for the probe byte, and the probe's system call (number -9) is answered with an unknown-syscall fault",
          all(release_console(x) for x in k1r + k2r))
    d1, d2 = rd("12-control-K1-debug.txt"), rd("13-control-K2-debug.txt")
    check("Release-kernel debug controls: the same root task built for and run on the debug kernels K1 and K2 passes the same tests, and there the kernel's boot lines are on the console, the kernel prints the probe byte and the system call returns: so the probe tells a printing kernel from a non-printing one",
          launched(d1, "K1", 1, False, "RELK_PASS", True) and run_ok(d1, printing=True, nodes=1, mutant="none", failing=()) and debug_console(d1)
          and launched(d2, "K2", 4, True, "RELK_PASS", True) and run_ok(d2, printing=True, nodes=4, mutant="none", failing=()) and debug_console(d2) and smp_ok(d2))
    m1, m2 = rd("20-mutant-K1R-skip-revoke.txt"), rd("21-mutant-K2R-rw-alias.txt")
    check("Release-kernel mutants: with the revocation left out, K1R fails exactly the revocation test (the second call reaches the root task); with the second view mapped writable, K2R fails exactly the page-permission test (the write is not refused and the frame changes); both end with RELK_FAIL, so a failing test is visible on a kernel without debug output",
          launched(m1, "K1R-skip-revoke", 1, False, "RELK_FAIL", True) and run_ok(m1, printing=False, nodes=1, mutant="skip-revoke", failing=("revoke-badged-copy",))
          and "RELK revoke: second call reached the root task=true kernel answered InvalidCapability(2)=false parent still usable=true" in m1
          and launched(m2, "K2R-rw-alias", 4, True, "RELK_FAIL", True) and run_ok(m2, printing=False, nodes=4, mutant="rw-alias", failing=("page-permission-and-unmap",))
          and "RELK page-permission: write through the second view refused=false frame still holds the pattern=false" in m2)
    n1, n2 = rd("22-neg-K1R-with-debug-built-root-task.txt"), rd("23-neg-K1R-with-debugputchar-demo.txt")
    demo = after_loader(n2)
    check("Release-kernel mismatched pairings: the root task built for the debug kernel K1, run on K1R, fails exactly the debug-syscall test (it expects the call to be accepted and the kernel refuses it); the demo root task that prints only through seL4_DebugPutChar, run on K1R, leaves the console empty after the loader and its marker is never seen",
          launched(n1, "K1R-debug-root", 1, False, "RELK_FAIL", True) and run_ok(n1, printing=True, nodes=1, mutant="none", failing=("debug-syscall",))
          and "RELK debug-syscall: kernel_accepts_debug_putchar=Some(false) expected_from_build_configuration=true" in n1
          and launched(n2, "K1R-putchar-demo", 1, False, "TEST_PASS", False) and demo == [] and "TEST_PASS\n" not in "\n".join(guest(n2)) + "\n")


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    def r(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"ReleaseKernel/{path}", fn)

    return [
        ("a K1R boot has a failing test", r("10-boot-K1R-2.txt", lambda t: t.replace("RELK test=ipc-call-reply result=PASS", "RELK test=ipc-call-reply result=FAIL", 1)), "Release-kernel K1R"),
        ("a K1R boot lacks a test", r("10-boot-K1R-1.txt", lambda t: t.replace("RELK test=timer-preemption result=PASS\n", "", 1)), "Release-kernel K1R"),
        ("a K1R boot was launched from the debug image", r("10-boot-K1R-3.txt", lambda t: t.replace("/relk-build/K1R/", "/relk-build/K1/", 1)), "Release-kernel K1R"),
        ("a K1R boot's revocation observation says the call arrived", r("10-boot-K1R-1.txt", lambda t: t.replace("reached the root task=false", "reached the root task=true", 1)), "Release-kernel K1R"),
        ("a K1R boot's preemption worker ran to its iteration limit", r("10-boot-K1R-3.txt", lambda t: re.sub(r"(RELK   got report badge=0x7 label=0x105 mr=\[)[0-9a-f]+", r"\g<1>77359400", t, count=1)), "Release-kernel K1R"),
        ("a K1R boot reports an out-of-range register access", r("10-boot-K1R-1.txt", lambda t: t.replace("mmio_range_errors=0", "mmio_range_errors=1", 1)), "Release-kernel K1R"),
        ("a K2R boot shows no progress on core 2", r("11-boot-K2R-2.txt", lambda t: re.sub(r"(RELK smp: core 2: worker progress seen after )Some\(\d+\)", r"\g<1>None", t, count=1)), "Release-kernel K2R"),
        ("a K2R boot's control worker ran", r("11-boot-K2R-1.txt", lambda t: t.replace("counter after suspending it=0", "counter after suspending it=7", 1)), "Release-kernel K2R"),
        ("a K2R boot ran with one vCPU", r("11-boot-K2R-3.txt", lambda t: t.replace(" -smp 4 ", " -smp 1 ", 1)), "Release-kernel K2R"),
        ("a release boot has a kernel line on the console", r("10-boot-K1R-2.txt", lambda t: t.replace("RELK start:", "Bootstrapping kernel\nRELK start:", 1)), "Release-kernel console"),
        ("a release kernel printed the probe byte", r("11-boot-K2R-2.txt", lambda t: t.replace("between the brackets: []", "between the brackets: [#]", 1)), "Release-kernel console"),
        ("the debug control shows the system call refused", r("12-control-K1-debug.txt", lambda t: t.replace("between the brackets: [#]", "between the brackets: []", 1)), "Release-kernel debug controls"),
        ("the revocation mutant passes", r("20-mutant-K1R-skip-revoke.txt", lambda t: t.replace("RELK test=revoke-badged-copy result=FAIL", "RELK test=revoke-badged-copy result=PASS", 1)), "Release-kernel mutants"),
        ("the demo control prints its marker", r("23-neg-K1R-with-debugputchar-demo.txt", lambda t: t.replace(LOADER_LAST, LOADER_LAST + "\nTEST_PASS", 1)), "Release-kernel mismatched pairings"),
        ("K2R's function table is not the recorded one", r("04-sums.txt", lambda t: re.sub(r"(?m)^(functions-K2R )([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "Release-kernel kernel identity"),
        ("K1R's kernel configuration is not the recorded one", r("04-sums.txt", lambda t: re.sub(r"(?m)^(gen_config-K1R )([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "Release-kernel kernel identity"),
        ("K1R's command lacks a release option", r("02-commands.txt", lambda t: t.replace("-DKernelDebugBuild=OFF -DKernelPrinting=OFF", "-DKernelDebugBuild=OFF", 1)), "Release-kernel builds"),
        ("a root-task source hash differs between the records", r("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )([0-9a-f])(?=[0-9a-f]{63}  crates/e2-root-task/src/pl011.rs)", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "Release-kernel tools and inputs"),
    ]
