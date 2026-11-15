#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""用短 shell fixture 验证 workflow 的 Rust 缓存门禁，不执行 Android 编译。"""

import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
import unittest


TREE = Path(__file__).resolve().parents[2]
WORKFLOW = TREE / ".github/workflows/build.yml"


def scripts():
    blocks = re.split(r"^      - name: ", WORKFLOW.read_text(), flags=re.M)[1:]
    result = {}
    for block in blocks:
        name = block.splitlines()[0]
        match = re.search(r"^        run: \|\n((?:          .*\n|\n)*)", block, re.M)
        if match:
            result[name] = "\n".join(line[10:] for line in match[1].splitlines()) + "\n"
    return result


@unittest.skipUnless(os.name == "posix", "requires Linux shell tools")
class RustCacheTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="yarp-rust-cache-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / "source"
        self.logs = self.root / "logs"
        self.bin = self.root / "bin"
        for path in (self.source, self.logs, self.bin):
            path.mkdir()
        # 预算边界不分配 GiB 数据；真实 mv、目录隔离、输出门禁保持不变。
        self.stub("du", 'printf "%s\\t%s\\n" "$FIXTURE_SIZE" "${@: -1}"\n')
        self.stub("df", 'printf "Filesystem 1024-blocks Used Available Capacity Mounted\\nfixture 99999999 0 %s 0%% /\\n" "$FIXTURE_FREE"\n')
        self.env = dict(os.environ, SOURCE_ROOT=str(self.source), RUNNER_TEMP=str(self.root),
                        CI_LOG_DIR=str(self.logs), GITHUB_OUTPUT=str(self.root / "output"),
                        GITHUB_ENV=str(self.root / "env"), PATH=f"{self.bin}:{os.environ['PATH']}",
                        FIXTURE_SIZE="16", FIXTURE_FREE=str(40 * 1024 * 1024),
                        RUST_CACHE_OUTCOME="success", RUST_CACHE_HIT="true",
                        SOONG_RUSTC_INCREMENTAL="true", OUT_DIR="out", OUT_DIR_COMMON_BASE="",
                        RUNNER_OS="Linux", RUNNER_ARCH="X64", BUILD_OUTCOME="success",
                        VERIFY_OUTCOME="success", RUST_CACHE_KEY="fixture-key")

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\n" + body)
        path.chmod(0o755)

    def run_step(self, name):
        (self.root / "output").write_text("")
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", scripts()[name]],
                                cwd=self.root, env=self.env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout)
        return (self.root / "output").read_text()

    def make_store(self, staging=True):
        path = (self.root / "yarp-rust-cache/rustc" if staging else self.source / "out/rustc")
        path.mkdir(parents=True)
        (path / "fixture.bin").write_bytes(b"incremental fixture")
        return path

    def activate(self):
        self.run_step("Activate complete Rust incremental cache")
        return json.loads((self.logs / "cache-rust-restore.json").read_text())

    def test_all_shell_syntax(self):
        for name, script in scripts().items():
            with self.subTest(step=name):
                subprocess.run(["bash", "-n"], input=script, text=True, check=True, timeout=5)
        subprocess.run(["bash", "-n", str(TREE / "tools/build.sh")], check=True, timeout=5)

    def test_restore_success_moves_complete_directory(self):
        store = self.make_store()
        self.assertTrue(self.activate()["restored"])
        self.assertFalse(store.exists())
        self.assertTrue((self.source / "out/rustc/fixture.bin").is_file())

    def test_restore_miss_failure_and_over_budget_are_isolated(self):
        for updates in ({"RUST_CACHE_HIT": "false"}, {"RUST_CACHE_OUTCOME": "failure"},
                        {"RUST_CACHE_OUTCOME": "cancelled"},
                        {"FIXTURE_SIZE": str(3 * 1024 * 1024 + 1)},
                        {"FIXTURE_FREE": str(25 * 1024 * 1024 - 1)}):
            with self.subTest(updates=updates):
                original = self.env.copy()
                self.env.update(updates)
                store = self.make_store()
                self.assertFalse(self.activate()["restored"])
                self.assertFalse(store.exists())
                self.assertFalse((self.source / "out/rustc").exists())
                self.assertTrue(list(self.root.glob("yarp-rust-cache-incomplete.*/rustc/fixture.bin")))
                self.env = original

    def test_failed_size_check_is_isolated(self):
        self.make_store()
        self.stub("du", "exit 1\n")
        self.assertFalse(self.activate()["restored"])
        self.assertFalse((self.source / "out/rustc").exists())

    def test_key_generation_failure_never_publishes_key(self):
        (self.root / "integration").mkdir()
        (self.root / "integration/manifest.lock.xml").write_text(
            '<manifest><project path="prebuilts/rust" revision="rust-sha"/></manifest>')
        self.stub("git", "exit 7\n")
        output = self.root / "output"
        output.write_text("")
        result = subprocess.run(["bash", "-c", scripts()["Prepare exact Rust incremental cache"]],
                                cwd=self.root, env=self.env, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(), "")

    def test_restore_missing_directory_is_cold(self):
        self.assertFalse(self.activate()["restored"])
        self.env["RUST_CACHE_HIT"] = "false"
        self.assertFalse(self.activate()["restored"])

    def test_save_gate_and_budget(self):
        store = self.make_store(staging=False)
        self.env["RUST_CACHE_HIT"] = "false"
        for updates in ({"BUILD_OUTCOME": "failure"}, {"VERIFY_OUTCOME": "failure"},
                        {"RUST_CACHE_HIT": "true"}, {"RUST_CACHE_KEY": ""},
                        {"SOONG_RUSTC_INCREMENTAL": "false"},
                        {"FIXTURE_SIZE": str(3 * 1024 * 1024 + 1)},
                        {"FIXTURE_FREE": str(3 * 1024 * 1024 + 15)}):
            with self.subTest(updates=updates):
                original = self.env.copy()
                self.env.update(updates)
                self.assertNotIn("save=true", self.run_step("Prepare verified Rust incremental cache save"))
                self.assertTrue(store.exists())
                self.env = original
        self.assertIn("save=true", self.run_step("Prepare verified Rust incremental cache save"))
        self.assertFalse(store.exists())
        self.assertTrue((self.root / "yarp-rust-cache/rustc/fixture.bin").exists())

    def test_failed_restore_can_save_only_new_verified_data(self):
        self.make_store()
        self.env.update(RUST_CACHE_OUTCOME="failure", RUST_CACHE_HIT="false")
        self.activate()
        self.make_store(staging=False).joinpath("fixture.bin").write_bytes(b"verified new data")
        self.assertIn("save=true", self.run_step("Prepare verified Rust incremental cache save"))
        self.assertEqual((self.root / "yarp-rust-cache/rustc/fixture.bin").read_bytes(), b"verified new data")

    def test_prepare_budget_and_key_inputs(self):
        (self.root / "integration").mkdir()
        manifest = self.root / "integration/manifest.lock.xml"
        manifest.write_text('<manifest><project path="prebuilts/rust" revision="rust-sha"/></manifest>')
        config = self.root / "BoardConfig.mk"
        config.write_text("TARGET_ARCH := arm64\n")
        self.stub("git", "printf 'integration/manifest.lock.xml\\0BoardConfig.mk\\0'\n")
        first = self.run_step("Prepare exact Rust incremental cache")
        self.assertIn("restore=true", first)
        self.assertIn("yarp-rust-v1-Linux-X64-rust-sha-", first)
        config.write_text("TARGET_ARCH := arm\n")
        second = self.run_step("Prepare exact Rust incremental cache")
        self.assertNotEqual(first, second)
        other_source = self.root / "other-source"
        other_source.mkdir()
        self.env["SOURCE_ROOT"] = str(other_source)
        self.assertNotEqual(second, self.run_step("Prepare exact Rust incremental cache"))
        self.env["FIXTURE_FREE"] = str(31 * 1024 * 1024 - 1)
        self.assertNotIn("restore=true", self.run_step("Prepare exact Rust incremental cache"))

    def test_action_metrics_handle_blueprint_continuations(self):
        graph = self.source / "out/soong"
        graph.mkdir(parents=True)
        output = ("out/soong/.intermediates/external/rust/crates/fixture/libfixture/"
                  "android_arm64_armv8-a_static_rlib/libfixture.rlib")
        graph.joinpath(".ninja_log").write_text(
            f"# ninja log v5\n100\t450\t0\t{output}\tabc\n")
        module = runpy.run_path(str(TREE / "tools/ci/summarize.py"))
        # Blueprint 在长输出后把规则名换到下一物理行；也覆盖多个连续续行。
        for edge in (
            f"build {output}: $\n    android/soong/rust.rustc fixture.rs\n",
            f"build $\n    {output}: $\n    android/soong/rust.rustc $\n    fixture.rs\n",
        ):
            with self.subTest(edge=edge):
                # $$ 是字面量美元符号，不能误吞下一条 build 语句。
                graph.joinpath("build.fixture.ninja").write_text("literal = $$\n" + edge)
                self.assertEqual(module["rust_actions"](self.source), [
                    {"output": output, "elapsed_ms": 350, "command_hash": "abc"}])

    def test_action_metrics_match_rules_and_deduplicate_logs(self):
        graph = self.source / "out/soong"
        graph.mkdir(parents=True)
        graph.joinpath("build.fixture.ninja").write_text(
            "build out/libfixture.rlib: android-soong-rust-rustc fixture.rs\n"
            "build out/other.rlib: cp prebuilt\n")
        record = "# ninja log v5\n100\t450\t0\tout/libfixture.rlib\tabc\n0\t999\t0\tout/other.rlib\tdef\n"
        graph.joinpath(".ninja_log").write_text(record)
        self.source.joinpath("out/.ninja_log").write_text(record)
        module = runpy.run_path(str(TREE / "tools/ci/summarize.py"))
        actions = module["rust_actions"](self.source)
        self.assertEqual(actions, [{"output": "out/libfixture.rlib", "elapsed_ms": 350, "command_hash": "abc"}])
        report = "\n".join(module["summarize_rust"](self.logs, self.source))
        self.assertIn("不证明 rustc 内部复用", report)
        self.assertEqual(json.loads((self.logs / "rust-actions.json").read_text()), actions)


if __name__ == "__main__":
    unittest.main(verbosity=2)
