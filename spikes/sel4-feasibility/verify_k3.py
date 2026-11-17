"""K3 checks for verify-evidence.py: the SMMU server in its own protection domain (results/K3.md). Spike code, stdlib only.
Loaded by verify-evidence.py by file path; `h` has `read`.

**What is independent of the root task's own verdicts, and what is not.** Every `K3 obs` line is re-judged here by the rule fixed in
the design (leak: REACHED if all 16 words of the target's secret arrived, REFUSED if the device's buffer came back all zero with
fault records for the attacker's stream, else MIXED; clobber: REACHED if all 16 words were overwritten, INTACT if none were). The
`K3 test` verdicts that the root task derives from its observations are re-derived here from those observation lines for the
checks named in `derived()` (the decisive ones and their positive controls); the sets of failing checks are compared with the
sets the design predicts for each server variant; the event records the server read, per stream, are compared with the records
QEMU's own trace reports per stream (a channel that does not pass through the server). **Not independent:** the numbers on the
`K3 obs` lines are the root task's own reduction of what the tasks reported (`K3 rep`) and the server answered (`K3 adm`); this
checker does not recompute them from those raw lines, and a few verdicts (for example T1pre, T2free, T3c1's target) are not
re-derived at all. results/K3.md section 10c lists the limits.

They establish what one kernel build, one emulated SMMU model and one device model did with the arrangement of results/K3.md.
Not hardware, not timing, not a general security property.
"""
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RS = "crates/e2-root-task/src"
TS = "crates/e2-task/src"
SOURCES = ("build-k3.sh", "build-relk.sh", "run-k3-evidence.sh", "verify_k3.py", "boot-a5.py", "a2a-compare.py",
           f"{TS}/k3_abi.rs", f"{TS}/k3_mmio.rs", f"{TS}/k3_smmu.rs", f"{TS}/k3_runtime.rs", f"{TS}/bin/k3_server.rs", f"{TS}/bin/k3_client.rs",
           f"{RS}/bin/k3_root_task.rs", f"{RS}/k3_script.rs", f"{RS}/k3_spawn.rs", f"{RS}/k3_world.rs",
           f"{RS}/a5_mmio.rs", f"{RS}/child_vspace.rs", f"{RS}/edu.rs", f"{RS}/object_allocator.rs", f"{RS}/pl011.rs", f"{RS}/slots.rs")
KERNELS = ("K2", "K2R")
MUTANTS = ("skip-invalidate", "reclaim-while-mapped", "no-owner-check", "death-without-teardown", "shared-address-space", "shared-asid")
# Per mutant: the sub-checks the design predicts it breaks, and the further ones it may break because the broken rule is shared
# with, or is a precondition of, later tests (observed in development runs and explained in results/K3.md).
MUST_FAIL: dict[str, frozenset[str]] = {
    "skip-invalidate": frozenset({"T2a", "T2d"}),
    "reclaim-while-mapped": frozenset({"T2a", "T2d"}),
    "no-owner-check": frozenset({"T1f", "T2e"}),
    "death-without-teardown": frozenset({"T4b", "T4c"}),
    "shared-address-space": frozenset({"T1d"}),
    "shared-asid": frozenset({"T1g"}),
}
MAY_FAIL: dict[str, frozenset[str]] = {
    "skip-invalidate": frozenset({"T3pre", "T3a4", "T4b", "T4c"}),
    "reclaim-while-mapped": frozenset({"T3pre", "T3a4", "T4b", "T4c"}),
    "no-owner-check": frozenset(),
    "death-without-teardown": frozenset(),
    "shared-address-space": frozenset({"T1e", "T2d", "T4b", "T4c"}),
    "shared-asid": frozenset(),
}
# The run of a mutant may end in a fault of an innocent task (the victim of the bug); only this one is allowed to.
MAY_ABORT = frozenset({"no-owner-check"})
REQUIRED_IDS = ("S0a", "S0b", "S0c", "S0d", "T1pre", "T1a", "T1b", "T1c", "T1c3", "T1g", "T1d", "T1e", "T1e0", "T1f", "T2pre", "T2free",
                "T2a", "T2b", "T2e", "T2d", "T3pre", "T3a1", "T3a2", "T3a3", "T3a4", "T3a7", "T3a8", "T3a5", "T3a6", "T3c0", "T3c3", "T4pre", "T4a", "T4b", "T4c")
MACHINE = "virt,secure=off,gic-version=2,virtualization=on,iommu=smmuv3,highmem=off"
TAIL = " -device edu,dma_mask=0xffffffffff -device edu,dma_mask=0xffffffffff -trace smmuv3_propagate_event"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
KV = re.compile(r'(\w+)=("[^"]*"|\S+)')
WORDS = 16


def rb(path: Path) -> bytes:
    return path.read_bytes() if path.is_file() else b""


def clean(log: str) -> str:
    return ANSI.sub("", log.replace("\r", ""))


def fields(line: str) -> dict[str, str]:
    return {k: v.strip('"') for k, v in KV.findall(line)}


def num(d: dict[str, str], key: str) -> int:
    try:
        return int(d[key], 0)
    except (KeyError, ValueError):
        return -1


def leak_outcome(d: dict[str, str]) -> str:
    if num(d, "secret_words") == WORDS and num(d, "marker_words") == 0:
        return "REACHED"
    if num(d, "zero_words") == WORDS and num(d, "secret_words") == 0 and num(d, "faults") >= 1:
        return "REFUSED"
    return "MIXED"


def clobber_outcome(d: dict[str, str]) -> str:
    if num(d, "attacked_words") == WORDS:
        return "REACHED"
    if num(d, "intact_words") == WORDS and num(d, "attacked_words") == 0:
        return "INTACT"
    return "MIXED"


class Run:
    """What one boot's log says, parsed; `problems` lists everything that makes it invalid."""

    def __init__(self, log: str, kernel: str, variant: str) -> None:
        self.kernel, self.variant = kernel, variant
        self.text = clean(log)
        self.lines = [ln for ln in self.text.split("\n") if ln.startswith("K3")]
        self.problems: list[str] = []
        self.tests: list[tuple[str, str]] = [(f["id"], f["result"]) for f in (fields(ln) for ln in self.lines if ln.startswith("K3 test "))]
        self.obs: dict[str, dict[str, str]] = {}
        for ln in self.lines:
            if ln.startswith("K3 obs "):
                f = fields(ln)
                self.obs[f.get("id", "?")] = f
        self.analyse()

    def bad(self, why: str) -> None:
        self.problems.append(why)

    def result(self, tid: str) -> str | None:
        return next((r for t, r in self.tests if t == tid), None)

    def analyse(self) -> None:
        first = self.text.split("\n", 1)[0]
        image = f"/external/k3-build/{self.kernel}-{self.variant}/image"
        if not (first.startswith("+ ") and f" -machine {MACHINE} -accel tcg -cpu cortex-a57 -smp 4 -m size=1024M " in first
                and first.endswith(image + TAIL)):
            self.bad("launch line")
        if "[boot-a5] marker 'K3_DONE' SEEN" not in self.text:
            self.bad("marker")
        mutant = self.variant if self.variant in MUTANTS else "none"
        mode = "naive" if self.variant == "naive" else "design"
        printing = "true" if self.kernel == "K2" else "false"
        header = f"K3 start built-for PRINTING={printing} MAX_NUM_NODES=4 ARM_HYPERVISOR_SUPPORT=false mode={mode} mutant={mutant}"
        if header not in self.lines:
            self.bad("header")
        if not all(f"K3 domain name={n} id={i} started" in self.lines for n, i in (("S", 4), ("C1", 1), ("C2", 2), ("M", 3))):
            self.bad("domains")
        if not all(f"Core {c} is up with logic id {c}" in self.text for c in (1, 2, 3)):
            self.bad("cores")
        if self.kernel == "K2R" and "Bootstrapping kernel" in self.text:
            self.bad("release kernel printed")
        for tid, f in self.obs.items():
            kind = f.get("kind")
            if kind == "leak" and leak_outcome(f) != f.get("outcome"):
                self.bad(f"leak outcome {tid}")
            if kind == "clobber" and clobber_outcome(f) != f.get("outcome"):
                self.bad(f"clobber outcome {tid}")
        if "K3_DONE" not in self.lines:
            self.bad("K3_DONE")
        summary = next((fields(ln) for ln in self.lines if ln.startswith("K3 summary ")), None)
        self.aborted = summary is None
        if summary is not None:
            counts = {r: sum(1 for _, x in self.tests if x == r) for r in ("PASS", "FAIL", "VOID")}
            if (num(summary, "passed"), num(summary, "failed"), num(summary, "void")) != (counts["PASS"], counts["FAIL"], counts["VOID"]):
                self.bad("summary counts")
            if num(summary, "console_bytes_dropped") != 0 or num(summary, "mmio_range_errors") != 0:
                self.bad("console or mmio errors")
        elif not any(ln.startswith("K3 fault ") for ln in self.lines):
            self.bad("run ended without a summary or a fault line")
        self.derived()
        self.authority()
        self.trace()

    def derived(self) -> None:
        """Verdicts re-derived from the observation lines."""
        o = self.obs
        naive = self.variant == "naive"

        def out(tid: str, key: str = "outcome") -> str | None:
            return o.get(tid, {}).get(key)

        def f(tid: str) -> dict[str, str]:
            return o.get(tid, {})

        checks: dict[str, bool | None] = {
            "T1a": num(f("T1a"), "words_from_source") == WORDS and num(f("T1a"), "words_old") == 0,
            "T1b": out("T1b") == "REFUSED",
            "T1e0": all(num(f(i), "faults") >= 1 for i in ("T1e1", "T1e2", "T1e4")),
            "T2b": f("T2b").get("copy", "").startswith("Some("),
            "T3a6": num(f("T3a6"), "untyped_ok") == 1 and num(f("T3a6"), "tcb_ok") == 0,
            "S0d": self.init_ok(),
            "T1c3": all(out(i) == "REFUSED" for i in ("T1c3-strtab", "T1c3-cmdq", "T1c3-l1")),
            "T1f": num(f("T1f"), "rc_other") == 2 and num(f("T1f"), "mapped") == 1 and num(f("T1f"), "owner") == 1,
            "T2pre": num(f("T2pre"), "rc") == 0 and num(f("T2pre"), "words_from_source") == WORDS,
            "T2e": num(f("T2e"), "rc_stale") == 2 and num(f("T2e"), "mapped") == 1 and num(f("T2e"), "owner") == 2,
            "T3pre": num(f("T3pre"), "rc") == 0 and num(f("T3pre"), "words_from_source") == WORDS,
            "T3a1": (num(f("T3a1"), "populated") == num(f("T3a1"), "root_populated") > 0 and num(f("T3a1"), "frames") == num(f("T3a1"), "root_frames")
                     and num(f("T3a1"), "untyped_ok") == 0 and num(f("T3a1"), "root_untyped") == 0 and num(f("T3a1"), "tcb_ok") == 0
                     and num(f("T3a1"), "revoke_failed") == 0),
            "T3a2": num(f("T3a2"), "ping_rc") == 6 and num(f("T3a2"), "events_rc") == 6 and num(f("T3a2"), "rebadge_rc") > 0,
            "T3a3": num(f("T3a3"), "unmap_rc") == 0 and num(f("T3a3"), "map_rc") == 0,
            "T3a4": (num(f("T3a4"), "revoke_rc") == 0 and num(f("T3a4"), "delete_rc") == 0 and num(f("T3a4"), "words_from_source") == WORDS
                     and num(f("T3a4"), "mapped") == 1 and num(f("T3a4"), "owner") == 1),
            "T3a8": (num(f("T3a8"), "frame_pa") == 0 and num(f("T3a8"), "retype_rc") == 0
                     and num(f("T3a8"), "handle") >= 0 and (int(f("T3a5").get("handles_mask", "0"), 16) >> max(num(f("T3a8"), "handle"), 0)) & 1 == 1),
            "T4a": (num(f("T4a"), "dead_rc") == 0 and num(f("T4a"), "freed") == num(f("T4a"), "pages_owned") > 0 and num(f("T4a"), "owned_after") == 0),
            "T4pre": f("T4pre").get("finished") == "true" and num(f("T4pre"), "words_from_device") == WORDS and num(f("T4pre"), "words_old") == 0,
            "T1c": out("T1c1") == "REFUSED" and out("T1c2") == "REFUSED",
            "T1e": all(out(i) == "INTACT" for i in ("T1e1", "T1e2", "T1e3", "T1e4")),
            "T1d": (num(f("T1d"), "secret_words") == 0 and num(f("T1d2"), "words_of_C2_secret") == 0
                    and num(f("T1d2"), "words_of_C1_page_a") == WORDS),
            "T1g": num(f("T1g"), "words_from_source") == WORDS and num(f("T1g"), "words_old") == 0,
            "T2a": out("T2a") == "REFUSED",
            "T2d": out("T2d1") == "REFUSED" and out("T2d2") == "INTACT",
            "T3a5": (num(f("T3a5"), "last_rc") == 3 and f("T3a5").get("distinct_pas") == "true" and f("T3a5").get("y_pa_once_with_C1") == "true"
                     and num(f("T3a5"), "mapped") == 8),
            "T3a7": num(f("T3a7"), "frame_pa") in self.y_candidates() and num(f("T3a7"), "retype_rc") == 11,
            "T3c0": (num(f("T3c0"), "rc") == 0) if naive else (num(f("T3c0"), "rc") == 5 and num(f("T3c0"), "detail") == 0),
            "T3c1": (out("T3c1") == "REACHED") if naive else None,
            "T3c3": ((out("T3c3") == "REACHED" and out("T3c5") == "REACHED") if naive
                     else (out("T3c3") == "REFUSED" and out("T3c4") == "REFUSED" and out("T3c5") == "INTACT")),
            "T4b": (f("T4b").get("finished") == "true" and all(f("T4b").get(k) == "true" for k in ("armed_at_kill", "armed_after_teardown", "armed_when_c2_owned_page"))
                    and num(f("T4b"), "faults") >= 1 and num(f("T4b"), "intact_words") == WORDS
                    and num(f("T4b"), "words_of_dead_drivers_buffer") == 0),
            "T4c": (f("T4c").get("finished") == "true" and num(f("T4c"), "faults") >= 1 and num(f("T4c"), "intact_words") == WORDS
                    and num(f("T4c"), "words_of_dead_drivers_buffer") == 0),
        }
        for tid, want in checks.items():
            got = self.result(tid)
            if want is None or got is None or tid not in {t for t, _ in self.tests}:
                continue
            if got == "VOID":
                continue
            if (got == "PASS") != bool(want):
                self.bad(f"verdict {tid} does not follow from its observations")
        if self.variant in ("design", "naive"):
            for key, expect in (("alloc", "commands=0 syncs=0 revokes=0"), ("free", "commands=2 syncs=1 revokes=1")):
                if f"K3 cost op={key} {expect}" not in self.lines:
                    self.bad(f"cost {key}")

    def c1_frames(self) -> set[int]:
        """The physical addresses of the frames C1 held before its attack, from the root task's own scan of C1's CNode."""
        ln = next((x for x in self.lines if x.startswith("K3 inventory dom=C1 when=before-attack")), "")
        m = re.search(r"frame_pas=\[([0-9a-f, ]*)\]", ln)
        return {int(x, 16) for x in m[1].replace(" ", "").split(",") if x} - {0x10000000} if m else set()

    def y_candidates(self) -> set[int]:
        """C1's frames before its attack, minus its device and the two pages it was given first: the page whose capability it drops."""
        pages = re.search(r"K3 pages C1a_pa=(0x[0-9a-f]+) C1b_pa=(0x[0-9a-f]+) ", self.text)
        known = {int(pages[1], 16), int(pages[2], 16)} if pages else set()
        return self.c1_frames() - known

    def init_ok(self) -> bool | None:
        """Both clients mapped their device and read the edu identification (their first report of step 1)."""
        got = {}
        for ln in self.lines:
            m = re.match(r"K3 rep dom=(C1|C2) tag=1 v1=(\d+) v2=(\d+) v3=(\d+)$", ln)
            if m and m[1] not in got:
                got[m[1]] = (int(m[2]), int(m[3]), int(m[4]))
        return len(got) == 2 and all(v == (0, 16777453, 1) for v in got.values())

    def authority(self) -> None:
        """The capabilities each untrusted domain was given, from the seed table, and what the root task found in their CNodes."""
        seeds: dict[str, list[dict[str, str]]] = {}
        for ln in self.lines:
            if ln.startswith("K3 seed "):
                d = fields(ln)
                seeds.setdefault(d["dom"], []).append(d)
        for dom in ("C1", "C2", "M", "S"):
            if dom not in seeds:
                self.bad(f"no seed table for {dom}")
        for dom in ("C1", "C2"):
            whats = " ".join(d.get("what", "") for d in seeds.get(dom, []))
            if re.search(r"untyped|U_|pool|SMMU registers", whats, re.IGNORECASE) or any(d.get("kind") == "move" for d in seeds.get(dom, [])):
                self.bad(f"{dom} was given an untyped or SMMU authority")
        if sum(1 for d in seeds.get("M", []) if "U_M" in d.get("what", "")) != 1 or any(d.get("kind") == "move" for d in seeds.get("M", [])):
            self.bad("M's seeds")
        moved = sorted(d.get("what", "").split(":")[0] for d in seeds.get("S", []) if d.get("kind") == "move")
        if moved != ["U_pool", "U_srv"]:
            self.bad("the pool and the server's memory are not moved to S")
        for dom, d in (("C1", "C1"), ("C2", "C2"), ("M", "M")):
            inv = next((fields(ln) for ln in self.lines if ln.startswith(f"K3 inventory dom={dom} when=start")), None)
            if inv is None or num(inv, "populated") != 2 + len(seeds.get(d, [])) or (dom != "M" and num(inv, "untyped") != 0):
                self.bad(f"inventory {dom}")
        for dom in ("C1", "C2"):
            inv = next((fields(ln) for ln in self.lines if ln.startswith(f"K3 inventory dom={dom} when=start")), None)
            if inv is not None and num(inv, "frames") != 1:
                self.bad(f"{dom} holds more than its device frame at the start")
        un = re.search(r"K3 untypeds pool_bits=(\d+) pool_paddr=(0x[0-9a-f]+) srv_bits=(\d+) srv_paddr=(0x[0-9a-f]+) ", self.text)
        if un is None or int(un[1]) < 15 or int(un[3]) < 16 or un[2] == un[4]:
            self.bad("the pool and server untypeds")

    def trace(self) -> None:
        """The event records the server read equal the records QEMU's SMMU model reports pushing: no overflow, none hidden."""
        read = sum(num(fields(ln), k) for ln in self.lines if ln.startswith("K3 adm op=13 ") for k in ("m0", "m1", "m2"))
        pushed = len(re.findall(r"smmuv3_propagate_event", self.text.split("[boot-a5]")[0].split("\n", 1)[1] if "\n" in self.text else ""))
        overflow = [num(fields(ln), "m3") for ln in self.lines if ln.startswith("K3 adm op=13 ")]
        if read != pushed or any(x != 0 for x in overflow):
            self.bad(f"event records: server read {read}, QEMU pushed {pushed}, overflows {overflow}")
        # per stream: the server's counts for C1's stream, C2's stream and the rest equal the records QEMU pushed for each
        binds = {}
        for m in re.finditer(r"K3 adm op=11 args=\[([0-9a-f]+), ([0-9a-f]+), ([0-9a-f]+), 0\] rc=0", self.text):
            binds[int(m[1], 16)] = int(m[2], 16)  # the root task prints the arguments in hex
        body = self.text.split("[boot-a5]")[0].split("\n", 1)[1] if "\n" in self.text else ""
        trace = [int(x, 16) for x in re.findall(r"smmuv3_propagate_event \S+ sid=0x([0-9a-f]+)", body)]
        sums = [sum(num(fields(ln), k) for ln in self.lines if ln.startswith("K3 adm op=13 ")) for k in ("m0", "m1", "m2")]
        if set(binds) != {1, 2}:
            self.bad("streams were not bound for both clients")
        else:
            per = [sum(1 for x in trace if x == binds[1]), sum(1 for x in trace if x == binds[2])]
            if sums != [per[0], per[1], len(trace) - per[0] - per[1]]:
                self.bad(f"per-stream event records: server {sums}, QEMU {per}")
        self.events = (read, pushed)

    def failed(self) -> set[str]:
        return {t for t, r in self.tests if r == "FAIL"}

    def signature(self) -> tuple[Any, ...]:
        return (tuple(self.tests), tuple(sorted((k, v.get("outcome")) for k, v in self.obs.items() if v.get("outcome"))))


def sha(path: Path) -> str:
    return hashlib.sha256(rb(path)).hexdigest()


def verify_k3(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    raw = res / "K3"

    def rd(name: str) -> str:
        p = raw / name
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    pre, post, sums = rd("00-preflight.txt"), rd("07-post-checks.txt"), rd("02-sums.txt")
    a = {m[2]: m[1] for m in re.finditer(r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$", pre)}
    b = {m[2]: m[1] for m in re.finditer(r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$", post)}
    record = (HERE / "results/K3.md").read_text(encoding="utf-8") if (HERE / "results/K3.md").is_file() else ""
    check("K3 inputs: the pinned clean seL4 (an unmodified kernel), clean seL4_tools, util_libs and rust-sel4 checkouts, QEMU 11.1.3; no change to the seL4 source, Cargo.toml or Cargo.lock; "
          "the sources, scripts and this checker are the repository files the preflight and post-run records name, unchanged between them, and results/K3.md lists every hash",
          "QEMU emulator version 11.1.3" in pre and "seL4 HEAD: 62e345c240a15671484530b4e6e069ce266c28d7; dirty files: 0" in pre
          and all(re.search(rf"(?m)^{re.escape(r)} HEAD: [0-9a-f]{{40}}; dirty files: 0$", pre) for r in ("tools/seL4", "projects/util_libs", "rust-sel4"))
          and "seL4 source tracked diff: 0 lines" in post and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post
          and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in pre
          and set(a) == set(SOURCES) and a == b and all(sha(HERE / rel) == s for rel, s in a.items())
          and all(f"`{s}`  `{rel}`" in record for rel, s in a.items()))

    s = {m[1]: m[2] for m in re.finditer(r"(?m)^(\S+) ([0-9a-f]{64})$", sums)}
    empty = hashlib.sha256(b"").hexdigest()
    variants = ("design", "naive", *MUTANTS)
    ok_builds = True
    for kernel in KERNELS:
        for v in variants:
            text = rd(f"01-build-{kernel}-{v}.txt")
            ok_builds &= text.startswith(f"## {kernel}-{v}: build exit 0") and not re.search(r"(?m)^(CMake )?Error|^FAILED|^error", text)
            ok_builds &= "-DKernelArmHypervisorSupport=OFF" in text and "-DKernelMaxNumNodes=4" in text
            ok_builds &= ("-DKernelDebugBuild=OFF -DKernelPrinting=OFF" in text) == (kernel == "K2R")
            ok_builds &= s.get(f"gen_config-{kernel}-{v}") == s.get(f"prefix-gen_config-{kernel}-{v}") == s.get(f"gen_config-{kernel}-design") is not None
        ident = (s.get(f"gen_config-{kernel}-design") == s.get(f"recorded-gen_config-{kernel}") != empty
                 and s.get(f"functions-{kernel}") == s.get(f"recorded-functions-{kernel}") != empty)
        ok_builds &= ident
        server = {s.get(f"k3-server-{kernel}-{v}") for v in variants}
        ok_builds &= len(server) == len(variants) and None not in server
        ok_builds &= len({s.get(f"k3-client-{kernel}-{v}") for v in variants}) == 1  # the client is the same program in every variant
    check("K3 builds: every one of the 16 builds exits 0 with no error line, is built for the non-hypervisor 4-node kernel (release options on K2R only) against the interface of its own kernel, the kernel "
          "configuration is the same in every variant and equals (same SHA-256) the published K2 (A2a) and K2R (A2a-variants), the kernel's function table equals the published one, the server differs "
          "between the 8 variants and the client does not", ok_builds)

    logs = {(k, v, n): Run(rd(f"{p}-{k}-{v}-{n}.txt"), k, v)
            for k in KERNELS for v, p, ns in (("design", "10", (1, 2, 3)), ("naive", "20", (1,)), *((m, "30", (1,)) for m in MUTANTS)) for n in ns}
    design = {k: [logs[(k, "design", n)] for n in (1, 2, 3)] for k in KERNELS}

    def valid(run: Run) -> bool:
        return not run.problems

    problems = {f"{k}-{v}-{n}": r.problems for (k, v, n), r in logs.items() if r.problems}
    check(f"K3 launches and validity: every one of the 20 boots was launched as recorded (machine, 4 vCPUs, the edu devices, QEMU's event trace, the image its name says), reached K3_DONE, "
          f"started the four domains, printed the header of its variant, has a seed table that gives C1 and C2 no untyped and no SMMU authority and moves exactly the pool and the server's memory to S, "
          f"and every observation line's printed outcome is the one its numbers give by the design's rule, the server's event count equals QEMU's. Problems: {problems}",
          not problems and len(logs) == 20)

    def clean_design(run: Run) -> bool:
        ids = {t for t, _ in run.tests}
        return (valid(run) and not run.aborted and all(i in ids for i in REQUIRED_IDS) and all(r == "PASS" for _, r in run.tests)
                and "K3_PASS" in run.lines and "K3_FAIL" not in run.lines)

    observed = {k: f"{len(design[k][0].tests)} checks" for k in KERNELS}
    check("K3 design build (the verdict): on K2 and on K2R, in each of 3 of 3 boots, every sub-check of T1 to T4 passes, none is void, the three boots agree, and the two kernels agree. "
          f"Observed: {observed}",
          all(clean_design(r) for k in KERNELS for r in design[k])
          and all(design[k][0].signature() == r.signature() for k in KERNELS for r in design[k])
          and design["K2"][0].signature() == design["K2R"][0].signature())
    naive = {k: logs[(k, "naive", 1)] for k in KERNELS}
    check("K3 control (the naive server that accepts a donated frame; not K3): on both kernels, the donation is accepted, C1's device reads the donated memory (positive control), and after the memory manager "
          "reclaims it and gives it to C2, C1's device reads and overwrites C2's secret: the arrangement of A5 step 2 reproduced across protection domains; every other sub-check is as in the design build",
          all(clean_design(r) and r.result("T3c1") == "PASS" and r.result("T3c3") == "PASS" and r.obs.get("T3c3", {}).get("outcome") == "REACHED"
              and r.obs.get("T3c5", {}).get("outcome") == "REACHED" for r in naive.values()))
    mut_ok = True
    for k in KERNELS:
        for m in MUTANTS:
            r = logs[(k, m, 1)]
            failed = r.failed()
            fine = valid(r) and MUST_FAIL[m] <= failed <= MUST_FAIL[m] | MAY_FAIL[m] and r.result("T1a") == "PASS" and "K3_FAIL" in r.lines and not any(x == "VOID" for _, x in r.tests)
            fine &= (not r.aborted) or (m in MAY_ABORT and any(ln.startswith("K3 fault ") for ln in r.lines))
            mut_ok &= fine
    check("K3 mutants (a validity condition on the experiment's power): on both kernels each of the six server bugs is detected: the sub-checks the design predicts for it fail, no sub-check outside the "
          "predicted and the explained collateral set fails, none is void, and the run does not pass. Only `no-owner-check` may end in a fault of the innocent task whose page the bug freed", mut_ok)
    ev = {k: sum(r.events[0] for r in design[k]) for k in KERNELS}
    check(f"K3 QEMU's trace: in every boot the number of event records the server read equals the number of records QEMU's SMMU model reports pushing (no overflow). Observed in the design boots: {ev}",
          all(r.events[0] == r.events[1] and r.events[0] > 0 for r in logs.values()))

    def line(kernel: str) -> str:
        d = design[kernel][0]
        fails = "; ".join(f"{m} fails {','.join(sorted(logs[(kernel, m, 1)].failed()))}" for m in MUTANTS)
        return (f"{kernel}: design passes {len(d.tests)} of {len(d.tests)} checks in 3 of 3 boots; naive control passes its {len(naive[kernel].tests)} checks, reproducing REACHED; "
                f"mutants: {fails}")

    check("K3 record: results/K3.md states, word for word, the outcome computed from the evidence for each kernel",
          all(f"`{line(k)}`" in record for k in KERNELS))


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    def r(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"K3/{path}", fn)

    val, des, mut = "K3 launches and validity", "K3 design build", "K3 mutants"
    flip = {"REACHED": "REFUSED", "REFUSED": "REACHED", "INTACT": "REACHED", "MIXED": "REACHED"}
    return [
        ("a design boot's printed outcome contradicts its numbers", r("10-K2R-design-1.txt", lambda t: re.sub(r"(id=T2a kind=leak [^\n]*outcome=)(\w+)", lambda m: m[1] + flip[m[2]], t, count=1)), val),
        ("a design boot's refused read has no fault records", r("10-K2-design-2.txt", lambda t: re.sub(r"(id=T1b kind=leak [^\n]*faults=)\d+", r"\g<1>0", t, count=1)), val),
        ("a design boot's test verdict contradicts its observations", r("10-K2R-design-3.txt", lambda t: t.replace("K3 test id=T2d result=PASS", "K3 test id=T2d result=FAIL", 1)), val),
        ("a design boot lost a check", r("10-K2-design-1.txt", lambda t: re.sub(r"(?m)^K3 test id=T4b [^\n]*\n", "", t, count=1)), val),
        ("a design boot has a failing check", r("10-K2R-design-2.txt", lambda t: t.replace("K3 test id=T1e result=PASS", "K3 test id=T1e result=FAIL", 1)), des),
        ("one design boot differs from the others", r("10-K2-design-3.txt", lambda t: re.sub(r"(id=T1g kind=roundtrip attacker=C2 words_from_source=)16", r"\g<1>15", t, count=1)), val),
        ("C1 is seeded with an untyped", r("10-K2R-design-1.txt", lambda t: t.replace("kind=copy what=\"BAR frame of its own edu device (device frame)\"", "kind=copy what=\"U_pool: a stolen untyped\"", 1)), val),
        ("the pool is not moved to S", r("10-K2-design-1.txt", lambda t: t.replace("kind=move what=\"U_pool", "kind=copy what=\"U_pool", 1)), val),
        ("the event count of the server differs from QEMU's", r("10-K2R-design-2.txt", lambda t: t.replace("smmuv3_propagate_event", "smmuv3_x", 1)), val),
        ("T1c3's observation has non-zero words and no faults", r("10-K2R-design-1.txt", lambda t: re.sub(r"(id=T1c3-strtab kind=leak [^\n]*zero_words=)16( secret_words=\d+ faults=)\d+", r"\g<1>0\g<2>0", t, count=1)), val),
        ("T4b's armed flags are false", r("10-K2-design-2.txt", lambda t: t.replace("armed_at_kill=true armed_after_teardown=true armed_when_c2_owned_page=true", "armed_at_kill=false armed_after_teardown=false armed_when_c2_owned_page=false", 1)), val),
        ("T1d's own-page word count is zero", r("10-K2R-design-3.txt", lambda t: re.sub(r"(words_of_C1_page_a=)16", r"\g<1>0", t, count=1)), val),
        ("T3a7's probe is a wrong frame address and a wrong error", r("10-K2-design-1.txt", lambda t: re.sub(r"(id=T3a7 kind=kernel-probe handle=\d+ frame_pa=)0x[0-9a-f]+( retype_rc=)\d+", r"\g<1>0x1\g<2>2", t, count=1)), val),
        ("T3a4's page is no longer reachable", r("10-K2R-design-2.txt", lambda t: re.sub(r"(id=T3a4 kind=drop-frame [^\n]*words_from_source=)16", r"\g<1>0", t, count=1)), val),
        ("a boot was launched with one vCPU", r("10-K2R-design-1.txt", lambda t: t.replace(" -smp 4 ", " -smp 1 ", 1)), val),
        ("the naive control no longer reaches the secret", r("20-K2R-naive-1.txt", lambda t: re.sub(r"(id=T3c3 kind=leak [^\n]*)secret_words=16", r"\g<1>secret_words=0", t, count=1)), "K3 control"),
        ("a mutant passes", r("30-K2R-skip-invalidate-1.txt", lambda t: t.replace("K3 test id=T2a result=FAIL", "K3 test id=T2a result=PASS", 1).replace("K3 test id=T2d result=FAIL", "K3 test id=T2d result=PASS", 1)), mut),
        ("a mutant's run has an unexplained failure", r("30-K2-death-without-teardown-1.txt", lambda t: t.replace("K3 test id=T1a result=PASS", "K3 test id=T1a result=FAIL", 1)), mut),
        ("the K2R kernel is not the recorded one", r("02-sums.txt", lambda t: re.sub(r"(?m)^(gen_config-K2R-design )([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "K3 builds"),
        ("a source hash differs between the records", r("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "K3 inputs"),
    ]
