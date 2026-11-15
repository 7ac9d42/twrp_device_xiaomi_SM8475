#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -eo pipefail
tree=$(cd "$(dirname "$0")/.." && pwd)
root=$(realpath "$tree/../../..")
test -f "$root/build/envsetup.sh" || { echo "Place the tree at device/xiaomi/liuqin" >&2; exit 1; }
cd "$root"
export PATH=/usr/local/bin:/usr/bin:/bin
export ALLOW_MISSING_DEPENDENCIES=true
# Upstream minimal manifest omits unrelated test/system projects. Selected missing
# dependencies still generate failing Ninja rules; do not bypass those failures.
export USE_CCACHE="${USE_CCACHE:-true}"
if [[ "$USE_CCACHE" == true ]]; then
    export CCACHE_EXEC=/usr/bin/ccache CCACHE_COMPILERCHECK=content
    export CCACHE_DIR="${CCACHE_DIR:-$root/out/ccache}" CCACHE_BASEDIR="$root"
    export CC_WRAPPER=/usr/bin/ccache CXX_WRAPPER=/usr/bin/ccache
fi
export LC_ALL=C SOONG_GOMEMLIMIT="${SOONG_GOMEMLIMIT:-6GiB}"
# The locked Soong switch also drops its codegen-units=1 default. Keep both
# cold and warm CI runs on this same native incremental configuration.
export SOONG_RUSTC_INCREMENTAL="${SOONG_RUSTC_INCREMENTAL:-true}"
# CI cache keys require this relative OUT_DIR and a stable absolute source root.
export OUT_DIR=out
unset OUT_DIR_COMMON_BASE
jobs="${JOBS:-4}"
backend_jobs="${BACKEND_JOBS:-6}"
mkdir -p logs artifacts
# Locked Soong PathForOutput(ctx, "rustc") is rooted at out/soong.
rust_size_kib() {
    if [[ -d out/soong/rustc ]]; then du -sk out/soong/rustc | cut -f1; else printf '0\n'; fi
}
printf '%s\n' "$(rust_size_kib)" > logs/rust-cache-before-kib.txt
report_cache_stats() {
    local status=$?
    trap - EXIT
    printf '%s\n' "$(rust_size_kib)" > logs/rust-cache-after-kib.txt || true
    if [[ "$USE_CCACHE" == true ]]; then
        ccache --show-stats | tee logs/ccache-after.txt || true
    fi
    exit "$status"
}
trap report_cache_stats EXIT
if [[ "$USE_CCACHE" == true ]]; then
    ccache --max-size="${CCACHE_MAX_SIZE:-5Gi}"
    ccache --set-config=compression=true
    ccache --zero-stats
    ccache --show-stats > logs/ccache-before.txt
fi
available=$(df -Pk . | awk 'NR==2 {print $4}')
(( available >= 25 * 1024 * 1024 )) || { echo "Less than 25 GiB free" >&2; exit 1; }
python3 -I "$tree/tools/extract-files.py" --root "$root" --check
python3 -I "$tree/tools/apply-patches.py" --root "$root" --check
# --check alone reports unapplied patches, so require all recorded diffs already present.
python3 -I "$tree/tools/apply-patches.py" --root "$root"
for obsolete in libvndksupport.so libcgrouprc.so; do
    stale="out/target/product/liuqin/recovery/root/vendor/lib64/$obsolete"
    if [[ -f "$stale" ]]; then
        rm -- "$stale"
        rm -f -- out/target/product/liuqin/obj/PACKAGING/recovery_intermediates/ramdisk_files-timestamp
    fi
done
source build/envsetup.sh
lunch twrp_liuqin bp2a eng
# Locked Soong ui/build/ninja.go appends NINJA_EXTRA_ARGS only to the final
# Ninja command; bootstrap keeps m's -j value. The last -j takes precedence.
export NINJA_EXTRA_ARGS="${NINJA_EXTRA_ARGS:+$NINJA_EXTRA_ARGS }-j$backend_jobs"
m -j"$jobs" recoveryimage host_init_verifier assemble_vintf avbtool 2>&1 | tee "logs/build-$(date +%Y%m%d-%H%M%S).log"
