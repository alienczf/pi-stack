"""Automatic requests retain the receiver generation selected before dispatch."""
from __future__ import annotations

import os
import sys
from unittest import mock

from support import EngineCase, ROOT, git, seed_ratified_stream
from test_coordinator_identity import HEADER, live

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import StreamsError, delivery

EVENTS = [{"at": "2026-10-23T00:00:00Z", "kind": "idle", "session": "worker", "role": "worker", "detail": ""}]


class AutomaticAdmissionTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.run_streams("init", str(self.root), "-y").returncode, 0)
        self.stream = self.register_stream("etl")
        seed_ratified_stream(self.stream, self.root.name)
        (self.stream / "threads.tsv").write_text(HEADER + f"current\tcoordinator\t\t{self.stream}\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-23T00:00:00Z\n")
        git(self.stream, self.env, "init")
        self.stub.reflect_delivery_ids = True
        self.environment = mock.patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.routes()

    def routes(self, generation: str = "first-generation", *, allowed: bool = True, supported: bool = True) -> None:
        status = live("current")
        if supported:
            status["automaticAdmission"] = {"sessionId": "current", "cwd": str(self.stream), "generation": generation, "allowed": allowed, "durable": True}
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [{"id": "current", "cwd": str(self.stream)}]),
            ("GET", "/api/sessions/current/status", 200, status),
            ("POST", "/api/sessions/current/prompt", 200, {"accepted": True}),
        ])

    def prepare(self):
        return delivery.prepare_locked(self.stream, "automatic-1", "current", "Saved automatic wake.", events=EVENTS)

    def test_selected_generation_is_persisted_and_sent_without_body_changes(self) -> None:
        record = self.prepare()
        expected = {"sessionId": "current", "cwd": str(self.stream), "generation": "first-generation", "kind": "wake"}
        self.assertEqual(record["automatic"], expected)
        result = delivery.send_locked(self.stream, "automatic-1")
        self.assertEqual(result["state"], "transport_accepted")
        self.assertEqual([request[3] for request in self.stub.requests if request[0] == "POST"], [{"text": "Saved automatic wake.", "deliveryId": "automatic-1", "automaticAdmission": expected}])

    def test_stop_does_not_renew_a_prepared_request_with_the_new_generation(self) -> None:
        self.prepare()
        self.routes("after-stop", allowed=False)
        result = delivery.send_locked(self.stream, "automatic-1")
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["automatic"]["generation"], "first-generation")
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])

    def test_stopped_coordinator_is_not_replaced_to_bypass_its_disabled_generation(self) -> None:
        self.routes("after-stop", allowed=False)
        routes = list(self.stub.routes)
        for method, path, _, value in routes:
            if method == "GET" and path.endswith("/status"):
                value["contextUsage"] = {"tokens": 180000}
        self.stub.set_routes(routes)
        from engine import artifacts
        artifacts._save_tick_data(self.stream, {"pending": EVENTS})
        before = (self.stream / "threads.tsv").read_bytes()
        result = self.run_streams("tick")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.assertEqual((self.stream / "threads.tsv").read_bytes(), before)
        self.assertEqual(delivery.current_tick(self.stream)["state"], "blocked")

    def test_unsupported_receiver_is_refused_before_any_automatic_prompt(self) -> None:
        self.routes(supported=False)
        with self.assertRaisesRegex(StreamsError, "automatic.*capability"):
            self.prepare()
            delivery.send_locked(self.stream, "automatic-1")
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])

    def test_fresh_explicit_steer_does_not_need_or_rearm_automatic_permission(self) -> None:
        self.routes("after-stop", allowed=False)
        delivery.prepare_locked(self.stream, "human-1", "current", "Fresh explicit correction.")
        result = delivery.send_locked(self.stream, "human-1")
        self.assertEqual(result["state"], "transport_accepted")
        self.assertNotIn("automatic", result)
        self.assertEqual([request[3] for request in self.stub.requests if request[0] == "POST"], [{"text": "Fresh explicit correction.", "deliveryId": "human-1"}])
