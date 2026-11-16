"""Saved openings cannot fence unrelated lifecycle work after their owner retires."""
from __future__ import annotations

import json

from test_coordinator_reuse import CoordinatorReuseTests
from test_retired_native_residue import RetiredNativeResidueTests


def seed_start(case, session="dead", *, phase="sending", operation="new"):
    path = case.stream / "log/tick-state.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    start = {"session": session, "cwd": str(case.stream), "role": "coordinator", "intent": "old-intent", "phase": phase, "operation": operation}
    data["session_start"] = start
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return start


class StaleOpeningRotationTests(CoordinatorReuseTests):
    def test_dead_opening_does_not_block_rotate_or_replay(self):
        self.checkpoint()
        original = seed_start(self)
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"))
        saved = self.state(self.stream)
        self.assertNotIn("session_start", saved)
        self.assertEqual(saved["session_start_residues"][0]["start"], original)
        self.assertFalse(any(path == "/api/sessions/dead/prompt" for _, path, _, _ in self.stub.requests))

    def test_registered_aborted_opening_does_not_block_rotate(self):
        self.checkpoint()
        seed_start(self, "current")
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"))


class StaleOpeningAdoptionTests(RetiredNativeResidueTests):
    def test_dead_opening_does_not_block_archive_and_adopt(self):
        original = seed_start(self)
        self.adopt()
        self.assertEqual(self.state(self.stream)["session_start_residues"][0]["start"], original)
        self.add_pending_event()
        ticked = self.tick("2026-11-03T00:01:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/retired/archive", "/api/sessions/successor/prompt"])

    def test_tick_reconciles_retired_opening_and_dispatches(self):
        self.adopt()
        seed_start(self, "retired")
        self.add_pending_event()
        ticked = self.tick("2026-11-03T00:01:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertNotIn("session_start", self.state(self.stream))
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/retired/archive", "/api/sessions/successor/prompt"])
