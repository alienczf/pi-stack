"""A failed retired-coordinator archive must not veto its exact successor."""
from __future__ import annotations

import json

from tick_support import PROMPTS, TickCase, info, reply, row, status, user


class RetiredNativeResidueTests(TickCase):
    def setUp(self):
        super().setUp()
        self.stream = self.make_stream(
            self.home,
            "etl",
            row("retired", "coordinator", str(self.home / "etl"), status="archived"),
        )
        self.write_log("retired", str(self.stream), user("Old task"), reply("Old checkpoint"))
        self.write_log("successor", str(self.stream), user("Successor task"), reply("Ready"))
        self.stub.automatic_admissions.update({
            sid: {"sessionId": sid, "cwd": str(self.stream), "generation": f"fixture-{sid}", "allowed": True, "durable": True}
            for sid in ("retired", "successor")
        })
        self.retired_status = {
            **status("retired"),
            "rotationSafety": {
                "entryId": "e2", "callbacksKnown": True,
                "callbackInventory": "native-and-extension-v1",
                "nativeChildCallbacks": [], "unprovenCallbacks": [],
            },
        }
        self.infos = [info(sid, str(self.stream), self.log_path(sid)) for sid in ("retired", "successor")]
        self.archive_reply = {
            "archived": True,
            "automaticAdmission": {
                **self.stub.automatic_admissions["retired"],
                "allowed": False,
                "generation": "frozen-retired",
            },
        }
        self.routes()

    def routes(self, *, archive_code=200, archive_reply=None, successor_status=None):
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, self.infos),
            ("GET", "/api/sessions/retired/status", 200, self.retired_status),
            ("GET", "/api/sessions/successor/status", 200, status("successor") if successor_status is None else successor_status),
            ("POST", "/api/sessions/retired/archive", archive_code, self.archive_reply if archive_reply is None else archive_reply),
            PROMPTS,
        ])

    def adopt(self):
        result = self.run_streams("new", "etl", "--coordinator-session", "successor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"), result.stdout)
        self.stub.requests.clear()

    def add_pending_event(self):
        path = self.stream / "log/tick-state.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        data["pending"] = [{
            "at": "2026-11-03T00:00:00Z", "kind": "subscription",
            "session": "", "role": "", "detail": "Retained successor event",
        }]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def posts(self):
        return [(path, body) for method, path, _query, body in self.stub.requests if method == "POST"]

    def seed_disposition(self, state):
        path = self.stream / "log/tick-state.json"
        data = json.loads(path.read_text()) if path.exists() else {}
        data.setdefault("terminal_sessions", {})["retired"] = {
            "cwd": str(self.stream), "state": state, "detail": f"Saved {state} outcome",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def prepared_delivery(self):
        from engine import delivery

        event = [{
            "at": "2026-11-03T00:00:00Z", "kind": "subscription",
            "session": "", "role": "", "detail": "Saved successor event",
        }]
        return delivery.prepare_locked(
            self.stream, "saved-delivery", "successor", "Saved successor event.", events=event,
        )

    def test_lost_archive_reply_keeps_uncertainty_and_never_replays(self):
        self.adopt()
        self.add_pending_event()

        def archive_then_lose_reply(_body):
            self.stub.archived_sessions.add("retired")
            return 503, {"error": "Archive completed but its reply was lost"}

        self.routes(archive_reply=archive_then_lose_reply)
        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        first_posts = self.posts()
        self.assertEqual([path for path, _ in first_posts], [
            "/api/sessions/retired/archive", "/api/sessions/successor/prompt",
        ])
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "uncertain")
        self.apply_tick_delivery(self.stream)
        self.stub.requests.clear()

        again = self.tick("2026-11-03T00:02:00Z")

        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.posts(), [])
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "uncertain")

    def test_prior_uncertain_disposition_is_not_replayed_and_does_not_block_successor(self):
        self.adopt()
        self.add_pending_event()
        self.seed_disposition("uncertain")

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/successor/prompt"])
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "uncertain")

    def test_prior_refusal_is_not_replayed_and_does_not_block_successor(self):
        self.adopt()
        self.add_pending_event()
        self.seed_disposition("refused")

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/successor/prompt"])
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "refused")

    def test_native_archive_refusal_still_dispatches_and_is_not_replayed(self):
        self.adopt()
        self.add_pending_event()
        self.routes(archive_code=409, archive_reply={"error": "Archive checkpoint was refused"})

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], [
            "/api/sessions/retired/archive", "/api/sessions/successor/prompt",
        ])
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "refused")
        self.apply_tick_delivery(self.stream)
        self.stub.requests.clear()

        again = self.tick("2026-11-03T00:02:00Z")

        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.posts(), [])

    def test_prior_sending_disposition_is_not_replayed_and_does_not_block_successor(self):
        self.adopt()
        self.add_pending_event()
        self.seed_disposition("sending")

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/successor/prompt"])
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "sending")

    def test_saved_delivery_is_blocked_without_native_queries_after_drive_off(self):
        import os
        from unittest import mock
        from engine import drive, delivery

        self.adopt()
        with mock.patch.dict(os.environ, self.env, clear=True):
            self.prepared_delivery()
            drive.pause_local(self.stream)
            self.stub.requests.clear()

            sent = delivery.send_locked(self.stream, "saved-delivery")

        self.assertEqual(sent["state"], "blocked")
        self.assertEqual(self.stub.requests, [])

    def test_invalid_successor_status_identity_is_a_hard_fence_before_archive(self):
        self.adopt()
        self.add_pending_event()
        self.routes(successor_status=status("not-successor"))

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 1)
        self.assertEqual(self.posts(), [])
        self.assertIn("successor", ticked.stderr)

    def test_disabled_successor_admission_prevents_archive_and_dispatch(self):
        self.adopt()
        self.add_pending_event()
        self.stub.automatic_admissions["successor"]["allowed"] = False

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual(self.posts(), [])

    def test_strict_resolver_still_rejects_retired_native_residue(self):
        import os
        from unittest import mock
        from engine import threads

        self.adopt()
        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(threads.RetiredCoordinatorResidue, "retired"):
                threads.resolve_coordinator(self.stream)

    def test_refused_archive_still_dispatches_once_to_successor_and_is_not_replayed(self):
        self.adopt()
        self.routes(archive_code=503, archive_reply={"error": "Lost archive reply"})
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        first_posts = self.posts()
        self.assertEqual([path for path, _ in first_posts], [
            "/api/sessions/retired/archive", "/api/sessions/successor/prompt",
        ])
        self.assertEqual(first_posts[1][1]["automaticAdmission"]["sessionId"], "successor")
        self.assertIn("Retained successor event", first_posts[1][1]["text"])
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "uncertain")
        self.assertNotIn("tick-error", self.events(self.stream))

        self.apply_tick_delivery(self.stream)
        again = self.tick("2026-11-03T00:02:00Z")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.posts(), [])

        observed = self.run_streams("status", "etl", "--json")
        self.assertEqual(observed.returncode, 0, observed.stderr)
        entry, = json.loads(observed.stdout)["streams"]
        self.assertEqual(entry["coordinator"]["session"], "successor")
        self.assertNotIn("dispatchBlockers", entry)
        self.assertEqual(entry["nativeReconciliations"][0]["session"], "retired")

    def test_successful_archive_precedes_successor_dispatch(self):
        self.adopt()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        posts = self.posts()
        self.assertEqual([path for path, _ in posts], [
            "/api/sessions/retired/archive", "/api/sessions/successor/prompt",
        ])
        self.assertEqual(posts[0][1]["expectedIdle"]["sessionId"], "retired")
        self.assertEqual(posts[1][1]["automaticAdmission"]["sessionId"], "successor")
        self.assertEqual(self.state(self.stream)["terminal_sessions"]["retired"]["state"], "archived")

    def test_successor_generation_change_after_initial_selection_blocks_wake(self):
        self.adopt()
        self.add_pending_event()

        def archive_and_change_successor(_body):
            current = self.stub.automatic_admissions["successor"]
            self.stub.automatic_admissions["successor"] = {**current, "generation": "changed-during-reconciliation"}
            return 200, self.archive_reply

        self.routes(archive_reply=archive_and_change_successor)

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 1)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/retired/archive"])
        self.assertIn("admission changed", ticked.stderr.lower())

    def test_delivery_prepare_rejects_changed_saved_admission(self):
        import os
        from unittest import mock
        from engine import StreamsError, delivery

        self.adopt()
        expected = {
            "sessionId": "successor", "cwd": str(self.stream),
            "generation": "fixture-successor", "kind": "wake",
        }
        current = self.stub.automatic_admissions["successor"]
        self.stub.automatic_admissions["successor"] = {**current, "generation": "changed-before-prepare"}
        event = [{"at": "2026-11-03T00:00:00Z", "kind": "subscription", "session": "", "role": "", "detail": "Saved successor event"}]

        with mock.patch.dict(os.environ, self.env, clear=True):
            with self.assertRaisesRegex(StreamsError, "admission changed before delivery preparation"):
                delivery.prepare_locked(
                    self.stream, "changed-prepare", "successor", "Saved successor event.",
                    events=event, expected_automatic=expected,
                )

        self.assertEqual(self.posts(), [])

    def test_successor_generation_change_before_send_blocks_saved_delivery(self):
        self.adopt()
        self.add_pending_event()
        calls = {"count": 0}

        def successor_status(_body):
            calls["count"] += 1
            if calls["count"] == 4:
                control = self.stub.automatic_admissions["successor"]
                self.stub.automatic_admissions["successor"] = {**control, "generation": "changed-after-prepare"}
            return 200, status("successor")

        self.stub.set_routes([
            ("GET", "/api/sessions", 200, self.infos),
            ("GET", "/api/sessions/retired/status", 200, self.retired_status),
            ("GET", "/api/sessions/successor/status", 200, successor_status),
            ("POST", "/api/sessions/retired/archive", 200, self.archive_reply),
            PROMPTS,
        ])

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/retired/archive"])
        record = self.state(self.stream)["deliveries"][self.state(self.stream)["tick_delivery"]]
        self.assertEqual(record["state"], "blocked")

    def test_explicit_drive_off_prevents_native_queries(self):
        self.adopt()
        self.run_streams("drive", "etl", "off")
        self.stub.requests.clear()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual(self.stub.requests, [])

    def test_archive_receipt_conflicting_with_live_listing_remains_a_diagnostic(self):
        self.adopt()
        self.stub.simulate_session_lifecycle = False
        self.routes()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], [
            "/api/sessions/retired/archive", "/api/sessions/successor/prompt",
        ])
        observed = self.run_streams("status", "etl", "--json")
        self.assertEqual(observed.returncode, 0, observed.stderr)
        entry, = json.loads(observed.stdout)["streams"]
        self.assertEqual(entry["nativeReconciliations"][0]["disposition"], "archived")
        self.assertIn("still live", entry["nativeReconciliations"][0]["detail"].lower())
        self.assertNotIn("dispatchBlockers", entry)

    def test_unsafe_predecessor_skips_archive_without_blocking_successor(self):
        self.adopt()
        self.retired_status = {**self.retired_status, "isStreaming": True}
        self.routes()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/successor/prompt"])

    def test_unregistered_native_candidate_remains_a_dispatch_fence(self):
        self.adopt()
        self.infos.append(info("unregistered", str(self.stream), self.log_path("unregistered")))
        self.routes()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 1)
        self.assertEqual(self.posts(), [])
        self.assertIn("unregistered coordinator candidate", ticked.stderr)

    def test_duplicate_successor_identity_still_blocks_dispatch(self):
        self.adopt()
        self.infos.append(self.infos[1].copy())
        self.routes()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 1)
        self.assertEqual(self.posts(), [])
        self.assertIn("successor has no unique exact native identity", ticked.stderr)

    def test_ambiguous_retired_identity_does_not_block_exact_successor(self):
        self.adopt()
        self.infos.append(self.infos[0].copy())
        self.routes()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 0, ticked.stderr)
        self.assertEqual([path for path, _ in self.posts()], ["/api/sessions/successor/prompt"])

    def test_ambiguous_successor_identity_blocks_before_retired_archive(self):
        self.adopt()
        self.infos.append(self.infos[1].copy())
        self.routes()
        self.add_pending_event()

        ticked = self.tick("2026-11-03T00:01:00Z")

        self.assertEqual(ticked.returncode, 1)
        self.assertEqual(self.posts(), [])
        self.assertIn("successor has no unique exact native identity", ticked.stderr)
