# YARP device tree — Xiaomi Pad 6 Pro / liuqin

**仅面向小米平板 6 Pro（liuqin）。旧版 TWRP 已通过下文所列真机测试，本次 YARP 构建已通过 CI，尚未经真机验证。仓库名称包含 SM8475，不代表其他同 SoC 设备受支持。**
没有测试其他手机或下文未列出的固件；不建议将 liuqin 镜像用于其他设备。

面向 HyperOS 4 / Android 17 的 YARP 设备适配，基于
[TWRP-Test 的 twrp-16.0 分支](https://github.com/TWRP-Test/platform_manifest_twrp_aosp/tree/twrp-16.0)。
Recovery 与解密主体来自上游；本项目保留 liuqin 硬件配置、安全服务集成和有日志依据的修复。
上游仓库、产品和构建变量仍沿用 TWRP 命名。

## CI 构建

在 [Actions](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/workflows/build.yml)
中手动运行 **Build YARP for liuqin**，选择需要构建的分支。也可使用：

```sh
gh workflow run build.yml --repo 7ac9d42/twrp_device_xiaomi_SM8475 --ref main
```

构建使用标准 GitHub-hosted `ubuntu-24.04`、锁定 manifest、浅同步和 clang sparse checkout。
默认同步并发为 8、编译并发为 4，Soong Go 内存目标 6 GiB，swap 总计约 8 GiB。
通过 Actions cache 持久化最多 5 GiB 的 ccache；源码和 `out/` 不做整体缓存。
缓存受 GitHub 分支作用域限制；迁移到尚无兼容缓存的分支（包括首次合入 main）时，
首轮仍需填充缓存，后续运行才能获得暖缓存收益。
runner 会按白名单释放无关 SDK 空间，分配 swap 后为首次同步保留至少 100 GiB，
并在编译前检查至少 25 GiB 剩余空间；
阶段超时或磁盘余量不足会终止任务并上传诊断。
同步与编译输出会实时显示在 Actions 日志中，每 30 秒输出阶段耗时和资源摘要；
运行汇总页同时列出阶段耗时、缓存传输耗时、资源采样和 ccache 命中率。

厂商载荷从本仓库现有 `v1.0.0/recovery.img` 恢复，验证整镜像及清单内每个文件的 SHA-256；
新版 Recovery 和系统运行库从锁定的上游源码编译。无需下载整套固件。
载荷不纳入 Git，原始固件提取入口 `tools/extract-files.py --super ... --reader ...` 继续保留。

成功后下载 `yarp-liuqin-<run_number>` artifact，包含 `recovery.img`、`SHA256SUMS`、
完整源码 manifest 和设备树提交。检查与构建日志存放在独立 diagnostics artifact，保留 14 天。
CI 不创建 Release。CI 通过代表构建与静态检查通过，新版触控、密码解密和重启仍需真机验证。

优化前的基线是 2026-11-10 的[成功构建 #2](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/42769591941)
使用设备树提交 `29d8ba4b359f9cbc3b4fe4343aec9da43304126d`，artifact 为 `yarp-liuqin-2`。
标准 runner 冷缓存构建全流程约 106 分钟，结束时磁盘剩余约 28 GiB。
镜像大小为 104857600 字节（100 MiB），SHA-256：

```text
470f23ba9563cb9b860a3e1991272563985a6ae4445862ace884d7d291b5a081
```

锁定清单包含 398 个项目，Linux 构建实际使用 397 个；macOS Bazel 项目标记为 `notdefault`，
未参与构建。下载产物中的 resolved manifest 已核对，所有实际项目的提交均与锁定清单一致。

### CI 性能实测

同一锁定源码、标准四核 runner 的两次优化后构建均通过镜像验证，设备树提交为
`d61e65d17d385fd571b20c0fa07eac4efdc01dd0`。

| 项目 | 优化前 #2 | 首次填充缓存 [#4](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/42787439077) | 恢复缓存 [#5](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/42796996648) |
| --- | --- | --- | --- |
| 源码同步 | 24:28 | 20:59 | 24:28 |
| 编译 | 78:42 | 39:02 | 25:48 |
| runner 执行总时长 | 106:27 | 63:02 | 53:23 |
| ccache 可缓存调用命中率 | 未启用 | 36.68% | 100%（13238/13238） |

时间单位为分:秒。编译时间取上游构建日志，其余取阶段计时和 job 起止时间；
总时长包含缓存传输、环境准备、验证和上传，不包含排队。
首次构建也会复用本次运行中已产生的相同编译结果，因此命中率不为零。
暖缓存恢复耗时 9 秒，精确命中后跳过重复保存；缓存实际约 0.8 GiB。
100% 只表示可缓存调用命中，Soong、Rust、链接等工作仍需执行。

编译阶段采样平均 CPU 使用率约 96% / 93%，最低可用内存约 1.8 / 1.6 GiB，
swap 使用峰值约 176 / 121 MiB，磁盘最低余量约 26 GiB。
同步阶段平均 CPU 使用率仅约 11% / 15%，仍受网络影响，不能将更高并发等同于稳定提速。
这些数据为本次测量结果，不保证每次 runner 和网络环境相同。

最新性能验证镜像来自 `yarp-liuqin-5`，大小 104857600 字节；下载后的哈希与
`SHA256SUMS` 和镜像检查报告一致，SHA-256：

```text
1a46c96b5e8e769e83d05fcba50a3bf528fead0ff95341854f75ed969a1e5b63
```

## 旧版 TWRP 已验证范围

已测试固件（Android 17）：

- OS4.0.0.129.XMYCNXM：启动、解密及基本功能。
- OS4.0.0.133.XMYCNXM：完整卡刷包安装与系统启动。

测试包作者：**酷安 @做梦书**

| 项目 | 结果 |
| --- | --- |
| Recovery 启动、主界面、触控、亮屏 | 真机通过 |
| metadata 加密分区 | 解密并挂载成功 |
| 用户 0 锁屏密码解密 | 在 liuqin 上实测通过 |
| 内部存储 | 在 liuqin 上实测通过 |
| ADB、安全服务、电池/充电状态 | 正常 |
| MTP | 在 liuqin 上实测通过 |
| 完整卡刷包安装 | 实测正常，OS4.0.0.133.XMYCNXM 包刷入后启动成功 |
| Boot 分区镜像刷入 | 在 liuqin 上实测正常 |
| TWRP 自刷入 | 在 liuqin 上实测正常 |
| fastbootd、增量 OTA、其他用户配置 | 未做真机操作测试 |
| 从 TWRP 重启系统 | 在 liuqin 上实测正常 |

镜像为独立 recovery：header v4、无内核、上限 104857600 字节。
已测试镜像 SHA-256：

    833b8ed065ce25dca4ab1faea8bbbd8c3077e90a3dde60aa0a10fea9a4f6ffbe

不同构建的镜像哈希可能因时间戳等因素不同

## 项目文档

- [改动说明](docs/CHANGES.md)
- [上游致谢与固定版本](docs/UPSTREAM.md)
- [许可证范围](docs/LICENSING.md)

## 致谢

感谢 **Team Win、Dees_Troy、bigbiff、TWRP-Test、AOSP、LineageOS、
The Linux Foundation / Qualcomm、ymdzq 与 EROFS 作者**。
具体贡献与继承关系见 [UPSTREAM.md](docs/UPSTREAM.md)；致谢不代表上游为本项目背书。

原创工具和文档采用 MIT；继承代码与补丁继续遵守各自许可证，详见 NOTICE。
