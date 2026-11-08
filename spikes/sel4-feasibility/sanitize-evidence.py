#!/usr/bin/env python3
"""Make public, sanitized copies of the raw A1 and A3 evidence logs.

    sanitize-evidence.py [--raw DIR] [--out DIR]

Reads every file under RAW/A1 and RAW/A3 (default RAW=results-raw, kept locally and gitignored) and
writes a sanitized copy to OUT/A1 and OUT/A3 (default OUT=results), plus OUT/evidence-manifest.txt.
It never modifies RAW. The identifying values (home directory, user name, host name, repository
path) are read from the live environment, so this file contains none of them. Rules, in order:

1. repository path -> <REPO>; scratch and temp directories -> <SCRATCH> and <TMPDIR>;
   home directory -> <HOME>; user name -> <user>; host name -> <host>.
2. Homebrew tap-trust warnings and bare tap listings (they name unrelated third-party taps) are
   replaced by one note each.
3. Homebrew inventories (`brew list --versions`) are cut to the formulae needed to reproduce A1 and
   A3 (ALLOWLIST), with a count and a SHA-256 of the full list so the omission is checkable.
4. 04-brew-drift-summary.txt records that the before and after inventories differ only by the two
   formulae installed for A1, with the hashes that support it.

Measurements, errors, tool versions and hashes are not touched. CRLF line endings become LF. Spike code, stdlib only.
"""
import argparse
import getpass
import hashlib
import os
import re
import socket
import sys
from pathlib import Path

# Formulae kept in a Homebrew inventory: the build tools the plan names, the compiler's runtime
# libraries, and the interpreters and helpers the build used.
ALLOWLIST = {
    "qemu", "cmake", "ninja", "dtc", "aarch64-elf-gcc", "aarch64-elf-binutils", "lz4", "gmp", "isl",
    "libmpc", "mpfr", "zstd", "xz", "python@3.12", "python@3.15", "protobuf", "cpio", "git", "libxml2",
    "libarchive",
}
INVENTORY_HEAD = "## brew list --versions (before)"
INVENTORY_END = "## brew pinned (before)"
TAP_START = "Warning: The following taps are not trusted:"
TAP_END = "https://docs.brew.sh/Tap-Trust"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Redactor:
    def __init__(self, repo: Path) -> None:
        home = str(Path.home())
        user = getpass.getuser()
        host = socket.gethostname()
        short = host.split(".")[0]
        self.rules: list[tuple[re.Pattern[str], str]] = [
            (re.compile(re.escape(str(repo))), "<REPO>"),
            (re.compile(r"/private/tmp/claude-[0-9]+/\S*"), "<SCRATCH>"),
            (re.compile(r"/private/var/folders/[^/\s]+/[^/\s]+/T"), "<TMPDIR>"),
            (re.compile(r"/var/folders/[^/\s]+/[^/\s]+/T"), "<TMPDIR>"),
            (re.compile(re.escape(home)), "<HOME>"),
            (re.compile(re.escape(user)), "<user>"),
        ]
        for name in {host, short}:
            if name and name not in ("localhost",):
                self.rules.append((re.compile(re.escape(name)), "<host>"))

    def apply(self, text: str) -> str:
        for pattern, repl in self.rules:
            text = pattern.sub(repl, text)
        return text


def drop_tap_warning(text: str) -> str:
    out: list[str] = []
    skipping = False
    for line in text.splitlines(keepends=True):
        if not skipping and line.startswith(TAP_START):
            skipping = True
            out.append("[Homebrew tap-trust warning omitted: it listed unrelated third-party taps]\n")
            continue
        if skipping:
            if TAP_END in line:
                skipping = False
            continue
        out.append(line)
    return "".join(out)


TAP_LINE = re.compile(r"^ {2}[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\s*$")


def drop_tap_fragments(text: str) -> str:
    """Remove bare indented `owner/repo` lines, which in a brew log are tap listings."""
    kept = [ln for ln in text.splitlines(keepends=True) if not TAP_LINE.match(ln)]
    if len(kept) != len(text.splitlines(keepends=True)):
        kept.insert(0, "[Homebrew tap listing omitted: it named unrelated third-party taps]\n")
    return "".join(kept)


def formula_of(line: str) -> str:
    return line.split(" ", 1)[0].strip()


def cut_inventory(lines: list[str]) -> list[str]:
    kept = [ln for ln in lines if formula_of(ln) in ALLOWLIST]
    omitted = len(lines) - len(kept)
    full = sha256_text("\n".join(sorted(ln.rstrip("\n") for ln in lines)) + "\n")
    kept.append(f"# {omitted} further formulae omitted: not needed to reproduce A1 or A3. "
                f"SHA-256 of the full sorted list: {full}\n")
    return kept


def inventory_in_baseline(text: str) -> str:
    out: list[str] = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].startswith(INVENTORY_HEAD):
            j = i + 1
            block: list[str] = []
            while j < len(lines) and not lines[j].startswith(INVENTORY_END):
                block.append(lines[j])
                j += 1
            out.extend(cut_inventory([b for b in block if b.strip()]))
            i = j
            continue
        i += 1
    return "".join(out)


def drift_summary(raw: Path) -> str:
    base = (raw / "A1" / "00-baseline.txt").read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(base) if ln.startswith(INVENTORY_HEAD)) + 1
    end = next(i for i, ln in enumerate(base) if ln.startswith(INVENTORY_END))
    before = sorted(ln for ln in base[start:end] if ln.strip())
    after = sorted(ln for ln in (raw / "A1" / "04-brew-after.txt").read_text(encoding="utf-8").splitlines()
                   if ln.strip())
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    only_new = [ln for ln in after if ln not in added]
    ok = only_new == before
    return (
        "# Homebrew drift check, from the full unredacted inventories (kept locally)\n"
        f"formulae before: {len(before)}   after: {len(after)}\n"
        f"added ({len(added)}):\n" + "".join(f"  + {ln}\n" for ln in added) +
        f"removed or changed ({len(removed)}):\n" + "".join(f"  - {ln}\n" for ln in removed) +
        f"after minus the added lines equals before: {ok}\n"
        f"SHA-256 of the full sorted 'before' list: {sha256_text(chr(10).join(before) + chr(10))}\n"
        f"SHA-256 of the full sorted 'after' list:  {sha256_text(chr(10).join(after) + chr(10))}\n"
    )


def sanitize(name: str, text: str, red: Redactor) -> str:
    text = drop_tap_warning(text)
    if "brew" in name:
        text = drop_tap_fragments(text)
    if name == "A1/00-baseline.txt":
        text = inventory_in_baseline(text)
    elif name == "A1/04-brew-after.txt":
        text = "".join(cut_inventory([ln for ln in text.splitlines(keepends=True) if ln.strip()]))
    # QEMU serial output uses CRLF. Git stores LF, so write LF: the manifest hashes then match a clone.
    return red.apply(text).replace("\r\n", "\n")


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--raw", default=str(here / "results-raw"))
    ap.add_argument("--out", default=str(here / "results"))
    args = ap.parse_args()
    raw, out = Path(args.raw), Path(args.out)
    repo = here.parents[1]
    if not (raw / "A1").is_dir() or not (raw / "A3").is_dir():
        print(f"error: {raw}/A1 and {raw}/A3 are required", file=sys.stderr)
        return 2
    red = Redactor(repo)
    manifest = ["# raw SHA-256  sanitized SHA-256  path (relative to results/). Raw files are kept locally.\n"]
    for src in sorted(p for p in raw.rglob("*") if p.is_file()):
        rel = src.relative_to(raw).as_posix()
        try:
            text = src.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            print(f"error: {rel} is not UTF-8 text", file=sys.stderr)
            return 2
        clean = sanitize(rel, text, red)
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="") as fh:
            fh.write(clean)
        manifest.append(f"{sha256_file(src)}  {sha256_file(dst)}  {rel}\n")
    (out / "A1" / "04-brew-drift-summary.txt").write_text(drift_summary(raw), encoding="utf-8")
    with open(out / "evidence-manifest.txt", "w", encoding="utf-8") as fh:
        fh.writelines(manifest)
    print(f"sanitized {len(manifest) - 1} files into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
