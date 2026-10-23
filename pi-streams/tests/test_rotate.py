"""Explicit rotation archives one checkpointed coordinator without abort or worker writes."""
from __future__ import annotations

from support import git
from tick_support import HEADER, TickCase, info, row, status


class RotateTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.stream = self.make_stream(self.home, "etl", row("coord-1", "coordinator", str(self.home / "etl")))
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [info("coord-1", str(self.stream), self.log_path("coord-1"))]),
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1")),
            ("POST", "/api/sessions", 200, {"id": "coord-2", "cwd": str(self.stream)}),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2")),
            ("POST", "/api/sessions/coord-2/prompt", 200, {"accepted": True}),
        ])

    def test_rotate_archives_old_and_spawns_new(self) -> None:
        self.author_coordinator_checkpoint(self.stream, "coord-1")
        rotated = self.run_streams("rotate", "etl")
        self.assertEqual(rotated.returncode, 0, rotated.stderr)
        self.assertEqual(rotated.stdout, "http://127.0.0.1:8504\ncoord-2\n")
        posted = [(path, body) for method, path, _, body in self.stub.requests if method == "POST"]
        self.assertEqual([path for path, _ in posted], [
            "/api/sessions/coord-1/archive", "/api/sessions", "/api/sessions/coord-2/model",
            "/api/sessions/coord-2/thinking-level", "/api/sessions/coord-2/prompt",
        ])
        self.assertEqual(posted[0][1], {"expectedIdle": {"sessionId": "coord-1", "cwd": str(self.stream), "entryId": "checkpoint-ack-coord-1", "generation": "fixture-coord-1"}})
        self.assertEqual(posted[1][1], {"cwd": str(self.stream)})
        self.assertEqual(posted[2][1], {"provider": "openai-codex", "modelId": "gpt-6-astra"})
        self.assertEqual(posted[3][1], {"level": "xhigh"})
        self.assertIn(str(self.stream / "AGENTS.md"), posted[4][1]["text"])
        self.assertIn(str(self.stream / "STATE.md"), posted[4][1]["text"])
        self.assertNotIn("Read STREAM.md", posted[4][1]["text"])
        self.assertEqual([line.split("\t")[0:2] + [line.split("\t")[8]] for line in self.rows(self.stream).splitlines()[1:]], [
            ["coord-1", "coordinator", "archived"], ["coord-2", "coordinator", "active"],
        ])
        self.assertEqual(git(self.stream, self.env, "log", "-1", "--format=%s").strip(), "pi-streams rotate etl")
        self.assertEqual(git(self.stream, self.env, "status", "--porcelain"), "")

    def test_rerun_after_a_failed_spawn_finishes_the_rotation(self) -> None:
        self.author_coordinator_checkpoint(self.stream, "coord-1")
        self.stub.set_routes([("POST", "/api/sessions", 500, {"error": "spawn failed"}), *self.stub.routes])
        failed = self.run_streams("rotate", "etl")
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(self.rows(self.stream), HEADER + row("coord-1", "coordinator", str(self.stream), status="archived"))
        self.stub.requests.clear()
        self.stub.set_routes([item for item in self.stub.routes if item[:3] != ("POST", "/api/sessions", 500)])
        again = self.run_streams("rotate", "etl")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(again.stdout, "http://127.0.0.1:8504\ncoord-2\n")
        posted = [path for method, path, _, _ in self.stub.requests if method == "POST"]
        self.assertEqual(posted.count("/api/sessions"), 1)
        self.assertEqual(posted.count("/api/sessions/coord-2/prompt"), 1)
        self.assertNotIn("/api/sessions/coord-1/archive", posted)
        self.assertEqual([line.split("\t")[0] + " " + line.split("\t")[8] for line in self.rows(self.stream).splitlines()[1:]], ["coord-1 archived", "coord-2 active"])

    def test_rotate_without_any_coordinator_points_at_new(self) -> None:
        (self.stream / "threads.tsv").write_text(HEADER)
        self.stub.requests.clear()
        refused = self.run_streams("rotate", "etl")
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(refused.stderr, "stream etl has no coordinator; run pi-streams new etl\n")
        self.assertEqual(self.stub.requests, [])
