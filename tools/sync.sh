#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
tree=$(cd "$(dirname "$0")/.." && pwd)
cd "$tree/../../.."
test -d .repo || { echo "Initialize the locked partial-clone manifest first" >&2; exit 1; }
jobs="${SYNC_JOBS:-8}"
sync_stage() {
    local stage=$1 start end status
    shift
    start=$(date +%s)
    printf 'sync stage=%s start_epoch=%s\n' "$stage" "$start"
    set +e
    (set -e; "$@")
    status=$?
    set -e
    end=$(date +%s)
    printf 'sync stage=%s start_epoch=%s end_epoch=%s duration_seconds=%s status=%s\n' \
        "$stage" "$start" "$end" "$((end - start))" "$status"
    return "$status"
}
checkout_clang() {
    local clang_git=.repo/projects/prebuilts/clang/host/linux-x86.git
    git --git-dir="$clang_git" config core.sparseCheckout true
    mkdir -p "$clang_git/info"
    cp "$tree/integration/clang-sparse-checkout.txt" "$clang_git/info/sparse-checkout"
    repo sync -l -j"$jobs" -v prebuilts/clang/host/linux-x86
}
# Fetch compiler metadata, configure the validated sparse selection, then hydrate it.
sync_stage clang-fetch repo sync -n -c -j"$jobs" -v --no-clone-bundle --no-tags prebuilts/clang/host/linux-x86
sync_stage clang-checkout checkout_clang
# Let repo apply the selected manifest groups; include clang in the normal sync.
sync_stage sources repo sync -c -j"$jobs" -v --no-clone-bundle --no-tags --optimized-fetch --fail-fast
