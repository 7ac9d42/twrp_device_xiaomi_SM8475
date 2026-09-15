# TWRP device tree — Xiaomi SM8475 / liuqin

**仅在小米平板 6 Pro（liuqin）测试通过。仓库名称包含 SM8475，不代表其他同 SoC 设备受支持。**
没有测试其他手机或下文未列出的固件；不建议将 liuqin 镜像用于其他设备。

面向 HyperOS 4 / Android 17 的 TWRP 设备适配，基于
[TWRP-Test 的 twrp-16.0 分支](https://github.com/TWRP-Test/platform_manifest_twrp_aosp/tree/twrp-16.0)。
Android 17 兼容与解密主体来自该上游；本项目提供 liuqin 硬件配置、服务集成和有日志依据的修复。

## 已验证范围

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
