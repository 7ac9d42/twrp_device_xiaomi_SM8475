#!/usr/bin/env python3
"""Compile and run GPT regression tests without Android or block devices."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    source = Path(__file__).with_suffix(".cpp")
    compiler = os.environ.get("CXX") or shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A local C++ compiler and zlib development headers are required")
    with tempfile.TemporaryDirectory(prefix="test_gpt_utils_") as directory:
        work = Path(directory)
        headers = work / "cutils"
        headers.mkdir()
        (headers / "log.h").write_text(
            '#pragma once\n#define ALOGE(...) fprintf(stderr, __VA_ARGS__)\n',
            encoding="utf-8",
        )
        (headers / "properties.h").write_text(
            '#pragma once\n#define PROPERTY_VALUE_MAX 92\n'
            'static inline int property_get(const char *, char *value, const char *def) {\n'
            '    strcpy(value, def); return strlen(def);\n}\n',
            encoding="utf-8",
        )
        executable = work / "test_gpt_utils"
        command = [
            compiler, "-std=c++17", "-Wall", "-Werror", "-Wno-unused-parameter",
            "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-I", str(work), str(source), "-lz", "-o", str(executable),
        ]
        print("Compile:", " ".join(command), flush=True)
        subprocess.run(command, check=True, timeout=120)
        print("Run:", executable, flush=True)
        environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
                           UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        result = subprocess.run([str(executable)], capture_output=True, text=True,
                                env=environment, timeout=60)
        print(result.stdout, end="", flush=True)
        if result.returncode:
            print(result.stderr, end="", flush=True)
        result.check_returncode()


if __name__ == "__main__":
    main()
