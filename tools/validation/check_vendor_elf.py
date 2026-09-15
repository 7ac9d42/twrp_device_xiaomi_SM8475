#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check vendor ELF dependencies and versioned symbols with the shipped namespaces."""
import argparse,pathlib,subprocess,re,json
ap=argparse.ArgumentParser()
ap.add_argument("--vendor-root",type=pathlib.Path)
ap.add_argument("--system-lib",type=pathlib.Path,required=True)
ap.add_argument("--system-root",type=pathlib.Path,help="Also check all packaged system ELF files")
ap.add_argument("--report",type=pathlib.Path,default=pathlib.Path("artifacts/vendor-elf-check.json"))
a=ap.parse_args()
root=pathlib.Path(__file__).resolve().parents[5]
vendor=a.vendor_root.resolve() if a.vendor_root else root/"device/xiaomi/liuqin/recovery/root/vendor"
system=a.system_lib.resolve()
vendor_paths=[vendor/"lib64",vendor/"lib64/hw"]
llndk={"libc.so","libm.so","libdl.so","liblog.so","libbinder_ndk.so","libvndksupport.so","libcgrouprc.so"}
cache={}
def label(p):
 try:return str(p.relative_to(root))
 except ValueError:return str(p)
def elf(p):
 if p in cache:return cache[p]
 h=subprocess.check_output(["readelf","-h",str(p)],text=True)
 if "AArch64" not in h:raise ValueError("Not AArch64: "+str(p))
 symbols_all=subprocess.check_output(["readelf","-Ws",str(p)],text=True)
 if re.search(r"\b(?:stub|stub\.c)\b",symbols_all):raise ValueError("SDK stub must not be installed: "+str(p))
 dyn=subprocess.check_output(["readelf","-d",str(p)],text=True)
 deps=re.findall(r"\(NEEDED\).*?\[(.*?)\]",dyn)
 defined=set();undefined=set()
 for line in subprocess.check_output(["readelf","--dyn-syms","--wide",str(p)],text=True).splitlines():
  cols=re.sub(r"<OS specific>:\s*10", "IFUNC", line).split()
  if len(cols)<8 or not cols[0].rstrip(":").isdigit():continue
  name=cols[7].replace("@@","@")
  if cols[6]=="UND":
   if cols[4]!="WEAK":undefined.add(name)
  else:
   defined.add(name)
   if "@@" in cols[7] or "@" not in name:defined.add(name.split("@")[0])
 cache[p]=(deps,defined,undefined)
 return cache[p]
linker=system.parent/"bin/linker64"
loader_exports=elf(linker)[1] if linker.is_file() else set()
result={}
seeds=[(p,"vendor") for p in sorted(list((vendor/"bin").rglob("*"))+list((vendor/"lib64").rglob("*.so")))]
if a.system_root:
 seeds += [(p,"system") for p in sorted(a.system_root.resolve().rglob("*")) if p.is_file()]
for seed,initial_namespace in seeds:
 if not seed.is_file() or seed.read_bytes()[:4]!=b"\x7fELF":continue
 pending=[(seed,initial_namespace)];seen=set();missing=set()
 definitions={"vendor":set(),"system":set()};undefined={}
 linked_exports=set()
 while pending:
  item,namespace=pending.pop()
  if (item,namespace) in seen:continue
  seen.add((item,namespace))
  deps,defined,undef=elf(item)
  definitions[namespace]|=defined
  undefined[(item,namespace)]=undef
  if namespace=="system" and item.name in llndk:linked_exports|=defined
  for name in deps:
   target=None;next_ns=namespace
   if namespace=="vendor":
    target=next((d/name for d in vendor_paths if (d/name).is_file()),None)
    if target is None and name in llndk:
     target=system/name;next_ns="system"
   else:target=system/name
   if target is None or not target.is_file():missing.add(namespace+":"+name)
   else:pending.append((target,next_ns))
 scopes={"vendor":definitions["vendor"]|linked_exports|loader_exports,"system":definitions["system"]|loader_exports}
 unresolved={label(p)+" ["+ns+"]":sorted(names-scopes[ns]) for (p,ns),names in undefined.items() if names-scopes[ns]}
 result[label(seed)]={"libraries":len(seen),"missing_libraries":sorted(missing),
 "unresolved_symbols":unresolved,
 "resolved_libraries":[{"path":label(p),"namespace":ns} for p,ns in sorted(seen)]}
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(result,indent=2))
failures=0
for k,v in result.items():
 if v["missing_libraries"] or v["unresolved_symbols"]:
  failures+=1
  print(pathlib.Path(k).name,"missing",v["missing_libraries"],"unresolved symbols",sum(len(s) for s in v["unresolved_symbols"].values()))
print("Checked",len(result),"ELF roots; failures",failures)
raise SystemExit(bool(failures))
