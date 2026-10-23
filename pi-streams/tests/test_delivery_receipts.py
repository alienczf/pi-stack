"""Transport acceptance is not coordinator consumption or application."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from support import EngineCase, ROOT, git, seed_ratified_stream
from test_coordinator_identity import HEADER, live

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError
from engine import delivery


class DeliveryReceiptTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.run_streams("init", str(self.root), "-y").returncode, 0)
        self.stream = self.register_stream("etl")
        seed_ratified_stream(self.stream, self.root.name)
        (self.stream / "threads.tsv").write_text(HEADER + f"current\tcoordinator\t\t{self.stream}\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-23T00:00:00Z\n")
        git(self.stream, self.env, "init")
        self.stub.reflect_delivery_ids = True
        self.stub.automatic_admissions["current"] = {"sessionId": "current", "cwd": str(self.stream), "generation": "fixture-current", "allowed": True, "durable": True}
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [{"id": "current", "cwd": str(self.stream)}]),
            ("GET", "/api/sessions/current/status", 200, live("current")),
            ("POST", "/api/sessions/current/prompt", 200, {"accepted": True}),
        ])
        self.environment = mock.patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def prepare(self, identity: str = "notice-1", body: str = "Change the current objective."):
        return delivery.prepare_locked(self.stream, identity, "current", body)

    def test_explicit_human_correction_reaches_unratified_kickoff_without_authorizing_workers(self) -> None:
        state = self.stream / "STATE.md"
        state.write_text(state.read_text().replace("ratified: 2026-10-23 fixture human confirmation", "ratified: no", 1))
        body = self.tmp / "human-notice.md"
        text = "Fixture human notice 42. Correct the kickoff objective before ratification.\n原本\n"
        body.write_text(text)
        result = self.run_streams("delivery", "send", "etl", "--delivery-id", "human-notice-42", "--session", "current", "--body-file", str(body), "--behavior", "steer")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual((record["origin"], record["state"], record["body"]), ("steer", "transport_accepted", text))
        self.assertEqual([request[3] for request in self.stub.requests if request[0] == "POST"], [{"text": text, "streamingBehavior": "steer", "deliveryId": "human-notice-42"}])
        self.assertTrue(state.read_text().startswith("## Goals\nratified: no\n"))
        before = list(self.stub.requests)
        worker = self.run_streams("thread", "spawn", "etl", "--repo", "alpha", "--role", "worker")
        self.assertEqual(worker.returncode, 1, worker.stdout)
        self.assertIn("unratified", worker.stderr)
        self.assertEqual(self.stub.requests, before)
        self.assertFalse((self.root / ".worktrees").exists())

    def test_cli_bodyfile_preserves_crlf_and_unicode_through_receipt_admission(self) -> None:
        body = self.tmp / "exact-notice.md"
        raw = "Exact punctuation: a,b?\r\n原本\r\n\r\n".encode()
        body.write_bytes(raw)
        result = self.run_streams("delivery", "send", "etl", "--delivery-id", "crlf-notice", "--session", "current", "--body-file", str(body), "--behavior", "steer")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["body"], raw.decode())
        self.assertEqual([request[3]["text"] for request in self.stub.requests if request[0] == "POST"], [raw.decode()])

    def test_automatic_tick_delivery_remains_blocked_when_kickoff_is_unratified(self) -> None:
        state = self.stream / "STATE.md"
        state.write_text(state.read_text().replace("ratified: 2026-10-23 fixture human confirmation", "ratified: no", 1))
        events = [{"at": "2026-10-23T00:00:00Z", "kind": "idle", "session": "private-worker", "role": "worker", "detail": ""}]
        delivery.prepare_locked(self.stream, "automatic-1", "current", "Do not admit this automatic wake.", events=events)
        with self.assertRaisesRegex(StreamsError, "unratified"):
            delivery.send_locked(self.stream, "automatic-1")
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.assertEqual(delivery.receipts(self.stream)[0]["state"], "prepared")
        self.assertFalse((self.root / ".worktrees").exists())

    def test_acceptance_retains_body_and_is_not_an_applied_receipt(self) -> None:
        self.prepare()
        result = delivery.send_locked(self.stream, "notice-1")
        self.assertEqual(result["state"], "transport_accepted")
        self.assertEqual(result["body"], "Change the current objective.")
        self.assertEqual(result["session"], "current")
        self.assertNotIn("evidence", result)
        self.assertEqual(delivery.receipts(self.stream), [result])
        self.assertEqual(delivery.send_locked(self.stream, "notice-1"), result)
        self.assertEqual([path for method, path, _, _ in self.stub.requests if method == "POST"], ["/api/sessions/current/prompt"])

    def test_distinct_notice_ids_preserve_identical_bodies_without_text_deduplication(self) -> None:
        self.prepare("notice-1", "Same steer.")
        self.prepare("notice-2", "Same steer.")
        self.assertEqual([item["id"] for item in delivery.receipts(self.stream)], ["notice-1", "notice-2"])
        self.assertEqual(self.prepare("notice-1", "Same steer.")["id"], "notice-1")
        delivery.send_locked(self.stream, "notice-1")
        delivery.send_locked(self.stream, "notice-2")
        sent = [body for method, _, _, body in self.stub.requests if method == "POST"]
        self.assertEqual(sent, [{"text": "Same steer.", "deliveryId": "notice-1"}, {"text": "Same steer.", "deliveryId": "notice-2"}])
        with self.assertRaisesRegex(StreamsError, "changed intent"):
            self.prepare("notice-1", "A different steer.")

    def test_consumption_does_not_claim_application(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        result = delivery.acknowledge_locked(self.stream, "notice-1", "current", "consumed", "Read the exact instruction.")
        self.assertEqual(result["state"], "consumed")
        self.assertNotIn("evidence", result)
        self.assertEqual(delivery.send_locked(self.stream, "notice-1")["state"], "consumed")

    def test_applied_receipt_verifies_a_real_owned_artifact_after_consumption(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        delivery.acknowledge_locked(self.stream, "notice-1", "current", "consumed", "Read the requested objective change.")
        evidence = self.stream / "context" / "observed-change.md"
        raw = "Actual current plan change. 原本\r\n".encode()
        evidence.write_bytes(raw)
        result = delivery.acknowledge_locked(self.stream, "notice-1", "current", "applied", "Updated the active plan with the requested step.", evidence="context/observed-change.md")
        self.assertEqual(result["state"], "applied")
        self.assertEqual(result["evidence"], {"path": "context/observed-change.md", "sha256": hashlib.sha256(raw).hexdigest()})
        self.assertEqual(evidence.read_bytes(), raw)

    def test_echoing_an_id_or_promising_application_is_not_an_applied_receipt(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        with self.assertRaisesRegex(StreamsError, "consumed"):
            delivery.acknowledge_locked(self.stream, "notice-1", "current", "applied", "I will do it.", evidence="STATE.md")
        delivery.acknowledge_locked(self.stream, "notice-1", "current", "consumed", "Read.")
        with self.assertRaisesRegex(StreamsError, "evidence"):
            delivery.acknowledge_locked(self.stream, "notice-1", "current", "applied", "I will do it.")
        self.assertEqual(delivery.receipts(self.stream)[0]["state"], "consumed")

    def test_blocked_instruction_remains_visible_and_is_not_replayed(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        result = delivery.acknowledge_locked(self.stream, "notice-1", "current", "blocked", "Requires a human ruling before writes.")
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["detail"], "Requires a human ruling before writes.")
        self.assertEqual(delivery.send_locked(self.stream, "notice-1"), result)
        self.assertEqual(len([r for r in self.stub.requests if r[0] == "POST"]), 1)

    def test_uncertain_transport_is_persisted_without_a_blind_retry(self) -> None:
        self.prepare()
        with mock.patch("engine.piweb.prompt", side_effect=StreamsError("fixture connection lost after send")):
            with self.assertRaisesRegex(StreamsError, "connection lost"):
                delivery.send_locked(self.stream, "notice-1")
        result = delivery.send_locked(self.stream, "notice-1")
        self.assertEqual(result["state"], "uncertain")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_explicit_receiver_rejection_stays_visibly_blocked(self) -> None:
        self.prepare()
        self.stub.set_routes([("POST", "/api/sessions/current/prompt", 400, {"error": "Instruction rejected before admission."}), *self.stub.routes])
        with self.assertRaises(StreamsError):
            delivery.send_locked(self.stream, "notice-1")
        result = delivery.send_locked(self.stream, "notice-1")
        self.assertEqual(result["state"], "blocked")
        self.assertIn("Instruction rejected", result["detail"])
        self.assertEqual(len([r for r in self.stub.requests if r[0] == "POST"]), 1)

    def test_an_accepted_response_without_matching_correlation_stays_uncertain(self) -> None:
        self.prepare()
        self.stub.reflect_delivery_ids = False
        with self.assertRaises(StreamsError):
            delivery.send_locked(self.stream, "notice-1")
        result = delivery.send_locked(self.stream, "notice-1")
        self.assertEqual(result["state"], "uncertain")
        self.assertEqual(len([r for r in self.stub.requests if r[0] == "POST"]), 1)

    def test_crash_after_application_before_receipt_does_not_replay_the_instruction(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        delivery.acknowledge_locked(self.stream, "notice-1", "current", "consumed", "Read exact instruction.")
        proof = self.stream / "context" / "applied-before-crash.md"
        proof.write_text("Actual plan updated before the receipt publication crash.\n")
        with mock.patch.object(delivery, "_save", side_effect=OSError("fixture receipt publication crash")):
            with self.assertRaises(OSError):
                delivery.acknowledge_locked(self.stream, "notice-1", "current", "applied", "Updated the active plan.", evidence="context/applied-before-crash.md")
        self.assertEqual(delivery.send_locked(self.stream, "notice-1")["state"], "consumed")
        result = delivery.acknowledge_locked(self.stream, "notice-1", "current", "applied", "Verified the existing plan change after restart.", evidence="context/applied-before-crash.md")
        self.assertEqual(result["state"], "applied")
        self.assertEqual(len([r for r in self.stub.requests if r[0] == "POST"]), 1)

    def test_last_native_resolution_must_still_return_the_designated_destination(self) -> None:
        self.prepare()
        with mock.patch("engine.threads.resolve_coordinator", return_value=None):
            with self.assertRaisesRegex(StreamsError, "destination"):
                delivery.send_locked(self.stream, "notice-1")
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.assertEqual(delivery.receipts(self.stream)[0]["state"], "prepared")

    def test_stale_destination_cannot_send_or_claim_application(self) -> None:
        self.prepare()
        table = self.stream / "threads.tsv"
        table.write_text(table.read_text().replace("current\t", "successor\t", 1))
        with self.assertRaisesRegex(StreamsError, "destination"):
            delivery.send_locked(self.stream, "notice-1")
        with self.assertRaisesRegex(StreamsError, "destination"):
            delivery.acknowledge_locked(self.stream, "notice-1", "successor", "consumed", "Wrong conversation.")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_evidence_cannot_escape_the_owned_stream_or_follow_a_symlink(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        delivery.acknowledge_locked(self.stream, "notice-1", "current", "consumed", "Read.")
        (self.stream / "context" / "escape").symlink_to(self.fx.alpha / "README")
        for evidence in ("../alpha/README", str(self.fx.alpha / "README"), "context/escape", "missing.md"):
            with self.subTest(evidence=evidence), self.assertRaises(StreamsError):
                delivery.acknowledge_locked(self.stream, "notice-1", "current", "applied", "Claimed update.", evidence=evidence)
        self.assertEqual(delivery.receipts(self.stream)[0]["state"], "consumed")

    def test_fifo_evidence_is_refused_without_blocking_the_acknowledgement_lock(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        delivery.acknowledge_locked(self.stream, "notice-1", "current", "consumed", "Read exact steer.")
        os.mkfifo(self.stream / "context/evidence.pipe")
        command = [str(ROOT / "bin/pi-streams"), "delivery", "ack", "etl", "notice-1", "--session", "current", "--state", "applied", "--detail", "Must refuse a nonregular proof.", "--evidence", "context/evidence.pipe"]
        try:
            result = subprocess.run(command, env=self.env, capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            self.fail("acknowledgement blocked opening FIFO evidence while holding its stream lock")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("regular file", result.stderr)
        self.assertEqual(delivery.receipts(self.stream)[0]["state"], "consumed")

    def test_regular_evidence_digest_preserves_all_bytes_across_read_chunks(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        delivery.acknowledge_locked(self.stream, "notice-1", "current", "consumed", "Read exact steer.")
        raw = ("Exact original proof bytes. 原本\r\n".encode() * 5000) + b"last byte!"
        (self.stream / "context/multichunk-proof.md").write_bytes(raw)
        result = delivery.acknowledge_locked(self.stream, "notice-1", "current", "applied", "Verified the complete owned artifact.", evidence="context/multichunk-proof.md")
        self.assertEqual(result["evidence"], {"path": "context/multichunk-proof.md", "sha256": hashlib.sha256(raw).hexdigest()})
        (self.stream / "context/empty-proof.md").write_bytes(b"")
        with self.assertRaisesRegex(StreamsError, "empty"):
            delivery._evidence(self.stream, "context/empty-proof.md")

    def test_cli_exposes_consumed_and_applied_as_separate_states(self) -> None:
        self.prepare()
        delivery.send_locked(self.stream, "notice-1")
        result = self.run_streams("delivery", "ack", "etl", "notice-1", "--session", "current", "--state", "consumed", "--detail", "Read exact steer.")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "consumed")
        result = self.run_streams("delivery", "list", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)[0]["state"], "consumed")
