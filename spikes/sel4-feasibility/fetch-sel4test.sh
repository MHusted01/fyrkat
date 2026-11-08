#!/usr/bin/env bash
# A3: fetch the sel4test project set at the revisions pinned by sel4test-manifest tag 17.0.0
# (commit 655b1f2a67de058571b5f653688aa55440745192), with plain git and no `repo` tool, into the
# gitignored external/sel4test-workspace/. Recreates the manifest's linkfiles. Verifies every pin.
# opensbi is skipped: it is RISC-V only. The kernel is the existing external/seL4 checkout.
set -euo pipefail
W="$(cd "$(dirname "$0")" && pwd)"
D="$W/external/sel4test-workspace"
mkdir -p "$D/projects" "$D/tools" "$D/.gitdirs"

fetch() { # path url sha
    local path="$D/$1" url="$2" sha="$3"
    # .git must be a file, as in a `repo` checkout: sel4test's musllibc build runs `rm src/.git`.
    if [ ! -e "$path/.git" ]; then
        git init -q --separate-git-dir "$D/.gitdirs/${1//\//_}" "$path"
        git -C "$path" remote add origin "$url"
    fi
    if [ "$(git -C "$path" rev-parse -q --verify HEAD 2>/dev/null || true)" != "$sha" ]; then
        git -C "$path" fetch -q --depth 1 origin "$sha"
        git -C "$path" checkout -q FETCH_HEAD
    fi
    local got
    got="$(git -C "$path" rev-parse HEAD)"
    if [ "$got" != "$sha" ]; then
        echo "MISMATCH $1: $got != $sha" >&2
        exit 1
    fi
    echo "OK $1 $got"
}

fetch projects/musllibc          https://github.com/seL4/musllibc.git            b0005f86fecbd6d0257b15363a5b013446914265
fetch tools/nanopb               https://github.com/nanopb/nanopb                cad3c18ef15a663e30e3e43e3a752b66378adec1
fetch projects/seL4_libs         https://github.com/seL4/seL4_libs.git           262a34dcb2f3285be01df9e5404d911132d567a6
fetch tools/seL4                 https://github.com/seL4/seL4_tools.git          6493e0c6fab360eb81a8115a49c9ca7bc280c48a
fetch projects/sel4_projects_libs https://github.com/seL4/sel4_projects_libs.git b9137c0d905ce966a02b1c9a0c6c0e4beb48223b
fetch projects/sel4runtime       https://github.com/seL4/sel4runtime.git         86489cf6efab9f314964e79468c036e9035394c7
fetch projects/sel4test          https://github.com/seL4/sel4test.git            f27e4f4cdd020ef9b37f15ded76a3b38477761f0
fetch projects/util_libs         https://github.com/seL4/util_libs.git           ef49a397b7044fc38b609a99a8c6265a97913b8e

# The kernel is the pinned seL4 checkout, which must be at the manifest's kernel revision.
[ "$(git -C "$W/external/seL4" rev-parse HEAD)" = 62e345c240a15671484530b4e6e069ce266c28d7 ]
ln -sfn ../seL4 "$D/kernel"

# Linkfiles from the manifest.
ln -sfn tools/seL4/cmake-tool/init-build.sh "$D/init-build.sh"
ln -sfn tools/seL4/cmake-tool/griddle "$D/griddle"
ln -sfn projects/sel4test/easy-settings.cmake "$D/easy-settings.cmake"
echo "done: $D"
