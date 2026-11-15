# YARP device tree — Xiaomi Pad 6 Pro / liuqin

**仅面向小米平板 6 Pro（liuqin）。YARP #8 已实测启动、metadata 解密、用户 0 密码解密及内部存储目录访问；后续维护改动尚未经新镜像验证。仓库名称包含 SM8475，不代表其他同 SoC 设备受支持。**
没有测试其他手机或下文未列出的固件；不建议将 liuqin 镜像用于其他设备。

面向 HyperOS 4 / Android 17 的 YARP 设备适配，基于
[TWRP-Test 的 twrp-16.0 分支](https://github.com/TWRP-Test/platform_manifest_twrp_aosp/tree/twrp-16.0)。
Recovery 与解密主体来自上游；本项目保留 liuqin 硬件配置、安全服务集成和有日志依据的修复。
上游仓库、产品和构建变量仍沿用 TWRP 命名。

系统 release、系统安全补丁和 vendor 安全补丁通过上游 `TW_OVERRIDE_SYSTEM_PROPS`
在启动时读取已安装的 system/vendor，不再固定编译版本和补丁日期；SDK 保持上游构建值。
QSEE、Keymaster、KeyMint、Gatekeeper 和 keystore2 等待上游 `twrp.storage.ready=1`，
该通知位于属性覆盖与临时挂载清理之后、data 解密之前。
锁定上游的属性名单存在二次字符串化缺陷，以一行补丁修正消费点，动态读取流程不变。
动态属性方案已通过本地宏消费探针、CI #7/#8 构建及镜像配置和启动检查，
并在 #8 完成 metadata 和用户 0 密码解密实测。后续 GPT 健壮性和 USB 清理仅完成本地验证，尚未构建新镜像。

## CI 构建

在 [Actions](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/workflows/build.yml)
中手动运行 **Build YARP for liuqin**，选择需要构建的分支。也可使用：

```sh
gh workflow run build.yml --repo 7ac9d42/twrp_device_xiaomi_SM8475 --ref main
```

构建使用标准 GitHub-hosted `ubuntu-24.04`、锁定 manifest、浅同步和 clang sparse checkout。
固定 repo v2.71，同步网络并发为 16、checkout 并发为 4，编译并发为 4；
Soong Go 内存目标 6 GiB，swap 总计约 8 GiB。
clang 与 Rust 先取浅层元数据、配置 sparse，再和其余项目共用一个 checkout 池；
保留主 clang、bindgen clang 及当前 Rust，排除 Rust 的 Darwin、Windows 和旧 Linux 版本。
通过 Actions cache 在同步前恢复最多 5 GiB 的 ccache；编译前仍要求至少 25 GiB 可用空间。
clang 单项目 Git 对象库另按精确提交和 sparse 清单缓存，最多 3 GiB，超出则跳过保存；
其余源码、完整 `.repo` 和 `out/` 不做整体缓存。
ccache 优先恢复同工具链缓存，再回退到同平台缓存，由编译器内容校验保证正确性。
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
CI 不创建 Release。CI 通过仅代表构建与静态检查通过，不能替代真机验证；已验证范围见下文。

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

2026-11-15 的 #6 独立 clang checkout 为 23:24；同步后只剩约 27 GiB，旧流程因低于
30 GiB 而跳过 ccache 恢复，最终命中率 36.67% 主要来自本轮重复编译。
本轮将 clang/Rust 与其余项目共用 checkout 池、精简已核实的工具链选集，并提前恢复 ccache。

标准四核 runner 上的 #7/#8 使用同一设备树提交
`0f98e394497d25654552f23cb8d518cc62c0f9d7`，均通过完整镜像验证：

| 项目 | 优化前 [#6](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43679041315) | 首轮 [#7](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43693513770) | 重复运行 [#8](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43696856323) |
| --- | --- | --- | --- |
| 源码同步步骤 | 38:59 | 11:45 | 9:40 |
| 编译步骤 | 39:09 | 26:57 | 18:15 |
| runner 执行总时长 | 81:41 | 42:29 | 30:50 |
| 历史 ccache 恢复 | 跳过 | 兼容键恢复 | 精确键恢复 |
| ccache 可缓存调用命中率 | 36.67% | 99.98%（13236/13238） | 100%（13238/13238） |
| clang 对象库恢复 | 未启用 | 未命中，构建后保存 | 精确命中 |

时间单位为分:秒。步骤时间取 Actions 的起止时间，总时长取 job 起止时间，包含缓存传输、
环境准备、验证和上传，不包含排队。#6 同步命令本身为 38:50，步骤总时长为 38:59。
#7 已恢复历史 ccache，只有 clang 对象缓存是冷的，不能将它称为完全冷缓存构建。
#8 的 ccache 恢复耗时 7 秒、clang 对象库恢复耗时 9 秒，精确命中后均跳过重复保存。
ccache 实际约 0.8 GiB，clang 对象库保存前约 1.10 GiB，均低于各自预算。
100% 只表示可缓存调用命中，Soong、Rust、链接等工作仍需执行。

相对 #6，#8 同步步骤缩短约 75%，runner 总时长缩短约 62%。这些是两次实际运行结果，
不是固定耗时保证；runner、网络及缓存状态均会影响结果，不能把差异全部归因于单一参数。
后续补充的缓存恢复异常隔离已通过五组本地模拟及只读复核，未额外运行第三轮 CI；
上述数据和镜像对应提交 `0f98e39`，不包含该失败路径防护。

最新性能验证镜像来自 `yarp-liuqin-8`，大小 104857600 字节；下载后的哈希与
`SHA256SUMS` 和镜像检查报告一致，397 个实际源码项目的提交均与锁定清单一致。
SHA-256：

```text
e48be16c07a38b6f653bebb5d10647d5020c1171ade87dbd66afb441595c49e1
```

### 进一步并行优化的证据与边界

#8 的诊断将构建分为 Soong bootstrap 约 5:41、主 Kati 约 0:48、最终 Ninja 后端约 11:31。
其中单条 Android.bp 分析/生成图命令约 4:56，Soong 峰值 RSS 约 13 GB；构建最低可用内存
约 2272 MiB，并使用了 swap。增加外层 jobs 不能直接拆分这条生成图命令。

按 Ninja 日志去重多输出后，后端约 95.6% 的时间同时运行 4 条命令，CPU 采样均值约 94.7%；
Rust、链接和生成步骤也不受 C/C++ ccache 全命中覆盖。因此当前仍保持网络 16、checkout 4、构建 4，
不直接改为全程 `-j8`。若开展对照实验，优先只调整最终后端为 `-j6`，保持前端为 4；
当前 `JOBS` 同时影响前后端，须先核对锁定 Soong 的独立覆盖接口，不能仅修改该变量。
同步 checkout 4→6 可作为独立的第二项实验，但 #8 同步阶段 I/O full stall 累计约 158 秒，
更高并发也可能增加磁盘竞争，不能仅凭低 CPU 判断网络池不足。

#8 两次缓存恢复分别为 7 秒和 9 秒，载荷下载/提取仅约 2 秒，将它们并行只能争取秒级收益；
拆分多个 hosted job 则会重复同步和前端工作。#7/#8 同提交同并发的构建子阶段仍相差约 1.5 倍，
小幅优化必须在相同精确缓存命中状态下交替比较阶段及总耗时，并核对内存、swap 和 PSI。
以上是既有日志分析，不是新并发参数的实测结果。

## YARP 已验证范围

2026-11-15，在 liuqin 上实测了上述
[`yarp-liuqin-8`](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43696856323)，
设备树提交 `0f98e394497d25654552f23cb8d518cc62c0f9d7`，镜像大小及 SHA-256 见上一节。

- 经有线 root ADB 写入 recovery_a 并重启成功，整分区读回哈希与产物一致，未进入 fastboot。
- 运行时动态属性为 release=17、system patch=2026-10-01、vendor patch=2026-02-01。
- metadata 解密成功，data 经解密映射设备以 F2FS 挂载。
- 用户仅在设备输入密码，日志确认 `User 0 Decrypted Successfully!`，
  `twrp.user.0.decrypt=1`、`twrp.all.users.decrypted=true`，`/data/media/0` 可访问。
- 随后同一镜像写入 recovery_b，A/B 整分区哈希均一致；写 B 槽时未切槽或重启，不能据此声称 B 槽启动通过。
- 触控可用，但用户复测报告解密页出现后约 10 秒才可用，估计误差约 ±3 秒。

MTP 文件传输、ROM 安装后的自动重装、fastbootd 切槽和重启系统仍未完成本轮验收。
以上结论仅对应 #8，不涵盖后续 GPT 和 USB 维护改动。

## 已知限制与待核实项

- 锁定上游的安装后自动重装只在无 `update-binary` 的成功 payload 安装分支调用；
  独立 A/B recovery 分支复制安装后的当前槽 recovery 到另一槽，未保存安装前的镜像，
  自动调用方也未检查重装返回值。因此该选项不能保证刷包后仍保留 YARP。
  本次采集仅保留 Fox 会话，未取得导致覆盖的 YARP 刷包日志，不能断言实际命中了哪条路径。
- 解密页可见不代表触控固件已就绪。#8 同次启动中触控 probe 约 4.21 秒完成，
  固件约 18.42 秒才被请求，18.61 秒更新完成。实装驱动的启动固件任务固定延后
  3500 jiffies，在 CONFIG_HZ=250 下为 14 秒；当前没有可调延迟参数。
  early-fs 约 3.87 秒才执行，与 probe 开始只差约 0.32 秒，因此不引入额外早加载。
  上游已有输入热插拔支持，不加等待或重扫补丁，也不修改驱动或其他分区。
  解密页首帧、首个有效触控事件与 UI 响应的统一时间戳仍缺失，不能把 14 秒等同于页面等待时长。
- GPT 维护修复已经过宿主合成 I/O、ASan/UBSan 回归测试，但尚未经 Android CI 和新镜像实测；
  不声称真实切槽、UFS BSG 或断电恢复已验证。

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
