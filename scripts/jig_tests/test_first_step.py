import json
import os
import subprocess
import sys
import unittest

from scripts.jig_tests import test_verification


class FirstStepTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_verification.VerificationTest(methodName="runTest")
        self.fixture.setUp()
        self.repo = self.fixture.repo
        self.fixture.begin()
        self.fixture.install_generated()
        completed = self.fixture.ctl("complete-verification")
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def tearDown(self):
        self.fixture.tearDown()

    def ctl(self, *arguments):
        return self.fixture.ctl(*arguments)

    def manifest(self):
        return self.fixture.manifest()

    def test_ready_enters_selecting_without_step_artifacts(self):
        before = self.manifest()
        selected = self.ctl("begin-step-selection")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        manifest = self.manifest()
        self.assertEqual(manifest["currentState"], "step-selecting")
        self.assertEqual(len(manifest["transitions"]), len(before["transitions"]) + 1)
        transition = manifest["transitions"][-1]
        self.assertEqual((transition["from"], transition["to"]), ("verification-ready", "step-selecting"))
        receipt = json.loads((self.repo / transition["receiptPath"]).read_text())
        runtime = manifest["verification"][0]["receiptPath"]
        runtime_artifact = next(item for item in manifest["artifacts"] if item["path"] == runtime)
        self.assertEqual(receipt["kind"], "step-selection-started")
        self.assertEqual(receipt["resourceIsolation"], manifest["resourceIsolation"])
        self.assertEqual(receipt["commandmentsSha256"], manifest["commandments"]["sha256"])
        self.assertEqual((receipt["runtimeReceiptPath"], receipt["runtimeReceiptSha256"]), (runtime, runtime_artifact["sha256"]))
        self.assertEqual(manifest["firstStep"]["outcome"], "pending")
        self.assertFalse((self.repo / ".pi/jig/steps/0001").exists())

    def test_matching_rerun_is_idempotent_and_drift_fails_closed(self):
        first = self.ctl("begin-step-selection")
        self.assertEqual(first.returncode, 0, first.stderr)
        original = (self.repo / ".pi/jig/manifest.json").read_bytes()
        rerun = self.ctl("begin-step-selection")
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), original)
        wrong_route = subprocess.run(
            [
                sys.executable,
                str(test_verification.CONTROLLER),
                "begin-step-selection",
                "--resource-isolation",
                "inherited-session",
            ],
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "JIG_PI_VERSION": "fixture-pi"},
        )
        self.assertNotEqual(wrong_route.returncode, 0)
        (self.repo / "drift.txt").write_text("drift\n")
        drifted = self.ctl("begin-step-selection")
        self.assertNotEqual(drifted.returncode, 0)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), original)

    def test_failure_and_start_reconcile_only_selecting(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        failed = self.ctl("record-failure", "--state", "step-selecting", "--reason", "seeded selection failure")
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(self.manifest()["currentState"], "failed-step-selecting")
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        manifest = self.manifest()
        self.assertEqual(manifest["currentState"], "step-selecting")
        self.assertEqual((manifest["transitions"][-1]["from"], manifest["transitions"][-1]["to"]), ("failed-step-selecting", "step-selecting"))
        self.assertFalse((self.repo / ".pi/jig/steps/0001").exists())


if __name__ == "__main__":
    unittest.main()
