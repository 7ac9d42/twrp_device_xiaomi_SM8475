#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract the exact liuqin inventory without expanding super or copying full partitions."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

TREE = Path(__file__).resolve().parent.parent

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="TWRP source root")
    parser.add_argument("--super", type=Path, help="Matching raw super.img; sparse images are rejected")
    parser.add_argument("--reader", type=Path, help="erofs_read binary")
    parser.add_argument("--check", action="store_true", help="Validate existing payloads without changes")
    args = parser.parse_args()
    spec = json.loads((TREE / "proprietary-files.json").read_text())
    missing = []
    for item in spec["files"]:
        destination = TREE / item["destination"]
        if destination.is_file() and digest(destination.read_bytes()) == item["sha256"]:
            continue
        missing.append(item)
    if args.check:
        if missing:
            raise SystemExit("Missing or mismatched: " + ", ".join(i["destination"] for i in missing))
        print(f"{len(spec['files'])} payload hashes verified")
        return
    vendor_needed = any(i["kind"] == "vendor" for i in missing)
    if vendor_needed:
        if not args.super or not args.reader:
            raise SystemExit("--super and --reader are required for missing vendor payloads")
        if args.super.stat().st_size != spec["super_bytes"]:
            raise SystemExit("Expected the documented raw super.img size")
        with args.super.open("rb") as image:
            if image.read(4) == bytes.fromhex("3aff26ed"):
                raise SystemExit("Sparse super.img is unsupported; do not silently use raw offsets")
    staged = []
    for item in missing:
        destination = TREE / item["destination"]
        if not destination.resolve().is_relative_to(TREE.resolve()):
            raise SystemExit("Destination escapes device tree")
        if item["kind"] == "source-tree":
            source = args.root.resolve() / item["path"]
            if "llndk-stub" in source.parts:
                raise SystemExit("SDK stubs cannot be installed")
            data = source.read_bytes()
        else:
            data = subprocess.check_output([str(args.reader.resolve()), str(args.super.resolve()),
                    str(spec["vendor_offset"]), "cat", item["path"]])
        if len(data) != item["bytes"] or digest(data) != item["sha256"]:
            raise SystemExit(f"Source hash mismatch: {item['destination']}")
        staged.append((destination, data))
    # Validate the entire extraction before replacing any payload.
    for destination, data in staged:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".extracting")
        temporary.write_bytes(data)
        temporary.chmod(0o755 if "/vendor/bin/" in str(destination) else 0o644)
        os.replace(temporary, destination)
    print(f"Extracted {len(staged)} files; all {len(spec['files'])} hashes verified")

if __name__ == "__main__":
    main()
