"""Normal wakes reuse one coordinator; explicit replacement needs a current checkpoint."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from support import ROOT, git

sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import replacement, threads
from engine.project import load_project, stream_lock
from tick_support import PROMPTS, TickCase, info, row, status


class CoordinatorReuseTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.worker = self.fx.alpha_wt
        self.stream = self.make_stream(self.home, "etl", row("current", "coordinator", str(self.home / "etl")) + row("worker", "worker", str(self.worker), branch="feat-a"))
        (self.worker / ".stream").write_text(str(self.stream) + "\n")
        self.write_log("current", str(self.stream))
        self.routes()

    def routes(self, *, tokens=1000, modified="2026-10-06T11:00:00Z", streaming=False, pending=0, callbacks=()):
        body = status("current", tokens=tokens, streaming=streaming)
        body["pendingMessageCount"] = pending
        body["rotationSafety"] = {"entryId": "checkpoint-ack", "callbacksKnown": True, "nativeChildCallbacks": list(callbacks)}
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [info("current", str(self.stream), self.log_path("current"), modified), info("worker", str(self.worker), self.log_path("worker"))]),
            ("GET", "/api/sessions/current/status", 200, body),
            ("GET", "/api/sessions/worker/status", 200, status("worker")),
            ("POST", "/api/sessions/current/archive", 200, {"archived": True, "automaticAdmission": {"sessionId": "current", "cwd": str(self.stream), "generation": "frozen-current", "allowed": False, "durable": True}}),
            ("POST", "/api/sessions", 200, {"id": "successor", "cwd": str(self.stream)}),
            ("GET", "/api/sessions/successor/status", 200, status("successor")),
            PROMPTS,
        ])

    def checkpoint(self):
        path = self.stream / "handover/coordinator/current.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("session: current\nCurrent checkpoint. Worker remains in its recorded owned worktree.\n")
        result = self.run_streams("checkpoint", "etl", "--session", "current")
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)["checkpoint"]
        self.write_log("current", str(self.stream), {"role": "assistant", "content": [{"type": "text", "text": f"Rotation checkpoint ready: {identity}"}], "stopReason": "stop"})
        path = Path(self.log_path("current"))
        lines = [json.loads(line) for line in path.read_text().splitlines()]
        lines[-1]["id"] = "checkpoint-ack"
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        self.stub.requests.clear()
        return identity

    def test_legacy_warm_fields_are_ignored_not_reassigned_as_new_thresholds(self):
        config = self.project_file
        config.write_text(config.read_text().replace("[caps]\n", '[caps]\nwarm_context_tokens = "retired ignored value"\nwarm_idle_hours = 0\n', 1))
        self.routes(tokens=180000, modified="2026-01-01T00:00:00Z")
        result = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([path for method, path, _, _ in self.stub.requests if method == "POST"], ["/api/sessions/current/prompt"])
        self.assertEqual(self.rows(self.stream).splitlines()[1].split("\t")[0], "current")

    def test_high_context_and_old_age_never_replace_the_designated_session(self):
        for tokens, modified in ((180000, "2026-10-06T11:59:00Z"), (1000, "2026-10-01T00:00:00Z")):
            with self.subTest(tokens=tokens, modified=modified):
                self.routes(tokens=tokens, modified=modified)
                (self.stream / "log/tick-state.json").unlink(missing_ok=True)
                result = self.tick("2026-10-06T12:00:00Z")
                self.assertEqual(result.returncode, 0, result.stderr)
                posts = [(path, body) for method, path, _, body in self.stub.requests if method == "POST"]
                self.assertEqual([path for path, _ in posts], ["/api/sessions/current/prompt"])
                self.assertEqual(posts[0][1]["text"], "pi-streams tick 2026-10-06T12:00:00Z:\nidle worker worker")
                self.assertEqual(self.rows(self.stream).splitlines()[1].split("\t")[0], "current")

    def test_busy_queue_or_native_callback_ownership_refuses_without_abort_archive_or_spawn(self):
        self.checkpoint()
        for options in ({"streaming": True}, {"pending": 1}, {"callbacks": ["native-child"]}):
            with self.subTest(options=options):
                self.routes(**options)
                self.stub.requests.clear()
                result = self.run_streams("rotate", "etl")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("callback" if "callbacks" in options else "busy", result.stderr)
                self.assertNotIn("checkpoint is required", result.stderr)
                self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
                self.assertEqual(self.rows(self.stream).splitlines()[1].split("\t")[0], "current")

    def test_missing_or_stale_checkpoint_refuses_before_retirement(self):
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("checkpoint", result.stderr)
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.checkpoint()
        state = self.stream / "STATE.md"
        state.write_bytes(state.read_bytes().replace(b"<the single human-authorized outcome>", b"A newer authorized goal."))
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("checkpoint", result.stderr)
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])

    def test_prearchive_retry_refuses_changed_handover_instead_of_guessing_through_checkpoint(self):
        self.checkpoint()
        with mock.patch.dict(os.environ, self.env, clear=True), stream_lock(self.stream):
            project = load_project(self.project_file)
            with mock.patch("engine.piweb.archive", side_effect=OSError("labelled interruption before native archive")):
                with self.assertRaisesRegex(OSError, "before native archive"):
                    replacement.rotate_locked(self.index, project, "etl")
        self.assertEqual(self.state(self.stream)["coordinator_rotation"]["phase"], "archiving")
        report = self.stream / "handover/coordinator/current.md"
        report.write_text(report.read_text() + "New non-STATE checkpoint input after interruption.\n")
        before = self.rows(self.stream)
        self.stub.requests.clear()
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("checkpoint", result.stderr)
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.assertEqual(self.rows(self.stream), before)

    def test_nonregular_native_checkpoint_evidence_is_refused_without_blocking(self):
        self.checkpoint()
        native = Path(self.log_path("current"))
        native.unlink()
        os.mkfifo(native)
        try:
            result = subprocess.run([str(ROOT / "bin/pi-streams"), "rotate", "etl"], env=self.env, capture_output=True, text=True, timeout=3)
        except subprocess.TimeoutExpired:
            self.fail("rotation blocked on nonregular native checkpoint evidence")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("regular", result.stderr)
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])

    def test_archive_then_failed_spawn_recovers_only_on_explicit_retry(self):
        self.checkpoint()
        self.stub.set_routes([("POST", "/api/sessions", 500, {"error": "labelled private spawn rejection"}), *self.stub.routes])
        failed = self.run_streams("rotate", "etl")
        self.assertEqual(failed.returncode, 1)
        data = self.state(self.stream)
        self.assertEqual(data["coordinator_rotation"]["phase"], "archived")
        self.assertEqual(self.rows(self.stream).splitlines()[1].split("\t")[8], "archived")
        self.stub.requests.clear()
        self.routes()
        tick = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.stub.requests.clear()
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"))
        self.assertEqual([path for method, path, _, _ in self.stub.requests if method == "POST"].count("/api/sessions/current/archive"), 0)
        self.assertEqual(self.state(self.stream)["coordinator_rotation"]["phase"], "complete")

    def test_accepted_successor_opening_is_not_replayed_after_registry_publication_failure(self):
        self.checkpoint()
        with mock.patch.dict(os.environ, self.env, clear=True), stream_lock(self.stream):
            project = load_project(self.project_file)
            with mock.patch.object(threads, "save_threads", side_effect=OSError("labelled successor registry failure")):
                with self.assertRaisesRegex(OSError, "successor registry"):
                    replacement.rotate_locked(self.index, project, "etl")
        start = self.state(self.stream)["session_start"]
        self.assertEqual((start["session"], start["phase"]), ("successor", "accepted"))
        self.stub.requests.clear()
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"))
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.assertNotIn("session_start", self.state(self.stream))

    def test_clean_checkpoint_rotates_once_and_a_completed_retry_does_not_prompt_again(self):
        self.checkpoint()
        before_worker = git(self.fx.alpha, self.env, "status", "--porcelain")
        result = self.run_streams("rotate", "etl")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.endswith("successor\n"))
        posts = [(path, body) for method, path, _, body in self.stub.requests if method == "POST"]
        self.assertEqual([path for path, _ in posts].count("/api/sessions/current/archive"), 1)
        self.assertEqual([path for path, _ in posts].count("/api/sessions"), 1)
        self.assertEqual([path for path, _ in posts].count("/api/sessions/successor/prompt"), 1)
        self.assertIn("AGENTS.md", posts[-1][1]["text"])
        self.assertIn("STATE.md", posts[-1][1]["text"])
        self.assertNotIn("Read STREAM.md", posts[-1][1]["text"])
        self.stub.requests.clear()
        again = self.run_streams("rotate", "etl")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertTrue(again.stdout.endswith("successor\n"))
        self.assertEqual([request for request in self.stub.requests if request[0] == "POST"], [])
        self.assertEqual(git(self.fx.alpha, self.env, "status", "--porcelain"), before_worker)
