from __future__ import annotations

import json
import os
import subprocess
import sys
from unittest import mock

from support import EngineCase, ROOT, snapshot

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, piweb


class PotetoInvocationTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.sid = "11111111-1111-4111-8111-111111111111"
        self.cwd = str(self.root)
        self.goal = "  Verify 'apostrophe', \"double\", $HOME and `ticks`, café.\r\nNext line\n/poteto-mode is literal here.  "
        self.text = f"Read current artifacts:\n- {self.cwd}/AGENTS.md\n- {self.cwd}/STATE.md\n/poteto-mode {self.goal}"
        self.token = {"sessionId": self.sid, "cwd": self.cwd, "generation": "saved-generation", "kind": "resume"}
        self.runtime = {"component": "sessiond", "capabilities": ["sessions.maintenanceCheckpoint", "prompt.potetoArguments", "sessions.streamsDcrEvents", "prompt.controlGoal", "sessions.conditionalAdmission", "prompt.recoveryControl", "sessions.failureBoundary", "sessions.failureFork", "sessions.failureMaintenance", "sessions.failureRetirement", "sessions.resumeObservation"]}
        self.status = {"sessionId": self.sid, "potetoInvocationSupport": "exact-goal-v1", "maintenanceSupport": "checkpoint-input-v1"}
        self.routes()

    def routes(self, status=None):
        self.stub.set_routes([
            ("GET", "/api/sessiond/runtime", 200, self.runtime),
            ("GET", f"/api/sessions/{self.sid}/status", 200, self.status if status is None else status),
            ("POST", f"/api/sessions/{self.sid}/prompt", 200, {"accepted": True, "deliveryId": "mode-notice"}),
            ("POST", f"/api/sessions/{self.sid}/maintenance/resume", 200, {"version": 1, "id": "mode-dcr", "sessionId": self.sid, "cwd": self.cwd, "state": "resuming", "inputSequence": 0, "inputs": [], "resume": {"deliveryId": "mode-resume", "text": self.text, "potetoGoal": self.goal, "generation": self.token["generation"], "inputSequence": 0, "state": "sending"}}),
        ])

    def test_standalone_json_invocation_preserves_exact_non_leading_body_and_goal(self):
        result = subprocess.run([str(ROOT / "bin/pi-web-cli"), "prompt", self.sid, "--delivery-id", "mode-notice", "--poteto"], input=json.dumps({"text": self.text, "goal": self.goal}), env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["transportAccepted"])
        self.assertEqual(self.stub.requests[-1][3], {"text": self.text, "deliveryId": "mode-notice", "potetoGoal": self.goal})

    def test_engine_prompt_requires_loaded_recipient_capability_and_carries_json_not_argv_goal(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            result = piweb.prompt(self.sid, self.text, delivery_id="mode-notice", poteto_goal=self.goal)
        self.assertTrue(result["transportAccepted"])
        self.assertEqual(self.stub.requests[-1][3]["potetoGoal"], self.goal)
        self.assertEqual(self.stub.requests[-1][3]["text"], self.text)
        self.routes(status={"sessionId": self.sid})
        self.stub.requests.clear()
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(StreamsError, "poteto|invocation|capability"):
                piweb.prompt(self.sid, self.text, delivery_id="mode-notice", poteto_goal=self.goal)
        self.assertEqual([request[0] for request in self.stub.requests], ["GET"])

    def test_saved_resume_retains_original_body_plus_exact_invocation_argument(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            record = piweb.resume_maintenance(self.sid, "mode-dcr", "native-compaction", 0, self.token, "mode-resume", self.text, poteto_goal=self.goal)
        self.assertEqual(record["resume"]["potetoGoal"], self.goal)
        self.assertEqual(self.stub.requests[-1][3], {"cwd": self.cwd, "id": "mode-dcr", "compactionEntryId": "native-compaction", "inputSequence": 0, "automaticAdmission": self.token, "deliveryId": "mode-resume", "text": self.text, "potetoGoal": self.goal})

    def test_free_length_goal_is_not_limited_by_one_argv_argument(self):
        goal = "x" * 180000 + "\r\nquoted 'tail'"
        text = "Read STATE first.\n/poteto-mode " + goal
        result = subprocess.run([str(ROOT / "bin/pi-web-cli"), "prompt", self.sid, "--delivery-id", "mode-notice", "--poteto"], input=json.dumps({"text": text, "goal": goal}), env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stub.requests[-1][3]["potetoGoal"], goal)
        self.assertEqual(self.stub.requests[-1][3]["text"], text)

    def test_mismatched_goal_or_malformed_invocation_is_refused_before_http(self):
        for body in ({"text": self.text, "goal": "different"}, {"text": self.text, "goal": None}, {"text": self.text}):
            result = subprocess.run([str(ROOT / "bin/pi-web-cli"), "prompt", self.sid, "--poteto"], input=json.dumps(body), env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertEqual(self.stub.requests, [])

    def test_installer_does_not_enable_the_tick_until_receiving_capabilities_pass(self):
        pstack = self.tmp / "private-pstack"
        names = subprocess.check_output(["bash", str(ROOT / "install.sh"), "--print-pstack-skills"], env=self.env, text=True).splitlines()
        for name in names:
            directory = pstack / "skills" / name
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(f"---\nname: {name}\ndescription: private installer fixture\n---\n# Fixture {name}\n")
        bindir = self.tmp / "installer-bin"
        bindir.mkdir()
        control_log = self.tmp / "systemctl.log"
        (bindir / "pi-web").write_text("#!/bin/sh\nexit 0\n")
        (bindir / "pi-web").chmod(0o755)
        (bindir / "systemctl").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$SYSTEMCTL_LOG"\n')
        (bindir / "systemctl").chmod(0o755)
        homes = self.xdg / "pi-streams/homes"
        homes.parent.mkdir(parents=True)
        homes.write_text(str(self.tmp / "private-index") + "\n")
        env = {**self.env, "PI_STACK": str(ROOT), "PSTACK": str(pstack), "PI_STACK_SKIP_PACKAGES": "1", "PATH": f"{bindir}:/usr/bin:/bin", "SYSTEMCTL_LOG": str(control_log)}
        self.stub.set_routes([("GET", "/api/sessiond/runtime", 200, {"component": "sessiond", "capabilities": []})])
        failed = subprocess.run(["bash", str(ROOT / "install.sh")], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn("before enabling the tick", failed.stderr)
        self.assertFalse(control_log.exists())
        self.routes()
        passed = subprocess.run(["bash", str(ROOT / "install.sh")], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertEqual(control_log.read_text(), "--user daemon-reload\n--user enable --now pi-streams-tick.timer\n")
        self.assertFalse((self.user_home / ".pi/agent/auth.json").exists())
        self.assertTrue(all(request[1] == "/api/sessiond/runtime" for request in self.stub.requests))

    def test_installer_read_only_capability_preflight_never_seeds_or_installs(self):
        before_home, before_config = snapshot(self.user_home), snapshot(self.xdg)
        result = subprocess.run(["bash", str(ROOT / "install.sh"), "--check-streams-capabilities"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertEqual(snapshot(self.user_home), before_home)
        self.assertEqual(snapshot(self.xdg), before_config)
        self.assertEqual([request[1] for request in self.stub.requests], ["/api/sessiond/runtime"])
        self.stub.set_routes([("GET", "/api/sessiond/runtime", 200, {"component": "sessiond", "capabilities": ["sessions.maintenanceCheckpoint", "prompt.potetoArguments", "sessions.streamsDcrEvents", "prompt.controlGoal"]})])
        result = subprocess.run(["bash", str(ROOT / "install.sh"), "--check-streams-capabilities"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertEqual(snapshot(self.user_home), before_home)
        self.assertEqual(snapshot(self.xdg), before_config)
