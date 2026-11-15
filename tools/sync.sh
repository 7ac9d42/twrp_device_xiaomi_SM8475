#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
tree=$(cd "$(dirname "$0")/.." && pwd)
cd "$tree/../../.."
test -d .repo || { echo "Initialize the locked partial-clone manifest first" >&2; exit 1; }
jobs="${SYNC_JOBS:-16}"
checkout_jobs="${SYNC_CHECKOUT_JOBS:-4}"
[[ $jobs =~ ^[1-9][0-9]*$ && $checkout_jobs =~ ^[1-9][0-9]*$ ]] || { echo "Sync job counts must be positive integers" >&2; exit 1; }
printf 'Sync network jobs=%s checkout jobs=%s\n' "$jobs" "$checkout_jobs"
repo version
git --version
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
configure_sparse() {
    python3 -I - "$tree" <<'PY'
from pathlib import Path
import os, re, subprocess, sys, xml.etree.ElementTree as ET
selection=Path(sys.argv[1])/"integration"
revision=ET.parse(selection/"manifest.lock.xml").find("./project[@path='build/soong']").attrib["revision"]
for source,key,override,pattern,prefix in [
    ("cc/config/global.go","ClangDefaultVersion","LLVM_PREBUILTS_VERSION","clang-sparse-checkout.txt","/"),
    ("rust/bindgen.go","bindgenClangVersion","","clang-sparse-checkout.txt","/"),
    ("rust/config/global.go","RustDefaultVersion","RUST_PREBUILTS_VERSION","rust-sparse-checkout.txt","/linux-x86/"),
]:
    text=subprocess.check_output(["git","--git-dir=.repo/projects/build/soong.git","show",revision+":"+source],text=True)
    match=re.search(r'\b'+key+r'\s*=\s*"([^"]+)"',text)
    if not match:raise SystemExit("Cannot resolve upstream "+key)
    version=os.environ.get(override) or match[1]
    if prefix+version+"/" not in (selection/pattern).read_text().splitlines():
        raise SystemExit("Sparse selection does not include "+key+"="+version)
    print("Selected "+key+"="+version,flush=True)
PY
    local project patterns git_dir
    for project in prebuilts/clang/host/linux-x86 prebuilts/rust; do
        if [[ $project == prebuilts/rust ]]; then patterns=rust; else patterns=clang; fi
        git_dir=".repo/projects/$project.git"
        git --git-dir="$git_dir" config core.sparseCheckout true
        git --git-dir="$git_dir" config core.sparseCheckoutCone false
        mkdir -p "$git_dir/info"
        cp "$tree/integration/$patterns-sparse-checkout.txt" "$git_dir/info/sparse-checkout"
    done
}
# Configure sparse paths before any toolchain blob hydration.
sync_stage toolchain-metadata repo sync -n -c -j"$jobs" -v --no-clone-bundle --no-tags --optimized-fetch \
    build/soong prebuilts/clang/host/linux-x86 prebuilts/rust
sync_stage toolchain-selection configure_sparse
# One checkout pool hydrates clang, Rust and other active projects concurrently.
sync_stage sources repo sync -c --no-interleaved --jobs-network="$jobs" --jobs-checkout="$checkout_jobs" \
    -v --no-clone-bundle --no-tags --optimized-fetch --fail-fast
