"""Status isolates stream diagnostics without changing stream artifacts."""
from __future__ import annotations

import json

from support import EngineCase, git, seed_ratified_stream, snapshot
from test_status import HEADER, live


class StatusToleranceTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        result = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(result.returncode, 0, result.stderr)

    def stream(self, name: str, *, drive: dict | None = None):
        stream = self.register_stream(name)
        seed_ratified_stream(stream, self.root.name)
        git(stream, self.env, "init")
        (stream / "log").mkdir(exist_ok=True)
        (stream / "threads.tsv").write_text(
            HEADER + f"{name}-coord\tcoordinator\t\t{stream}\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-23T00:00:00Z\n"
        )
        if drive is not None:
            (stream / "log/tick-state.json").write_text(json.dumps({"drive": drive}))
        return stream

    def routes(self, streams, *, archived=(), unregistered=()) -> None:
        listing = [
            {"id": f"{stream.name}-coord", "cwd": str(stream), "archived": stream.name in archived}
            for stream in streams
        ]
        listing += [{"id": "unregistered-candidate", "cwd": str(stream)} for stream in unregistered]
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, listing),
            *[("GET", f"/api/sessions/{stream.name}-coord/status", 200, live(f"{stream.name}-coord", 2)) for stream in streams],
        ])

    def report(self, *args):
        result = self.run_streams("status", *args, "--json")
        self.assertEqual((result.returncode, result.stderr), (0, ""), result.stdout)
        return json.loads(result.stdout)["streams"]

    def assert_diagnostic(self, entry, message: str, error_type: str = "StreamsError") -> None:
        self.assertEqual(entry["error"]["type"], error_type)
        self.assertIn(message, entry["error"]["message"])
        for field in ("coordinator", "threads", "coordinatorCostShare"):
            self.assertIsNone(entry[field], field)

    def assert_read_only(self, before) -> None:
        self.assertEqual(snapshot(self.home), before)
        self.assertTrue(all(method == "GET" for method, _path, _query, _body in self.stub.requests))

    def test_default_status_lists_malformed_archived_unregistered_and_later_healthy_streams(self) -> None:
        malformed = self.stream("cb-tslite-fix-mass-cancel", drive={"enabled": True, "run_id": "fixture-run", "remote_state": "on-unconfirmed"})
        path = malformed / "STATE.md"
        path.write_text("Historical content before Goals.\n" + path.read_text())
        archived = self.stream("fill", drive={"enabled": False, "remote_state": "off-confirmed", "remote_generation": "stop-2"})
        unregistered = self.stream("pi-streams-harness")
        healthy = self.stream("later-healthy")
        self.routes([malformed, archived, unregistered, healthy], archived=["fill"], unregistered=[unregistered])
        before = snapshot(self.home)

        streams = self.report()
        self.assertEqual([entry["id"] for entry in streams], [malformed.name, archived.name, unregistered.name, healthy.name])
        self.assert_diagnostic(streams[0], "content before Goals")
        self.assert_diagnostic(streams[1], "archived", "TerminalSession")
        self.assert_diagnostic(streams[2], "unregistered")
        self.assertEqual([(entry["drive"]["known"], entry["drive"]["enabled"], entry["drive"]["remote_state"]) for entry in streams], [
            (True, True, "on-unconfirmed"), (True, False, "off-confirmed"),
            (True, False, "not-requested"), (True, False, "not-requested"),
        ])
        self.assertNotIn("ratified", streams[3])
        self.assertEqual(streams[3]["coordinator"]["session"], "later-healthy-coord")
        self.assertEqual(streams[3]["coordinator"]["model"], "gpt-6-astra")
        self.assertEqual(streams[3]["coordinator"]["thinkingLevel"], "xhigh")
        self.assertNotIn("error", streams[3])
        text = self.run_streams("status")
        self.assertEqual((text.returncode, text.stderr), (0, ""))
        for stream in (malformed, archived, unregistered):
            self.assertIn(f"{stream.name}\terror=", text.stdout)
        for stream in (malformed, archived, unregistered, healthy):
            self.assertIn(f"{stream.name}\tdrive=", text.stdout)
        self.assertIn("later-healthy-coord", text.stdout)
        self.assertIn("remote=on-unconfirmed", text.stdout)
        self.assertNotIn("ratified=", text.stdout)
        self.assert_read_only(before)

    def test_named_malformed_stream_is_a_diagnostic_not_an_exception(self) -> None:
        stream = self.stream("malformed")
        (stream / "STATE.md").write_bytes(b"\xff")
        before = snapshot(self.home)
        entry, = self.report("malformed")
        self.assertEqual(entry["id"], "malformed")
        self.assertIn("UTF-8", entry["error"]["message"])
        self.assertNotIn("ratified", entry)
        self.assertEqual(entry["drive"]["known"], True)
        self.assertEqual(entry["drive"]["remote_state"], "not-requested")
        self.assert_read_only(before)

    def test_native_listing_error_reports_every_stream_and_preserves_drive_observation(self) -> None:
        one = self.stream("one", drive={"enabled": True, "run_id": "run-one", "remote_state": "on-confirmed", "remote_generation": "epoch-1"})
        two = self.stream("two")
        self.stub.set_routes([("GET", "/api/sessions", 503, {"error": "fixture native listing unavailable"})])
        before = snapshot(self.home)
        entries = self.report()
        self.assertEqual([entry["id"] for entry in entries], [one.name, two.name])
        for entry in entries:
            self.assert_diagnostic(entry, "fixture native listing unavailable")
            self.assertEqual(entry["drive"]["known"], True)
        self.assertEqual(entries[0]["drive"]["remote_state"], "on-confirmed")
        text = self.run_streams("status")
        self.assertEqual((text.returncode, text.stderr), (0, ""))
        self.assertEqual(text.stdout.count("fixture native listing unavailable"), 2)
        self.assert_read_only(before)

    def test_unknown_drive_does_not_imply_disabled_or_remote_confirmation(self) -> None:
        bad = self.stream("bad-drive")
        good = self.stream("good")
        self.routes([bad, good])
        for metadata in ('{"drive": {"enabled": "yes"}}', '{"drive":', '[]'):
            with self.subTest(metadata=metadata):
                (bad / "log/tick-state.json").write_text(metadata)
                before = snapshot(self.home)
                entries = self.report()
                driving = entries[0]["drive"]
                self.assertEqual((driving["known"], driving["enabled"], driving["remote_state"]), (False, None, "unknown"))
                self.assertEqual(driving["error"]["type"], "StreamsError")
                self.assertEqual(entries[1]["coordinator"]["session"], "good-coord")
                text = self.run_streams("status")
                self.assertEqual((text.returncode, text.stderr), (0, ""))
                self.assertIn("bad-drive\tdrive=unknown", text.stdout)
                self.assertIn("drive-error=", text.stdout)
                self.assert_read_only(before)

    def test_missing_legacy_artifact_is_local_and_later_stream_is_visible(self) -> None:
        self.register_stream("missing-legacy")
        healthy = self.stream("healthy")
        self.routes([healthy])
        entries = self.report()
        self.assertEqual(entries[0]["error"]["type"], "FileNotFoundError")
        self.assertNotIn("ratified", entries[0])
        self.assertEqual(entries[1]["coordinator"]["session"], "healthy-coord")

    def test_retired_coordinator_still_has_a_visible_drive_state(self) -> None:
        stream = self.stream("retired")
        path = stream / "threads.tsv"
        path.write_text(path.read_text().replace("\tactive\t", "\tarchived\t"))
        self.routes([stream], archived=["retired"])
        entry, = self.report("retired")
        self.assertIsNone(entry["coordinator"])
        self.assertNotIn("error", entry)
        self.assertEqual(entry["drive"]["known"], True)
        text = self.run_streams("status", "retired")
        self.assertEqual((text.returncode, text.stderr), (0, ""))
        self.assertIn("retired\tdrive=off\tdelivery=-\tremote=not-requested\n", text.stdout)

    def test_global_index_and_selection_errors_remain_command_failures(self) -> None:
        for args, message in ((["--home", str(self.tmp / "missing-index")], "no index"), (["unknown-stream"], "no stream")):
            with self.subTest(args=args):
                result = self.run_streams("status", *args, "--json")
                self.assertEqual((result.returncode, result.stdout), (1, ""))
                self.assertIn(message, result.stderr)
        (self.index / "streams.tsv").write_text("invalid header\n")
        result = self.run_streams("status", "--json")
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("header", result.stderr)
        self.assertEqual(self.stub.requests, [])

    def test_missing_stream_directory_has_unknown_drive_and_does_not_hide_later_streams(self) -> None:
        self.register_stream("missing-directory").rmdir()
        healthy = self.stream("healthy")
        self.routes([healthy])
        entries = self.report()
        self.assertEqual([entry["id"] for entry in entries], ["missing-directory", "healthy"])
        self.assertEqual(entries[0]["error"]["type"], "FileNotFoundError")
        self.assertEqual(entries[0]["drive"]["known"], False)
        self.assertIsNone(entries[0]["drive"]["enabled"])
        self.assertEqual(entries[0]["drive"]["remote_state"], "unknown")
        self.assertIn("stream directory is unavailable", entries[0]["drive"]["error"]["message"])
        self.assertEqual(entries[1]["coordinator"]["session"], "healthy-coord")

    def test_global_home_configuration_errors_are_not_stream_diagnostics(self) -> None:
        (self.index / "homes").write_bytes(b"\xff")
        result = self.run_streams("status", "--json")
        self.assertEqual((result.returncode, result.stdout), (1, ""))
        self.assertIn("utf-8", result.stderr)
        self.assertEqual(self.stub.requests, [])

    def test_empty_index_preserves_no_streams_text(self) -> None:
        self.assertEqual(self.report(), [])
        result = self.run_streams("status")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "no streams\n", ""))
