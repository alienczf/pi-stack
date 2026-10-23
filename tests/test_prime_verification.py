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
        self.runtime = self.root / "fake-prime-agent"
        self.runtime.write_text(f'''#!/usr/bin/env python3
import json, os, signal, sys
from pathlib import Path
sys.path.insert(0, {str(ROOT / "tests")!r})
from test_prime_tools import OwnedSupervisor
root = Path(sys.argv[sys.argv.index("--daemon-socket") + 1]).parent
Path({str(self.log)!r}).write_text(json.dumps({{"argv": sys.argv[1:], "agentDir": os.environ.get("PRIME_AGENT_CODING_AGENT_DIR")}}))
with OwnedSupervisor(root) as server:
    signal.signal(signal.SIGTERM, lambda *_: server.stopped.set())
    server.stopped.wait(15)
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
            "agentDir": str(self.owned / "agent")})
        self.assertEqual((self.owned / "agent/settings.json").read_bytes(), before)
        self.assertFalse((self.owned / "daemon.sock").exists())
        self.assertFalse((self.owned / "verification.lock").exists())

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
        text = self.runtime.read_text().replace("OwnedSupervisor(root)", 'OwnedSupervisor(root, fail_command="get_commands")')
        self.runtime.write_text(text)
        proc = self.verify()
        self.assertEqual(proc.returncode, 1, proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["error"]["error"], "upstream_error")
        self.assertEqual(result["retainedOwnedSessions"], [])
        self.assertEqual(result["runtime"], {"started": True, "stopped": True, "socketRemoved": True})
        self.assertFalse((self.owned / "daemon.sock").exists())

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
