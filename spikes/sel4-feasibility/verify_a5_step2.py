"""A5 step 2 checks for verify-evidence.py: the revoke-while-mapped experiment (results/A5-step2.md). Spike code, stdlib only.
Loaded by verify-evidence.py by file path; `h` has `read`, `E1_PINS`.

**These checks do not require any particular outcome.** They require that each run is valid (positive controls, set-up,
finished transfers), that every finding the root task printed is the one its own observation lines give by the rule fixed in
the design (REACHED: all 16 secret words read out, all 16 words overwritten, no event; REFUSED: none read, none overwritten,
16 translation-fault records for each transfer; anything else MIXED), that the three boots on each kernel agree, that
QEMU's trace is consistent with the outcome, and that the record states the outcomes the evidence shows (the line this
module computes must be in results/A5-step2.md). A run that stops in scenario C is accepted as such: A and B are judged
without it. One validity condition concerns the experiment's power: the mutant must change scenario B's outcome.

They establish **what one kernel build and one emulated SMMU model did in an arrangement in which one task plays every role**.
Not an A5 outcome, not a statement about hardware, and not a general security property.
"""
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RS = "crates/e2-root-task/src"
SOURCES = ("build-a5-e1h.sh", "build-relk.sh", "run-a5-step2-evidence.sh", "verify_a5_step2.py", "boot-a5.py", "a2a-compare.py", f"{RS}/bin/a5_step2_root_task.rs",
           f"{RS}/a5_step2_tests.rs", f"{RS}/smmuv3.rs", f"{RS}/edu.rs", f"{RS}/slots.rs", f"{RS}/pl011.rs", f"{RS}/a5_mmio.rs", f"{RS}/object_allocator.rs")
MUTANT = "teardown-without-invalidation"
MACHINE = "virt,secure=off,gic-version=2,virtualization=on,iommu=smmuv3,highmem=off"
DEVICES = " -device edu,dma_mask=0xffffffffff -device edu,dma_mask=0xffffffffff -trace "
ANSI = re.compile(r"\x1b\[[0-9;]*m")
HEX = r"0x[0-9a-f]+"
IOVA = "0x100000000"
READ_EV = "A5S2   events after the device's read of the mapping under test: "
WRITE_EV = "A5S2   events after the device's write to the mapping under test: "
FAULT = "n=16 type=0x10 sid=0x10 write={} page=" + IOVA
PROBE = re.compile(r"A5S2 ([AB]): secret words the device read out=(\d+)/16; victim words the device overwrote=(\d+)/16 \(victim still intact=(\d+)/16\); "
                   r"transfers through the mapping left no event=(true|false), only translation faults=(true|false); transfers through page O left no event=(true|false)")
TRUE = {"true": True, "false": False}


def rb(path: Path) -> bytes:
    return path.read_bytes() if path.is_file() else b""


def body(log: str) -> list[str]:
    lines = ANSI.sub("", log.replace("\r", "")).split("\n")
    if lines and lines[0].startswith("+ "):
        lines = lines[1:]
    end = next((i for i, ln in enumerate(lines) if ln.startswith("[boot-a5]")), len(lines))
    return lines[:end]


def launched(log: str, smp: int, image_suffix: str) -> bool:
    """The command line is the expected one; the marker may or may not have been seen (a stop in scenario C is an outcome)."""
    first = log.replace("\r", "").split("\n", 1)[0]
    return (first.startswith("+ ") and f" -machine {MACHINE} -accel tcg -cpu cortex-a57 -smp {smp} -m size=1024M " in first
            and f"{image_suffix}{DEVICES}" in first and "[boot-a5] marker 'A5S2_DONE' " in log and f"(machine={MACHINE})" in log)


def part(lines: list[str], start: str, end: str) -> list[str]:
    """The lines from the first that starts with START up to and including the first after it that starts with END."""
    a = next((i for i, ln in enumerate(lines) if ln.startswith(start)), None)
    if a is None:
        return []
    b = next((i for i in range(a, len(lines)) if lines[i].startswith(end)), None)
    return [] if b is None else lines[a:b + 1]


def probe_outcome(lines: list[str], scenario: str) -> str | None:
    """The outcome the design's rule gives for the scenario's observation and event lines, or None if they are missing or
    inconsistent with each other."""
    m = next((m for ln in lines if (m := PROBE.fullmatch(ln)) and m[1] == scenario), None)
    read = next((ln[len(READ_EV):] for ln in lines if ln.startswith(READ_EV)), None)
    write = next((ln[len(WRITE_EV):] for ln in lines if ln.startswith(WRITE_EV)), None)
    if m is None or read is None or write is None:
        return None
    leaked, overwritten, intact = int(m[2]), int(m[3]), int(m[4])
    quiet, refused, moves = TRUE[m[5]], TRUE[m[6]], TRUE[m[7]]
    if quiet != (read == "none" and write == "none") or refused != (read == FAULT.format("false") and write == FAULT.format("true")):
        return None  # the summary line disagrees with the event lines
    if overwritten + intact > 16:
        return None
    if leaked == 16 and overwritten == 16 and quiet and moves:
        return "REACHED"
    if leaked == 0 and overwritten == 0 and intact == 16 and refused and moves:
        return "REFUSED"
    return "MIXED"


def scenario_a(a5: list[str]) -> str | None:
    """Scenario A's outcome if the scenario is valid and its printed finding is the one its observations give."""
    lines = part(a5, "A5S2   events after scenario A's positive control", "A5S2 finding=naive-frame-reuse")
    setup = next((m for ln in lines if (m := re.fullmatch(
        rf"A5S2 A: positive control=16/16; after the donor's revoke: copying the frame capability: Err\(FailedLookup\); copying the server's copy of it: Err\(FailedLookup\); "
        rf"reused frame at physical ({HEX}), the old frame was at ({HEX}) \(same=true\); reused frame reads as zero=16/16", ln))), None)
    outcome = probe_outcome(lines, "A")
    if setup is None or setup[1] != setup[2] or int(setup[1], 16) < 0x4000_0000 or outcome is None or "A5S2   events after scenario A's positive control: none" not in lines:
        return None
    return outcome if lines[-1] == f"A5S2 finding=naive-frame-reuse observed={outcome}" else None


def scenario_b(a5: list[str], *, mutant: bool) -> tuple[str, str] | None:
    """(outcome of the retype attempt, outcome of scenario B), under the same conditions."""
    lines = part(a5, "A5S2   events after scenario B's positive control", "A5S2 finding=teardown-then-reuse")
    retype = next((m for ln in lines if (m := re.fullmatch(r"A5S2 B: a retype of the untyped while its frame capability exists: (Ok\(\(\)\)|Err\((\w+)\))", ln))), None)
    setup = any(re.fullmatch(rf"A5S2 B: positive control=16/16; mapping torn down, then revoked; reused frame at physical {HEX} \(same as the old=true\)", ln) for ln in lines)
    outcome = probe_outcome(lines, "B")
    teardown = f"A5S2   teardown: table entry cleared, CMD_TLBI_NH_VA issued={'false' if mutant else 'true'}, CMD_SYNC complete"
    said = "A5S2 B: MUTANT teardown-without-invalidation, CMD_TLBI_NH_VA is not issued" in lines
    if retype is None or not setup or outcome is None or teardown not in lines or said != mutant or "A5S2   events after scenario B's positive control: none" not in lines:
        return None
    kernel = "ACCEPTED" if retype[1].startswith("Ok") else "REFUSED"
    if f"A5S2 finding=retype-while-child-exists observed={kernel}" not in lines or lines[-1] != f"A5S2 finding=teardown-then-reuse observed={outcome}":
        return None
    return (f"{kernel}({retype[2] or 'ok'})", outcome)


def scenario_c(a5: list[str]) -> str | None:
    """Scenario C's findings as one string, each recomputed from its observation line; "STOPPED" if the run ended inside C."""
    if not any(ln.startswith("A5S2 C: positive control=16/16; revoked; the untyped is now a CNode of 128 slots") for ln in a5):
        return None
    lines = part(a5, "A5S2   events after scenario C's positive control", "A5S2 finding=dma-duplicate-survives-revocation")
    if not lines:
        return "STOPPED" if a5[-1] not in ("A5S2_DONE", "A5S2_VOID") else None
    raw = next((m for ln in lines if (m := re.fullmatch(r"A5S2 C: bytes of the kernel object the device read out: slot 0 = \[([0-9a-f, ]+)\], slot 1 = \[([0-9a-f, ]+)\]", ln))), None)
    dup = next((m for ln in lines if (m := re.fullmatch(rf"A5S2 C: copying a capability out of slot 2 before the device wrote it: (\S+); after: (\S+); a signal through that copy arrived with badge ({HEX})", ln))), None)
    rev = next((m for ln in lines if (m := re.fullmatch(
        rf"A5S2 C: a copy of slot 1 made by the kernel delivered a signal with badge ({HEX}) before the revoke; after revoking the notification's original capability: "
        rf"copying the minted capability in slot 1: (\S+); copying the kernel-made copy: (\S+); a signal through the device-made duplicate arrived with badge ({HEX})", ln))), None)
    read_quiet = "A5S2   events after the device's read of the kernel object: none" in lines
    copy_quiet = "A5S2   events after the device's copy of slot 1 onto slot 2: none" in lines
    if raw is None or dup is None or rev is None:
        return None
    slot0, slot1 = [int(x, 16) for x in raw[1].split(", ")], [int(x, 16) for x in raw[2].split(", ")]
    badge, empty = "0x5eedc0de", "Err(FailedLookup)"
    t = lambda x: "true" if x else "false"  # noqa: E731
    f1 = (f"A5S2 finding=kernel-object-disclosed read-left-no-event={t(read_quiet)} slot0-empty={t(not any(slot0))} "
          f"slot1-nonzero-words={sum(x != 0 for x in slot1)}/4 badge-visible={t(0x5eedc0de in slot1)}")
    f2 = (f"A5S2 finding=capability-duplicated-by-dma device-copy-left-no-event={t(copy_quiet)} copy-out-refused-before={t(dup[1] == empty)} "
          f"copy-out-accepted-after={t(dup[2] == 'Ok(())')} signal-arrived-with-the-badge={t(dup[3] == badge)}")
    f3 = (f"A5S2 finding=dma-duplicate-survives-revocation kernel-made-copy-worked-before={t(rev[1] == badge)} minted-capability-removed={t(rev[2] == empty)} "
          f"kernel-made-copy-removed={t(rev[3] == empty)} dma-duplicate-still-works={t(rev[4] == badge)}")
    if f1 not in lines or f2 not in lines or lines[-1] != f3 or len(slot0) != 4 or len(slot1) != 4:
        return None
    return "; ".join(x.split(" ", 2)[2] for x in (f1, f2, f3))


def run_summary(log: str, header: str, *, mutant: bool) -> str | None:
    """One run's outcomes as a single string, or None if the run is invalid or inconsistent."""
    a5 = [ln for ln in body(log) if ln.startswith("A5S2")]
    if header not in a5 or any("VOID" in ln or "void" in ln or "INVALID-SETUP" in ln or "overflowed" in ln or "A5S2 stopped" in ln for ln in a5):
        return None
    a, b, c = scenario_a(a5), scenario_b(a5, mutant=mutant), scenario_c(a5)
    if a is None or b is None or c is None:
        return None
    if c != "STOPPED":
        end = "A5S2 at the end: device transfers not reported finished=0 console_bytes_dropped=0 mmio_range_errors=0"
        state = "A5S2 smmu at the end [IDR0, IDR1, IDR5, CR0, CR0ACK, GBPA, GERROR^GERRORN] = [d44101b, 2730010, 74, d, d, 1000, 0]"
        if a5[-3:] != [state, end, "A5S2_DONE"]:
            return None
    return f"A naive frame reuse: {a}. B retype while the frame exists: {b[0]}; teardown then reuse: {b[1]}. C: {c}."


def trace_consistent(log: str, *, mutant: bool) -> bool:
    """QEMU's trace against the root task's lines: only stage-1 translations of stream 0x10 inside the window and never a
    global decision; one page invalidation per teardown that issued one; and in scenario A the device's two transfers through
    the mapping are reported as translations to the reused frame exactly when the scenario's outcome is REACHED."""
    lines = body(log)
    a5 = [ln for ln in lines if ln.startswith("A5S2")]
    ok = [re.fullmatch(rf"smmuv3_translate_success \S+ sid=0x10 iova=({HEX}) translated=({HEX}) perm=0x3 stage=1\s*", ln) for ln in lines if ln.startswith("smmuv3_translate_")]
    if not ok or any(m is None for m in ok) or not all(int(m[1], 16) >> 12 in (0x100000, 0x100003) for m in ok):
        return False
    issued = sum(ln == "A5S2   teardown: table entry cleared, CMD_TLBI_NH_VA issued=true, CMD_SYNC complete" for ln in a5)
    inval = sum(ln.startswith(f"smmuv3_range_inval vmid=0 asid=7 addr={IOVA} tg=0 num_pages=0x1 ttl=0 leaf=1 stage=1") for ln in lines)
    reused = next((m[1] for ln in a5 if (m := re.match(rf"A5S2 A: .*reused frame at physical ({HEX}),", ln))), None)
    probe = part(lines, "A5S2 A: positive control", "A5S2 A: secret words")
    to_reused = sum(1 for ln in probe if f"iova={IOVA} translated={reused} " in ln)
    outcome = scenario_a(a5)
    return reused is not None and inval == issued and outcome is not None and (to_reused == 2) == (outcome == "REACHED") and (to_reused == 0 or outcome != "REFUSED")


def verify_a5_step2(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    try:
        _verify(res, check, h)
        check("A5 step 2 evidence files are present and well-formed", True)
    except (OSError, KeyError, ValueError, IndexError, TypeError) as err:
        check(f"A5 step 2 evidence files are present and well-formed (stopped at: {type(err).__name__})", False)


def _verify(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    rd = lambda rel: h.read(res, f"A5-step2/{rel}")  # noqa: E731
    pre, post, sums = rd("00-preflight.txt"), rd("07-post-checks.txt"), rd("02-sums.txt")
    pin = f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0"
    src = r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$"
    a = {m[2]: m[1] for m in re.finditer(src, pre)}
    b = {m[2]: m[1] for m in re.finditer(src, post)}
    e3 = h.read(res, "E3/04-post-checks.txt")
    kernel, loader = re.search(r"(?m)^e3 ([0-9a-f]{64})  kernel.elf$", e3), re.search(r"(?m)^e3 ([0-9a-f]{64})  sel4-kernel-loader.elf$", e3)
    check("A5 step 2 inputs: the pinned clean seL4 (an unmodified kernel), clean seL4_tools, util_libs and rust-sel4 checkouts, QEMU 11.1.3; no change to the seL4 source, Cargo.toml or Cargo.lock; the E1-H kernel and loader are those of the E3 evidence build (same SHA-256); the scripts and sources are the repository files the preflight and post-run record name",
          pin in pre and "QEMU emulator version 11.1.3" in pre
          and all(re.search(rf"(?m)^{re.escape(r)} HEAD: [0-9a-f]{{40}}; dirty files: 0$", pre) for r in ("tools/seL4", "projects/util_libs", "rust-sel4"))
          and "seL4 source tracked diff: 0 lines" in post and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post
          and kernel is not None and loader is not None and f"e3 kernel.elf sha256: {kernel[1]}" in pre and f"e3 sel4-kernel-loader.elf sha256: {loader[1]}" in pre
          and set(a) == set(SOURCES) and a == b
          and all(hashlib.sha256(rb(HERE / rel)).hexdigest() == sha for rel, sha in a.items()))
    names = ["e1h-main", f"e1h-{MUTANT}", "k2r-main"]
    builds = {n: rd(f"01-build-{n}.txt") for n in names}
    s = {m[1]: m[2] for m in re.finditer(r"(?m)^(\S+) ([0-9a-f]{64})$", sums)}
    empty = hashlib.sha256(b"").hexdigest()
    cfg, table = hashlib.sha256(rb(res / "A2a-variants/gen_config-K2R.json")).hexdigest(), hashlib.sha256(rb(res / "A2a-variants/functions-K2R.tsv")).hexdigest()
    check("A5 step 2 builds: all three exit 0 with no error line and give three distinct images; the K2R image is built with the release options, 4 nodes and the experiment's root task, and its kernel configuration and function table equal (same SHA-256) the published K2R of the A2a-variants evidence",
          all(builds[n].startswith(f"## {n}: build exit 0") and not re.search(r"(?m)^(CMake )?Error|^FAILED|^error", builds[n]) for n in names)
          and len({s.get(f"image-{n}") for n in names}) == 3 and None not in {s.get(f"image-{n}") for n in names}
          and "root task: a5_step2_root_task, mutant: none," in builds["k2r-main"] and "-DKernelDebugBuild=OFF -DKernelPrinting=OFF" in builds["k2r-main"]
          and "-DKernelMaxNumNodes=4" in builds["k2r-main"] and "-DKernelArmHypervisorSupport=OFF" in builds["k2r-main"]
          and cfg != empty and table != empty and s.get("gen_config-k2r") == s.get("prefix-gen_config-k2r") == s.get("recorded-gen_config-K2R") == cfg
          and s.get("functions-k2r") == s.get("recorded-functions-K2R") == table)
    e1h = [rd(f"10-e1h-main-{n}.txt") for n in (1, 2, 3)]
    k2r = [rd(f"11-k2r-main-{n}.txt") for n in (1, 2, 3)]
    mut = rd(f"20-mutant-e1h-{MUTANT}.txt")
    k2r_image = "/external/relk-build/K2R-a5s2/build/images/rust-root-task-image-arm-qemu-arm-virt"
    check("A5 step 2 launches: every run's recorded QEMU command line names `iommu=smmuv3,highmem=off`, 1024 MiB, the edu devices, the trace of the SMMU model, the vCPU count (1 for E1-H, 4 for K2R) and the image its file name says",
          all(launched(x, 1, "/external/a5-step2-build/main/image.elf") for x in e1h) and all(launched(x, 4, k2r_image) for x in k2r)
          and launched(mut, 1, f"/external/a5-step2-build/{MUTANT}/image.elf"))
    e1h_header = "A5S2 start: built-for PRINTING=true MAX_NUM_NODES=1 ARM_HYPERVISOR_SUPPORT=true mutant=none"
    k2r_header = "A5S2 start: built-for PRINTING=false MAX_NUM_NODES=4 ARM_HYPERVISOR_SUPPORT=false mutant=none"
    se = [run_summary(x, e1h_header, mutant=False) for x in e1h]
    sk = [run_summary(x, k2r_header, mutant=False) for x in k2r]
    sm = run_summary(mut, f"A5S2 start: built-for PRINTING=true MAX_NUM_NODES=1 ARM_HYPERVISOR_SUPPORT=true mutant={MUTANT}", mutant=True)
    check(f"A5 step 2 on the E1-H kernel: each of three boots is valid (positive controls moved 16 of 16 words; after the revoke both the frame capability and the server's copy of it are gone; the reused frame has the old frame's physical address and reads as zero; no transfer left unfinished) and each printed finding is the one the run's own observation and event lines give by the design's rule; the three boots agree. Observed: {se[0]}",
          se[0] is not None and se[0] == se[1] == se[2])
    check(f"A5 step 2 on K2R (non-hypervisor, 4 vCPUs, release kernel, seL4's elfloader, nothing from the kernel on the console): the same validity and consistency in each of three boots, which agree. Observed: {sk[0]}",
          sk[0] is not None and sk[0] == sk[1] == sk[2] and all(all(f"Core {c} is up with logic id {c}" in x for c in (1, 2, 3)) and "Bootstrapping kernel" not in x for x in k2r))
    check("A5 step 2 agreement with QEMU's trace (all seven boots): every translation the SMMU model reports is stage 1 for stream 0x10 inside the window, never a global decision; it reports one page invalidation for each teardown in which the root task issued one; in scenario A it reports the device's two transfers as translations to the reused frame's physical address exactly when the scenario's outcome is REACHED",
          all(trace_consistent(x, mutant=False) for x in e1h + k2r) and trace_consistent(mut, mutant=True))
    check(f"A5 step 2 mutant (E1-H, one boot; a validity condition on the experiment's power): the run is valid and consistent, and leaving the invalidation command out of scenario B's teardown changes scenario B's outcome and nothing else. Observed: {sm}",
          sm is not None and se[0] is not None and sm != se[0] and sm.split(" B ")[0] == se[0].split(" B ")[0] and sm.split(" C: ")[1] == se[0].split(" C: ")[1]
          and sm.split("teardown then reuse: ")[1].split(".")[0] != se[0].split("teardown then reuse: ")[1].split(".")[0])
    record = (HERE / "results/A5-step2.md").read_text(encoding="utf-8") if (HERE / "results/A5-step2.md").is_file() else ""
    check("A5 step 2 record: results/A5-step2.md states, word for word, the outcomes computed from the evidence for the E1-H kernel, for K2R and for the mutant",
          all(x is not None and f"`{label}: {x}`" in record for label, x in (("E1-H", se[0]), ("K2R", sk[0]), ("E1-H mutant", sm))))


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    def r(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"A5-step2/{path}", fn)

    e1h, k2r, tr = "A5 step 2 on the E1-H kernel", "A5 step 2 on K2R", "A5 step 2 agreement with QEMU's trace"
    flip = {"REACHED": "REFUSED", "REFUSED": "REACHED", "MIXED": "REACHED"}
    return [
        ("an E1-H boot's printed finding for A contradicts its observations", r("10-e1h-main-1.txt", lambda t: re.sub(r"(finding=naive-frame-reuse observed=)(\w+)", lambda m: m[1] + flip.get(m[2], "REACHED"), t, count=1)), e1h),
        ("an E1-H boot's printed finding for B contradicts its observations", r("10-e1h-main-2.txt", lambda t: re.sub(r"(finding=teardown-then-reuse observed=)(\w+)", lambda m: m[1] + flip.get(m[2], "REACHED"), t, count=1)), e1h),
        ("an E1-H boot's reused frame is at another address", r("10-e1h-main-2.txt", lambda t: re.sub(r"(A5S2 A: [^\n]*the old frame was at 0x[0-9a-f]+)000 \(same=true\)", r"\g<1>100 (same=true)", t, count=1)), e1h),
        ("an E1-H boot's server copy survived the revoke", r("10-e1h-main-3.txt", lambda t: t.replace("copying the server's copy of it: Err(FailedLookup)", "copying the server's copy of it: Ok(())", 1)), e1h),
        ("an E1-H boot's positive control failed", r("10-e1h-main-1.txt", lambda t: t.replace("A5S2 A: positive control=16/16", "A5S2 A: positive control=0/16", 1)), e1h),
        ("an E1-H boot's event lines disagree with its summary line", r("10-e1h-main-3.txt", lambda t: t.replace(READ_EV + "none", READ_EV + FAULT.format("false"), 1) if READ_EV + "none" in t else t.replace(READ_EV + FAULT.format("false"), READ_EV + "none", 1)), e1h),
        ("one E1-H boot differs from the other two", r("10-e1h-main-2.txt", lambda t: re.sub(r"(A5S2 A: secret words the device read out=)(\d+)(/16; victim words the device overwrote=)(\d+)(/16 \(victim still intact=)(\d+)", lambda m: m[1] + "8" + m[3] + "8" + m[5] + "8", t, count=1)), e1h),
        ("an E1-H boot's finding in C contradicts its observation line", r("10-e1h-main-1.txt", lambda t: re.sub(r"(dma-duplicate-still-works=)(true|false)", lambda m: m[1] + ("false" if m[2] == "true" else "true"), t, count=1)), e1h),
        ("an E1-H boot left a transfer unfinished", r("10-e1h-main-3.txt", lambda t: t.replace("device transfers not reported finished=0", "device transfers not reported finished=1", 1)), e1h),
        ("a K2R boot has a kernel line on the console", r("11-k2r-main-1.txt", lambda t: t.replace("A5S2 start:", "Bootstrapping kernel\nA5S2 start:", 1)), k2r),
        ("a K2R boot's printed finding for A contradicts its observations", r("11-k2r-main-2.txt", lambda t: re.sub(r"(finding=naive-frame-reuse observed=)(\w+)", lambda m: m[1] + flip.get(m[2], "REACHED"), t, count=1)), k2r),
        ("a boot's trace has a global bypass decision", r("11-k2r-main-3.txt", lambda t: re.sub(r"(?m)^smmuv3_translate_success (\S+ sid=0x10 iova=0x100000000) [^\n]*$", r"smmuv3_translate_bypass \1 perm=0x3", t, count=1)), tr),
        ("a boot's trace lacks a page invalidation", r("10-e1h-main-1.txt", lambda t: re.sub(r"(?m)^smmuv3_range_inval [^\n]*\n", "", t, count=1)), tr),
        ("the mutant's teardown is recorded as having issued the invalidation", r(f"20-mutant-e1h-{MUTANT}.txt", lambda t: t.replace("CMD_TLBI_NH_VA issued=false", "CMD_TLBI_NH_VA issued=true", 1)), "A5 step 2 mutant"),
        ("a run was launched with one vCPU on K2R", r("11-k2r-main-1.txt", lambda t: t.replace(" -smp 4 ", " -smp 1 ", 1)), "A5 step 2 launches"),
        ("the K2R kernel is not the recorded K2R", r("02-sums.txt", lambda t: re.sub(r"(?m)^(gen_config-k2r )([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "A5 step 2 builds"),
        ("a source hash differs between the records", r("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )([0-9a-f])(?=[0-9a-f]{63}  crates/e2-root-task/src/a5_step2_tests.rs)", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "A5 step 2 inputs"),
    ]
