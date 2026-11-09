"""E3 (capability revocation) checks for verify-evidence.py. Spike code, stdlib only.

Loaded by verify-evidence.py by file path, so it imports nothing from it: the helpers it needs are passed in as `h`
(a namespace with `read`, `sums`, `in_order`, `guest_output`, `section`, `E1_PINS`). It reads only sanitized files in
results/E3 (and E1's post-run record for comparison), and the source files named in the evidence, from the directory
this file is in.

What the checks establish, and what they do not: the log is produced by the E3 root task and tasks, so every claim
here is "the program reported this". The refusals are corroborated by the kernel's own debug lines, which the program
does not print. Nothing here is a proof about seL4's revocation in general.
"""
import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
IDS = (1, 2)
FAILURE = re.compile(r"E3_FAIL|panic|halt|assert|abort|exception|fault|!!!", re.IGNORECASE)
PROBE = re.compile(r"(?m)^E3_ROOT (before|after|fresh): task (\d) slot (\d) copy (ok|refused) ?(?:\((\w+)\))?$")
REVOKE = "E3_ROOT revoke step\n"
REVOKED = "E3_ROOT revoke returned\n"
SOURCES = ("crates/e2-root-task/src/bin/e3_root_task.rs", "crates/e2-root-task/src/e3_spawn.rs",
           "crates/e2-task/src/bin/e3_task.rs", "crates/e2-task/src/e3_abi.rs", "crates/e2-task/src/lib.rs",
           "build-e3.sh", "build-e2.sh", "boot-image.py")
E2_SOURCES = ("crates/e2-task/src/abi.rs", "crates/e2-task/src/runtime.rs", "crates/e2-task/src/bin/client.rs",
              "crates/e2-task/src/bin/server.rs", "crates/e2-root-task/src/main.rs",
              "crates/e2-root-task/src/child_vspace.rs", "crates/e2-root-task/src/object_allocator.rs")
# A refused copy is a lookup of an empty source slot; the error is recorded, and the same for every refusal.
REFUSED = "FailedLookup"


def _lines(task: int, phase_lines: list[str]) -> list[str]:
    return [ln.replace("{t}", str(task)) for ln in phase_lines]


def sequence() -> list[str]:
    """The regular expressions that must match, each after the previous, in the guest output of every boot."""
    seq = [r"Bootstrapping kernel", r"Booting all finished, dropped to user space", r"(?m)^E3_ROOT start$",
           r"(?m)^E3_ROOT mutant=none$",
           r"(?m)^E3_ROOT built: P, Q, 2 tasks with derived, copy and control capabilities$",
           r"(?m)^E3_ROOT before: P in the root task's CNode copy ok$"]
    for t in IDS:
        seq += _lines(t, [r"(?m)^E3_ROOT recv on P: task {t} badge=0xb30{t} code=0x100$",
                          r"(?m)^E3_TASK {t} before: derived slot served$",
                          r"(?m)^E3_ROOT recv on P: task {t} badge=0xb30{t} code=0x200$",
                          r"(?m)^E3_TASK {t} before: copy slot served$",
                          r"(?m)^E3_ROOT recv on Q: task {t} badge=0xd30{t} code=0x300$",
                          r"(?m)^E3_TASK {t} before: control slot served$",
                          r"(?m)^E3_ROOT event from task {t}$"])
    seq += [r"(?m)^E3_ROOT revoke step$", r"(?m)^E3_ROOT revoke P$", r"(?m)^E3_ROOT revoke returned$",
            r"(?m)^E3_ROOT after: P in the root task's CNode copy ok$",
            r"(?m)^E3_ROOT after: Q in the root task's CNode copy ok$"]
    for t in IDS:
        seq += _lines(t, [r"(?m)^E3_TASK {t} after: derived slot refused label=[1-9][0-9]*$",
                          r"(?m)^E3_TASK {t} after: copy slot refused label=[1-9][0-9]*$",
                          r"(?m)^E3_TASK {t} after: never-populated slot refused label=[1-9][0-9]*$",
                          r"(?m)^E3_ROOT event from task {t}$",
                          r"(?m)^E3_ROOT recv on Q: task {t} badge=0xd30{t} code=0x700$",
                          r"(?m)^E3_TASK {t} after: control slot served$",
                          r"(?m)^E3_ROOT event from task {t}$"])
    for t in IDS:
        seq += _lines(t, [r"(?m)^E3_ROOT fresh: task {t} slot 7 copy ok$",
                          r"(?m)^E3_ROOT recv on P: task {t} badge=0xf30{t} code=0x800$",
                          r"(?m)^E3_TASK {t} after: fresh slot served$",
                          r"(?m)^E3_ROOT event from task {t}$"])
    return seq + [r"(?m)^E3_PASS$"]


def in_order_re(text: str, patterns: list[str]) -> bool:
    """True when every pattern matches, each starting after the end of the previous match."""
    pos = 0
    for pat in patterns:
        m = re.compile(pat).search(text, pos)
        if m is None:
            return False
        pos = m.end()
    return True


def through_marker(text: str) -> str:
    """Boot output up to and including E3_PASS, CRs removed (the line terminator after it depends on read timing)."""
    clean = text.replace("\r", "")
    return clean[: clean.find("E3_PASS") + len("E3_PASS")] if "E3_PASS" in clean else clean


def probes(text: str, phase: str) -> list[tuple[int, int, str, str]]:
    return sorted((int(m[2]), int(m[3]), m[4], m[5] or "") for m in PROBE.finditer(text) if m[1] == phase)


def expected_probes(phase: str) -> list[tuple[int, int, str, str]]:
    ok, no = ("ok", ""), ("refused", REFUSED)
    table = {"before": {1: ok, 2: ok, 3: ok, 6: no, 7: no},
             "after": {1: no, 2: no, 3: ok, 6: no, 7: no},
             "fresh": {7: ok}}[phase]
    return sorted((t, slot, *outcome) for t in IDS for slot, outcome in table.items())


def calls(text: str, ep: str) -> list[tuple[str, str, str]]:
    return re.findall(rf"(?m)^E3_ROOT recv on {ep}: task (\d) badge=0x(\w+) code=0x(\w+)$", text)


EXPECTED_CALLS = {
    ("pre", "P"): [("1", "b301", "100"), ("1", "b301", "200"), ("2", "b302", "100"), ("2", "b302", "200")],
    ("pre", "Q"): [("1", "d301", "300"), ("2", "d302", "300")],
    ("post", "P"): [("1", "f301", "800"), ("2", "f302", "800")],
    ("post", "Q"): [("1", "d301", "700"), ("2", "d302", "700")],
}
PROBLEM = re.compile(r"E3_ROOT unexpected|reached the root task|should be (?:empty|populated)|E3_FAIL")


def revocation_checks(guests: list[str]) -> dict[str, bool]:
    """Claims about the order of events around the revoke, checked in every boot."""
    parts = [g.split(REVOKE, 1) for g in guests]
    split = all(len(p) == 2 and REVOKED in p[1] for p in parts)
    if not split:
        return {"split": False}
    pre = [p[0] for p in parts]
    post = [p[1] for p in parts]
    return {
        "split": True,
        "before": all(probes(s, "before") == expected_probes("before") and not probes(s, "after")
                      and not probes(s, "fresh") for s in pre),
        "after": all(probes(s, "after") == expected_probes("after") and probes(s, "fresh") == expected_probes("fresh")
                     and not probes(s, "before") for s in post),
        # After the revoke the only calls to reach the root task on P are the fresh ones, minted after it.
        "nothing_through_revoked": all(
            [(t, b, c) for t, b, c in calls(s, "P")] == EXPECTED_CALLS[("post", "P")] for s in post)
        and not any(PROBLEM.search(g) for g in guests),
        # Every call the root task received, on either endpoint, before and after, is the expected one and no other.
        "exact_calls": all(calls(a, ep) == EXPECTED_CALLS[("pre", ep)] for a in pre for ep in ("P", "Q"))
        and all(calls(b, "Q") == EXPECTED_CALLS[("post", "Q")] for b in post),
        # The kernel's own lines (not printed by the program): a call on a null cap, a copy from an empty slot.
        # A null-cap call is made by a task (a child of the root task), a refused copy by the root task itself.
        "kernel_lines": all(
            len(re.findall(rf"child of: 'rootserver'\"[^\n]*Attempted to invoke a null cap #{n}\.", s)) == 2
            for s in post for n in (1, 2, 6))
        and all(len(re.findall(r"Attempted to invoke a null cap", s)) == 6 for s in post)
        and all(not re.search(r"Attempted to invoke a null cap", s) for s in pre)
        and all(len(re.findall(r"\"rootserver\"[^\n]*Source slot invalid or empty", s)) == 4 for s in pre)
        and all(len(re.findall(r"\"rootserver\"[^\n]*Source slot invalid or empty", s)) == 8 for s in post),
    }


def source_records(text: str) -> dict[str, str]:
    return {m[2]: m[1] for m in re.finditer(r"(?m)^src sha256: ([0-9a-f]{64})  (\S+)$", text)}


def sources_ok(pre: str, post: str) -> bool:
    """The preflight and the post-run record name the same hashes for the same files, and those are the files in the
    repository now: so the evidence is the evidence of this source and these scripts, not of an earlier edit."""
    a, b = source_records(pre), source_records(post)
    if set(a) != set(SOURCES) or a != b:
        return False
    return all((HERE / rel).is_file() and hashlib.sha256((HERE / rel).read_bytes()).hexdigest() == sha
               for rel, sha in a.items())


def timestamps_ok(pre: str, post: str) -> bool:
    a = re.search(r"(?m)^# E3 preflight record, (\S+)\. Written before the evidence build\.$", pre)
    b = re.search(r"(?m)^# E3 post-run checks, (\S+)$", post)
    return a is not None and b is not None and a[1] < b[1]


def verify_e3(res: Path, lock_text: str, e1_post: str, check: Callable[[str, bool], None], e1_present: bool,
              h: Any) -> None:
    """E3 checks. `check` records (name, ok)."""
    cfg = json.loads(h.read(res, "E3/02-kernel-gen_config.json"))
    e1cfg = json.loads(h.read(res, "E1/02-kernel-gen_config.json")) if e1_present else None
    diff = h.read(res, "E3/05-config-diff-vs-e1.txt")
    check("E3 kernel config: byte-for-key identical to E1's (hypervisor support on, 156 keys, 0 differ)",
          cfg == e1cfg and cfg.get("ARM_HYPERVISOR_SUPPORT") is True
          and "156 keys in E1-H config, 156 in E3 config, 0 differ:" in diff)
    build, post, pre = h.read(res, "E3/01-build.txt"), h.read(res, "E3/04-post-checks.txt"), h.read(res, "E3/00-preflight.txt")
    check("E3 build: succeeded (exit 0) with no error line", "BUILD_EXIT=0" in build and not re.search(r"(?m)^error", build))
    lock_hash = hashlib.sha256(lock_text.encode()).hexdigest()
    e2_list = re.search(r"E2 sources \(([^)]*)\) tracked diff vs HEAD: 0 lines", post)
    check("E3 inputs: seL4 and rust-sel4 at their pins and clean; Cargo.toml, Cargo.lock, crates/root-task and the listed "
          "E2 sources unchanged (the repository lock is the one the preflight and the post-run record name)",
          all(f"{n} HEAD: {sha}; dirty files: 0" in post for n, sha in h.E1_PINS.items())
          and "Cargo.toml and Cargo.lock tracked diff vs HEAD: 0 lines" in post
          and "crates/root-task tracked diff vs HEAD: 0 lines" in post
          and "crates/*/Cargo.toml tracked diff vs HEAD: 0 lines" in post
          and e2_list is not None and e2_list[1].split() == list(E2_SOURCES)
          and f"Cargo.lock sha256: {lock_hash}" in post and f"Cargo.lock sha256: {lock_hash}" in pre)
    check("E3 sources: the preflight and the post-run record name the same SHA-256 for the E3 sources, build-e3.sh, "
          "build-e2.sh and boot-image.py, they are the files in the repository, and the preflight is earlier",
          sources_ok(pre, post) and timestamps_ok(pre, post))
    check("E3 toolchain and host recorded (QEMU 11.1.3, GCC 16.2.0, CMake 4.4.5, nightly-2026-08-21 rustc, arm64 host)",
          "QEMU emulator version 11.1.3" in pre and "aarch64-elf-gcc (GCC) 16.2.0" in pre
          and "cmake version 4.4.5" in pre and "8925ea358 2026-08-20" in pre and "arm64" in pre)
    built = h.sums(build)
    names = {"kernel.elf", "sel4-kernel-loader.elf", "e3_task.elf", "e3_root_task.elf", "image.elf"}
    recorded = {m.group(2): m.group(1) for m in re.finditer(r"(?m)^e3 ([0-9a-f]{64})\s+(\S+)$", post)}
    e1_recorded = {m.group(2): m.group(1) for m in re.finditer(r"(?m)^e1 ([0-9a-f]{64})\s+(\S+)$", e1_post)}
    hashes_ok = set(built) == names and built == recorded
    check("E3 hash table: the build log and the post-run record agree on the five outputs; the loader is E1's loader",
          hashes_ok and built["sel4-kernel-loader.elf"] == e1_recorded.get("sel4-kernel-loader.elf"))
    built = {n: built.get(n, "") for n in names} if hashes_ok else {n: "" for n in names}
    image_line = re.search(r"image used for the boots: \S+ ([0-9a-f]{64})", post)
    boots = [h.read(res, f"E3/10-boot-{n}.txt") for n in (1, 2, 3)]
    check("E3 boots: all three used the recorded image.elf",
          image_line is not None and built["image.elf"] != "" and image_line.group(1) == built["image.elf"])
    check("E3 boots: each run's command line and footer record virt,secure=off,gic-version=2,virtualization=on "
          "under TCG, Cortex-A57, 1 vCPU",
          all("-machine virt,secure=off,gic-version=2,virtualization=on -accel tcg -cpu cortex-a57 -smp 1" in b
              and "accel=tcg cpu=cortex-a57 smp=1 gic=2 virt=True" in b for b in boots))
    guests = [h.guest_output(b) for b in boots]
    check("E3 boots: in the guest output of all three, the whole E3 sequence appears in order, ending in an E3_PASS line",
          all(in_order_re(g, sequence()) for g in guests))
    check("E3 boots: in all three, the harness reports the marker SEEN", all("marker 'E3_PASS' SEEN" in b for b in boots))
    check("E3 boots: no E3_FAIL, panic, halt, assertion, abort, exception, fault or '!!!' in the guest output of any of the three",
          not any(FAILURE.search(g) for g in guests))
    rev = revocation_checks(guests)
    check("E3 revocation: the root task's probes before the revoke found the derived, copy and control slots populated "
          "and the never-populated and fresh slots empty (FailedLookup), for both tasks",
          rev["split"] and rev["before"])
    check("E3 revocation: after the revoke, the derived and copy slots (and the never-populated and fresh-to-be slot) "
          "are empty (FailedLookup) and the control slot is populated, for both tasks; the fresh slot is populated once minted",
          rev["split"] and rev["after"])
    check("E3 revocation: after the revoke no call through a P-derived capability reached the root task (the only "
          "calls on P are the two minted after it), and no unexpected or failed-probe line appears anywhere",
          rev["split"] and rev["nothing_through_revoked"])
    check("E3 revocation: the calls the root task received on P and Q are exactly the expected ones, with the "
          "expected badges and codes, before and after the revoke", rev["split"] and rev["exact_calls"])
    check("E3 revocation: the kernel's own debug lines agree (a call on a null cap for slots 1, 2 and 6, once per "
          "task, only after the revoke; a copy from an empty slot 4 times before and 8 times after)",
          rev["split"] and rev["kernel_lines"])
    check("E3 boots: output through E3_PASS identical across the three (the line terminator after the marker "
          "depends on read timing and is excluded)", len({through_marker(g) for g in guests}) == 1)
    verify_mutants(res, built, check, h)


# name, the line that says what the root task did instead of the revoke, and the lines that must follow the revoke step
MUTANTS = {
    "M1": ("noop-revoke", "E3_ROOT mutant: no revoke",
           ("E3_ROOT after: task 1 slot 1 copy ok, but the slot should be empty",
            'E3_FAIL root: Check("a slot that should be empty is populated")')),
    "M2": ("revoke-wrong-ancestor", "E3_ROOT mutant: revoke Q, not P",
           ("E3_ROOT after: task 1 slot 1 copy ok, but the slot should be empty",
            'E3_FAIL root: Check("a slot that should be empty is populated")')),
    "M3": ("noop-revoke-blind-probes", "E3_ROOT mutant: no revoke",
           ("E3_ROOT call reached the root task: badge=0xb301 code=0x400",
            'E3_FAIL root: Check("a call arrived where the task\'s event was due")')),
    "M4": ("revoke-too-much", "E3_ROOT mutant: revoke P, then Q",
           ("E3_ROOT after: task 1 slot 3 copy refused (FailedLookup), but the slot should be populated",
            'E3_FAIL root: Check("a slot that should be populated is empty")')),
    "M5": ("revoke-task-1-only", "E3_ROOT mutant: delete task 1's slots 1 and 2, no revoke",
           ("E3_ROOT after: task 2 slot 1 copy ok, but the slot should be empty",
            'E3_FAIL root: Check("a slot that should be empty is populated")')),
    "M6": ("serve-refused", "E3_ROOT mutant: no revoke",
           ("E3_ROOT recv on P: task 1 badge=0xb301 code=0x400",
            "E3_FAIL task: a call that should be refused was served")),
}


def guest_of_mutant(section_text: str) -> str:
    """The mutant's guest output: without the header comments, the command line and the harness footer, which name the marker."""
    keep = [ln for ln in section_text.replace("\r", "").split("\n")
            if not ln.startswith(("#", "+ ", "[boot-image]", "## "))]
    return "\n".join(keep)


def verify_mutants(res: Path, built: dict[str, str], check: Callable[[str, bool], None], h: Any) -> None:
    mut = h.read(res, "E3/06-mutation-checks.txt")
    sections = {k: h.section(mut, k) for k in MUTANTS}

    def failed(k: str) -> bool:
        name, action, (stop, fail) = MUTANTS[k]
        s = sections[k]
        pre, _, post = s.partition(REVOKE)
        guest = guest_of_mutant(s)
        extra = {"M4": ("E3_ROOT after: task 1 slot 1 copy refused (FailedLookup)",),
                 "M5": ("E3_TASK 1 after: control slot served", "E3_ROOT after: task 1 slot 1 copy refused (FailedLookup)"),
                 "M3": (), "M6": ()}.get(k, ())
        return (bool(s) and f"E3_ROOT mutant={name}\n" in s and "marker 'E3_PASS' NOT seen" in s
                and "marker 'E3_PASS' SEEN" not in s and "E3_PASS" not in guest
                and "E3_TASK 2 before: control slot served" in pre and "E3_ROOT event from task 2" in pre
                and len(re.findall(r"Source slot invalid or empty", pre)) == 4
                and not re.search(r"(?m)^E3_ROOT revoke P$", s)
                and action + "\n" in post and REVOKED in post and stop in post and fail in post
                and post.index(stop) < post.index(fail)
                and all(e in post for e in extra)
                and (("E3_FAIL root" not in guest) if k == "M6" else ("E3_FAIL task" not in guest)))

    check("E3 mutation checks: all six mutants passed every check before the revoke step, did what their record says "
          "instead of the revoke, stopped at the check each is meant to reach (the root task's probe of a slot that "
          "should be empty or populated; a call reaching the root task; the task's own refusal check), and none printed "
          "E3_PASS: no revoke, the wrong ancestor, too much, one task only, probes left out, a root task that answers",
          all(failed(k) for k in MUTANTS)
          and "slot 1 copy" not in sections["M3"].partition(REVOKED)[2]
          and "slot 1 copy" not in sections["M6"].partition(REVOKED)[2])

    def sha(k: str, what: str) -> str:
        m = re.search(rf"(?m)^# {what} sha256: ([0-9a-f]{{64}})$", sections[k])
        return m.group(1) if m else ""

    roots = [sha(k, "e3_root_task.elf") for k in MUTANTS]
    check("E3 mutants: each was built against the evidence build's kernel, loader and task binary (same hashes), and "
          "only the root task and image differ, from the evidence build and from each other",
          all(built[n] != "" and sha(k, w) == built[n]
              for k in MUTANTS for w, n in (("kernel.elf", "kernel.elf"), ("sel4-kernel-loader.elf", "sel4-kernel-loader.elf"),
                                            ("e3_task.elf", "e3_task.elf")))
          and all(sha(k, "e3_root_task.elf") not in ("", built["e3_root_task.elf"])
                  and sha(k, "image.elf") not in ("", built["image.elf"]) for k in MUTANTS)
          and len(set(roots)) == len(MUTANTS))


def self_test_cases(edit: Callable[..., Callable[[Path], None]], every_boot: Callable[..., Callable[[Path], None]],
                    drop_line: Callable[[str], Callable[[str], str]]) -> list[tuple[str, Callable[[Path], None], str]]:
    """Corruptions of a copy of the evidence, each with a substring of the check that must fail."""
    def replace_in_boots(old: str, new: str) -> Callable[[Path], None]:
        return every_boot(lambda t: t.replace(old, new, 1), "E3")

    def mutants(old: str, new: str) -> Callable[[Path], None]:
        return edit("E3/06-mutation-checks.txt", lambda t: t.replace(old, new, 1))

    after = "E3_ROOT revoke returned\n"
    return [
        ("the guest never prints E3_PASS (the footer still names it)", every_boot(drop_line("E3_PASS"), "E3"),
         "whole E3 sequence appears in order"),
        ("the control slot is not served after the revoke", every_boot(drop_line("E3_TASK 1 after: control slot served"), "E3"),
         "whole E3 sequence appears in order"),
        ("a refused call after the revoke reports label 0", replace_in_boots(
            "E3_TASK 2 after: copy slot refused label=2", "E3_TASK 2 after: copy slot refused label=0"),
         "whole E3 sequence appears in order"),
        ("a derived slot still copies after the revoke", replace_in_boots(
            "E3_ROOT after: task 2 slot 2 copy refused", "E3_ROOT after: task 2 slot 2 copy ok"),
         "after the revoke, the derived and copy slots"),
        ("a refusal after the revoke carries another error", replace_in_boots(
            "E3_ROOT after: task 2 slot 2 copy refused (FailedLookup)", "E3_ROOT after: task 2 slot 2 copy refused (DeleteFirst)"),
         "after the revoke, the derived and copy slots"),
        ("a control slot no longer copies after the revoke", replace_in_boots(
            "E3_ROOT after: task 1 slot 3 copy ok", "E3_ROOT after: task 1 slot 3 copy refused (FailedLookup)"),
         "after the revoke, the derived and copy slots"),
        ("a derived slot was already empty before the revoke", replace_in_boots(
            "E3_ROOT before: task 1 slot 1 copy ok", "E3_ROOT before: task 1 slot 1 copy refused (FailedLookup)"),
         "probes before the revoke found"),
        ("a call through a derived capability reaches the root task after the revoke", replace_in_boots(
            after, after + "E3_ROOT recv on P: task 1 badge=0xb301 code=0x400\n"),
         "after the revoke no call through a P-derived capability"),
        ("an unexpected-call line before the revoke", replace_in_boots(
            "E3_ROOT built:", "E3_ROOT unexpected call on P: badge=0xb301 code=0x100\nE3_ROOT built:"),
         "after the revoke no call through a P-derived capability"),
        ("a control call after the revoke arrives with another badge", replace_in_boots(
            "E3_ROOT recv on Q: task 1 badge=0xd301 code=0x700", "E3_ROOT recv on Q: task 1 badge=0xb301 code=0x700"),
         "the calls the root task received on P and Q are exactly"),
        ("a call before the revoke is missing", every_boot(drop_line("E3_ROOT recv on P: task 2 badge=0xb302 code=0x200"), "E3"),
         "the calls the root task received on P and Q are exactly"),
        ("a kernel null-cap line is attributed to the root task instead of a task", replace_in_boots(
            "\"child of: 'rootserver'\"", "\"rootserver\""), "the kernel's own debug lines agree"),
        ("the sixth mutant's failure line comes before the call that causes it", edit(
            "E3/06-mutation-checks.txt", lambda t: re.sub(
                r"(E3_ROOT recv on P: task 1 badge=0xb301 code=0x400\n)(E3_FAIL task: [^\n]*\n)", r"\2\1", t, count=1)),
         "E3 mutation checks"),
        ("one kernel null-cap line is missing", replace_in_boots("Attempted to invoke a null cap #1.", "Attempted to invoke a null cap #9."),
         "the kernel's own debug lines agree"),
        ("an E3_FAIL line in boot 2", edit("E3/10-boot-2.txt", lambda t: t.replace(
            "E3_TASK 1 before", "E3_FAIL task: x\nE3_TASK 1 before", 1)), "no E3_FAIL, panic"),
        ("hypervisor support off in the E3 config", edit("E3/02-kernel-gen_config.json", lambda t: t.replace(
            '"ARM_HYPERVISOR_SUPPORT": true', '"ARM_HYPERVISOR_SUPPORT": false', 1)), "byte-for-key identical to E1"),
        ("a different image hash in the post-run record", edit("E3/04-post-checks.txt", lambda t: t.replace(
            "image used for the boots: external/e3-build/image.elf ", "image used for the boots: external/e3-build/image.elf 0000", 1)),
         "all three used the recorded image.elf"),
        ("the build log lacks image.elf", edit("E3/01-build.txt", lambda t: re.sub(r"(?m)^[0-9a-f]{64}  image.elf\n", "", t)),
         "E3 hash table"),
        ("the post-run record names another hash for the root-task source", edit("E3/04-post-checks.txt", lambda t: re.sub(
            r"(?m)^(src sha256: )[0-9a-f](?=[0-9a-f]{63}  crates/e2-root-task/src/bin/e3_root_task.rs)", r"\g<1>0", t, count=1)),
         "E3 sources"),
        ("the preflight names another hash for build-e3.sh", edit("E3/00-preflight.txt", lambda t: re.sub(
            r"(?m)^(src sha256: )[0-9a-f](?=[0-9a-f]{63}  build-e3.sh)", r"\g<1>0", t, count=1)),
         "E3 sources"),
        ("a mutant is recorded as having passed", mutants("marker 'E3_PASS' NOT seen", "marker 'E3_PASS' SEEN"),
         "E3 mutation checks"),
        ("a mutant's guest prints E3_PASS with a trailing space", mutants(
            "E3_FAIL root: Check(\"a slot that should be empty is populated\")",
            "E3_FAIL root: Check(\"a slot that should be empty is populated\")\nE3_PASS "), "E3 mutation checks"),
        ("a mutant's record of what it did instead of the revoke is changed", mutants(
            "E3_ROOT mutant: delete task 1's slots 1 and 2, no revoke", "E3_ROOT mutant: no revoke"), "E3 mutation checks"),
        ("the call that reached the root task in the third mutant is not recorded", mutants(
            "E3_ROOT call reached the root task: badge=0xb301 code=0x400", "E3_ROOT x"), "E3 mutation checks"),
        ("a mutant's task binary differs from the evidence build's", edit("E3/06-mutation-checks.txt", lambda t: re.sub(
            r"(?m)^(# e3_task.elf sha256: )[0-9a-f]", r"\g<1>0", t, count=1)), "each was built against the evidence build's kernel"),
    ]
