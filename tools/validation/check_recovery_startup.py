#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check pinned vendor paths and security-service readiness in the recovery image."""
from pathlib import Path
import argparse, json, xml.etree.ElementTree as ET
ap=argparse.ArgumentParser()
ap.add_argument("--root",type=Path,default=Path("artifacts/image-check/root"))
ap.add_argument("--report",type=Path,default=Path("artifacts/startup-check.json"))
args=ap.parse_args(); root=args.root; errors=[]
def require(ok,message):
    if not ok: errors.append(message)
def read(name):
    p=root/name
    return p.read_text() if p.is_file() else ""
def start_actions(text,service):
    actions=[]; trigger=""
    for line in text.splitlines():
        line=line.split("#",1)[0].rstrip()
        if not line.strip(): continue
        if not line[0].isspace():
            trigger=line if line.startswith("on ") else ""
        if line.split()==["start",service]: actions.append(trigger)
    return actions
def service_blocks(text):
    blocks=[]; options=None
    for line in text.splitlines():
        line=line.split("#",1)[0].rstrip()
        if not line.strip(): continue
        if not line[0].isspace():
            fields=line.split()
            options=[] if len(fields)>=3 and fields[0]=="service" else None
            if options is not None: blocks.append((fields,options))
        elif options is not None: options.append(line.split())
    return blocks
def declarations(paths):
    result=set()
    for p in paths:
        if not p.is_file():continue
        tree=ET.parse(p).getroot()
        for hal in tree.findall("hal"):
            for fq in hal.findall("fqname"):
                result.add((hal.findtext("name"),fq.text))
    return result
system_manifests=[root/"system/etc/vintf/manifest.xml",*sorted((root/"system/etc/vintf/manifest").glob("*.xml"))]
visible=declarations(system_manifests)
require(("android.hidl.manager","@1.2::IServiceManager/default") in visible,"System VINTF must declare HIDL IServiceManager 1.2")
vendor=declarations([root/"vendor/etc/vintf/manifest.xml"])
for item in vendor:
    require(item in visible,"Recovery system VINTF is missing "+str(item))
for item in [("android.hardware.security.keymint","IKeyMintDevice/default"),
             ("android.hardware.security.sharedsecret","ISharedSecret/default"),
             ("android.hardware.security.secureclock","ISecureClock/default")]:
    require(item in visible,"Required AIDL HAL missing: "+str(item))
fstab=read("system/etc/recovery.fstab")
misc=[line.split() for line in fstab.splitlines() if not line.startswith("#") and " /misc " in line]
require(len(misc)==1 and misc[0]==["/dev/block/by-name/misc","/misc","emmc","defaults","defaults"],
        "Default recovery fstab must resolve real misc for boot control")
qcom=read("init.recovery.qcom.rc")
require("on early-init" in qcom and "mount none /vendor /twrp_vendor bind" in qcom,
        "Ramdisk vendor must be pinned before real vendor mounts")
require("mount none none /twrp_vendor private" in qcom,"Pinned vendor must have private mount propagation")
security_services=["vendor.qseecomd","vendor.keymaster-4-1","vendor.keymint-qti","gatekeeper-1-0"]
for service in security_services:
    actions=start_actions(qcom,service)
    require(len(actions)==1 and "property:twrp.storage.ready=1" in actions[0].split(),
            service+": must start only after upstream runtime property overrides")
rcs=list((root/"vendor/etc/init").glob("*.rc"))+[root/"system/etc/init/android.hardware.health@2.1-service.rc"]
services=[]
for p in rcs:
    text=p.read_text()
    for fields,options in service_blocks(text):
        name,exe=fields[1:3]; services.append(name)
        if name in security_services:
            require(["disabled"] in options,name+": class startup must not bypass runtime property readiness")
        require(exe.startswith("/twrp_vendor/bin/"),name+": executable not pinned")
        if exe.startswith("/twrp_vendor/"):
            actual=root/"vendor"/exe.removeprefix("/twrp_vendor/")
            require(actual.is_file(),name+": missing pinned executable")
        require(["setenv","LD_CONFIG_FILE","/twrp_vendor/etc/ld.config.liuqin.txt"] in options,name+": linker config not pinned")
        require(["setenv","LD_LIBRARY_PATH","/twrp_vendor/lib64:/twrp_vendor/lib64/hw"] in options,name+": library path not pinned")
for service in security_services:
    require(service in services,service+": service definition missing")
cfg=read("vendor/etc/ld.config.liuqin.txt")
require("dir.vendor = /twrp_vendor/bin" in cfg,"Linker section must select pinned executables")
require("namespace.default.search.paths = /twrp_vendor/${LIB}:/twrp_vendor/${LIB}/hw" in cfg,"Vendor namespace search paths are not pinned")
require("namespace.default.permitted.paths = /twrp_vendor/${LIB}" in cfg,"Vendor namespace permitted path is not pinned")
require((root/"vendor/lib64/libbase.so").is_file(),"Pinned vendor libbase.so absent")
ks=read("system/etc/init/keystore2.rc")
require("on late-init" not in ks,"keystore2 must not start unconditionally before security HALs")
ks_actions=start_actions(ks,"keystore2")
require(len(ks_actions)==1,"keystore2 must have a single readiness-gated start action")
for prop in ["hwservicemanager.ready=true","vendor.sys.listeners.registered=true","twrp.modules.loaded=true","twrp.storage.ready=1"]:
    require(len(ks_actions)==1 and "property:"+prop in ks_actions[0].split(),"keystore2 readiness gate missing: "+prop)
ks_services=[options for fields,options in service_blocks(ks) if fields[1]=="keystore2"]
require(len(ks_services)==1 and ["disabled"] in ks_services[0],"keystore2 class startup must not bypass readiness gates")
require("/system/bin/keystore2 /tmp/misc/keystore" in ks,"keystore2 must keep temporary DB")
require("critical window=0" in ks,"Critical service failure detection must remain enabled")
result={"errors":errors,"recovery_visible_hals":sorted(visible),"pinned_services":services,
        "runtime_validation":"NOT PERFORMED"}
args.report.parent.mkdir(parents=True,exist_ok=True)
args.report.write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
raise SystemExit(bool(errors))
