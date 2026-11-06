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
        self.assertEqual(result.returncode, 0, "PHASE1_SPAWN_RATIFICATION " + result.stderr)
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
        for method, path, _, body in self.stub.routes:
            if method == "GET" and path == "/api/sessions/coord/status":
                body["rotationSafety"] = {"entryId": "e1"}
        data = {}
        data["drive"] = {"enabled": False, "run_id": "retained-run", "remote_state": "off-confirmed", "remote_generation": "silent-off"}
        (self.stream / "log").mkdir(exist_ok=True)
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))

    def test_tick_heals_exact_silent_off_once(self):
        self.legacy_off()
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.drive()["enabled"], self.drive()["run_id"]), (True, "retained-run"), "PHASE1_DRIVE_SILENT_OFF")
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
        self.assertIn("coord", dumps, "PHASE1_VALIDATED_DUMP must exist before compaction can fail")
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


class CapacityLoadParityTests(TickCase):
    def fixture(self, role):
        self.cwd = self.home / "etl" if role == "coordinator" else self.fx.alpha_wt
        rows = row("source", role, str(self.cwd), branch="feat-a" if role != "coordinator" else "")
        if role != "coordinator":
            rows += row("healthy", "coordinator", str(self.home / "etl"))
        self.stream = self.make_stream(self.home, "etl", rows)
        if role != "coordinator":
            (self.cwd / ".stream").write_text(str(self.stream) + "\n")
        self.write_log("source", str(self.cwd), reply("Completed work retained before SYNC."))
        self.write_log("successor", str(self.cwd))
        self.stub.reflect_control_goals = True
        self.native_status = status("source", tokens=150000)
        self.native_status.update(conditionalAdmissionSupport="generation-cas-v1", rotationSafety={"entryId": "e1", "callbacksKnown": True, "callbackInventory": "native-and-extension-v1", "nativeChildCallbacks": [], "unprovenCallbacks": []}, failureBoundary={"enrollment": {"role": role, "assignment": "Verify only the bounded alpha assignment."}})
        successor = status("successor")
        successor.update(messageCount=0, controlGoalSupport="preserve-ask-v1", recoveryControlSupport="question-safe-v1", conditionalAdmissionSupport="generation-cas-v1", rotationSafety={"entryId": None})
        self.successor_status = successor
        self.stub.automatic_admissions["source"] = {"sessionId": "source", "cwd": str(self.cwd), "generation": "source-generation", "allowed": True, "durable": True}
        self.source_info = info("source", str(self.cwd), self.log_path("source"))
        listing = [self.source_info]
        if role != "coordinator":
            self.write_log("healthy", str(self.stream), reply("The coordinator retains its own role."))
            listing.append(info("healthy", str(self.stream), self.log_path("healthy")))
        self.routes = [
            ("GET", "/api/sessions", 200, listing),
            ("GET", "/api/sessions/source/status", 200, self.native_status),
            ("GET", "/api/sessions/healthy/status", 200, status("healthy")),
            ("GET", "/api/sessions/successor/status", 200, successor),
            ("POST", "/api/sessions/source/prompt", 200, {"accepted": True}),
            ("POST", "/api/sessions/healthy/prompt", 200, {"accepted": True}),
            ("POST", "/api/sessions/source/maintenance/events/watch", 200, lambda body: (200, {"id": body["id"], "entryId": "watch"})),
            ("POST", "/api/sessions", 200, info("successor", str(self.cwd), self.log_path("successor"))),
            ("POST", "/api/sessions/source/archive", 200, self.archive),
            ("POST", "/api/sessions/successor/control-goal", 200, {"state": "queued"}),
        ]
        self.stub.set_routes(self.routes)
        started = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn("source", self.state(self.stream).get("dcr_operations", {}), "Tick must maintain workers as well as coordinators")
        self.op = self.state(self.stream)["dcr_operations"]["source"]
        ready = self.run_streams("dcr", "ready", "etl", "--session", "source", "--operation", self.op["id"])
        self.assertEqual(ready.returncode, 0, ready.stderr)
        self.write_log("source", str(self.cwd), reply("Completed work retained before SYNC."), reply(json.loads(ready.stdout)["acknowledgement"]))
        self.native_status["rotationSafety"]["entryId"] = "e2"
        self.native = {"version": 1, "id": self.op["id"], "sessionId": "source", "cwd": str(self.cwd), "entryId": "e2", "generation": "source-generation", "instructions": self.op["compact_instructions"], "state": "compacting", "inputSequence": 0, "inputs": [], "compactionEntryId": None, "compactionSha256": None, "resume": None, "targetTokens": 150000}
        self.routes += [("POST", "/api/sessions/source/maintenance/compact", 200, self.compact), ("GET", f"/api/sessions/source/maintenance/{self.op['id']}", 200, self.native)]
        self.stub.set_routes(self.routes)
        self.advance()
        self.assertEqual(self.state(self.stream)["dcr_operations"]["source"]["phase"], "compacting")
        self.dump = copy.deepcopy(self.state(self.stream)["dcr_dumps"]["source"])

    def compact(self, body):
        self.assertEqual(body["expectedIdle"]["entryId"], "e2")
        entry = {"type": "custom", "customType": "pi-web.maintenance", "id": "marker", "parentId": "e2", "data": {"id": self.op["id"], "sessionId": "source", "cwd": str(self.cwd), "entryId": "e2", "generation": "source-generation"}}
        with Path(self.log_path("source")).open("a") as handle:
            handle.write(json.dumps(entry) + "\n")
        self.native_status["rotationSafety"]["entryId"] = "marker"
        self.native["markerEntryId"] = "marker"
        return 200, self.native

    def archive(self, body):
        self.assertEqual(body["expectedIdle"]["entryId"], "marker")
        archive = self.tmp / "source-archive.jsonl"
        archive.write_bytes(Path(self.log_path("source")).read_bytes())
        self.source_info.update(archived=True, archivePath=str(archive), archivedAt="2026-10-06T12:06:00Z")
        return 200, {"archived": True, "automaticAdmission": {**self.stub.automatic_admissions["source"], "allowed": False}}

    def advance(self):
        result = self.run_streams("dcr", "advance", "etl", "--session", "source", "--operation", self.op["id"])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def rotate(self, role):
        self.fixture(role)
        self.native.update(state="failed", detail="Labelled expired native compaction lease; writer fenced")
        self.advance()
        data = self.state(self.stream)
        self.assertEqual(data["dcr_operations"]["source"]["phase"], "rotated", data["dcr_operations"]["source"]["detail"])
        intent = data["coordinator_replacement"]
        self.assertEqual((intent["phase"], intent["source"], intent["target"], intent["load"]["state"]), ("complete", "source", "successor", "pending"))
        self.assertEqual(data["dcr_dumps"]["source"], self.dump)
        handoff = json.loads((self.stream / intent["handoff"]["path"]).read_text())
        self.assertEqual((handoff["role"], handoff["cwd"]), (role, str(self.cwd)))
        self.assertEqual((self.stream / handoff["syncedState"]["path"]).read_bytes(), base64.b64decode(self.dump["ready_source"]))
        self.assertEqual(Path(handoff["archive"]["archivePath"]).read_bytes(), Path(self.log_path("source")).read_bytes())
        self.assertIn(f"successor\t{role}\t", self.rows(self.stream))
        return intent

    def load_acknowledgement(self, intent):
        identity = intent["load"]["delivery"]
        control = self.stub.control_goals[identity]
        prefix = control["text"][:-len("/poteto-mode " + control["potetoGoal"])]
        self.write_log("successor", str(self.cwd), user(prefix + '<skill name="poteto-mode" location="/offline/skill.md">\nControlled fixture.\n</skill>\n\n' + control["potetoGoal"]), reply("Dump checkpoint loaded: " + intent["id"]))
        self.successor_status["rotationSafety"]["entryId"] = "e2"
        self.successor_status["messageCount"] = 2
        control["state"] = "ended"
        self.advance()
        loaded = self.state(self.stream)["coordinator_replacement"]["load"]
        self.assertEqual((loaded["state"], loaded["userEntryId"], loaded["assistantEntryId"]), ("observed", "e1", "e2"))
        self.assertEqual(loaded["assistantSha256"], hashlib.sha256(Path(self.log_path("successor")).read_bytes().splitlines(keepends=True)[-1]).hexdigest())
        before = len([item for item in self.stub.requests if item[0] == "POST"])
        self.advance()
        self.assertEqual(len([item for item in self.stub.requests if item[0] == "POST"]), before)

    def test_coordinator_dump_rotate_load(self):
        self.load_acknowledgement(self.rotate("coordinator"))

    def test_worker_dump_rotate_load(self):
        self.load_acknowledgement(self.rotate("research"))
        self.assertIn("healthy\tcoordinator", self.rows(self.stream))

    def test_newer_native_input_fences_dump_rotation(self):
        self.fixture("research")
        before = self.rows(self.stream)
        self.native.update(state="failed", detail="Labelled expired compaction")
        with Path(self.log_path("source")).open("a") as handle:
            handle.write(json.dumps({"type": "message", "id": "new-input", "parentId": "marker", "message": user("New human input must remain retained.")}) + "\n")
        self.native_status["rotationSafety"]["entryId"] = "new-input"
        self.stub.requests.clear()
        self.advance()
        data = self.state(self.stream)
        self.assertEqual(data["dcr_operations"]["source"]["phase"], "blocked")
        self.assertIn("newer native input", data["dcr_operations"]["source"]["detail"])
        self.assertEqual(self.rows(self.stream), before)
        self.assertEqual(data["dcr_dumps"]["source"], self.dump)
        self.assertFalse(any(item[0] == "POST" and item[1].endswith("/archive") for item in self.stub.requests))

    def test_corrupted_saved_dump_never_authorizes_retirement(self):
        self.fixture("coordinator")
        data = self.state(self.stream)
        data["dcr_operations"]["source"]["ready_revision"] = "0" * 64
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))
        self.native.update(state="failed", detail="Labelled expired compaction")
        self.stub.requests.clear()
        self.advance()
        self.assertEqual(self.state(self.stream)["dcr_operations"]["source"]["phase"], "blocked")
        self.assertEqual(self.state(self.stream)["dcr_dumps"]["source"], self.dump)
        self.assertIn("source\tcoordinator", self.rows(self.stream))
        self.assertFalse(any(item[0] == "POST" and item[1].endswith("/archive") for item in self.stub.requests))

    def test_successor_stop_preserves_dump_without_load_replay(self):
        intent = self.rotate("research")
        identity = intent["load"]["delivery"]
        self.stub.automatic_admissions["successor"].update(allowed=False, generation="successor-human-stop")
        self.stub.control_goals[identity]["state"] = "superseded"
        self.stub.requests.clear()
        self.advance()
        data = self.state(self.stream)
        self.assertEqual(data["coordinator_replacement"]["load"]["state"], "superseded")
        self.assertEqual(data["dcr_dumps"]["source"], self.dump)
        self.assertEqual(self.stub.automatic_admissions["successor"]["allowed"], False)
        self.assertEqual([item for item in self.stub.requests if item[0] == "POST"], [])
