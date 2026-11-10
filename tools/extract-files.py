#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract the exact liuqin inventory without expanding super or copying full partitions."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

# Isolated mode (-I) omits the script directory from the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from recovery_image import extract_cpio, read_ramdisk, relative_name

TREE = Path(__file__).resolve().parent.parent
RECOVERY_SHA256 = "833b8ed065ce25dca4ab1faea8bbbd8c3077e90a3dde60aa0a10fea9a4f6ffbe"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def inventory(spec):
    targets = set()
    for item in spec["files"]:
        name = item["destination"]
        if relative_name(name) != name or not name.startswith("recovery/root/"):
            raise ValueError(f"Invalid payload destination: {name!r}")
        destination = TREE / name
        if not destination.resolve().is_relative_to(TREE.resolve()):
            raise ValueError("Destination escapes device tree")
        for path in (destination, *destination.parents):
            if path == TREE:
                break
            if path.is_symlink():
                raise ValueError(f"Symlink payload destination: {path}")
        key = name.casefold()
        if key in targets:
            raise ValueError(f"Duplicate payload destination: {name}")
        targets.add(key)
        if item["kind"] not in ("vendor", "source-tree"):
            raise ValueError(f"Unknown payload kind: {item['kind']}")
        source_name = item["path"]
        if item["kind"] == "vendor":
            if not source_name.startswith("/"):
                raise ValueError("Vendor source path must be absolute")
            source_name = source_name[1:]
        if relative_name(source_name) != source_name or source_name == ".":
            raise ValueError(f"Invalid payload source: {item['path']!r}")
        if "llndk-stub" in Path(source_name).parts:
            raise ValueError("SDK stubs cannot be installed")
        if (type(item["bytes"]) is not int or item["bytes"] < 0
                or len(item["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in item["sha256"])):
            raise ValueError(f"Invalid payload size or SHA256: {name}")
    for name in targets:
        if any(str(parent) in targets for parent in PurePosixPath(name).parents):
            raise ValueError(f"Overlapping payload destination: {name}")
    return spec["files"]


def matches(data, item):
    return len(data) == item["bytes"] and digest(data) == item["sha256"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=TREE, help="TWRP source root (default: device tree)")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--super", type=Path, help="Matching raw super.img; sparse images are rejected")
    sources.add_argument("--recovery", type=Path, help="Pinned, tested recovery.img containing all payloads")
    parser.add_argument("--reader", type=Path, help="erofs_read binary")
    parser.add_argument("--check", action="store_true", help="Validate existing payloads without changes")
    args = parser.parse_args()
    spec = json.loads((TREE / "proprietary-files.json").read_text())
    items = inventory(spec)
    recovered = None
    if args.recovery:
        recovered = extract_cpio(read_ramdisk(args.recovery, RECOVERY_SHA256),
                                 [i["destination"][len("recovery/root/"):] for i in items])
        for item in items:
            if not matches(recovered[item["destination"][len("recovery/root/"):]], item):
                raise ValueError(f"Recovery payload hash/size mismatch: {item['destination']}")
    missing = []
    for item in items:
        destination = TREE / item["destination"]
        if destination.is_file() and matches(destination.read_bytes(), item):
            continue
        missing.append(item)
    if args.check:
        if missing:
            raise SystemExit("Missing or mismatched: " + ", ".join(i["destination"] for i in missing))
        print(f"{len(items)} payload hashes and sizes verified")
        return
    vendor_needed = recovered is None and any(i["kind"] == "vendor" for i in missing)
    if vendor_needed:
        if not args.super or not args.reader:
            raise SystemExit("--recovery or both --super and --reader are required for missing vendor payloads")
        if args.super.stat().st_size != spec["super_bytes"]:
            raise SystemExit("Expected the documented raw super.img size")
        with args.super.open("rb") as image:
            if image.read(4) == bytes.fromhex("3aff26ed"):
                raise SystemExit("Sparse super.img is unsupported; do not silently use raw offsets")
    staged = []
    for item in missing:
        destination = TREE / item["destination"]
        if recovered is not None:
            data = recovered[item["destination"][len("recovery/root/"):]]
        elif item["kind"] == "source-tree":
            source = (args.root.resolve() / item["path"]).resolve()
            if not source.is_relative_to(args.root.resolve()):
                raise ValueError("Source escapes TWRP root")
            data = source.read_bytes()
        else:
            data = subprocess.check_output([str(args.reader.resolve()), str(args.super.resolve()),
                    str(spec["vendor_offset"]), "cat", item["path"]], timeout=120)
        if not matches(data, item):
            raise ValueError(f"Source hash/size mismatch: {item['destination']}")
        staged.append((destination, data, item["destination"].startswith("recovery/root/vendor/bin/")))
    # Validate the entire extraction before staging or replacing any payload.
    temporary_files = []
    try:
        for destination, data, executable in staged:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".extract-", delete=False) as stream:
                temporary = Path(stream.name)
                temporary_files.append((temporary, destination))
                stream.write(data)
            temporary.chmod(0o755 if executable else 0o644)
        for temporary, destination in temporary_files:
            os.replace(temporary, destination)
    finally:
        for temporary, _ in temporary_files:
            temporary.unlink(missing_ok=True)
    print(f"Extracted {len(staged)} files; all {len(items)} hashes and sizes verified")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc)) from exc
