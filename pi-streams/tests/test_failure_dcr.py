from __future__ import annotations

import hashlib
import json
from pathlib import Path

import test_failure_recovery as recovery_cases
from tick_support import TickCase, reply, user


class FailureDcrTests(TickCase):
    seed = recovery_cases.FailureRecoveryTests.seed
    digest = recovery_cases.FailureRecoveryTests.digest
    body = recovery_cases.FailureRecoveryTests.body
    fixture = recovery_cases.FailureRecoveryTests.fixture
    append = recovery_cases.FailureRecoveryTests.append
    fork_response = recovery_cases.FailureRecoveryTests.fork_response
    advance = recovery_cases.FailureRecoveryTests.advance

    def start(self, role="coordinator"):
        self.fixture(role, model="gpt-6.1-sol" if role != "coordinator" else "gpt-6-astra")
        bound = self.advance()
        self.assertEqual(bound.returncode, 0, bound.stderr)
        self.native = None
        self.routes.append(("POST", "/api/sessions/coi/failure-recovery/maintenance", 200, self.maintenance))
        self.stub.set_routes(self.routes)
        sent = self.advance()
        self.assertEqual(sent.returncode, 0, sent.stderr)
        self.assertIn("dcr_operations", self.state(self.stream), "Explicit ratified recovery must force DCR even below 150k")
        self.op = self.state(self.stream)["dcr_operations"]["returned-fork"]
        self.assertEqual(self.op["phase"], "sync-admitted")
        return self.op

    def maintenance(self, body):
        identity = self.request["id"]
        self.assertEqual(body["id"], identity)
        action = body["action"]
        if action == "prepare":
            self.assertEqual(body["expectedForkGeneration"], "held-generation")
            self.result["maintenance"] = {"id": identity, "expectedGeneration": "held-generation", "phase": "ready", "generation": "maintenance-generation"}
            self.stub.automatic_admissions["returned-fork"].update(allowed=True, generation="maintenance-generation")
        if action == "sync":
            self.result["maintenance"]["sync"] = {"text": body["text"], "deliveryId": body["deliveryId"], "state": "ended"}
        receipt = {"operation": self.result, "automaticAdmission": self.stub.automatic_admissions["returned-fork"]}
        if action in {"prepare", "sync"}:
            leaf = self.original["rotationSafety"]["entryId"]
            saved = self.append("coi", "native-"+action, leaf, "pi-web.failure-recovery", self.result)
            self.original["rotationSafety"]["entryId"] = saved["entryId"]
        if action in {"watch", "close"}:
            receipt["events"] = {"id": identity, "entryId": "offline-event-receipt", **({"closed": True} if action == "close" else {})}
        if action == "compact":
            self.native = {"version": 1, "id": identity, "sessionId": "returned-fork", "cwd": str(self.cwd), "entryId": body["expectedIdle"]["entryId"], "generation": "maintenance-generation", "markerEntryId": "offline-maintenance-marker", "instructions": body["instructions"], "state": "compacting", "inputSequence": 0, "inputs": [], "compactionEntryId": None, "compactionSha256": None, "resume": None}
        if action == "resume":
            self.native.update(state="resuming", resume={"deliveryId": body["deliveryId"], "text": body["text"], "potetoGoal": body["potetoGoal"], "generation": "maintenance-generation", "inputSequence": 0, "state": "sending"})
        if action in {"compact", "resume", "maintenance-status"}:
            receipt["maintenance"] = self.native
        return 200, receipt

    def message(self, identity, message):
        parent = self.fork_status["rotationSafety"]["entryId"]
        raw = (json.dumps({"type": "message", "id": identity, "parentId": parent, "message": message}) + "\n").encode()
        with open(self.log_path("returned-fork"), "ab") as target:
            target.write(raw)
        self.fork_status["rotationSafety"]["entryId"] = identity
        return hashlib.sha256(raw).hexdigest()

    def compacted(self):
        ready = self.run_streams("dcr", "ready", "etl", "--session", "returned-fork", "--operation", self.op["id"])
        self.assertEqual(ready.returncode, 0, ready.stderr)
        ack = json.loads(ready.stdout)["acknowledgement"]
        self.message("sync-user", user(self.op["sync_text"]))
        self.message("sync-stop", reply(ack))
        self.assertEqual(self.advance().returncode, 0)
        self.assertEqual(self.state(self.stream)["dcr_operations"]["returned-fork"]["phase"], "compacting")
        raw = (json.dumps({"type": "compaction", "id": "native-compaction", "parentId": "sync-stop", "summary": "Labelled offline persisted native compaction fixture", "firstKeptEntryId": "e1", "tokensBefore": 1000}) + "\n").encode()
        with open(self.log_path("returned-fork"), "ab") as target:
            target.write(raw)
        self.fork_status["rotationSafety"]["entryId"] = "native-compaction"
        self.native.update(state="complete", compactionEntryId="native-compaction", compactionSha256=hashlib.sha256(raw).hexdigest())
        advanced = self.advance()
        self.assertEqual(advanced.returncode, 0, advanced.stderr)
        self.assertEqual(self.state(self.stream)["dcr_operations"]["returned-fork"]["phase"], "resuming")

    def observed(self):
        receipt = self.native["resume"]
        goal = receipt["potetoGoal"]
        prefix = receipt["text"][:-len("/poteto-mode "+goal)]
        user_hash = self.message("resume-user", user(prefix+'<skill name="poteto-mode" location="/offline/skill.md">\nLabelled offline loaded mode, not actual activation proof.\n</skill>\n\n'+goal))
        assistant = self.message("resume-stop", reply("Labelled resumed completed work"))
        data = {"kind": "assistant-stop", "operationId": self.op["id"], "sessionId": "returned-fork", "cwd": str(self.cwd), "generation": "maintenance-generation", "deliveryId": self.op["id"]+":resume", "compactionEntryId": "native-compaction", "userEntryId": "resume-user", "userSha256": user_hash, "assistantEntryId": "resume-stop", "assistantSha256": assistant}
        raw = self.append("returned-fork", "resume-observed", "resume-stop", "pi-web.resume-observed", data)
        self.fork_status["rotationSafety"]["entryId"] = "resume-observed"
        self.native["resume"].update(state="admitted", observation={key: value for key, value in data.items() if key not in ("operationId", "sessionId", "cwd", "generation")}|raw)
        self.native["state"] = "resumed"

    def test_forces_coordinator_dcr_below_threshold_without_generic_prompt(self):
        op = self.start()
        self.assertEqual(op["recovery_original"], "coi")
        self.assertIn(str(self.stream / "STATE.md"), op["sync_text"])
        self.assertIn("--session returned-fork", op["sync_text"])
        self.assertFalse(any(item[1].endswith("/prompt") for item in self.stub.requests))
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")

    def test_worker_uses_same_returned_fork_and_its_own_cwd(self):
        op = self.start("research")
        self.assertEqual(op["cwd"], str(self.cwd))
        self.assertEqual(op["session"], "returned-fork")
        self.assertIn("openai-codex/gpt-6.1-sol\txhigh\tactive", (self.stream / "threads.tsv").read_text())
        self.assertEqual((self.cwd / ".stream").read_text(), str(self.stream))

    def test_compaction_and_completed_resume_must_bind_exact_persisted_native_facts(self):
        self.start()
        self.compacted()
        self.native.update(state="resumed")
        self.native["resume"]["state"] = "admitted"
        self.assertEqual(self.advance().returncode, 0)
        self.assertEqual(self.state(self.stream)["dcr_operations"]["returned-fork"]["phase"], "resuming")
        self.observed()
        result = self.advance()
        self.assertEqual(result.returncode, 0, result.stderr)
        op = self.state(self.stream)["failure_recoveries"]["coi"]
        self.assertEqual(op["phase"], "observed")
        self.assertEqual(op["observation"]["assistantEntryId"], "resume-stop")
        self.assertEqual(op["observation"]["compactionEntryId"], "native-compaction")
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
        self.assertFalse(any(item[0] == "DELETE" or item[1].endswith("/archive") for item in self.stub.requests))

    def test_tick_advances_owned_recovery_without_ordinary_failure_or_drive_fallback(self):
        self.fixture()
        self.assertEqual(self.advance().returncode, 0)
        self.native = None
        self.routes.append(("POST", "/api/sessions/coi/failure-recovery/maintenance", 200, self.maintenance))
        self.stub.set_routes(self.routes)
        ticked = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        operation = self.state(self.stream)["dcr_operations"]["returned-fork"]
        self.assertEqual(operation["phase"], "sync-admitted")
        self.assertFalse(any(item[1].endswith("/prompt") for item in self.stub.requests))

    def test_lost_preparation_reply_reconciles_saved_generation_without_a_second_rearm(self):
        self.fixture()
        self.assertEqual(self.advance().returncode, 0)
        self.native = None
        def lost(body):
            code, payload = self.maintenance(body)
            return (503, {"error": "Labelled preparation reply loss"}) if body["action"] == "prepare" else (code, payload)
        self.routes.append(("POST", "/api/sessions/coi/failure-recovery/maintenance", 200, lost))
        self.stub.set_routes(self.routes)
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual(self.state(self.stream)["failure_recoveries"]["coi"]["phase"], "preparing")
        advanced = self.advance()
        self.assertEqual(advanced.returncode, 0, advanced.stderr)
        self.assertEqual(self.state(self.stream)["dcr_operations"]["returned-fork"]["phase"], "sync-admitted")
        preparations = [item for item in self.stub.requests if isinstance(item[3], dict) and item[3].get("action") == "prepare"]
        self.assertEqual(len(preparations), 1)

    def test_newer_fork_stop_preserves_both_files_and_marker_without_sync_replay(self):
        self.start()
        before = (self.stream / "threads.tsv").read_bytes()
        self.stub.automatic_admissions["returned-fork"].update(allowed=False, generation="newer-human-stop")
        self.assertNotEqual(self.advance().returncode, 0)
        self.assertEqual((self.stream / "threads.tsv").read_bytes(), before)
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
        self.assertEqual(sum(isinstance(item[3], dict) and item[3].get("action") == "sync" for item in self.stub.requests), 1)

    def test_forged_observation_hash_cannot_authorize_original_retirement(self):
        self.start()
        self.compacted()
        self.observed()
        self.native["resume"]["observation"]["sha256"] = "0"*64
        self.assertEqual(self.advance().returncode, 0)
        op = self.state(self.stream)["dcr_operations"]["returned-fork"]
        self.assertEqual(op["phase"], "blocked")
        self.assertIn("hash", op["detail"])
        self.assertEqual((self.stream / "failures/coi.lastgood").read_bytes(), b"e4\n")
