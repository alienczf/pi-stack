"""rotate archives the coordinator and starts a fresh one."""
from __future__ import annotations

import urllib.parse

from support import EngineCase, git

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"
OLD = "coord-1\tcoordinator\t\t/wt\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T00:00:00Z\n"
ROTATION = (
    "You are the new coordinator for stream etl. "
    "Your memory is the files in this folder. Read STATE.md, then continue."
)


def status_body(sid: str) -> dict[str, object]:
    return {
        "sessionId": sid,
        "isStreaming": False,
        "contextUsage": {"tokens": 10},
        "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
        "thinkingLevel": "xhigh",
        "cost": 0,
    }


class RotateTests(EngineCase):
    def test_rotate_archives_old_and_spawns_new(self) -> None:
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stream_dir = (self.home / "etl").resolve()
        stream_dir.mkdir()
        (stream_dir / "STREAM.md").write_text("ratified: no\n", encoding="utf-8")
        (stream_dir / "STATE.md").write_text("# STATE\n", encoding="utf-8")
        (stream_dir / "threads.tsv").write_text(HEADER + OLD, encoding="utf-8")
        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [{"id": "coord-1", "cwd": str(stream_dir)}]),
            ("POST", "/api/sessions", 200, {"id": "coord-2"}),
            ("GET", "/api/sessions/coord-2/status", 200, status_body("coord-2")),
            ("POST", "/api/sessions/coord-2/prompt", 200, {"accepted": True}),
        ])
        rotated = self.run_streams("rotate", "etl")
        self.assertEqual(rotated.returncode, 0, rotated.stderr)
        self.assertEqual(rotated.stdout, "http://127.0.0.1:8504\ncoord-2\n")
        self.assertEqual(len(self.stub.requests), 7)
        self.assertEqual(
            self.stub.requests[0],
            ("POST", "/api/sessions/coord-1/archive", "", {}),
        )
        method, path, query, body = self.stub.requests[1]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/api/sessions")
        self.assertEqual(urllib.parse.parse_qs(query), {"cwd": [str(stream_dir)]})
        self.assertIsNone(body)
        self.assertEqual(self.stub.requests[2], ("POST", "/api/sessions", "", {"cwd": str(stream_dir)}))
        self.assertEqual(
            self.stub.requests[3],
            (
                "POST",
                "/api/sessions/coord-2/model",
                "",
                {"provider": "openai-codex", "modelId": "gpt-6-astra"},
            ),
        )
        self.assertEqual(
            self.stub.requests[4],
            ("POST", "/api/sessions/coord-2/thinking-level", "", {"level": "xhigh"}),
        )
        self.assertEqual(self.stub.requests[5], ("GET", "/api/sessions/coord-2/status", "", None))
        self.assertEqual(
            self.stub.requests[6],
            ("POST", "/api/sessions/coord-2/prompt", "", {"text": ROTATION}),
        )
        prompted = [item[1] for item in self.stub.requests if item[1].endswith("/prompt")]
        self.assertEqual(prompted, ["/api/sessions/coord-2/prompt"])
        lines = (stream_dir / "threads.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[1].split("\t")[0], "coord-1")
        self.assertEqual(lines[1].split("\t")[8], "archived")
        self.assertEqual(lines[2].split("\t")[0], "coord-2")
        self.assertEqual(lines[2].split("\t")[1], "coordinator")
        self.assertEqual(lines[2].split("\t")[8], "active")
        self.assertEqual(git(self.home, self.env, "log", "-1", "--format=%s").strip(), "pi-streams rotate etl")


if __name__ == "__main__":
    unittest.main()
