#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -eo pipefail
tree=$(cd "$(dirname "$0")/.." && pwd)
root=$(realpath "$tree/../../..")
test -f "$root/build/envsetup.sh" || { echo "Place the tree at device/xiaomi/liuqin" >&2; exit 1; }
cd "$root"
python "$tree/tools/extract-files.py" --root "$root" --check
python "$tree/tools/apply-patches.py" --root "$root" --check
# --check alone reports unapplied patches, so require all recorded diffs already present.
python "$tree/tools/apply-patches.py" --root "$root"
export PATH=/usr/local/bin:/usr/bin:/bin
export ALLOW_MISSING_DEPENDENCIES=true
# Upstream minimal manifest omits unrelated test/system projects. Selected missing
# dependencies still generate failing Ninja rules; do not bypass those failures.
export USE_CCACHE=true CCACHE_EXEC=/usr/bin/ccache CCACHE_COMPILERCHECK=content
export CCACHE_DIR="$root/.ccache" CC_WRAPPER=/usr/bin/ccache CXX_WRAPPER=/usr/bin/ccache
export LC_ALL=C SOONG_GOMEMLIMIT="${SOONG_GOMEMLIMIT:-12GiB}"
jobs="${JOBS:-$(nproc)}"
mkdir -p logs artifacts
available=$(df -Pk . | awk 'NR==2 {print $4}')
(( available >= 25 * 1024 * 1024 )) || { echo "Less than 25 GiB free" >&2; exit 1; }
ccache --max-size=15Gi
ccache --set-config=compression=true
for obsolete in libvndksupport.so libcgrouprc.so; do
    stale="out/target/product/liuqin/recovery/root/vendor/lib64/$obsolete"
    if [[ -f "$stale" ]]; then
        rm -- "$stale"
        rm -f -- out/target/product/liuqin/obj/PACKAGING/recovery_intermediates/ramdisk_files-timestamp
    fi
done
ccache --show-stats > logs/ccache-before.txt
source build/envsetup.sh
lunch twrp_liuqin bp2a eng
m -j"$jobs" recoveryimage 2>&1 | tee "logs/build-$(date +%Y%m%d-%H%M%S).log"
ccache --show-stats | tee logs/ccache-after.txt
