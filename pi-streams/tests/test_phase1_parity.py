from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

import test_dcr as dcr_cases
import test_drive as drive_cases
import test_thread_spawn as spawn_cases
from support import EngineCase, seed_ratified_stream
from tick_support import HEADER, TickCase, info, reply, row, status, user


class SpawnParityTests(EngineCase):
    def setUp(self):
        super().setUp()
        result = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.stream_dir = (self.home / "etl").resolve()
        self.stream_dir.mkdir(parents=True)
        seed_ratified_stream(self.stream_dir, self.root.name)
        (self.stream_dir / "threads.tsv").write_text(HEADER)
        self.register_stream("etl", self.stream_dir)
        self.stub.requests.clear()

    spawn_datapull = spawn_cases.SpawnTests.spawn_datapull

    def test_spawn_without_ratification(self):
        state = self.stream_dir / "STATE.md"
        state.write_text("\n".join(line for line in state.read_text().splitlines() if not line.startswith("ratified:")) + "\n")
        worktree = (self.root / ".worktrees/alpha/etl-datapull").resolve()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "thread-1", "cwd": str(worktree)}),
            ("GET", "/api/sessions/thread-1/status", 200, spawn_cases.status_body("thread-1")),
            ("POST", "/api/sessions/thread-1/prompt", 200, {"accepted": True}),
        ])
        result = self.spawn_datapull()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "thread-1\n")
        self.assertEqual((worktree / ".stream").read_text(), str(self.stream_dir) + "\n")


class DriveParityTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, "etl", row("coord", "coordinator", str(self.home / "etl")))
        self.write_log("coord", str(self.stream), reply("Previous authorized work finished."))
        self.stub.reflect_control_goals = True
        self.goal = "<the single human-authorized outcome>"
        self.routes()

    routes = drive_cases.DriveTests.routes
    enable = drive_cases.DriveTests.enable
    drive = drive_cases.DriveTests.drive
    goal_posts = drive_cases.DriveTests.goal_posts

    def legacy_off(self):
        self.stub.simulate_conditional_controls = True
        self.stub.automatic_admissions["coord"].update(allowed=False, generation="silent-off")
        data = {}
        data["drive"] = {"enabled": False, "run_id": "retained-run", "remote_state": "off-confirmed", "remote_generation": "silent-off"}
        (self.stream / "log").mkdir(exist_ok=True)
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))

    def test_tick_heals_exact_silent_off_once(self):
        self.legacy_off()
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.drive()["enabled"], self.drive()["run_id"]), (True, "retained-run"))
        self.assertEqual(self.goal_posts()[0][3]["text"], f"/poteto-mode {self.goal}")
        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.stub.automatic_admissions["coord"]["generation"], "silent-off-next")
        self.assertEqual([item for item in self.stub.requests if item[1].endswith("/automatic-admission")], [])

    def test_tick_preserves_newer_receiving_stop(self):
        self.legacy_off()
        self.stub.automatic_admissions["coord"]["generation"] = "newer-stop"
        before = (self.stream / "STATE.md").read_bytes()
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("superseded", result.stderr)
        self.assertEqual(self.drive()["enabled"], False)
        self.assertEqual(self.stub.automatic_admissions["coord"]["generation"], "newer-stop")
        self.assertEqual(self.goal_posts(), [])
        self.assertEqual((self.stream / "STATE.md").read_bytes(), before)

    def test_deliberate_off_never_observes_or_rearms(self):
        self.stub.simulate_conditional_controls = True
        self.enable()
        stopped = self.run_streams("drive", "etl", "off")
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        self.assertEqual(self.drive().get("stop_intent"), "operator-off")
        self.stub.set_routes([("GET", "/api/sessions", 503, {"error": "must not observe a deliberately stopped stream"})])
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.drive()["enabled"], False)
        self.assertEqual(self.stub.requests, [])


class DumpParityTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(self.home, "etl", row("coord", "coordinator", str(self.home / "etl")))
        self.write_log("coord", str(self.stream), reply("Earlier completed work."))

    operation = dcr_cases.DcrTests.operation
    routes = dcr_cases.DcrTests.routes
    start = dcr_cases.DcrTests.start
    ready = dcr_cases.DcrTests.ready
    backend = dcr_cases.DcrTests.backend

    def compacting(self):
        operation = self.ready(self.start())
        native = self.backend(operation)
        self.routes(streaming=False, leaf="e2", operation=operation, native=native)
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.operation()["phase"], "compacting")
        return self.operation(), native

    def test_validated_dump_survives_compaction_failure(self):
        operation, native = self.compacting()
        dumps = self.state(self.stream).get("dcr_dumps", {})
        self.assertIn("coord", dumps, "A validated dump must exist before compaction can fail")
        saved = copy.deepcopy(dumps["coord"])
        self.assertEqual(base64.b64decode(saved["ready_source"]), (self.stream / "STATE.md").read_bytes())
        self.assertEqual(saved["checkpoint_entry"], "e2")
        self.assertEqual(saved["checkpoint_sha256"], hashlib.sha256(Path(self.log_path("coord")).read_bytes().splitlines(keepends=True)[-1]).hexdigest())
        native.update(state="uncertain", detail="Labelled unconfirmed native outcome")
        self.routes(streaming=False, leaf="e2", operation=operation, native=native)
        failed = self.tick("2026-10-06T12:06:00Z")
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(self.operation()["phase"], "blocked")
        self.assertEqual(self.state(self.stream)["dcr_dumps"]["coord"], saved)
        self.assertFalse(any(item[0] == "POST" and item[1].endswith(("/resume", "/archive")) for item in self.stub.requests))

    def test_changed_state_after_ready_does_not_publish_validated_dump(self):
        operation = self.ready(self.start())
        goal = self.tmp / "new-goal.txt"
        goal.write_text("A newer authorized objective.")
        changed = self.run_streams("state", "objective", "etl", "--body-file", str(goal))
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.routes(streaming=False, leaf="e2", operation=operation)
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.operation()["phase"], "superseded")
        self.assertEqual(self.state(self.stream).get("dcr_dumps", {}), {})

    def test_stop_after_validated_dump_keeps_dump_without_resume(self):
        operation, native = self.compacting()
        saved = self.state(self.stream).get("dcr_dumps", {}).get("coord")
        self.assertIsNotNone(saved, "The completed SYNC boundary must already be retained")
        self.stub.automatic_admissions["coord"].update(allowed=False, generation="human-stop")
        native.update(state="superseded", cancelledByStop=True, detail="Explicit stop/cancel superseded maintenance")
        self.routes(streaming=False, leaf="e2", operation=operation, native=native)
        result = self.tick("2026-10-06T12:06:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.operation()["phase"], "superseded")
        self.assertEqual(self.state(self.stream)["dcr_dumps"]["coord"], saved)
        self.assertEqual(self.stub.automatic_admissions["coord"]["allowed"], False)
        self.assertFalse(any(item[0] == "POST" and item[1].endswith(("/resume", "/archive", "/prompt")) for item in self.stub.requests))
