"""A5 step 1 checks for verify-evidence.py: QEMU's SMMUv3, enabled and programmed by a seL4 root task, translates the DMA of one
configured `edu` stream through a stage-1 table and refuses everything else. Spike code, stdlib only. Loaded by
verify-evidence.py by file path; `h` has `read`, `E1_PINS`.

What the checks establish, for the E1-H kernel and for K2R, three boots each: the experiment's eleven tests pass; the log holds
the observations behind each verdict (page contents and the records of the SMMU's event queue, per test); QEMU's own trace of
its SMMU model agrees with them (every translation it reports is stage 1, for the configured stream, from one of the two mapped
I/O virtual addresses to the physical address the root task mapped it to; the events it reports are the ones the root task
read; it never reports a global bypass or abort decision); and each of five mutants fails exactly the test it breaks.
They establish **what one emulated SMMU model does for one device model**: not an A5 outcome, nothing about hardware, and
nothing about confinement against software (the root task holds every capability). QEMU's trace is not independent of the
model it traces.
"""
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RS = "crates/e2-root-task/src"
SOURCES = ("build-a5-e1h.sh", "build-relk.sh", "run-a5-step1-evidence.sh", "boot-a5.py", "a2a-compare.py", f"{RS}/bin/a5_step1_root_task.rs",
           f"{RS}/a5_step1_tests.rs", f"{RS}/smmuv3.rs", f"{RS}/edu.rs", f"{RS}/pl011.rs", f"{RS}/a5_mmio.rs", f"{RS}/object_allocator.rs")
MUTANTS = {"skip-tlbi": "unmap-effective-after-invalidation", "skip-cfgi": "stream-removal-effective-after-invalidation",
           "map-unmapped": "unmapped-iova-denied", "rw-readonly": "read-only-mapping-enforced", "second-stream-configured": "other-stream-denied"}
TESTS = ["smmu-enabled", "unconfigured-stream-denied", "mapped-iova-translated", "unmapped-iova-denied", "physical-address-denied",
         "unmapped-memory-not-readable", "read-only-mapping-enforced", "other-stream-denied", "unmap-effective-after-invalidation",
         "stream-removal-effective-after-invalidation", "global-state-unchanged"]
MACHINE = "virt,secure=off,gic-version=2,virtualization=on,iommu=smmuv3,highmem=off"
DEVICES = " -device edu,dma_mask=0xffffffffff -device edu,dma_mask=0xffffffffff -trace "
IOVA_RW, IOVA_RO, IOVA_UNMAPPED = 0x1_0000_0000, 0x1_0000_1000, 0x1_0000_2000
BAD_STE, F_TRANSLATION, F_PERMISSION = 0x04, 0x10, 0x13
ANSI = re.compile(r"\x1b\[[0-9;]*m")
EVENT = re.compile(r"A5S1   events after (.+?): (?:none|n=(\d+) type=(0x[0-9a-f]+) sid=(0x[0-9a-f]+) write=(true|false) page=(0x[0-9a-f]+))")
SUCCESS = re.compile(r"smmuv3_translate_success \S+ sid=(0x[0-9a-f]+) iova=(0x[0-9a-f]+) translated=(0x[0-9a-f]+) perm=(0x[0-9a-f]+) stage=(\d)")


def rb(path: Path) -> bytes:
    return path.read_bytes() if path.is_file() else b""


def body(log: str) -> list[str]:
    """The run's lines between boot-a5.py's command line and its footer, without colour codes."""
    lines = ANSI.sub("", log.replace("\r", "")).split("\n")
    if lines and lines[0].startswith("+ "):
        lines = lines[1:]
    end = next((i for i, ln in enumerate(lines) if ln.startswith("[boot-a5]")), len(lines))
    return lines[:end]


def launched(log: str, smp: int, image_suffix: str, marker: str) -> bool:
    first = log.replace("\r", "").split("\n", 1)[0]
    return (first.startswith("+ ") and f" -machine {MACHINE} -accel tcg -cpu cortex-a57 -smp {smp} -m size=1024M " in first
            and f"{image_suffix}{DEVICES}" in first and f"[boot-a5] marker '{marker}' SEEN after" in log and f"(machine={MACHINE})" in log)


def verdicts(lines: list[str]) -> list[tuple[str, str]]:
    return [(m[1], m[2]) for ln in lines if (m := re.fullmatch(r"A5S1 test=(\S+) result=(PASS|FAIL)", ln))]


def events(lines: list[str]) -> list[tuple[str, tuple[int, int, int, bool, int] | None]]:
    """Every event line of the root task, in order: (what it followed, None or (count, type, stream, write, page))."""
    out = []
    for ln in lines:
        m = EVENT.fullmatch(ln)
        if m:
            out.append((m[1], None if m[2] is None else (int(m[2]), int(m[3], 16), int(m[4], 16), m[5] == "true", int(m[6], 16))))
    return out


def configured(lines: list[str]) -> tuple[int, int, int] | None:
    """The physical addresses of pages P, R and Q, from the root task's configuration line."""
    m = next((m for ln in lines if (m := re.fullmatch(
        r"A5S1 configured: stream 0x10 stage 1, asid 7; 0x100000000 -> P at physical (0x[0-9a-f]+) read-write; 0x100001000 -> R at physical (0x[0-9a-f]+) read-only; "
        r"0x100002000 unmapped; guard Q at physical (0x[0-9a-f]+)", ln))), None)
    return None if m is None else (int(m[1], 16), int(m[2], 16), int(m[3], 16))


def expected_events(p: int, q: int) -> list[tuple[int, int, int, bool, int] | None]:
    """What the event queue must hold after each transfer of an unmutated run, in order (None: nothing)."""
    return [(16, BAD_STE, 0x10, True, 0), (16, BAD_STE, 0x10, True, 0), None, (16, F_TRANSLATION, 0x10, True, IOVA_UNMAPPED),
            (16, F_TRANSLATION, 0x10, True, q), (16, F_TRANSLATION, 0x10, False, q), None, None, (16, F_PERMISSION, 0x10, True, IOVA_RO),
            (16, BAD_STE, 0x18, True, 0), None, None, (16, F_TRANSLATION, 0x10, True, IOVA_RW), None, None, (16, BAD_STE, 0x10, True, 0)]


OBSERVATIONS = [
    "A5S1 devices: configured stream sid=0x10, unconfigured stream sid=0x18",
    "A5S1 smmu before enabling [IDR0, IDR1, IDR5, CR0, CR0ACK, GBPA, GERROR^GERRORN] = [d44101b, 2730010, 74, 0, 0, 1000, 0]",
    "A5S1 smmu after enabling  [IDR0, IDR1, IDR5, CR0, CR0ACK, GBPA, GERROR^GERRORN] = [d44101b, 2730010, 74, d, d, 1000, 0]",
    "A5S1 unconfigured: transfers finished=true page P intact=16/16",
    "A5S1 unmapped: transfer finished=true guard page Q intact=16/16 page P still zero=16/16",
    "A5S1 physical: transfer finished=true guard page Q intact=16/16",
    "A5S1 read-only: read through it delivered=16/16 write finished=true page R unchanged=16/16",
    "A5S1 other-stream: transfer finished=true page P intact=16/16; the configured device's round trip=16/16",
    "A5S1 unmap: entry cleared, no invalidation yet: the write still landed=16/16 words",
    "A5S1 unmap: after the invalidation: transfer finished=true words landed=0/16 page P still zero=16/16",
    "A5S1 stream-removal: restored mapping round trip=16/16; entry cleared, no invalidation yet: the write still landed=16/16 words",
    "A5S1 stream-removal: after the invalidation: transfer finished=true words landed=0/16 page P still zero=16/16",
    "A5S1 global: CR0=0xd CR0ACK=0xd GBPA=0x1000 (abort bit set=false) GERROR^GERRORN=0x0",
]


def in_order(lines: list[str], wanted: list[str]) -> bool:
    pos = 0
    for want in wanted:
        nxt = next((i for i in range(pos, len(lines)) if lines[i] == want), None)
        if nxt is None:
            return False
        pos = nxt + 1
    return True


def trace_ok(lines: list[str], p: int, r: int, total_events: dict[tuple[int, int], int], *, tlbi: bool, cfgi_ste: int, successes: tuple[int, int] | None) -> bool:
    """QEMU's trace of its SMMU model, compared with what the root task printed."""
    tr = [ln for ln in lines if ln.startswith("smmu")]
    ok = [SUCCESS.fullmatch(ln.strip()) for ln in tr if ln.startswith("smmuv3_translate_")]
    if not ok or any(m is None for m in ok):  # a translate_ line that is not a success (bypass, disable, abort) fails here
        return False
    seen = [(int(m[1], 16), int(m[2], 16), int(m[3], 16), int(m[4], 16), int(m[5])) for m in ok]
    names = {"SMMU_EVT_C_BAD_STE": BAD_STE, "SMMU_EVT_F_TRANSLATION": F_TRANSLATION, "SMMU_EVT_F_PERMISSION": F_PERMISSION}
    reported: dict[tuple[int, int], int] = {}
    for ln in tr:
        m = re.fullmatch(r"smmuv3_propagate_event (\S+) sid=(0x[0-9a-f]+)\s*", ln)
        if m:
            if m[1] not in names:
                return False
            key = (names[m[1]], int(m[2], 16))
            reported[key] = reported.get(key, 0) + 1
    inval = [ln for ln in tr if ln.startswith("smmuv3_range_inval")]
    cleared = next((i for i, ln in enumerate(lines) if ln.startswith("A5S1 unmap: entry cleared")), -1)
    judged = next((i for i, ln in enumerate(lines) if ln.startswith("A5S1 unmap: after the invalidation")), -1)
    at = next((i for i, ln in enumerate(lines) if ln.startswith("smmuv3_range_inval")), -1)
    return (all(s in ((0x10, IOVA_RW, p, 0x3, 1), (0x10, IOVA_RO, r, 0x1, 1)) for s in seen)
            and (successes is None or (sum(s[1] == IOVA_RW for s in seen), sum(s[1] == IOVA_RO for s in seen)) == successes)
            and reported == total_events
            and sum(ln.startswith("smmuv3_cmdq_cfgi_ste streamid= 0x10") for ln in tr) == cfgi_ste
            and sum(ln.startswith("smmuv3_cmdq_cfgi_cd sid=0x10") for ln in tr) == 1
            and sum(ln.startswith("smmuv3_cmdq_cfgi_ste_range start=0x0 - end=0xffffffff") for ln in tr) == 1
            and sum(ln.startswith("smmuv3_cmdq_tlbi_nsnh") for ln in tr) == 1
            and ((len(inval) == 1 and inval[0].startswith("smmuv3_range_inval vmid=0 asid=7 addr=0x100000000 tg=0 num_pages=0x1 ttl=0 leaf=1 stage=1")
                  and 0 <= cleared < at < judged) if tlbi else not inval))


def totals(evs: list[tuple[str, tuple[int, int, int, bool, int] | None]]) -> dict[tuple[int, int], int]:
    out: dict[tuple[int, int], int] = {}
    for _, e in evs:
        if e is not None:
            out[(e[1], e[2])] = out.get((e[1], e[2]), 0) + e[0]
    return out


def guest_ok(log: str, header: str) -> bool:
    """One unmutated run as the root task reports it: verdicts, the observations behind them, the event queue per transfer."""
    lines = body(log)
    a5 = [ln for ln in lines if ln.startswith("A5S1")]
    pages = configured(a5)
    if pages is None:
        return False
    p, r, q = pages
    return (header in a5 and verdicts(a5) == [(t, "PASS") for t in TESTS] and a5[-1] == "A5S1_PASS"
            and a5[-2] == "A5S1 summary passed=11 failed=0 console_bytes_dropped=0 mmio_range_errors=0" and in_order(a5, OBSERVATIONS)
            and len({p, r, q}) == 3 and all(x >= 0x4000_0000 and x % 4096 == 0 for x in (p, r, q))
            and f"A5S1 mapped: 16/16 words made the round trip; the address used (0x100000000) differs from P's physical address ({p:#x})=true" in a5
            and any(ln.startswith("A5S1 no-read: transfer finished=true words of Q's content that reached P=0/16 ") for ln in a5)
            and [e for _, e in events(a5)] == expected_events(p, q))


def trace_agrees(log: str) -> bool:
    """One unmutated run: QEMU's trace of its SMMU model against the addresses and event records the root task printed."""
    lines = body(log)
    a5 = [ln for ln in lines if ln.startswith("A5S1")]
    pages = configured(a5)
    return pages is not None and trace_ok(lines, pages[0], pages[1], totals(events(a5)), tlbi=True, cfgi_ste=2, successes=(11, 1))


def mutant_ok(log: str, mutant: str) -> bool:
    lines = body(log)
    a5 = [ln for ln in lines if ln.startswith("A5S1")]
    pages = configured(a5)
    if pages is None:
        return False
    p, r, _q = pages
    want = [(t, "FAIL" if t == MUTANTS[mutant] else "PASS") for t in TESTS]
    telling = {
        "skip-tlbi": ["A5S1 unmap: MUTANT skip-tlbi, CMD_TLBI_NH_VA is not issued", "A5S1 unmap: after the invalidation: transfer finished=true words landed=16/16 page P still zero=0/16"],
        "skip-cfgi": ["A5S1 stream-removal: MUTANT skip-cfgi, CMD_CFGI_STE is not issued", "A5S1 stream-removal: after the invalidation: transfer finished=true words landed=16/16 page P still zero=0/16"],
        "map-unmapped": ["A5S1 unmapped: transfer finished=true guard page Q intact=0/16 page P still zero=16/16"],
        "rw-readonly": ["A5S1 read-only: read through it delivered=16/16 write finished=true page R unchanged=0/16"],
        "second-stream-configured": ["A5S1 configure: MUTANT second-stream-configured, stream 0x18 gets the same address space",
                                     "A5S1 other-stream: transfer finished=true page P intact=0/16; the configured device's round trip=16/16"],
    }[mutant]
    # The trace must show the missing command missing; translations to the guard page appear only where the mutant maps it.
    tr_ok = {
        "skip-tlbi": lambda: trace_ok(lines, p, r, totals(events(a5)), tlbi=False, cfgi_ste=2, successes=None),
        "skip-cfgi": lambda: trace_ok(lines, p, r, totals(events(a5)), tlbi=True, cfgi_ste=1, successes=None),
        "map-unmapped": lambda: any(f"iova=0x100002000 translated={_q:#x} perm=0x3 stage=1" in ln for ln in lines),
        "rw-readonly": lambda: any(f"iova=0x100001000 translated={r:#x} perm=0x3 stage=1" in ln for ln in lines),
        "second-stream-configured": lambda: any(f"sid=0x18 iova=0x100000000 translated={p:#x} perm=0x3 stage=1" in ln for ln in lines),
    }[mutant]()
    return (f"A5S1 start: built-for PRINTING=true MAX_NUM_NODES=1 ARM_HYPERVISOR_SUPPORT=true mutant={mutant}" in a5 and verdicts(a5) == want
            and a5[-1] == "A5S1_FAIL" and a5[-2] == "A5S1 summary passed=10 failed=1 console_bytes_dropped=0 mmio_range_errors=0" and in_order(a5, telling) and tr_ok)


def verify_a5_step1(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    try:
        _verify(res, check, h)
        check("A5 step 1 evidence files are present and well-formed", True)
    except (OSError, KeyError, ValueError, IndexError, TypeError) as err:
        check(f"A5 step 1 evidence files are present and well-formed (stopped at: {type(err).__name__})", False)


def _verify(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    rd = lambda rel: h.read(res, f"A5-step1/{rel}")  # noqa: E731
    pre, post, sums = rd("00-preflight.txt"), rd("07-post-checks.txt"), rd("02-sums.txt")
    pin = f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0"
    src = r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$"
    a = {m[2]: m[1] for m in re.finditer(src, pre)}
    b = {m[2]: m[1] for m in re.finditer(src, post)}
    e3 = h.read(res, "E3/04-post-checks.txt")
    kernel, loader = re.search(r"(?m)^e3 ([0-9a-f]{64})  kernel.elf$", e3), re.search(r"(?m)^e3 ([0-9a-f]{64})  sel4-kernel-loader.elf$", e3)
    check("A5 step 1 inputs: the pinned clean seL4, clean seL4_tools, util_libs and rust-sel4 checkouts, QEMU 11.1.3; no change to the seL4 source, Cargo.toml or Cargo.lock; the E1-H kernel and loader are those of the E3 evidence build (same SHA-256); the scripts and sources are the repository files the preflight and post-run record name",
          pin in pre and "QEMU emulator version 11.1.3" in pre
          and all(re.search(rf"(?m)^{re.escape(r)} HEAD: [0-9a-f]{{40}}; dirty files: 0$", pre) for r in ("tools/seL4", "projects/util_libs", "rust-sel4"))
          and "seL4 source tracked diff: 0 lines" in post and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post
          and kernel is not None and loader is not None and f"e3 kernel.elf sha256: {kernel[1]}" in pre and f"e3 sel4-kernel-loader.elf sha256: {loader[1]}" in pre
          and set(a) == set(SOURCES) and a == b
          and all(hashlib.sha256(rb(HERE / rel)).hexdigest() == sha for rel, sha in a.items()))
    names = ["e1h-main"] + [f"e1h-{m}" for m in MUTANTS] + ["k2r-main"]
    n_images = len(names)
    builds = {n: rd(f"01-build-{n}.txt") for n in names}
    s = {m[1]: m[2] for m in re.finditer(r"(?m)^(\S+) ([0-9a-f]{64})$", sums)}
    empty = hashlib.sha256(b"").hexdigest()
    cfg, table = hashlib.sha256(rb(res / "A2a-variants/gen_config-K2R.json")).hexdigest(), hashlib.sha256(rb(res / "A2a-variants/functions-K2R.tsv")).hexdigest()
    check("A5 step 1 builds: all seven exit 0 with no error line and give seven distinct images; the K2R image is built with the release options, 4 nodes and the experiment's root task, and its kernel configuration and function table equal (same SHA-256) the published K2R of the A2a-variants evidence",
          all(builds[n].startswith(f"## {n}: build exit 0") and not re.search(r"(?m)^(CMake )?Error|^FAILED|^error", builds[n]) for n in names)
          and len({s.get(f"image-{n}") for n in names}) == n_images and None not in {s.get(f"image-{n}") for n in names}
          and "root task: a5_step1_root_task, mutant: none," in builds["k2r-main"] and "-DKernelDebugBuild=OFF -DKernelPrinting=OFF" in builds["k2r-main"]
          and "-DKernelMaxNumNodes=4" in builds["k2r-main"] and "-DKernelArmHypervisorSupport=OFF" in builds["k2r-main"]
          and cfg != empty and table != empty and s.get("gen_config-k2r") == s.get("prefix-gen_config-k2r") == s.get("recorded-gen_config-K2R") == cfg
          and s.get("functions-k2r") == s.get("recorded-functions-K2R") == table)
    e1h = [rd(f"10-e1h-main-{n}.txt") for n in (1, 2, 3)]
    k2r = [rd(f"11-k2r-main-{n}.txt") for n in (1, 2, 3)]
    muts = {m: rd(f"20-mutant-e1h-{m}.txt") for m in MUTANTS}
    k2r_image = "/external/relk-build/K2R-a5s1/build/images/rust-root-task-image-arm-qemu-arm-virt"
    check("A5 step 1 launches: every run's recorded QEMU command line names `iommu=smmuv3,highmem=off`, two edu devices with a 40-bit DMA mask, the trace of the SMMU model, the vCPU count (1 for E1-H, 4 for K2R) and the image its file name says",
          all(launched(x, 1, "/external/a5-step1-build/main/image.elf", "A5S1_PASS") for x in e1h)
          and all(launched(x, 4, k2r_image, "A5S1_PASS") for x in k2r)
          and all(launched(x, 1, f"/external/a5-step1-build/{m}/image.elf", "A5S1_FAIL") for m, x in muts.items()))
    check("A5 step 1 on the E1-H kernel (three of three boots): with the SMMU enabled, the unconfigured stream reaches nothing; after configuration a transfer through the mapped I/O virtual address reaches page P in both directions although that address is not P's physical address; writes to an unmapped I/O virtual address and to the guard page's physical address change nothing and a read of the guard page delivers none of its content, each with 16 translation-fault records naming the stream, the direction and the page; the read-only mapping can be read and not written (16 permission-fault records); the second device, whose stream is not configured, reaches nothing while the first still does; a cleared table entry and a cleared stream entry stop transfers once the invalidation command and its sync have completed, and not before; the SMMU's global state never changes",
          all(guest_ok(x, "A5S1 start: built-for PRINTING=true MAX_NUM_NODES=1 ARM_HYPERVISOR_SUPPORT=true mutant=none") for x in e1h))
    check("A5 step 1 on K2R (three of three boots, non-hypervisor, 4 vCPUs, release kernel, seL4's elfloader): the same eleven tests pass with the same observations, and every console line after the loader's last is the root task's or QEMU's trace (the kernel prints nothing)",
          all(guest_ok(x, "A5S1 start: built-for PRINTING=false MAX_NUM_NODES=4 ARM_HYPERVISOR_SUPPORT=false mutant=none")
              and all(f"Core {c} is up with logic id {c}" in x for c in (1, 2, 3)) and release_console(x) for x in k2r))
    check("A5 step 1 agreement with QEMU's trace (all six boots): every translation the SMMU model reports is stage 1 for stream 0x10, from the read-write address to page P (11 times) or from the read-only address to page R (once, read-only), and never a global bypass, disable or abort decision; the events it reports are, by type and stream, exactly the records the root task read from the event queue (64 translation faults, 16 permission faults, 48 and 16 invalid-stream-entry events); it reports one page invalidation (asid 7, the read-write address) between the clearing of the entry and the refused transfer, two stream-entry invalidations and one context invalidation",
          all(trace_agrees(x) for x in e1h + k2r))
    check("A5 step 1 mutants (E1-H, one boot each): leaving out CMD_TLBI_NH_VA lets the transfer land after the entry is cleared (and QEMU's trace shows no page invalidation); leaving out CMD_CFGI_STE lets it land after the stream entry is cleared (one stream-entry invalidation instead of two); mapping the 'unmapped' address to the guard page lets the write reach it; mapping the 'read-only' page writable lets the write change it; giving the second device's stream the first one's address space lets the second device's write reach page P (and the trace shows a translation for stream 0x18); each fails exactly its test and ends with A5S1_FAIL",
          all(mutant_ok(x, m) for m, x in muts.items()))


def release_console(log: str) -> bool:
    lines = body(log)
    at = next((i for i, ln in enumerate(lines) if ln.startswith("Enabling MMU and jumping to entry point...")), None)
    return at is not None and all(ln.startswith(("A5S1", "smmu")) for ln in lines[at + 1:] if ln.strip()) and "Bootstrapping kernel" not in log


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    def r(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"A5-step1/{path}", fn)

    e1h, k2r, tr = "A5 step 1 on the E1-H kernel", "A5 step 1 on K2R", "A5 step 1 agreement with QEMU's trace"
    return [
        ("an E1-H boot has a failing test", r("10-e1h-main-2.txt", lambda t: t.replace("A5S1 test=other-stream-denied result=PASS", "A5S1 test=other-stream-denied result=FAIL", 1)), e1h),
        ("an E1-H boot's guard page changed", r("10-e1h-main-1.txt", lambda t: t.replace("A5S1 physical: transfer finished=true guard page Q intact=16/16", "A5S1 physical: transfer finished=true guard page Q intact=0/16", 1)), e1h),
        ("an E1-H boot has no fault record for the unmapped write", r("10-e1h-main-3.txt", lambda t: re.sub(r"(events after a write to the unmapped address: )n=16 [^\n]*", r"\g<1>none", t, count=1)), e1h),
        ("an E1-H boot's fault record names another page", r("10-e1h-main-1.txt", lambda t: t.replace("write=true page=0x100002000", "write=true page=0x100003000", 1)), e1h),
        ("an E1-H boot's permission fault is recorded as a translation fault", r("10-e1h-main-2.txt", lambda t: t.replace("type=0x13 sid=0x10", "type=0x10 sid=0x10", 1)), e1h),
        ("an E1-H boot's second device is the configured stream", r("10-e1h-main-3.txt", lambda t: t.replace("type=0x04 sid=0x18", "type=0x04 sid=0x10", 1)), e1h),
        ("an E1-H boot shows no stale translation before the invalidation", r("10-e1h-main-1.txt", lambda t: t.replace("A5S1 unmap: entry cleared, no invalidation yet: the write still landed=16/16 words", "A5S1 unmap: entry cleared, no invalidation yet: the write still landed=0/16 words", 1)), e1h),
        ("an E1-H boot's trace has a global bypass decision", r("10-e1h-main-2.txt", lambda t: re.sub(r"(?m)^smmuv3_translate_success (\S+) (sid=0x10) (iova=0x100000000) [^\n]*$", r"smmuv3_translate_bypass \1 \2 \3 perm=0x3", t, count=1)), tr),
        ("an E1-H boot's trace translates to another physical page", r("10-e1h-main-3.txt", lambda t: re.sub(r"(iova=0x100000000 translated=0x[0-9a-f]+)a000", r"\g<1>b000", t, count=1)), tr),
        ("an E1-H boot's trace lacks the page invalidation", r("10-e1h-main-1.txt", lambda t: re.sub(r"(?m)^smmuv3_range_inval [^\n]*\n", "", t, count=1)), tr),
        ("an E1-H boot's trace reports fewer events than the root task read", r("10-e1h-main-2.txt", lambda t: re.sub(r"(?m)^smmuv3_propagate_event SMMU_EVT_F_PERMISSION [^\n]*\n", "", t, count=1)), tr),
        ("a K2R boot ran with one vCPU", r("11-k2r-main-1.txt", lambda t: t.replace(" -smp 4 ", " -smp 1 ", 1)), "A5 step 1 launches"),
        ("a K2R boot has a kernel line on the console", r("11-k2r-main-2.txt", lambda t: t.replace("A5S1 start:", "Bootstrapping kernel\nA5S1 start:", 1)), k2r),
        ("a K2R boot lacks a test", r("11-k2r-main-3.txt", lambda t: t.replace("A5S1 test=read-only-mapping-enforced result=PASS\n", "", 1)), k2r),
        ("the K2R kernel is not the recorded K2R", r("02-sums.txt", lambda t: re.sub(r"(?m)^(functions-k2r )([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "A5 step 1 builds"),
        ("the skip-tlbi mutant passes", r("20-mutant-e1h-skip-tlbi.txt", lambda t: t.replace("A5S1 test=unmap-effective-after-invalidation result=FAIL", "A5S1 test=unmap-effective-after-invalidation result=PASS", 1)), "A5 step 1 mutants"),
        ("the skip-cfgi mutant's trace has both stream invalidations", r("20-mutant-e1h-skip-cfgi.txt", lambda t: t.replace("smmuv3_cmdq_cfgi_cd sid=0x10", "smmuv3_cmdq_cfgi_ste streamid= 0x10\nsmmuv3_cmdq_cfgi_cd sid=0x10", 1)), "A5 step 1 mutants"),
        ("the second-stream mutant leaves page P intact", r("20-mutant-e1h-second-stream-configured.txt", lambda t: t.replace("page P intact=0/16", "page P intact=16/16", 1)), "A5 step 1 mutants"),
        ("an E1-H boot reports an out-of-range register access", r("10-e1h-main-1.txt", lambda t: t.replace("mmio_range_errors=0", "mmio_range_errors=2", 1)), e1h),
        ("a mutant was launched from the unmutated image", r("20-mutant-e1h-rw-readonly.txt", lambda t: t.replace("/a5-step1-build/rw-readonly/", "/a5-step1-build/main/", 1)), "A5 step 1 launches"),
        ("a source hash differs between the records", r("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )([0-9a-f])(?=[0-9a-f]{63}  crates/e2-root-task/src/smmuv3.rs)", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "A5 step 1 inputs"),
    ]
