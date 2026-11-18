#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail

action=$1
name=$2
case "$name" in
    clang) path=prebuilts/clang/host/linux-x86; limit=3 ;;
    rust) path=prebuilts/rust; limit=2 ;;
    *) printf 'Unknown toolchain cache: %s\n' "$name" >&2; exit 2 ;;
esac
store="$SOURCE_ROOT/.repo/project-objects/platform/$path.git"

case "$action" in
    finish-restore)
        outcome=${3:-skipped}
        hit=${4:-false}
        now=$(date +%s)
        printf '{"stage":"%s-cache-restore","start_epoch":%s,"end_epoch":%s,"status":"%s","exact_hit":"%s"}\n' \
            "$name" "${5:-$now}" "$now" "$outcome" "$hit" > "$CI_LOG_DIR/cache-$name-restore.json"
        if [[ -e "$store" && ( "$outcome" != success || "$hit" != true ) ]]; then
            incomplete=$(mktemp -d "$RUNNER_TEMP/yarp-$name-cache-incomplete.XXXXXX")
            mv -- "$store" "$incomplete/"
            printf 'Isolated incomplete %s cache in %s; use a cold sync.\n' "$name" "$incomplete"
        fi
        ;;
    check-save)
        printf '%s_CACHE_SAVE_START=%s\n' "${name^^}" "$(date +%s)" >> "$GITHUB_ENV"
        project="$SOURCE_ROOT/.repo/projects/$path.git"
        if [[ ! -d "$store/objects" || ! "$project/objects" -ef "$store/objects" ]]; then
            printf 'Skip %s cache save: project uses a different object store.\n' "$name"
            exit 0
        fi
        size=$(du -sk -- "$store" | cut -f1)
        available=$(df -Pk -- "$store" | awk 'NR==2 {print $4}')
        printf '%s object cache: %s KiB; limit %s GiB; free %s KiB.\n' "$name" "$size" "$limit" "$available"
        if (( size <= limit * 1024 * 1024 && available >= size + 3 * 1024 * 1024 )); then
            printf 'save=true\n' >> "$GITHUB_OUTPUT"
        else
            printf 'Skip %s cache save: exceeds cache budget or archive space reserve.\n' "$name"
        fi
        ;;
    finish-save)
        now=$(date +%s)
        printf '{"stage":"%s-cache-save","start_epoch":%s,"end_epoch":%s,"status":"%s"}\n' \
            "$name" "${4:-$now}" "$now" "${3:-skipped}" > "$CI_LOG_DIR/cache-$name-save.json"
        ;;
    *) printf 'Unknown toolchain cache action: %s\n' "$action" >&2; exit 2 ;;
esac
