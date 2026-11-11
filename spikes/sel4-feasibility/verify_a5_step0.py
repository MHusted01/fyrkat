"""A5 step 0 checks for verify-evidence.py: an environment and feasibility probe of QEMU's SMMUv3 and the `edu` device from a
seL4 root task. Spike code, stdlib only. Loaded by verify-evidence.py by file path; `h` has `read`, `E1_PINS`.

What the checks establish: the probe was built and run with the recorded tools, sources and kernel; the root task reached the SMMU
registers, found `edu` through the ECAM, and moved data between two RAM pages through the device's DMA engine under each global
SMMU state; QEMU's own trace shows the SMMU model translating `edu`'s accesses (stream id 0x10) and aborting them exactly while the
abort bit was set; and the controls fail as stated. They establish **nothing about DMA confinement**: the SMMU was never enabled and
no stream table was built. The trace is QEMU's, not an independent measurement.
"""
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCES = ("build-a5-probe.sh", "run-a5-step0-evidence.sh", "boot-a5.py", "crates/e2-root-task/src/bin/a5_probe_root_task.rs",
           "crates/e2-root-task/src/a5_mmio.rs", "crates/e2-root-task/src/object_allocator.rs")
SID = "sid=0x10"


def rb(path: Path) -> bytes:
    return path.read_bytes() if path.is_file() else b""


def lines(log: str) -> list[str]:
    """The probe's own lines and QEMU's SMMU translation events, in the order they were printed."""
    clean = re.sub(r"\x1b\[[0-9;]*m", "", log.replace("\r", ""))
    return [ln for ln in clean.split("\n") if ln.startswith(("A5P", "smmuv3_translate_"))]


def trace(ls: list[str]) -> list[str]:
    return [ln for ln in ls if ln.startswith("smmuv3_translate_")]


def roundtrips(ls: list[str]) -> list[str]:
    return [m[1] for ln in ls if (m := re.search(r"roundtrip state=\S+ .* -> (DATA MOVED|NOTHING MOVED|PARTIAL)$", ln))]


def iova(ln: str) -> int:
    return int(re.search(r"iova:(0x[0-9a-f]+)", ln)[1], 16)


def all_done(ls: list[str]) -> bool:
    """Every round trip of the run reports that both of the device's transfers finished (so "nothing moved" is not a timeout)."""
    flags = [m.groups() for ln in ls if (m := re.search(r"roundtrip state=\S+ dma1_done=(\w+) dma2_done=(\w+) ", ln))]
    return len(flags) == 3 and all(f == ("true", "true") for f in flags)


def launched(log: str, machine_extra: str, device: str, image: str) -> bool:
    """The run's QEMU command line (the first line, printed by boot-a5.py) and its footer name exactly this machine, device and image."""
    first = log.replace("\r", "").split("\n", 1)[0]
    machine = "virt,secure=off,gic-version=2,virtualization=on" + (f",{machine_extra}" if machine_extra else "")
    return (first.startswith("+ ") and f" -machine {machine} -accel tcg -cpu cortex-a57 -smp 1 -m size=1024M " in first
            and first.endswith(f"/external/a5-step0-build-{image}/image.elf -device {device} -trace smmuv3_translate_*")
            and f"(machine={machine})" in log)


def verify_a5(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    try:
        _verify(res, check, h)
        check("A5 step 0 evidence files are present and well-formed", True)
    except (OSError, KeyError, ValueError, IndexError, TypeError, RuntimeError, StopIteration) as err:
        check(f"A5 step 0 evidence files are present and well-formed (stopped at: {type(err).__name__})", False)


def _verify(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    rd = lambda rel: h.read(res, f"A5-step0/{rel}")  # noqa: E731
    pre, post = rd("00-preflight.txt"), rd("07-post-checks.txt")
    pin = f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0"
    src = r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$"
    a = {m[2]: m[1] for m in re.finditer(src, pre)}
    b = {m[2]: m[1] for m in re.finditer(src, post)}
    e3 = h.read(res, "E3/04-post-checks.txt")
    kernel, loader = re.search(r"(?m)^e3 ([0-9a-f]{64})  kernel.elf$", e3), re.search(r"(?m)^e3 ([0-9a-f]{64})  sel4-kernel-loader.elf$", e3)
    check("A5 step 0 inputs: the pinned clean seL4, QEMU 11.1.3, no change to the seL4 source, Cargo.toml or Cargo.lock; the kernel and loader are those of the E3 evidence build (same SHA-256); the probe sources and scripts are the repository files the preflight and post-run record name",
          pin in pre and "QEMU emulator version 11.1.3" in pre and "seL4 source tracked diff: 0 lines" in post
          and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post
          and kernel is not None and loader is not None and f"e3 kernel.elf sha256: {kernel[1]}" in pre and f"e3 sel4-kernel-loader.elf sha256: {loader[1]}" in pre
          and set(a) == set(SOURCES) and a == b
          and all(hashlib.sha256(rb(HERE / rel)).hexdigest() == sha for rel, sha in a.items()))
    low, high = rd("01-build-low.txt"), rd("01-build-high.txt")
    sums = rd("02-sums.txt")
    hashes = re.findall(r"(?m)^([0-9a-f]{64})  (a5_probe_root_task.elf|image.elf)$", sums)
    check("A5 step 0 builds: both probe builds (ECAM at 0x3f000000, and at 0x4010000000) exit 0 with no error, and produce distinct root tasks and images",
          low.startswith("## low: build exit 0") and high.startswith("## high: build exit 0") and not re.search(r"(?m)^error", low + high)
          and len(hashes) == 4 and len({x[0] for x in hashes}) == 4)
    off, on, kd = rd("03-qemu-highmem-off.dts"), rd("03-qemu-highmem-on.dts"), rd("04-kernel-dtb.txt")
    smmu_node = 'smmuv3@9050000 {' in off and "reg = <0x00 0x9050000 0x00 0x20000>;" in off and 'compatible = "arm,smmu-v3";' in off
    check("A5 step 0 device trees (generated by QEMU): the SMMUv3 is at 0x09050000 (0x20000 bytes) in both layouts with a requester-to-stream identity map; the ECAM is at 0x3f000000 with highmem=off and 0x4010000000 with highmem=on; the kernel's own built-in tree names no SMMU and no IOMMU and has the high ECAM",
          smmu_node and "smmuv3@9050000 {" in on and re.search(r"iommu-map = <0x00 0x[0-9a-f]+ 0x00 0x10000>;", off) is not None
          and "reg = <0x00 0x3f000000 0x00 0x1000000>;" in off and "reg = <0x40 0x10000000 0x00 0x10000000>;" in on
          and "smmu: 0" in kd and "iommu: 0" in kd and "pcie@: 1" in kd and "pcie node reg: reg = <0x40 0x10000000 0x00 0x10000000>;" in kd)

    WIDE, LOW_M, HIGH_M = "edu,dma_mask=0xffffffffff", "iommu=smmuv3,highmem=off", "iommu=smmuv3"
    runs = {f"10-primary-low-wide-{n}.txt": (LOW_M, WIDE, "low") for n in (1, 2, 3)} | {
        "11-low-default-mask.txt": (LOW_M, "edu", "low"), "12-high-wide.txt": (HIGH_M, WIDE, "high"),
        "13-high-default-mask.txt": (HIGH_M, "edu", "high"), "20-neg-no-smmu.txt": ("highmem=off", WIDE, "low"),
        "21-neg-high-probe-on-highmem-off.txt": (LOW_M, WIDE, "high"), "22-neg-low-probe-on-highmem-on.txt": (HIGH_M, WIDE, "low")}
    check("A5 step 0 launches: every run's recorded QEMU command line names the machine options, the edu device (wide or default DMA mask) and the probe image (low or high ECAM) that its file name says, with the SMMU translation trace on",
          all(launched(rd(name), *want) for name, want in runs.items()))
    primary = [lines(rd(f"10-primary-low-wide-{n}.txt")) for n in (1, 2, 3)]
    wanted = ["A5P start", "A5P untypeds total=52 device=27 ram=25", "A5P cover smmu 0x9050000: device untyped 0x9000000 + 0x1000000",
              "A5P cover ecam 0x3f000000: device untyped 0x20000000 + 0x20000000", "A5P smmu IDR0 = 0x0d44101b", "A5P smmu AIDR = 0x00000001",
              "A5P smmu CR0 = 0x00000000", "A5P smmu GBPA = 0x00001000",
              "A5P ecam 0x3f000000 00:00.0 vendor:device = 0x1b36:0x0008", "A5P ecam 0x3f000000 00:02.0 vendor:device = 0x1234:0x11e8",
              "A5P edu bar0 before=0x0 sizing_mask=0xfff00000 (size 0x100000) set=0x10000000 readback=0x10000000 command 0x0 -> 0x6",
              "A5P edu id=0x10000ed liveness 0xedcba987 (expect the complement of 0x12345678: 0xedcba987)", "A5P mmio range errors: 0", "A5P_DONE"]

    def has_all(ls: list[str]) -> bool:
        pos = 0
        for want in wanted:
            nxt = next((i for i in range(pos, len(ls)) if ls[i].startswith(want)), None)
            if nxt is None:
                return False
            pos = nxt + 1
        return True

    check("A5 step 0 reach (three of three boots, identical): the root task finds the SMMU registers and the ECAM in device untypeds, reads the identification registers of QEMU's SMMUv3 model (IDR0 0x0d44101b, AIDR 1, disabled at reset, GBPA 0x1000), finds edu at 00:02.0 through the ECAM, assigns its 1 MiB BAR0 at 0x10000000 and reads its identification and liveness registers",
          all(has_all(p) for p in primary) and primary[0] == primary[1] == primary[2])

    def abort_gating(ls: list[str]) -> bool:
        def at(needle: str) -> int:
            return next((i for i, ln in enumerate(ls) if needle in ln), -1)

        i_reset, i_on, i_state, i_off = at("roundtrip state=reset-default "), at("abort true"), at("roundtrip state=gbpa-abort "), at("abort false")
        i_cleared = at("roundtrip state=gbpa-abort-cleared ")
        if not 0 <= i_reset < i_on < i_state < i_off < i_cleared:
            return False
        tr = [(i, ln) for i, ln in enumerate(ls) if ln.startswith("smmuv3_translate_")]
        pages = {0x70003, 0x70004}  # the two RAM pages: one event per page in a bypassed transfer, 16 per page when aborted
        ok = lambda ln, kind: ln.startswith(f"smmuv3_translate_{kind}") and SID in ln and iova(ln) >> 12 in pages  # noqa: E731
        before = [ln for i, ln in tr if i < i_reset]
        inside = [ln for i, ln in tr if i_on < i < i_state]
        after = [ln for i, ln in tr if i_off < i < i_cleared]
        return (len(tr) == len(before) + len(inside) + len(after)
                and len(before) == 2 and {iova(ln) >> 12 for ln in before} == pages and all(ok(ln, "disable") for ln in before)
                and len(inside) == 32 and all(ok(ln, "abort") for ln in inside)
                and all(sum(iova(ln) >> 12 == page for ln in inside) == 16 for page in pages)
                and len(after) == 2 and {iova(ln) >> 12 for ln in after} == pages and all(ok(ln, "disable") for ln in after))

    check("A5 step 0 DMA traverses the SMMU path (three of three boots): with edu's DMA mask widened, the round trip RAM, edu buffer, RAM moves the data in the reset state, moves nothing while the SMMU's global abort bit is set, and moves it again once cleared; QEMU's trace shows the SMMU model seeing edu's accesses as stream id 0x10 at the pages' full physical addresses, as exactly 32 `translate_abort` events between the moment the bit is set and the report of that state, and as exactly two `translate_disable` events (one per page) in the reset state and two in the cleared state, with no other translation event; the device reports every transfer finished",
          all(roundtrips(p) == ["DATA MOVED", "NOTHING MOVED", "DATA MOVED"] and all_done(p) and abort_gating(p) for p in primary)
          and all("GBPA 0x1000 -> 0x101000 (abort true)" in " ".join(p) and "GBPA 0x101000 -> 0x1000 (abort false)" in " ".join(p) for p in primary))
    dm = lines(rd("11-low-default-mask.txt"))
    check("A5 step 0 DMA addressing constraint: with edu's default 28-bit DMA mask the same round trip moves nothing in any SMMU state, and the SMMU sees only clamped addresses below 0x10000000 (never the pages' physical addresses at 0x70003000): so with default settings edu cannot reach RAM above 256 MiB except through a translation",
          has_all(dm) and all_done(dm) and roundtrips(dm) == ["NOTHING MOVED"] * 3
          and len(trace(dm)) > 0 and all(iova(ln) < 0x1000_0000 and SID in ln for ln in trace(dm)))
    hw, hd = lines(rd("12-high-wide.txt")), lines(rd("13-high-default-mask.txt"))
    check("A5 step 0 the default machine layout (highmem=on, ECAM at 0x4010000000) gives the same results: wide mask DATA MOVED, NOTHING MOVED, DATA MOVED; default mask NOTHING MOVED in all three; edu found at 00:02.0",
          roundtrips(hw) == ["DATA MOVED", "NOTHING MOVED", "DATA MOVED"] and roundtrips(hd) == ["NOTHING MOVED"] * 3 and all_done(hw) and all_done(hd)
          and all("A5P ecam 0x4010000000 00:02.0 vendor:device = 0x1234:0x11e8" in " ".join(x) and x[-1] == "A5P_DONE" for x in (hw, hd)))
    n1, n2, n3 = (rd(f) for f in ("20-neg-no-smmu.txt", "21-neg-high-probe-on-highmem-off.txt", "22-neg-low-probe-on-highmem-on.txt"))
    def done(log: str) -> bool:
        return any(ln.startswith("A5P_DONE") for ln in lines(log))

    fault = "vm fault on data at address %s with status 0x92000010"
    check("A5 step 0 negative controls (hazards, recorded): without an SMMU in the machine the first read of its address is a fatal synchronous external abort of the root task (nothing reads as zero); a probe built for the wrong ECAM layout reads the SMMU fine and then takes the same abort at the ECAM; none reaches A5P_DONE",
          fault % "0x40000000" in n1 and "A5P smmu IDR0" not in n1 and not done(n1) and "A5P cover ecam 0x3f000000" in n1
          and "A5P smmu IDR0 = 0x0d44101b" in n2 and fault % "0x40001000" in n2 and not done(n2) and "A5P cover ecam 0x4010000000" in n2
          and "A5P smmu IDR0 = 0x0d44101b" in n3 and fault % "0x40001000" in n3 and not done(n3) and "A5P cover ecam 0x3f000000" in n3)


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    def r(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"A5-step0/{path}", fn)

    return [
        ("a primary run no longer moves data in the reset state", r("10-primary-low-wide-2.txt", lambda t: t.replace("state=reset-default dma1_done=true dma2_done=true words_copied=16/16 words_untouched=0/16 -> DATA MOVED", "state=reset-default dma1_done=true dma2_done=true words_copied=0/16 words_untouched=16/16 -> NOTHING MOVED", 1)), "A5 step 0 DMA traverses the SMMU path"),
        ("an abort event is recorded outside the abort window", r("10-primary-low-wide-1.txt", lambda t: re.sub(r"(?m)^(smmuv3_translate_disable [^\n]*iova:0x70003000[^\n]*)$", lambda m: m[1].replace("translate_disable", "translate_abort"), t, count=1)), "A5 step 0 DMA traverses the SMMU path"),
        ("the trace names another stream", r("10-primary-low-wide-3.txt", lambda t: t.replace("sid=0x10", "sid=0x08")), "A5 step 0 DMA traverses the SMMU path"),
        ("the SMMU's identification register differs", r("10-primary-low-wide-1.txt", lambda t: t.replace("IDR0 = 0x0d44101b", "IDR0 = 0x0d44101a", 1)), "A5 step 0 reach"),
        ("edu is not found at 00:02.0", r("10-primary-low-wide-2.txt", lambda t: t.replace("00:02.0 vendor:device = 0x1234:0x11e8", "00:02.0 vendor:device = 0xffff:0xffff", 1)), "A5 step 0 reach"),
        ("the default-mask run moves data", r("11-low-default-mask.txt", lambda t: t.replace("words_copied=0/16 words_untouched=16/16 -> NOTHING MOVED", "words_copied=16/16 words_untouched=0/16 -> DATA MOVED", 1)), "A5 step 0 DMA addressing constraint"),
        ("the high-layout wide run blocks in the reset state", r("12-high-wide.txt", lambda t: t.replace("-> DATA MOVED", "-> NOTHING MOVED", 1)), "A5 step 0 the default machine layout"),
        ("the no-SMMU control reads the SMMU", r("20-neg-no-smmu.txt", lambda t: t.replace("A5P cover ecam", "A5P smmu IDR0 = 0x0\nA5P cover ecam", 1)), "A5 step 0 negative controls"),
        ("the kernel's own tree names an SMMU", r("04-kernel-dtb.txt", lambda t: t.replace("smmu: 0", "smmu: 1", 1)), "A5 step 0 device trees"),
        ("the SMMU is recorded at another address", r("03-qemu-highmem-off.dts", lambda t: t.replace("smmuv3@9050000", "smmuv3@9060000"), ), "A5 step 0 device trees"),
        ("the no-SMMU control was launched with an SMMU", r("20-neg-no-smmu.txt", lambda t: t.replace("virtualization=on,highmem=off", "virtualization=on,iommu=smmuv3,highmem=off")), "A5 step 0 launches"),
        ("the default-mask run was launched with the wide mask", r("11-low-default-mask.txt", lambda t: t.replace("-device edu -trace", "-device edu,dma_mask=0xffffffffff -trace", 1)), "A5 step 0 launches"),
        ("a primary run was launched with the other image", r("10-primary-low-wide-1.txt", lambda t: t.replace("a5-step0-build-low/image.elf", "a5-step0-build-high/image.elf", 1)), "A5 step 0 launches"),
        ("a transfer in the abort state did not finish", r("10-primary-low-wide-2.txt", lambda t: t.replace("state=gbpa-abort dma1_done=true", "state=gbpa-abort dma1_done=false", 1)), "A5 step 0 DMA traverses the SMMU path"),
        ("the reset-state translation events are missing", r("10-primary-low-wide-3.txt", lambda t: re.sub(r"(?m)^smmuv3_translate_disable [^\n]*\n", "", t, count=2)), "A5 step 0 DMA traverses the SMMU path"),
        ("half of the abort events are missing", r("10-primary-low-wide-1.txt", lambda t: re.sub(r"(?m)^smmuv3_translate_abort [^\n]*\n", "", t, count=16)), "A5 step 0 DMA traverses the SMMU path"),
        ("the default-mask run does not reach A5P_DONE", r("11-low-default-mask.txt", lambda t: t.replace("A5P_DONE\n", "", 1)), "A5 step 0 DMA addressing constraint"),
        ("all abort events name one page", r("10-primary-low-wide-3.txt", lambda t: re.sub(r"(?m)^(smmuv3_translate_abort [^\n]*iova:0x7000)4", r"\g<1>3", t)), "A5 step 0 DMA traverses the SMMU path"),
        ("a run was launched with another memory size", r("12-high-wide.txt", lambda t: t.replace("-m size=1024M", "-m size=2048M", 1)), "A5 step 0 launches"),
        ("a primary run has no abort-set line", r("10-primary-low-wide-2.txt", lambda t: t.replace("(abort true)", "(abort ?)", 1)), "A5 step 0 DMA traverses the SMMU path"),
        ("a probe source hash differs between the records", r("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )([0-9a-f])(?=[0-9a-f]{63}  boot-a5.py)", lambda m: m[1] + ("1" if m[2] == "0" else "0"), t, count=1)), "A5 step 0 inputs"),
    ]
