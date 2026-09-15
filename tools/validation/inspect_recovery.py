#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect a built recovery without mounting or modifying any image."""
import argparse, gzip, hashlib, json, pathlib, stat, struct, subprocess, shutil
ap=argparse.ArgumentParser()
ap.add_argument("image",type=pathlib.Path)
ap.add_argument("--out",type=pathlib.Path,default=pathlib.Path("artifacts/image-check"))
a=ap.parse_args()
raw=a.image.read_bytes()
assert len(raw)<=104857600, "Recovery exceeds partition capacity"
assert raw[:8]==b"ANDROID!", "Not an Android boot image"
kernel,ramdisk,osversion,header_size=struct.unpack_from("<IIII",raw,8)
version=struct.unpack_from("<I",raw,40)[0]
assert version==4 and kernel==0, (version,kernel)
assert header_size==1584, header_size
compressed=raw[4096:4096+ramdisk]
assert len(compressed)==ramdisk and ramdisk>0
if compressed[:2]==b"\x1f\x8b": data=gzip.decompress(compressed); compression="gzip"
elif compressed[:6] in (b"070701",b"070702"): data=compressed; compression="none"
else:
 data=subprocess.run(["lz4","-dc"],input=compressed,stdout=subprocess.PIPE,check=True).stdout
 compression="lz4"
a.out.mkdir(parents=True,exist_ok=True)
extracted=a.out/"root"
if extracted.exists():
 assert not extracted.is_symlink() and extracted.resolve().parent==a.out.resolve()
 shutil.rmtree(extracted)
files={};entries=[];off=0;trailer=False
while off+110<=len(data):
 assert data[off:off+6] in (b"070701",b"070702"), ("Invalid cpio",off)
 size=int(data[off+54:off+62],16); ns=int(data[off+94:off+102],16); mode=int(data[off+14:off+22],16)
 assert ns>0
 name=data[off+110:off+110+ns-1].decode()
 start=(off+110+ns+3)&~3
 payload=data[start:start+size];assert len(payload)==size
 off=(start+size+3)&~3
 if name=="TRAILER!!!": trailer=True;break
 path=pathlib.PurePosixPath(name)
 assert not path.is_absolute() and ".." not in path.parts,name
 name=str(path)
 entry={"name":name,"mode":oct(mode),"size":size}
 if stat.S_ISREG(mode):
  files[name]=payload;entry["sha256"]=hashlib.sha256(payload).hexdigest()
  # Extract only ELF and configuration for linkage and content checks.
  if payload[:4]==b"\x7fELF" or name.endswith((".rc",".prop",".xml",".fstab")) or "fstab" in name or "ld.config" in name or name in ("prop.default","default.prop"):
   dest=a.out/"root"/name;dest.parent.mkdir(parents=True,exist_ok=True)
   assert not dest.is_symlink(),str(dest)
   dest.write_bytes(payload)
 elif stat.S_ISLNK(mode):entry["link"]=payload.decode()
 entries.append(entry)
assert trailer,"Missing cpio trailer"
required=[
 "system/bin/recovery","system/bin/keystore2","system/bin/fastbootd",
 "vendor/bin/qseecomd","vendor/bin/hw/android.hardware.keymaster@4.1-service-qti",
 "vendor/bin/hw/android.hardware.security.keymint-service-qti",
 "vendor/bin/hw/android.hardware.gatekeeper@1.0-service-qti",
 "system/bin/hw/boot-service.liuqin",
 "vendor/etc/vintf/manifest.xml",
 "vendor/etc/ld.config.liuqin.txt",
 "system/lib64/hw/bootctrl.taro.so",
 "twres/languages/zh_CN.xml",
]
missing=[s for s in required if s not in files]
fstabs={k:v.decode(errors="replace") for k,v in files.items() if "fstab" in k}
fstab_text="\n".join(fstabs.values())
encryption={s:s in fstab_text for s in [
 "fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0",
 "keydirectory=/metadata/vold/metadata_encryption",
 "metadata_encryption=aes-256-xts:wrappedkey_v0"]}
report={"image":str(a.image.resolve()),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
 "header_version":version,"kernel_bytes":kernel,"ramdisk_bytes":ramdisk,"compression":compression,
 "os_version_encoded":osversion,"entry_count":len(entries),"missing_required_files":missing,
 "encryption_flags":encryption,"fstabs":fstabs,"entries":entries,
 "device_runtime":"NOT TESTED"}
(a.out/"report.json").write_text(json.dumps(report,indent=2))
(a.out/"ramdisk-files.txt").write_text("\n".join(x["name"] for x in entries)+"\n")
print(json.dumps({k:v for k,v in report.items() if k not in ("entries","fstabs")},indent=2))
assert not missing,missing
assert all(encryption.values()),encryption
