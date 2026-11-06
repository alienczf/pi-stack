from __future__ import annotations

import os
import unittest

import test_native_modules as native_cases


@unittest.skipUnless(os.environ.get("PI_STACK_NATIVE_TEST_ROOT"), "set PI_STACK_NATIVE_TEST_ROOT to the patched disposable package")
class Phase1NativeTests(unittest.TestCase):
    run_native = native_cases.NativeModuleTests.run_native

    def test_hung_compaction_fences_late_writes(self):
        self.run_native("phase1-maintenance", 3)
