# 改动说明

## 设备适配

- 配置 liuqin 的显示、触控、亮度、USB、A/B 和动态分区。
- 生成 header v4、无内核的独立 Recovery 镜像。
- 集成 Qualcomm Keymaster、KeyMint、Gatekeeper、QSEE 和 boot control 服务。
- 配置 FBE v2、wrapped key 与 metadata 加密，启用 vendor.gatekeeper.disable_spu。
- 保留中文界面、ADB、MTP、fastbootd 和日志功能。

## 功能修复

- 在临时厂商分区卸载后通知 init 启动相关服务。
- 为 boot control 添加 /misc 分区配置。
- 补全两种触控面板的固件提取清单。
- 按目标固件设置 RPMB 节点的所有者和访问权限。
- 配置 DSP 固件搜索路径、只读挂载标签与电池服务启动顺序。
- 使用 libvndksupport 和 libcgrouprc 的真实运行库，配置厂商链接命名空间。

## 构建与工具

- 添加 Android 17 版本构建配置。
- 集成 crash_dump64 原生崩溃日志工具。
- 固定源码依赖版本，提供按需同步与厂商文件提取工具。
- 启用 ccache 和增量构建。
- 添加镜像格式、依赖库、服务配置、VINTF 与 AVB 哈希检查。
