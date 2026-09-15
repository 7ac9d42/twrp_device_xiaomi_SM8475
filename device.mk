# SPDX-License-Identifier: MIT
DEVICE_PATH := device/xiaomi/liuqin
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/emulated_storage.mk)
$(call inherit-product, vendor/twrp/config/common.mk)
PRODUCT_USE_DYNAMIC_PARTITIONS := true
PRODUCT_SHIPPING_API_LEVEL := 31
PRODUCT_SOONG_NAMESPACES += $(DEVICE_PATH) hardware/qcom-caf/bootctrl
PRODUCT_PACKAGES += bootctrl.taro.recovery android.hardware.boot@1.2-impl-qti.recovery
PRODUCT_EXTRA_RECOVERY_KEYS += $(DEVICE_PATH)/security/miui_releasekey
PRODUCT_PROPERTY_OVERRIDES += ro.twrp.device.name=liuqin
$(call inherit-product-if-exists, $(DEVICE_PATH)/proprietary.mk)
BOARD_SHIPPING_API_LEVEL := 31
PRODUCT_PACKAGES += boot-service.liuqin
PRODUCT_BUILD_RECOVERY_IMAGE := true
# Recovery-only build; retain the real mi_ext layout without generating super images.
PRODUCT_BUILD_SUPER_PARTITION := false
PRODUCT_BUILD_SUPER_EMPTY_IMAGE := false
