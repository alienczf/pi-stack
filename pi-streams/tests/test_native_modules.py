"""Actual pinned Node modules, enabled only with an explicit disposable copy."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("PI_STACK_NATIVE_TEST_ROOT"), "set PI_STACK_NATIVE_TEST_ROOT to the patched disposable package")
class NativeModuleTests(unittest.TestCase):
    def test_actual_retry_modules(self):
        self.run_native("retry", 10)

    def test_actual_maintenance_modules(self):
        self.run_native("maintenance", 3)

    def test_actual_recovery_modules(self):
        self.run_native("recovery", 4)

    def test_actual_callback_ownership_modules(self):
        self.run_native("callbacks", 4)

    def test_actual_disabled_child_ownership(self):
        self.run_native("callbacks-child", 1)

    def run_native(self, name, count):
        native = Path(os.environ["PI_STACK_NATIVE_TEST_ROOT"]).resolve()
        self.assertIn(".harness-heal", native.parts)
        with tempfile.TemporaryDirectory() as temporary:
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": temporary, "XDG_CONFIG_HOME": temporary, "TMPDIR": temporary, "PI_OFFLINE": "1", "PI_STACK_NATIVE_TEST_ROOT": str(native)}
            result = subprocess.run([shutil.which("node"), "--test", str(ROOT / f"pi-streams/tests/native/{name}.test.mjs")], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"# pass {count}", result.stdout)
