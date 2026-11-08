#!/usr/bin/env python3
"""Compare the original A1 build with the rerun that used the corrected Cargo.lock.

    compare-a1-runs.py --orig DIR --new DIR --rerun1-image FILE [--work DIR]

DIR holds a finished build.sh output (kernel.elf, sel4-kernel-loader.elf, s1-root-task.elf, image.elf,
sel4-install/, rust-sel4-host-target/). --rerun1-image is the image of the rerun's first clean build, and
--new is its second. The script only reads them. It accounts for every byte that differs, so that the
difference is stated, not just noticed:

1. hashes of the four outputs;
2. the root task: section sizes and contents, instruction words, and the Cargo build-script directory
   name that is embedded in a panic-location string;
3. the boot image: a control that add-payload reproduces the original image from the original inputs, then
   an image made from the original inputs plus the new root task, compared with the original image
   (expected: only bytes of the root task's loaded segments, each placed in a named part of the ELF) and
   with the new image (expected: only device-tree seed bytes);
4. the two rerun images against each other (expected: only device-tree seed bytes).

Needs aarch64-elf-readelf, aarch64-elf-objcopy, aarch64-elf-objdump and dtc on PATH. It reads the preserved
outputs in place and writes only to --work (or a temporary directory). Spike code, stdlib only. Exit code 0 when
every difference is accounted for.
"""
import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

OUTPUTS = ("kernel.elf", "sel4-kernel-loader.elf", "s1-root-task.elf", "image.elf")
SEL4_SYS_BUILD = "root-task-target/aarch64-sel4/release/build/sel4-sys"
DTB = "sel4-install/support/kernel.dtb"
ADD_PAYLOAD = "rust-sel4-host-target/release/sel4-kernel-loader-add-payload"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def sections(elf: Path) -> dict[str, tuple[int, int]]:
    """Section name -> (file offset, size)."""
    out: dict[str, tuple[int, int]] = {}
    for line in run(["aarch64-elf-readelf", "-SW", str(elf)]).splitlines():
        m = re.match(r"^\s*\[\s*\d+\]\s+(\.\S+)\s+\S+\s+[0-9a-f]+\s+([0-9a-f]+)\s+([0-9a-f]+)", line)
        if m:
            out[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))
    return out


def load_segments(elf: Path) -> list[tuple[int, int]]:
    """(file offset, file size) of each PT_LOAD segment that has file content."""
    out: list[tuple[int, int]] = []
    for line in run(["aarch64-elf-readelf", "-lW", str(elf)]).splitlines():
        m = re.match(r"^\s*LOAD\s+0x([0-9a-f]+)\s+\S+\s+\S+\s+0x([0-9a-f]+)", line)
        if m and int(m.group(2), 16) > 0:
            out.append((int(m.group(1), 16), int(m.group(2), 16)))
    return out


def place(elf_offset: int, secs: dict[str, tuple[int, int]]) -> str:
    """Name the part of the root-task ELF that a file offset belongs to."""
    if 0x28 <= elf_offset < 0x30:
        return "ELF header e_shoff"
    for name, (off, size) in secs.items():
        if off <= elf_offset < off + size and name in (".text", ".rodata"):
            return name
    return "UNPLACED"


def section_bytes(elf: Path, name: str, work: Path) -> bytes:
    tmp = work / "section.bin"
    run(["aarch64-elf-objcopy", "-O", "binary", f"--only-section={name}", str(elf), str(tmp)])
    return tmp.read_bytes()


def instruction_words(elf: Path) -> list[str]:
    """Instruction lines with addresses kept and symbol annotations removed."""
    lines = []
    for ln in run(["aarch64-elf-objdump", "-d", str(elf)]).splitlines():
        if re.match(r"^\s+[0-9a-f]+:", ln):
            lines.append(re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", ln)).strip())
    return lines


def diff_offsets(a: bytes, b: bytes) -> list[int]:
    if len(a) != len(b):
        raise ValueError(f"different lengths: {len(a)} and {len(b)}")
    return [i for i in range(len(a)) if a[i] != b[i]]


def dts_props(blob: bytes, work: Path, tag: str) -> dict[str, str]:
    src = work / f"{tag}.dtb"
    src.write_bytes(blob)
    props: dict[str, str] = {}
    for ln in run(["dtc", "-I", "dtb", "-O", "dts", str(src)]).splitlines():
        m = re.match(r"^\s*([\w,#.+-]+) = (.*);$", ln)
        if m:
            props.setdefault(m.group(1), m.group(2))
    return props


def differing_props(a: bytes, b: bytes, work: Path) -> list[str]:
    pa, pb = dts_props(a, work, "a"), dts_props(b, work, "b")
    return sorted(k for k in set(pa) | set(pb) if pa.get(k) != pb.get(k))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--orig", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--rerun1-image", required=True)
    ap.add_argument("--work")
    args = ap.parse_args()
    orig, new, rerun1 = Path(args.orig), Path(args.new), Path(args.rerun1_image)
    ok = True

    def say(msg: str, good: bool = True) -> None:
        nonlocal ok
        ok = ok and good
        print(msg)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(args.work) if args.work else Path(tmp)
        work.mkdir(parents=True, exist_ok=True)

        print("## outputs: original run against the rerun (second build)")
        for name in OUTPUTS:
            a, b = sha(orig / name), sha(new / name)
            print(f"{name}  original {a[:16]}  rerun {b[:16]}  {'same' if a == b else 'DIFFERENT'}")
        print(f"image.elf  rerun first build {sha(rerun1)[:16]}  rerun second build {sha(new / 'image.elf')[:16]}")

        print("## root task")
        so, sn = sections(orig / "s1-root-task.elf"), sections(new / "s1-root-task.elf")
        size_diff = sorted(f"{k} {so[k][1] if k in so else None} -> {sn[k][1] if k in sn else None}"
                           for k in set(so) | set(sn) if (so.get(k) or (0, 0))[1] != (sn.get(k) or (0, 0))[1])
        print(f"section sizes that differ (bytes, decimal): {', '.join(size_diff) if size_diff else 'none'}")
        differing = {}
        for sec in sorted(so):
            if sec in (".symtab", ".strtab", ".shstrtab", ".comment"):
                continue
            a = section_bytes(orig / "s1-root-task.elf", sec, work)
            b = section_bytes(new / "s1-root-task.elf", sec, work)
            if a != b:
                differing[sec] = len(diff_offsets(a, b))
        print("loaded sections whose bytes differ: " + (", ".join(f"{k} ({v} bytes)" for k, v in differing.items())
                                                        or "none"))
        wo, wn = instruction_words(orig / "s1-root-task.elf"), instruction_words(new / "s1-root-task.elf")
        pairs = [(x, y) for x, y in zip(wo, wn) if x != y]
        kinds = sorted({x.split(" ")[2] for x, _ in pairs})
        print(f"instruction words: {len(wo)} and {len(wn)}; differing: {len(pairs)}")
        say(f"all differing instructions are address computations (adr/adrp/add): "
            f"{'yes' if set(kinds) <= {'adr', 'adrp', 'add'} else 'NO'} ({', '.join(kinds)})",
            len(wo) == len(wn) and set(kinds) <= {"adr", "adrp", "add"})
        dirs = {}
        for tag, d in (("original", orig), ("rerun", new)):
            names = sorted(p.name for p in (d / SEL4_SYS_BUILD).iterdir())
            blob = (d / "s1-root-task.elf").read_bytes()
            hits = [n for n in names if f"/sel4-sys/{n}/out/invocations.rs".encode() in blob]
            dirs[tag] = hits
            print(f"{tag}: the root task embeds the sel4-sys build-script directory name {hits}")
        say("the embedded name differs between the runs: "
            + ("yes" if dirs["original"] and dirs["rerun"] and dirs["original"] != dirs["rerun"] else "NO"),
            bool(dirs["original"] and dirs["rerun"] and dirs["original"] != dirs["rerun"]))

        print("## boot image")
        tool = orig / ADD_PAYLOAD
        say(f"add-payload tool identical in both runs: {'yes' if sha(tool) == sha(new / ADD_PAYLOAD) else 'NO'}",
            sha(tool) == sha(new / ADD_PAYLOAD))

        def build_image(prefix: Path, loader: Path, app: Path, out: Path) -> Path:
            run([str(tool), "--loader", str(loader), "--sel4-prefix", str(prefix / "sel4-install"),
                 "--app", str(app), "-o", str(out)])
            return out

        control = build_image(orig, orig / "sel4-kernel-loader.elf", orig / "s1-root-task.elf", work / "control.elf")
        say(f"control: add-payload on the original inputs reproduces the original image: "
            f"{'yes' if sha(control) == sha(orig / 'image.elf') else 'NO'}", sha(control) == sha(orig / "image.elf"))
        mixed = build_image(orig, orig / "sel4-kernel-loader.elf", new / "s1-root-task.elf", work / "mixed.elf")

        img_o, img_m, img_n = (orig / "image.elf").read_bytes(), mixed.read_bytes(), (new / "image.elf").read_bytes()
        dtb_o, dtb_n = (orig / DTB).read_bytes(), (new / DTB).read_bytes()
        at_o, at_n = img_o.find(dtb_o), img_n.find(dtb_n)
        print(f"kernel.dtb ({len(dtb_o)} bytes) sits in the original image at offset {at_o} and in the rerun image at {at_n}")

        # The root task's loaded segments are copied into the image unchanged. Locate each one, then name the
        # part of the ELF that every differing byte belongs to.
        rt_orig = (orig / "s1-root-task.elf").read_bytes()
        placed: list[tuple[int, int, int]] = []  # (image offset, elf offset, size)
        for off, size in load_segments(orig / "s1-root-task.elf"):
            at = img_o.find(rt_orig[off:off + size])
            placed.append((at, off, size))
            print(f"original root-task loaded segment (ELF file offset {off:#x}, {size} bytes) sits in the image at {at}")
        d1 = diff_offsets(img_o, img_m)
        names: dict[str, int] = {}
        for i in d1:
            hit = next((e + (i - at) for at, e, size in placed if at >= 0 and at <= i < at + size), None)
            label = "UNPLACED" if hit is None else place(hit, so)
            names[label] = names.get(label, 0) + 1
        detail = ", ".join(f"{k}: {v}" for k, v in sorted(names.items()))
        say(f"original image against (original inputs + new root task): {len(d1)} bytes differ; every one is in a "
            f"loaded segment of the root task and placed ({detail}): {'yes' if 'UNPLACED' not in names else 'NO'}",
            "UNPLACED" not in names and bool(placed) and all(at >= 0 for at, _, _ in placed))
        d2 = diff_offsets(img_m, img_n)
        want = [at_o + i for i in diff_offsets(dtb_o, dtb_n)]
        inside2 = d2 == want and at_o == at_n and at_o >= 0
        props = differing_props(dtb_o, dtb_n, work)
        say(f"(original inputs + new root task) against the rerun image: {len(d2)} bytes differ; exactly the "
            f"kernel.dtb bytes that differ: {'yes' if inside2 else 'NO'}; device-tree properties that differ: "
            f"{', '.join(props)}", inside2 and set(props) <= {"rng-seed", "kaslr-seed"})

        img_r1 = rerun1.read_bytes()
        d3 = diff_offsets(img_r1, img_n)
        in_dtb = all(at_n <= i < at_n + len(dtb_n) for i in d3)
        props3 = differing_props(img_r1[at_n:at_n + len(dtb_n)], dtb_n, work)
        say(f"rerun first build against rerun second build: {len(d3)} bytes differ; all inside kernel.dtb: "
            f"{'yes' if in_dtb else 'NO'}; device-tree properties that differ: {', '.join(props3)}",
            in_dtb and set(props3) <= {"rng-seed", "kaslr-seed"})

    print(f"\nall differences accounted for: {'yes' if ok else 'NO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
