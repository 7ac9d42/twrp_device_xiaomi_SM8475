# YARP device tree — Xiaomi Pad 6 Pro / liuqin

**仅面向小米平板 6 Pro（liuqin）。YARP #9 已通过 main CI，并实测启动、metadata 解密、用户 0 密码解密及内部存储目录访问；用户确认显示和触控正常。仓库名称包含 SM8475，不代表其他同 SoC 设备受支持。**
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
动态属性方案已通过本地宏消费探针、CI #7/#8/#9 构建及镜像配置和启动检查，
并在 #8/#9 完成 metadata 和用户 0 密码解密实测。GPT 健壮性和 USB 清理已纳入 #9，
同时通过 CI 合成 I/O 回归、Android 编译及下述 A 槽实机检查。

## CI 构建

在 [Actions](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/workflows/build.yml)
中手动运行 **Build YARP for liuqin**，选择需要构建的分支。也可使用：

```sh
gh workflow run build.yml --repo 7ac9d42/twrp_device_xiaomi_SM8475 --ref main
```

构建使用标准 GitHub-hosted `ubuntu-24.04`、锁定 manifest、浅同步和 clang sparse checkout。
固定 repo v2.71，同步网络并发为 16、checkout 并发为 4，Soong 前端并发为 4、最终 Ninja 后端并发为 6；
Soong Go 内存目标 6 GiB，swap 总计约 8 GiB。
clang 与 Rust 先取浅层元数据、配置 sparse，再和其余项目共用一个 checkout 池；
保留主 clang、bindgen clang 及当前 Rust，排除 Rust 的 Darwin、Windows 和旧 Linux 版本。
通过 Actions cache 在同步前恢复最多 5 GiB 的 ccache；编译前仍要求至少 25 GiB 可用空间。
Clang 和 Rust 工具链的 Git 对象库独立按 runner 平台、锁定提交和各自的 sparse 清单精确缓存，
预算分别为 3 GiB 和 2 GiB；仅在镜像验证通过、未精确命中且磁盘余量充足时保存。
恢复失败或未命中会隔离残留对象库并正常同步；仍按锁定提交完成 checkout 和镜像验证。
其余源码、完整 `.repo` 和 `out/` 不做整体缓存；Rust 工具链缓存不包含编译增量产物。
ccache 优先恢复同工具链缓存，再回退到同平台缓存，由编译器内容校验保证正确性。
缓存受 GitHub 分支作用域限制；迁移到尚无兼容缓存的分支（包括首次合入 main）时，
首轮仍需填充缓存，后续运行才能获得暖缓存收益。
runner 会按白名单释放无关 SDK 空间，分配 swap 后为首次同步保留至少 100 GiB，
并在编译前检查至少 25 GiB 剩余空间；
阶段超时或磁盘余量不足会终止任务并上传诊断。
同步与编译输出会实时显示在 Actions 日志中，每 30 秒输出阶段耗时和资源摘要；
运行汇总页同时列出阶段耗时、缓存传输耗时与精确命中、资源采样和 ccache 命中率。
Rust 工具链缓存默认开启，可通过 `cache_rust_toolchain=false` 关闭作对照。用同一提交、同样的
ccache/Clang 命中状态，比较“Rust 恢复 + 同步”和 job 总耗时；首轮另计保存开销。
当前尚无 Rust 工具链缓存的远端净收益数据。

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

此前全暖缓存基线镜像来自 `yarp-liuqin-8`，大小 104857600 字节；下载后的哈希与
`SHA256SUMS` 和镜像检查报告一致，397 个实际源码项目的提交均与锁定清单一致。
SHA-256：

```text
e48be16c07a38b6f653bebb5d10647d5020c1171ade87dbd66afb441595c49e1
```

2026-11-15 的 main [CI #9](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43713820044)
对应设备树提交 `3f76cfb67f0029c667230ee29cd1cd30e0bf7df4`，通过 GPT 回归和完整镜像检查。
同步步骤为 11:39、构建 26:19、job 总时长 40:52；Soong 前端约 7:53、主 Kati 约 1:09、
最终后端约 16:55。ccache 经兼容键恢复，命中 13233/13238（99.96%），不是精确恢复。
日志确认前端峰值 4 个任务、后端峰值 6 个任务，highmem 仍报告 1；后端 CPU 采样均值约
96.9%，最低可用内存约 6739 MiB，没有观察到严重内存压力。前端最低可用内存约 1972 MiB，
因此不提高其并发。#9 比 #7 的后端快约 13 秒，但比 #8 慢约 324 秒，前端也有类似波动；
没有同一 runner、同一精确缓存状态的交替对照，不能据此证明提速或判定并发回归，暂保留后端 6，不继续加大。

最新实测镜像为 `yarp-liuqin-9`，104857600 字节，header v4、无内核；ZIP、镜像校验和及
397 个实际项目与锁定清单均已核对。SHA-256：

```text
584e71f01888ea23792d4d199e51600ded1651acf9ac68ed7dc7d7c023457606
```

### 进一步并行优化的证据与边界

#8 的诊断将构建分为 Soong bootstrap 约 5:41、主 Kati 约 0:48、最终 Ninja 后端约 11:31。
其中单条 Android.bp 分析/生成图命令约 4:56，Soong 峰值 RSS 约 13 GB；构建最低可用内存
约 2272 MiB，并使用了 swap。增加外层 jobs 不能直接拆分这条生成图命令。

按 Ninja 日志去重多输出后，后端约 95.6% 的时间同时运行 4 条命令，CPU 采样均值约 94.7%；
Rust、链接和生成步骤也不受 C/C++ ccache 全命中覆盖。因此不直接改为全程 `-j8`，
而是保持网络 16、checkout 4、Soong 前端 4，仅将最终后端设为 6。
`JOBS` 仍控制前端，新增 `BACKEND_JOBS` 控制后端；锁定 Soong 的 `NINJA_EXTRA_ARGS`
只追加到最终 Ninja 命令，末尾的 `-j6` 覆盖默认值，不改变 bootstrap 并发。
新参数已通过本地 fixture 和 main CI #9，实际并发及镜像正确性已验证，性能净收益尚未隔离证明。
同步 checkout 4→6 可作为独立的第二项实验，但 #8 同步阶段 I/O full stall 累计约 158 秒，
更高并发也可能增加磁盘竞争，不能仅凭低 CPU 判断网络池不足。

#8 两次缓存恢复分别为 7 秒和 9 秒，载荷下载/提取仅约 2 秒，将它们并行只能争取秒级收益；
拆分多个 hosted job 则会重复同步和前端工作。#7/#8 同提交同并发的构建子阶段仍相差约 1.5 倍，
小幅优化必须在相同精确缓存命中状态下交替比较阶段及总耗时，并核对内存、swap 和 PSI。
#7/#8 是选择新参数的历史依据，#9 的实测结果见前述，不把不同缓存或 runner 状态当作严格对照。

### Rust 增量缓存实验（未保留）

2026-11-15 的 [CI #10](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43722309004)
和 [CI #11](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43726271821)
均通过构建与镜像检查。#10 最初误将 `out/rustc` 作为缓存目录，未保存缓存；
追踪锁定 Soong 的 `PathForOutput` 后，#11 修正为实际的 `out/soong/rustc`。
#11 同步命令阶段 10:16、构建 25:39，320 个 Rust 动作耗时合计 2646.023 秒
（并行动作相加，不是墙钟），ccache 可缓存调用命中 13238/13238。

完整 Rust 增量目录为 4617032 KiB（约 4.40 GiB），超过本次实验自行设定的 3 GiB 保存预算，
因此没有上传，也未执行没有暖缓存可恢复的重复构建。3 GiB 是本项目实验预算，不是 GitHub 平台上限；
本结果不证明更大预算下没有收益。原生 `SOONG_RUSTC_INCREMENTAL` 还会取消固定的
`codegen-units=1`，冷构建耗时不能隔离缓存收益。由于未取得预算内的暖缓存净收益证据，
已撤回该开关、缓存步骤、专项统计与测试，维持前述已验证流程。#10/#11 未进行设备刷写或真机验收。

### 宿主 Rust 编译实验（默认关闭）

同提交的 [#13](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/44311896940)
和 [#14](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/44318083368) 中，
`bindgen` 单个构建动作耗时 119/178 秒、`cxxbridge` 112/146 秒，且 C/C++ 可缓存调用全部命中。
`fast_host_rust=true` 只将锁定 Soong 中 Linux glibc 宿主 Rust 模块的默认优化级别改为 `-C opt-level=1`；
模块显式 flags 仍可覆盖，Android 目标参数、Rust 工具链、构建目标和镜像检查保持不变。
关闭时沿用 `-C opt-level=3`。本地核对补丁与参数边界，不代表 CI 已提速。

验收用同一提交、相同缓存命中状态交替运行两种模式，核对代表性宿主与 Android Rust 命令的最终参数，
比较宿主生成工具及其下游动作、完整编译和 job 总耗时，同时要求镜像检查通过。

## YARP 已验证范围

2026-11-15，在 liuqin 上实测了上述
[`yarp-liuqin-9`](https://github.com/7ac9d42/twrp_device_xiaomi_SM8475/actions/runs/43713820044)，
设备树提交 `3f76cfb67f0029c667230ee29cd1cd30e0bf7df4`，镜像大小及 SHA-256 见上一节。

- 经有线 root ADB 写入 recovery_a 并重启成功，整分区读回哈希与产物一致，未进入 fastboot。
- 运行时动态属性为 release=17、system patch=2026-10-01、vendor patch=2026-02-01。
- metadata 解密成功，data 经解密映射设备以 F2FS 挂载。
- 用户仅在设备输入密码，日志确认 `User 0 Decrypted Successfully!`，
  `twrp.user.0.decrypt=1`、`twrp.all.users.decrypted=true`，`/data/media/0` 可访问。
- 随后同一镜像写入 recovery_b，A/B 整分区哈希均一致；写 B 槽时未切槽或重启，不能据此声称 B 槽启动通过。
- 用户确认密码解密后主界面、显示和触控正常。#8 曾报告页面后约 10±3 秒才有触控；#9 未做新的页面到首次触控计时，不声称迟就绪已修复。
- 新镜像的 boot control 只读查询成功：当前槽 0，A 槽可启动；未执行切槽或 GPT 写入测试。

MTP 文件传输、ROM 安装后的自动重装、fastbootd 切槽和重启系统仍未完成本轮验收。
以上结论对应 #9；A 槽启动已验证，B 槽仅写入及读回校验。

## 已知限制与待核实项

- 锁定上游的安装后自动重装只在无 `update-binary` 的成功 payload 安装分支调用；
  独立 A/B recovery 分支复制安装后的当前槽 recovery 到另一槽，未保存安装前的镜像，
  自动调用方也未检查重装返回值。因此该选项不能保证刷包后仍保留 YARP。
  本次采集仅保留 Fox 会话，未取得导致覆盖的 YARP 刷包日志，不能断言实际命中了哪条路径。
- 解密页可见不代表触控固件已就绪。#8 同次启动中触控 probe 约 4.21 秒完成，
  固件约 18.42 秒才被请求，18.61 秒更新完成。实装驱动的启动固件任务固定延后
  3500 jiffies，在 CONFIG_HZ=250 下为 14 秒；当前没有可调延迟参数。
  #9 的 probe 约 4.196 秒完成，固件在 18.420 秒请求、18.611 秒更新成功，固定延迟仍在。
  early-fs 约 3.87 秒才执行，与 probe 开始只差约 0.32 秒，因此不引入额外早加载。
  上游已有输入热插拔支持，不加等待或重扫补丁，也不修改驱动或其他分区。
  解密页首帧、首个有效触控事件与 UI 响应的统一时间戳仍缺失，不能把 14 秒等同于页面等待时长。
- GPT 维护修复已通过宿主/CI 合成 I/O、ASan/UBSan、Android 编译及 A 槽启动后的只读 boot control 查询；
  不声称真实切槽、UFS BSG 或断电恢复已验证。
- 继承的 Qualcomm boot control 按 by-name 下 `boot*` 名称计数，会将 Recovery 创建的
  `boot -> boot_a` 别名和 `boot_a/boot_b` 一起计为 3。只读检查已确认是别名重复计数，
  不代表第三个物理槽；本轮未修改该上游逻辑，也未执行切槽。

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
