from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

import test_phase1_parity as parity
import test_failure_recovery as recovery_cases
from tick_support import TickCase, reply, user


class CapacityFixture(TickCase):
    fixture = parity.CapacityLoadParityTests.fixture
    compact = parity.CapacityLoadParityTests.compact
    archive = parity.CapacityLoadParityTests.archive
    advance = parity.CapacityLoadParityTests.advance
    rotate = parity.CapacityLoadParityTests.rotate
    load_acknowledgement = parity.CapacityLoadParityTests.load_acknowledgement


class HistoricalDumpTests(CapacityFixture):
    def later_sync(self, role="research"):
        self.fixture(role)
        self.native.update(state="resumed", compactionEntryId="compact-old", compactionSha256="a" * 64,
                           resume={"state": "admitted"})
        data = self.state(self.stream)
        old = data["dcr_operations"]["source"]
        old.update(phase="complete", completed_leaf="marker")
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))
        self.native_status["contextUsage"] = {"tokens": 170000}
        self.stub.automatic_admissions["source"]["generation"] = "later-generation"
        self.append("bounded-user", "marker", user("A completed later bounded assignment."))
        self.append("bounded-stop", "bounded-user", reply("Bounded work complete."))
        self.native_status["rotationSafety"]["entryId"] = "bounded-stop"
        self.tick_ok()
        self.op = copy.deepcopy(self.state(self.stream)["dcr_operations"]["source"])
        self.assertNotEqual(self.op["id"], self.dump["id"])
        self.assertEqual(self.op["phase"], "sync-admitted")
        self.append("later-sync", "bounded-stop", user(self.op["sync_text"]))
        self.append("later-stop", "later-sync", reply("Finished without calling ready."))
        self.native_status["rotationSafety"]["entryId"] = "later-stop"
        before = (self.stream / "STATE.md").read_bytes()
        (self.stream / "STATE.md").write_bytes(before.replace(b"<the single human-authorized outcome>", b"The newer authorized bounded objective"))
        self.current = (self.stream / "STATE.md").read_bytes()
        self.original = Path(self.log_path("source")).read_bytes()

    def append(self, identity, parent, message):
        with Path(self.log_path("source")).open("a") as handle:
            handle.write(json.dumps({"type": "message", "id": identity, "parentId": parent, "message": message}) + "\n")

    def tick_ok(self):
        result = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)

    def archive(self, body):
        expected = "later-stop" if hasattr(self, "current") else "marker"
        self.assertEqual(body["expectedIdle"]["entryId"], expected)
        archive = self.tmp / "source-archive.jsonl"
        archive.write_bytes(Path(self.log_path("source")).read_bytes())
        self.source_info.update(archived=True, archivePath=str(archive), archivedAt="2026-10-06T12:11:00Z")
        return 200, {"archived": True, "automaticAdmission": {**self.stub.automatic_admissions["source"], "allowed": False}}

    def test_later_idle_sync_uses_separately_bound_prior_dump(self):
        self.later_sync()
        self.tick_ok()
        data = self.state(self.stream)
        self.assertIn("coordinator_replacement", data, "P1 later idle SYNC must select its prior validated dump")
        intent = data["coordinator_replacement"]
        recovery = data["dcr_historical_recoveries"]["source"]
        self.assertEqual(recovery["stalled_operation"], self.op["id"])
        self.assertEqual(recovery["dump"], self.dump)
        self.assertEqual(recovery["automatic"]["generation"], "later-generation")
        self.assertEqual(recovery["retirement"]["entryId"], "later-stop")
        self.assertEqual(data["dcr_operations"]["source"], self.op)
        self.assertEqual(data["dcr_dumps"]["source"], self.dump)
        handoff = json.loads((self.stream / intent["handoff"]["path"]).read_text())
        self.assertEqual(handoff["checkpoint"]["operation"], self.dump["id"])
        self.assertEqual(handoff["role"], "research")
        self.assertEqual(handoff["assignment"], "Verify only the bounded alpha assignment.")
        self.assertEqual((self.stream / handoff["syncedState"]["path"]).read_bytes(), base64.b64decode(self.dump["ready_source"]))
        self.assertEqual((self.stream / handoff["currentState"]["path"]).read_bytes(), self.current)
        self.assertEqual(Path(handoff["archive"]["archivePath"]).read_bytes(), self.original)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), self.current)
        self.assertIn("healthy\tcoordinator", self.rows(self.stream))
        self.load_acknowledgement(intent)

    def test_historical_recovery_reconciles_archive_without_replaying_retirement(self):
        self.later_sync("coordinator")
        calls = []

        def lost_receipt(body):
            calls.append(body)
            self.archive(body)
            return 503, {"error": "Labelled lost archive receipt after durable retirement"}

        self.routes = [(method, path, code, lost_receipt if method == "POST" and path == "/api/sessions/source/archive" else body)
                       for method, path, code, body in self.routes]
        self.stub.set_routes(self.routes)
        self.tick_ok()
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["phase"], "archiving")
        self.tick_ok()
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["phase"], "complete")
        self.assertEqual(len(calls), 1)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), self.current)

    def test_corrupt_historical_dump_cannot_retire_the_current_session(self):
        self.later_sync()
        for key in ("ready_revision", "checkpoint_sha256"):
            with self.subTest(key=key):
                data = self.state(self.stream)
                data["dcr_dumps"]["source"] = {**self.dump, key: "0" * 64}
                (self.stream / "log/tick-state.json").write_text(json.dumps(data))
                self.tick_ok()
                data = self.state(self.stream)
                self.assertNotIn("coordinator_replacement", data)
                self.assertEqual(data["dcr_operations"]["source"], self.op)
                self.assertEqual((self.stream / "STATE.md").read_bytes(), self.current)
                self.assertFalse(any(item[0] == "POST" and item[1].endswith("/archive") for item in self.stub.requests))

    def test_later_sync_busy_unknown_callbacks_and_pending_input_stay_fenced(self):
        self.later_sync()
        variants = [{"isStreaming": True}, {"pendingMessageCount": 1}, {"pendingAsk": {"askId": "retain"}},
                    {"rotationSafety": {**self.native_status["rotationSafety"], "callbacksKnown": False}}]
        for change in variants:
            with self.subTest(change=change):
                before = copy.deepcopy(self.native_status)
                self.native_status.update(change)
                self.tick_ok()
                self.assertNotIn("coordinator_replacement", self.state(self.stream))
                self.native_status.clear()
                self.native_status.update(before)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), self.current)


class MissingLoadAckTests(CapacityFixture):
    def finish_without_ack(self, intent):
        identity = intent["load"]["delivery"]
        control = self.stub.control_goals[identity]
        prefix = control["text"][:-len("/poteto-mode " + control["potetoGoal"])]
        self.write_log("successor", str(self.cwd), user(prefix + '<skill name="poteto-mode" location="/offline/skill.md">\nControlled fixture.\n</skill>\n\n' + control["potetoGoal"]), reply("I did not load the checkpoint."))
        self.successor_status["rotationSafety"]["entryId"] = "e2"
        self.successor_status["messageCount"] = 2
        control["state"] = "ended"

    def test_missing_exact_ack_is_blocked_with_evidence_and_lane_local_ownership(self):
        intent = self.rotate("research")
        self.finish_without_ack(intent)
        self.advance()
        blocked = self.state(self.stream)["coordinator_replacement"]["load"]
        self.assertEqual(blocked["state"], "blocked", "P2 a terminal load missing exact ack cannot remain pending")
        self.assertEqual((blocked["userEntryId"], blocked["assistantEntryId"]), ("e1", "e2"))
        self.assertEqual(blocked["assistantSha256"], hashlib.sha256(Path(self.log_path("successor")).read_bytes().splitlines(keepends=True)[-1]).hexdigest())
        self.successor_status["contextUsage"] = {"tokens": 200000}
        self.stub.requests.clear()
        for _ in range(3):
            result = self.tick("2026-10-06T12:15:00Z")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(any(item[0] == "GET" and item[1] == "/api/sessions/healthy/status" for item in self.stub.requests), "healthy coordinator observation must not be starved")
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"], blocked)
        self.assertFalse(any(item[0] == "POST" and item[1].startswith("/api/sessions/successor/") for item in self.stub.requests))
        self.assertNotIn("successor", self.state(self.stream).get("dcr_operations", {}))

    def test_second_replacement_cannot_demote_pending_worker_load_before_ack(self):
        intent = self.rotate("research")
        for method, path, _, body in self.routes:
            if method == "GET" and path == "/api/sessions/healthy/status":
                body["conditionalAdmissionSupport"] = "generation-cas-v1"
                body["rotationSafety"] = {"entryId": "e1", "callbacksKnown": True, "callbackInventory": "native-and-extension-v1", "nativeChildCallbacks": []}
        self.write_log("another", str(self.stream))
        self.routes[0][3].append({"id": "another", "cwd": str(self.stream), "path": self.log_path("another")})
        other = copy.deepcopy(self.successor_status)
        other["sessionId"] = "another"
        self.routes.append(("GET", "/api/sessions/another/status", 200, other))
        for sid in ("healthy", "another"):
            self.stub.automatic_admissions[sid] = {"sessionId": sid, "cwd": str(self.stream), "generation": "fixture-" + sid, "allowed": True, "durable": True}
        self.stub.set_routes(self.routes)
        denied = self.run_streams("replace", "etl", "--coordinator-session", "another", "--from", "healthy")
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(self.state(self.stream)["coordinator_replacement"], intent, "a second replacement must not strand the pending first load in history")
        self.assertIn("checkpoint load", denied.stderr)
        self.routes[0][3][:] = [item for item in self.routes[0][3] if item.get("id") != "another"]
        self.stub.set_routes(self.routes)
        ticked = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertTrue(any(item[0] == "GET" and item[1] == "/api/sessions/healthy/status" for item in self.stub.requests))
        self.load_acknowledgement(intent)

    def test_completed_worker_loader_error_does_not_abort_coordinator_observation(self):
        intent = self.rotate("research")
        handoff = self.stream / intent["handoff"]["path"]
        handoff.write_text(handoff.read_text() + "changed evidence\n")
        result = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual(result.returncode, 1, "load evidence failure must remain visible")
        self.assertTrue(any(item[0] == "GET" and item[1] == "/api/sessions/healthy/status" for item in self.stub.requests), "a worker loader exception must not abort coordinator observation")
        self.assertNotIn("successor", self.state(self.stream).get("dcr_operations", {}))

    def test_terminal_failed_load_is_blocked_even_when_native_failure_parks_admission(self):
        intent = self.rotate("research")
        self.finish_without_ack(intent)
        path = Path(self.log_path("successor"))
        lines = path.read_text().splitlines()
        failed = json.loads(lines[-1])
        failed["message"].update(stopReason="error", errorMessage="Terminal model error in checkpoint load")
        lines[-1] = json.dumps(failed)
        path.write_text("\n".join(lines) + "\n")
        self.stub.automatic_admissions["successor"].update(allowed=False, generation="native-failure-park")
        self.successor_status["failureBoundary"] = {"sessionId": "successor", "cwd": str(self.cwd), "state": "parked", "failure": {"entryId": "e2"}}
        self.advance()
        load = self.state(self.stream)["coordinator_replacement"]["load"]
        self.assertEqual(load["state"], "blocked")
        self.assertEqual(load["assistantEntryId"], "e2")
        self.assertEqual(load["assistantSha256"], hashlib.sha256(path.read_bytes().splitlines(keepends=True)[-1]).hexdigest())
        self.assertFalse(self.stub.automatic_admissions["successor"]["allowed"])

    def test_pending_worker_load_does_not_starve_healthy_coordinator(self):
        self.rotate("research")
        self.stub.requests.clear()
        result = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(item[0] == "GET" and item[1] == "/api/sessions/healthy/status" for item in self.stub.requests), "P2 postpublication worker ownership is lane-local even before completion")


class FailedLoadRecoveryFenceTests(TickCase):
    fixture = recovery_cases.FailureRecoveryTests.fixture
    seed = recovery_cases.FailureRecoveryTests.seed
    digest = recovery_cases.FailureRecoveryTests.digest
    body = recovery_cases.FailureRecoveryTests.body
    append = recovery_cases.FailureRecoveryTests.append
    fork_response = recovery_cases.FailureRecoveryTests.fork_response

    def unloaded_failure(self):
        self.fixture("research", model="gpt-6.1-sol")
        data = self.state(self.stream)
        data["coordinator_replacement_history"] = [{"id": "prior-load", "mode": "capacity", "target": "coi", "load": {"state": "blocked"}}]
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))
        self.before = copy.deepcopy(self.state(self.stream))
        self.stub.requests.clear()

    def test_direct_failure_advance_cannot_bypass_unloaded_successor_fence(self):
        self.unloaded_failure()
        result = self.run_streams("failure", "advance", "etl", "--session", "coi", "--episode", self.episode["id"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkpoint load", result.stderr)
        self.assertEqual(self.state(self.stream), self.before)
        self.assertEqual(self.stub.requests, [])

    def test_automatic_parked_resume_cannot_create_recovery_for_unloaded_successor(self):
        self.unloaded_failure()
        result = self.tick("2026-10-06T12:20:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("coi", self.state(self.stream).get("failure_recoveries", {}))
        self.assertEqual(self.state(self.stream)["failures"], self.before["failures"])
        self.assertFalse(any(item[0] == "POST" and item[1].startswith("/api/sessions/coi/") for item in self.stub.requests))

    def test_explicit_parked_resume_cannot_bypass_unloaded_successor_fence(self):
        self.unloaded_failure()
        result = self.run_streams("resume", "etl", "--all-parked")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0].get("state"), "load-blocked")
        self.assertEqual(self.state(self.stream), self.before)
        self.assertEqual(self.stub.requests, [])
