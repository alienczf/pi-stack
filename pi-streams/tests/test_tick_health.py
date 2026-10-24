from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from tick_support import TickCase, PROMPTS, info, reply, row, status
from support import ROOT

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, artifacts, doctor, piweb, tick
from engine.project import git


class TickHealthTests(TickCase):
    def setUp(self):
        super().setUp()
        self.a = self.make_stream(self.home, "a", row("coi-a", "coordinator", str(self.home / "a")) + row("worker-a", "worker", str(self.fx.alpha_wt), branch="feat-a"))
        self.b = self.make_stream(self.home, "b", row("coi-b", "coordinator", str(self.home / "b")))
        for sid, cwd in [("coi-a", self.a), ("coi-b", self.b), ("worker-a", self.fx.alpha_wt)]:
            self.write_log(sid, str(cwd), reply("Prior completed authorized work."))
        self.stub.reflect_control_goals = True
        self.routes()

    def routes(self, failed_worker=False):
        routes = [PROMPTS, ("GET", "/api/sessions", 200, [info("coi-a", str(self.a), self.log_path("coi-a")), info("coi-b", str(self.b), self.log_path("coi-b")), info("worker-a", str(self.fx.alpha_wt), self.log_path("worker-a"))])]
        for sid, stream in [("coi-a", self.a), ("coi-b", self.b)]:
            body = status(sid); body["controlGoalSupport"] = "preserve-ask-v1"
            routes += [("GET", f"/api/sessions/{sid}/status", 200, body), ("POST", f"/api/sessions/{sid}/control-goal", 200, {"state": "queued"}), ("POST", f"/api/sessions/{sid}/automatic-admission", 200, {**self.stub.automatic_admissions[sid]})]
        routes.append(("GET", "/api/sessions/worker-a/status", 503 if failed_worker else 200, {"error": "Labelled unavailable worker observation"} if failed_worker else status("worker-a", streaming=True)))
        self.stub.set_routes(routes)

    def test_unavailable_worker_does_not_skip_own_or_other_stream_goal_and_every_log_still_rotates(self):
        for name in ["a", "b"]:
            enabled = self.run_streams("drive", name, "on")
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
        with mock.patch.dict(os.environ, self.env, clear=True):
            for stream in [self.a, self.b]:
                for number in range(31):
                    artifacts.append_log(stream, "2026-10-06T10:00:00Z", f"private fixture {number}", "Labelled isolated prior fixture fact.", request_id=f"health-fixture-{number}")
        self.routes(failed_worker=True)
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 1)
        posts = [request[1] for request in self.stub.requests if request[0] == "POST" and request[1].endswith("/control-goal")]
        self.assertEqual(posts, ["/api/sessions/coi-a/control-goal", "/api/sessions/coi-b/control-goal"])
        for stream in [self.a, self.b]:
            self.assertEqual(len(self.state(stream)["state_log"]["entries"]), 30)
        report = json.loads((self.index / "tick-health.json").read_text())
        self.assertFalse(report["ok"])
        self.assertFalse(report["streams"][str(self.a)]["ok"])
        self.assertTrue(report["streams"][str(self.b)]["ok"])
        with mock.patch.dict(os.environ, self.env, clear=True):
            findings = doctor.check_tick()
        self.assertTrue(any(finding.level == "FAIL" for finding in findings), findings)

    def test_native_io_holds_neither_the_index_writer_lock_nor_another_stream_lock(self):
        original = piweb.session_status
        checked = False
        def boundary(sid):
            nonlocal checked
            if not checked:
                checked = True
                with open(self.index / ".pi-streams.lock", "a") as handle:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        self.fail("Native I/O still owns the index registration/writer lock")
                with open(self.b / ".git/pi-streams.lock", "a") as handle:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        self.fail("Native I/O still owns an unrelated stream writer lock")
            return original(sid)
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(piweb, "session_status", side_effect=boundary):
            result = tick.tick_index(self.index, tick.clock.parse("2026-10-06T12:00:00Z"))
        self.assertTrue(checked)
        self.assertTrue(result)

    def test_a_fresh_stream_state_file_without_a_completed_pass_cannot_certify_tick_health(self):
        (self.b / "log").mkdir()
        (self.b / "log/tick-state.json").write_text("{}\n")
        with mock.patch.dict(os.environ, self.env, clear=True):
            findings = doctor.check_tick()
        self.assertTrue(findings, "One fresh state file is not a completed whole tick pass")
        self.assertTrue(all(finding.level in ["WARN", "FAIL"] for finding in findings))

    def test_owned_tick_lease_refuses_a_second_pass_before_any_native_request(self):
        from engine.tickhealth import tick_lease
        self.stub.requests.clear()
        with tick_lease(self.index):
            result = self.run_streams("tick")
        self.assertEqual(result.returncode, 1)
        self.assertIn("another tick pass owns", result.stderr)
        self.assertEqual(self.stub.requests, [])

    def test_health_fifo_is_refused_without_reading_or_repairing_it(self):
        os.mkfifo(self.index / "tick-health.json")
        with mock.patch.dict(os.environ, self.env, clear=True):
            findings = doctor.check_tick()
        self.assertTrue(any(finding.level == "FAIL" and "regular" in finding.detail for finding in findings))
        self.assertTrue((self.index / "tick-health.json").is_fifo())

    def test_git_boundary_timeout_is_reported_without_claiming_effects_were_rolled_back(self):
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch("engine.project.subprocess.run", side_effect=subprocess.TimeoutExpired("labelled private git timeout", 1)):
            with self.assertRaisesRegex(StreamsError, "timed out.*reconcile"):
                git(self.a, "status", "--porcelain")

    def test_native_boundary_timeout_is_reported_as_an_engine_error_not_a_hung_writer(self):
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(piweb.subprocess, "run", side_effect=subprocess.TimeoutExpired("labelled private adapter timeout", 1)):
            with self.assertRaisesRegex(StreamsError, "timed out|timeout"):
                piweb.list_sessions(str(self.a))
