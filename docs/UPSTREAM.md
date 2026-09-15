# 上游来源与致谢

| 项目 | 固定来源 | 本项目使用方式 |
| --- | --- | --- |
| TWRP-Test manifest | 6f074703a0ab31f22518b1a94331b358190237ba，twrp-16.0 | AOSP16 / Android17 兼容基线 |
| TWRP-Test Recovery | 580a0e89cb27007f4584cbb9649ba2607bb21d6a | 界面、FBE、metadata、keystore 数据保护；只附模块通知顺序补丁 |
| ymdzq/device_xiaomi_liuqin-TWRP | eb6333b9d77ad0171adcf0d8b9d0cd25fc49a68b | 硬件信息索引、bootctrl/gpt-utils、带原版权头的 USB 配置 |
| LineageOS/android_hardware_qcom_bootctrl | 581fb573e1e26168f7fd56f5ad84ce75d92fe623 | Qualcomm boot control HAL |
| AOSP native_bridge_support | b527289974e3883460370012325ab3736d59268a | crash_dump 的真实寄存器访问器 |
| AOSP VNDK 31 | 1a059a5a203352d3e0c2fd3ccff5719cc37fc340 | 兼容库只在本地使用，精确清单记录哈希 |
| AOSP / EROFS | integration/manifest.lock.xml 中固定版本 | 工具链、系统服务与只读固件解析 |
| Xiaomi / Qualcomm | OS4.0.0.129.XMYCNXM 本地固件 | 核对硬件事实、本地提取必需 HAL 与触控固件 |

链接：

- https://github.com/TWRP-Test/platform_manifest_twrp_aosp
- https://github.com/TWRP-Test/android_bootable_recovery
- https://github.com/ymdzq/device_xiaomi_liuqin-TWRP
- https://github.com/LineageOS/android_hardware_qcom_bootctrl
- https://android.googlesource.com/platform/frameworks/libs/native_bridge_support
- https://android.googlesource.com/platform/external/erofs-utils

ymdzq 的 README 也向 Redmi K60 OrangeFox 与 skkk 小米 12S 设备树致谢。
Android 17 解密实现来自 TWRP-Test 上游，本项目提供 liuqin 的设备适配。

## 测试包致谢

感谢 **酷安 @做梦书** 制作 OS4.0.0.133.XMYCNXM 2in1-Root 完整包。
该包已在 liuqin 上完成刷入与启动测试。
