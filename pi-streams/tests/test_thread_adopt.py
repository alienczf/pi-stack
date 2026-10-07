"""thread adopt records a session and does not prompt it."""
from __future__ import annotations

import urllib.parse
from pathlib import Path

from support import EngineCase, git

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"


class AdoptTests(EngineCase):
    def test_adopt_sends_no_prompt(self) -> None:
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stream_dir = (self.home / "etl").resolve()
        stream_dir.mkdir()
        (stream_dir / "STREAM.md").write_text("ratified: no\n", encoding="utf-8")
        (stream_dir / "threads.tsv").write_text(HEADER, encoding="utf-8")
        worktree = self.fx.alpha_wt.resolve()
        base = git(worktree, self.env, "rev-parse", "HEAD").strip()
        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [{"id": "sess-adopt", "cwd": str(worktree)}]),
            (
                "GET",
                "/api/sessions/sess-adopt/status",
                200,
                {
                    "sessionId": "sess-adopt",
                    "isStreaming": False,
                    "contextUsage": {"tokens": 4},
                    "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
                    "thinkingLevel": "xhigh",
                    "cost": 0,
                },
            ),
        ])
        adopted = self.run_streams(
            "thread",
            "adopt",
            "etl",
            "sess-adopt",
            "--worktree",
            str(worktree),
            "--role",
            "review",
        )
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        self.assertEqual(adopted.stdout, "sess-adopt\n")
        self.assertEqual(len(self.stub.requests), 2)
        method, path, query, body = self.stub.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/api/sessions")
        self.assertEqual(urllib.parse.parse_qs(query), {"cwd": [str(worktree)]})
        self.assertIsNone(body)
        self.assertEqual(
            self.stub.requests[1],
            ("GET", "/api/sessions/sess-adopt/status", "", None),
        )
        self.assertEqual([item for item in self.stub.requests if item[0] == "POST"], [])
        self.assertEqual((worktree / ".stream").read_text(encoding="utf-8"), str(stream_dir) + "\n")
        common = git(worktree, self.env, "rev-parse", "--git-common-dir").strip()
        common_path = Path(common)
        if not common_path.is_absolute():
            common_path = (worktree / common_path).resolve()
        exclude = (common_path / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        self.assertIn("/.stream", exclude)
        self.assertEqual(git(worktree, self.env, "status", "--porcelain"), "")
        cells = (stream_dir / "threads.tsv").read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(
            cells[:9],
            [
                "sess-adopt",
                "review",
                "alpha",
                str(worktree),
                "feat-a",
                base,
                "openai-codex/gpt-6-astra",
                "xhigh",
                "active",
            ],
        )
        self.assertRegex(cells[9], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(
            git(self.home, self.env, "log", "-1", "--format=%s").strip(),
            "pi-streams thread adopt etl sess-adopt",
        )

    def test_adopt_refuses_an_archived_session(self) -> None:
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stream_dir = (self.home / "etl").resolve()
        stream_dir.mkdir()
        (stream_dir / "STREAM.md").write_text("ratified: no\n", encoding="utf-8")
        (stream_dir / "threads.tsv").write_text(HEADER, encoding="utf-8")
        worktree = self.fx.alpha_wt.resolve()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [
                {"id": "sess-old", "cwd": str(worktree), "messageCount": 9, "archived": True},
            ]),
        ])
        refused = self.run_streams(
            "thread", "adopt", "etl", "sess-old", "--worktree", str(worktree), "--role", "review"
        )
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(refused.stderr, "session sess-old is archived\n")
        self.assertEqual((stream_dir / "threads.tsv").read_text(encoding="utf-8"), HEADER)
        self.assertFalse((worktree / ".stream").exists())


if __name__ == "__main__":
    unittest.main()
