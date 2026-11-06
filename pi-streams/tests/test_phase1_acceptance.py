from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import unittest


class AcceptanceRunnerTests(unittest.TestCase):
    def test_baseline_requires_behavior_failures_not_setup_errors(self):
        path = Path(__file__).resolve().parents[2] / "scripts/check-prime-phase1-parity.py"
        spec = importlib.util.spec_from_file_location("phase1_acceptance", path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        output = "Ran 3 tests\nFAILED (failures=3)\n" + "\n".join(runner.FAILURE_MARKERS)
        self.assertEqual(runner.expected_baseline_failures(subprocess.CompletedProcess([], 1, "", output)), True)
        for invalid in (
            subprocess.CompletedProcess([], 0, "", output),
            subprocess.CompletedProcess([], 1, "", output.replace("PHASE1_DRIVE_SILENT_OFF", "fixture setup failed")),
            subprocess.CompletedProcess([], 1, "", output + "\nERROR: loader failed"),
            subprocess.CompletedProcess([], 1, "", "FAILED (errors=3)"),
            subprocess.CompletedProcess([], 1, "", output.replace("Ran 3 tests", "Ran 2 tests")),
        ):
            with self.subTest(result=invalid):
                self.assertEqual(runner.expected_baseline_failures(invalid), False)
