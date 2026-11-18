#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""验证工具链缓存的隔离、容量门禁和计时记录。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("toolchain-cache.sh")


@unittest.skipUnless(os.name == "posix", "requires Linux utilities")
class ToolchainCacheTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="yarp-cache-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = self.root / ".repo/project-objects/platform/prebuilts/rust.git"
        (self.store / "objects").mkdir(parents=True)
        self.project = self.root / ".repo/projects/prebuilts/rust.git"
        self.project.mkdir(parents=True)
        self.output = self.root / "output"
        self.env = dict(os.environ, SOURCE_ROOT=str(self.root), RUNNER_TEMP=str(self.root),
                        CI_LOG_DIR=str(self.root), GITHUB_OUTPUT=str(self.output),
                        GITHUB_ENV=str(self.root / "env"))

    def run_cache(self, action, *args):
        return subprocess.check_output(
            ["bash", str(SCRIPT), action, "rust", *args], env=self.env, text=True, timeout=10,
        )

    def test_exact_hit_preserves_object_store(self):
        self.run_cache("finish-restore", "success", "true", "123")
        self.assertTrue(self.store.is_dir())
        timing = json.loads((self.root / "cache-rust-restore.json").read_text())
        self.assertEqual((timing["start_epoch"], timing["exact_hit"]), (123, "true"))

    def test_non_exact_restore_is_isolated(self):
        for outcome, hit in [("failure", "true"), ("success", "false"), ("skipped", "")]:
            with self.subTest(outcome=outcome, hit=hit):
                self.run_cache("finish-restore", outcome, hit)
                self.assertFalse(self.store.exists())
                isolated = list(self.root.glob("yarp-rust-cache-incomplete.*/rust.git"))
                self.assertEqual(len(isolated), 1)
                isolated[0].rename(self.store)
                isolated[0].parent.rmdir()

    def test_save_requires_shared_store_and_space(self):
        (self.project / "objects").mkdir()
        self.run_cache("check-save")
        self.assertFalse(self.output.exists())
        (self.project / "objects").rmdir()
        (self.project / "objects").symlink_to(self.store / "objects", target_is_directory=True)
        for size, available, can_save in [(1024, 8388608, True), (2097153, 8388608, False),
                                           (1024, 3146751, False)]:
            with self.subTest(size=size, available=available):
                for tool, result in {"du": f"{size}\tfake", "df": f"header\nfake 0 0 {available}"}.items():
                    fake = self.root / tool
                    fake.write_text(f"#!/bin/sh\nprintf '%s\\n' '{result}'\n", encoding="utf-8")
                    fake.chmod(0o700)
                self.output.write_text("")
                self.env["PATH"] = f"{self.root}{os.pathsep}{os.environ['PATH']}"
                self.run_cache("check-save")
                self.assertEqual(self.output.read_text() == "save=true\n", can_save)
        self.run_cache("finish-save", "success", "456")
        timing = json.loads((self.root / "cache-rust-save.json").read_text())
        self.assertEqual((timing["start_epoch"], timing["status"]), (456, "success"))


if __name__ == "__main__":
    unittest.main()
