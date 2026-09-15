#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
tree=$(cd "$(dirname "$0")/.." && pwd)
root=${1:?Usage: build-reader.sh TWRP_ROOT}
root=$(realpath "$root")
if [[ -x "$root/tools/erofs_read" ]]; then
    echo "$root/tools/erofs_read"
    exit 0
fi
work="$tree/.cache/erofs-host"
mkdir -p "$work"
if [[ ! -f "$work/config.status" ]]; then
    git -C "$root/external/erofs-utils" archive HEAD | tar -x -C "$work"
    (cd "$work"; autoreconf -fi >&2; ./configure --disable-fuse --without-selinux --disable-lzma >&2)
fi
make -C "$work/lib" -j"${JOBS:-4}" >&2
cc -O2 -I"$work/include" -I"$work" "$tree/tools/erofs_read.c" \
    "$work/lib/.libs/liberofs.a" $(pkg-config --libs liblz4 libzstd zlib) -pthread -o "$tree/.cache/erofs_read"
echo "$tree/.cache/erofs_read"
