# 上游来源与致谢

| 项目 | 固定来源 | 本项目使用方式 |
| --- | --- | --- |
| TWRP-Test manifest | 814b553116ceedde197f70389cff9661d81d8337，twrp-16.0 | 完整官方 minimal 快照，396 个官方项目加 2 个设备必需项目 |
| TWRP-Test Recovery / YARP | a93a12ec107265ab9c3c7fe3e4f96c8740a01337 | GUI2、FBE、metadata、keystore 数据保护；模块卸载后通知顺序已由上游实现 |
| TWRP-Test LVGL | 992dd52fc5112b24845078ea60c1cf1e2e27c5b5 | GUI2 界面运行库 |
| TWRP-Test libvpx | f42506c3faf4592a9d8929c9ca832fd72fff94a0 | GUI2 录屏 VP8 编码 |
| TWRP-Test libwebm | 99fcd14602ba76998d086b602f29a243e1d5c835 | GUI2 录屏 WebM 封装 |
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

`integration/manifest.lock.xml` 按官方 `default.xml` → `twrp-default.xml` → `remove-minimal.xml` 展开；全部项目固定到提交 SHA。官方 minimal 的目录完整保留，另保留 `hardware/qcom-caf/bootctrl` 和 `frameworks/libs/native_bridge_support`。ERoFS 与 VNDK 31 仍在官方项目集中；VNDK 兼容库不使用 SDK stub。

此次随分支更新的其他提交为 build/make `1ff6b0ae732a31412d94882aaa89d030f0a6be17`、system/vold `e7e26ed2ffd9ad0469a05515cfd91940a3366d19`、vendor/twrp `4c5070577457a8dbb87f71ed53925cb56b397234`。cgroup-runtime、crash-dump、native-accessor、platform-release 四个补丁的锁定项目基线未变，已对精确上游文件执行应用检查；保留真实 recovery 运行库。

Recovery 的 `LoadVendorModules()` 已在发布 `twrp.modules.loaded` 前显式卸载本函数挂载的分区、禁用 scope guard 并恢复可选设备运行资源，因此删除旧 module-order 补丁。GUI2 的中文目录编译在 `libgui2.so` 中；`gui2/resources/Android.bp` 的 `gui2_fonts` 使用根目录 `prebuilt_res`，安装到 `/res/fonts/`。镜像验证改查 GUI2/LVGL/codec 运行库、中文目录和三个 TTF 字体，替代旧 `/twres/languages/zh_CN.xml` 断言；现有触控固件哈希、ELF、fstab、VINTF、init、AVB 与安全服务顺序检查继续保留。

以上完成静态核对；完整编译、产物验证及设备运行验证由后续 CI 和实机测试确认。

## 测试包致谢

感谢 **酷安 @做梦书** 制作 OS4.0.0.133.XMYCNXM 2in1-Root 完整包。
该包已在 liuqin 上完成刷入与启动测试。
