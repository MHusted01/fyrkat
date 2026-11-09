#!/usr/bin/env python3
"""Make public, sanitized copies of the raw logs of one experiment (E1, E2, E3 style) and list them in the manifest.

    sanitize-run.py EXPERIMENT [--raw DIR] [--out DIR]

Reads every file under RAW/EXPERIMENT (default RAW=results-raw, kept locally and gitignored) and writes a
sanitized copy to OUT/EXPERIMENT (default OUT=results), then replaces that experiment's lines in
OUT/evidence-manifest.txt (raw SHA-256, sanitized SHA-256, path) and leaves every other line alone. It never modifies
RAW. It uses the same redaction rules as sanitize-evidence.py (repository path, scratch and temp directories, home
directory, user name, host name), read from the live environment, and turns CRLF into LF. Measurements, errors, tool
versions and hashes are not touched. Exit code 2 on any error found before writing (a file that is not UTF-8, a
malformed manifest line, a file in OUT/EXPERIMENT that RAW does not have), with nothing written; an error while
writing is reported with exit code 2 and may leave a partial result. Spike code, stdlib only.
"""
import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path


def load_redactor(here: Path):
    """The Redactor class of sanitize-evidence.py (its file name has a hyphen, so it cannot be imported by name)."""
    spec = importlib.util.spec_from_file_location("sanitize_evidence", here / "sanitize-evidence.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sanitize-evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Redactor


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("experiment", help="directory name under RAW, for example E3")
    ap.add_argument("--raw", default=str(here / "results-raw"))
    ap.add_argument("--out", default=str(here / "results"))
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.experiment):
        print("error: the experiment name must be a plain directory name", file=sys.stderr)
        return 2
    raw, out = Path(args.raw) / args.experiment, Path(args.out)
    if not raw.is_dir():
        print(f"error: {raw} is not a directory", file=sys.stderr)
        return 2
    red = load_redactor(here)(here.parents[1])
    cleaned: list[tuple[Path, str, str]] = []
    for src in sorted(p for p in raw.rglob("*") if p.is_file()):
        rel = f"{args.experiment}/{src.relative_to(raw).as_posix()}"
        try:
            text = src.read_bytes().decode("utf-8")
            cleaned.append((src, rel, red.apply(text.replace("\r\n", "\n"))))
        except (UnicodeDecodeError, ValueError) as err:
            print(f"error: {rel}: {err}", file=sys.stderr)
            return 2
    manifest_path = out / "evidence-manifest.txt"
    kept: list[str] = []
    try:
        for ln in manifest_path.read_text(encoding="utf-8").splitlines(keepends=True):
            if ln.startswith("#") or not ln.strip():
                kept.append(ln)
                continue
            fields = ln.split(None, 2)
            if len(fields) != 3:
                print(f"error: malformed manifest line: {ln.strip()!r}", file=sys.stderr)
                return 2
            if not fields[2].strip().startswith(args.experiment + "/"):
                kept.append(ln)
    except OSError as err:
        print(f"error: cannot read the manifest: {err}", file=sys.stderr)
        return 2
    expected = {rel for _src, rel, _clean in cleaned}
    stale = sorted(p.relative_to(out).as_posix() for p in (out / args.experiment).rglob("*")
                   if p.is_file() and p.relative_to(out).as_posix() not in expected) if (out / args.experiment).is_dir() else []
    if stale:
        print(f"error: {out / args.experiment} has files that {raw} does not: {stale}; remove them first", file=sys.stderr)
        return 2
    try:
        for src, rel, clean in cleaned:
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "w", encoding="utf-8", newline="") as fh:
                fh.write(clean)
            kept.append(f"{sha256_file(src)}  {sha256_file(dst)}  {rel}\n")
        manifest_path.write_text("".join(kept), encoding="utf-8")
    except OSError as err:
        print(f"error: while writing: {err}", file=sys.stderr)
        return 2
    print(f"sanitized {len(cleaned)} files into {out / args.experiment}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
