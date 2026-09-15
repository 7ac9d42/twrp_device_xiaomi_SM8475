#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply only patches against their pinned project commits; never reset sources."""
import argparse
import json
import subprocess
from pathlib import Path

TREE = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
pending = []
for meta in sorted((TREE / "patches").glob("*.json")):
    spec = json.loads(meta.read_text())
    project = args.root.resolve() / spec["project"]
    patch = meta.with_name(spec["patch"])
    head = subprocess.check_output(["git", "-C", str(project), "rev-parse", "HEAD"], text=True).strip()
    if head != spec["base_commit"]:
        raise SystemExit(f"Commit mismatch: {spec['project']}: {head}")
    command = ["git", "-C", str(project), "apply"]
    if subprocess.run(command + ["--reverse", "--check", str(patch)], capture_output=True).returncode == 0:
        print(f"Already applied: {meta.stem}")
        continue
    subprocess.run(command + ["--check", str(patch)], check=True)
    pending.append((command, patch))
if not args.check:
    for command, patch in pending:
        subprocess.run(command + [str(patch)], check=True)
        print(f"Applied: {patch.stem}")
print(f"{len(pending)} patches {'ready' if args.check else 'applied'}")
