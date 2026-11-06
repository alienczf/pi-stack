from __future__ import annotations

import copy
import json
from pathlib import Path

import test_phase2_review as previous

CapacityFixture = previous.CapacityFixture
from tick_support import reply, user


class IncompleteReadyTests(CapacityFixture):
    later_sync = previous.HistoricalDumpTests.later_sync
    append = previous.HistoricalDumpTests.append
    tick_ok = previous.HistoricalDumpTests.tick_ok
    archive = previous.HistoricalDumpTests.archive

    def incomplete_ready(self, *, blocked=False):
        self.later_sync()
        result = self.run_streams("dcr", "ready", "etl", "--session", "source", "--operation", self.op["id"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.op = copy.deepcopy(self.state(self.stream)["dcr_operations"]["source"])
        self.assertNotEqual(self.op["ready_revision"], "")
        self.assertEqual(self.op["checkpoint_entry"], "")
        if blocked:
            self.op.update(phase="blocked", detail="DCR has no complete native SYNC acknowledgement at its exact idle leaf")
            data = self.state(self.stream)
            data["dcr_operations"]["source"] = self.op
            (self.stream / "log/tick-state.json").write_text(json.dumps(data))

    def recover_ready(self, *, blocked=False):
        self.incomplete_ready(blocked=blocked)
        self.tick_ok()
        data = self.state(self.stream)
        self.assertIn("coordinator_replacement", data, "READY_WITHOUT_ACK must select the previous validated dump")
        self.assertEqual(data["dcr_historical_recoveries"]["source"]["dump"], self.dump)
        self.assertEqual(data["dcr_dumps"]["source"], self.dump)
        self.assertEqual(data["dcr_operations"]["source"], self.op)
        self.assertEqual((self.stream / "STATE.md").read_bytes(), self.current)
        self.load_acknowledgement(data["coordinator_replacement"])

    def test_ready_without_final_ack_selects_previous_dump(self):
        self.recover_ready()

    def test_preexisting_blocked_ready_without_ack_selects_previous_dump(self):
        self.recover_ready(blocked=True)

    def test_ready_without_ack_and_no_prior_dump_stays_fenced(self):
        self.incomplete_ready()
        data = self.state(self.stream)
        del data["dcr_dumps"]["source"]
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))
        self.tick_ok()
        self.tick_ok()
        data = self.state(self.stream)
        self.assertEqual(data["dcr_operations"]["source"]["phase"], "blocked")
        self.assertNotIn("coordinator_replacement", data)
        self.assertEqual(data["dcr_dumps"], {})

    def test_exact_current_ack_uses_normal_compaction_not_historical_dump(self):
        self.incomplete_ready()
        path = Path(self.log_path("source"))
        lines = path.read_text().splitlines()
        entry = json.loads(lines[-1])
        entry["message"] = reply(f"DCR SYNC ready: {self.op['id']} {self.op['ready_revision']}")
        lines[-1] = json.dumps(entry)
        path.write_text("\n".join(lines) + "\n")
        self.routes = [(method, route, 503, {"error": "Labelled refusal at the normal compact boundary"})
                       if route == "/api/sessions/source/maintenance/compact" else (method, route, code, body)
                       for method, route, code, body in self.routes]
        self.stub.set_routes(self.routes)
        self.stub.requests.clear()
        self.tick_ok()
        data = self.state(self.stream)
        self.assertEqual(data["dcr_dumps"]["source"]["id"], self.op["id"])
        self.assertEqual(data["dcr_operations"]["source"]["checkpoint_entry"], "later-stop")
        self.assertNotIn("dcr_historical_recoveries", data)
        self.assertNotIn("coordinator_replacement", data)
        compacts = [body for method, route, _, body in self.stub.requests if method == "POST" and route.endswith("/compact")]
        self.assertEqual(len(compacts), 1)
        self.assertEqual(compacts[0]["expectedIdle"]["entryId"], "later-stop")

    def test_ready_without_ack_preserves_state_and_native_safety_fences(self):
        self.incomplete_ready(blocked=True)
        baseline = copy.deepcopy(self.state(self.stream))
        status = copy.deepcopy(self.native_status)
        variants = [
            {"isStreaming": True}, {"isCompacting": True}, {"isBashRunning": True},
            {"pendingMessageCount": 1}, {"pendingAsk": {"askId": "retain"}},
            {"rotationSafety": {**status["rotationSafety"], "callbacksKnown": False}},
            {"rotationSafety": {**status["rotationSafety"], "nativeChildCallbacks": ["retain"]}},
            {"maintenanceSupport": "unsupported"},
        ]
        for change in variants:
            with self.subTest(change=change):
                self.native_status.update(change)
                (self.stream / "log/tick-state.json").write_text(json.dumps(baseline))
                self.stub.requests.clear()
                self.tick_ok()
                data = self.state(self.stream)
                self.assertEqual(data["dcr_operations"]["source"], self.op)
                self.assertEqual(data["dcr_dumps"]["source"], self.dump)
                self.assertNotIn("coordinator_replacement", data)
                self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])
                self.native_status.clear()
                self.native_status.update(copy.deepcopy(status))
        self.assertEqual((self.stream / "STATE.md").read_bytes(), self.current)

    def test_checkpoint_or_admitted_maintenance_cannot_use_incomplete_sync_fallback(self):
        self.incomplete_ready(blocked=True)
        baseline = copy.deepcopy(self.state(self.stream))
        for change in ({"checkpoint_entry": "later-stop"}, {"checkpoint_sha256": "a" * 64},
                       {"compaction_entry": "already-admitted"}, {"compaction_sha256": "a" * 64},
                       {"resume_text": "Already admitted"}, {"resume_goal": "Already admitted"}):
            with self.subTest(change=change):
                data = copy.deepcopy(baseline)
                data["dcr_operations"]["source"].update(change)
                (self.stream / "log/tick-state.json").write_text(json.dumps(data))
                self.stub.requests.clear()
                self.tick_ok()
                data = self.state(self.stream)
                self.assertNotIn("coordinator_replacement", data)
                self.assertEqual(data["dcr_dumps"]["source"], self.dump)
                self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_ready_with_corrupt_dump_or_hash_cannot_retire_source(self):
        self.incomplete_ready(blocked=True)
        for key in ("ready_revision", "checkpoint_sha256"):
            with self.subTest(key=key):
                data = self.state(self.stream)
                data["dcr_dumps"]["source"] = {**self.dump, key: "0" * 64}
                (self.stream / "log/tick-state.json").write_text(json.dumps(data))
                self.stub.requests.clear()
                self.tick_ok()
                data = self.state(self.stream)
                self.assertEqual(data["dcr_operations"]["source"], self.op)
                self.assertNotIn("coordinator_replacement", data)
                self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_newer_user_or_malformed_watcher_cannot_select_prior_dump(self):
        self.incomplete_ready(blocked=True)
        path = Path(self.log_path("source"))
        original = path.read_bytes()
        for newer in (
            {"type": "message", "message": user("A newer human instruction.")},
            {"type": "custom", "customType": "pi-web.stream-failure", "data": {"version": 1}},
        ):
            with self.subTest(newer=newer):
                path.write_bytes(original + (json.dumps({**newer, "id": "newer", "parentId": "later-stop"}) + "\n").encode())
                self.native_status["rotationSafety"]["entryId"] = "newer"
                self.stub.requests.clear()
                self.tick_ok()
                data = self.state(self.stream)
                self.assertEqual(data["dcr_operations"]["source"], self.op)
                self.assertNotIn("coordinator_replacement", data)
                self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_ready_without_ack_preserves_receiving_stop(self):
        self.incomplete_ready(blocked=True)
        self.stub.automatic_admissions["source"].update(allowed=False, generation="receiving-stop")
        self.tick_ok()
        data = self.state(self.stream)
        self.assertNotIn("coordinator_replacement", data)
        self.assertEqual(data["dcr_dumps"]["source"], self.dump)
        self.assertFalse(self.stub.automatic_admissions["source"]["allowed"])


class LoadReconciliationTests(CapacityFixture):
    def completed_receiver(self, intent, *, acknowledgement=True):
        identity = intent["load"]["delivery"]
        control = self.stub.control_goals[identity]
        prefix = control["text"][:-len("/poteto-mode " + control["potetoGoal"])]
        text = "Dump checkpoint loaded: " + intent["id"] if acknowledgement else "The required acknowledgement is absent."
        self.write_log("successor", str(self.cwd), user(prefix + '<skill name="poteto-mode" location="/offline/skill.md">\nControlled fixture.\n</skill>\n\n' + control["potetoGoal"]), reply(text))
        self.successor_status["rotationSafety"]["entryId"] = "e2"
        self.successor_status["messageCount"] = 2
        control["state"] = "ended"

    def journal(self, intent, state):
        data = self.state(self.stream)
        record = data["deliveries"][intent["load"]["delivery"]]
        record["state"] = state
        record["control"]["state"] = "sending" if state == "sending" else "uncertain"
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))

    def reconcile(self, state):
        intent = self.rotate("research")
        self.completed_receiver(intent)
        self.journal(intent, state)
        self.stub.requests.clear()
        self.advance()
        data = self.state(self.stream)
        self.assertEqual(data["coordinator_replacement"]["load"]["state"], "observed", "EXACT_RECEIPT must reconcile without redispatch")
        self.assertEqual(data["deliveries"][intent["load"]["delivery"]]["control"]["state"], "ended")
        self.assertEqual((data["coordinator_replacement"]["load"]["userEntryId"], data["coordinator_replacement"]["load"]["assistantEntryId"]), ("e1", "e2"))
        self.assertTrue(any(method == "GET" and "/control-goal/" in path for method, path, _, _ in self.stub.requests))
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])
        self.advance()
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_transport_accepted_journal_still_observes_exact_completed_receiver(self):
        self.reconcile("transport_accepted")

    def test_sending_journal_observes_exact_completed_receiver(self):
        self.reconcile("sending")

    def test_uncertain_journal_observes_exact_completed_receiver(self):
        self.reconcile("uncertain")

    def test_uncertain_receiver_remains_fenced_despite_native_ack(self):
        intent = self.rotate("research")
        self.completed_receiver(intent)
        self.journal(intent, "uncertain")
        self.stub.control_goals[intent["load"]["delivery"]]["state"] = "uncertain"
        self.stub.requests.clear()
        self.advance()
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"]["state"], "pending")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_changed_receiver_intent_cannot_complete_uncertain_load(self):
        intent = self.rotate("research")
        self.completed_receiver(intent)
        self.journal(intent, "uncertain")
        self.stub.control_goals[intent["load"]["delivery"]]["potetoGoal"] = "A different intent"
        self.stub.requests.clear()
        self.run_streams("dcr", "advance", "etl", "--session", "source", "--operation", self.op["id"])
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"]["state"], "pending")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_exact_receipt_without_exact_native_ack_is_blocked(self):
        intent = self.rotate("research")
        self.completed_receiver(intent, acknowledgement=False)
        self.journal(intent, "uncertain")
        self.stub.requests.clear()
        self.advance()
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"]["state"], "blocked")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_absent_receiver_receipt_preserves_uncertain_fence(self):
        intent = self.rotate("research")
        self.completed_receiver(intent)
        self.journal(intent, "uncertain")
        del self.stub.control_goals[intent["load"]["delivery"]]
        self.stub.requests.clear()
        self.run_streams("dcr", "advance", "etl", "--session", "source", "--operation", self.op["id"])
        data = self.state(self.stream)
        self.assertEqual(data["coordinator_replacement"]["load"]["state"], "pending")
        self.assertEqual(data["deliveries"][intent["load"]["delivery"]]["state"], "uncertain")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_receiving_stop_wins_over_exact_completed_receipt(self):
        intent = self.rotate("research")
        self.completed_receiver(intent)
        self.journal(intent, "uncertain")
        self.stub.automatic_admissions["successor"].update(allowed=False, generation="new-receiving-stop")
        self.stub.requests.clear()
        self.advance()
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"]["state"], "stopped")
        self.assertFalse(self.stub.automatic_admissions["successor"]["allowed"])
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def initial_loader_error(self, *, completed=False):
        self.fixture("research")

        def reject(body):
            if completed:
                self.stub.control_goals[body["id"]] = {**body, "version": 1, "sessionId": "successor", "state": "ended"}
                current = self.state(self.stream)["coordinator_replacement"]
                self.completed_receiver(current)
                return 503, {"error": "Labelled lost response after exact completion"}
            self.stub.automatic_admissions["successor"].update(allowed=False, generation="receiving-stop")
            return 409, {"error": "Receiving stop refused admission"}

        self.routes = [(method, path, code, reject if method == "POST" and path == "/api/sessions/successor/control-goal" else body)
                       for method, path, code, body in self.routes]
        self.stub.set_routes(self.routes)
        self.native.update(state="failed", detail="Labelled expired native compaction lease; writer fenced")
        self.advance()
        data = self.state(self.stream)
        self.assertEqual(data["coordinator_replacement"]["phase"], "complete")
        self.assertIn(data["dcr_operations"]["source"]["phase"], {"rotation-pending", "rotated"}, "PUBLISHED_OWNER must survive initial loader exceptions")
        return data["coordinator_replacement"]

    def test_initial_refused_load_reconciles_stopped_without_owner_loss(self):
        intent = self.initial_loader_error()
        self.stub.requests.clear()
        self.advance()
        data = self.state(self.stream)
        self.assertEqual(data["coordinator_replacement"]["load"]["state"], "stopped")
        self.assertEqual(data["dcr_operations"]["source"]["phase"], "rotated")
        self.assertFalse(self.stub.automatic_admissions["successor"]["allowed"])
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_initial_lost_reply_reconciles_exact_completion_without_owner_loss(self):
        intent = self.initial_loader_error(completed=True)
        self.stub.requests.clear()
        self.advance()
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"]["state"], "observed")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_completed_replacement_rejects_changed_owner_or_target(self):
        intent = self.rotate("research")
        self.completed_receiver(intent)
        baseline = copy.deepcopy(self.state(self.stream))
        variants = [
            ("dcr_operations.source.cwd", str(self.tmp / "changed-owner")),
            ("dcr_operations.source.id", "changed-operation"),
            ("dcr_operations.source.checkpoint_entry", "changed-checkpoint"),
            ("dcr_operations.source.checkpoint_sha256", "0" * 64),
            ("dcr_operations.source.automatic.generation", "changed-generation"),
            ("dcr_operations.source.ready_revision", "0" * 64),
            ("dcr_operations.source.capacity.receipt.detail", "changed-outcome"),
            ("dcr_operations.source.phase", "compacting"),
            ("coordinator_replacement.source", "changed-source"),
            ("coordinator_replacement.phase", "prepared"),
            ("coordinator_replacement.target", "stale-target"),
        ]
        for field, value in variants:
            with self.subTest(field=field):
                data = copy.deepcopy(baseline)
                data["dcr_operations"]["source"].update(phase="blocked", detail="Labelled prior loader exception")
                parts = field.split(".")
                record = data
                for part in parts[:-1]:
                    record = record[part]
                record[parts[-1]] = value
                if field.endswith(".cwd"):
                    data["dcr_operations"]["source"]["automatic"]["cwd"] = value
                (self.stream / "log/tick-state.json").write_text(json.dumps(data))
                self.stub.requests.clear()
                result = self.run_streams("dcr", "advance", "etl", "--session", "source", "--operation", self.op["id"])
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.state(self.stream)["dcr_operations"]["source"], data["dcr_operations"]["source"])
                self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"]["state"], "pending")
                self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_preexisting_blocked_owner_reconciles_completed_replacement(self):
        intent = self.rotate("research")
        self.completed_receiver(intent)
        data = self.state(self.stream)
        data["dcr_operations"]["source"].update(phase="blocked", detail="Labelled prior loader exception")
        (self.stream / "log/tick-state.json").write_text(json.dumps(data))
        self.stub.requests.clear()
        self.advance()
        self.assertEqual(self.state(self.stream)["coordinator_replacement"]["load"]["state"], "observed")
        self.assertEqual(self.state(self.stream)["dcr_operations"]["source"]["phase"], "rotated")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])
