#!/usr/bin/env python3
"""A2a comparison of preprocessed seL4 kernels, function by function. Spike code, stdlib only.

    a2a-compare.py extract ID --pp kernel_all_pp.c --sel4 DIR --build DIR --out functions-ID.tsv
    a2a-compare.py compare DIR [--ref K0] --out comparison.json
    a2a-compare.py matrix DIR [--ref K0] --out property-functions.tsv
    a2a-compare.py report comparison.json [--names]
    a2a-compare.py self-test

`extract` reads one preprocessed kernel (seL4's own `kernel_all_pp.c`, the file its verification toolchain starts from),
finds every top-level function definition, and writes one line per function: name, the source file it came from, the
SHA-256 of its whitespace-normalised text, and the length of that text. Absolute paths in the text (from `__FILE__` in assertions) are
replaced by `<SEL4>` and `<BUILD>` so that the same source in two build directories gives the same hash.

`matrix` lists, for each required property, every function of its files with its status in each configuration.
`compare` reads `functions-ID.tsv` and `gen_config-ID.json` for every configuration in DIR and writes a deterministic
JSON summary: the differing configuration keys, the function-level comparison against the reference (default K0) and between
the other pairs, and the same per required property of the plan's assurance matrix (PROPERTY_FILES below). It needs
neither the compiler nor the preprocessed files, so anyone with the published `functions-*.tsv` can rerun it.

WHAT THIS IS NOT. Textual identity of a preprocessed function with the reference is a statement about text. It does not
say that a proof covers that function in this configuration: that also needs the verified-configuration assumptions to
hold (platform, build options, compiler, boot, hardware), which this script cannot know. A successful build and
equal configuration keys are not evidence of verification either. Types, macros and global data are not compared, only
function definitions.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Fixed before any comparison was run, from the plan's "Kernel code it depends on" column (a starting list, which A2a
# completes). A function belongs to a property when its source file is in the property's list. P5 is the SMMU code plus
# the P3 code that governs the reuse of memory (the kernel's part of a user-level SMMU server design, K3).
P3_FILES = ("src/object/cnode.c", "src/object/objecttype.c", "src/object/untyped.c", "src/kernel/cspace.c",
            "src/arch/arm/64/object/objecttype.c")
PROPERTY_FILES = {
    "P1 address-space isolation": ("src/arch/arm/64/kernel/vspace.c", "src/arch/arm/64/object/objecttype.c",
                                   "src/object/untyped.c"),
    "P2 authority integrity": ("src/object/cnode.c", "src/kernel/cspace.c", "src/object/objecttype.c",
                               "src/arch/arm/64/object/objecttype.c", "src/object/endpoint.c", "src/object/notification.c"),
    "P3 revocation and reclamation": P3_FILES,
    "P4 kernel integrity": ("src/api/syscall.c", "src/api/faults.c", "src/arch/arm/api/faults.c", "src/kernel/faulthandler.c",
                            "src/arch/arm/64/c_traps.c", "src/arch/arm/c_traps.c", "src/fastpath/fastpath.c"),
    "P5 DMA confinement (kernel part)": ("src/arch/arm/object/smmu.c", "src/arch/arm/object/iospace.c",
                                         "src/drivers/smmu/smmuv2.c") + P3_FILES,
}
LINEMARK = re.compile(r'^#\s+\d+\s+"([^"]*)"')


def strip_balanced(text: str, keyword: str) -> str:
    """Remove every `keyword ( ... )` (balanced) from TEXT, such as `__attribute__((...))`."""
    out, i = [], 0
    pat = re.compile(rf"\b{keyword}\b\s*\(")
    while True:
        m = pat.search(text, i)
        if m is None:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:m.start()])
        depth, j = 1, m.end()
        while j < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            j += 1
        i = j


def function_name(header: str) -> str | None:
    """The name of a function definition from the text before its `{`, or None when it is not one."""
    h = header
    for kw in ("__attribute__", "__asm__", "__asm", "asm", "__extension__"):
        h = strip_balanced(h, kw)
    h = h.strip()
    if not h.endswith(")") or h.startswith("typedef") or "(" not in h:
        return None
    m = re.search(r"([A-Za-z_]\w*)\s*$", h[: h.index("(")])
    return m.group(1) if m else None


def normalise(text: str, roots: dict[str, str]) -> str:
    for path, tag in roots.items():
        text = text.replace(path, tag)
    return re.sub(r"\s+", " ", text).strip()


def relative(file: str, roots: dict[str, str]) -> str:
    for path, tag in roots.items():
        if file.startswith(path):
            rest = file[len(path):].lstrip("/")
            return rest if tag == "<SEL4>" else f"{tag}/{rest}"
    return file


def functions(text: str, roots: dict[str, str]) -> list[tuple[str, str, str, int]]:
    """Every top-level function definition of preprocessed C: (name, file, sha256 of normalised text, length)."""
    found: list[tuple[str, str, str, int]] = []
    seen: dict[str, int] = {}
    cur = ""
    item: list[str] = []
    item_file = ""
    body: list[str] = []
    depth = 0
    skipping = False  # inside a struct, enum or initializer: ignore until its `;`
    quote = ""
    name: str | None = None
    comment = False  # inside a block comment: seL4 keeps comments in kernel_all_pp.c, and they are not code
    for line in text.split("\n"):
        mark = LINEMARK.match(line)
        if mark and not quote and not comment and depth == 0:
            cur = relative(mark.group(1), roots)
            continue
        if line.startswith("#") and not quote and not comment:
            continue
        line += "\n"
        k = 0
        while k < len(line):
            ch = line[k]
            nxt = line[k + 1] if k + 1 < len(line) else ""
            k += 1
            if comment:
                if ch == "*" and nxt == "/":
                    comment = False
                    k += 1
                continue
            if not quote and ch == "/" and nxt == "*":
                comment = True
                k += 1
                continue
            if not quote and ch == "/" and nxt == "/":
                break  # a line comment: the rest of the line
            if quote:
                (body if depth else item).append(ch)
                if quote.endswith("\\"):
                    quote = quote[:-1]  # this character was escaped
                elif ch == "\\":
                    quote = quote + "\\"
                elif ch == quote[0]:
                    quote = ""
                continue
            if ch in "\"'":
                quote = ch
                (body if depth else item).append(ch)
                continue
            if depth == 0:
                if not item and ch.isspace():
                    continue
                if not item:
                    item_file = cur
                item.append(ch)
                if ch == ";":
                    item, skipping = [], False
                elif ch == "{":
                    name = None if skipping else function_name("".join(item[:-1]))
                    depth = 1
                    body = []
            else:
                body.append(ch)
                depth += {"{": 1, "}": -1}.get(ch, 0)
                if depth == 0:
                    if name is not None:
                        text_n = normalise("".join(item) + "".join(body), roots)
                        digest = hashlib.sha256(text_n.encode()).hexdigest()
                        seen[name] = seen.get(name, 0) + 1
                        key = name if seen[name] == 1 else f"{name}#{seen[name]}"
                        found.append((key, item_file, digest, len(text_n)))
                        item = []
                    else:
                        skipping = True  # keep the item: the declaration continues to its `;`
    if depth or quote or comment:
        raise ValueError("unbalanced braces, quotes or comment at the end of the preprocessed file")
    return sorted(found)


def read_tsv(path: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, file, digest, _length = line.split("\t")
            out[name] = (file, digest)
    return out


def diff_functions(ref: dict[str, tuple[str, str]], other: dict[str, tuple[str, str]], files: tuple[str, ...] | None) -> dict:
    def wanted(entry: tuple[str, str]) -> bool:
        return files is None or entry[0] in files

    names = sorted({n for n, e in ref.items() if wanted(e)} | {n for n, e in other.items() if wanted(e)})
    same = [n for n in names if n in ref and n in other and ref[n][1] == other[n][1]]
    differs = [n for n in names if n in ref and n in other and ref[n][1] != other[n][1]]
    only_ref = [n for n in names if n in ref and n not in other]
    only_other = [n for n in names if n in other and n not in ref]
    return {"in_reference": sum(1 for n in names if n in ref), "identical": len(same), "differs": len(differs),
            "only_reference": len(only_ref), "only_other": len(only_other), "differs_names": differs,
            "only_reference_names": only_ref, "only_other_names": only_other}


def compare(directory: Path, ref_id: str) -> dict:
    ids = sorted(p.name[len("functions-"):-len(".tsv")] for p in directory.glob("functions-*.tsv"))
    funcs = {i: read_tsv(directory / f"functions-{i}.tsv") for i in ids}
    cfgs = {i: json.loads((directory / f"gen_config-{i}.json").read_text(encoding="utf-8")) for i in ids}
    others = [i for i in ids if i != ref_id]
    result: dict = {"reference": ref_id, "configurations": ids,
                    "function_counts": {i: len(funcs[i]) for i in ids}, "config_keys": {i: len(cfgs[i]) for i in ids}}
    result["config_diff_vs_reference"] = {
        i: {k: [cfgs[ref_id].get(k), cfgs[i].get(k)] for k in sorted(set(cfgs[ref_id]) | set(cfgs[i]))
            if cfgs[ref_id].get(k) != cfgs[i].get(k)} for i in others}
    result["functions_vs_reference"] = {i: diff_functions(funcs[ref_id], funcs[i], None) for i in others}
    result["functions_by_property_vs_reference"] = {
        prop: {i: diff_functions(funcs[ref_id], funcs[i], files) for i in others} for prop, files in PROPERTY_FILES.items()}
    result["property_files"] = {prop: list(files) for prop, files in PROPERTY_FILES.items()}
    pairs = [(a, b) for n, a in enumerate(others) for b in others[n + 1:]]
    result["functions_between_others"] = {f"{a} vs {b}": diff_functions(funcs[a], funcs[b], None) for a, b in pairs}
    for key in ("functions_vs_reference", "functions_between_others"):  # the long name lists stay in the property tables
        for entry in result[key].values():
            for list_key in ("differs_names", "only_reference_names", "only_other_names"):
                entry.pop(list_key)
    return result


def matrix(directory: Path, ref_id: str) -> str:
    """One line per function of the code each property depends on (PROPERTY_FILES): its status in every configuration
    against the reference. `=` identical text, `!` different text, `-` absent; the reference's own column is `+` or `-`."""
    ids = sorted(p.name[len("functions-"):-len(".tsv")] for p in directory.glob("functions-*.tsv"))
    funcs = {i: read_tsv(directory / f"functions-{i}.tsv") for i in ids}
    ordered = [ref_id] + [i for i in ids if i != ref_id]
    rows = ["# property\tfile\tfunction\t" + "\t".join(ordered) + f"\t(status against {ref_id}: = identical text, ! different text, - absent; {ref_id} column: + present, - absent)"]
    for prop, files in PROPERTY_FILES.items():
        names = sorted({n for i in ids for n, (f, _h) in funcs[i].items() if f in files})
        for n in names:
            file = next(funcs[i][n][0] for i in ordered if n in funcs[i])
            cells = []
            for i in ordered:
                if i == ref_id:
                    cells.append("+" if n in funcs[i] else "-")
                elif n not in funcs[i]:
                    cells.append("-")
                else:
                    cells.append("=" if n in funcs[ref_id] and funcs[ref_id][n][1] == funcs[i][n][1] else "!")
            rows.append(f"{prop}\t{file}\t{n}\t" + "\t".join(cells))
    return "\n".join(rows) + "\n"


def report(result: dict, names: bool) -> str:
    """The comparison as Markdown tables (what results/A2a.md quotes)."""
    ref, ids = result["reference"], [i for i in result["configurations"] if i != result["reference"]]
    out = [f"Functions found in the preprocessed kernel: " + ", ".join(f"{i} {result['function_counts'][i]}" for i in result["configurations"]) + ".", ""]
    out += [f"| Against {ref} | Configuration keys that differ (of {result['config_keys'][ref]}) | Functions identical | Functions that differ | Only in {ref} | Only in the other |", "|---|---|---|---|---|---|"]
    for i in ids:
        f = result["functions_vs_reference"][i]
        out.append(f"| {i} | {len(result['config_diff_vs_reference'][i])} | {f['identical']} | {f['differs']} | {f['only_reference']} | {f['only_other']} |")
    out += ["", f"Per property (functions whose source file is in the property's file list; `identical / differs / only in {ref} / only in the other`, of the functions of the union):", "",
            "| Property | " + " | ".join(ids) + " |", "|---|" + "---|" * len(ids)]
    for prop, per in result["functions_by_property_vs_reference"].items():
        cells = [f"{per[i]['identical']} / {per[i]['differs']} / {per[i]['only_reference']} / {per[i]['only_other']}" for i in ids]
        out.append(f"| {prop} | " + " | ".join(cells) + " |")
    out += ["", "Between the other configurations (all functions):", "", "| Pair | Identical | Differ | Only in the first | Only in the second |", "|---|---|---|---|---|"]
    for pair, f in result["functions_between_others"].items():
        out.append(f"| {pair} | {f['identical']} | {f['differs']} | {f['only_reference']} | {f['only_other']} |")
    if names:
        for prop, per in result["functions_by_property_vs_reference"].items():
            for i in ids:
                f = per[i]
                if f["differs"] or f["only_reference"] or f["only_other"]:
                    out += ["", f"**{prop}, {i}.** Differ: {', '.join(f['differs_names']) or 'none'}. Only in {ref}: {', '.join(f['only_reference_names']) or 'none'}. Only in {i}: {', '.join(f['only_other_names']) or 'none'}."]
    return "\n".join(out) + "\n"


def self_test() -> int:
    roots = {"/s": "<SEL4>", "/b": "<BUILD>"}
    sample = '''# 1 "/s/src/a.c"
static inline __attribute__((always_inline)) int add(int a, int b)
{
    if (a) { return a + b; }
    return "}{" [0] + '{' + b;
}
# 5 "/s/src/b.c"
struct s { int x; struct { int y; } z; } var = { 1, { 2 } };
enum e { A, B };
static const char *msg = "has } and { in it"; static const char *bs = "a\\\\"; 
void __attribute__((noreturn)) halt(void) { for (;;) { } }
/* a comment with a } brace and a ' quote */
extern int proto(int); // and { another

int (*fp)(int) = 0;
char *name(const char *p)  __attribute__((nonnull))
{
    return (char *) "/s/src/b.c" + (p != 0);
}
'''
    got = functions(sample, roots)
    names = [(n, f) for n, f, _h, _l in got]
    ok = names == [("add", "src/a.c"), ("halt", "src/b.c"), ("name", "src/b.c")]
    a = functions(sample, roots)
    b = functions(sample.replace("/s", "/other"), {"/other": "<SEL4>", "/b": "<BUILD>"})
    same_after_path_change = [(n, h) for n, _f, h, _l in a] == [(n, h) for n, _f, h, _l in b]
    changed = functions(sample.replace("a + b", "a - b"), roots)
    detects_edit = [h for n, _f, h, _l in changed if n == "add"] != [h for n, _f, h, _l in a if n == "add"]
    try:
        functions("int f(void) {", roots)
        rejects_unbalanced = False
    except ValueError:
        rejects_unbalanced = True
    results = {"finds exactly the three functions, with their files": ok, "hash is independent of the source root": same_after_path_change,
               "hash changes when the body changes": detects_edit, "rejects unbalanced input": rejects_unbalanced}
    for label, passed in results.items():
        print(f"{'ok  ' if passed else 'FAIL'}  {label}")
    return 0 if all(results.values()) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("id")
    ex.add_argument("--pp", required=True)
    ex.add_argument("--sel4", required=True)
    ex.add_argument("--build", required=True)
    ex.add_argument("--out", required=True)
    cp = sub.add_parser("compare")
    cp.add_argument("directory")
    cp.add_argument("--ref", default="K0")
    cp.add_argument("--out", required=True)
    mx = sub.add_parser("matrix")
    mx.add_argument("directory")
    mx.add_argument("--ref", default="K0")
    mx.add_argument("--out", required=True)
    rp = sub.add_parser("report")
    rp.add_argument("comparison")
    rp.add_argument("--names", action="store_true")
    sub.add_parser("self-test")
    ns = ap.parse_args()
    if ns.cmd == "self-test":
        return self_test()
    if ns.cmd == "extract":
        roots = {str(Path(ns.build).resolve()): "<BUILD>", str(Path(ns.sel4).resolve()): "<SEL4>"}
        roots = dict(sorted(roots.items(), key=lambda kv: -len(kv[0])))
        found = functions(Path(ns.pp).read_text(encoding="utf-8"), roots)
        with open(ns.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"# a2a-compare.py extract {ns.id}: {len(found)} function definitions in the preprocessed kernel\n")
            for name, file, digest, length in found:
                fh.write(f"{name}\t{file}\t{digest}\t{length}\n")
        print(f"{ns.id}: {len(found)} functions")
        return 0
    if ns.cmd == "matrix":
        Path(ns.out).write_text(matrix(Path(ns.directory), ns.ref), encoding="utf-8", newline="\n")
        return 0
    if ns.cmd == "report":
        sys.stdout.write(report(json.loads(Path(ns.comparison).read_text(encoding="utf-8")), ns.names))
        return 0
    result = compare(Path(ns.directory), ns.ref)
    Path(ns.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"compared {len(result['configurations'])} configurations against {ns.ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
