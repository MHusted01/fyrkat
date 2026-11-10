"""A2a (assurance classification) checks for verify-evidence.py. Spike code, stdlib only.

Loaded by verify-evidence.py by file path, so it imports nothing from it: the helpers it needs are passed in as `h`
(a namespace with `read`, `E1_PINS`). It reads the sanitized files in results/A2a, and the published A1 and E1
configurations for comparison. It also loads a2a-compare.py from this directory and **recomputes the whole comparison
from the published function tables and configurations**, so the published numbers cannot be edited apart from their inputs.

What the checks establish, and what they do not: that the four kernels were built with the recorded tools, commands and
configurations, that the function tables are complete (every C function with code in each kernel.elf is in them) and
reproducible across two clean builds, and that the comparison is the one the tables give. They do not establish
anything about formal verification: textual identity with K0 is not proof applicability.
"""
import hashlib
import importlib.util
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
IDS = ("K0", "K1", "K2", "E1H")
SOURCES = ("build-a2a.sh", "a2a-compare.py", "boot-image.py")
# Assembly-defined entry points and vectors, and data labels, that nm lists as text symbols but that have no C
# definition in the preprocessed kernel (the roughly 340 lines of assembly that the proofs assume correct).
NOT_C = {"_start", "arm_vector_table", "avail_p_regs", "cur_el_da", "cur_el_ia", "cur_el_inv", "cur_el_irq", "cur_el_sync",
         "el0_user", "idle_thread", "invalid_vector_entry", "kernel_device_frames", "kernel_device_reserved_regions",
         "ki_boot_end", "lel_da", "lel_ia", "lel_syscall", "lockTLBEntry", "lower_el_irq", "lower_el_sync"}
KNOWN_FUNCTIONS = ("cteRevoke", "cteDelete", "decodeCNodeInvocation", "handleSyscall", "deriveCap", "invokeUntyped_Retype")


def load_compare() -> Any:
    spec = importlib.util.spec_from_file_location("a2a_compare", HERE / "a2a-compare.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load a2a-compare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def src_records(text: str) -> dict[str, str]:
    return {m[2]: m[1] for m in re.finditer(r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$", text)}


def sources_ok(pre: str, post: str) -> bool:
    a, b = src_records(pre), src_records(post)
    if set(a) != set(SOURCES) or a != b:
        return False
    return all((HERE / rel).is_file() and hashlib.sha256((HERE / rel).read_bytes()).hexdigest() == sha for rel, sha in a.items())


def timestamps_ok(pre: str, post: str) -> bool:
    a = re.search(r"(?m)^# A2a preflight record, (\S+)\. Written before the builds\.$", pre)
    b = re.search(r"(?m)^# A2a post-run record, (\S+)$", post)
    return a is not None and b is not None and a[1] < b[1]


def section(text: str, ident: str) -> str:
    parts = re.split(r"(?m)^(?=## )", text)
    return next((p for p in parts if p.startswith(f"## {ident}\n") or p.startswith(f"## {ident}:")), "")


def verify_a2a(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    """A2a checks. `check` records (name, ok). A missing or malformed file fails a named check and does not crash the verifier."""
    try:
        _verify_a2a(res, check, h)
        check("A2a evidence files are present and well-formed", True)
    except (OSError, KeyError, ValueError, IndexError, TypeError) as err:  # json.JSONDecodeError is a ValueError
        check(f"A2a evidence files are present and well-formed (stopped at: {type(err).__name__})", False)


def _verify_a2a(res: Path, check: Callable[[str, bool], None], h: Any) -> None:
    rd = lambda rel: h.read(res, f"A2a/{rel}")  # noqa: E731
    pre, post, tools = rd("00-preflight.txt"), rd("07-post-checks.txt"), rd("01-tools.txt")
    check("A2a tools: GCC 16.2.0 (aarch64-elf-gcc), CMake 4.4.5, Ninja 1.13.2; the pinned seL4 commit, clean; and all eight builds used these same tools",
          "compiler: aarch64-elf-gcc (GCC) 16.2.0" in tools and "cmake: cmake version 4.4.5" in tools and "ninja: 1.13.2" in tools
          and f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0" in tools and "tools differ" not in tools
          and f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0" in pre and f"seL4 HEAD: {h.E1_PINS['seL4']}; dirty files: 0" in post
          and "seL4 source tracked diff: 0 lines" in post and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post)
    check("A2a sources: the preflight and the post-run record name the same SHA-256 for build-a2a.sh, a2a-compare.py and boot-image.py, they are the files in the repository, and the preflight is earlier",
          sources_ok(pre, post) and timestamps_ok(pre, post))
    commands = rd("02-commands.txt")
    cmd = {i: section(commands, i) for i in IDS}
    builds = {i: rd(f"03-build-{i}.txt") for i in IDS}
    check("A2a builds: all four kernels built (exit 0) with no 'error' line, each with the commands the plan and the decision record define: K0 from configs/AARCH64_verified.cmake; K1 the A1 options; K2 K1 with 4 nodes; E1H K1 with hypervisor support on",
          all(builds[i].startswith(f"## {i}: build exit 0") and not re.search(r"(?m)^(CMake )?Error|^FAILED|error:", builds[i]) for i in IDS)
          and "-C " in cmd["K0"] and "configs/AARCH64_verified.cmake" in cmd["K0"] and "KernelPlatform" not in cmd["K0"]
          and all("ninja" in cmd[i] and "kernel.elf" in cmd[i] and "kernel_all_pp_wrapper" in cmd[i] for i in IDS)
          and all("-DKernelPlatform=qemu-arm-virt" in cmd[i] and "-DKernelVerificationBuild=OFF" in cmd[i] and "-DARM_CPU=cortex-a57" in cmd[i] for i in ("K1", "K2", "E1H"))
          and "-DKernelArmHypervisorSupport=OFF" in cmd["K1"] and "-DKernelArmHypervisorSupport=OFF" in cmd["K2"]
          and "-DKernelArmHypervisorSupport=ON" in cmd["E1H"]
          and "KernelMaxNumNodes" not in cmd["K1"] and "-DKernelMaxNumNodes=4" in cmd["K2"] and "KernelMaxNumNodes" not in cmd["E1H"])
    cfg = {i: json.loads(rd(f"gen_config-{i}.json")) for i in IDS}
    a1 = json.loads(h.read(res, "A1/kernel-gen_config.json")) if (res / "A1/kernel-gen_config.json").is_file() else None
    e1 = json.loads(h.read(res, "E1/02-kernel-gen_config.json")) if (res / "E1/02-kernel-gen_config.json").is_file() else None
    k = cfg["K0"]
    check("A2a configurations: K0 is a hypervisor-mode, verification-build, release kernel for the tx2 platform (1 node, non-MCS, no SMMU); K1 equals A1's recorded kernel configuration; E1H equals E1's; K2 differs from K1 in exactly ENABLE_SMP_SUPPORT and MAX_NUM_NODES (=4)",
          k.get("ARM_HYPERVISOR_SUPPORT") is True and k.get("VERIFICATION_BUILD") is True and k.get("DEBUG_BUILD") is False
          and k.get("PRINTING") is False and k.get("MAX_NUM_NODES") == "1" and k.get("KERNEL_MCS") is False and k.get("ARM_SMMU") is False
          and k.get("PLAT_TX2") is True
          and cfg["K1"] == a1 and cfg["E1H"] == e1 and cfg["K1"].get("ARM_HYPERVISOR_SUPPORT") is False
          and sorted(x for x in set(cfg["K1"]) | set(cfg["K2"]) if cfg["K1"].get(x) != cfg["K2"].get(x)) == ["ENABLE_SMP_SUPPORT", "MAX_NUM_NODES"]
          and cfg["K2"].get("MAX_NUM_NODES") == "4")
    sums: dict[str, dict[str, tuple[str, str]]] = {i: {} for i in IDS}
    for m in re.finditer(r"(?m)^(\w+) (\S+) ([0-9a-f]{64}) ([0-9a-f]{64})$", rd("04-sums.txt")):
        sums.setdefault(m[1], {})[m[2]] = (m[3], m[4])
    check("A2a hashes: each configuration's published gen_config.json is the file whose hash is recorded and is identical in both builds; kernel_all_pp.c and kernel_all.i are the same text; all four kernel.elf are distinct",
          all(sums[i].get("gen_config.json", ("", ""))[0] == hashlib.sha256((res / f"A2a/gen_config-{i}.json").read_bytes()).hexdigest()
              and sums[i]["gen_config.json"][0] == sums[i]["gen_config.json"][1]
              and sums[i]["kernel_all_pp.c"] == sums[i]["kernel_all.i"] for i in IDS)
          and len({sums[i]["kernel.elf"][0] for i in IDS}) == 4)
    repro = rd("06-reproducibility.txt")
    recorded_tables = {m[1]: (int(m[2]), m[3]) for m in re.finditer(r"(?m)^(\w+): function tables identical \((\d+) functions, sha256 ([0-9a-f]{64})\)$", repro)}
    check("A2a reproducibility: the function table of every configuration is identical from two clean builds in different directories, and the table published is the one whose hash and count are recorded; the comparison and the matrix are identical when rerun",
          set(recorded_tables) == set(IDS)
          and all(recorded_tables[i] == (sum(1 for ln in rd(f"functions-{i}.tsv").splitlines() if ln and not ln.startswith("#")),
                                         hashlib.sha256((res / f"A2a/functions-{i}.tsv").read_bytes()).hexdigest()) for i in IDS)
          and "comparison and matrix rerun on the same tables: identical" in repro and "DIFFER" not in repro)
    cross = rd("05-nm-crosscheck.txt")
    miss = {m[1]: set(m[3].split()) for m in re.finditer(r"(?m)^(\w+): (\d+) text symbols, \d+ functions extracted, \d+ symbols not extracted: ?(.*)$", cross)}
    tsv_counts = {i: sum(1 for ln in rd(f"functions-{i}.tsv").splitlines() if ln and not ln.startswith("#")) for i in IDS}
    stated = {m[1]: int(m[2]) for m in re.finditer(r"(?m)^(\w+): \d+ text symbols, (\d+) functions extracted", cross)}
    check("A2a completeness: every C function with code in each kernel.elf (nm) is in its function table; the symbols that are not are exactly the assembly-defined entry points, vectors and data labels; the counts match the tables",
          set(miss) == set(IDS) and all(miss[i] == NOT_C for i in IDS) and stated == tsv_counts
          and all(all(re.search(rf"(?m)^{f}\t", rd(f"functions-{i}.tsv")) for f in KNOWN_FUNCTIONS) for i in IDS))
    cmp_mod = load_compare()
    again = cmp_mod.compare(res / "A2a", "K0")
    published = json.loads(rd("comparison.json"))
    tables = sorted(p.name[len("functions-"):-len(".tsv")] for p in (res / "A2a").glob("functions-*.tsv"))
    configs = sorted(p.name[len("gen_config-"):-len(".json")] for p in (res / "A2a").glob("gen_config-*.json"))
    check("A2a comparison: the configurations published are exactly K0, K1, K2 and E1H; recomputed from their function tables and configurations, the comparison is the published one, and the property-by-function matrix is the published one",
          tables == sorted(IDS) == configs and sorted(published["configurations"]) == sorted(IDS)
          and again == published and cmp_mod.matrix(res / "A2a", "K0") == rd("property-functions.tsv"))


def self_test_cases(edit: Callable[..., Callable[[Path], None]]) -> list[tuple[str, Callable[[Path], None], str]]:
    """Corruptions of a copy of the evidence, each with a substring of the check that must fail."""
    def first_row(path: str, fn: Callable[[str], str]) -> Callable[[Path], None]:
        return edit(f"A2a/{path}", fn)

    def flip_hash(t: str) -> str:
        m = re.search(r"(?m)^(cteRevoke\t\S+\t)([0-9a-f])", t)
        return t.replace(m[0], m[1] + ("0" if m[2] != "0" else "1"), 1) if m else t

    def add_k9(root: Path) -> None:
        (root / "A2a/functions-K9.tsv").write_text((root / "A2a/functions-K1.tsv").read_text(encoding="utf-8"), encoding="utf-8")
        (root / "A2a/gen_config-K9.json").write_text((root / "A2a/gen_config-K1.json").read_text(encoding="utf-8"), encoding="utf-8")

    def drop_table(root: Path) -> None:
        (root / "A2a/functions-K2.tsv").unlink()

    return [
        ("K0 is recorded as a non-hypervisor kernel", first_row("gen_config-K0.json", lambda t: t.replace('"ARM_HYPERVISOR_SUPPORT": true', '"ARM_HYPERVISOR_SUPPORT": false', 1)), "A2a configurations"),
        ("K2 also differs from K1 in a third key", first_row("gen_config-K2.json", lambda t: t.replace('"PRINTING": true', '"PRINTING": false', 1)), "A2a configurations"),
        ("a different compiler is recorded", first_row("01-tools.txt", lambda t: t.replace("GCC) 16.2.0", "GCC) 15.3.1", 1)), "A2a tools"),
        ("a build is recorded as failed", first_row("03-build-K1.txt", lambda t: t.replace("build exit 0", "build exit 2", 1)), "A2a builds"),
        ("K2's command lacks the 4 nodes", first_row("02-commands.txt", lambda t: t.replace("-DKernelMaxNumNodes=4", "", 1)), "A2a builds"),
        ("a function's hash is changed in K1's table", first_row("functions-K1.tsv", flip_hash), "A2a comparison"),
        ("a count in the published comparison is changed", first_row("comparison.json", lambda t: re.sub(r'"identical": (\d+)', lambda m: f'"identical": {int(m[1]) + 1}', t, count=1)), "A2a comparison"),
        ("the property matrix is edited", first_row("property-functions.tsv", lambda t: t.replace("\t!\t", "\t=\t", 1)), "A2a comparison"),
        ("the reproducibility record says a table differs", first_row("06-reproducibility.txt", lambda t: t.replace("K1: function tables identical", "K1: function tables DIFFER", 1)), "A2a reproducibility"),
        ("the nm cross-check finds a missing C function", first_row("05-nm-crosscheck.txt", lambda t: t.replace("symbols not extracted: ", "symbols not extracted: cteRevoke ", 1)), "A2a completeness"),
        ("cteRevoke is missing from K0's table", first_row("functions-K0.tsv", lambda t: re.sub(r"(?m)^cteRevoke\t.*\n", "", t, count=1)), "A2a completeness"),
        ("the post-run record names another hash for a2a-compare.py", first_row("07-post-checks.txt", lambda t: re.sub(r"(?m)^(src sha256: )[0-9a-f](?=[0-9a-f]{63}  a2a-compare.py)", r"\g<1>0", t, count=1)), "A2a sources"),
        ("only the hash recorded in the reproducibility record is changed", first_row("06-reproducibility.txt", lambda t: re.sub(r"(K1: function tables identical \(\d+ functions, sha256 )[0-9a-f]", lambda m: m[1] + ("0" if m[0][-1] != "0" else "1"), t, count=1)), "A2a reproducibility"),
        ("a fifth configuration is added", add_k9, "A2a comparison"),
        ("a function table is missing", drop_table, "A2a evidence files are present and well-formed"),
        ("a gen_config hash differs between the two builds", first_row("04-sums.txt", lambda t: re.sub(r"(?m)^(K1 gen_config.json [0-9a-f]{64} )[0-9a-f]", r"\g<1>0", t, count=1)), "A2a hashes"),
    ]
