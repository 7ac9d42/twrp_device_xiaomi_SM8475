# 许可证与分发范围

本仓库使用逐文件授权。

| 范围 | 许可证/处理方式 |
| --- | --- |
| 原创 Python、Shell 工具及文档 | MIT；保留版权与许可文本 |
| 带 Apache 头或 SPDX 的设备配置、bootctrl 服务和 Android.bp | Apache-2.0；保留原版权头 |
| gpt-utils 与 init.recovery.usb.rc | 原 Linux Foundation BSD 三条款，完整原文保留 |
| patches/module-order.patch | GPL-3.0-or-later，继承 TWRP NOTICE |
| 其他 AOSP 源码补丁及对应元数据 | Apache-2.0，修改目标和基线在每个 JSON 中记录 |
| tools/erofs_read.c | GPL-2.0-or-later；不改写已声明许可证 |
| integration/manifest.lock.xml | 生成的依赖版本事实清单；本项目整理为 MIT，不改变所列项目许可 |
| proprietary-files.json | 原创文件清单和校验数据；不授予对应二进制许可 |
| security/miui_releasekey.x509.pem | 公共验证证书数据，不含私钥，不授予厂商软件许可 |

[LICENSE](../LICENSE) 的 MIT 适用于本项目的原创部分；继承代码继续使用各自许可证。
完整许可文本位于 [LICENSES](../LICENSES)，各文件保留原版权声明。
