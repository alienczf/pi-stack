"""Each stream is its own git repo. The index holds ALERTS."""
from __future__ import annotations

from pathlib import Path

from support import EngineCase, git, pi_stack_revision
from tick_support import PROMPTS, got_prompt, info, row, status


def status_body(sid: str) -> dict[str, object]:
    return {
        "sessionId": sid,
        "isStreaming": False,
        "contextUsage": {"tokens": 10},
        "model": {"provider": "openai-codex", "id": "gpt-6-astra"},
        "thinkingLevel": "xhigh",
        "cost": 0,
    }


class PerStreamTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.stub.requests.clear()

    def _routes(self, sid: str, stream_id: str) -> list[tuple[str, str, int, object]]:
        return [
            ("GET", "/api/sessions", 200, []),
            ("POST", "/api/sessions", 200, {"id": sid, "cwd": str(self.home / stream_id)}),
            ("POST", f"/api/sessions/{sid}/model", 200, {}),
            ("POST", f"/api/sessions/{sid}/thinking-level", 200, {}),
            ("GET", f"/api/sessions/{sid}/status", 200, status_body(sid)),
            ("POST", f"/api/sessions/{sid}/prompt", 200, {"accepted": True}),
        ]

    def _new(self, stream_id: str, sid: str) -> Path:
        self.stub.set_routes(self._routes(sid, stream_id))
        proc = self.run_streams("new", stream_id)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, f"http://127.0.0.1:8504\n{sid}\n")
        return (self.home / stream_id).resolve()

    def test_two_new_streams_are_two_git_repos(self) -> None:
        one = self._new("one", "coord-1")
        two = self._new("two", "coord-2")
        self.assertTrue((one / ".git").is_dir())
        self.assertTrue((two / ".git").is_dir())
        self.assertFalse((self.home / ".git").exists())
        self.assertFalse((self.index / ".git").exists())
        self.assertEqual(
            (one / "stream.toml").read_text(encoding="utf-8"),
            f'project = "proj"\npi_stack_revision = "{pi_stack_revision()}"\nstate_schema = 1\n',
        )
        self.assertNotIn("../context/README.md", (one / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn("context/README.md", (one / "AGENTS.md").read_text(encoding="utf-8"))
        alpha = str(self.fx.alpha.resolve())
        self.assertEqual(
            (one / "context" / "README.md").read_text(encoding="utf-8"),
            "# Shared context\n"
            "\n"
            f"alpha\t{alpha}\t{alpha}/AGENTS.md\n"
            f"beta\t{self.fx.beta.resolve()}\n"
            f"gamma\t{self.fx.gamma.resolve()}\n",
        )
        head_two = git(two, self.env, "rev-parse", "HEAD")
        (one / "STATE.md").write_text((one / "STATE.md").read_text().replace("## Rules\n\n", "## Rules\nKeep this stream apart.\n\n"), encoding="utf-8")
        git(one, self.env, "add", "-A")
        git(one, self.env, "commit", "-m", "one only")
        self.assertNotEqual(git(one, self.env, "rev-parse", "HEAD"), head_two)
        self.assertEqual(git(two, self.env, "rev-parse", "HEAD"), head_two)
        self.assertEqual(git(two, self.env, "status", "--porcelain"), "")

    def test_a_shared_worktree_writes_one_claim_line_in_the_index(self) -> None:
        one = self._new("one", "coord-1")
        two = self._new("two", "coord-2")
        for stream in (one, two):
            state = stream / "STATE.md"
            state.write_text(state.read_text().replace("ratified: no", "ratified: 2026-10-23 fixture human confirmation", 1))
        self.stub.reflect_delivery_ids = True
        shared = "/wt/shared"
        (one / "threads.tsv").write_text(
            (one / "threads.tsv").read_text(encoding="utf-8") + row("t-1", "worker", shared),
            encoding="utf-8",
        )
        (two / "threads.tsv").write_text(
            (two / "threads.tsv").read_text(encoding="utf-8") + row("t-2", "reviewer", shared),
            encoding="utf-8",
        )
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True)),
            ("GET", "/api/sessions/t-2/status", 200, status("t-2", streaming=True)),
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1")),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2")),
            ("GET", "/api/sessions", 200, [
                info("coord-1", str(one), str(self.tmp / "coord-1.jsonl")),
                info("coord-2", str(two), str(self.tmp / "coord-2.jsonl")),
                info("t-1", shared, str(self.tmp / "t-1.jsonl")),
                info("t-2", shared, str(self.tmp / "t-2.jsonl")),
            ]),
            PROMPTS,
        ])
        self.env["PI_STREAMS_NOW"] = "2026-10-06T12:00:00Z"
        proc = self.run_streams("tick")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            (self.index / "ALERTS").read_text(encoding="utf-8"),
            "2026-10-06T12:00:00Z claim one/t-1,two/t-2 worker and reviewer share worktree /wt/shared\n",
        )
        self.assertFalse((one / "ALERTS").exists())
        self.assertFalse((two / "ALERTS").exists())
        self.assertIn('"kind": "claim"', (one / "log" / "events.jsonl").read_text(encoding="utf-8"))
        self.assertIn('"kind": "claim"', (two / "log" / "events.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(
            self.stub.requests[-1],
            self.delivery_prompt(
                "coord-2",
                "pi-streams tick 2026-10-06T12:00:00Z:\n"
                "claim t-2 reviewer shares worktree /wt/shared with one worker t-1",
            ),
        )

    def test_log_is_uncommitted(self) -> None:
        one = self._new("one", "coord-1")
        log = one / "log" / "events.jsonl"
        log.parent.mkdir(exist_ok=True)
        log.write_text("{}\n", encoding="utf-8")
        self.assertEqual(git(one, self.env, "status", "--porcelain"), "")
        self.assertEqual(git(one, self.env, "check-ignore", "log/events.jsonl"), "log/events.jsonl\n")

    def test_upgrade_preserves_owned_state_history_and_retired_originals(self) -> None:
        one = self._new("one", "coord-1")
        kept = "KEEP\n"
        (one / "STATE.md").write_text(kept, encoding="utf-8")
        (one / "STREAM.md").write_text("retired original bytes\n", encoding="utf-8")
        (one / "history" / "owned.md").write_text("cold exact bytes\n", encoding="utf-8")
        toml = one / "stream.toml"
        toml.write_text(toml.read_text(encoding="utf-8").replace(pi_stack_revision(), "0" * 40), encoding="utf-8")
        git(one, self.env, "add", "-A")
        git(one, self.env, "commit", "-m", "old revision")
        proc = self.run_streams("upgrade", "one")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((one / "STATE.md").read_text(encoding="utf-8"), kept)
        self.assertEqual((one / "STREAM.md").read_text(encoding="utf-8"), "retired original bytes\n")
        self.assertEqual((one / "history" / "owned.md").read_text(encoding="utf-8"), "cold exact bytes\n")
        self.assertEqual(
            toml.read_text(encoding="utf-8"),
            f'project = "proj"\npi_stack_revision = "{pi_stack_revision()}"\nstate_schema = 1\n',
        )
        self.assertEqual(git(one, self.env, "log", "-1", "--format=%s"), "pi-streams upgrade one\n")
        self.assertEqual(git(one, self.env, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"), "stream.toml\n")


if __name__ == "__main__":
    unittest.main()
