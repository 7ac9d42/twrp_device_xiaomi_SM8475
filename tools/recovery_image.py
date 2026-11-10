#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read a kernel-less Android v4 recovery and selected newc ramdisk files."""
import gzip
import hashlib
import stat
import struct
import subprocess
from collections.abc import Iterable
from pathlib import Path, PurePosixPath


def relative_name(name):
    """Normalize a POSIX archive name without accepting host-specific paths."""
    if not isinstance(name, str) or not name or any(c in name for c in "\\:\x00"):
        raise ValueError(f"Invalid relative path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or any(ord(c) < 32 for c in name):
        raise ValueError(f"Invalid relative path: {name!r}")
    return str(path)


def read_ramdisk(image: Path, expected_sha256: str) -> bytes:
    """Verify the entire image and return decompressed cpio bytes.

    Requires lz4 on PATH for LZ4 ramdisks. Invalid images raise ValueError;
    file access and decompressor failures propagate without writing files.
    """
    with image.open("rb") as stream:
        raw = stream.read(104857601)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Recovery image SHA256 mismatch")
    if len(raw) < 4096 or len(raw) > 104857600 or raw[:8] != b"ANDROID!":
        raise ValueError("Invalid Android recovery image")
    kernel, ramdisk, _, header_size = struct.unpack_from("<IIII", raw, 8)
    version = struct.unpack_from("<I", raw, 40)[0]
    if version != 4 or kernel != 0 or header_size != 1584:
        raise ValueError("Expected a kernel-less Android boot v4 image")
    compressed = raw[4096:4096 + ramdisk]
    if not ramdisk or len(compressed) != ramdisk:
        raise ValueError("Truncated recovery ramdisk")
    if compressed.startswith(b"\x1f\x8b"):
        return gzip.decompress(compressed)
    if compressed[:6] in (b"070701", b"070702"):
        return compressed
    if compressed[:4] not in (b"\x02\x21\x4c\x18", b"\x04\x22\x4d\x18"):
        raise ValueError("Unsupported ramdisk compression")
    try:
        return subprocess.run(["lz4", "-dc"], input=compressed,
                              stdout=subprocess.PIPE, check=True, timeout=120).stdout
    except FileNotFoundError as exc:
        raise ValueError("LZ4 ramdisk requires an existing lz4 executable on PATH") from exc


def extract_cpio(data: bytes, wanted: Iterable[str]) -> dict[str, bytes]:
    """Return requested regular files as {canonical POSIX path: payload bytes}.

    Validate the entire newc archive without filesystem writes. Invalid entries,
    duplicate archive paths and missing requested files raise ValueError.
    """
    wanted = set(wanted)
    if any(relative_name(name) != name or name == "." for name in wanted):
        raise ValueError("Requested cpio paths must be canonical relative paths")
    files = {}
    seen = set()
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError(f"Invalid cpio header at {offset}")
        fields = [header[i:i + 8] for i in range(6, 110, 8)]
        if any(any(c not in b"0123456789abcdefABCDEF" for c in field) for field in fields):
            raise ValueError(f"Invalid cpio fields at {offset}")
        values = [int(field, 16) for field in fields]
        mode, size, namesize, checksum = values[1], values[6], values[11], values[12]
        name_end = offset + 110 + namesize
        start = (name_end + 3) & ~3
        end = start + size
        next_offset = (end + 3) & ~3
        if not namesize or name_end > len(data) or next_offset > len(data):
            raise ValueError("Truncated cpio entry")
        encoded_name = data[offset + 110:name_end]
        if encoded_name[-1:] != b"\x00" or b"\x00" in encoded_name[:-1]:
            raise ValueError("Invalid cpio filename terminator")
        name = relative_name(encoded_name[:-1].decode("utf-8"))
        payload = memoryview(data)[start:end]
        if header[:6] == b"070702" and sum(payload) & 0xffffffff != checksum:
            raise ValueError(f"Cpio checksum mismatch: {name}")
        if name == "TRAILER!!!":
            if size or any(memoryview(data)[next_offset:]):
                raise ValueError("Invalid cpio trailer or trailing data")
            missing = wanted - files.keys()
            if missing:
                raise ValueError("Missing ramdisk payloads: " + ", ".join(sorted(missing)))
            return files
        if name in seen:
            raise ValueError(f"Duplicate cpio path: {name}")
        seen.add(name)
        if name == "." and not stat.S_ISDIR(mode):
            raise ValueError("Cpio root entry must be a directory")
        if name in wanted:
            if not stat.S_ISREG(mode):
                raise ValueError(f"Ramdisk payload is not a regular file: {name}")
            files[name] = bytes(payload)
        offset = next_offset
    raise ValueError("Missing cpio trailer")
