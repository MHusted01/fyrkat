"""Checks for the A2a release variants (K1R, K2R, E1HR and the extra K0Q) for verify-evidence.py. Spike code, stdlib only.

Loaded by verify-evidence.py by file path; `h` is the namespace it passes (`read`, `E1_PINS`). It reuses the helpers of
verify_a2a.py from this directory, and like it **recomputes the whole comparison from the published function tables and
configurations**, here for eight configurations: the four of the reviewed A2a evidence (whose tables are copied and whose
hashes must equal those in results/A2a) and the four variants.

What the checks establish: that each variant was built with the recorded tools and command, differs from its parent in
exactly the configuration keys it is meant to (debug and printing for the release variants; the platform for K0Q), that its
function table is complete and reproducible, and that the comparison is the one the tables give. They establish nothing
about verification: textual identity with K0 is not proof applicability, and none of these is a matrix row.
"""
import hashlib
import importlib.util
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
IDS = ("K1R", "K2R", "E1HR", "K0Q")
BASE = ("K0", "K1", "K2", "E1H")
SOURCES = ("build-a2a-variants.sh", "a2a-compare.py", "boot-image.py")
DEBUG_KEYS = ["COLOUR_PRINTING", "DEBUG_BUILD", "IRQ_REPORTING", "PRINTING", "USER_STACK_TRACE_LENGTH"]
PLATFORM_KEYS = ["ARM_MACH", "ARM_PLAT", "MACH", "PLAT", "PLAT_QEMU_ARM_VIRT", "PLAT_TX2", "TIMER_FREQUENCY"]
K0_KNOBS = ["ALLOW_SMC_CALLS", "MAX_NUM_BOOTINFO_UNTYPED_CAPS", "NUM_DOMAINS", "NUM_DOMAIN_SCHEDULES", "VERIFICATION_BUILD"]


def sibling(name: str, file: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rb(path: Path) -> bytes:
    """The bytes of PATH, or nothing when it is missing: a missing file must fail a check, not crash the verifier."""
    return path.read_bytes() if path.is_file() else b""


def records(text: str, pattern: str) -> dict[str, str]:
    return {m[2]: m[1] for m in re.finditer(pattern, text)}


def verify_variants(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    try:
        _verify(res, check, h)
        check("A2a variants evidence files are present and well-formed", True)
    except (OSError, KeyError, ValueError, IndexError, TypeError) as err:  # json.JSONDecodeError is a ValueError
        check(f"A2a variants evidence files are present and well-formed (stopped at: {type(err).__name__})", False)


def _verify(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    base = sibling("verify_a2a", "verify_a2a.py")
    rd = lambda rel: h.read(res, f"A2a-variants/{rel}")  # noqa: E731
    pre, post, tools = rd("00-preflight.txt"), rd("07-post-checks.txt"), rd("01-tools.txt")
    pin = f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0"
    check("A2a variants tools: GCC 16.2.0, CMake 4.4.5, Ninja 1.13.2, the pinned clean seL4, no change to the seL4 source or to Cargo.toml and Cargo.lock, and the same tools for all eight builds",
          "compiler: aarch64-elf-gcc (GCC) 16.2.0" in tools and "cmake: cmake version 4.4.5" in tools and "ninja: 1.13.2" in tools
          and pin in tools and "tools differ" not in tools and pin in pre and pin in post
          and "seL4 source tracked diff: 0 lines" in post and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post)
    src_pat = r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$"
    a, b = records(pre, src_pat), records(post, src_pat)
    tab_pat = r"(?m)^a2a table sha256: ([0-9a-f]{64})  (\w+)$"
    ta, tb = records(pre, tab_pat), records(post, tab_pat)
    t_ok = (re.search(r"(?m)^# A2a variants preflight record, (\S+)\. Written before the builds\.$", pre) or [None, "z"])[1] < \
        (re.search(r"(?m)^# A2a variants post-run record, (\S+)$", post) or [None, ""])[1]
    check("A2a variants sources: the preflight and the post-run record name the same SHA-256 for build-a2a-variants.sh, a2a-compare.py and boot-image.py and they are the repository files; the tables of K0, K1, K2 and E1H are byte-identical to the reviewed A2a tables; the preflight is earlier",
          set(a) == set(SOURCES) and a == b
          and all((HERE / rel).is_file() and hashlib.sha256((HERE / rel).read_bytes()).hexdigest() == sha for rel, sha in a.items())
          and set(ta) == set(BASE) and ta == tb
          and all(hashlib.sha256(rb(res / f"A2a/functions-{i}.tsv")).hexdigest() == ta[i]
                  == hashlib.sha256(rb(res / f"A2a-variants/functions-{i}.tsv")).hexdigest()
                  and rb(res / f"A2a/gen_config-{i}.json") != b""
                  and rb(res / f"A2a/gen_config-{i}.json") == rb(res / f"A2a-variants/gen_config-{i}.json") for i in BASE)
          and t_ok)
    commands = rd("02-commands.txt")
    cmd = {i: base.section(commands, i) for i in IDS}
    builds = {i: rd(f"03-build-{i}.txt") for i in IDS}
    rel = "-DKernelDebugBuild=OFF" in "".join(cmd[i] for i in ("K1R", "K2R", "E1HR")) and all(
        "-DKernelDebugBuild=OFF" in cmd[i] and "-DKernelPrinting=OFF" in cmd[i] for i in ("K1R", "K2R", "E1HR"))
    check("A2a variants builds: all four exit 0 with no error line, with the commands defined in build-a2a-variants.sh: K1R, K2R and E1HR are K1, K2 and E1H with the release options; K0Q is K0's own file on the qemu-arm-virt platform (platform options before the file, nothing else)",
          all(builds[i].startswith(f"## {i}: build exit 0") and not re.search(r"(?m)^(CMake )?Error|^FAILED|error:", builds[i]) for i in IDS)
          and rel and all("kernel.elf" in cmd[i] and "kernel_all_pp_wrapper" in cmd[i] for i in IDS)
          and "-DKernelArmHypervisorSupport=OFF" in cmd["K1R"] and "KernelMaxNumNodes" not in cmd["K1R"]
          and "-DKernelArmHypervisorSupport=OFF" in cmd["K2R"] and "-DKernelMaxNumNodes=4" in cmd["K2R"]
          and "-DKernelArmHypervisorSupport=ON" in cmd["E1HR"]
          and "-DKernelPlatform=qemu-arm-virt" in cmd["K0Q"] and "AARCH64_verified.cmake" in cmd["K0Q"]
          and cmd["K0Q"].index("-DKernelPlatform=qemu-arm-virt") < cmd["K0Q"].index("-C ")
          and "KernelDebugBuild" not in cmd["K0Q"] and "KernelVerificationBuild" not in cmd["K0Q"])
    cfg = {i: json.loads(rd(f"gen_config-{i}.json")) for i in BASE + IDS}
    diff = lambda x, y: sorted(k for k in set(cfg[x]) | set(cfg[y]) if cfg[x].get(k) != cfg[y].get(k))  # noqa: E731
    check("A2a variants configurations: each release variant differs from its parent in exactly the debug and printing keys (and is non-debug, non-printing); K0Q differs from K0 in exactly the platform and timer keys and is hypervisor-mode with the verification build on; K0Q differs from E1HR in exactly the verification-style keys",
          diff("K1", "K1R") == DEBUG_KEYS and diff("K2", "K2R") == DEBUG_KEYS and diff("E1H", "E1HR") == DEBUG_KEYS
          and all(cfg[i].get("DEBUG_BUILD") is False and cfg[i].get("PRINTING") is False for i in ("K1R", "K2R", "E1HR", "K0Q"))
          and diff("K0", "K0Q") == PLATFORM_KEYS and cfg["K0Q"].get("ARM_HYPERVISOR_SUPPORT") is True
          and cfg["K0Q"].get("VERIFICATION_BUILD") is True and cfg["K0Q"].get("PLAT_QEMU_ARM_VIRT") is True
          and diff("E1HR", "K0Q") == K0_KNOBS and cfg["K2R"].get("MAX_NUM_NODES") == "4" and cfg["K1R"].get("ARM_HYPERVISOR_SUPPORT") is False)
    sums: dict[str, dict[str, tuple[str, str]]] = {i: {} for i in IDS}
    for m in re.finditer(r"(?m)^(\w+) (\S+) ([0-9a-f]{64}) ([0-9a-f]{64})$", rd("04-sums.txt")):
        sums.setdefault(m[1], {})[m[2]] = (m[3], m[4])
    check("A2a variants hashes: each published gen_config.json is the hashed file and is identical in both builds; kernel_all_pp.c and kernel_all.i are the same text",
          all(sums[i].get("gen_config.json", ("", ""))[0] == hashlib.sha256((res / f"A2a-variants/gen_config-{i}.json").read_bytes()).hexdigest()
              and sums[i]["gen_config.json"][0] == sums[i]["gen_config.json"][1] and sums[i]["kernel_all_pp.c"] == sums[i]["kernel_all.i"] for i in IDS))
    repro = rd("06-reproducibility.txt")
    recorded_tables = {m[1]: (int(m[2]), m[3]) for m in re.finditer(r"(?m)^(\w+): function tables identical \((\d+) functions, sha256 ([0-9a-f]{64})\)$", repro)}
    check("A2a variants reproducibility: the function table of every variant is identical from two clean builds in different directories, and the table published is the one whose hash and count are recorded; the comparison and matrix are identical when rerun",
          set(recorded_tables) == set(IDS)
          and all(recorded_tables[i] == (sum(1 for ln in rd(f"functions-{i}.tsv").splitlines() if ln and not ln.startswith("#")),
                                         hashlib.sha256(rb(res / f"A2a-variants/functions-{i}.tsv")).hexdigest()) for i in IDS)
          and "comparison and matrix rerun on the same tables: identical" in repro and "DIFFER" not in repro)
    cross = rd("05-nm-crosscheck.txt")
    miss = {m[1]: set(m[3].split()) for m in re.finditer(r"(?m)^(\w+): (\d+) text symbols, \d+ functions extracted, \d+ symbols not extracted: ?(.*)$", cross)}
    tsv_counts = {i: sum(1 for ln in rd(f"functions-{i}.tsv").splitlines() if ln and not ln.startswith("#")) for i in IDS}
    stated = {m[1]: int(m[2]) for m in re.finditer(r"(?m)^(\w+): \d+ text symbols, (\d+) functions extracted", cross)}
    check("A2a variants completeness: every C function with code in each variant's kernel.elf (nm) is in its table; the symbols that are not are only assembly-defined entry points, vectors and data labels; the counts match the tables",
          set(miss) == set(IDS) and all(miss[i] <= base.NOT_C and len(miss[i]) >= 19 for i in IDS) and stated == tsv_counts
          and all(all(re.search(rf"(?m)^{f}\t", rd(f"functions-{i}.tsv")) for f in base.KNOWN_FUNCTIONS) for i in IDS))
    cmp_mod = sibling("a2a_compare", "a2a-compare.py")
    published = json.loads(rd("comparison.json"))
    check("A2a variants comparison: recomputed from the published tables and configurations of all eight, the comparison is the published one, and so is the property-by-function matrix",
          cmp_mod.compare(res / "A2a-variants", "K0") == published and cmp_mod.matrix(res / "A2a-variants", "K0") == rd("property-functions.tsv")
          and sorted(published["configurations"]) == sorted(BASE + IDS))


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    def row(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"A2a-variants/{path}", fn)

    return [
        ("K1R is recorded as a debug build", row("gen_config-K1R.json", lambda t: t.replace('"DEBUG_BUILD": false', '"DEBUG_BUILD": true', 1)), "A2a variants configurations"),
        ("K0Q is recorded as non-hypervisor", row("gen_config-K0Q.json", lambda t: t.replace('"ARM_HYPERVISOR_SUPPORT": true', '"ARM_HYPERVISOR_SUPPORT": false', 1)), "A2a variants configurations"),
        ("K2R's command lacks the release option", row("02-commands.txt", lambda t: t.replace("-DKernelPrinting=OFF", "", 1)), "A2a variants builds"),
        ("a variant is recorded as failed", row("03-build-E1HR.txt", lambda t: t.replace("build exit 0", "build exit 1", 1)), "A2a variants builds"),
        ("a base table is edited", row("functions-K1.tsv", lambda t: re.sub(r"(?m)^(cteRevoke\t\S+\t)([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "A2a variants sources"),
        ("a count in the published comparison is changed", row("comparison.json", lambda t: re.sub(r'"identical": (\d+)', lambda m: f'"identical": {int(m[1]) + 1}', t, count=1)), "A2a variants comparison"),
        ("the reproducibility record says a table differs", row("06-reproducibility.txt", lambda t: t.replace("K0Q: function tables identical", "K0Q: function tables DIFFER", 1)), "A2a variants reproducibility"),
        ("the nm cross-check finds a missing C function", row("05-nm-crosscheck.txt", lambda t: t.replace("symbols not extracted: ", "symbols not extracted: cteRevoke ", 1)), "A2a variants completeness"),
        ("a variant table is not the one whose hash is recorded", row("06-reproducibility.txt", lambda t: re.sub(r"(?m)^(K1R: function tables identical \(\d+ functions, sha256 )([0-9a-f])", lambda m: m[1] + ("0" if m[2] != "0" else "1"), t, count=1)), "A2a variants reproducibility"),
        ("a variant table is edited consistently with the comparison files but not with its recorded hash", row("functions-K1R.tsv", lambda t: t + "zzz_added\tsrc/object/cnode.c\t" + "0" * 64 + "\t1\n"), "A2a variants reproducibility"),
        ("the nm cross-check file is missing", lambda root: (root / "A2a-variants/05-nm-crosscheck.txt").unlink(), "A2a variants evidence files are present and well-formed"),
        ("a source hash differs between the records", row("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )[0-9a-f](?=[0-9a-f]{63}  build-a2a-variants.sh)", r"\g<1>0", t, count=1)), "A2a variants sources"),
    ]
