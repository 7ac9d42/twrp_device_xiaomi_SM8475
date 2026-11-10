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
- 固定最新 YARP 官方依赖及 LVGL/GUI2 资源，使用上游已修复的模块加载通知顺序。
- 提供标准 Ubuntu 24.04 hosted runner 的手动 CI，限制并发和内存目标，检查磁盘余量并设置阶段超时。
- 从已测镜像按完整 SHA-256 恢复厂商载荷，保留原始固件提取方式。
- 同步默认 8 并发，编译默认 4 并发；保留 6 GiB Soong Go 内存目标和约 8 GiB swap。
- 启用跨运行 ccache，上限 5 GiB，缓存位于沙箱可写的 `out/ccache`；不整体缓存源码或构建输出。
- 同步和编译日志实时显示，提供 30 秒资源心跳、阶段计时和 Actions 性能汇总。
- 添加镜像格式、依赖库、服务配置、GUI2 字体、VINTF 与 AVB 哈希检查。
