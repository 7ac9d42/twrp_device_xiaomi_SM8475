#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Only for a disposable, standard Ubuntu 24.04 GitHub-hosted x64 runner.
# MIN_FREE_GIB is the required free space AFTER allocating up to 8 GiB swap.
set -euo pipefail
export LC_ALL=C

fail() { printf 'prepare-runner: %s\n' "$*" >&2; exit 1; }
[[ ${GITHUB_ACTIONS:-} == true && ${RUNNER_ENVIRONMENT:-} == github-hosted ]] ||
    fail 'requires a disposable GitHub-hosted Actions runner'
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'requires Linux x86_64'
# The OS file is provided by the runner image, not by the checkout.
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || fail 'requires Ubuntu 24.04'
: "${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
MIN_FREE_GIB=${MIN_FREE_GIB:-80}
[[ $MIN_FREE_GIB =~ ^[1-9][0-9]*$ ]] || fail 'MIN_FREE_GIB must be a positive integer'

resources() {
    date -u '+%Y-%m-%dT%H:%M:%SZ'
    df -h -- "$GITHUB_WORKSPACE" "$RUNNER_TEMP"
    free -h
}
resources
cpus=$(nproc)
printf 'CPUs: %s; required free space after swap: %s GiB\n' "$cpus" "$MIN_FREE_GIB"
[[ $cpus == 4 ]] || fail 'requires the standard public 4-CPU runner'
mem_kib=0
swap_kib=0
while read -r key value _; do
    case $key in
        MemTotal:) mem_kib=$value ;;
        SwapTotal:) swap_kib=$value ;;
    esac
done < /proc/meminfo
(( mem_kib >= 14 * 1024 * 1024 )) || fail 'requires at least 14 GiB physical memory'
swap_needed_kib=$((8 * 1024 * 1024 - swap_kib))
if (( swap_needed_kib > 0 )); then
    # mkswap reserves one page for its header; account for it in the allocation.
    page_kib=$(($(getconf PAGESIZE) / 1024))
    swap_needed_kib=$(((swap_needed_kib + page_kib - 1) / page_kib * page_kib + page_kib))
else
    swap_needed_kib=0
fi

# A fixed allowlist, checked before any deletion. Python is part of the image;
# isolated mode prevents imports from the checkout or user site directories.
timeout --signal=TERM --kill-after=15s 5m sudo -n /usr/bin/python3 -I - \
    "$MIN_FREE_GIB" "$swap_needed_kib" "$GITHUB_WORKSPACE" "$RUNNER_TEMP" "$PWD" "${BASH_SOURCE[0]}" "${SOURCE_ROOT:-$PWD}" <<'PY'
import os
import re
import shutil
import stat
import sys

minimum = int(sys.argv[1]) * 2**30
reserve = int(sys.argv[2]) * 1024
protected = [os.path.abspath(path) for path in sys.argv[3:6]]
# Also protect the script and source tree when invoked outside the checkout.
protected.append(os.path.dirname(os.path.realpath(sys.argv[6])))
source_root = os.path.abspath(sys.argv[7])
check_directories = tuple(protected)
protected.append(source_root)
allowed = (
    "/usr/local/lib/android",
    "/usr/share/dotnet",
    "/opt/ghc",
    "/usr/local/.ghcup",
    "/usr/share/swift",
    "/usr/local/share/powershell",
    "/opt/hostedtoolcache/CodeQL",
    "/usr/share/miniconda",
)


def fail(message):
    raise SystemExit("prepare-runner: " + message)


def check_ancestors(path):
    current = path
    while True:
        if os.path.islink(current):
            fail("refusing symlink: " + current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent


def contains(parent, child):
    return os.path.commonpath((parent, child)) == parent


for path in protected:
    check_ancestors(path)
    if path in check_directories and not os.path.isdir(path):
        fail("not a directory: " + path)

with open("/proc/self/mountinfo", encoding="utf-8") as stream:
    mounts = [
        re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), line.split()[4])
        for line in stream
    ]

for path in allowed:
    check_ancestors(path)
    if any(contains(path, item) or contains(item, path) for item in protected):
        fail("cleanup overlaps a protected directory: " + path)
    if any(contains(path, mount) for mount in mounts):
        fail("cleanup would cross a mount point: " + path)
    if os.path.lexists(path) and not stat.S_ISDIR(os.lstat(path).st_mode):
        fail("cleanup target is not a directory: " + path)

if not shutil.rmtree.avoids_symlink_attacks:
    fail("requires symlink-safe rmtree")
# Recovery sources + 25 GiB output, without a first-run ccache allocation.
# Reserve the swap deficit as well so the final free-space check still passes.
target = minimum + reserve
for path in allowed:
    available = shutil.disk_usage(protected[0]).free
    if available >= target:
        break
    if os.path.isdir(path):
        print("Removing allowlisted SDK: " + path, flush=True)
        # rmtree unlinks internal symlinks without following them. The preflight
        # above rejects target/ancestor symlinks and every nested mount point.
        shutil.rmtree(path)
    print(f"Free bytes: {shutil.disk_usage(protected[0]).free}; target: {target}", flush=True)

if shutil.disk_usage(protected[0]).free < target:
    fail("allowlisted cleanup did not provide enough space (including swap reserve)")
if shutil.disk_usage(protected[1]).free < reserve:
    fail("RUNNER_TEMP has insufficient space for the swap deficit")
PY

swap_dir=
swap_active=false
finish() {
    local status=$?
    trap - EXIT
    if [[ -n $swap_dir && $swap_active == false ]]; then
        rm -f -- "$swap_dir/swapfile"
        rmdir -- "$swap_dir"
    fi
    resources || true
    exit "$status"
}
trap finish EXIT
if (( swap_needed_kib > 0 )); then
    swap_dir=$(mktemp -d "$RUNNER_TEMP/ci-swap.XXXXXXXX")
    swap_file="$swap_dir/swapfile"
    (umask 077; : > "$swap_file")
    fallocate -l "${swap_needed_kib}K" -- "$swap_file"
    sudo -n mkswap -- "$swap_file"
    sudo -n swapon -- "$swap_file"
    swap_active=true
    printf 'Enabled %s KiB additional swap at %s (runner lifetime only)\n' "$swap_needed_kib" "$swap_file"
fi
swap_kib=0
while read -r key value _; do
    [[ $key != SwapTotal: ]] || swap_kib=$value
done < /proc/meminfo
(( swap_kib >= 8 * 1024 * 1024 )) || fail 'total active swap is still below 8 GiB'
/usr/bin/python3 -I - "$GITHUB_WORKSPACE" "$MIN_FREE_GIB" <<'PY'
import shutil
import sys

available = shutil.disk_usage(sys.argv[1]).free
minimum = int(sys.argv[2]) * 2**30
print(f"Final free bytes: {available}; required: {minimum}")
if available < minimum:
    raise SystemExit("prepare-runner: insufficient free space after swap allocation")
PY
