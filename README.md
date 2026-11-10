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
默认同步与编译并发均为 2，Soong Go 内存目标 6 GiB，swap 总计约 8 GiB，禁用 ccache。
runner 会按白名单释放无关 SDK 空间，分配 swap 后为首次同步保留至少 100 GiB，
并在编译前检查至少 25 GiB 剩余空间；
阶段超时或磁盘余量不足会终止任务并上传诊断。

厂商载荷从本仓库现有 `v1.0.0/recovery.img` 恢复，验证整镜像及清单内每个文件的 SHA-256；
新版 Recovery 和系统运行库从锁定的上游源码编译。无需下载整套固件。
载荷不纳入 Git，原始固件提取入口 `tools/extract-files.py --super ... --reader ...` 继续保留。

成功后下载 `yarp-liuqin-<run_number>` artifact，包含 `recovery.img`、`SHA256SUMS`、
完整源码 manifest 和设备树提交。检查与构建日志存放在独立 diagnostics artifact，保留 14 天。
CI 不创建 Release。CI 通过代表构建与静态检查通过，新版触控、密码解密和重启仍需真机验证。

2026-11-10 的[成功构建 #2](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/42769591941)
使用设备树提交 `29d8ba4b359f9cbc3b4fe4343aec9da43304126d`，artifact 为 `yarp-liuqin-2`。
标准 runner 冷缓存构建全流程约 106 分钟，结束时磁盘剩余约 28 GiB。
镜像大小为 104857600 字节（100 MiB），SHA-256：

```text
470f23ba9563cb9b860a3e1991272563985a6ae4445862ace884d7d291b5a081
```

锁定清单包含 398 个项目，Linux 构建实际使用 397 个；macOS Bazel 项目标记为 `notdefault`，
未参与构建。下载产物中的 resolved manifest 已核对，所有实际项目的提交均与锁定清单一致。

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
