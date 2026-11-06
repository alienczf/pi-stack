from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

from test_phase1_parity import CapacityLoadParityTests
from tick_support import reply, user


class HistoricalDumpTests(CapacityLoadParityTests):
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
        return 200, {"archived": True}

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


class MissingLoadAckTests(CapacityLoadParityTests):
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
        self.stub.requests.clear()
        for _ in range(3):
            result = self.tick("2026-10-06T12:15:00Z")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"], blocked)
        reads = [item for item in self.stub.requests if item[0] == "GET" and item[1] == "/api/sessions/healthy/status"]
        self.assertGreaterEqual(len(reads), 3, "healthy coordinator observation must not be starved")
        self.assertFalse(any(item[0] == "POST" and item[1].startswith("/api/sessions/successor/") for item in self.stub.requests))
        self.assertNotIn("successor", self.state(self.stream).get("dcr_operations", {}))

    def test_pending_worker_load_does_not_starve_healthy_coordinator(self):
        self.rotate("research")
        self.stub.requests.clear()
        result = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any(item[0] == "GET" and item[1] == "/api/sessions/healthy/status" for item in self.stub.requests), "P2 postpublication worker ownership is lane-local even before completion")
