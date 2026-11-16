"""Saved openings cannot fence unrelated lifecycle work after their owner retires."""
from __future__ import annotations

import json
import os
import sys
from unittest import mock

from support import ROOT

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, threads
from test_thread_spawn import SpawnTests, status_body
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
    def test_missing_opening_is_retained_once_without_native_mutation(self):
        original = seed_start(self)
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(threads.reconcile_start(self.stream), "missing")
            self.assertEqual(threads.reconcile_start(self.stream), "absent")
        self.assertEqual(self.state(self.stream)["session_start_residues"], [{"start": original, "disposition": "missing"}])
        self.assertEqual(self.posts(), [])

    def test_dead_rotation_opening_does_not_keep_its_pending_slot(self):
        original = seed_start(self, operation="rotation:dead")
        path = self.stream / "log/tick-state.json"
        data = json.loads(path.read_text())
        data["coordinator_rotation"] = {"phase": "archived", "owner": "rotation:dead"}
        path.write_text(json.dumps(data))
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(threads.reconcile_start(self.stream, supersede=True), "missing")
        self.assertNotIn("session_start", self.state(self.stream))
        self.assertEqual(self.state(self.stream)["session_start_residues"][0]["start"], original)
        self.assertEqual(self.posts(), [])

    def test_owned_uncertain_rotation_opening_remains_a_no_replay_fence(self):
        original = seed_start(self, "successor", operation="rotation:owned")
        path = self.stream / "log/tick-state.json"
        data = json.loads(path.read_text())
        data["coordinator_rotation"] = {"phase": "archived", "owner": "rotation:owned"}
        path.write_text(json.dumps(data))
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(threads.reconcile_start(self.stream, supersede=True), "owned")
        self.assertEqual(self.state(self.stream)["session_start"], original)
        self.assertEqual(self.posts(), [])

    def test_dead_opening_does_not_block_archive_and_adopt(self):
        original = seed_start(self)
        self.adopt()
        self.assertEqual(self.state(self.stream)["session_start_residues"][0]["start"], original)
        self.add_pending_event()
        ticked = self.tick("2026-11-03T00:01:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/retired/archive", "/api/sessions/successor/prompt"])

    def test_saved_opening_does_not_block_explicit_replace(self):
        table = self.stream / "threads.tsv"
        table.write_text(table.read_text().replace("\tarchived\t", "\tactive\t"))
        seed_start(self, "retired")
        self.infos[0].update(archivePath=self.log_path("retired"), archivedAt="2026-11-03T00:00:00Z")
        result = self.run_streams("replace", "etl", "--coordinator-session", "successor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"))
        self.assertNotIn("session_start", self.state(self.stream))
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/retired/archive"])

    def test_failed_native_observation_keeps_pending_evidence(self):
        original = seed_start(self)
        with mock.patch.dict(os.environ, self.env, clear=True):
            with mock.patch.object(threads.piweb, "list_sessions", side_effect=StreamsError("temporary listing failure")):
                self.assertEqual(threads.reconcile_start(self.stream), "deferred")
        self.assertEqual(self.state(self.stream)["session_start"], original)

    def test_live_unregistered_uncertain_opening_is_not_automatically_replayed(self):
        seed_start(self, "successor")
        result = self.run_streams("new", "etl")
        self.assertEqual(result.returncode, 1)
        self.assertIn("session start is pending", result.stderr)
        self.assertEqual(self.posts(), [])
        self.assertEqual(self.state(self.stream)["session_start"]["phase"], "sending")

    def test_exact_explicit_adoption_does_not_replay_uncertain_opening(self):
        original = seed_start(self, "successor")
        result = self.run_streams("new", "etl", "--coordinator-session", "successor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"))
        self.assertEqual(self.posts(), [])
        self.assertEqual(self.state(self.stream)["session_start_residues"][0]["start"], original)

    def test_tick_reconciles_retired_opening_and_dispatches(self):
        self.adopt()
        seed_start(self, "retired")
        self.add_pending_event()
        ticked = self.tick("2026-11-03T00:01:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertNotIn("session_start", self.state(self.stream))
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/retired/archive", "/api/sessions/successor/prompt"])


class StaleOpeningWorkerTests(SpawnTests):
    def test_worker_spawn_is_not_blocked_by_dead_coordinator_opening(self):
        self.stream = self.stream_dir
        original = seed_start(self)
        worktree = (self.root / ".worktrees" / "alpha" / "etl-datapull").resolve()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "thread-1", "cwd": str(worktree)}),
            ("GET", "/api/sessions/thread-1/status", 200, status_body("thread-1")),
            ("POST", "/api/sessions/thread-1/prompt", 200, {"accepted": True}),
        ])
        spawned = self.spawn_datapull()
        self.assertEqual(spawned.returncode, 0, spawned.stderr)
        self.assertEqual(spawned.stdout, "thread-1\n")
        data = json.loads((self.stream / "log/tick-state.json").read_text())
        self.assertNotIn("session_start", data)
        self.assertEqual(data["session_start_residues"][0]["start"], original)
        self.assertEqual([path for method, path, _, _ in self.stub.requests if method == "POST" and path.endswith("/prompt")], ["/api/sessions/thread-1/prompt"])


def load_tests(loader, _tests, _pattern):
    import unittest

    suite = unittest.TestSuite()
    for case in (StaleOpeningRotationTests, StaleOpeningAdoptionTests, StaleOpeningWorkerTests):
        suite.addTests(case(name) for name in case.__dict__ if name.startswith("test_"))
    return suite
