from __future__ import annotations

import json
import subprocess
from pathlib import Path

from support import EngineCase, ROOT, snapshot

CAPABILITIES = ["sessions.maintenanceCheckpoint", "prompt.potetoArguments", "sessions.streamsDcrEvents", "prompt.controlGoal", "sessions.conditionalAdmission", "prompt.recoveryControl", "sessions.failureBoundary", "sessions.failureFork", "sessions.failureMaintenance", "sessions.failureRetirement", "sessions.resumeObservation"]


class FailureAlignmentTests(EngineCase):
    def test_readonly_cli_installer_and_doctor_refuse_each_missing_failure_safety_capability(self):
        before = snapshot(self.user_home)
        for missing in CAPABILITIES[6:]:
            with self.subTest(missing=missing):
                runtime = {"component": "sessiond", "capabilities": [item for item in CAPABILITIES if item != missing]}
                self.stub.set_routes([("GET", "/api/sessiond/runtime", 200, runtime), ("GET", "/api/sessions", 200, [])])
                cli = subprocess.run([str(ROOT / "bin/pi-web-cli"), "capabilities"], env=self.env, capture_output=True, text=True)
                self.assertEqual(cli.returncode, 1)
                self.assertEqual(json.loads(cli.stdout)["missing"], [missing])
                installer = subprocess.run(["bash", str(ROOT / "install.sh"), "--check-streams-capabilities"], env=self.env, capture_output=True, text=True)
                self.assertEqual(installer.returncode, 1)
                report = self.run_streams("doctor")
                self.assertIn("FAIL maintenance:", report.stdout)
        self.assertEqual(snapshot(self.user_home), before)
        self.stub.set_routes([("GET", "/api/sessiond/runtime", 200, {"component": "sessiond", "capabilities": CAPABILITIES})])
        cli = subprocess.run([str(ROOT / "bin/pi-web-cli"), "capabilities"], env=self.env, capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["missing"], [])
        self.assertFalse(any(item[0] == "POST" for item in self.stub.requests))

    def test_new_stream_generated_instructions_teach_typed_parking_and_gated_singular_recovery(self):
        initialized = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        stream = self.home / "etl"
        self.stub.set_routes([("GET", "/api/sessions", 200, []), ("POST", "/api/sessions", 200, {"id": "fixture-coordinator", "cwd": str(stream)}), ("GET", "/api/sessions/fixture-coordinator/status", 200, {"sessionId": "fixture-coordinator", "model": {"provider": "openai-codex", "id": "gpt-6-astra"}, "thinkingLevel": "xhigh"}), ("POST", "/api/sessions/fixture-coordinator/prompt", 200, {"accepted": True})])
        generated = self.run_streams("new", "etl")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        instructions = (stream / "AGENTS.md").read_text()
        self.assertIn("Only usage-limit failures", instructions)
        self.assertIn("authenticated ZF notice", instructions)
        self.assertIn("single original", instructions)
        self.assertIn("independent authorized lanes", instructions)
        self.assertIn("not authentication proof", instructions)
        self.assertFalse((stream / "TODO.md").exists())
        self.assertFalse((stream / "PLAN.md").exists())
