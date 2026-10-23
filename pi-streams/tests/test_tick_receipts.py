"""A tick retains its event batch until an applied receipt exists."""
from __future__ import annotations

import json

from tick_support import PROMPTS, TickCase, info, row, status


class TickReceiptTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.stream = self.make_stream(self.home, "etl", row("current", "coordinator", str(self.home / "etl")) + row("worker", "worker", "/private-worker"))
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [info("current", str(self.stream), self.log_path("current")), info("worker", "/private-worker", self.log_path("worker"))]),
            ("GET", "/api/sessions/current/status", 200, status("current")),
            ("GET", "/api/sessions/worker/status", 200, status("worker")),
            PROMPTS,
        ])

    def test_transport_accepted_events_remain_pending_without_replaying(self) -> None:
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.state(self.stream)
        self.assertEqual([event["kind"] for event in data["pending"]], ["idle"])
        identity = data["tick_delivery"]
        record = data["deliveries"][identity]
        self.assertEqual(record["state"], "transport_accepted")
        self.assertEqual(record["body"], "pi-streams tick 2026-10-06T12:00:00Z:\nidle worker worker")
        self.assertEqual(record["session"], "current")
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state(self.stream)["tick_delivery"], identity)
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])

    def test_applied_batch_preserves_newer_pending_input(self) -> None:
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        identity = self.state(self.stream)["tick_delivery"]
        (self.stream / "context").mkdir(exist_ok=True)
        (self.stream / "context/active-plan.md").write_text("Actual fixture plan now includes the idle worker.\n")
        for phase, extra in (("consumed", []), ("applied", ["--evidence", "context/active-plan.md"])):
            result = self.run_streams("delivery", "ack", "etl", identity, "--session", "current", "--state", phase, "--detail", "Fixture has incorporated the worker event.", *extra)
            self.assertEqual(result.returncode, 0, result.stderr)
        path = self.stream / "log/tick-state.json"
        data = json.loads(path.read_text())
        newer = {"at": "2026-10-06T12:03:00Z", "kind": "subscription", "session": "", "role": "", "detail": "New input after the saved batch."}
        data["pending"].append(newer)
        path.write_text(json.dumps(data))
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.state(self.stream)
        self.assertEqual(data["pending"], [newer])
        self.assertNotEqual(data["tick_delivery"], identity)
        self.assertEqual(data["deliveries"][identity]["state"], "applied")
        sent = [body for method, _, _, body in self.stub.requests if method == "POST"]
        self.assertEqual(sent, [{"text": "pi-streams tick 2026-10-06T12:05:00Z:\nsubscription New input after the saved batch.", "deliveryId": data["tick_delivery"], "automaticAdmission": {"sessionId": "current", "cwd": str(self.stream), "generation": "fixture-current", "kind": "wake"}}])

    def test_consumed_alone_retains_events_then_applied_removes_only_the_original_batch(self) -> None:
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.state(self.stream)
        self.assertEqual(len(data["pending"]), 1)
        identity = data["tick_delivery"]
        result = self.run_streams("delivery", "ack", "etl", identity, "--session", "current", "--state", "consumed", "--detail", "Read the exact idle event.")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.state(self.stream)["pending"]), 1)
        (self.stream / "context").mkdir(exist_ok=True)
        (self.stream / "context/receipt-proof.md").write_text("Actual plan now accounts for the idle worker.\n")
        result = self.run_streams("delivery", "ack", "etl", identity, "--session", "current", "--state", "applied", "--detail", "Updated the active plan.", "--evidence", "context/receipt-proof.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.state(self.stream)
        self.assertEqual(data["pending"], [])
        self.assertNotIn("tick_delivery", data)
        self.assertEqual(data["deliveries"][identity]["state"], "applied")
        self.assertEqual([r for r in self.stub.requests if r[0] == "POST"], [])
