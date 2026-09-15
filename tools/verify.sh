#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -eo pipefail
tree=$(cd "$(dirname "$0")/.." && pwd)
cd "$tree/../../.."
mkdir -p logs artifacts
cp "$tree/integration/touch-firmware.json" artifacts/touch-firmware.json
image="out/target/product/liuqin/recovery.img"
python "$tree/tools/validation/inspect_recovery.py" "$image" > logs/image-inspection.log
python "$tree/tools/validation/check_vendor_elf.py" --vendor-root artifacts/image-check/root/vendor \
  --system-lib artifacts/image-check/root/system/lib64 --system-root artifacts/image-check/root/system \
  --report artifacts/image-elf-check.json > logs/image-elf-check.log
python "$tree/tools/validation/verify_image_config.py" > logs/image-configuration-check.log
python "$tree/tools/validation/check_recovery_startup.py" > logs/image-startup-check.log
out/host/linux-x86/bin/host_init_verifier --out_system=artifacts/image-check/root/system \
  --out_vendor=artifacts/image-check/root/vendor > logs/image-init-check.log 2>&1
for rc in artifacts/image-check/root/init.recovery.qcom.rc artifacts/image-check/root/init.recovery.usb.rc; do
  out/host/linux-x86/bin/host_init_verifier "$rc" >> logs/image-init-check.log 2>&1
done
out/host/linux-x86/bin/assemble_vintf -i artifacts/image-check/root/vendor/etc/vintf/manifest.xml \
  -o artifacts/vintf-schema-check.xml > logs/image-vintf-check.log 2>&1
out/host/linux-x86/bin/assemble_vintf -i artifacts/image-check/root/system/etc/vintf/manifest.xml:artifacts/image-check/root/system/etc/vintf/manifest/liuqin.xml \
  -o artifacts/recovery-vintf-schema-check.xml >> logs/image-vintf-check.log 2>&1
out/host/linux-x86/bin/avbtool info_image --image "$image" > logs/image-avb-info.log
out/host/linux-x86/bin/avbtool verify_image --image "$image" > logs/image-avb-check.log
echo "Header, ramdisk, ELF, overlay, properties, init, VINTF and AVB hash checks passed."
