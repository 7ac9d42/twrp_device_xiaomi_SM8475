#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""将阶段计时和资源采样汇总到 Actions 页面。"""

import argparse
import json
import os
from pathlib import Path
import re


def duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def summarize(logs, source):
    lines = [
        "## YARP CI 性能与进度",
        "",
        f"编译并发 {os.environ.get('JOBS', '?')}；"
        f"同步并发 {os.environ.get('SYNC_JOBS', '?')}；"
        f"Soong Go 内存目标 {os.environ.get('SOONG_GOMEMLIMIT', '?')}；"
        f"ccache 上限 {os.environ.get('CCACHE_MAX_SIZE', '?')}。",
        "",
        "| 阶段 | 耗时 | 结果 |",
        "| --- | --- | --- |",
    ]
    timings = []
    for path in sorted(logs.glob("*/timing.json")) + sorted(logs.glob("cache-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "end_epoch" not in data:
                continue
            elapsed = int(data["end_epoch"]) - int(data["start_epoch"])
            status = data.get("status")
            if status is None:
                status = "success" if data["exit_status"] == 0 else f"exit {data['exit_status']}"
            timings.append((int(data["start_epoch"]), data["stage"], elapsed, status))
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"Cannot summarize {path.name}: {error}")
    for _, stage, elapsed, status in sorted(timings):
        lines.append(f"| {stage} | {duration(elapsed)} | {status} |")
    if not timings:
        lines.append("| 尚无已完成阶段 | — | 请查看实时日志 |")

    sample = re.compile(
        r"CPU=(\d+)% available=(\d+)MiB swap-used=(\d+)MiB disk-free=(\d+)MiB"
    )
    lines += [
        "",
        "| 阶段 | 平均 CPU 使用率 | 最低可用内存 | 最高 swap 使用 | 最低磁盘余量 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for path in sorted(logs.glob("*/resources.log")):
        samples = []
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                match = sample.search(line)
                if match:
                    samples.append(tuple(map(int, match.groups())))
        if not samples:
            continue
        # 首次采样还没有 CPU 差分，最后一次为整个阶段平均值。
        cpu_samples = samples[1:-1] or samples[-1:]
        cpu = sum(item[0] for item in cpu_samples) / len(cpu_samples)
        minimum_mem = min(item[1] for item in samples) / 1024
        maximum_swap = max(item[2] for item in samples)
        minimum_disk = min(item[3] for item in samples) / 1024
        stage = path.parent.name.rsplit(".", 1)[0]
        lines.append(
            f"| {stage} | {cpu:.0f}% | {minimum_mem:.1f} GiB | "
            f"{maximum_swap} MiB | {minimum_disk:.1f} GiB |"
        )
    lines += ["", "资源数据为每 30 秒采样，可能漏掉短时峰值。"]

    stats = source / "logs" / "ccache-after.txt"
    if stats.is_file():
        lines += ["", "### 本次编译缓存统计", "", "```text"]
        lines.extend(stats.read_text(encoding="utf-8", errors="replace").splitlines())
        lines += ["```"]
    lines += [
        "",
        "对比基线：同步 00:24:28、构建 01:18:42。"
        "缓存传输和其余步骤也占用运行时间，应结合 Actions 总耗时判断净收益。",
        "",
        "镜像静态检查结果见 Verify the final image 步骤；设备运行仍需真机验证。",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.logs, args.source)
    with args.summary.open("a", encoding="utf-8") as stream:
        stream.write(report)
    print(report)


if __name__ == "__main__":
    main()
