#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit final ramdisk contents against the device overlay and firmware facts."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
r=Path(__file__).resolve().parents[5]
check=r/"artifacts/image-check"
report=json.loads((check/"report.json").read_text())
entries={x["name"]:x for x in report["entries"]}
assert entries.get("twrp_vendor", {}).get("mode") == "0o40755", "Missing pinned vendor mount point"
overlay=r/"device/xiaomi/liuqin/recovery/root"
mismatches=[]
for p in overlay.rglob("*"):
 if not p.is_file():continue
 name=str(p.relative_to(overlay))
 actual=entries.get(name,{}).get("sha256")
 if actual!=hashlib.sha256(p.read_bytes()).hexdigest():mismatches.append(name)
assert not mismatches,("Overlay absent or stale",mismatches)
root=check/"root"
props=dict(line.split("=",1) for line in (root/"prop.default").read_text().splitlines() if "=" in line and not line.startswith("#"))
wanted={"ro.build.version.release":"17","ro.build.version.sdk":"36","ro.build.version.security_patch":"2026-08-01","ro.vendor.build.security_patch":"2026-02-01","ro.twrp.device.name":"liuqin","ro.board.platform":"taro","ro.virtual_ab.enabled":"true","ro.debuggable":"1","vendor.gatekeeper.disable_spu":"true"}
assert all(props.get(k)==v for k,v in wanted.items()),{k:props.get(k) for k in wanted}
manifest=ET.parse(root/"vendor/etc/vintf/manifest.xml").getroot()
hal_names={h.findtext("name") for h in manifest.findall("hal")}
required={"android.hardware.gatekeeper","android.hardware.keymaster","android.hardware.security.keymint","android.hardware.security.sharedsecret","android.hardware.security.secureclock","android.hardware.boot","android.hardware.health"}
assert required<=hal_names,required-hal_names
for name,command in {
 "system/etc/init/android.hardware.boot@1.2-service.rc":"/system/bin/hw/boot-service.liuqin",
 "system/etc/init/android.hardware.health@2.1-service.rc":"/twrp_vendor/bin/hw/android.hardware.health@2.1-service",
}.items():assert command in (root/name).read_text()
keystore=(root/"system/etc/init/keystore2.rc").read_text()
assert "/system/bin/keystore2 /tmp/misc/keystore" in keystore
recovery=(root/"system/bin/recovery").read_bytes()
assert b"/tmp/misc/keystore/persistent.sqlite" in recovery
assert b"/data/misc/keystore/persistent.sqlite" in recovery
assert b"LD_CONFIG_FILE" in (root/"system/bin/linker64").read_bytes()
touch=json.loads((r/"artifacts/touch-firmware.json").read_text())
for info in touch["files"].values():
 assert entries.get(info["ramdisk_path"],{}).get("sha256")==info["sha256"],"Touch firmware absent or modified: "+info["ramdisk_path"]
for name in ["system/bin/crash_dump64","system/lib64/libprocinfo.so","system/lib64/libcgrouprc.so","system/lib64/libvndksupport.so"]:
 assert name in entries,name
for name in ["vendor/lib64/libcgrouprc.so","vendor/lib64/libvndksupport.so"]:
 assert name not in entries,"Removed SDK stub still packaged: "+name
assert "/dev/0:0:0:49476 0600 system system" in (root/"vendor/etc/ueventd.rc").read_text()
rc=(root/"init.recovery.qcom.rc").read_text()
assert "context=u:object_r:rootfs:s0" in rc and "write /sys/module/firmware_class/parameters/path /firmware/image" in rc
# GUI2 embeds translations in libgui2 and installs fonts through gui2_fonts.
for name in ["system/lib64/libgui2.so","system/lib64/liblvgl_twrp.so","system/lib64/libvpx.so","system/lib64/libwebm_mkvmuxer.so",
             "res/fonts/wqy-microhei.ttf","res/fonts/DroidSansMono.ttf","res/fonts/RobotoCondensed-Regular.ttf"]:
 assert entries.get(name,{}).get("size",0)>0,"GUI2 runtime asset absent or empty: "+name
gui2=(root/"system/lib64/libgui2.so").read_bytes()
assert b"zh_CN" in gui2 and "简体中文".encode() in gui2,"GUI2 Chinese catalogue absent"
for name in ["system/bin/adbd","system/bin/fastbootd","system/lib64/libtwrpmtp-ffs.so","system/lib64/hw/bootctrl.taro.so"]:
 assert name in entries,name
out={"overlay_files_verified":sum(p.is_file() for p in overlay.rglob("*")),"firmware_properties":wanted,
 "declared_hals":sorted(hal_names),"keystore_tmpfs_protection":True,"debug_linker_config_supported":True,
 "chinese_adb_mtp_fastbootd_present":True,
 "gatekeeper_disable_spu":props["vendor.gatekeeper.disable_spu"],
 "runtime_validation":"NOT PERFORMED"}
(check/"configuration-check.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
