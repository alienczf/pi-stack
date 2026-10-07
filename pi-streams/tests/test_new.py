"""pi-streams new spawns, adopts, or refuses a coordinator."""
from __future__ import annotations

import urllib.parse
from pathlib import Path

from support import EngineCase, git

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"


def status_body(sid: str, model_id: str = "gpt-6-astra", thinking: str = "xhigh") -> dict[str, object]:
    return {
        "sessionId": sid,
        "isStreaming": False,
        "contextUsage": {"tokens": 10},
        "model": {"provider": "openai-codex", "id": model_id},
        "thinkingLevel": thinking,
        "cost": 0,
    }


class NewTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.stub.requests.clear()

    def stream(self) -> str:
        return str((self.home / "etl").resolve())

    def assert_call(self, index: int, method: str, path: str, body: object, cwd: str | None = None) -> None:
        got_method, got_path, query, got_body = self.stub.requests[index]
        self.assertEqual(got_method, method)
        self.assertEqual(got_path, path)
        self.assertEqual(got_body, body)
        if cwd is None:
            self.assertEqual(query, "")
        else:
            self.assertEqual(urllib.parse.parse_qs(query), {"cwd": [cwd]})

    def test_new_spawns_then_second_new_spawns_nothing(self) -> None:
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "coord-1"}),
            ("GET", "/api/sessions/coord-1/status", 200, status_body("coord-1")),
            ("POST", "/api/sessions/coord-1/prompt", 200, {"accepted": True}),
        ])
        proc = self.run_streams("new", "etl")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "http://127.0.0.1:8504\ncoord-1\n")
        stream = self.stream()
        self.assertEqual(len(self.stub.requests), 6)
        self.assert_call(0, "GET", "/api/sessions", None, cwd=stream)
        self.assert_call(1, "POST", "/api/sessions", {"cwd": stream})
        self.assert_call(
            2,
            "POST",
            "/api/sessions/coord-1/model",
            {"provider": "openai-codex", "modelId": "gpt-6-astra"},
        )
        self.assert_call(3, "POST", "/api/sessions/coord-1/thinking-level", {"level": "xhigh"})
        self.assert_call(4, "GET", "/api/sessions/coord-1/status", None)
        self.assert_call(5, "POST", "/api/sessions/coord-1/prompt", {"text": "/skill:stream-kickoff"})
        rows = (self.home / "etl" / "threads.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(rows[0], HEADER.rstrip("\n"))
        cells = rows[1].split("\t")
        self.assertEqual(
            cells[:9],
            ["coord-1", "coordinator", "", stream, "", "", "openai-codex/gpt-6-astra", "xhigh", "active"],
        )
        self.assertRegex(cells[9], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(len(cells), 10)
        self.assertTrue((self.home / "etl" / "STREAM.md").read_text(encoding="utf-8").startswith("ratified: no\n"))
        self.assertEqual(git(Path(self.stream()), self.env, "log", "-1", "--format=%s").strip(), "pi-streams new etl")
        self.assertEqual(git(Path(self.stream()), self.env, "rev-list", "--count", "HEAD").strip(), "1")
        head = git(Path(self.stream()), self.env, "rev-parse", "HEAD")
        before = len(self.stub.requests)
        again = self.run_streams("new", "etl")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(again.stdout, "http://127.0.0.1:8504\ncoord-1\n")
        self.assertEqual(self.stub.requests[before:], [])
        self.assertEqual(git(Path(self.stream()), self.env, "rev-parse", "HEAD"), head)

    def test_new_adopts_a_listed_session_without_spawn(self) -> None:
        stream = self.stream()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [{"id": "coord-existing", "cwd": stream, "messageCount": 12}]),
            ("GET", "/api/sessions/coord-existing/status", 200, status_body("coord-existing")),
            ("POST", "/api/sessions/coord-existing/prompt", 200, {"accepted": True}),
        ])
        proc = self.run_streams("new", "etl")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "http://127.0.0.1:8504\ncoord-existing\n")
        self.assertEqual(len(self.stub.requests), 4)
        self.assert_call(0, "GET", "/api/sessions", None, cwd=stream)
        self.assert_call(
            1,
            "POST",
            "/api/sessions/coord-existing/model",
            {"provider": "openai-codex", "modelId": "gpt-6-astra"},
        )
        self.assert_call(2, "POST", "/api/sessions/coord-existing/thinking-level", {"level": "xhigh"})
        self.assert_call(3, "GET", "/api/sessions/coord-existing/status", None)
        paths = [item[1] for item in self.stub.requests]
        self.assertNotIn("/api/sessions/coord-existing/prompt", paths)
        posted = [item for item in self.stub.requests if item[0] == "POST" and item[1] == "/api/sessions"]
        self.assertEqual(posted, [])

    def test_failed_kickoff_is_resent_and_archived_sessions_are_skipped(self) -> None:
        stream = self.stream()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "coord-1"}),
            ("GET", "/api/sessions/coord-1/status", 200, status_body("coord-1")),
            ("POST", "/api/sessions/coord-1/prompt", 503, {"error": "busy"}),
        ])
        failed = self.run_streams("new", "etl")
        self.assertEqual(failed.returncode, 1)
        self.assertEqual((self.home / "etl" / "threads.tsv").read_text(encoding="utf-8"), HEADER)
        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [
                {"id": "stale", "cwd": stream, "messageCount": 30, "archived": True},
                {"id": "coord-1", "cwd": stream, "messageCount": 0},
            ]),
            ("GET", "/api/sessions/coord-1/status", 200, status_body("coord-1")),
            ("POST", "/api/sessions/coord-1/prompt", 200, {"accepted": True}),
        ])
        again = self.run_streams("new", "etl")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(again.stdout, "http://127.0.0.1:8504\ncoord-1\n")
        self.assertEqual(
            [(method, path) for method, path, _query, _body in self.stub.requests],
            [
                ("GET", "/api/sessions"),
                ("POST", "/api/sessions/coord-1/model"),
                ("POST", "/api/sessions/coord-1/thinking-level"),
                ("GET", "/api/sessions/coord-1/status"),
                ("POST", "/api/sessions/coord-1/prompt"),
            ],
        )
        self.assert_call(4, "POST", "/api/sessions/coord-1/prompt", {"text": "/skill:stream-kickoff"})
        cells = (self.home / "etl" / "threads.tsv").read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(cells[:2], ["coord-1", "coordinator"])
        self.assertEqual(git(Path(self.stream()), self.env, "log", "-1", "--format=%s").strip(), "pi-streams new etl")

    def test_status_mismatch_fails_new(self) -> None:
        stream = self.stream()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "coord-1"}),
            ("GET", "/api/sessions/coord-1/status", 200, status_body("coord-1", model_id="gpt-6-luna")),
        ])
        proc = self.run_streams("new", "etl")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("gpt-6-luna", proc.stderr)
        self.assertIn("gpt-6-astra", proc.stderr)
        self.assertEqual(len(self.stub.requests), 5)
        self.assert_call(0, "GET", "/api/sessions", None, cwd=stream)
        self.assert_call(1, "POST", "/api/sessions", {"cwd": stream})
        self.assert_call(4, "GET", "/api/sessions/coord-1/status", None)
        prompts = [item for item in self.stub.requests if item[1].endswith("/prompt")]
        self.assertEqual(prompts, [])
        self.assertEqual((self.home / "etl" / "threads.tsv").read_text(encoding="utf-8"), HEADER)
        self.assertIn("??", git(Path(self.stream()), self.env, "status", "--porcelain"))
        with self.assertRaises(AssertionError):
            git(Path(self.stream()), self.env, "rev-parse", "--verify", "HEAD")


if __name__ == "__main__":
    unittest.main()
