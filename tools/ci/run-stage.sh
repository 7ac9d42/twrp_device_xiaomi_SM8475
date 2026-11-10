#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Usage: CI_LOG_DIR=... CI_DEADLINE=<unix seconds> bash run-stage.sh <stage> <command> [args...]
# The caller sets one deadline for the entire job (normally job start + 330 min).
# Command output and 30-second resource snapshots go into a unique stage directory.
set -euo pipefail
set +m
export LC_ALL=C

fail() { printf 'run-stage: %s\n' "$*" >&2; exit 125; }
(( $# >= 2 )) || fail 'usage: run-stage.sh <stage> <command> [args...]'
stage=$1
shift
[[ $stage =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] || fail 'invalid stage name'
[[ -n ${CI_LOG_DIR:-} ]] || fail 'CI_LOG_DIR is required'
[[ ${CI_DEADLINE:-} =~ ^[1-9][0-9]{0,10}$ ]] || fail 'CI_DEADLINE must be a Unix timestamp in seconds'
remaining=$((CI_DEADLINE - $(date +%s)))
if (( remaining <= 0 )); then
    printf 'run-stage: shared CI deadline has already expired\n' >&2
    exit 124
fi
for tool in setsid timeout df free; do
    command -v "$tool" >/dev/null || fail "required tool is unavailable: $tool"
done
mkdir -p -- "$CI_LOG_DIR"
log_dir=$(mktemp -d "$CI_LOG_DIR/${stage}.XXXXXXXX")
command_log="$log_dir/command.log"
resource_log="$log_dir/resources.log"
started=$(date +%s)
last_cpu_total=0
last_cpu_idle=0
resource_paths=("$PWD" "$CI_LOG_DIR")
if [[ -n ${SOURCE_ROOT:-} && -d $SOURCE_ROOT ]]; then
    resource_paths+=("$SOURCE_ROOT")
fi
printf 'Stage %s: deadline=%s; logs=%s\n' "$stage" "$CI_DEADLINE" "$log_dir"
printf 'Command:' > "$command_log"
printf ' %q' "$@" >> "$command_log"
printf '\n' >> "$command_log"

# Return an error on failed measurements as well as on low space; do not keep
# building after the monitor can no longer measure the filesystems being used.
resources() {
    local path output available minimum=9223372036854775807
    local key value mem_available=0 swap_total=0 swap_free=0
    local cpu_user cpu_nice cpu_system cpu_idle cpu_wait cpu_irq cpu_softirq cpu_steal
    local cpu_total cpu_inactive cpu_busy=0 elapsed pressure line
    {
        date -u '+%Y-%m-%dT%H:%M:%SZ'
        df -h -- "${resource_paths[@]}"
        free -h
        for pressure in cpu memory io; do
            if [[ -r /proc/pressure/$pressure ]]; then
                while IFS= read -r line; do
                    printf 'pressure %s %s\n' "$pressure" "$line"
                done < "/proc/pressure/$pressure"
            fi
        done
        while read -r key value; do
            case $key in
                pswpin|pswpout) printf '%s %s\n' "$key" "$value" ;;
            esac
        done < /proc/vmstat
    } >> "$resource_log" 2>&1 || return 1
    for path in "${resource_paths[@]}"; do
        output=$(df -B1 --output=avail -- "$path") || return 1
        available=${output##*$'\n'}
        [[ $available =~ ^[[:space:]]*([0-9]+)[[:space:]]*$ ]] || return 1
        available=${BASH_REMATCH[1]}
        (( available >= minimum )) || minimum=$available
        if (( available < 3 * 1024 * 1024 * 1024 )); then
            printf 'Free space below 3 GiB: %s (%s bytes)\n' "$path" "$available" >> "$resource_log"
            return 1
        fi
    done
    while read -r key value _; do
        case $key in
            MemAvailable:) mem_available=$value ;;
            SwapTotal:) swap_total=$value ;;
            SwapFree:) swap_free=$value ;;
        esac
    done < /proc/meminfo
    read -r _ cpu_user cpu_nice cpu_system cpu_idle cpu_wait cpu_irq cpu_softirq cpu_steal _ < /proc/stat
    cpu_total=$((cpu_user + cpu_nice + cpu_system + cpu_idle + cpu_wait + cpu_irq + cpu_softirq + cpu_steal))
    cpu_inactive=$((cpu_idle + cpu_wait))
    if (( last_cpu_total > 0 && cpu_total > last_cpu_total )); then
        cpu_busy=$((100 * (cpu_total - last_cpu_total - cpu_inactive + last_cpu_idle) / (cpu_total - last_cpu_total)))
    fi
    last_cpu_total=$cpu_total
    last_cpu_idle=$cpu_inactive
    elapsed=$(($(date +%s) - started))
    printf '[%s] elapsed=%02d:%02d:%02d CPU=%s%% available=%sMiB swap-used=%sMiB disk-free=%sMiB\n' \
        "$stage" "$((elapsed / 3600))" "$((elapsed / 60 % 60))" "$((elapsed % 60))" \
        "$cpu_busy" "$((mem_available / 1024))" "$(((swap_total - swap_free) / 1024))" \
        "$((minimum / 1024 / 1024))" | tee -a "$resource_log"
}
resources || fail "insufficient disk space or resource check failed; see $resource_log"

stage_pid=
logger_pid=
log_fd=
monitor_pid=
wait_interrupted=false
forced_status=0
supervisor_pid=$BASHPID

stop_stage() {
    [[ -n $stage_pid ]] || return 0
    kill -0 -- "-$stage_pid" 2>/dev/null || return 0
    printf 'Sending TERM to stage process group %s\n' "$stage_pid" >> "$resource_log"
    kill -TERM -- "-$stage_pid" 2>/dev/null || true
    local tick
    for ((tick = 0; tick < 30; tick++)); do
        kill -0 -- "-$stage_pid" 2>/dev/null || return 0
        sleep 1
    done
    kill -KILL -- "-$stage_pid" 2>/dev/null || true
}

stop_monitor() {
    if [[ -n $monitor_pid ]]; then
        kill -TERM "$monitor_pid" 2>/dev/null || true
        wait "$monitor_pid" 2>/dev/null || true
        monitor_pid=
    fi
}

interrupt() {
    wait_interrupted=true
    forced_status=$1
    # Disable further signals while the 30-second termination grace is running.
    trap '' INT TERM USR1
    stop_monitor
    stop_stage
}

finish() {
    local status=$? logger_status=0 ended
    trap - EXIT
    trap '' INT TERM USR1
    stop_monitor
    # Also collect descendants left behind by an exited command/timeout.
    stop_stage
    if [[ -n $log_fd ]]; then
        exec {log_fd}>&-
        log_fd=
    fi
    if [[ -n $logger_pid ]]; then
        wait "$logger_pid" || logger_status=$?
        if (( status == 0 && logger_status != 0 )); then
            status=$logger_status
        fi
    fi
    resources || true
    ended=$(date +%s)
    printf '{"stage":"%s","start_epoch":%s,"end_epoch":%s,"exit_status":%s}\n' \
        "$stage" "$started" "$ended" "$status" > "$log_dir/timing.json"
    printf 'Exit status: %s\n' "$status" >> "$resource_log"
    if (( status != 0 )); then
        printf 'Last 80 command log lines for %s:\n' "$stage"
        tail -n 80 -- "$command_log" || true
    fi
    printf 'Stage %s exited %s; logs=%s\n' "$stage" "$status" "$log_dir"
    exit "$status"
}
trap finish EXIT
trap 'interrupt 130' INT
trap 'interrupt 143' TERM
trap 'interrupt 125' USR1

monitor() {
    local sleep_pid=
    trap 'if [[ -n $sleep_pid ]]; then kill "$sleep_pid" 2>/dev/null || true; wait "$sleep_pid" 2>/dev/null || true; fi; exit 0' INT TERM
    trap - EXIT USR1
    while true; do
        sleep 30 &
        sleep_pid=$!
        wait "$sleep_pid" || return 0
        sleep_pid=
        if ! resources; then
            printf 'run-stage: low disk space or resource measurement failed; stopping %s\n' "$stage" >&2
            kill -USR1 "$supervisor_pid" 2>/dev/null || true
            return 0
        fi
    done
}

# With job control disabled, setsid runs without forking: $! is the session and
# process-group leader. timeout signals this group at the shared deadline.
# Avoid --foreground: it would only time out the immediate command.
remaining=$((CI_DEADLINE - $(date +%s)))
(( remaining > 0 )) || exit 124
exec {log_fd}> >(tee -a "$command_log")
logger_pid=$!
setsid timeout --signal=TERM --kill-after=30s "${remaining}s" "$@" >&"$log_fd" 2>&1 &
stage_pid=$!
# Only the stage holds the writer; the logger can finish when its output closes.
exec {log_fd}>&-
log_fd=
monitor &
monitor_pid=$!
while true; do
    wait_interrupted=false
    status=0
    wait "$stage_pid" || status=$?
    # A trapped signal interrupts wait; wait again to collect the child status.
    [[ $wait_interrupted == true ]] || break
done
# Preserve ordinary command exit codes and timeout's 124/137. A monitor-triggered
# cancellation must still fail if the command handles TERM by exiting zero.
if (( status == 0 && forced_status != 0 )); then
    status=$forced_status
fi
exit "$status"
