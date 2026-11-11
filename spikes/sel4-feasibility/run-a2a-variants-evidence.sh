#!/usr/bin/env bash
# A2a follow-up: raw evidence in results-raw/A2a-variants (gitignored) for the release variants K1R, K2R, E1HR and the extra
# K0Q (see build-a2a-variants.sh). It rebuilds each in a second directory, extracts the function tables, copies the published
# A2a tables of K0, K1, K2 and E1H (so the comparison is self-contained and tied to the reviewed A2a evidence), and compares
# all eight against K0. Then sanitize and check:
#
#   spikes/sel4-feasibility/run-a2a-variants-evidence.sh
#   python3 spikes/sel4-feasibility/sanitize-run.py A2a-variants
#   python3 spikes/sel4-feasibility/verify-evidence.py
#
# Builds kernels only; boots nothing, installs nothing. Spike code.
set -uo pipefail

W="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 1
R=results-raw/A2a-variants
IDS=(K1R K2R E1HR K0Q)
BASE=(K0 K1 K2 E1H)
SOURCES=(build-a2a-variants.sh a2a-compare.py boot-image.py)

for id in "${BASE[@]}"; do
    [ -f "results/A2a/functions-$id.tsv" ] || { echo "error: results/A2a/functions-$id.tsv is missing (the A2a evidence must exist)"; exit 1; }
done
rm -rf "$R" external/a2a-variants-build external/a2a-variants-build-repro
mkdir -p "$R"

{
    echo "# A2a variants preflight record, $(date -u +%Y-%m-%dT%H:%M:%SZ). Written before the builds."
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "branch: $(git branch --show-current)"
    echo "git status --short:"
    git status --short -- . ':!external' ':!results-raw' ':!.venv' | sed 's/^/ /'
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "Cargo.toml and Cargo.lock sha256: $(shasum -a 256 Cargo.toml Cargo.lock | cut -d' ' -f1 | tr '\n' ' ')"
    for f in "${SOURCES[@]}"; do echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done
    for id in "${BASE[@]}"; do echo "a2a table sha256: $(shasum -a 256 "results/A2a/functions-$id.tsv" | cut -d' ' -f1)  $id"; done
} >"$R/00-preflight.txt"

fail=0
for id in "${IDS[@]}"; do
    ./build-a2a-variants.sh "$id" >"$R/.build-$id.out" 2>&1 || fail=1
    tail -1 "$R/.build-$id.out"
done
for id in "${IDS[@]}"; do
    A2A_BUILD_ROOT="$(cd external && pwd -P)/a2a-variants-build-repro" ./build-a2a-variants.sh "$id" >"$R/.repro-$id.out" 2>&1 || fail=1
done
[ "$fail" -eq 0 ] || { echo "a build failed; see $R/.build-*.out"; exit 1; }

cp external/a2a-variants-build/K1R/tools.txt "$R/01-tools.txt"
for id in "${IDS[@]}"; do
    for root in a2a-variants-build a2a-variants-build-repro; do
        cmp -s external/a2a-variants-build/K1R/tools.txt "external/$root/$id/tools.txt" || echo "tools differ: $root/$id" >>"$R/01-tools.txt"
    done
done
{ for id in "${IDS[@]}"; do echo "## $id"; cat "external/a2a-variants-build/$id/command.txt"; done; } >"$R/02-commands.txt"
for id in "${BASE[@]}"; do
    cp "results/A2a/functions-$id.tsv" "$R/functions-$id.tsv"
    cp "results/A2a/gen_config-$id.json" "$R/gen_config-$id.json"
done
for id in "${IDS[@]}"; do
    {
        echo "## $id: build exit $(cat "external/a2a-variants-build/$id/BUILD_EXIT")"
        cat "external/a2a-variants-build/$id/build.log"
    } >"$R/03-build-$id.txt"
    cp "external/a2a-variants-build/$id/gen_config.json" "$R/gen_config-$id.json"
    python3 -B a2a-compare.py extract "$id" --pp "external/a2a-variants-build/$id/kernel_all_pp.c" --sel4 external/seL4 \
        --build "external/a2a-variants-build/$id/sel4" --out "$R/functions-$id.tsv"
    python3 -B a2a-compare.py extract "$id" --pp "external/a2a-variants-build-repro/$id/kernel_all_pp.c" --sel4 external/seL4 \
        --build "external/a2a-variants-build-repro/$id/sel4" --out "$R/.repro-functions-$id.tsv" >/dev/null
done
python3 -B a2a-compare.py compare "$R" --ref K0 --out "$R/comparison.json"
python3 -B a2a-compare.py matrix "$R" --ref K0 --out "$R/property-functions.tsv"

{
    echo "# Hashes of the build outputs of the variants. Column 2 is the second build, in another directory."
    for id in "${IDS[@]}"; do
        for f in gen_config.json kernel.elf kernel_all_pp.c kernel_all.i; do
            echo "$id $f $(shasum -a 256 "external/a2a-variants-build/$id/$f" | cut -d' ' -f1) $(shasum -a 256 "external/a2a-variants-build-repro/$id/$f" | cut -d' ' -f1)"
        done
    done
} >"$R/04-sums.txt"

{
    echo "# Reproducibility: the function table of each variant from two clean builds in different directories."
    for id in "${IDS[@]}"; do
        if cmp -s "$R/functions-$id.tsv" "$R/.repro-functions-$id.tsv"; then
            echo "$id: function tables identical ($(grep -vc '^#' "$R/functions-$id.tsv") functions, sha256 $(shasum -a 256 "$R/functions-$id.tsv" | cut -d' ' -f1))"
        else
            echo "$id: function tables DIFFER"
        fi
    done
    python3 -B a2a-compare.py compare "$R" --ref K0 --out "$R/.comparison-again.json" >/dev/null
    python3 -B a2a-compare.py matrix "$R" --ref K0 --out "$R/.matrix-again.tsv"
    if cmp -s "$R/comparison.json" "$R/.comparison-again.json" && cmp -s "$R/property-functions.tsv" "$R/.matrix-again.tsv"; then echo "comparison and matrix rerun on the same tables: identical"; else echo "comparison or matrix rerun: DIFFERS"; fi
} >"$R/06-reproducibility.txt"

{
    echo "# Completeness of the extraction for the variants: C functions with code in each kernel.elf (nm, type t or T; compiler clone suffixes removed) that are missing from the function table."
    for id in "${IDS[@]}"; do
        python3 -B - "$id" "$R/functions-$id.tsv" "$(aarch64-elf-nm "external/a2a-variants-build/$id/kernel.elf" | awk '$2 ~ /^[tT]$/ {print $3}' | sort -u | tr '\n' ' ')" <<'PY'
import re, sys
ident, tsv, symbols = sys.argv[1], sys.argv[2], sys.argv[3].split()
names = {l.split("\t")[0].split("#")[0] for l in open(tsv) if l.strip() and not l.startswith("#")}
syms = {re.sub(r"\.(part|isra|constprop|cold|lto_priv)\..*$", "", s) for s in symbols}
missing = sorted(syms - names)
print(f"{ident}: {len(syms)} text symbols, {len(names)} functions extracted, {len(missing)} symbols not extracted: {' '.join(missing)}")
PY
    done
} >"$R/05-nm-crosscheck.txt"
rm -f "$R"/.repro-functions-*.tsv "$R"/.comparison-again.json "$R"/.matrix-again.tsv "$R"/.build-*.out "$R"/.repro-*.out

{
    echo "# A2a variants post-run record, $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "repo HEAD: $(git rev-parse HEAD)"
    echo "seL4 HEAD: $(git -C external/seL4 rev-parse HEAD); dirty files: $(git -C external/seL4 status --porcelain | wc -l | tr -d ' ')"
    echo "Cargo.toml and Cargo.lock tracked diff vs HEAD: $(git diff HEAD -- Cargo.toml Cargo.lock | wc -l | tr -d ' ') lines"
    echo "seL4 source tracked diff: $(git -C external/seL4 diff HEAD | wc -l | tr -d ' ') lines"
    for f in "${SOURCES[@]}"; do echo "src sha256: $(shasum -a 256 "$f" | cut -d' ' -f1)  $f"; done
    for id in "${BASE[@]}"; do echo "a2a table sha256: $(shasum -a 256 "results/A2a/functions-$id.tsv" | cut -d' ' -f1)  $id"; done
} >"$R/07-post-checks.txt"
echo ALL-DONE
