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


def ninja_lines(stream):
    """还原 Ninja 的 $ 换行，忽略续行缩进；转义的 $$ 不触发续行。"""
    parts = []
    for physical in stream:
        text = physical.rstrip("\n")
        if parts:
            text = text.lstrip(" \t")
        trailing_dollars = len(text) - len(text.rstrip("$"))
        if trailing_dollars % 2:
            parts.append(text[:-1])
            continue
        yield "".join(parts) + text
        parts.clear()


def rust_actions(source):
    """按 Soong rustc 规则匹配 Ninja 已完成动作，不推测编译器内部命中率。"""
    outputs = set()
    for graph in sorted((source / "out/soong").glob("build*.ninja")):
        with graph.open(encoding="utf-8", errors="replace") as stream:
            for line in ninja_lines(stream):
                if not line.startswith("build "):
                    continue
                paths, separator, rule = line[6:].partition(": ")
                if separator and rule.split(maxsplit=1)[0].endswith("rustc"):
                    outputs.update(paths.split())
    actions = {}
    for log in (source / "out/.ninja_log", source / "out/soong/.ninja_log"):
        if not log.is_file():
            continue
        with log.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                fields = line.rstrip("\n").split("\t")
                if len(fields) != 5 or fields[3] not in outputs:
                    continue
                try:
                    elapsed = int(fields[1]) - int(fields[0])
                except ValueError:
                    continue
                if elapsed >= 0:
                    # 一个输出在日志中可能出现多次，保留最后一次已完成动作。
                    actions[fields[3]] = {"output": fields[3], "elapsed_ms": elapsed,
                                          "command_hash": fields[4]}
    return sorted(actions.values(), key=lambda item: item["output"])


def summarize_rust(logs, source):
    lines = ["", "### Rust 增量缓存", ""]
    restore = logs / "cache-rust-restore.json"
    if restore.is_file():
        state = json.loads(restore.read_text(encoding="utf-8"))
        lines.append(f"Actions 精确键命中：{state.get('exact_hit', 'unknown')}；"
                     f"实际激活：{state.get('restored', False)}；"
                     f"staging 检查尺寸：{state.get('size_kib', 0)} KiB。")
    sizes = []
    for phase in ("before", "after"):
        path = source / f"logs/rust-cache-{phase}-kib.txt"
        sizes.append(str(int(path.read_text().strip())) if path.is_file() else "未知")
    lines.append(f"完整 out/rustc：构建前 {sizes[0]} KiB，构建后 {sizes[1]} KiB；保存上限 3 GiB。")
    budget = logs / "rust-cache-save-budget.json"
    if budget.is_file():
        state = json.loads(budget.read_text(encoding="utf-8"))
        lines.append(f"保存检查：{state['size_kib']} KiB；可用磁盘 {state['available_kib']} KiB。")
    actions = rust_actions(source)
    (logs / "rust-actions.json").write_text(
        json.dumps(actions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines.append(f"匹配 Soong rustc 规则的已完成动作 {len(actions)} 个；"
                 f"动作耗时合计 {sum(item['elapsed_ms'] for item in actions) / 1000:.3f} 秒"
                 "（并行动作相加，不是墙钟耗时）。逐输出耗时与 Ninja 命令 hash 见 rust-actions.json。")
    lines += [
        "Actions 命中和目录尺寸均不证明 rustc 内部复用；未启用不稳定的统计接口。"
        "请比较同 commit、同参数的冷暖两轮动作耗时、命令 hash、构建资源和缓存传输耗时；"
        "0 个动作表示未匹配到已完成记录，不能推断为全部复用。",
        "固定 Soong 启用增量开关后不再强制 codegen-units=1，通常使用增量默认 256 CGU；"
        "冷暖两轮均使用这一配置。相对旧基线的差异还包含 CGU 变化，应检查内存峰值和最终镜像验证。",
    ]
    return lines


def summarize(logs, source):
    lines = [
        "## YARP CI 性能与进度",
        "",
        f"Soong 前端并发 {os.environ.get('JOBS', '?')}、"
        f"Ninja 后端并发 {os.environ.get('BACKEND_JOBS', '?')}；"
        f"同步网络并发 {os.environ.get('SYNC_JOBS', '?')}、"
        f"checkout 并发 {os.environ.get('SYNC_CHECKOUT_JOBS', '?')}；"
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

    restore = logs / "cache-restore.json"
    if restore.is_file():
        try:
            state = json.loads(restore.read_text(encoding="utf-8"))
            if "restored" in state:
                restored = "已恢复" if state["restored"] else "未恢复"
                lines += ["", f"ccache 历史缓存：{restored}；精确键命中：{state.get('exact_hit', 'unknown')}。"]
                if not state["restored"]:
                    lines += ["以下命中可能来自本轮内部重复编译，不能视为跨运行缓存复用。"]
        except (OSError, ValueError, TypeError) as error:
            print(f"Cannot summarize cache restore: {error}")

    stats = source / "logs" / "ccache-after.txt"
    if stats.is_file():
        lines += ["", "### 本次编译缓存统计", "", "```text"]
        lines.extend(stats.read_text(encoding="utf-8", errors="replace").splitlines())
        lines += ["```"]
    try:
        lines += summarize_rust(logs, source)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print(f"Cannot summarize Rust cache: {error}")
    lines += [
        "",
        "历史优化前基线：CI #2（run 42769591941）的命令阶段为同步 00:24:28、构建 01:18:42；"
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
