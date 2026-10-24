from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from unittest import mock

from support import EngineCase, ROOT

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, doctor, piweb


class MaintenanceAdapterTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.sid = "11111111-1111-4111-8111-111111111111"
        self.cwd = str(self.root.resolve())
        self.operation_id = "dcr-op-1"
        self.file = self.tmp / "native.jsonl"
        self.line = (json.dumps({"type": "compaction", "id": "compaction-1", "parentId": "marker-1", "summary": "real persisted summary", "firstKeptEntryId": "good-leaf", "tokensBefore": 150000}) + "\n").encode()
        self.file.write_bytes((json.dumps({"type": "session", "id": self.sid, "cwd": self.cwd}) + "\n").encode() + self.line)
        self.expected = {"sessionId": self.sid, "cwd": self.cwd, "entryId": "good-leaf", "generation": "saved-generation"}
        self.status = {"sessionId": self.sid, "maintenanceSupport": "checkpoint-input-v1", "rotationSafety": {"entryId": "good-leaf"}, "automaticAdmission": {"sessionId": self.sid, "cwd": self.cwd, "generation": "saved-generation", "allowed": True, "durable": True}}
        self.operation = {"version": 1, "id": self.operation_id, "sessionId": self.sid, "cwd": self.cwd, "entryId": "good-leaf", "generation": "saved-generation", "instructions": "exact instructions", "state": "complete", "inputSequence": 0, "lastInputGeneration": "saved-generation", "inputs": [], "markerEntryId": "marker-1", "compactionEntryId": "compaction-1", "compactionSha256": hashlib.sha256(self.line).hexdigest()}
        self.routes()

    def routes(self, operation=None, status=None):
        self.stub.set_routes([
            ("GET", "/api/sessiond/runtime", 200, {"component": "sessiond", "capabilities": ["sessions.maintenanceCheckpoint", "prompt.potetoArguments", "sessions.streamsDcrEvents", "prompt.controlGoal", "sessions.conditionalAdmission", "prompt.recoveryControl", "sessions.failureBoundary", "sessions.failureFork", "sessions.failureMaintenance", "sessions.failureRetirement", "sessions.resumeObservation"]}),
            ("GET", f"/api/sessions/{self.sid}/status", 200, self.status if status is None else status),
            ("GET", "/api/sessions", 200, [{"id": self.sid, "cwd": self.cwd, "path": str(self.file)}]),
            ("POST", f"/api/sessions/{self.sid}/commands/run", 200, {"type": "done", "message": "Compaction started…"}),
            ("POST", f"/api/sessions/{self.sid}/maintenance/compact", 200, {**self.operation, "state": "compacting", "compactionEntryId": None, "compactionSha256": None}),
            ("GET", f"/api/sessions/{self.sid}/maintenance/{self.operation_id}", 200, self.operation if operation is None else operation),
            ("POST", f"/api/sessions/{self.sid}/maintenance/{self.operation_id}/reconcile", 200, {**self.operation, "state": "superseded"}),
            ("POST", f"/api/sessions/{self.sid}/maintenance/resume", 200, {**self.operation, "state": "resuming", "resume": {"deliveryId": "resume-1", "text": "exact engine resume\r\nGoal: 'quoted'", "generation": "saved-generation", "inputSequence": 0, "state": "sending"}}),
        ])

    def test_command_run_uses_native_command_endpoint_and_never_claims_compaction_completion(self):
        text = "/compact exact focus\nkeep Unicode café"
        result = subprocess.run([str(ROOT / "bin/pi-web-cli"), "command-run", self.sid], input=text, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["commandAccepted"])
        self.assertEqual(data["result"], {"type": "done", "message": "Compaction started…"})
        self.assertNotIn("compactionCompleted", data)
        self.assertEqual(self.stub.requests[-1][1], f"/api/sessions/{self.sid}/commands/run")
        self.assertEqual(self.stub.requests[-1][3], {"text": text})

    def test_guarded_compact_carries_exact_saved_checkpoint_and_instructions(self):
        text = "Preserve newline\r\nquotes 'x' and café."
        self.operation["instructions"] = text
        self.routes()
        with mock.patch.dict(os.environ, self.env, clear=True):
            result = piweb.compact_at_checkpoint(self.sid, self.operation_id, self.expected, text)
        self.assertEqual(result["state"], "compacting")
        posts = [request for request in self.stub.requests if request[0] == "POST"]
        self.assertEqual([(post[1], post[3]) for post in posts], [(f"/api/sessions/{self.sid}/maintenance/compact", {"cwd": self.cwd, "id": self.operation_id, "expectedIdle": self.expected, "instructions": text})])

    def test_start_receipt_is_not_a_compaction_result(self):
        self.routes(operation={**self.operation, "state": "compacting", "compactionEntryId": None, "compactionSha256": None})
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertIsNone(piweb.compaction_result(self.cwd, self.sid, self.operation_id))
        self.assertEqual([request[1] for request in self.stub.requests], [f"/api/sessions/{self.sid}/maintenance/{self.operation_id}"])

    def test_observation_requires_exact_persisted_compaction_bytes_not_http_success(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            result = piweb.compaction_result(self.cwd, self.sid, self.operation_id)
        self.assertEqual(result["entryId"], "compaction-1")
        self.assertEqual(result["sha256"], hashlib.sha256(self.line).hexdigest())
        self.assertEqual(result["tokensBefore"], 150000)
        self.routes(operation={**self.operation, "compactionSha256": "0" * 64})
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(StreamsError, "hash mismatch"):
                piweb.compaction_result(self.cwd, self.sid, self.operation_id)

    def test_misidentified_receiver_or_non_compaction_native_entry_refuses(self):
        for changed in ({"sessionId": "different"}, {"cwd": str(self.tmp / "other")}, {"version": True}):
            self.routes(operation={**self.operation, **changed})
            with mock.patch.dict(os.environ, self.env, clear=True):
                with self.assertRaises(StreamsError):
                    piweb.compaction_result(self.cwd, self.sid, self.operation_id)
        bad = (json.dumps({"type": "message", "id": "compaction-1", "message": {"role": "assistant", "content": "not compaction"}}) + "\n").encode()
        self.file.write_bytes((json.dumps({"type": "session", "id": self.sid}) + "\n").encode() + bad)
        self.routes(operation={**self.operation, "compactionSha256": hashlib.sha256(bad).hexdigest()})
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(StreamsError, "compaction"):
                piweb.compaction_result(self.cwd, self.sid, self.operation_id)

    def test_missing_receiving_capability_refuses_before_any_compact_or_prompt(self):
        self.routes(status={key: value for key, value in self.status.items() if key != "maintenanceSupport"})
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(StreamsError, "maintenance|capability"):
                piweb.compact_at_checkpoint(self.sid, self.operation_id, self.expected, "unused")
        self.assertEqual([request[0] for request in self.stub.requests], ["GET"])

    def test_saved_resume_and_explicit_reconcile_preserve_body_sequence_and_generation(self):
        token = {"sessionId": self.sid, "cwd": self.cwd, "generation": "saved-generation", "kind": "resume"}
        text = "exact engine resume\r\nGoal: 'quoted'"
        with mock.patch.dict(os.environ, self.env, clear=True):
            result = piweb.resume_maintenance(self.sid, self.operation_id, "compaction-1", 0, token, "resume-1", text)
            reconciled = piweb.reconcile_maintenance(self.cwd, self.sid, self.operation_id)
        self.assertEqual(result["state"], "resuming")
        self.assertEqual(reconciled["state"], "superseded")
        posts = [request for request in self.stub.requests if request[0] == "POST"]
        self.assertEqual(posts[0][3], {"cwd": self.cwd, "id": self.operation_id, "compactionEntryId": "compaction-1", "inputSequence": 0, "automaticAdmission": token, "deliveryId": "resume-1", "text": text})
        self.assertEqual(posts[1][3], {"cwd": self.cwd})

    def test_doctor_fails_unsupported_maintenance_and_accepts_versioned_receiver(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(doctor.check_maintenance()[0].level, "PASS")
        self.stub.set_routes([("GET", "/api/sessiond/runtime", 200, {"component": "sessiond", "capabilities": []})])
        with mock.patch.dict(os.environ, self.env, clear=True):
            finding = doctor.check_maintenance()[0]
        self.assertEqual(finding.level, "FAIL")
        self.assertIn("automatic DCR", finding.detail)
