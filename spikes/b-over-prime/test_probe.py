import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import unittest

from probe import Intake, Journal, Wire, dispatch


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="prime-t4-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "intake.sqlite3"
        self.journal = Journal(self.path)
        self.addCleanup(self.journal.close)
        self.ask = Intake("session-1", "user", "message-1", "follow_up", "Keep the original ask")

    def test_record_is_committed_before_dispatch_and_duplicate_does_not_send(self):
        observed = []

        def send(kind, **fields):
            with sqlite3.connect(self.path) as reader:
                observed.extend(reader.execute("SELECT source_id, body, state FROM intake").fetchall())
            self.assertEqual((kind, fields), ("follow_up", {
                "activeSessionId": "session-1", "message": "Keep the original ask"}))
            return {"success": True, "data": {"queued": True}}

        first = dispatch(self.journal, self.ask, send)
        second = dispatch(self.journal, self.ask, lambda *a, **k: self.fail("duplicate sent"))
        self.assertEqual(observed, [("message-1", "Keep the original ask", "dispatch_uncertain")])
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "admitted")
        self.assertEqual(first["reply"], {"success": True, "data": {"queued": True}})

    def test_uncertain_send_survives_reopen_and_is_not_retried(self):
        def disconnect(*args, **kwargs):
            raise ConnectionError("acknowledgement lost")

        with self.assertRaisesRegex(ConnectionError, "acknowledgement lost"):
            dispatch(self.journal, self.ask, disconnect)
        with Journal(self.path) as reopened:
            row = dispatch(reopened, self.ask, lambda *a, **k: self.fail("uncertain send retried"))
        self.assertEqual(row["state"], "dispatch_uncertain")
        self.assertIsNone(row["reply"])

    def test_same_identity_with_changed_body_or_lane_is_rejected(self):
        dispatch(self.journal, self.ask, lambda *a, **k: {"success": True})
        for body, lane in [("Changed ask", "follow_up"), (self.ask.body, "steer")]:
            with self.subTest(body=body, lane=lane), self.assertRaisesRegex(ValueError, "identity conflict"):
                dispatch(self.journal, Intake("session-1", "user", "message-1", lane, body),
                         lambda *a, **k: self.fail("conflict sent"))

    def test_provider_refusal_is_retained_as_rejection_not_completion(self):
        row = dispatch(self.journal, self.ask, lambda *a, **k: {
            "success": False, "error": "No API key found for openai-codex."})
        self.assertEqual(row["state"], "rejected")
        self.assertEqual(row["reply"], {
            "success": False, "error": "No API key found for openai-codex."})

    def test_bad_response_leaves_uncertainty(self):
        with self.assertRaisesRegex(ValueError, "success must be boolean"):
            dispatch(self.journal, self.ask, lambda *a, **k: {"success": "yes"})
        row = self.journal.lookup(self.ask)
        self.assertEqual(row["state"], "dispatch_uncertain")

    def test_storage_error_prevents_dispatch(self):
        self.journal.db.execute("PRAGMA query_only=ON")
        with self.assertRaises(sqlite3.OperationalError):
            dispatch(self.journal, self.ask, lambda *a, **k: self.fail("unpersisted send"))

    def test_source_namespace_and_session_are_part_of_identity(self):
        for session, kind in [("session-1", "user"), ("session-1", "automation"), ("session-2", "user")]:
            dispatch(self.journal, Intake(session, kind, "message-1", "prompt", "Same text"),
                     lambda *a, **k: {"success": True})
        self.assertEqual(self.journal.db.execute("SELECT count(*) FROM intake").fetchone()[0], 3)


class WireTests(unittest.TestCase):
    def test_event_and_unrelated_reply_do_not_replace_correlated_reply(self):
        with tempfile.TemporaryDirectory(prefix="prime-t4-wire-") as root:
            path = str(Path(root) / "daemon.sock")
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(path)
                server.listen()
                errors = []

                def fixture():
                    try:
                        conn, _ = server.accept()
                        with conn, conn.makefile("rb") as reader:
                            conn.sendall(b'{"type":"daemon_hello","protocol":{"name":"prime-agent.daemon","version":7},"schemaRevision":30}\n')
                            request = json.loads(reader.readline())
                            self.assertEqual(request["command"], {"type": "list", "cwd": "/test"})
                            frames = [
                                {"type": "session_event", "event": {"type": "turn_end"}},
                                {"type": "response", "id": "other", "command": "list", "success": True},
                                {"type": "response", "id": request["id"], "command": "list", "success": True,
                                 "data": {"sessions": []}},
                            ]
                            conn.sendall("".join(json.dumps(f) + "\n" for f in frames).encode())
                    except BaseException as exc:
                        errors.append(exc)

                thread = threading.Thread(target=fixture)
                thread.start()
                with Wire(path, timeout=3) as wire:
                    response = wire.request("list", cwd="/test")
                    self.assertEqual(response["data"], {"sessions": []})
                    self.assertEqual(wire.events, [{"type": "session_event", "event": {"type": "turn_end"}}])
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
