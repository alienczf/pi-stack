"""Mutating commands wait for the index lock, then the stream repo lock."""
from __future__ import annotations

import fcntl
import os
import subprocess
import time
import unittest

from support import CLI, EngineCase, git


class LockTests(EngineCase):
    def test_new_waits_for_the_index_lock(self) -> None:
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "coord-1"}),
            (
                "GET",
                "/api/sessions/coord-1/status",
                200,
                {
                    "sessionId": "coord-1",
                    "isStreaming": False,
                    "contextUsage": {"tokens": 10},
                    "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
                    "thinkingLevel": "xhigh",
                    "cost": 0,
                },
            ),
            ("POST", "/api/sessions/coord-1/prompt", 200, {"accepted": True}),
        ])
        self.stub.requests.clear()
        with open(self.index / ".pi-streams.lock", "a", encoding="utf-8") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            waiting = subprocess.Popen(
                [os.fspath(CLI), "new", "etl"],
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            self.addCleanup(waiting.kill)
            time.sleep(1.5)
            self.assertIsNone(waiting.poll(), "new finished while the lock was held")
            self.assertEqual(self.stub.requests, [])
            self.assertFalse((self.home / "etl").exists())
        out, err = waiting.communicate(timeout=30)
        self.assertEqual(waiting.returncode, 0, err)
        self.assertEqual(out, "http://127.0.0.1:8504\ncoord-1\n")
        self.assertEqual(git(self.home / "etl", self.env, "log", "-1", "--format=%s").strip(), "pi-streams new etl")


if __name__ == "__main__":
    unittest.main()
