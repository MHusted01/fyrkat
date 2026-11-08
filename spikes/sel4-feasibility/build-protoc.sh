#!/usr/bin/env bash
# A3: build protoc 3.20.3 locally, from the pinned source commit, into the gitignored external/.
# Why: sel4-deps pins the Python protobuf below 4, and Homebrew's protoc (36.2) generates code that
# needs a newer runtime, so nanopb's generator fails. A protoc matching protobuf 3.20.3 is needed.
# Apple Silicon has no official 3.20.3 binary (Intel only, needs Rosetta), and grpcio-tools <1.49
# has no arm64 or Python 3.12 wheel. Installs nothing outside external/.
set -euo pipefail
W="$(cd "$(dirname "$0")" && pwd)"
SRC="$W/external/protobuf-3.20.3"
SHA=fe271ab76f2ad2b2b28c10443865d2af21e27e0e   # tag v3.20.3

if [ ! -d "$SRC/.git" ]; then
    git init -q "$SRC"
    git -C "$SRC" remote add origin https://github.com/protocolbuffers/protobuf
fi
if [ "$(git -C "$SRC" rev-parse -q --verify HEAD 2>/dev/null || true)" != "$SHA" ]; then
    git -C "$SRC" fetch -q --depth 1 origin "$SHA"
    git -C "$SRC" checkout -q FETCH_HEAD
fi
got="$(git -C "$SRC" rev-parse HEAD)"
[ "$got" = "$SHA" ] || { echo "error: protobuf source at $got, expected $SHA" >&2; exit 1; }

cmake -S "$SRC/cmake" -B "$W/external/protoc-build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -Dprotobuf_BUILD_TESTS=OFF \
    -Dprotobuf_BUILD_SHARED_LIBS=OFF \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5
ninja -C "$W/external/protoc-build" protoc
"$W/external/protoc-build/protoc" --version
