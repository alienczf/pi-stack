"""Owned launcher checks through subprocesses and fake supervisor processes only."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_prime_cli import ROOT
from test_prime_tools import OwnedSupervisor


DEFINITION = {"provider": "openai-codex", "id": "gpt-6.1-sol", "name": "GPT-6.1 Sol",
              "api": "openai-codex-responses", "reasoning": True,
              "thinkingLevelMap": {"off": None, "minimal": "low", "low": "low", "medium": "medium",
                                   "high": "high", "xhigh": "xhigh", "max": "max"},
              "input": ["text", "image"],
              "contextWindow": 500000, "maxTokens": 128000,
              "cost": {"input": 2, "output": 10, "cacheRead": 0.1, "cacheWrite": 2.5}}


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="prime-verification-test-")
        self.root = Path(self.temp.name)
        self.env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                    "TMPDIR": str(self.root)}
        self.script = ROOT / "scripts/check-prime-cli-live.py"
        proc = self.run_check("prepare")
        self.owned = Path(json.loads(proc.stdout)["root"])
        self.log = self.root / "runtime.json"
        self.events_log = self.root / "events.json"
        self.runtime = self.root / "fake-prime-agent"
        self.runtime.write_text(f'''#!/usr/bin/env python3
import json, os, signal, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "tests")!r})
from test_prime_tools import OwnedSupervisor
root = Path(sys.argv[sys.argv.index("--daemon-socket") + 1]).parent
Path({str(self.log)!r}).write_text(json.dumps({{"argv": sys.argv[1:], "agentDir": os.environ.get("PRIME_AGENT_CODING_AGENT_DIR"), "sessionDir": os.environ.get("PRIME_AGENT_SESSION_DIR"), "socketEnv": os.environ.get("PRIME_AGENT_DAEMON_SOCKET"), "cwd": os.getcwd()}}))
class MetadataSupervisor(OwnedSupervisor):
    def response(self, command, owner):
        if command["type"] == "shutdown":
            self.stopped.set()
            return {{"success": True}}
        if command["type"] == "create":
            self.archived = False
        result = super().response(command, owner)
        if result.get("success") and command["type"] in ("get_connection_state", "set_model"):
            definition = json.loads((root / "agent/models.json").read_text())["providers"]["openai-codex"]["models"][0]
            model = {{"provider": "openai-codex", **definition}}
            if command["type"] == "get_connection_state":
                result["data"]["model"] = model
            else:
                result["data"] = model
        return result
with MetadataSupervisor(root) as server:
    signal.signal(signal.SIGTERM, lambda *_: server.stopped.set())
    server.stopped.wait(15)
Path({str(self.events_log)!r}).write_text(json.dumps({{"requests": server.requests, "events": server.events, "admitted": server.admitted_inputs, "runnable": server.runnable_inputs}}))
''')
        self.runtime.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def run_check(self, *args):
        return subprocess.run(["python3", str(self.script), *args], capture_output=True, text=True,
                              env=self.env, timeout=25)

    def verify(self, *args):
        return self.run_check("verify", "--root", str(self.owned), "--runtime", str(self.runtime),
                              "--timeout", "2", *args)

    def test_launcher_reuses_root_and_stops_only_its_fake_process(self):
        before = (self.owned / "agent/settings.json").read_bytes()
        proc = self.verify()
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["retainedOwnedSessions"], [])
        self.assertEqual(result["inferenceRequested"], False)
        self.assertEqual(result["runtime"], {"started": True, "stopped": True, "socketRemoved": True})
        self.assertEqual(json.loads(self.log.read_text()), {
            "argv": ["--mode", "daemon", "--daemon-socket", str(self.owned / "daemon.sock")],
            "agentDir": str(self.owned / "agent"), "sessionDir": str(self.owned / "agent/sessions"),
            "socketEnv": str(self.owned / "daemon.sock"), "cwd": str(self.owned / "work")})
        self.assertEqual((self.owned / "agent/settings.json").read_bytes(), before)
        self.assertFalse((self.owned / "daemon.sock").exists())
        self.assertFalse((self.owned / "verification.lock").exists())

    def test_launcher_native_shutdown_targets_only_owned_socket(self):
        proc = self.verify()
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        events = json.loads(self.events_log.read_text())
        self.assertEqual(events["requests"][-1], {"type": "shutdown", "force": True})
        self.assertEqual(events["admitted"], [])
        self.assertEqual(events["runnable"], [])

    def test_explicit_inference_runs_control_first_and_never_retries_native_failure(self):
        proc = self.verify("--inference")
        self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["error"]["error"], "upstream_error")
        self.assertEqual(result["retainedOwnedSessions"], [])
        events = json.loads(self.events_log.read_text())["events"]
        self.assertEqual(events.count("create"), 2)
        self.assertEqual(events.count("prompt_and_wait"), 1)
        self.assertLess(events.index("kill"), events.index("prompt"))
        self.assertEqual(events[-1], "shutdown")

    def test_root_safety_and_no_retry_settings_are_checked_before_launch(self):
        settings = self.owned / "agent/settings.json"
        original = settings.read_bytes()
        for changes in ({"enabled": True}, {"provider": {"waitForUsage": {"enabled": True, "pauseUntilReset": True}}}):
            config = json.loads(original)
            config["retry"].update(changes)
            settings.write_text(json.dumps(config))
            proc = self.verify()
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertEqual(json.loads(proc.stdout)["error"]["error"], "unsafe_verification_root")
            self.assertFalse(self.log.exists())
        settings.write_bytes(original)
        outside = self.root / "outside-settings.json"
        outside.write_bytes(original)
        settings.unlink()
        settings.symlink_to(outside)
        proc = self.verify()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["error"]["error"], "unsafe_verification_root")
        self.assertFalse(self.log.exists())

    def test_launcher_refuses_existing_socket_without_contact_or_shutdown(self):
        with OwnedSupervisor(self.owned) as server:
            proc = self.verify()
            result = json.loads(proc.stdout)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertEqual(result["error"]["error"], "runtime_collision")
            self.assertEqual(result["runtime"]["started"], False)
            self.assertEqual(server.requests, [])
            self.assertTrue((self.owned / "daemon.sock").exists())
        self.assertFalse(self.log.exists())

    def test_launcher_refuses_existing_lock_and_unprepared_root(self):
        lock = self.owned / "verification.lock"
        lock.write_text("another-owner\n")
        proc = self.verify()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["error"]["error"], "runtime_collision")
        self.assertEqual(lock.read_text(), "another-owner\n")
        invalid = self.run_check("verify", "--root", str(self.root), "--runtime", str(self.runtime))
        self.assertEqual(invalid.returncode, 1, invalid.stdout)
        self.assertEqual(json.loads(invalid.stdout)["runtime"]["started"], False)
        self.assertFalse(self.log.exists())

    def test_launcher_stops_fake_runtime_after_check_failure(self):
        text = self.runtime.read_text().replace("MetadataSupervisor(root)", 'MetadataSupervisor(root, fail_command="get_commands")')
        self.runtime.write_text(text)
        proc = self.verify()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["error"]["error"], "upstream_error")
        self.assertEqual(result["retainedOwnedSessions"], [])
        self.assertEqual(result["runtime"], {"started": True, "stopped": True, "socketRemoved": True})
        self.assertFalse((self.owned / "daemon.sock").exists())

    def test_registration_uses_only_whitelisted_metadata_in_isolated_agent_dir(self):
        text = self.runtime.read_text().replace('"agentDir": os.environ.get("PRIME_AGENT_CODING_AGENT_DIR")',
            '"agentDir": os.environ.get("PRIME_AGENT_CODING_AGENT_DIR"), "models": json.loads((root / "agent/models.json").read_text())')
        self.runtime.write_text(text)
        proc = self.verify()
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        model = {key: value for key, value in DEFINITION.items() if key != "provider"}
        self.assertEqual(json.loads(self.log.read_text())["models"], {"providers": {"openai-codex": {"models": [model]}}})
        self.assertFalse((self.owned / "agent/models.json").exists())
        self.assertIn("not represented", json.loads(proc.stdout)["modelMetadata"]["limitations"][0])

    def test_explicit_metadata_is_validated_without_launch_or_secret_fields(self):
        source = self.root / "definition.json"
        cases = [{**DEFINITION, "contextWindow": 0}, {**DEFINITION, "reasoning": "true"},
                 {**DEFINITION, "maxTokens": 500001}, {**DEFINITION, "contextWindow": True},
                 {**DEFINITION, "provider": "other"}, {**DEFINITION, "api": "other"},
                 {**DEFINITION, "cost": {**DEFINITION["cost"], "input": -1}},
                 {**DEFINITION, "cost": {**DEFINITION["cost"], "output": float("nan")}},
                 {**DEFINITION, "thinkingLevelMap": {"xhigh": "guessed"}},
                 {**DEFINITION, "headers": {}}, {**DEFINITION, "baseUrl": "not-a-provider-endpoint"},
                 {key: value for key, value in DEFINITION.items() if key != "maxTokens"}]
        for definition in cases:
            with self.subTest(definition=definition):
                source.write_text(json.dumps(definition))
                proc = self.verify("--model-definition", str(source))
                self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
                self.assertEqual(json.loads(proc.stdout)["error"]["error"], "invalid_model_definition")
                self.assertFalse(self.log.exists())
                self.assertFalse((self.owned / "agent/models.json").exists())
                self.assertFalse((self.owned / "verification.lock").exists())

    def test_metadata_mismatch_blocks_inference_and_cleans_owned_runtime(self):
        text = self.runtime.read_text().replace('model = {"provider": "openai-codex", **definition}',
            'model = {"provider": "openai-codex", **definition, "contextWindow": 128000}')
        self.runtime.write_text(text)
        proc = self.verify("--inference")
        self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["error"]["error"], "model_metadata_mismatch")
        self.assertEqual(result["retainedOwnedSessions"], [])
        self.assertEqual(result["runtime"]["stopped"], True)
        self.assertNotIn("prompt_and_wait", [row.get("command") for row in result["checks"]])

    def test_registration_refuses_existing_native_config_without_replacing_it(self):
        config = self.owned / "agent/models.json"
        config.write_text("unowned configuration\n")
        proc = self.verify()
        self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["error"]["error"], "model_registration_collision")
        self.assertEqual(config.read_text(), "unowned configuration\n")
        self.assertFalse(self.log.exists())

    def test_launcher_never_runs_check_after_startup_exit(self):
        self.runtime.write_text('#!/usr/bin/env python3\nraise SystemExit(17)\n')
        proc = self.verify()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["error"]["error"], "runtime_start_failed")
        self.assertEqual(result["runtime"]["stopped"], True)
        self.assertEqual(result["retainedOwnedSessions"], [])
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
