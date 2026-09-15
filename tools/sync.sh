#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
tree=$(cd "$(dirname "$0")/.." && pwd)
cd "$tree/../../.."
test -d .repo || { echo "Initialize the locked partial-clone manifest first" >&2; exit 1; }
# Fetch compiler metadata, configure the validated sparse selection, then hydrate it.
repo sync -n -c -j1 --no-clone-bundle --no-tags prebuilts/clang/host/linux-x86
clang_git=.repo/projects/prebuilts/clang/host/linux-x86.git
git --git-dir="$clang_git" config core.sparseCheckout true
mkdir -p "$clang_git/info"
cp "$tree/integration/clang-sparse-checkout.txt" "$clang_git/info/sparse-checkout"
repo sync -l -j1 prebuilts/clang/host/linux-x86
mapfile -t projects < <(repo list -a -p | grep -vx prebuilts/clang/host/linux-x86)
repo sync -c -j"${SYNC_JOBS:-8}" --no-clone-bundle --no-tags --optimized-fetch "${projects[@]}"
