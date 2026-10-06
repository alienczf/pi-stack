"""thread spawn creates a worktree and sends the brief."""
from __future__ import annotations

import urllib.parse
from pathlib import Path

from support import EngineCase, git

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"


def status_body(sid: str) -> dict[str, object]:
    return {
        "sessionId": sid,
        "isStreaming": False,
        "contextUsage": {"tokens": 10},
        "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
        "thinkingLevel": "xhigh",
        "cost": 0,
    }


def expected_brief(stream_dir: str, worktree: str, base: str) -> str:
    return (
        "You are a thread of stream etl.\n"
        f"Your working directory is {worktree}. The stream folder is {stream_dir}.\n"
        f"Role: datapull. Repo: alpha. Branch: stream/etl/datapull. Base: {base}.\n"
        "\n"
        f"Read {stream_dir}/STREAM.md. Restate its goal and acceptance in your first reply before working.\n"
        "\n"
        f"Stay in {worktree}. Never write outside it. Verify on the real artifact.\n"
        "\n"
        "ship the slice\n"
        "\n"
        f"Before you stop, write {stream_dir}/handover/datapull.md with intent, "
        "what was done with proof, what is left, and what the next agent should know.\n"
    )


class SpawnTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.stream_dir = (self.home / "etl").resolve()
        self.stream_dir.mkdir()
        (self.stream_dir / "STREAM.md").write_text("ratified: no\n", encoding="utf-8")
        (self.stream_dir / "threads.tsv").write_text(HEADER, encoding="utf-8")
        self.stub.requests.clear()

    def assert_call(self, index: int, method: str, path: str, body: object, cwd: str | None = None) -> None:
        got_method, got_path, query, got_body = self.stub.requests[index]
        self.assertEqual(got_method, method)
        self.assertEqual(got_path, path)
        self.assertEqual(got_body, body)
        if cwd is None:
            self.assertEqual(query, "")
        else:
            self.assertEqual(urllib.parse.parse_qs(query), {"cwd": [cwd]})

    def test_spawn_creates_worktree_and_sends_the_brief(self) -> None:
        base = git(self.fx.alpha, self.env, "rev-parse", "HEAD").strip()
        worktree = (self.root / ".worktrees" / "alpha" / "etl-datapull").resolve()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "thread-1"}),
            ("GET", "/api/sessions/thread-1/status", 200, status_body("thread-1")),
            ("POST", "/api/sessions/thread-1/prompt", 200, {"accepted": True}),
        ])
        proc = self.spawn_datapull()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "thread-1\n")
        self.assertEqual(len(self.stub.requests), 6)
        self.assert_call(0, "GET", "/api/sessions", None, cwd=str(worktree))
        self.assert_call(1, "POST", "/api/sessions", {"cwd": str(worktree)})
        self.assert_call(
            2,
            "POST",
            "/api/sessions/thread-1/model",
            {"provider": "openai-codex", "modelId": "gpt-6-astra"},
        )
        self.assert_call(3, "POST", "/api/sessions/thread-1/thinking-level", {"level": "xhigh"})
        self.assert_call(4, "GET", "/api/sessions/thread-1/status", None)
        self.assert_call(
            5,
            "POST",
            "/api/sessions/thread-1/prompt",
            {"text": expected_brief(str(self.stream_dir), str(worktree), base)},
        )
        self.assertEqual(git(worktree, self.env, "branch", "--show-current").strip(), "stream/etl/datapull")
        self.assertEqual(git(worktree, self.env, "rev-parse", "HEAD").strip(), base)
        self.assertEqual((worktree / ".stream").read_text(encoding="utf-8"), str(self.stream_dir) + "\n")
        common = git(worktree, self.env, "rev-parse", "--git-common-dir").strip()
        common_path = Path(common)
        if not common_path.is_absolute():
            common_path = (worktree / common_path).resolve()
        exclude = (common_path / "info" / "exclude").read_text(encoding="utf-8").splitlines()
        self.assertIn("/.stream", exclude)
        self.assertEqual(git(worktree, self.env, "status", "--porcelain"), "")
        self.assertEqual(git(self.fx.alpha, self.env, "status", "--porcelain"), "")
        cells = (self.stream_dir / "threads.tsv").read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(
            cells[:9],
            [
                "thread-1",
                "datapull",
                "alpha",
                str(worktree),
                "stream/etl/datapull",
                base,
                "openai-codex/gpt-6-astra",
                "xhigh",
                "active",
            ],
        )
        self.assertRegex(cells[9], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(git(self.home, self.env, "log", "-1", "--format=%s").strip(), "pi-streams thread spawn etl datapull")
        head = git(self.home, self.env, "rev-parse", "HEAD")
        before = len(self.stub.requests)
        again = self.spawn_datapull()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(again.stdout, "thread-1\n")
        self.assertEqual(self.stub.requests[before:], [])
        self.assertEqual(git(self.home, self.env, "rev-parse", "HEAD"), head)

    def spawn_datapull(self):
        return self.run_streams(
            "thread",
            "spawn",
            "etl",
            "--repo",
            "alpha",
            "--role",
            "datapull",
            "--note",
            "ship the slice",
        )

    def test_failed_brief_is_resent_on_rerun(self) -> None:
        base = git(self.fx.alpha, self.env, "rev-parse", "HEAD").strip()
        worktree = (self.root / ".worktrees" / "alpha" / "etl-datapull").resolve()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "thread-1"}),
            ("GET", "/api/sessions/thread-1/status", 200, status_body("thread-1")),
            ("POST", "/api/sessions/thread-1/prompt", 503, {"error": "busy"}),
        ])
        failed = self.spawn_datapull()
        self.assertEqual(failed.returncode, 1)
        self.assertEqual((self.stream_dir / "threads.tsv").read_text(encoding="utf-8"), HEADER)
        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [
                {"id": "old-1", "cwd": str(worktree), "messageCount": 40, "archived": True},
                {"id": "thread-1", "cwd": str(worktree), "messageCount": 0},
            ]),
            ("GET", "/api/sessions/thread-1/status", 200, status_body("thread-1")),
            ("POST", "/api/sessions/thread-1/prompt", 200, {"accepted": True}),
        ])
        again = self.spawn_datapull()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(again.stdout, "thread-1\n")
        self.assertEqual(
            [(method, path) for method, path, _query, _body in self.stub.requests],
            [
                ("GET", "/api/sessions"),
                ("POST", "/api/sessions/thread-1/model"),
                ("POST", "/api/sessions/thread-1/thinking-level"),
                ("GET", "/api/sessions/thread-1/status"),
                ("POST", "/api/sessions/thread-1/prompt"),
            ],
        )
        self.assert_call(
            4,
            "POST",
            "/api/sessions/thread-1/prompt",
            {"text": expected_brief(str(self.stream_dir), str(worktree), base)},
        )
        cells = (self.stream_dir / "threads.tsv").read_text(encoding="utf-8").splitlines()[1].split("\t")
        self.assertEqual(cells[:2], ["thread-1", "datapull"])

    def test_successor_in_an_archived_threads_worktree_keeps_its_base(self) -> None:
        base = git(self.fx.alpha, self.env, "rev-parse", "HEAD").strip()
        worktree = (self.root / ".worktrees" / "alpha" / "etl-datapull").resolve()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": "thread-1"}),
            ("GET", "/api/sessions/thread-1/status", 200, status_body("thread-1")),
            ("POST", "/api/sessions/thread-1/prompt", 200, {"accepted": True}),
        ])
        self.assertEqual(self.spawn_datapull().returncode, 0)
        rows = (self.stream_dir / "threads.tsv").read_text(encoding="utf-8")
        (self.stream_dir / "threads.tsv").write_text(rows.replace("\tactive\t", "\tarchived\t"), encoding="utf-8")
        (self.fx.alpha / "later").write_text("later\n", encoding="utf-8")
        git(self.fx.alpha, self.env, "add", "-A")
        git(self.fx.alpha, self.env, "commit", "-m", "later")
        self.stub.requests.clear()
        self.stub.set_routes([
            ("GET", "/api/sessions", 200, [
                {"id": "thread-1", "cwd": str(worktree), "messageCount": 80, "archived": True},
            ]),
            ("POST", "/api/sessions", 200, {"id": "thread-2"}),
            ("GET", "/api/sessions/thread-2/status", 200, status_body("thread-2")),
            ("POST", "/api/sessions/thread-2/prompt", 200, {"accepted": True}),
        ])
        successor = self.spawn_datapull()
        self.assertEqual(successor.returncode, 0, successor.stderr)
        self.assertEqual(successor.stdout, "thread-2\n")
        self.assert_call(
            5,
            "POST",
            "/api/sessions/thread-2/prompt",
            {"text": expected_brief(str(self.stream_dir), str(worktree), base)},
        )
        lines = (self.stream_dir / "threads.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            [line.split("\t")[0] + " " + line.split("\t")[5] + " " + line.split("\t")[8] for line in lines[1:]],
            [f"thread-1 {base} archived", f"thread-2 {base} active"],
        )


if __name__ == "__main__":
    unittest.main()
