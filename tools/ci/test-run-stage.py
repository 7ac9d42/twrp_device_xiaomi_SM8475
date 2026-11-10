#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""在 Linux 上验证阶段日志和进程监督的关键行为。"""

import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time
import unittest


SCRIPT = Path(__file__).with_name("run-stage.sh")


@unittest.skipUnless(os.name == "posix", "requires Linux process groups")
class StageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="yarp-stage-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.environment = dict(os.environ, CI_LOG_DIR=str(self.root))
        self.environment.pop("SOURCE_ROOT", None)

    def start(self, command, seconds=20):
        self.environment["CI_DEADLINE"] = str(int(time.time()) + seconds)
        process = subprocess.Popen(
            ["bash", str(SCRIPT), "test", "bash", "-c", command],
            cwd=self.root,
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.addCleanup(self.stop, process)
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=40)

    def receive(self, process, marker):
        output = b""
        deadline = time.monotonic() + 5
        while marker not in output:
            remaining = deadline - time.monotonic()
            self.assertGreater(remaining, 0, output.decode(errors="replace"))
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            self.assertTrue(ready, output.decode(errors="replace"))
            data = os.read(process.stdout.fileno(), 65536)
            self.assertTrue(data, output.decode(errors="replace"))
            output += data
        return output

    def timing(self):
        return json.loads(next(self.root.glob("*/timing.json")).read_text())

    def test_live_stdout_stderr_and_final_output(self):
        process = self.start("printf 'live-output\\n'; printf 'stderr-output\\n' >&2; sleep 3; printf 'final-output\\n'")
        live = self.receive(process, b"stderr-output\n")
        self.assertIsNone(process.poll(), "output only appeared after the command finished")
        rest, _ = process.communicate(timeout=8)
        output = live + rest
        self.assertEqual(process.returncode, 0, output.decode())
        self.assertIn(b"final-output\n", output)
        saved = next(self.root.glob("*/command.log")).read_bytes()
        self.assertIn(b"live-output\nstderr-output\n", saved)
        self.assertTrue(saved.endswith(b"final-output\n"))
        self.assertEqual(self.timing()["exit_status"], 0)

    def test_log_relay_drains_before_exit(self):
        process = self.start("for ((i=0;i<10000;i++)); do printf 'buffered-output\\n'; done; printf 'last-record\\n'")
        output, _ = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 0)
        saved = next(self.root.glob("*/command.log")).read_bytes()
        self.assertEqual(saved.count(b"buffered-output\n"), 10000)
        self.assertTrue(saved.endswith(b"last-record\n"))
        self.assertIn(b"last-record\n", output)

    def test_command_failure_is_preserved(self):
        process = self.start("printf 'failed-command\\n'; exit 7")
        output, _ = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 7, output.decode())
        self.assertEqual(self.timing()["exit_status"], 7)

    def test_timeout_is_preserved(self):
        process = self.start("exec sleep 30", seconds=1)
        output, _ = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 124, output.decode())
        self.assertEqual(self.timing()["exit_status"], 124)

    def test_cancel_stops_descendant(self):
        process = self.start("printf 'descendant=%s\\n' \"$$\"; exec sleep 60")
        output = self.receive(process, b"descendant=")
        while b"\n" not in output.split(b"descendant=", 1)[1]:
            output += os.read(process.stdout.fileno(), 1024)
        child = int(output.split(b"descendant=", 1)[1].splitlines()[0])
        process.send_signal(signal.SIGTERM)
        rest, _ = process.communicate(timeout=40)
        self.assertEqual(process.returncode, 143, (output + rest).decode())
        self.assertFalse(Path(f"/proc/{child}").exists(), "stage descendant survived cancellation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
